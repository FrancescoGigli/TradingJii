"""
🗄️ Training Data Database Module

Manages SQLite database for ML training data:
- training_data: OHLCV + 16 indicators for ML training
  - Date aligned between 15m and 1h timeframes
  - No NULL values (warmup candles are fetched but discarded)
- backfill_status: Tracks download progress per symbol/timeframe
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

# Warmup period - extra candles to fetch for indicator calculation
WARMUP_CANDLES = 200


class BackfillStatus(Enum):
    """Status of data backfill for a symbol/timeframe"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"


@dataclass
class BackfillInfo:
    """Information about backfill status"""
    symbol: str
    timeframe: str
    status: BackfillStatus
    oldest_timestamp: Optional[datetime] = None
    newest_timestamp: Optional[datetime] = None
    total_candles: int = 0
    warmup_candles: int = 0
    training_candles: int = 0
    completeness_pct: float = 0.0
    gap_count: int = 0
    last_update: Optional[datetime] = None
    error_message: Optional[str] = None


class TrainingDatabase:
    """
    SQLite Database manager for ML training data.
    
    Creates and manages:
    - training_data: OHLCV + 16 technical indicators
      - Date aligned between timeframes
      - No NULL values
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
        """Initialize database tables for training data"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        # Training Data table (OHLCV + 16 indicators)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS training_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                
                -- OHLCV
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                
                -- Technical Indicators (16 total - NO NULL values)
                sma_20 REAL NOT NULL,
                sma_50 REAL NOT NULL,
                ema_12 REAL NOT NULL,
                ema_26 REAL NOT NULL,
                bb_upper REAL NOT NULL,
                bb_mid REAL NOT NULL,
                bb_lower REAL NOT NULL,
                macd REAL NOT NULL,
                macd_signal REAL NOT NULL,
                macd_hist REAL NOT NULL,
                rsi REAL NOT NULL,
                stoch_k REAL NOT NULL,
                stoch_d REAL NOT NULL,
                atr REAL NOT NULL,
                volume_sma REAL NOT NULL,
                obv REAL NOT NULL,
                
                -- Metadata
                fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(symbol, timeframe, timestamp)
            )
        ''')
        
        # Indexes for fast queries
        cur.execute('CREATE INDEX IF NOT EXISTS idx_train_symbol ON training_data(symbol)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_train_timeframe ON training_data(timeframe)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_train_timestamp ON training_data(timestamp)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_train_symbol_tf ON training_data(symbol, timeframe)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_train_symbol_tf_ts ON training_data(symbol, timeframe, timestamp)')
        
        # Backfill Status table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS backfill_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                oldest_timestamp TEXT,
                warmup_start TEXT,
                training_start TEXT,
                newest_timestamp TEXT,
                total_candles INTEGER DEFAULT 0,
                warmup_candles INTEGER DEFAULT 0,
                training_candles INTEGER DEFAULT 0,
                completeness_pct REAL DEFAULT 0.0,
                gap_count INTEGER DEFAULT 0,
                last_update TEXT DEFAULT CURRENT_TIMESTAMP,
                error_message TEXT,
                UNIQUE(symbol, timeframe)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("🗄️ Training database initialized (2 tables: training_data, backfill_status)")
    
    # =========================================
    # BACKFILL STATUS OPERATIONS
    # =========================================
    
    def init_backfill_status(self, symbol: str, timeframe: str):
        """Initialize backfill status for a symbol/timeframe if not exists"""
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
        
        # Build update query dynamically
        updates = []
        params = []
        
        if status is not None:
            updates.append("status = ?")
            params.append(status.value if isinstance(status, BackfillStatus) else status)
        
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
        
        updates.append("last_update = datetime('now')")
        
        params.extend([symbol, timeframe])
        
        cur.execute(f'''
            UPDATE backfill_status
            SET {', '.join(updates)}
            WHERE symbol = ? AND timeframe = ?
        ''', params)
        
        conn.commit()
        conn.close()
    
    def get_backfill_status(self, symbol: str, timeframe: str) -> Optional[BackfillInfo]:
        """Get backfill status for a symbol/timeframe"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT symbol, timeframe, status, oldest_timestamp, newest_timestamp,
                   total_candles, warmup_candles, training_candles,
                   completeness_pct, gap_count, last_update, error_message
            FROM backfill_status
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return BackfillInfo(
            symbol=row['symbol'],
            timeframe=row['timeframe'],
            status=BackfillStatus(row['status']),
            oldest_timestamp=datetime.strptime(row['oldest_timestamp'], '%Y-%m-%d %H:%M:%S') if row['oldest_timestamp'] else None,
            newest_timestamp=datetime.strptime(row['newest_timestamp'], '%Y-%m-%d %H:%M:%S') if row['newest_timestamp'] else None,
            total_candles=row['total_candles'] or 0,
            warmup_candles=row['warmup_candles'] or 0,
            training_candles=row['training_candles'] or 0,
            completeness_pct=row['completeness_pct'] or 0.0,
            gap_count=row['gap_count'] or 0,
            last_update=datetime.strptime(row['last_update'], '%Y-%m-%d %H:%M:%S') if row['last_update'] else None,
            error_message=row['error_message']
        )
    
    def get_all_backfill_status(self) -> List[BackfillInfo]:
        """Get backfill status for all symbol/timeframe pairs"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT symbol, timeframe, status, oldest_timestamp, newest_timestamp,
                   total_candles, warmup_candles, training_candles,
                   completeness_pct, gap_count, last_update, error_message
            FROM backfill_status
            ORDER BY symbol, timeframe
        ''')
        
        results = []
        for row in cur.fetchall():
            results.append(BackfillInfo(
                symbol=row['symbol'],
                timeframe=row['timeframe'],
                status=BackfillStatus(row['status']),
                oldest_timestamp=datetime.strptime(row['oldest_timestamp'], '%Y-%m-%d %H:%M:%S') if row['oldest_timestamp'] else None,
                newest_timestamp=datetime.strptime(row['newest_timestamp'], '%Y-%m-%d %H:%M:%S') if row['newest_timestamp'] else None,
                total_candles=row['total_candles'] or 0,
                warmup_candles=row['warmup_candles'] or 0,
                training_candles=row['training_candles'] or 0,
                completeness_pct=row['completeness_pct'] or 0.0,
                gap_count=row['gap_count'] or 0,
                last_update=datetime.strptime(row['last_update'], '%Y-%m-%d %H:%M:%S') if row['last_update'] else None,
                error_message=row['error_message']
            ))
        
        conn.close()
        return results
    
    def get_pending_backfills(self) -> List[Tuple[str, str]]:
        """Get list of (symbol, timeframe) pairs with PENDING status"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT symbol, timeframe FROM backfill_status
            WHERE status = 'PENDING'
            ORDER BY symbol, timeframe
        ''')
        
        results = [(row['symbol'], row['timeframe']) for row in cur.fetchall()]
        conn.close()
        return results
    
    # =========================================
    # SAVE OPERATIONS
    # =========================================
    
    def save_training_data(
        self, 
        symbol: str, 
        timeframe: str, 
        df: pd.DataFrame
    ) -> int:
        """
        Save OHLCV candles with indicators to training_data table.
        Only saves rows where ALL indicators are valid (no NULL).
        
        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe (e.g., '15m')
            df: DataFrame with OHLCV data and indicators (must have datetime index)
            
        Returns:
            Number of candles saved
        """
        if df is None or df.empty:
            return 0
        
        conn = self._get_connection()
        cur = conn.cursor()
        
        # Prepare data
        data = df.reset_index()
        if 'timestamp' not in data.columns and df.index.name == 'timestamp':
            data = data.reset_index()
        
        # Convert timestamp to string if datetime
        if 'timestamp' in data.columns:
            if pd.api.types.is_datetime64_any_dtype(data['timestamp']):
                data['timestamp'] = data['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        # Indicator columns (all required)
        indicator_cols = [
            'sma_20', 'sma_50', 'ema_12', 'ema_26',
            'bb_upper', 'bb_mid', 'bb_lower',
            'macd', 'macd_signal', 'macd_hist',
            'rsi', 'stoch_k', 'stoch_d', 'atr',
            'volume_sma', 'obv'
        ]
        
        count = 0
        skipped = 0
        
        for _, row in data.iterrows():
            try:
                # Check if all indicators are valid (not NULL)
                has_all_indicators = True
                for col in indicator_cols:
                    val = row.get(col, None)
                    if val is None or pd.isna(val):
                        has_all_indicators = False
                        break
                
                if not has_all_indicators:
                    skipped += 1
                    continue
                
                # Build insert query
                cols = 'symbol, timeframe, timestamp, open, high, low, close, volume'
                placeholders = '?, ?, ?, ?, ?, ?, ?, ?'
                values = [
                    symbol, timeframe, row['timestamp'],
                    float(row['open']), float(row['high']), 
                    float(row['low']), float(row['close']), 
                    float(row['volume'])
                ]
                
                # Add all indicators
                for col in indicator_cols:
                    cols += f', {col}'
                    placeholders += ', ?'
                    values.append(float(row[col]))
                
                cols += ', fetched_at'
                placeholders += ', ?'
                values.append(now)
                
                cur.execute(f'''
                    INSERT OR REPLACE INTO training_data 
                    ({cols})
                    VALUES ({placeholders})
                ''', values)
                count += 1
                
            except Exception as e:
                logger.warning(f"Error saving candle {symbol}[{timeframe}] {row.get('timestamp', 'N/A')}: {e}")
                skipped += 1
        
        conn.commit()
        conn.close()
        
        if skipped > 0:
            logger.info(f"  ⚠️ Skipped {skipped} candles with NULL indicators (warmup period)")
        
        return count
    
    def clear_training_data(self, symbol: str = None, timeframe: str = None):
        """Clear training data (optionally filtered by symbol/timeframe)"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        if symbol and timeframe:
            cur.execute('DELETE FROM training_data WHERE symbol = ? AND timeframe = ?', 
                       (symbol, timeframe))
        elif symbol:
            cur.execute('DELETE FROM training_data WHERE symbol = ?', (symbol,))
        elif timeframe:
            cur.execute('DELETE FROM training_data WHERE timeframe = ?', (timeframe,))
        else:
            cur.execute('DELETE FROM training_data')
        
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"🗑️ Cleared {deleted} rows from training_data")
        return deleted
    
    # =========================================
    # READ OPERATIONS
    # =========================================
    
    def get_training_data(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = None
    ) -> pd.DataFrame:
        """
        Get training data with all indicators from database.
        All rows guaranteed to have no NULL values.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe
            start_date: Start of date range (optional)
            end_date: End of date range (optional)
            limit: Maximum rows to return (optional)
            
        Returns:
            DataFrame with OHLCV + 16 indicators, datetime index
        """
        conn = self._get_connection()
        
        query = '''
            SELECT timestamp, open, high, low, close, volume,
                   sma_20, sma_50, ema_12, ema_26,
                   bb_upper, bb_mid, bb_lower,
                   macd, macd_signal, macd_hist,
                   rsi, stoch_k, stoch_d, atr,
                   volume_sma, obv
            FROM training_data
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
            FROM training_data
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
            SELECT COUNT(*) FROM training_data
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        
        count = cur.fetchone()[0]
        conn.close()
        return count
    
    def get_symbols(self) -> List[str]:
        """Get all symbols with training data"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('SELECT DISTINCT symbol FROM training_data ORDER BY symbol')
        symbols = [row[0] for row in cur.fetchall()]
        
        conn.close()
        return symbols
    
    def get_timeframes(self, symbol: str = None) -> List[str]:
        """Get available timeframes"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        if symbol:
            cur.execute('SELECT DISTINCT timeframe FROM training_data WHERE symbol = ?', (symbol,))
        else:
            cur.execute('SELECT DISTINCT timeframe FROM training_data')
        
        timeframes = [row[0] for row in cur.fetchall()]
        conn.close()
        return timeframes
    
    # =========================================
    # STATISTICS
    # =========================================
    
    def get_stats(self) -> Dict:
        """Get overall database statistics"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('SELECT COUNT(DISTINCT symbol) FROM training_data')
        symbols_count = cur.fetchone()[0] or 0
        
        cur.execute('SELECT COUNT(DISTINCT timeframe) FROM training_data')
        tf_count = cur.fetchone()[0] or 0
        
        cur.execute('SELECT COUNT(*) FROM training_data')
        candles_count = cur.fetchone()[0] or 0
        
        cur.execute('SELECT MIN(timestamp), MAX(timestamp) FROM training_data')
        time_range = cur.fetchone()
        
        conn.close()
        
        # Database file size
        db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
        
        return {
            'symbols': symbols_count,
            'timeframes': tf_count,
            'total_candles': candles_count,
            'min_date': time_range[0] if time_range else None,
            'max_date': time_range[1] if time_range else None,
            'db_size_mb': db_size / (1024 * 1024)
        }
    
    def get_symbol_stats(self) -> List[Dict]:
        """Get per-symbol statistics"""
        conn = self._get_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT symbol, timeframe, 
                   COUNT(*) as candles,
                   MIN(timestamp) as start_date,
                   MAX(timestamp) as end_date
            FROM training_data
            GROUP BY symbol, timeframe
            ORDER BY symbol, timeframe
        ''')
        
        results = []
        for row in cur.fetchall():
            results.append({
                'symbol': row[0],
                'timeframe': row[1],
                'candles': row[2],
                'start_date': row[3],
                'end_date': row[4]
            })
        
        conn.close()
        return results
    
    def print_stats(self):
        """Print database statistics"""
        stats = self.get_stats()
        
        print(colored("\n" + "="*60, "cyan"))
        print(colored("📊 TRAINING DATA STATISTICS", "cyan", attrs=['bold']))
        print(colored("="*60, "cyan"))
        print(colored(f"  📈 Unique symbols: {stats['symbols']}", "white"))
        print(colored(f"  ⏰ Timeframes: {stats['timeframes']}", "white"))
        print(colored(f"  🕯️ Total candles: {stats['total_candles']:,}", "white"))
        print(colored(f"  💾 DB Size: {stats['db_size_mb']:.2f} MB", "white"))
        if stats['min_date'] and stats['max_date']:
            print(colored(f"  📅 Date range: {stats['min_date'][:10]} → {stats['max_date'][:10]}", "white"))
        print(colored("="*60, "cyan"))
    
    # =========================================
    # UTILITY
    # =========================================
    
    def get_symbols_from_data_fetcher(self) -> List[str]:
        """
        Get symbol list from the data-fetcher's top_symbols table.
        """
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute('SELECT symbol FROM top_symbols ORDER BY rank ASC')
            symbols = [row['symbol'] for row in cur.fetchall()]
        except sqlite3.OperationalError:
            symbols = []
        
        conn.close()
        return symbols


def align_date_to_hour(dt: datetime) -> datetime:
    """Align datetime to the nearest hour (for 15m/1h alignment)"""
    return dt.replace(minute=0, second=0, microsecond=0)


def get_aligned_date_range(
    start_date: datetime, 
    end_date: datetime
) -> Tuple[datetime, datetime]:
    """
    Get date range aligned to hour boundaries.
    Both 15m and 1h candles will have same start/end hours.
    
    Args:
        start_date: Requested start date
        end_date: Requested end date
        
    Returns:
        Tuple of (aligned_start, aligned_end) at hour boundaries
    """
    # Align start to next hour if not on hour
    aligned_start = align_date_to_hour(start_date)
    if aligned_start < start_date:
        aligned_start += timedelta(hours=1)
    
    # Align end to previous hour if not on hour
    aligned_end = align_date_to_hour(end_date)
    
    return aligned_start, aligned_end
