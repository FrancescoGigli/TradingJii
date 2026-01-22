#!/usr/bin/env python3
"""Inspect database in Docker volume"""
import sqlite3

DB_PATH = "/app/shared/data_cache/trading_data.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Get all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [t[0] for t in cur.fetchall()]

print("=" * 70)
print("TABELLE NEL DATABASE")
print("=" * 70)
print(f"Trovate {len(tables)} tabelle:")
print()

for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"  📋 {table}: {count:,} righe")

print()
print("=" * 70)
print("DETTAGLI PER TABELLA")
print("=" * 70)

for table in tables:
    print(f"\n--- {table} ---")
    cur.execute(f"PRAGMA table_info({table})")
    columns = cur.fetchall()
    print(f"Colonne ({len(columns)}):")
    for col in columns[:10]:  # Prime 10 colonne
        print(f"  - {col[1]} ({col[2]})")
    if len(columns) > 10:
        print(f"  ... e altre {len(columns) - 10} colonne")

print()
print("=" * 70)
print("STATISTICHE LABELS (se esistono)")
print("=" * 70)

# Check for labels tables
for table in ['training_labels', 'ml_training_labels']:
    if table in tables:
        print(f"\n--- {table} ---")
        cur.execute(f"""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT symbol) as symbols,
                AVG(score_long) as avg_long,
                AVG(score_short) as avg_short
            FROM {table}
        """)
        r = cur.fetchone()
        print(f"  Total rows: {r[0]:,}")
        print(f"  Symbols: {r[1]}")
        print(f"  Avg Score Long: {r[2]:.6f}" if r[2] else "  Avg Score Long: N/A")
        print(f"  Avg Score Short: {r[3]:.6f}" if r[3] else "  Avg Score Short: N/A")

conn.close()
