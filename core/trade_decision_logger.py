#!/usr/bin/env python3
"""
📊 TRADE DECISION LOGGER

Sistema completo per logging persistente delle decisioni di trading con:
- Salvataggio decisioni Ensemble + RL prima dell'apertura
- Storico prezzi e indicatori tecnici durante la vita del trade
- Snapshot periodici configurabili
- Analisi post-trade complete
- Query avanzate per statistiche

Database: data_cache/trade_decisions.db
"""

import sqlite3
import logging
import threading
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from termcolor import colored
import pandas as pd


@dataclass
class TradeDecision:
    """Decisione di trading completa"""
    id: Optional[int]
    timestamp: str
    symbol: str
    signal_name: str
    position_side: str
    
    # Prezzo e sizing
    entry_price: float
    position_size: float
    leverage: int
    margin_used: float
    stop_loss: float
    
    # Decisione Ensemble XGBoost
    xgb_confidence: float
    tf_15m_vote: Optional[int]
    tf_30m_vote: Optional[int]
    tf_1h_vote: Optional[int]
    
    # Decisione RL
    rl_confidence: Optional[float]
    rl_approved: Optional[bool]
    rl_primary_reason: Optional[str]
    
    # Contesto mercato
    market_volatility: Optional[float]
    rsi_position: Optional[float]
    trend_strength: Optional[float]
    volume_surge: Optional[float]
    
    # Stato portfolio
    available_balance: float
    active_positions_count: int
    
    # Risultato (aggiornato alla chiusura)
    status: str = 'OPEN'
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    close_reason: Optional[str] = None
    pnl_pct: Optional[float] = None
    pnl_usd: Optional[float] = None


@dataclass
class MarketSnapshot:
    """Snapshot di mercato per un timeframe"""
    price: float
    ema5: Optional[float] = None
    ema10: Optional[float] = None
    ema20: Optional[float] = None
    rsi: Optional[float] = None
    macd: Optional[float] = None
    atr: Optional[float] = None
    volume: Optional[float] = None


class TradeDecisionLogger:
    """
    Sistema thread-safe per logging decisioni di trading
    """
    
    def __init__(self, db_path: str = "data_cache/trade_decisions.db"):
        """
        Initialize trade decision logger
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        
        # Thread safety
        self._db_lock = threading.RLock()
        
        # Statistics
        self.stats = {
            'decisions_logged': 0,
            'snapshots_logged': 0,
            'decisions_closed': 0
        }
        
        self._init_database()
        logging.debug(f"📊 TradeDecisionLogger initialized: {self.db_path}")
    
    def _init_database(self):
        """Initialize database tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Table 1: Trading Decisions
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS trading_decisions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME NOT NULL,
                        symbol TEXT NOT NULL,
                        signal_name TEXT NOT NULL,
                        position_side TEXT NOT NULL,
                        
                        -- Price and sizing
                        entry_price REAL NOT NULL,
                        position_size REAL NOT NULL,
                        leverage INTEGER NOT NULL,
                        margin_used REAL NOT NULL,
                        stop_loss REAL NOT NULL,
                        
                        -- Ensemble XGBoost decision
                        xgb_confidence REAL NOT NULL,
                        tf_15m_vote INTEGER,
                        tf_30m_vote INTEGER,
                        tf_1h_vote INTEGER,
                        
                        -- RL decision
                        rl_confidence REAL,
                        rl_approved BOOLEAN,
                        rl_primary_reason TEXT,
                        
                        -- Market context
                        market_volatility REAL,
                        rsi_position REAL,
                        trend_strength REAL,
                        volume_surge REAL,
                        
                        -- Portfolio state
                        available_balance REAL,
                        active_positions_count INTEGER,
                        
                        -- Result (updated on close)
                        status TEXT DEFAULT 'OPEN',
                        exit_price REAL,
                        exit_time DATETIME,
                        close_reason TEXT,
                        pnl_pct REAL,
                        pnl_usd REAL
                    )
                ''')
                
                # Table 2: Market Snapshots
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS market_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        decision_id INTEGER NOT NULL,
                        snapshot_time DATETIME NOT NULL,
                        snapshot_type TEXT NOT NULL,
                        
                        -- 15m timeframe data
                        tf_15m_price REAL,
                        tf_15m_ema5 REAL,
                        tf_15m_ema10 REAL,
                        tf_15m_ema20 REAL,
                        tf_15m_rsi REAL,
                        tf_15m_macd REAL,
                        tf_15m_atr REAL,
                        tf_15m_volume REAL,
                        
                        -- 30m timeframe data
                        tf_30m_price REAL,
                        tf_30m_ema5 REAL,
                        tf_30m_ema10 REAL,
                        tf_30m_ema20 REAL,
                        tf_30m_rsi REAL,
                        tf_30m_macd REAL,
                        tf_30m_atr REAL,
                        tf_30m_volume REAL,
                        
                        -- 1h timeframe data
                        tf_1h_price REAL,
                        tf_1h_ema5 REAL,
                        tf_1h_ema10 REAL,
                        tf_1h_ema20 REAL,
                        tf_1h_rsi REAL,
                        tf_1h_macd REAL,
                        tf_1h_atr REAL,
                        tf_1h_volume REAL,
                        
                        FOREIGN KEY(decision_id) REFERENCES trading_decisions(id)
                    )
                ''')
                
                # Create indexes
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON trading_decisions(symbol)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON trading_decisions(status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON trading_decisions(timestamp DESC)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_decision_snapshots ON market_snapshots(decision_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshot_time ON market_snapshots(snapshot_time)')
                
                conn.commit()
                logging.debug("📊 Database tables created/verified")
                
        except Exception as e:
            logging.error(f"❌ Database initialization failed: {e}")
    
    def log_opening_decision(
        self,
        signal_data: Dict,
        market_context: Dict,
        position_details: Dict,
        portfolio_state: Dict,
        market_snapshots: Optional[Dict[str, pd.Series]] = None
    ) -> Optional[int]:
        """
        Log decisione di trading PRIMA dell'apertura posizione
        
        Args:
            signal_data: Dati segnale (symbol, signal_name, confidence, tf_predictions, rl_*)
            market_context: Contesto mercato (volatility, rsi, trend_strength, volume_surge)
            position_details: Dettagli posizione (entry_price, position_size, margin, stop_loss, leverage)
            portfolio_state: Stato portfolio (available_balance, active_positions)
            market_snapshots: Optional dict con Series per '15m', '30m', '1h' timeframes
            
        Returns:
            int: decision_id se successo, None se fallito
        """
        try:
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Extract data from signal_data
                    symbol = signal_data.get('symbol', '')
                    signal_name = signal_data.get('signal_name', 'BUY')
                    position_side = 'long' if signal_name == 'BUY' else 'short'
                    xgb_confidence = signal_data.get('confidence', 0.0)
                    
                    # Extract timeframe votes
                    tf_predictions = signal_data.get('tf_predictions', {})
                    tf_15m_vote = tf_predictions.get('15m')
                    tf_30m_vote = tf_predictions.get('30m')
                    tf_1h_vote = tf_predictions.get('1h')
                    
                    # Extract RL data
                    rl_confidence = signal_data.get('rl_confidence')
                    rl_approved = signal_data.get('rl_approved')
                    rl_details = signal_data.get('rl_details', {})
                    rl_primary_reason = rl_details.get('primary_reason')
                    
                    # Extract market context
                    market_volatility = market_context.get('volatility')
                    rsi_position = market_context.get('rsi_position')
                    trend_strength = market_context.get('trend_strength')
                    volume_surge = market_context.get('volume_surge')
                    
                    # Extract position details
                    entry_price = position_details.get('entry_price', 0.0)
                    position_size = position_details.get('position_size', 0.0)
                    margin_used = position_details.get('margin', 0.0)
                    stop_loss = position_details.get('stop_loss', 0.0)
                    leverage = position_details.get('leverage', 10)
                    
                    # Extract portfolio state
                    available_balance = portfolio_state.get('available_balance', 0.0)
                    active_positions_count = portfolio_state.get('active_positions', 0)
                    
                    # Insert decision
                    cursor.execute('''
                        INSERT INTO trading_decisions (
                            timestamp, symbol, signal_name, position_side,
                            entry_price, position_size, leverage, margin_used, stop_loss,
                            xgb_confidence, tf_15m_vote, tf_30m_vote, tf_1h_vote,
                            rl_confidence, rl_approved, rl_primary_reason,
                            market_volatility, rsi_position, trend_strength, volume_surge,
                            available_balance, active_positions_count,
                            status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        datetime.now().isoformat(), symbol, signal_name, position_side,
                        entry_price, position_size, leverage, margin_used, stop_loss,
                        xgb_confidence, tf_15m_vote, tf_30m_vote, tf_1h_vote,
                        rl_confidence, rl_approved, rl_primary_reason,
                        market_volatility, rsi_position, trend_strength, volume_surge,
                        available_balance, active_positions_count,
                        'OPEN'
                    ))
                    
                    decision_id = cursor.lastrowid
                    conn.commit()
                    
                    self.stats['decisions_logged'] += 1
                    
                    symbol_short = symbol.replace('/USDT:USDT', '')
                    logging.info(colored(
                        f"📊 Decision logged: {symbol_short} {signal_name} | "
                        f"XGB: {xgb_confidence:.1%} | RL: {rl_approved} | ID: {decision_id}",
                        "cyan"
                    ))
                    
                    # Log entry snapshot if provided
                    if market_snapshots:
                        self._log_market_snapshot(
                            decision_id, 'ENTRY', market_snapshots
                        )
                    
                    return decision_id
                    
        except Exception as e:
            logging.error(f"❌ Failed to log opening decision: {e}")
            return None
    
    def _log_market_snapshot(
        self,
        decision_id: int,
        snapshot_type: str,
        snapshots: Dict[str, pd.Series]
    ) -> bool:
        """
        Log market snapshot for multiple timeframes
        
        Args:
            decision_id: ID della decisione
            snapshot_type: 'ENTRY', 'PERIODIC', 'EXIT'
            snapshots: Dict con '15m', '30m', '1h' -> pd.Series
            
        Returns:
            bool: True se successo
        """
        try:
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Extract data for each timeframe
                    data = {
                        'decision_id': decision_id,
                        'snapshot_time': datetime.now().isoformat(),
                        'snapshot_type': snapshot_type
                    }
                    
                    for tf in ['15m', '30m', '1h']:
                        if tf in snapshots and snapshots[tf] is not None:
                            series = snapshots[tf]
                            prefix = f"tf_{tf.replace('m', 'm').replace('h', 'h')}_"
                            
                            # Extract indicators (safe get with defaults)
                            data[f'{prefix}price'] = float(series.get('close', 0))
                            data[f'{prefix}ema5'] = float(series.get('ema5', 0)) if 'ema5' in series else None
                            data[f'{prefix}ema10'] = float(series.get('ema10', 0)) if 'ema10' in series else None
                            data[f'{prefix}ema20'] = float(series.get('ema20', 0)) if 'ema20' in series else None
                            data[f'{prefix}rsi'] = float(series.get('rsi_fast', 0)) if 'rsi_fast' in series else None
                            data[f'{prefix}macd'] = float(series.get('macd', 0)) if 'macd' in series else None
                            data[f'{prefix}atr'] = float(series.get('atr', 0)) if 'atr' in series else None
                            data[f'{prefix}volume'] = float(series.get('volume', 0)) if 'volume' in series else None
                    
                    # Build INSERT query
                    columns = ', '.join(data.keys())
                    placeholders = ', '.join(['?' for _ in data])
                    
                    cursor.execute(f'''
                        INSERT INTO market_snapshots ({columns})
                        VALUES ({placeholders})
                    ''', tuple(data.values()))
                    
                    conn.commit()
                    self.stats['snapshots_logged'] += 1
                    
                    logging.debug(f"📊 Market snapshot logged: {snapshot_type} for decision {decision_id}")
                    return True
                    
        except Exception as e:
            logging.error(f"❌ Failed to log market snapshot: {e}")
            return False
    
    def update_closing_decision(
        self,
        symbol: str,
        entry_time: str,
        exit_price: float,
        close_reason: str,
        pnl_pct: float,
        pnl_usd: float,
        exit_snapshots: Optional[Dict[str, pd.Series]] = None
    ) -> bool:
        """
        Aggiorna decisione con dati di chiusura
        
        Args:
            symbol: Trading symbol
            entry_time: Timestamp di entrata (ISO format)
            exit_price: Prezzo di uscita
            close_reason: Motivo chiusura
            pnl_pct: PnL percentuale
            pnl_usd: PnL in USD
            exit_snapshots: Optional snapshot di mercato all'uscita
            
        Returns:
            bool: True se successo
        """
        try:
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Find decision by symbol and entry time
                    cursor.execute('''
                        SELECT id FROM trading_decisions
                        WHERE symbol = ? AND timestamp = ? AND status = 'OPEN'
                        ORDER BY id DESC LIMIT 1
                    ''', (symbol, entry_time))
                    
                    result = cursor.fetchone()
                    if not result:
                        logging.warning(f"⚠️ Decision not found for {symbol} @ {entry_time}")
                        return False
                    
                    decision_id = result[0]
                    
                    # Update decision
                    cursor.execute('''
                        UPDATE trading_decisions
                        SET status = 'CLOSED',
                            exit_price = ?,
                            exit_time = ?,
                            close_reason = ?,
                            pnl_pct = ?,
                            pnl_usd = ?
                        WHERE id = ?
                    ''', (
                        exit_price,
                        datetime.now().isoformat(),
                        close_reason,
                        pnl_pct,
                        pnl_usd,
                        decision_id
                    ))
                    
                    conn.commit()
                    self.stats['decisions_closed'] += 1
                    
                    symbol_short = symbol.replace('/USDT:USDT', '')
                    pnl_color = 'green' if pnl_pct > 0 else 'red'
                    
                    logging.info(colored(
                        f"📊 Decision closed: {symbol_short} | "
                        f"Reason: {close_reason} | PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})",
                        pnl_color
                    ))
                    
                    # Log exit snapshot if provided
                    if exit_snapshots:
                        self._log_market_snapshot(
                            decision_id, 'EXIT', exit_snapshots
                        )
                    
                    return True
                    
        except Exception as e:
            logging.error(f"❌ Failed to update closing decision: {e}")
            return False
    
    def log_periodic_snapshot(
        self,
        symbol: str,
        entry_time: str,
        snapshots: Dict[str, pd.Series]
    ) -> bool:
        """
        Log snapshot periodico durante la vita del trade
        
        Args:
            symbol: Trading symbol
            entry_time: Entry timestamp per trovare la decisione
            snapshots: Dict con snapshots per timeframe
            
        Returns:
            bool: True se successo
        """
        try:
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Find decision
                    cursor.execute('''
                        SELECT id FROM trading_decisions
                        WHERE symbol = ? AND timestamp = ? AND status = 'OPEN'
                        ORDER BY id DESC LIMIT 1
                    ''', (symbol, entry_time))
                    
                    result = cursor.fetchone()
                    if not result:
                        return False
                    
                    decision_id = result[0]
                    
                    # Log snapshot
                    return self._log_market_snapshot(
                        decision_id, 'PERIODIC', snapshots
                    )
                    
        except Exception as e:
            logging.error(f"❌ Failed to log periodic snapshot: {e}")
            return False
    
    def get_last_n_positions(
        self,
        n: int = 100,
        status: Optional[str] = None
    ) -> List[TradeDecision]:
        """
        Recupera ultime N posizioni
        
        Args:
            n: Numero di posizioni da recuperare
            status: Optional filtro per status ('OPEN', 'CLOSED', None=tutti)
            
        Returns:
            List[TradeDecision]: Lista decisioni
        """
        try:
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    if status:
                        cursor.execute('''
                            SELECT * FROM trading_decisions
                            WHERE status = ?
                            ORDER BY timestamp DESC
                            LIMIT ?
                        ''', (status, n))
                    else:
                        cursor.execute('''
                            SELECT * FROM trading_decisions
                            ORDER BY timestamp DESC
                            LIMIT ?
                        ''', (n,))
                    
                    rows = cursor.fetchall()
                    
                    decisions = []
                    for row in rows:
                        decision = TradeDecision(
                            id=row['id'],
                            timestamp=row['timestamp'],
                            symbol=row['symbol'],
                            signal_name=row['signal_name'],
                            position_side=row['position_side'],
                            entry_price=row['entry_price'],
                            position_size=row['position_size'],
                            leverage=row['leverage'],
                            margin_used=row['margin_used'],
                            stop_loss=row['stop_loss'],
                            xgb_confidence=row['xgb_confidence'],
                            tf_15m_vote=row['tf_15m_vote'],
                            tf_30m_vote=row['tf_30m_vote'],
                            tf_1h_vote=row['tf_1h_vote'],
                            rl_confidence=row['rl_confidence'],
                            rl_approved=row['rl_approved'],
                            rl_primary_reason=row['rl_primary_reason'],
                            market_volatility=row['market_volatility'],
                            rsi_position=row['rsi_position'],
                            trend_strength=row['trend_strength'],
                            volume_surge=row['volume_surge'],
                            available_balance=row['available_balance'],
                            active_positions_count=row['active_positions_count'],
                            status=row['status'],
                            exit_price=row['exit_price'],
                            exit_time=row['exit_time'],
                            close_reason=row['close_reason'],
                            pnl_pct=row['pnl_pct'],
                            pnl_usd=row['pnl_usd']
                        )
                        decisions.append(decision)
                    
                    return decisions
                    
        except Exception as e:
            logging.error(f"❌ Failed to get last N positions: {e}")
            return []
    
    def get_trade_with_snapshots(self, decision_id: int) -> Optional[Dict]:
        """
        Recupera trade completo con tutti gli snapshot
        
        Args:
            decision_id: ID della decisione
            
        Returns:
            Dict: {'decision': TradeDecision, 'snapshots': List[Dict]}
        """
        try:
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    # Get decision
                    cursor.execute('''
                        SELECT * FROM trading_decisions WHERE id = ?
                    ''', (decision_id,))
                    
                    row = cursor.fetchone()
                    if not row:
                        return None
                    
                    decision = TradeDecision(
                        id=row['id'],
                        timestamp=row['timestamp'],
                        symbol=row['symbol'],
                        signal_name=row['signal_name'],
                        position_side=row['position_side'],
                        entry_price=row['entry_price'],
                        position_size=row['position_size'],
                        leverage=row['leverage'],
                        margin_used=row['margin_used'],
                        stop_loss=row['stop_loss'],
                        xgb_confidence=row['xgb_confidence'],
                        tf_15m_vote=row['tf_15m_vote'],
                        tf_30m_vote=row['tf_30m_vote'],
                        tf_1h_vote=row['tf_1h_vote'],
                        rl_confidence=row['rl_confidence'],
                        rl_approved=row['rl_approved'],
                        rl_primary_reason=row['rl_primary_reason'],
                        market_volatility=row['market_volatility'],
                        rsi_position=row['rsi_position'],
                        trend_strength=row['trend_strength'],
                        volume_surge=row['volume_surge'],
                        available_balance=row['available_balance'],
                        active_positions_count=row['active_positions_count'],
                        status=row['status'],
                        exit_price=row['exit_price'],
                        exit_time=row['exit_time'],
                        close_reason=row['close_reason'],
                        pnl_pct=row['pnl_pct'],
                        pnl_usd=row['pnl_usd']
                    )
                    
                    # Get snapshots
                    cursor.execute('''
                        SELECT * FROM market_snapshots
                        WHERE decision_id = ?
                        ORDER BY snapshot_time ASC
                    ''', (decision_id,))
                    
                    snapshot_rows = cursor.fetchall()
                    snapshots = [dict(row) for row in snapshot_rows]
                    
                    return {
                        'decision': decision,
                        'snapshots': snapshots
                    }
                    
        except Exception as e:
            logging.error(f"❌ Failed to get trade with snapshots: {e}")
            return None
    
    def get_statistics(self) -> Dict:
        """Get logging statistics"""
        try:
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Count decisions
                    cursor.execute('SELECT COUNT(*) FROM trading_decisions')
                    total_decisions = cursor.fetchone()[0]
                    
                    cursor.execute('SELECT COUNT(*) FROM trading_decisions WHERE status = "OPEN"')
                    open_count = cursor.fetchone()[0]
                    
                    cursor.execute('SELECT COUNT(*) FROM trading_decisions WHERE status = "CLOSED"')
                    closed_count = cursor.fetchone()[0]
                    
                    # Count snapshots
                    cursor.execute('SELECT COUNT(*) FROM market_snapshots')
                    total_snapshots = cursor.fetchone()[0]
                    
                    # Win rate for closed trades
                    cursor.execute('SELECT COUNT(*) FROM trading_decisions WHERE status = "CLOSED" AND pnl_pct > 0')
                    wins = cursor.fetchone()[0]
                    
                    win_rate = (wins / closed_count * 100) if closed_count > 0 else 0
                    
                    # Average PnL
                    cursor.execute('SELECT AVG(pnl_pct), AVG(pnl_usd) FROM trading_decisions WHERE status = "CLOSED"')
                    avg_pnl_row = cursor.fetchone()
                    avg_pnl_pct = avg_pnl_row[0] or 0
                    avg_pnl_usd = avg_pnl_row[1] or 0
                    
                    return {
                        'total_decisions': total_decisions,
                        'open_positions': open_count,
                        'closed_positions': closed_count,
                        'total_snapshots': total_snapshots,
                        'win_rate_pct': win_rate,
                        'avg_pnl_pct': avg_pnl_pct,
                        'avg_pnl_usd': avg_pnl_usd,
                        **self.stats
                    }
                    
        except Exception as e:
            logging.error(f"❌ Failed to get statistics: {e}")
            return self.stats


# Global instance
global_trade_decision_logger = TradeDecisionLogger()
