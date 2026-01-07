"""
🗄️ Historical Database Module

Manages SQLite database for historical OHLCV data:
- historical_ohlcv: Long-term price data (12+ months)
- backfill_status: Progress tracking for each symbol/timeframe
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import pandas as pd
from termcolor import colored

import config

logger = logging.getLogger(__name__)


class BackfillStatus(Enum):
    """Status of backfill operation for a symbol/timeframe"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"
    NEEDS_UPDATE = "NEEDS_UPDATE"


@dataclass
class BackfillInfo:
    """Information about backfill status for a symbol/timeframe"""
    symbol: str
    timeframe: str
    status: BackfillStatus
    oldest_timestamp: Optional[datetime]
    warmup_start: Optional[datetime]
    training_start: Optional[datetime]
    newest_timestamp: Optional[datetime]
    total_candles: int
    warmup_candles: int
    training_candles: int
    completeness_pct: float
    gap_count: int
    last_update: Optional[datetime]
    error_message: Optional[str]


class HistoricalDatabase:
    """
    SQLite Database manager for historical OHLCV data.
    
    Creates and manages:
    - historical_ohlcv: Store 12+ months of candle data
    - backfill_status: Track download progress per symbol/timeframe
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        self._ensure_path()
        self._init_db()
    
    def _ensure_path(self):
        """Ensure database directory exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize database tables for historical data"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        # Historical OHLCV table (main data store for ML)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS historical_ohlcv (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                interpolated INTEGER DEFAULT 0,
                
                UNIQUE(symbol, timeframe, timestamp)
            )
        ''')
        
        # Indexes for fast queries
        cur.execute('CREATE INDEX IF NOT EXISTS idx_hist_symbol_tf ON historical_ohlcv(symbol, timeframe)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_hist_timestamp ON historical_ohlcv(timestamp)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_hist_symbol_tf_ts ON historical_ohlcv(symbol, timeframe, timestamp)')
        
        # Backfill status table (tracks progress)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS backfill_status (
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                
                -- Date range
                oldest_timestamp TEXT,
                warmup_start TEXT,
                training_start TEXT,
                newest_timestamp TEXT,
                
                -- Statistics
                total_candles INTEGER DEFAULT 0,
                warmup_candles INTEGER DEFAULT 0,
                training_candles INTEGER DEFAULT 0,
                
                -- Quality metrics
                completeness_pct REAL DEFAULT 0.0,
                gap_count INTEGER DEFAULT 0,
                
                -- Tracking
                last_update TEXT,
                error_message TEXT,
                
                PRIMARY KEY (symbol, timeframe)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("🗄️ Historical database initialized")
    
    # =========================================
    # OHLCV DATA OPERATIONS
    # =========================================
    
    def save_candles(
        self, 
        symbol: str, 
        timeframe: str, 
        df: pd.DataFrame,
        interpolated: bool = False
    ) -> int:
        """
        Save OHLCV candles to historical_ohlcv table.
        Uses INSERT OR REPLACE for upsert behavior.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe (e.g., '15m')
            df: DataFrame with OHLCV data (must have datetime index)
            interpolated: Mark candles as interpolated
            
        Returns:
            Number of candles saved
        """
        if df is None or df.empty:
            return 0
        
        conn = self._get_connection()
        cur = conn.cursor()
        
        # Prepare data
        data = df.reset_index()
        if 'timestamp' not in data.columns and data.index.name == 'timestamp':
            data = data.reset_index()
        
        # Convert timestamp to string if datetime
        if 'timestamp' in data.columns:
            if pd.api.types.is_datetime64_any_dtype(data['timestamp']):
                data['timestamp'] = data['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        interp_flag = 1 if interpolated else 0
        
        count = 0
        for _, row in data.iterrows():
            try:
                cur.execute('''
                    INSERT OR REPLACE INTO historical_ohlcv 
                    (symbol, timeframe, timestamp, open, high, low, close, volume, fetched_at, interpolated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol, timeframe, row['timestamp'],
                    float(row['open']), float(row['high']), 
                    float(row['low']), float(row['close']), 
                    float(row['volume']), now, interp_flag
                ))
                count += 1
            except Exception as e:
                logger.warning(f"Error saving candle {symbol}[{timeframe}] {row.get('timestamp', 'N/A')}: {e}")
        
        conn.commit()
        conn.close()
        
        return count
    
    def get_candles(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = None
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data from database.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe
            start_date: Start of date range (optional)
            end_date: End of date range (optional)
            limit: Maximum rows to return (optional)
            
        Returns:
            DataFrame with OHLCV data, datetime index
        """
        conn = self._get_connection()
        
        query = '''
            SELECT timestamp, open, high, low, close, volume, interpolated
            FROM historical_ohlcv
            WHERE symbol = ? AND timeframe = ?
        '''
        params = [symbol, timeframe]
        
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date.strftime('%Y-%m-%d %H:%M:%S'))
        
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date.strftime('%Y-%m-%d %H:%M:%S'))
        
        query += ' ORDER BY timestamp ASC'
        
        if limit:
            query += f' LIMIT {limit}'
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        
        return df
    
    def get_date_range(self, symbol: str, timeframe: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Get the date range of data for a symbol/timeframe"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT MIN(timestamp), MAX(timestamp)
            FROM historical_ohlcv
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        
        row = cur.fetchone()
        conn.close()
        
        if row and row[0] and row[1]:
            return (
                datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S'),
                datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S')
            )
        return None, None
    
    def get_candle_count(self, symbol: str, timeframe: str) -> int:
        """Get total candle count for a symbol/timeframe"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT COUNT(*) FROM historical_ohlcv
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        
        count = cur.fetchone()[0]
        conn.close()
        return count
    
    def get_newest_timestamp(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """Get the most recent candle timestamp for a symbol/timeframe"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT MAX(timestamp) FROM historical_ohlcv
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        
        row = cur.fetchone()
        conn.close()
        
        if row and row[0]:
            return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
        return None
    
    def get_oldest_timestamp(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """Get the oldest candle timestamp for a symbol/timeframe"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT MIN(timestamp) FROM historical_ohlcv
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        
        row = cur.fetchone()
        conn.close()
        
        if row and row[0]:
            return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
        return None
    
    # =========================================
    # BACKFILL STATUS OPERATIONS
    # =========================================
    
    def init_backfill_status(self, symbol: str, timeframe: str):
        """Initialize backfill status for a symbol/timeframe"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('''
            INSERT OR IGNORE INTO backfill_status (symbol, timeframe, status)
            VALUES (?, ?, 'PENDING')
        ''', (symbol, timeframe))
        
        conn.commit()
        conn.close()
    
    def update_backfill_status(
        self,
        symbol: str,
        timeframe: str,
        status: BackfillStatus = None,
        oldest_timestamp: datetime = None,
        warmup_start: datetime = None,
        training_start: datetime = None,
        newest_timestamp: datetime = None,
        total_candles: int = None,
        warmup_candles: int = None,
        training_candles: int = None,
        completeness_pct: float = None,
        gap_count: int = None,
        error_message: str = None
    ):
        """Update backfill status for a symbol/timeframe"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        # Build dynamic update query
        updates = []
        params = []
        
        if status is not None:
            updates.append("status = ?")
            params.append(status.value)
        
        if oldest_timestamp is not None:
            updates.append("oldest_timestamp = ?")
            params.append(oldest_timestamp.strftime('%Y-%m-%d %H:%M:%S'))
        
        if warmup_start is not None:
            updates.append("warmup_start = ?")
            params.append(warmup_start.strftime('%Y-%m-%d %H:%M:%S'))
        
        if training_start is not None:
            updates.append("training_start = ?")
            params.append(training_start.strftime('%Y-%m-%d %H:%M:%S'))
        
        if newest_timestamp is not None:
            updates.append("newest_timestamp = ?")
            params.append(newest_timestamp.strftime('%Y-%m-%d %H:%M:%S'))
        
        if total_candles is not None:
            updates.append("total_candles = ?")
            params.append(total_candles)
        
        if warmup_candles is not None:
            updates.append("warmup_candles = ?")
            params.append(warmup_candles)
        
        if training_candles is not None:
            updates.append("training_candles = ?")
            params.append(training_candles)
        
        if completeness_pct is not None:
            updates.append("completeness_pct = ?")
            params.append(completeness_pct)
        
        if gap_count is not None:
            updates.append("gap_count = ?")
            params.append(gap_count)
        
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)
        
        # Always update last_update
        updates.append("last_update = ?")
        params.append(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Add WHERE params
        params.extend([symbol, timeframe])
        
        query = f"UPDATE backfill_status SET {', '.join(updates)} WHERE symbol = ? AND timeframe = ?"
        cur.execute(query, params)
        
        conn.commit()
        conn.close()
    
    def get_backfill_status(self, symbol: str, timeframe: str) -> Optional[BackfillInfo]:
        """Get backfill status for a symbol/timeframe"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT * FROM backfill_status
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return None
        
        def parse_dt(s):
            return datetime.strptime(s, '%Y-%m-%d %H:%M:%S') if s else None
        
        return BackfillInfo(
            symbol=row['symbol'],
            timeframe=row['timeframe'],
            status=BackfillStatus(row['status']),
            oldest_timestamp=parse_dt(row['oldest_timestamp']),
            warmup_start=parse_dt(row['warmup_start']),
            training_start=parse_dt(row['training_start']),
            newest_timestamp=parse_dt(row['newest_timestamp']),
            total_candles=row['total_candles'] or 0,
            warmup_candles=row['warmup_candles'] or 0,
            training_candles=row['training_candles'] or 0,
            completeness_pct=row['completeness_pct'] or 0.0,
            gap_count=row['gap_count'] or 0,
            last_update=parse_dt(row['last_update']),
            error_message=row['error_message']
        )
    
    def get_all_backfill_status(self) -> List[BackfillInfo]:
        """Get backfill status for all symbol/timeframe combinations"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('SELECT * FROM backfill_status ORDER BY symbol, timeframe')
        rows = cur.fetchall()
        conn.close()
        
        def parse_dt(s):
            return datetime.strptime(s, '%Y-%m-%d %H:%M:%S') if s else None
        
        result = []
        for row in rows:
            result.append(BackfillInfo(
                symbol=row['symbol'],
                timeframe=row['timeframe'],
                status=BackfillStatus(row['status']),
                oldest_timestamp=parse_dt(row['oldest_timestamp']),
                warmup_start=parse_dt(row['warmup_start']),
                training_start=parse_dt(row['training_start']),
                newest_timestamp=parse_dt(row['newest_timestamp']),
                total_candles=row['total_candles'] or 0,
                warmup_candles=row['warmup_candles'] or 0,
                training_candles=row['training_candles'] or 0,
                completeness_pct=row['completeness_pct'] or 0.0,
                gap_count=row['gap_count'] or 0,
                last_update=parse_dt(row['last_update']),
                error_message=row['error_message']
            ))
        
        return result
    
    def get_pending_backfills(self) -> List[Tuple[str, str]]:
        """Get list of symbol/timeframe pairs that need backfill"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT symbol, timeframe FROM backfill_status
            WHERE status IN ('PENDING', 'IN_PROGRESS', 'NEEDS_UPDATE', 'ERROR')
            ORDER BY 
                CASE status 
                    WHEN 'IN_PROGRESS' THEN 1 
                    WHEN 'PENDING' THEN 2 
                    WHEN 'NEEDS_UPDATE' THEN 3 
                    ELSE 4 
                END
        ''')
        
        result = [(row['symbol'], row['timeframe']) for row in cur.fetchall()]
        conn.close()
        return result
    
    # =========================================
    # STATISTICS
    # =========================================
    
    def get_stats(self) -> Dict:
        """Get overall database statistics"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        # Historical data stats
        cur.execute('SELECT COUNT(DISTINCT symbol) FROM historical_ohlcv')
        symbols_count = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(DISTINCT timeframe) FROM historical_ohlcv')
        tf_count = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM historical_ohlcv')
        candles_count = cur.fetchone()[0]
        
        cur.execute('SELECT MIN(timestamp), MAX(timestamp) FROM historical_ohlcv')
        time_range = cur.fetchone()
        
        cur.execute('SELECT COUNT(*) FROM historical_ohlcv WHERE interpolated = 1')
        interpolated_count = cur.fetchone()[0]
        
        # Backfill status stats
        cur.execute('''
            SELECT status, COUNT(*) as count 
            FROM backfill_status 
            GROUP BY status
        ''')
        status_counts = {row['status']: row['count'] for row in cur.fetchall()}
        
        conn.close()
        
        # Database file size
        db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
        
        return {
            'symbols': symbols_count,
            'timeframes': tf_count,
            'total_candles': candles_count,
            'interpolated_candles': interpolated_count,
            'min_date': time_range[0],
            'max_date': time_range[1],
            'db_size_mb': db_size / (1024 * 1024),
            'status_counts': status_counts
        }
    
    def print_stats(self):
        """Print database statistics"""
        stats = self.get_stats()
        
        print(colored("\n" + "="*60, "cyan"))
        print(colored("📊 HISTORICAL DATABASE STATISTICS", "cyan", attrs=['bold']))
        print(colored("="*60, "cyan"))
        print(colored(f"  📈 Unique symbols: {stats['symbols']}", "white"))
        print(colored(f"  ⏰ Timeframes: {stats['timeframes']}", "white"))
        print(colored(f"  🕯️ Total candles: {stats['total_candles']:,}", "white"))
        print(colored(f"  🔄 Interpolated: {stats['interpolated_candles']:,}", "yellow"))
        print(colored(f"  💾 DB Size: {stats['db_size_mb']:.2f} MB", "white"))
        if stats['min_date'] and stats['max_date']:
            print(colored(f"  📅 Date range: {stats['min_date'][:10]} → {stats['max_date'][:10]}", "white"))
        
        if stats['status_counts']:
            print(colored("\n  📋 Backfill Status:", "white"))
            for status, count in stats['status_counts'].items():
                icon = "✅" if status == "COMPLETE" else "🔄" if status == "IN_PROGRESS" else "⏳" if status == "PENDING" else "❌"
                print(colored(f"     {icon} {status}: {count}", "white"))
        
        print(colored("="*60, "cyan"))
    
    def get_symbols_from_data_fetcher(self) -> List[str]:
        """
        Get symbol list from the data-fetcher's top_symbols table.
        This ensures we use the same symbols for historical data.
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute('SELECT symbol FROM top_symbols ORDER BY rank ASC')
            symbols = [row['symbol'] for row in cur.fetchall()]
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            symbols = []
        
        conn.close()
        return symbols
