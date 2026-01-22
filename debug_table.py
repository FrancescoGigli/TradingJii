#!/usr/bin/env python
"""Debug table display issue"""
import sqlite3
import pandas as pd

# Connect to the CORRECT database (trading_data.db, not crypto_cache.db!)
conn = sqlite3.connect('/app/shared/data_cache/trading_data.db')

# List all tables
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("TABLES:", [t[0] for t in tables])

# Check views
cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
views = cursor.fetchall()
print("VIEWS:", [v[0] for v in views])

# Check training_labels table
try:
    df = pd.read_sql_query("SELECT COUNT(*) as cnt, symbol, timeframe FROM training_labels GROUP BY symbol, timeframe LIMIT 5", conn)
    print("\ntraining_labels sample:")
    print(df)
except Exception as e:
    print(f"Error: {e}")

# Try v_xgb_training
try:
    df = pd.read_sql_query("SELECT COUNT(*) as cnt FROM v_xgb_training LIMIT 1", conn)
    print("\nv_xgb_training count:")
    print(df)
except Exception as e:
    print(f"VIEW Error: {e}")

# Try direct labels query
try:
    df = pd.read_sql_query("""
        SELECT timestamp, score_long, score_short 
        FROM training_labels 
        WHERE symbol = 'BTC/USDT:USDT' AND timeframe = '15m' 
        LIMIT 5
    """, conn)
    print("\nDirect BTC labels:")
    print(df)
except Exception as e:
    print(f"Direct query error: {e}")

conn.close()
