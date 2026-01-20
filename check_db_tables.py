"""Check database tables"""
import sqlite3
from pathlib import Path

# Try different paths
paths = [
    Path("shared/crypto_data.db"),
    Path("shared/training_data.db"),
]

for p in paths:
    print(f"\n{'='*50}")
    print(f"Checking: {p}")
    print(f"Exists: {p.exists()}")
    
    if p.exists():
        conn = sqlite3.connect(p)
        tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"Tables: {tables}")
        
        # Check backfill_status
        if 'backfill_status' in tables:
            cur = conn.cursor()
            cur.execute("SELECT status, COUNT(*) FROM backfill_status GROUP BY status")
            print("\nBackfill status counts:")
            for row in cur.fetchall():
                print(f"  {row[0]}: {row[1]}")
        
        conn.close()
