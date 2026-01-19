"""
🗄️ Database Cache Module - SQLite Storage

Manages SQLite database for:
- Top 100 symbols with volume (updated on startup/manual refresh)
- Real-time OHLCV candles with indicators (updated every 15 minutes)
"""

import sqlite3
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

import pandas as pd
from termcolor import colored

# Database path from environment
SHARED_DATA_PATH = os.getenv("SHARED_DATA_PATH", "/app/shared")
DB_PATH = f"{SHARED_DATA_PATH}/data_cache/trading_data.db"


class DatabaseCache:
    """SQLite Database Cache for crypto data"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._ensure_path()
        self._init_db()
    
    def _ensure_path(self):
        """Ensure database directory exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def _init_db(self):
        """Initialize database tables"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        # =========================================
        # TABLE 1: top_symbols
        # =========================================
        cur.execute('''
            CREATE TABLE IF NOT EXISTS top_symbols (
                symbol TEXT PRIMARY KEY,
                rank INTEGER,
                volume_24h REAL,
                fetched_at TEXT
            )
        ''')
        
        # =========================================
        # TABLE 2: update_status
        # =========================================
        cur.execute('''
            CREATE TABLE IF NOT EXISTS update_status (
                id INTEGER PRIMARY KEY DEFAULT 1,
                status TEXT DEFAULT 'IDLE',
                last_update TEXT,
                last_update_duration_sec REAL,
                symbols_updated INTEGER DEFAULT 0,
                candles_updated INTEGER DEFAULT 0,
                CHECK (id = 1)
            )
        ''')
        
        # Insert default status if not exists
        cur.execute('''
            INSERT OR IGNORE INTO update_status (id, status) VALUES (1, 'IDLE')
        ''')
        
        # =========================================
        # TABLE 3: realtime_ohlcv (MAIN TABLE)
        # =========================================
        cur.execute('''
            CREATE TABLE IF NOT EXISTS realtime_ohlcv (
                symbol TEXT,
                timeframe TEXT,
                timestamp TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                
                -- Technical Indicators (16 total)
                sma_20 REAL,
                sma_50 REAL,
                ema_12 REAL,
                ema_26 REAL,
                bb_upper REAL,
                bb_mid REAL,
                bb_lower REAL,
                macd REAL,
                macd_signal REAL,
                macd_hist REAL,
                rsi REAL,
                stoch_k REAL,
                stoch_d REAL,
                atr REAL,
                volume_sma REAL,
                obv REAL,
                
                PRIMARY KEY (symbol, timeframe, timestamp)
            )
        ''')
        
        cur.execute('CREATE INDEX IF NOT EXISTS idx_rt_symbol ON realtime_ohlcv(symbol)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_rt_timeframe ON realtime_ohlcv(timeframe)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_rt_timestamp ON realtime_ohlcv(timestamp)')
        
        conn.commit()
        conn.close()
        
        logging.info("🗄️ Database initialized (3 tables: top_symbols, update_status, realtime_ohlcv)")
    
    # =========================================
    # TOP SYMBOLS METHODS
    # =========================================
    
    def save_top_symbols(self, symbols_with_volume: List[Tuple[str, float]]):
        """
        Save top symbols list to database.
        Replaces existing data completely.
        
        Args:
            symbols_with_volume: List of (symbol, volume_24h) tuples
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        # Clear existing data
        cur.execute('DELETE FROM top_symbols')
        
        # Insert new data
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        for rank, (symbol, volume) in enumerate(symbols_with_volume, 1):
            cur.execute('''
                INSERT OR REPLACE INTO top_symbols (symbol, rank, volume_24h, fetched_at)
                VALUES (?, ?, ?, ?)
            ''', (symbol, rank, volume, now))
        
        conn.commit()
        conn.close()
        
        logging.info(f"💾 Saved {len(symbols_with_volume)} top symbols")
    
    def get_top_symbols(self) -> List[Dict]:
        """
        Get all top symbols with their volumes and ranks.
        
        Returns:
            List of dicts with symbol, rank, volume_24h, fetched_at
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT symbol, rank, volume_24h, fetched_at 
            FROM top_symbols 
            ORDER BY rank ASC
        ''')
        
        results = []
        for row in cur.fetchall():
            results.append({
                'symbol': row[0],
                'rank': row[1],
                'volume_24h': row[2],
                'fetched_at': row[3]
            })
        
        conn.close()
        return results
    
    def get_top_symbols_list(self) -> List[str]:
        """Get only symbol names ordered by rank"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('SELECT symbol FROM top_symbols ORDER BY rank ASC')
        symbols = [row[0] for row in cur.fetchall()]
        
        conn.close()
        return symbols
    
    # =========================================
    # REALTIME OHLCV METHODS
    # =========================================
    
    def save_realtime_data(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """
        Save OHLCV data with indicators to realtime_ohlcv table.
        Uses INSERT OR REPLACE for upsert behavior.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            df: DataFrame with OHLCV and indicator columns
        """
        if df is None or df.empty:
            return 0
        
        conn = self._get_connection()
        cur = conn.cursor()
        
        data = df.reset_index()
        if 'timestamp' in data.columns:
            if pd.api.types.is_datetime64_any_dtype(data['timestamp']):
                data['timestamp'] = data['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Indicator columns (16 total)
        indicator_cols = [
            'sma_20', 'sma_50', 'ema_12', 'ema_26',
            'bb_upper', 'bb_mid', 'bb_lower',
            'macd', 'macd_signal', 'macd_hist',
            'rsi', 'stoch_k', 'stoch_d', 'atr',
            'volume_sma', 'obv'
        ]
        
        count = 0
        for _, row in data.iterrows():
            try:
                # Build dynamic query with indicators
                cols = 'symbol, timeframe, timestamp, open, high, low, close, volume'
                placeholders = '?, ?, ?, ?, ?, ?, ?, ?'
                values = [
                    symbol, timeframe, row['timestamp'],
                    float(row['open']), float(row['high']), 
                    float(row['low']), float(row['close']), 
                    float(row['volume'])
                ]
                
                for col in indicator_cols:
                    cols += f', {col}'
                    placeholders += ', ?'
                    val = row.get(col, None) if hasattr(row, 'get') else (row[col] if col in row.index else None)
                    values.append(None if val is None or pd.isna(val) else float(val))
                
                cur.execute(f'''
                    INSERT OR REPLACE INTO realtime_ohlcv 
                    ({cols})
                    VALUES ({placeholders})
                ''', values)
                count += 1
            except Exception as e:
                logging.warning(f"Error saving realtime candle {symbol}[{timeframe}]: {e}")
        
        conn.commit()
        conn.close()
        return count
    
    def get_realtime_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        """Get real-time OHLCV data with indicators from database"""
        conn = self._get_connection()
        
        query = '''
            SELECT timestamp, open, high, low, close, volume,
                   sma_20, sma_50, ema_12, ema_26,
                   bb_upper, bb_mid, bb_lower,
                   macd, macd_signal, macd_hist,
                   rsi, stoch_k, stoch_d, atr,
                   volume_sma, obv
            FROM realtime_ohlcv
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
        '''
        
        df = pd.read_sql_query(query, conn, params=(symbol, timeframe, limit))
        conn.close()
        
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            df.set_index('timestamp', inplace=True)
        
        return df
    
    def get_symbols(self) -> List[str]:
        """Get all symbols with candle data"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('SELECT DISTINCT symbol FROM realtime_ohlcv ORDER BY symbol')
        symbols = [row[0] for row in cur.fetchall()]
        
        conn.close()
        return symbols
    
    def get_timeframes(self, symbol: str = None) -> List[str]:
        """Get available timeframes"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        if symbol:
            cur.execute('SELECT DISTINCT timeframe FROM realtime_ohlcv WHERE symbol = ?', (symbol,))
        else:
            cur.execute('SELECT DISTINCT timeframe FROM realtime_ohlcv')
        
        timeframes = [row[0] for row in cur.fetchall()]
        conn.close()
        return timeframes
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('SELECT COUNT(DISTINCT symbol) FROM realtime_ohlcv')
        symbols_count = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(DISTINCT timeframe) FROM realtime_ohlcv')
        tf_count = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM realtime_ohlcv')
        candles_count = cur.fetchone()[0]
        
        cur.execute('SELECT MIN(timestamp), MAX(timestamp) FROM realtime_ohlcv')
        time_range = cur.fetchone()
        
        # Top symbols stats
        cur.execute('SELECT COUNT(*) FROM top_symbols')
        top_count = cur.fetchone()[0]
        
        conn.close()
        
        # Database file size
        db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
        
        return {
            'symbols': symbols_count or 0,
            'timeframes': tf_count or 0,
            'candles': candles_count or 0,
            'min_date': time_range[0] if time_range else None,
            'max_date': time_range[1] if time_range else None,
            'top_symbols_count': top_count or 0,
            'db_size_mb': db_size / (1024 * 1024)
        }
    
    def print_db_stats(self):
        """Print database statistics"""
        stats = self.get_stats()
        
        print(colored("\n" + "="*60, "cyan"))
        print(colored("🗄️ DATABASE STATISTICS", "cyan", attrs=['bold']))
        print(colored("="*60, "cyan"))
        print(colored(f"  📊 Unique symbols: {stats['symbols']}", "white"))
        print(colored(f"  ⏰ Timeframes: {stats['timeframes']}", "white"))
        print(colored(f"  🕯️ Total candles: {stats['candles']:,}", "white"))
        print(colored(f"  💾 DB Size: {stats['db_size_mb']:.2f} MB", "white"))
        if stats['min_date'] and stats['max_date']:
            print(colored(f"  📅 Data range: {stats['min_date'][:16]} → {stats['max_date'][:16]}", "white"))
        print(colored("="*60, "cyan"))
    
    def cleanup_old_data(self, keep_candles: int = 500):
        """Cleanup old candles keeping only latest N per symbol/timeframe"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        # Get all symbol-timeframe combinations
        cur.execute('SELECT DISTINCT symbol, timeframe FROM realtime_ohlcv')
        pairs = cur.fetchall()
        
        deleted = 0
        for symbol, tf in pairs:
            cur.execute('''
                DELETE FROM realtime_ohlcv
                WHERE symbol = ? AND timeframe = ?
                AND timestamp NOT IN (
                    SELECT timestamp FROM realtime_ohlcv
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                )
            ''', (symbol, tf, symbol, tf, keep_candles))
            deleted += cur.rowcount
        
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logging.info(f"🧹 Cleaned up {deleted} old candles")
    
    # =========================================
    # UPDATE STATUS METHODS
    # =========================================
    
    def set_status_updating(self):
        """Set status to UPDATING when starting data fetch"""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute('''
            UPDATE update_status 
            SET status = 'UPDATING'
            WHERE id = 1
        ''')
        conn.commit()
        conn.close()
        logging.info("🔄 Status: UPDATING")
    
    def set_status_idle(self, symbols_updated: int = 0, candles_updated: int = 0, duration_sec: float = 0):
        """Set status to IDLE after completing data fetch"""
        conn = self._get_connection()
        cur = conn.cursor()
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        cur.execute('''
            UPDATE update_status 
            SET status = 'IDLE',
                last_update = ?,
                last_update_duration_sec = ?,
                symbols_updated = ?,
                candles_updated = ?
            WHERE id = 1
        ''', (now, duration_sec, symbols_updated, candles_updated))
        conn.commit()
        conn.close()
        logging.info(f"✅ Status: IDLE (updated {symbols_updated} symbols, {candles_updated} candles in {duration_sec:.1f}s)")
    
    def get_update_status(self) -> Dict:
        """Get current update status for frontend"""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT status, last_update, last_update_duration_sec, 
                   symbols_updated, candles_updated
            FROM update_status WHERE id = 1
        ''')
        row = cur.fetchone()
        conn.close()
        
        if row:
            return {
                'status': row[0] or 'IDLE',
                'last_update': row[1],
                'duration_sec': row[2] or 0,
                'symbols_updated': row[3] or 0,
                'candles_updated': row[4] or 0
            }
        return {
            'status': 'IDLE',
            'last_update': None,
            'duration_sec': 0,
            'symbols_updated': 0,
            'candles_updated': 0
        }
