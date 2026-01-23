#!/usr/bin/env python3
"""Check training database tables and views"""

import sqlite3
from pathlib import Path

# Check crypto_data.db
db_path = Path("shared/crypto_data.db")
if not db_path.exists():
    print("crypto_data.db NOT FOUND")
else:
    print(f"=== crypto_data.db ({db_path.stat().st_size/1024:.1f} KB) ===")
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    
    # Get tables and views
    cur.execute("SELECT type, name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY type, name")
    for obj_type, name in cur.fetchall():
        print(f"  [{obj_type}] {name}")
    
    # Check for training data
    cur.execute("SELECT name FROM sqlite_master WHERE name LIKE '%training%' OR name LIKE '%label%'")
    training_tables = cur.fetchall()
    if training_tables:
        print("\n  Training-related:")
        for t in training_tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t[0]}")
                count = cur.fetchone()[0]
                print(f"    - {t[0]}: {count:,} rows")
            except:
                print(f"    - {t[0]}: (cannot count)")
    
    conn.close()

print()

# Check trading_data.db
db_path2 = Path("shared/data_cache/trading_data.db")
if not db_path2.exists():
    print("trading_data.db NOT FOUND")
else:
    print(f"=== trading_data.db ({db_path2.stat().st_size/1024:.1f} KB) ===")
    conn = sqlite3.connect(str(db_path2))
    cur = conn.cursor()
    
    # Get tables
    cur.execute("SELECT type, name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY type, name")
    for obj_type, name in cur.fetchall():
        print(f"  [{obj_type}] {name}")
    
    # Check ml_training_labels
    try:
        cur.execute("SELECT COUNT(*) FROM ml_training_labels")
        count = cur.fetchone()[0]
        print(f"\n  ml_training_labels: {count:,} rows")
        
        if count > 0:
            cur.execute("SELECT DISTINCT timeframe FROM ml_training_labels")
            timeframes = [t[0] for t in cur.fetchall()]
            print(f"  Timeframes: {timeframes}")
    except Exception as e:
        print(f"  ml_training_labels: ERROR - {e}")
    
    conn.close()

# Check models directory
models_dir = Path("shared/models")
print(f"\n=== Models Directory ===")
if models_dir.exists():
    files = list(models_dir.glob("*"))
    if files:
        for f in files:
            print(f"  - {f.name} ({f.stat().st_size/1024:.1f} KB)")
    else:
        print("  (empty)")
else:
    print("  NOT FOUND")
