#!/usr/bin/env python3
"""Reset failed training job to pending."""
import sqlite3

db_path = "/app/shared/data_cache/trading_data.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("UPDATE training_jobs SET status='pending', progress_pct=0, error=NULL WHERE id=1")
conn.commit()
print(f"Job 1 reset to pending. Rows affected: {cur.rowcount}")
conn.close()
