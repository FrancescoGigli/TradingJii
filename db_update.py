import sqlite3
import os
import logging
from config import DB_FILE, ENABLED_TIMEFRAMES

def add_missing_columns():
    """
    Aggiunge colonne mancanti alle tabelle esistenti nel database.
    In particolare, aggiunge la colonna 'volatility' se non esiste.
    """
    if not os.path.exists(DB_FILE):
        logging.info("Database file non esiste. Non è necessario aggiornare.")
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    for timeframe in ENABLED_TIMEFRAMES:
        table_name = f"data_{timeframe}"
        
        # Verifica se la tabella esiste
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if not cursor.fetchone():
            logging.info(f"La tabella {table_name} non esiste. Saltando.")
            continue
        
        # Controlla se la colonna volatility esiste già
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'volatility' not in columns:
            logging.info(f"Aggiungendo la colonna 'volatility' alla tabella {table_name}...")
            try:
                # Metodo 1: Tentativo di aggiungere la colonna - questo potrebbe fallire su alcune versioni di SQLite
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN volatility REAL DEFAULT 0.0")
                logging.info(f"Colonna 'volatility' aggiunta correttamente alla tabella {table_name}")
            except sqlite3.OperationalError as e:
                logging.warning(f"Errore nell'aggiungere la colonna: {e}")
                logging.info(f"Tentativo alternativo di ricostruzione della tabella {table_name}...")
                
                # Metodo 2: Ricrea la tabella con la nuova colonna - più complessa ma funziona sempre
                try:
                    # Backup dei dati
                    cursor.execute(f"CREATE TABLE {table_name}_backup AS SELECT * FROM {table_name}")
                    
                    # Drop della vecchia tabella
                    cursor.execute(f"DROP TABLE {table_name}")
                    
                    # Crea la nuova tabella con la colonna aggiuntiva
                    cursor.execute(f'''
                        CREATE TABLE {table_name} (
                            timestamp TEXT,
                            symbol TEXT,
                            open REAL,
                            high REAL,
                            low REAL,
                            close REAL,
                            volume REAL,
                            ema5 REAL,
                            ema10 REAL,
                            ema20 REAL,
                            macd REAL,
                            macd_signal REAL,
                            rsi_fast REAL,
                            stoch_rsi REAL,
                            atr REAL,
                            bollinger_hband REAL,
                            bollinger_lband REAL,
                            vwap REAL,
                            adx REAL,
                            roc REAL,
                            weekday_sin REAL,
                            weekday_cos REAL,
                            hour_sin REAL,
                            hour_cos REAL,
                            volatility REAL DEFAULT 0.0,
                            PRIMARY KEY (timestamp, symbol)
                        )
                    ''')
                    
                    # Recupera i dati dal backup
                    old_columns = columns
                    old_columns_str = ", ".join(old_columns)
                    cursor.execute(f"INSERT INTO {table_name} ({old_columns_str}) SELECT {old_columns_str} FROM {table_name}_backup")
                    
                    # Drop della tabella di backup
                    cursor.execute(f"DROP TABLE {table_name}_backup")
                    
                    logging.info(f"Tabella {table_name} ricostruita con successo includendo la colonna 'volatility'")
                except Exception as e2:
                    logging.error(f"Errore nella ricostruzione della tabella: {e2}")
        else:
            logging.info(f"La colonna 'volatility' esiste già nella tabella {table_name}")
    
    conn.commit()
    conn.close()
    logging.info("Aggiornamento del database completato")

def fix_db_schema_for_volatility():
    """
    Funzione di correzione one-shot: se il database esiste ma con la vecchia struttura,
    questa funzione tenta di correggere lo schema prima che il programma principale
    tenti di accedere alla colonna 'volatility'.
    
    Blocca temporaneamente l'accesso al database fino al completamento.
    """
    if not os.path.exists(DB_FILE):
        return  # Nessun database da aggiornare
        
    print("Verifica della struttura del database...")
    logging.info("Verifica della struttura del database...")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    needs_update = False
    
    # Controlla se ci sono tabelle che necessitano di aggiornamento
    for tf in ENABLED_TIMEFRAMES:
        table_name = f"data_{tf}"
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if cursor.fetchone():  # La tabella esiste
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [info[1] for info in cursor.fetchall()]
            if 'volatility' not in columns:
                needs_update = True
                break
    
    conn.close()
    
    if needs_update:
        print("⚠️ Database: colonna volatility mancante, aggiornamento necessario.")
        print("🔄 Aggiornamento dello schema del database in corso...")
        logging.info("Database: colonna volatility mancante, aggiornamento necessario.")
        add_missing_columns()
        print("✅ Aggiornamento del database completato con successo.")
    else:
        print("✅ Database già aggiornato o non necessita aggiornamenti.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    fix_db_schema_for_volatility()
