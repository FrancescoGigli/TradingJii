#!/usr/bin/env python3
"""Quick DB check"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'shared' / 'crypto_data.db'

print(f"📁 Database: {DB_PATH}")
print(f"   Exists: {DB_PATH.exists()}")

if DB_PATH.exists():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Get tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    
    print(f"\n📋 Tabelle trovate: {len(tables)}")
    
    if tables:
        for t in tables:
            table_name = t[0]
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            print(f"   - {table_name}: {count:,} righe")
    else:
        print("   ⚠️ DATABASE VUOTO - Nessuna tabella!")
        print("\n💡 Per popolare il database, esegui:")
        print("   python run_full_training_pipeline.py --symbols 5 --timeframe 15m --days 30")
    
    conn.close()
else:
    print("   ❌ File non trovato!")
