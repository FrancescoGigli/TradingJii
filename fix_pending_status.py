"""
🔧 Fix PENDING Status in backfill_status table

This script converts all remaining PENDING records to SKIPPED
after a download has completed.
"""

import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path("shared/crypto_data.db")

def fix_pending_status():
    """Convert all PENDING records to SKIPPED"""
    
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Count current status
    cur.execute("SELECT status, COUNT(*) FROM backfill_status GROUP BY status")
    print("\n📊 Current status distribution:")
    for row in cur.fetchall():
        print(f"   {row[0]}: {row[1]}")
    
    # Count PENDING
    cur.execute("SELECT COUNT(*) FROM backfill_status WHERE status = 'PENDING'")
    pending_count = cur.fetchone()[0]
    
    if pending_count == 0:
        print("\n✅ No PENDING records found. Nothing to fix.")
        conn.close()
        return
    
    print(f"\n⚠️ Found {pending_count} PENDING records")
    
    # Convert PENDING to SKIPPED
    cur.execute("""
        UPDATE backfill_status 
        SET status = 'SKIPPED', 
            error_message = 'Not processed - download completed'
        WHERE status = 'PENDING'
    """)
    
    updated = cur.rowcount
    conn.commit()
    
    print(f"✅ Converted {updated} PENDING → SKIPPED")
    
    # Show updated distribution
    cur.execute("SELECT status, COUNT(*) FROM backfill_status GROUP BY status")
    print("\n📊 Updated status distribution:")
    for row in cur.fetchall():
        print(f"   {row[0]}: {row[1]}")
    
    conn.close()
    print("\n✅ Done!")

if __name__ == "__main__":
    fix_pending_status()
