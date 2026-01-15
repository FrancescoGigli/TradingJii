"""
🔧 Database Alignment Script
============================

Aligns training data across timeframes by removing records
that don't have matching timestamps across 15m and 1h.

For each symbol:
1. Find the latest start date between 15m and 1h
2. Find the earliest end date between 15m and 1h
3. Delete records outside this aligned range

This ensures data is temporally aligned for training.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import pandas as pd


def get_db_path():
    """Get database path"""
    # Check Docker path first
    docker_path = Path("/app/shared/data_cache/trading_data.db")
    if docker_path.exists():
        return docker_path
    
    # Local path
    local_path = Path(__file__).parent / "shared" / "data_cache" / "trading_data.db"
    if local_path.exists():
        return local_path
    
    raise FileNotFoundError("Database not found!")


def analyze_alignment(conn):
    """Analyze current alignment status"""
    print("\n" + "="*60)
    print("📊 ANALYZING CURRENT DATABASE ALIGNMENT")
    print("="*60)
    
    # Get date ranges per symbol/timeframe for ml_training_labels
    query = """
        SELECT symbol, timeframe, 
               MIN(timestamp) as start_date,
               MAX(timestamp) as end_date,
               COUNT(*) as count
        FROM ml_training_labels 
        GROUP BY symbol, timeframe
        ORDER BY symbol, timeframe
    """
    df = pd.read_sql_query(query, conn)
    df['start_date'] = pd.to_datetime(df['start_date'])
    df['end_date'] = pd.to_datetime(df['end_date'])
    
    # Pivot to compare 15m vs 1h
    alignment_issues = []
    symbols = df['symbol'].unique()
    
    for symbol in symbols:
        sym_data = df[df['symbol'] == symbol]
        
        tf_15m = sym_data[sym_data['timeframe'] == '15m']
        tf_1h = sym_data[sym_data['timeframe'] == '1h']
        
        if tf_15m.empty or tf_1h.empty:
            continue
        
        start_15m = tf_15m['start_date'].iloc[0]
        start_1h = tf_1h['start_date'].iloc[0]
        end_15m = tf_15m['end_date'].iloc[0]
        end_1h = tf_1h['end_date'].iloc[0]
        
        # Check misalignment
        start_diff = abs((start_15m - start_1h).total_seconds() / 3600)  # hours
        end_diff = abs((end_15m - end_1h).total_seconds() / 3600)  # hours
        
        if start_diff > 1 or end_diff > 1:  # More than 1 hour difference
            alignment_issues.append({
                'symbol': symbol,
                'start_15m': start_15m,
                'start_1h': start_1h,
                'start_diff_hours': start_diff,
                'end_15m': end_15m,
                'end_1h': end_1h,
                'end_diff_hours': end_diff,
                'aligned_start': max(start_15m, start_1h),
                'aligned_end': min(end_15m, end_1h),
            })
    
    if alignment_issues:
        print(f"\n⚠️  Found {len(alignment_issues)} symbols with alignment issues:\n")
        for issue in alignment_issues[:10]:  # Show first 10
            print(f"  {issue['symbol']}")
            print(f"    15m: {issue['start_15m']} → {issue['end_15m']}")
            print(f"    1h:  {issue['start_1h']} → {issue['end_1h']}")
            print(f"    Aligned: {issue['aligned_start']} → {issue['aligned_end']}")
            print()
        if len(alignment_issues) > 10:
            print(f"    ... and {len(alignment_issues) - 10} more")
    else:
        print("\n✅ All symbols are aligned!")
    
    return alignment_issues


def align_ml_training_labels(conn, dry_run=True):
    """
    Align ml_training_labels by removing records outside aligned range.
    
    Args:
        conn: SQLite connection
        dry_run: If True, only show what would be deleted
    """
    print("\n" + "="*60)
    print("🔧 ALIGNING ml_training_labels TABLE")
    print("="*60)
    
    cursor = conn.cursor()
    
    # Get all symbols with both timeframes
    cursor.execute("""
        SELECT DISTINCT symbol FROM ml_training_labels
        WHERE symbol IN (
            SELECT symbol FROM ml_training_labels WHERE timeframe = '15m'
            INTERSECT
            SELECT symbol FROM ml_training_labels WHERE timeframe = '1h'
        )
    """)
    symbols = [row[0] for row in cursor.fetchall()]
    
    total_deleted = 0
    
    for symbol in symbols:
        # Get aligned range for this symbol
        cursor.execute("""
            SELECT timeframe, MIN(timestamp) as start_ts, MAX(timestamp) as end_ts
            FROM ml_training_labels
            WHERE symbol = ?
            GROUP BY timeframe
        """, (symbol,))
        
        ranges = {row[0]: {'start': row[1], 'end': row[2]} for row in cursor.fetchall()}
        
        if '15m' not in ranges or '1h' not in ranges:
            continue
        
        # Calculate aligned range (intersection)
        aligned_start = max(ranges['15m']['start'], ranges['1h']['start'])
        aligned_end = min(ranges['15m']['end'], ranges['1h']['end'])
        
        # Count records to delete
        cursor.execute("""
            SELECT COUNT(*) FROM ml_training_labels
            WHERE symbol = ?
            AND (timestamp < ? OR timestamp > ?)
        """, (symbol, aligned_start, aligned_end))
        to_delete = cursor.fetchone()[0]
        
        if to_delete > 0:
            print(f"  {symbol}: Deleting {to_delete} records outside {aligned_start} → {aligned_end}")
            total_deleted += to_delete
            
            if not dry_run:
                cursor.execute("""
                    DELETE FROM ml_training_labels
                    WHERE symbol = ?
                    AND (timestamp < ? OR timestamp > ?)
                """, (symbol, aligned_start, aligned_end))
    
    if dry_run:
        print(f"\n📋 DRY RUN: Would delete {total_deleted} total records")
        print("   Run with --execute to apply changes")
    else:
        conn.commit()
        print(f"\n✅ Deleted {total_deleted} total records")
    
    return total_deleted


def align_historical_ohlcv(conn, dry_run=True):
    """
    Align historical_ohlcv by removing records outside aligned range.
    
    Args:
        conn: SQLite connection
        dry_run: If True, only show what would be deleted
    """
    print("\n" + "="*60)
    print("🔧 ALIGNING historical_ohlcv TABLE")
    print("="*60)
    
    cursor = conn.cursor()
    
    # Get all symbols with both timeframes
    cursor.execute("""
        SELECT DISTINCT symbol FROM historical_ohlcv
        WHERE symbol IN (
            SELECT symbol FROM historical_ohlcv WHERE timeframe = '15m'
            INTERSECT
            SELECT symbol FROM historical_ohlcv WHERE timeframe = '1h'
        )
    """)
    symbols = [row[0] for row in cursor.fetchall()]
    
    total_deleted = 0
    
    for symbol in symbols:
        # Get aligned range for this symbol
        cursor.execute("""
            SELECT timeframe, MIN(timestamp) as start_ts, MAX(timestamp) as end_ts
            FROM historical_ohlcv
            WHERE symbol = ?
            GROUP BY timeframe
        """, (symbol,))
        
        ranges = {row[0]: {'start': row[1], 'end': row[2]} for row in cursor.fetchall()}
        
        if '15m' not in ranges or '1h' not in ranges:
            continue
        
        # Calculate aligned range (intersection)
        aligned_start = max(ranges['15m']['start'], ranges['1h']['start'])
        aligned_end = min(ranges['15m']['end'], ranges['1h']['end'])
        
        # Count records to delete
        cursor.execute("""
            SELECT COUNT(*) FROM historical_ohlcv
            WHERE symbol = ?
            AND (timestamp < ? OR timestamp > ?)
        """, (symbol, aligned_start, aligned_end))
        to_delete = cursor.fetchone()[0]
        
        if to_delete > 0:
            print(f"  {symbol}: Deleting {to_delete} records outside aligned range")
            total_deleted += to_delete
            
            if not dry_run:
                cursor.execute("""
                    DELETE FROM historical_ohlcv
                    WHERE symbol = ?
                    AND (timestamp < ? OR timestamp > ?)
                """, (symbol, aligned_start, aligned_end))
    
    if dry_run:
        print(f"\n📋 DRY RUN: Would delete {total_deleted} total records")
    else:
        conn.commit()
        print(f"\n✅ Deleted {total_deleted} total records")
    
    return total_deleted


def main():
    import sys
    
    dry_run = "--execute" not in sys.argv
    
    print("\n" + "="*60)
    print("🔧 DATABASE ALIGNMENT TOOL")
    print("="*60)
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be made")
        print("   Add --execute flag to apply changes")
    else:
        print("\n🔴 EXECUTE MODE - Changes will be applied!")
        confirm = input("   Type 'yes' to confirm: ")
        if confirm.lower() != 'yes':
            print("   Aborted.")
            return
    
    db_path = get_db_path()
    print(f"\n📂 Database: {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    
    try:
        # 1. Analyze current state
        issues = analyze_alignment(conn)
        
        if not issues:
            print("\n✅ Database is already aligned!")
            return
        
        # 2. Align ml_training_labels
        align_ml_training_labels(conn, dry_run=dry_run)
        
        # 3. Align historical_ohlcv
        align_historical_ohlcv(conn, dry_run=dry_run)
        
        # 4. Verify after alignment
        if not dry_run:
            print("\n" + "="*60)
            print("📊 VERIFYING ALIGNMENT AFTER CHANGES")
            print("="*60)
            issues_after = analyze_alignment(conn)
            if not issues_after:
                print("\n✅ Database successfully aligned!")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
