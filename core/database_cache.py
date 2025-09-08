"""
🗄️ DATABASE CACHE SYSTEM

Sistema di cache basato su SQLite per dati OHLCV che permette:
- Query efficienti sui dati storici
- Update incrementali robusti
- Controllo completo dei dati
- Backup/restore semplice
- Transazioni ACID per sicurezza
"""

import sqlite3
import pandas as pd
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from termcolor import colored
import os

class DatabaseCache:
    """Sistema di cache intelligente basato su SQLite"""
    
    def __init__(self, db_path="data_cache/trading_data.db"):
        """
        Initialize database cache system
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        
        # Performance tracking
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'incremental_updates': 0,
            'full_downloads': 0,
            'total_api_calls_saved': 0,
            'session_start': datetime.now().isoformat()
        }
        
        self.init_database()
        self.load_stats()
        # Silenced: logging.info(f"🗄️ Database Cache initialized: {self.db_path}")
    
    def init_database(self):
        """Initialize database tables and indexes"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create enhanced data table with all indicators (GAME CHANGER!)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS enhanced_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        -- OHLCV Base Data (5 columns)
                        open REAL NOT NULL,
                        high REAL NOT NULL,
                        low REAL NOT NULL,
                        close REAL NOT NULL,
                        volume REAL NOT NULL,
                        -- Technical Indicators (28 columns)
                        ema5 REAL, ema10 REAL, ema20 REAL,
                        macd REAL, macd_signal REAL, macd_histogram REAL,
                        rsi_fast REAL, stoch_rsi REAL,
                        atr REAL, bollinger_hband REAL, bollinger_lband REAL,
                        volatility REAL, vwap REAL, obv REAL, adx REAL,
                        -- Swing Probability Features (13 columns)
                        price_pos_5 REAL, price_pos_10 REAL, price_pos_20 REAL,
                        vol_acceleration REAL, atr_norm_move REAL, momentum_divergence REAL,
                        volatility_squeeze REAL, resistance_dist_10 REAL, resistance_dist_20 REAL,
                        support_dist_10 REAL, support_dist_20 REAL, price_acceleration REAL,
                        vol_price_alignment REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, timeframe, timestamp)
                    )
                ''')
                
                # Keep legacy OHLCV table for backward compatibility
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ohlcv_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        open REAL NOT NULL,
                        high REAL NOT NULL,
                        low REAL NOT NULL,
                        close REAL NOT NULL,
                        volume REAL NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, timeframe, timestamp)
                    )
                ''')
                
                # Create performance tracking table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS cache_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_start DATETIME NOT NULL,
                        cache_hits INTEGER DEFAULT 0,
                        cache_misses INTEGER DEFAULT 0,
                        incremental_updates INTEGER DEFAULT 0,
                        full_downloads INTEGER DEFAULT 0,
                        total_api_calls_saved INTEGER DEFAULT 0,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create indexes for efficient queries
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_symbol_timeframe_timestamp 
                    ON ohlcv_data(symbol, timeframe, timestamp)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON ohlcv_data(timestamp)
                ''')
                
                # Create indexes for enhanced_data table (PERFORMANCE CRITICAL!)
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_enhanced_symbol_timeframe_timestamp 
                    ON enhanced_data(symbol, timeframe, timestamp)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_enhanced_timestamp 
                    ON enhanced_data(timestamp)
                ''')
                
                conn.commit()
                # Silenced: logging.info("🗄️ Database tables and indexes created/verified")
                
        except Exception as e:
            logging.error(f"❌ Database initialization failed: {e}")
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with optimized settings"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        
        # Optimize SQLite performance
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
        conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes
        conn.execute("PRAGMA cache_size=-64000")   # 64MB cache
        conn.execute("PRAGMA temp_store=MEMORY")   # Temp tables in memory
        
        return conn
    
    def load_stats(self):
        """Load performance statistics from database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT cache_hits, cache_misses, incremental_updates, 
                           full_downloads, total_api_calls_saved
                    FROM cache_stats 
                    ORDER BY updated_at DESC 
                    LIMIT 1
                ''')
                
                result = cursor.fetchone()
                if result:
                    keys = ['cache_hits', 'cache_misses', 'incremental_updates', 'full_downloads', 'total_api_calls_saved']
                    for i, key in enumerate(keys):
                        self.stats[key] += result[i] or 0
                        
        except Exception as e:
            logging.warning(f"Could not load database stats: {e}")
    
    def save_stats(self):
        """Save current performance statistics to database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO cache_stats 
                    (session_start, cache_hits, cache_misses, incremental_updates, 
                     full_downloads, total_api_calls_saved, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    self.stats['session_start'],
                    self.stats['cache_hits'],
                    self.stats['cache_misses'], 
                    self.stats['incremental_updates'],
                    self.stats['full_downloads'],
                    self.stats['total_api_calls_saved']
                ))
                conn.commit()
                
        except Exception as e:
            logging.warning(f"Could not save database stats: {e}")
    
    def get_cached_data(self, symbol: str, timeframe: str, limit_days: int = 90) -> Optional[pd.DataFrame]:
        """
        Recupera dati dal database per simbolo/timeframe
        
        Args:
            symbol: Simbolo (es. 'DOGE/USDT:USDT')
            timeframe: Timeframe (es. '15m')
            limit_days: Giorni di dati da recuperare
            
        Returns:
            DataFrame con dati OHLCV o None se non trovati
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=limit_days)
            
            with self.get_connection() as conn:
                df = pd.read_sql_query('''
                    SELECT timestamp, open, high, low, close, volume
                    FROM ohlcv_data 
                    WHERE symbol = ? AND timeframe = ? AND timestamp >= ?
                    ORDER BY timestamp ASC
                ''', conn, params=(symbol, timeframe, cutoff_date))
                
                if len(df) > 0:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                    
                    self.stats['cache_hits'] += 1
                    logging.debug(f"🗄️ DB hit: {symbol}[{timeframe}] - {len(df)} candles")
                    return df
                else:
                    self.stats['cache_misses'] += 1
                    return None
                    
        except Exception as e:
            logging.warning(f"❌ Database read failed for {symbol}[{timeframe}]: {e}")
            self.stats['cache_misses'] += 1
            return None
    
    def save_data_to_db(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """
        Salva DataFrame nel database
        
        Args:
            symbol: Simbolo
            timeframe: Timeframe
            df: DataFrame con dati OHLCV
        """
        try:
            if df is None or len(df) == 0:
                return
            
            # Validate inputs
            if not isinstance(symbol, str) or not isinstance(timeframe, str):
                logging.error(f"Invalid parameter types: symbol={type(symbol)}, timeframe={type(timeframe)}")
                return
                
            # Prepare data for insertion with proper type conversion
            data_records = []
            for timestamp, row in df.iterrows():
                try:
                    # Ensure timestamp is properly formatted
                    if hasattr(timestamp, 'strftime'):
                        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        timestamp_str = str(timestamp)
                    
                    # Convert all numeric values to float with validation
                    open_val = float(row['open']) if pd.notna(row['open']) else 0.0
                    high_val = float(row['high']) if pd.notna(row['high']) else 0.0
                    low_val = float(row['low']) if pd.notna(row['low']) else 0.0
                    close_val = float(row['close']) if pd.notna(row['close']) else 0.0
                    volume_val = float(row['volume']) if pd.notna(row['volume']) else 0.0
                    
                    data_records.append((
                        str(symbol), str(timeframe), timestamp_str,
                        open_val, high_val, low_val, close_val, volume_val
                    ))
                    
                except Exception as row_error:
                    logging.warning(f"Skipping invalid row for {symbol}[{timeframe}]: {row_error}")
                    continue
            
            if not data_records:
                logging.warning(f"No valid data records to save for {symbol}[{timeframe}]")
                return
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Use INSERT OR REPLACE for upsert behavior
                cursor.executemany('''
                    INSERT OR REPLACE INTO ohlcv_data 
                    (symbol, timeframe, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', data_records)
                
                # Cleanup old data to maintain retention
                cutoff_date = datetime.now() - timedelta(days=90)
                cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    DELETE FROM ohlcv_data 
                    WHERE timestamp < ?
                ''', (cutoff_str,))
                
                conn.commit()
                logging.debug(f"🗄️ DB save: {symbol}[{timeframe}] - {len(data_records)} candles saved")
                
        except Exception as e:
            logging.error(f"❌ Database save failed for {symbol}[{timeframe}]: {e}")
    
    def get_enhanced_cached_data(self, symbol: str, timeframe: str, limit_days: int = 90) -> Optional[pd.DataFrame]:
        """
        🚀 ENHANCED: Recupera dati completi con indicatori dal database (GAME CHANGER!)
        
        Args:
            symbol: Simbolo (es. 'DOGE/USDT:USDT')
            timeframe: Timeframe (es. '15m')
            limit_days: Giorni di dati da recuperare
            
        Returns:
            DataFrame con OHLCV + tutti gli indicatori o None se non trovati
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=limit_days)
            
            with self.get_connection() as conn:
                # Get ALL columns from enhanced_data table
                df = pd.read_sql_query('''
                    SELECT timestamp, open, high, low, close, volume,
                           ema5, ema10, ema20, macd, macd_signal, macd_histogram,
                           rsi_fast, stoch_rsi, atr, bollinger_hband, bollinger_lband,
                           volatility, vwap, obv, adx,
                           price_pos_5, price_pos_10, price_pos_20,
                           vol_acceleration, atr_norm_move, momentum_divergence,
                           volatility_squeeze, resistance_dist_10, resistance_dist_20,
                           support_dist_10, support_dist_20, price_acceleration,
                           vol_price_alignment
                    FROM enhanced_data 
                    WHERE symbol = ? AND timeframe = ? AND timestamp >= ?
                    ORDER BY timestamp ASC
                ''', conn, params=(symbol, timeframe, cutoff_date))
                
                if len(df) > 0:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                    
                    self.stats['cache_hits'] += 1
                    symbol_short = symbol.replace('/USDT:USDT', '')
                    logging.debug(f"🚀 Enhanced DB hit: {symbol_short}[{timeframe}] - {len(df)} candles with ALL indicators")
                    return df
                else:
                    self.stats['cache_misses'] += 1
                    return None
                    
        except Exception as e:
            logging.warning(f"❌ Enhanced database read failed for {symbol}[{timeframe}]: {e}")
            self.stats['cache_misses'] += 1
            return None
    
    def save_enhanced_data_to_db(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """
        🚀 ENHANCED: Salva DataFrame completo con indicatori nel database (GAME CHANGER!)
        
        Args:
            symbol: Simbolo
            timeframe: Timeframe
            df: DataFrame con OHLCV + tutti gli indicatori
        """
        try:
            if df is None or len(df) == 0:
                return
            
            # Expected columns from EXPECTED_COLUMNS in config.py
            expected_cols = [
                'open', 'high', 'low', 'close', 'volume',
                'ema5', 'ema10', 'ema20', 'macd', 'macd_signal', 'macd_histogram',
                'rsi_fast', 'stoch_rsi', 'atr', 'bollinger_hband', 'bollinger_lband',
                'vwap', 'obv', 'adx', 'volatility',
                'price_pos_5', 'price_pos_10', 'price_pos_20',
                'vol_acceleration', 'atr_norm_move', 'momentum_divergence',
                'volatility_squeeze', 'resistance_dist_10', 'resistance_dist_20',
                'support_dist_10', 'support_dist_20', 'price_acceleration',
                'vol_price_alignment'
            ]
            
            # Check if DataFrame has all required columns
            missing_cols = [col for col in expected_cols if col not in df.columns]
            if missing_cols:
                logging.warning(f"Missing columns for enhanced save {symbol}[{timeframe}]: {missing_cols}")
                # Fallback to legacy save
                self.save_data_to_db(symbol, timeframe, df)
                return
            
            # Prepare data for insertion with ALL indicators
            data_records = []
            for timestamp, row in df.iterrows():
                try:
                    # Ensure timestamp is properly formatted
                    if hasattr(timestamp, 'strftime'):
                        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        timestamp_str = str(timestamp)
                    
                    # Convert all values to float with validation
                    values = [str(symbol), str(timeframe), timestamp_str]
                    
                    for col in expected_cols:
                        val = float(row[col]) if pd.notna(row[col]) else 0.0
                        values.append(val)
                    
                    data_records.append(tuple(values))
                    
                except Exception as row_error:
                    logging.warning(f"Skipping invalid enhanced row for {symbol}[{timeframe}]: {row_error}")
                    continue
            
            if not data_records:
                logging.warning(f"No valid enhanced data records to save for {symbol}[{timeframe}]")
                return
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Create column list for INSERT
                col_names = ', '.join(['symbol', 'timeframe', 'timestamp'] + expected_cols)
                placeholders = ', '.join(['?'] * (3 + len(expected_cols)))
                
                # Use INSERT OR REPLACE for upsert behavior on enhanced table
                cursor.executemany(f'''
                    INSERT OR REPLACE INTO enhanced_data 
                    ({col_names})
                    VALUES ({placeholders})
                ''', data_records)
                
                # Cleanup old data to maintain retention
                cutoff_date = datetime.now() - timedelta(days=90)
                cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    DELETE FROM enhanced_data 
                    WHERE timestamp < ?
                ''', (cutoff_str,))
                
                conn.commit()
                
                symbol_short = symbol.replace('/USDT:USDT', '')
                logging.debug(f"🚀 Enhanced DB save: {symbol_short}[{timeframe}] - {len(data_records)} candles with ALL indicators")
                
        except Exception as e:
            logging.error(f"❌ Enhanced database save failed for {symbol}[{timeframe}]: {e}")
            # Fallback to legacy save
            try:
                self.save_data_to_db(symbol, timeframe, df)
            except:
                pass

    def get_last_timestamp(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """Ottieni timestamp dell'ultima candela nel database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT MAX(timestamp) 
                    FROM ohlcv_data 
                    WHERE symbol = ? AND timeframe = ?
                ''', (symbol, timeframe))
                
                result = cursor.fetchone()
                if result and result[0]:
                    return pd.to_datetime(result[0]).to_pydatetime()
                return None
                
        except Exception as e:
            logging.warning(f"Could not get last timestamp for {symbol}[{timeframe}]: {e}")
            return None
    
    def get_data_info(self, symbol: str, timeframe: str) -> Dict:
        """Ottieni informazioni sui dati disponibili"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_candles,
                        MIN(timestamp) as first_candle,
                        MAX(timestamp) as last_candle
                    FROM ohlcv_data 
                    WHERE symbol = ? AND timeframe = ?
                ''', (symbol, timeframe))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'total_candles': result[0],
                        'first_candle': result[1],
                        'last_candle': result[2],
                        'has_data': result[0] > 0
                    }
                return {'has_data': False}
                
        except Exception as e:
            logging.error(f"Error getting data info for {symbol}[{timeframe}]: {e}")
            return {'has_data': False}
    
    def get_cache_stats(self) -> Dict:
        """Get cache performance statistics"""
        total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            'total_requests': total_requests,
            'hit_rate_pct': hit_rate
        }
    
    def get_database_size(self) -> str:
        """Get database file size for monitoring"""
        try:
            size_bytes = self.db_path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            return f"{size_mb:.1f} MB"
        except:
            return "Unknown"
    
    def get_database_summary(self) -> Dict:
        """Get complete database summary"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Count total symbols and data points
                cursor.execute('''
                    SELECT 
                        COUNT(DISTINCT symbol) as unique_symbols,
                        COUNT(DISTINCT timeframe) as unique_timeframes,
                        COUNT(*) as total_candles,
                        MIN(timestamp) as oldest_data,
                        MAX(timestamp) as newest_data
                    FROM ohlcv_data
                ''')
                
                result = cursor.fetchone()
                if result:
                    return {
                        'db_size': self.get_database_size(),
                        'unique_symbols': result[0],
                        'unique_timeframes': result[1], 
                        'total_candles': result[2],
                        'oldest_data': result[3],
                        'newest_data': result[4]
                    }
                return {}
                
        except Exception as e:
            logging.error(f"Error getting database summary: {e}")
            return {}


class SmartDatabaseManager:
    """Gestore intelligente che usa il database per cache"""
    
    def __init__(self, db_cache: DatabaseCache):
        self.db_cache = db_cache
    
    async def get_ohlcv_smart(self, exchange, symbol: str, timeframe: str, limit: int = 1000) -> Optional[pd.DataFrame]:
        """
        🧠 SMART DATABASE FETCHING
        
        Strategia intelligente con database:
        1. Controlla ultima candela nel DB
        2. Se dati vecchi/mancanti, aggiornamento incrementale
        3. Se DB vuoto, download completo
        4. Salva tutto nel DB per query future
        """
        try:
            symbol_short = symbol.replace('/USDT:USDT', '')
            
            # Check what data we have in database
            data_info = self.db_cache.get_data_info(symbol, timeframe)
            last_timestamp = self.db_cache.get_last_timestamp(symbol, timeframe)
            
            if not data_info['has_data']:
                # No data in database - full download needed
                logging.info(colored(f"🗄️ {symbol_short}[{timeframe}]: No DB data, full download", "yellow"))
                
                from fetcher import get_data_async
                df = await get_data_async(exchange, symbol, timeframe, limit)
                
                if df is not None:
                    # Save to database
                    self.db_cache.save_data_to_db(symbol, timeframe, df)
                    self.db_cache.stats['full_downloads'] += 1
                    logging.debug(f"🗄️ {symbol_short}[{timeframe}]: Saved {len(df)} candles to DB")
                    
                return df
                
            else:
                # Check if update needed
                now = datetime.utcnow()
                last_utc = last_timestamp.replace(tzinfo=None) if last_timestamp.tzinfo else last_timestamp
                age_minutes = (now - last_utc).total_seconds() / 60
                
                if age_minutes <= 3:
                    # Data is fresh, load from database
                    cached_data = self.db_cache.get_cached_data(symbol, timeframe)
                    self.db_cache.stats['total_api_calls_saved'] += 1
                    logging.debug(f"⚡ {symbol_short}[{timeframe}]: Using DB cache ({age_minutes:.1f}m old)")
                    return cached_data
                    
                else:
                    # Incremental update needed
                    logging.debug(f"🔄 {symbol_short}[{timeframe}]: DB update needed ({age_minutes:.1f}m old)")
                    
                    # Fetch only recent data since last timestamp
                    since_dt = last_utc - timedelta(hours=1)
                    since = int(since_dt.timestamp() * 1000)
                    
                    try:
                        new_ohlcv = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100, since=since)
                        
                        if new_ohlcv:
                            # Convert new data to DataFrame
                            new_df = pd.DataFrame(new_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                            new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms')
                            new_df.set_index('timestamp', inplace=True)
                            new_df.sort_index(inplace=True)
                            
                            # Save new data to database (will merge automatically)
                            self.db_cache.save_data_to_db(symbol, timeframe, new_df)
                            
                            # Return complete dataset from database
                            complete_data = self.db_cache.get_cached_data(symbol, timeframe)
                            
                            self.db_cache.stats['incremental_updates'] += 1
                            self.db_cache.stats['total_api_calls_saved'] += 8
                            
                            logging.debug(f"📈 {symbol_short}[{timeframe}]: +{len(new_df)} new candles added to DB")
                            return complete_data
                            
                        else:
                            # No new data, return cached
                            cached_data = self.db_cache.get_cached_data(symbol, timeframe)
                            self.db_cache.stats['total_api_calls_saved'] += 1
                            return cached_data
                            
                    except Exception as fetch_error:
                        logging.warning(f"Incremental fetch failed for {symbol}: {fetch_error}")
                        # Fallback to cached data
                        return self.db_cache.get_cached_data(symbol, timeframe)
            
        except Exception as e:
            logging.error(f"❌ Smart DB fetch failed for {symbol}[{timeframe}]: {e}")
            # Final fallback: normal fetch without cache
            try:
                from fetcher import get_data_async
                return await get_data_async(exchange, symbol, timeframe, limit)
            except:
                return None


class DatabaseQueryManager:
    """Manager per query avanzate sui dati storici"""
    
    def __init__(self, db_cache: DatabaseCache):
        self.db_cache = db_cache
    
    def query_symbol_data(self, symbol: str, timeframe: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Query dati per simbolo specifico con filtri data"""
        try:
            query = '''
                SELECT timestamp, open, high, low, close, volume
                FROM ohlcv_data 
                WHERE symbol = ? AND timeframe = ?
            '''
            params = [symbol, timeframe]
            
            if start_date:
                query += ' AND timestamp >= ?'
                params.append(start_date)
                
            if end_date:
                query += ' AND timestamp <= ?'
                params.append(end_date)
                
            query += ' ORDER BY timestamp ASC'
            
            with self.db_cache.get_connection() as conn:
                df = pd.read_sql_query(query, conn, params=params)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                return df
                
        except Exception as e:
            logging.error(f"Query failed for {symbol}[{timeframe}]: {e}")
            return pd.DataFrame()
    
    def get_available_symbols(self) -> List[str]:
        """Ottieni lista di tutti i simboli disponibili nel database"""
        try:
            with self.db_cache.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT symbol FROM ohlcv_data ORDER BY symbol')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Error getting available symbols: {e}")
            return []
    
    def get_available_timeframes(self, symbol: str = None) -> List[str]:
        """Ottieni timeframes disponibili (opzionalmente per simbolo specifico)"""
        try:
            with self.db_cache.get_connection() as conn:
                cursor = conn.cursor()
                if symbol:
                    cursor.execute('SELECT DISTINCT timeframe FROM ohlcv_data WHERE symbol = ? ORDER BY timeframe', (symbol,))
                else:
                    cursor.execute('SELECT DISTINCT timeframe FROM ohlcv_data ORDER BY timeframe')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Error getting available timeframes: {e}")
            return []


# Global instances
global_db_cache = DatabaseCache()
global_db_manager = SmartDatabaseManager(global_db_cache)
global_query_manager = DatabaseQueryManager(global_db_cache)


def display_database_stats():
    """Display comprehensive database statistics"""
    try:
        cache_stats = global_db_cache.get_cache_stats()
        db_summary = global_db_cache.get_database_summary()
        
        print(colored("\n🗄️ DATABASE CACHE STATISTICS", "cyan", attrs=['bold']))
        print(colored("=" * 80, "cyan"))
        print(colored(f"📊 Cache Hit Rate: {cache_stats['hit_rate_pct']:.1f}% ({cache_stats['cache_hits']}/{cache_stats['total_requests']})", "green"))
        print(colored(f"🚀 API Calls Saved: {cache_stats['total_api_calls_saved']}", "green"))
        print(colored(f"📈 Incremental Updates: {cache_stats['incremental_updates']}", "yellow"))
        print(colored(f"📥 Full Downloads: {cache_stats['full_downloads']}", "yellow"))
        
        if db_summary:
            print(colored(f"💾 Database Size: {db_summary['db_size']}", "blue"))
            print(colored(f"📊 Symbols in DB: {db_summary['unique_symbols']}", "blue"))
            print(colored(f"📈 Timeframes: {db_summary['unique_timeframes']}", "blue"))
            print(colored(f"🕯️ Total Candles: {db_summary['total_candles']:,}", "blue"))
            if db_summary.get('oldest_data') and db_summary.get('newest_data'):
                print(colored(f"📅 Data Range: {db_summary['oldest_data'][:10]} to {db_summary['newest_data'][:10]}", "blue"))
        
        print(colored("=" * 80, "cyan"))
        
        # Save stats
        global_db_cache.save_stats()
        
    except Exception as e:
        logging.warning(f"Error displaying database stats: {e}")


async def fetch_with_database(exchange, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """🗄️ DATABASE-AWARE FETCHING WRAPPER"""
    return await global_db_manager.get_ohlcv_smart(exchange, symbol, timeframe)
