#!/usr/bin/env python3
"""Script to create backfill_status table if it doesn't exist"""
import sqlite3
import os

db_path = os.environ.get('SHARED_DATA_PATH', '/app/shared') + '/data_cache/trading_data.db'
print(f"Database path: {db_path}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Check existing tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"Existing tables: {tables}")

# Create backfill_status table if not exists
cur.execute('''
    CREATE TABLE IF NOT EXISTS backfill_status (
        symbol TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING',
        oldest_timestamp TEXT,
        warmup_start TEXT,
        training_start TEXT,
        newest_timestamp TEXT,
        total_candles INTEGER DEFAULT 0,
        warmup_candles INTEGER DEFAULT 0,
        training_candles INTEGER DEFAULT 0,
        completeness_pct REAL DEFAULT 0.0,
        gap_count INTEGER DEFAULT 0,
        last_update TEXT,
        error_message TEXT,
        PRIMARY KEY (symbol, timeframe)
    )
''')

conn.commit()
print("backfill_status table created/verified!")

# Verify
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"Tables after fix: {tables}")

conn.close()
