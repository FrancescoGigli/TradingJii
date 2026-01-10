#!/usr/bin/env python3
"""Check database for indicators"""
import sqlite3

conn = sqlite3.connect('shared/data_cache/trading_data.db')
cur = conn.cursor()

# List all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print('=== ALL TABLES IN DATABASE ===')
for t in tables:
    print(f'  - {t[0]}')

# Check if historical_ohlcv exists
if any(t[0] == 'historical_ohlcv' for t in tables):
    print('\n=== COLUMNS IN historical_ohlcv ===')
    cur.execute('PRAGMA table_info(historical_ohlcv)')
    cols = cur.fetchall()
    for c in cols:
        print(f'  {c[1]}: {c[2]}')
    
    print('\n=== SAMPLE DATA WITH INDICATORS ===')
    cur.execute("""
        SELECT timestamp, close, sma_20, rsi, macd, atr 
        FROM historical_ohlcv 
        ORDER BY timestamp DESC 
        LIMIT 5
    """)
    rows = cur.fetchall()
    for r in rows:
        print(f'  {r}')
    
    print('\n=== INDICATOR FILL STATUS ===')
    cur.execute('SELECT COUNT(*) FROM historical_ohlcv')
    total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM historical_ohlcv WHERE sma_20 IS NOT NULL')
    with_sma = cur.fetchone()[0]
    
    print(f'  Total rows: {total}')
    if total > 0:
        print(f'  With SMA_20: {with_sma} ({100*with_sma/total:.1f}%)')
else:
    print('\n*** historical_ohlcv TABLE DOES NOT EXIST ***')
    print('Run the historical-data backfill to create it')

conn.close()
