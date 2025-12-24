"""
🗄️ Database Cache Module - SQLite Storage

Manages SQLite database for:
- Top 100 symbols with volume (updated on startup/manual refresh)
- OHLCV candles (200 candles per symbol, updated every 15 minutes)
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
SHARED_DATA_PATH = os.getenv("SHARED_DATA_PATH", "/app/shared/data_cache")
DB_PATH = f"{SHARED_DATA_PATH}/trading_data.db"


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
        
        # Top symbols table (static list updated on startup/manual refresh)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS top_symbols (
                symbol TEXT PRIMARY KEY,
                rank INTEGER,
                volume_24h REAL,
                fetched_at TEXT
            )
        ''')
        
        # OHLCV candles table (updated every 15 minutes)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS ohlcv_data (
                symbol TEXT,
                timeframe TEXT,
                timestamp TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY (symbol, timeframe, timestamp)
            )
        ''')
        
        cur.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON ohlcv_data(symbol)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_timeframe ON ohlcv_data(timeframe)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON ohlcv_data(timestamp)')
        
        conn.commit()
        conn.close()
        
        logging.info("🗄️ Database initialized successfully")
    
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
    
    def save_data_to_db(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """
        Save OHLCV data to database.
        Uses INSERT OR REPLACE for upsert behavior.
        """
        if df is None or df.empty:
            return
        
        conn = self._get_connection()
        cur = conn.cursor()
        
        data = df.reset_index()
        data['timestamp'] = data['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        for _, row in data.iterrows():
            cur.execute('''
                INSERT OR REPLACE INTO ohlcv_data 
                (symbol, timeframe, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol, timeframe, row['timestamp'],
                row['open'], row['high'], row['low'], row['close'], row['volume']
            ))
        
        conn.commit()
        conn.close()
    
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        """Get OHLCV data from database"""
        conn = self._get_connection()
        
        query = '''
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv_data
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
        
        cur.execute('SELECT DISTINCT symbol FROM ohlcv_data ORDER BY symbol')
        symbols = [row[0] for row in cur.fetchall()]
        
        conn.close()
        return symbols
    
    def get_timeframes(self, symbol: str = None) -> List[str]:
        """Get available timeframes"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        if symbol:
            cur.execute('SELECT DISTINCT timeframe FROM ohlcv_data WHERE symbol = ?', (symbol,))
        else:
            cur.execute('SELECT DISTINCT timeframe FROM ohlcv_data')
        
        timeframes = [row[0] for row in cur.fetchall()]
        conn.close()
        return timeframes
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('SELECT COUNT(DISTINCT symbol) FROM ohlcv_data')
        symbols_count = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(DISTINCT timeframe) FROM ohlcv_data')
        tf_count = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM ohlcv_data')
        candles_count = cur.fetchone()[0]
        
        cur.execute('SELECT MIN(timestamp), MAX(timestamp) FROM ohlcv_data')
        time_range = cur.fetchone()
        
        # Top symbols stats
        cur.execute('SELECT COUNT(*) FROM top_symbols')
        top_count = cur.fetchone()[0]
        
        conn.close()
        
        # Database file size
        db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
        
        return {
            'symbols': symbols_count,
            'timeframes': tf_count,
            'candles': candles_count,
            'min_date': time_range[0],
            'max_date': time_range[1],
            'top_symbols_count': top_count,
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
    
    def cleanup_old_data(self, keep_candles: int = 200):
        """Cleanup old candles keeping only latest N per symbol/timeframe"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        # Get all symbol-timeframe combinations
        cur.execute('SELECT DISTINCT symbol, timeframe FROM ohlcv_data')
        pairs = cur.fetchall()
        
        deleted = 0
        for symbol, tf in pairs:
            cur.execute('''
                DELETE FROM ohlcv_data
                WHERE symbol = ? AND timeframe = ?
                AND timestamp NOT IN (
                    SELECT timestamp FROM ohlcv_data
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
