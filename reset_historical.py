"""
Script per resettare i dati historical della tab Train
Cancella: historical_ohlcv, backfill_status, training_labels
"""
import sqlite3
from pathlib import Path

DB_PATH = Path("shared/data_cache/trading_data.db")

def main():
    if not DB_PATH.exists():
        print(f"❌ Database non trovato: {DB_PATH}")
        return
    
    print(f"📁 Database: {DB_PATH}")
    print(f"📊 Dimensione: {DB_PATH.stat().st_size / (1024*1024):.2f} MB")
    print()
    
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    
    # Lista tabelle esistenti
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"📋 Tabelle esistenti: {tables}")
    print()
    
    # Conta righe prima della cancellazione
    for table in ['historical_ohlcv', 'backfill_status', 'training_labels']:
        if table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"🔢 {table}: {count:,} righe")
    
    print()
    print("🗑️ Cancellazione in corso...")
    
    # DROP tables
    tables_to_drop = ['historical_ohlcv', 'backfill_status', 'training_labels']
    
    for table in tables_to_drop:
        if table in tables:
            cur.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"   ✅ {table} eliminata")
        else:
            print(f"   ⏭️ {table} non esistente")
    
    # VACUUM per recuperare spazio
    print()
    print("🧹 VACUUM database...")
    conn.commit()
    cur.execute("VACUUM")
    conn.close()
    
    print()
    print(f"📊 Nuova dimensione: {DB_PATH.stat().st_size / (1024*1024):.2f} MB")
    print()
    print("✅ Reset completato!")

if __name__ == "__main__":
    main()
