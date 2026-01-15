import sqlite3
conn = sqlite3.connect('/app/shared/data_cache/trading_data.db')
cursor = conn.cursor()
cursor.execute("SELECT MAX(timestamp) FROM historical_ohlcv WHERE timeframe='15m'")
print('MAX TS:', cursor.fetchone()[0])
conn.close()
