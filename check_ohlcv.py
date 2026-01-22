"""Check OHLCV data in database."""
import sqlite3
import os

db_path = os.environ.get('DB_PATH', './shared/trading.db')
print(f"DB Path: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print(f"\nTables: {tables}")

# Check ohlcv_data
if 'ohlcv_data' in tables:
    cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
    print(f"\nOHLCV total rows: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT DISTINCT timeframe FROM ohlcv_data")
    print(f"Timeframes: {[r[0] for r in cursor.fetchall()]}")
    
    cursor.execute("SELECT symbol, timeframe, COUNT(*) FROM ohlcv_data GROUP BY symbol, timeframe LIMIT 10")
    print(f"\nTop 10 symbol/tf counts:")
    for row in cursor.fetchall():
        print(f"  {row}")
else:
    print("\n❌ ohlcv_data table not found!")

# Check training_labels
if 'training_labels' in tables:
    cursor.execute("SELECT COUNT(*) FROM training_labels")
    print(f"\nTraining labels rows: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT symbol, timeframe FROM training_labels LIMIT 3")
    print(f"Sample symbols in labels: {cursor.fetchall()}")

conn.close()
