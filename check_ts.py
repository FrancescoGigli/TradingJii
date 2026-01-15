import sqlite3

conn = sqlite3.connect('shared/data_cache/trading_data.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT symbol, MAX(timestamp) as max_ts 
    FROM historical_ohlcv 
    WHERE timeframe='15m' 
    GROUP BY symbol 
    ORDER BY MAX(timestamp) DESC 
    LIMIT 30
""")

print("Symbol | Max Timestamp")
print("-" * 60)
for row in cursor.fetchall():
    print(f"{row[0]:30} | {row[1]}")

conn.close()
