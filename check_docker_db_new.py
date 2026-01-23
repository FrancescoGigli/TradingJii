"""Quick check of Docker database status."""
import sqlite3
import os

# Check the volume path from docker-compose
db_path = r"C:\Users\gigli\Desktop\Trae - Versione modificata\crypto_data\trading_data.db"

# Also try shared path
alt_path = r"C:\Users\gigli\Desktop\Trae - Versione modificata\shared\trading.db"

for path in [db_path, alt_path]:
    print(f"\n📁 Checking: {path}")
    if os.path.exists(path):
        print(f"   Size: {os.path.getsize(path) / 1024 / 1024:.2f} MB")
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            
            # Get tables
            tables = cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            print(f"   Tables: {[t[0] for t in tables]}")
            
            # Count rows in main tables
            for table in tables:
                tname = table[0]
                count = cursor.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
                print(f"   - {tname}: {count:,} rows")
            
            conn.close()
        except Exception as e:
            print(f"   Error: {e}")
    else:
        print("   NOT FOUND")

# List crypto_data directory
crypto_data_dir = r"C:\Users\gigli\Desktop\Trae - Versione modificata\crypto_data"
if os.path.exists(crypto_data_dir):
    print(f"\n📁 Contents of crypto_data/:")
    for f in os.listdir(crypto_data_dir):
        fpath = os.path.join(crypto_data_dir, f)
        size = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
        print(f"   {f}: {size / 1024 / 1024:.2f} MB")
else:
    print(f"\n📁 crypto_data/ directory not found")
