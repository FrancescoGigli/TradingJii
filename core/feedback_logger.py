#!/usr/bin/env python3
"""
📊 FEEDBACK LOGGER - Adaptive Learning System

Persistent trade outcome tracking with rich context for meta-learning.
Stores all trade data in SQLite for analysis and adaptation.

FEATURES:
- Atomic trade logging with full context
- Rich technical indicators and execution metrics
- Efficient queries for statistics and calibration
- MFE/MAE tracking for exit quality analysis
- Symbol/cluster performance tracking
"""

import sqlite3
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
from contextlib import contextmanager

@dataclass
class TradeStatistics:
    """Statistics computed from trade history"""
    total_trades: int
    win_count: int
    loss_count: int
    win_rate: float
    avg_roe: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    reward_risk_ratio: float
    avg_duration_minutes: float

class FeedbackLogger:
    """
    Persistent trade outcome logger with SQLite backend
    
    Thread-safe, atomic operations, automatic schema creation
    """
    
    def __init__(self, db_path: str = "adaptive_state/trade_feedback.db"):
        """
        Initialize feedback logger
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database schema
        self._initialize_database()
        
        logging.info(f"📊 FeedbackLogger initialized: {self.db_path}")
    
    def _initialize_database(self):
        """Create database schema if not exists"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Main trades table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        -- Identity
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        strategy_version TEXT DEFAULT 'v1.0',
                        
                        -- Position Data
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        cluster TEXT DEFAULT 'DEFAULT',
                        
                        -- ML Predictions
                        confidence_raw REAL NOT NULL,
                        confidence_calibrated REAL,
                        predicted_direction TEXT,
                        model_version TEXT,
                        features_hash TEXT,
                        
                        -- Entry Data
                        entry_price REAL NOT NULL,
                        entry_time TEXT NOT NULL,
                        position_size REAL NOT NULL,
                        margin REAL NOT NULL,
                        
                        -- Technical Context at Entry
                        atr REAL DEFAULT 0,
                        volatility REAL DEFAULT 0,
                        adx REAL DEFAULT 0,
                        rsi REAL DEFAULT 0,
                        bucket_vol REAL DEFAULT 0,
                        bucket_liq REAL DEFAULT 0,
                        
                        -- Exit Data
                        exit_price REAL NOT NULL,
                        exit_time TEXT NOT NULL,
                        duration_seconds INTEGER NOT NULL,
                        close_reason TEXT,
                        
                        -- Outcomes (NET of fees/slippage)
                        roe_pct REAL NOT NULL,
                        pnl_usd REAL NOT NULL,
                        result INTEGER NOT NULL,
                        stop_hit INTEGER DEFAULT 0,
                        tp_hit INTEGER DEFAULT 0,
                        
                        -- Execution Quality Metrics
                        fees_usd REAL DEFAULT 0,
                        slippage_bp REAL DEFAULT 0,
                        spread_bp REAL DEFAULT 0,
                        latency_ms INTEGER DEFAULT 0,
                        
                        -- Price Action Analysis
                        mfe_bp REAL DEFAULT 0,
                        mae_bp REAL DEFAULT 0,
                        roe_path_hash TEXT,
                        
                        -- Adaptive System State at Trade
                        tau_global REAL DEFAULT 0.70,
                        tau_side REAL DEFAULT 0.70,
                        tau_tf REAL DEFAULT 0.70,
                        tau_cluster REAL DEFAULT 0.70,
                        kelly_fraction REAL DEFAULT 0,
                        cooldown_applied INTEGER DEFAULT 0,
                        
                        -- Penalty Score (computed)
                        penalty_score REAL DEFAULT 0
                    )
                """)
                
                # Create indexes for fast queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_symbol ON trades(symbol)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp ON trades(timestamp)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cluster ON trades(cluster)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_result ON trades(result)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_side_tf ON trades(side, timeframe)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session ON trades(session_id)
                """)
                
                conn.commit()
                logging.debug("📊 Database schema initialized/verified")
                
        except Exception as e:
            logging.error(f"❌ Database initialization failed: {e}")
            raise
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()
    
    def log_trade_outcome(self, trade_info: Dict) -> int:
        """
        Log a completed trade outcome (atomic operation)
        
        Args:
            trade_info: Dictionary with trade data (see schema for fields)
            
        Returns:
            int: Trade ID in database
        """
        try:
            # Validate required fields
            required_fields = [
                'symbol', 'side', 'timeframe', 'confidence_raw',
                'entry_price', 'entry_time', 'position_size', 'margin',
                'exit_price', 'exit_time', 'duration_seconds',
                'roe_pct', 'pnl_usd', 'result'
            ]
            
            for field in required_fields:
                if field not in trade_info:
                    logging.warning(f"⚠️ Missing required field: {field}")
                    trade_info[field] = 0 if field != 'symbol' else 'UNKNOWN'
            
            # Add timestamp if not provided
            if 'timestamp' not in trade_info:
                trade_info['timestamp'] = datetime.now().isoformat()
            
            # Add session_id if not provided
            if 'session_id' not in trade_info:
                trade_info['session_id'] = datetime.now().strftime('%Y%m%d')
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Insert trade
                cursor.execute("""
                    INSERT INTO trades (
                        timestamp, session_id, strategy_version,
                        symbol, side, timeframe, cluster,
                        confidence_raw, confidence_calibrated, predicted_direction,
                        model_version, features_hash,
                        entry_price, entry_time, position_size, margin,
                        atr, volatility, adx, rsi, bucket_vol, bucket_liq,
                        exit_price, exit_time, duration_seconds, close_reason,
                        roe_pct, pnl_usd, result, stop_hit, tp_hit,
                        fees_usd, slippage_bp, spread_bp, latency_ms,
                        mfe_bp, mae_bp, roe_path_hash,
                        tau_global, tau_side, tau_tf, tau_cluster,
                        kelly_fraction, cooldown_applied, penalty_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_info.get('timestamp'),
                    trade_info.get('session_id'),
                    trade_info.get('strategy_version', 'v1.0'),
                    trade_info.get('symbol'),
                    trade_info.get('side'),
                    trade_info.get('timeframe'),
                    trade_info.get('cluster', 'DEFAULT'),
                    trade_info.get('confidence_raw'),
                    trade_info.get('confidence_calibrated'),
                    trade_info.get('predicted_direction'),
                    trade_info.get('model_version'),
                    trade_info.get('features_hash'),
                    trade_info.get('entry_price'),
                    trade_info.get('entry_time'),
                    trade_info.get('position_size'),
                    trade_info.get('margin'),
                    trade_info.get('atr', 0),
                    trade_info.get('volatility', 0),
                    trade_info.get('adx', 0),
                    trade_info.get('rsi', 0),
                    trade_info.get('bucket_vol', 0),
                    trade_info.get('bucket_liq', 0),
                    trade_info.get('exit_price'),
                    trade_info.get('exit_time'),
                    trade_info.get('duration_seconds'),
                    trade_info.get('close_reason'),
                    trade_info.get('roe_pct'),
                    trade_info.get('pnl_usd'),
                    trade_info.get('result'),
                    trade_info.get('stop_hit', 0),
                    trade_info.get('tp_hit', 0),
                    trade_info.get('fees_usd', 0),
                    trade_info.get('slippage_bp', 0),
                    trade_info.get('spread_bp', 0),
                    trade_info.get('latency_ms', 0),
                    trade_info.get('mfe_bp', 0),
                    trade_info.get('mae_bp', 0),
                    trade_info.get('roe_path_hash'),
                    trade_info.get('tau_global', 0.70),
                    trade_info.get('tau_side', 0.70),
                    trade_info.get('tau_tf', 0.70),
                    trade_info.get('tau_cluster', 0.70),
                    trade_info.get('kelly_fraction', 0),
                    trade_info.get('cooldown_applied', 0),
                    trade_info.get('penalty_score', 0)
                ))
                
                trade_id = cursor.lastrowid
                conn.commit()
                
                logging.debug(f"📊 Trade logged: ID={trade_id}, {trade_info.get('symbol')} {trade_info.get('side')}")
                return trade_id
                
        except Exception as e:
            logging.error(f"❌ Failed to log trade: {e}")
            return -1
    
    def get_statistics(self, window: int = 100, filters: Optional[Dict] = None) -> TradeStatistics:
        """
        Get trade statistics for recent window
        
        Args:
            window: Number of recent trades to analyze
            filters: Optional filters (symbol, side, timeframe, etc.)
            
        Returns:
            TradeStatistics: Computed statistics
        """
        try:
            with self._get_connection() as conn:
                # Build query with filters
                query = "SELECT * FROM trades WHERE 1=1"
                params = []
                
                if filters:
                    if 'symbol' in filters:
                        query += " AND symbol = ?"
                        params.append(filters['symbol'])
                    if 'side' in filters:
                        query += " AND side = ?"
                        params.append(filters['side'])
                    if 'timeframe' in filters:
                        query += " AND timeframe = ?"
                        params.append(filters['timeframe'])
                    if 'cluster' in filters:
                        query += " AND cluster = ?"
                        params.append(filters['cluster'])
                
                query += " ORDER BY id DESC LIMIT ?"
                params.append(window)
                
                df = pd.read_sql_query(query, conn, params=params)
                
                if len(df) == 0:
                    return TradeStatistics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
                
                # Compute statistics
                total_trades = len(df)
                win_count = int((df['result'] == 1).sum())
                loss_count = int((df['result'] == 0).sum())
                win_rate = win_count / total_trades if total_trades > 0 else 0
                
                avg_roe = float(df['roe_pct'].mean())
                
                wins = df[df['result'] == 1]['roe_pct']
                losses = df[df['result'] == 0]['roe_pct']
                
                avg_win = float(wins.mean()) if len(wins) > 0 else 0
                avg_loss = float(losses.mean()) if len(losses) > 0 else 0
                
                total_wins = float(wins.sum()) if len(wins) > 0 else 0
                total_losses = float(abs(losses.sum())) if len(losses) > 0 else 0
                profit_factor = total_wins / total_losses if total_losses > 0 else 0
                
                reward_risk_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
                
                avg_duration_minutes = float(df['duration_seconds'].mean() / 60)
                
                return TradeStatistics(
                    total_trades=total_trades,
                    win_count=win_count,
                    loss_count=loss_count,
                    win_rate=win_rate,
                    avg_roe=avg_roe,
                    avg_win=avg_win,
                    avg_loss=avg_loss,
                    profit_factor=profit_factor,
                    reward_risk_ratio=reward_risk_ratio,
                    avg_duration_minutes=avg_duration_minutes
                )
                
        except Exception as e:
            logging.error(f"❌ Failed to get statistics: {e}")
            return TradeStatistics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    
    def get_calibration_data(self, side: str, timeframe: str, min_samples: int = 50) -> pd.DataFrame:
        """
        Get data for confidence calibration
        
        Args:
            side: Position side (LONG/SHORT)
            timeframe: Timeframe
            min_samples: Minimum samples required
            
        Returns:
            DataFrame with confidence_raw and result columns
        """
        try:
            with self._get_connection() as conn:
                query = """
                    SELECT confidence_raw, confidence_calibrated, result
                    FROM trades
                    WHERE side = ? AND timeframe = ?
                    ORDER BY id DESC
                    LIMIT 1000
                """
                
                df = pd.read_sql_query(query, conn, params=(side, timeframe))
                
                if len(df) < min_samples:
                    logging.debug(f"⚠️ Insufficient calibration data: {len(df)} < {min_samples}")
                    return pd.DataFrame()
                
                return df
                
        except Exception as e:
            logging.error(f"❌ Failed to get calibration data: {e}")
            return pd.DataFrame()
    
    def get_kelly_parameters(self, bucket: str, window: int = 200) -> Tuple[float, float, float]:
        """
        Get Kelly parameters for a bucket (symbol/cluster/timeframe)
        
        Args:
            bucket: Bucket identifier (symbol, cluster, or timeframe)
            window: Recent trades window
            
        Returns:
            Tuple[float, float, float]: (R ratio, win_prob, sigma_pnl)
        """
        try:
            with self._get_connection() as conn:
                # Try symbol filter first
                query = """
                    SELECT roe_pct, result
                    FROM trades
                    WHERE symbol = ?
                    ORDER BY id DESC
                    LIMIT ?
                """
                
                df = pd.read_sql_query(query, conn, params=(bucket, window))
                
                # If not enough data, try cluster or timeframe
                if len(df) < 30:
                    query = """
                        SELECT roe_pct, result
                        FROM trades
                        WHERE cluster = ? OR timeframe = ?
                        ORDER BY id DESC
                        LIMIT ?
                    """
                    df = pd.read_sql_query(query, conn, params=(bucket, bucket, window))
                
                if len(df) < 10:
                    # Default values if insufficient data
                    return (2.0, 0.70, 1.0)
                
                # Calculate parameters
                wins = df[df['result'] == 1]['roe_pct']
                losses = df[df['result'] == 0]['roe_pct']
                
                avg_win = abs(wins.mean()) if len(wins) > 0 else 1.0
                avg_loss = abs(losses.mean()) if len(losses) > 0 else 1.0
                
                R = avg_win / avg_loss if avg_loss > 0 else 2.0
                win_prob = len(wins) / len(df) if len(df) > 0 else 0.70
                sigma_pnl = float(df['roe_pct'].std())
                
                return (R, win_prob, sigma_pnl)
                
        except Exception as e:
            logging.error(f"❌ Failed to get Kelly parameters: {e}")
            return (2.0, 0.70, 1.0)
    
    def get_recent_trades(self, n: int = 100) -> List[Dict]:
        """
        Get N most recent trades
        
        Args:
            n: Number of trades to retrieve
            
        Returns:
            List of trade dictionaries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM trades
                    ORDER BY id DESC
                    LIMIT ?
                """, (n,))
                
                rows = cursor.fetchall()
                trades = [dict(row) for row in rows]
                
                return trades
                
        except Exception as e:
            logging.error(f"❌ Failed to get recent trades: {e}")
            return []
    
    def count_total_trades(self) -> int:
        """Get total number of trades in database"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM trades")
                count = cursor.fetchone()[0]
                return int(count)
                
        except Exception as e:
            logging.error(f"❌ Failed to count trades: {e}")
            return 0
    
    def get_symbol_performance(self, symbol: str, window: int = 50) -> Dict:
        """
        Get performance metrics for a specific symbol
        
        Args:
            symbol: Trading symbol
            window: Recent trades window
            
        Returns:
            Dict with performance metrics
        """
        try:
            stats = self.get_statistics(window=window, filters={'symbol': symbol})
            
            return {
                'symbol': symbol,
                'total_trades': stats.total_trades,
                'win_rate': stats.win_rate,
                'avg_roe': stats.avg_roe,
                'profit_factor': stats.profit_factor
            }
            
        except Exception as e:
            logging.error(f"❌ Failed to get symbol performance: {e}")
            return {}
    
    def cleanup_old_data(self, max_trades: int = 5000, max_days: int = 180):
        """
        Clean up old data to keep database size manageable
        
        Args:
            max_trades: Maximum trades to keep
            max_days: Maximum days to keep
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Get current count
                cursor.execute("SELECT COUNT(*) FROM trades")
                current_count = cursor.fetchone()[0]
                
                if current_count > max_trades:
                    # Delete oldest trades beyond limit
                    cursor.execute("""
                        DELETE FROM trades
                        WHERE id IN (
                            SELECT id FROM trades
                            ORDER BY id ASC
                            LIMIT ?
                        )
                    """, (current_count - max_trades,))
                    
                    deleted = cursor.rowcount
                    logging.info(f"🗑️ Cleaned up {deleted} old trades (limit: {max_trades})")
                
                # Also delete trades older than max_days
                cutoff_date = (datetime.now() - timedelta(days=max_days)).isoformat()
                cursor.execute("""
                    DELETE FROM trades
                    WHERE timestamp < ?
                """, (cutoff_date,))
                
                deleted_old = cursor.rowcount
                if deleted_old > 0:
                    logging.info(f"🗑️ Cleaned up {deleted_old} trades older than {max_days} days")
                
                conn.commit()
                
                # Vacuum database to reclaim space
                cursor.execute("VACUUM")
                
        except Exception as e:
            logging.error(f"❌ Cleanup failed: {e}")


# Global instance
global_feedback_logger = FeedbackLogger()
