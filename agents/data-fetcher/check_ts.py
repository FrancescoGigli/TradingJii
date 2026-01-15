import sqlite3
conn = sqlite3.connect('/app/shared/data_cache/trading_data.db')
c = conn.cursor()
c.execute("SELECT symbol, MAX(timestamp) FROM historical_ohlcv WHERE timeframe='15m' GROUP BY symbol ORDER BY MAX(timestamp) DESC LIMIT 10")
print("Symbol | Max TS")
print("-" * 50)
for row in c.fetchall():
    print(f"{row[0][:25]:25} | {row[1]}")
conn.close()
