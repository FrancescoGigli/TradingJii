#!/usr/bin/env python3
"""Check Docker database content"""
import sqlite3

db = '/app/shared/data_cache/trading_data.db'
c = sqlite3.connect(db)
cur = c.cursor()

print("=== trading_data.db ===")
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [t[0] for t in cur.fetchall()])

try:
    cur.execute("SELECT COUNT(*) FROM training_labels")
    print("training_labels rows:", cur.fetchone()[0])
    
    cur.execute("SELECT COUNT(*) FROM training_data")
    print("training_data rows:", cur.fetchone()[0])
    
    cur.execute("SELECT * FROM training_data LIMIT 1")
    cols = [d[0] for d in cur.description]
    print("training_data columns:", len(cols), "columns")
    print("Sample cols:", cols[:15], "...")
    
    # Check if it has indicators
    if 'rsi' in cols:
        print("Has RSI: YES")
    if 'score_long' in cols:
        print("Has score_long: YES")
except Exception as e:
    print("Error:", e)

c.close()
