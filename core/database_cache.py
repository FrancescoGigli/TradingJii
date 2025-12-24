"""
🗄️ DATABASE CACHE SYSTEM - Semplificato

Sistema di cache SQLite per dati OHLCV:
- Salvataggio delle ultime 1000 candele per simbolo/timeframe
- Query efficienti sui dati storici
- Statistiche sul database
"""

import sqlite3
import pandas as pd
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
from termcolor import colored
import threading

import config


class DatabaseCache:
    """Sistema di cache SQLite thread-safe per dati OHLCV"""
    
    def __init__(self, db_path=None):
        """
        Inizializza il sistema di cache
        
        Args:
            db_path: Path al database SQLite (default: data_cache/trading_data.db)
        """
        if db_path is None:
            db_path = f"{config.CACHE_DIR}/{config.DB_FILE}"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        
        # Thread safety
        self._db_lock = threading.RLock()
        
        # Statistiche
        self.stats = {
            'records_saved': 0,
            'queries_executed': 0,
            'session_start': datetime.now().isoformat()
        }
        
        self.init_database()
    
    def init_database(self):
        """Crea le tabelle del database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Tabella principale OHLCV
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
                
                # Indici per query veloci
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_symbol_timeframe_timestamp 
                    ON ohlcv_data(symbol, timeframe, timestamp)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_symbol_timeframe 
                    ON ohlcv_data(symbol, timeframe)
                ''')
                
                conn.commit()
                logging.info("🗄️ Database inizializzato correttamente")
                
        except Exception as e:
            logging.error(f"❌ Errore inizializzazione database: {e}")
    
    def get_connection(self) -> sqlite3.Connection:
        """Ottiene una connessione ottimizzata al database"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        
        # Ottimizzazioni SQLite
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")
        conn.execute("PRAGMA temp_store=MEMORY")
        
        return conn
    
    def save_data_to_db(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """
        Salva dati OHLCV nel database
        
        Args:
            symbol: Simbolo (es. 'BTC/USDT:USDT')
            timeframe: Timeframe (es. '15m')
            df: DataFrame con dati OHLCV
        """
        try:
            if df is None or len(df) == 0:
                return
            
            with self._db_lock:
                data_records = []
                
                for timestamp, row in df.iterrows():
                    try:
                        if hasattr(timestamp, 'strftime'):
                            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            timestamp_str = str(timestamp)
                        
                        data_records.append((
                            str(symbol), str(timeframe), timestamp_str,
                            float(row['open']), float(row['high']),
                            float(row['low']), float(row['close']),
                            float(row['volume'])
                        ))
                    except Exception as e:
                        logging.debug(f"Skip riga invalida: {e}")
                        continue
                
                if not data_records:
                    return
                
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Upsert dei dati
                    cursor.executemany('''
                        INSERT OR REPLACE INTO ohlcv_data 
                        (symbol, timeframe, timestamp, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', data_records)
                    
                    # Mantieni solo le ultime N candele per simbolo/timeframe
                    cursor.execute('''
                        DELETE FROM ohlcv_data 
                        WHERE symbol = ? AND timeframe = ? 
                        AND id NOT IN (
                            SELECT id FROM ohlcv_data 
                            WHERE symbol = ? AND timeframe = ?
                            ORDER BY timestamp DESC 
                            LIMIT ?
                        )
                    ''', (symbol, timeframe, symbol, timeframe, config.CANDLES_LIMIT))
                    
                    conn.commit()
                    
                self.stats['records_saved'] += len(data_records)
                symbol_short = symbol.replace('/USDT:USDT', '')
                logging.debug(f"💾 {symbol_short}[{timeframe}]: {len(data_records)} candele salvate")
                
        except Exception as e:
            logging.error(f"❌ Errore salvataggio {symbol}[{timeframe}]: {e}")
    
    def get_data(self, symbol: str, timeframe: str, limit: int = None) -> Optional[pd.DataFrame]:
        """
        Recupera dati OHLCV dal database
        
        Args:
            symbol: Simbolo
            timeframe: Timeframe
            limit: Numero massimo di candele (default: tutte)
            
        Returns:
            DataFrame con dati OHLCV o None
        """
        try:
            with self._db_lock:
                query = '''
                    SELECT timestamp, open, high, low, close, volume
                    FROM ohlcv_data 
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY timestamp DESC
                '''
                params = [symbol, timeframe]
                
                if limit:
                    query += ' LIMIT ?'
                    params.append(limit)
                
                with self.get_connection() as conn:
                    df = pd.read_sql_query(query, conn, params=params)
                    
                    if len(df) > 0:
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        df.set_index('timestamp', inplace=True)
                        df.sort_index(inplace=True)  # Ordine cronologico
                        
                        self.stats['queries_executed'] += 1
                        return df
                    
                    return None
                    
        except Exception as e:
            logging.error(f"❌ Errore lettura {symbol}[{timeframe}]: {e}")
            return None
    
    def get_symbols_list(self) -> List[str]:
        """Restituisce lista di tutti i simboli nel database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT symbol FROM ohlcv_data ORDER BY symbol')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Errore lista simboli: {e}")
            return []
    
    def get_timeframes_for_symbol(self, symbol: str) -> List[str]:
        """Restituisce timeframes disponibili per un simbolo"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT DISTINCT timeframe FROM ohlcv_data WHERE symbol = ? ORDER BY timeframe',
                    (symbol,)
                )
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Errore timeframes per {symbol}: {e}")
            return []
    
    def get_symbol_info(self, symbol: str, timeframe: str) -> Dict:
        """Ottiene informazioni sui dati di un simbolo"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        COUNT(*) as candles,
                        MIN(timestamp) as first_candle,
                        MAX(timestamp) as last_candle
                    FROM ohlcv_data 
                    WHERE symbol = ? AND timeframe = ?
                ''', (symbol, timeframe))
                
                result = cursor.fetchone()
                if result and result[0] > 0:
                    return {
                        'candles': result[0],
                        'first_candle': result[1],
                        'last_candle': result[2]
                    }
                return {'candles': 0}
                
        except Exception as e:
            logging.error(f"Errore info {symbol}[{timeframe}]: {e}")
            return {'candles': 0}
    
    def get_database_summary(self) -> Dict:
        """Restituisce un riepilogo del database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT 
                        COUNT(DISTINCT symbol) as symbols,
                        COUNT(DISTINCT timeframe) as timeframes,
                        COUNT(*) as total_candles,
                        MIN(timestamp) as oldest,
                        MAX(timestamp) as newest
                    FROM ohlcv_data
                ''')
                
                result = cursor.fetchone()
                
                # Dimensione file database
                size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
                size_mb = size_bytes / (1024 * 1024)
                
                return {
                    'symbols': result[0] or 0,
                    'timeframes': result[1] or 0,
                    'total_candles': result[2] or 0,
                    'oldest_data': result[3],
                    'newest_data': result[4],
                    'db_size_mb': round(size_mb, 2)
                }
                
        except Exception as e:
            logging.error(f"Errore riepilogo database: {e}")
            return {}
    
    def cleanup_old_data(self, days: int = None):
        """Rimuove dati più vecchi di N giorni"""
        if days is None:
            days = config.DATA_RETENTION_DAYS
        
        try:
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')
            
            with self._db_lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM ohlcv_data WHERE timestamp < ?', (cutoff_str,))
                    deleted = cursor.rowcount
                    conn.commit()
                    
                    if deleted > 0:
                        logging.info(f"🗑️ Rimossi {deleted} record più vecchi di {days} giorni")
                        
        except Exception as e:
            logging.error(f"Errore cleanup: {e}")


def display_database_stats(db_cache: DatabaseCache):
    """Mostra statistiche del database in modo formattato"""
    summary = db_cache.get_database_summary()
    
    print(colored("\n" + "="*60, "cyan"))
    print(colored("🗄️ STATISTICHE DATABASE", "cyan", attrs=['bold']))
    print(colored("="*60, "cyan"))
    
    if summary:
        print(colored(f"  📊 Simboli unici: {summary.get('symbols', 0)}", "white"))
        print(colored(f"  ⏰ Timeframes: {summary.get('timeframes', 0)}", "white"))
        print(colored(f"  🕯️ Candele totali: {summary.get('total_candles', 0):,}", "white"))
        print(colored(f"  💾 Dimensione DB: {summary.get('db_size_mb', 0)} MB", "white"))
        
        if summary.get('oldest_data') and summary.get('newest_data'):
            print(colored(f"  📅 Range dati: {summary['oldest_data'][:16]} → {summary['newest_data'][:16]}", "white"))
    
    print(colored("="*60, "cyan"))


# Istanza globale
global_db_cache = DatabaseCache()
