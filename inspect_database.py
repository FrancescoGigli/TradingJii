#!/usr/bin/env python3
"""
🔍 DATABASE INSPECTOR
Mostra un report completo di tutti i dati nel database.

Uso:
    python inspect_database.py
    python inspect_database.py --detailed
    python inspect_database.py --symbol BTCUSDT
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import argparse
import json

DB_PATH = Path(__file__).parent / 'shared' / 'crypto_data.db'


def print_header(title):
    print("\n" + "="*70)
    print(f"📊 {title}")
    print("="*70)


def print_subheader(title):
    print(f"\n--- {title} ---")


def get_connection():
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return None
    return sqlite3.connect(DB_PATH)


def inspect_tables(conn):
    """List all tables with row counts"""
    print_header("TABLES OVERVIEW")
    
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    
    if not tables:
        print("⚠️ No tables found in database")
        return []
    
    print(f"\n{'Table':<30} {'Rows':>15} {'Size (KB)':>15}")
    print("-"*60)
    
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            # Estimate size
            cur.execute(f"SELECT SUM(length(CAST(* AS BLOB))) FROM {table} LIMIT 1000")
            print(f"{table:<30} {count:>15,} {'~':>15}")
        except:
            print(f"{table:<30} {'error':>15}")
    
    return tables


def inspect_training_data(conn, detailed=False, symbol_filter=None):
    """Inspect training_data table"""
    print_header("TRAINING DATA")
    
    cur = conn.cursor()
    
    # Check if table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_data'")
    if not cur.fetchone():
        print("⚠️ Table 'training_data' not found")
        return
    
    # Get column info
    cur.execute("PRAGMA table_info(training_data)")
    columns = [r[1] for r in cur.fetchall()]
    print(f"\n📋 Columns ({len(columns)}): {', '.join(columns[:10])}...")
    
    # Summary by timeframe
    print_subheader("By Timeframe")
    cur.execute('''
        SELECT 
            timeframe,
            COUNT(*) as rows,
            COUNT(DISTINCT symbol) as symbols,
            MIN(timestamp) as min_date,
            MAX(timestamp) as max_date
        FROM training_data
        GROUP BY timeframe
    ''')
    
    for row in cur.fetchall():
        print(f"\n  📈 {row[0]}:")
        print(f"     Rows: {row[1]:,}")
        print(f"     Symbols: {row[2]}")
        print(f"     Date Range: {row[3]} → {row[4]}")
    
    # Summary by symbol
    if detailed or symbol_filter:
        print_subheader("By Symbol")
        
        query = '''
            SELECT 
                symbol,
                timeframe,
                COUNT(*) as rows,
                MIN(timestamp) as min_date,
                MAX(timestamp) as max_date,
                AVG(close) as avg_close,
                MIN(close) as min_close,
                MAX(close) as max_close
            FROM training_data
        '''
        if symbol_filter:
            query += f" WHERE symbol LIKE '%{symbol_filter}%'"
        query += " GROUP BY symbol, timeframe ORDER BY rows DESC"
        
        if not detailed:
            query += " LIMIT 10"
        
        cur.execute(query)
        results = cur.fetchall()
        
        print(f"\n{'Symbol':<25} {'TF':<5} {'Rows':>10} {'Avg Close':>12}")
        print("-"*55)
        for r in results:
            sym = r[0].replace('/USDT:USDT', '')
            print(f"{sym:<25} {r[1]:<5} {r[2]:>10,} {r[5]:>12,.2f}")
    
    # Check indicators
    print_subheader("Indicators Check")
    indicator_cols = ['rsi', 'macd', 'atr', 'adx', 'cci', 'willr', 'obv', 
                      'sma_20', 'sma_50', 'ema_12', 'ema_26', 
                      'bb_upper', 'bb_middle', 'bb_lower']
    
    for col in indicator_cols:
        if col in columns:
            cur.execute(f'SELECT COUNT(*), COUNT({col}), AVG({col}) FROM training_data')
            total, non_null, avg = cur.fetchone()
            pct = (non_null / total * 100) if total > 0 else 0
            avg_str = f"{avg:.4f}" if avg else "N/A"
            status = "✅" if pct > 95 else "⚠️" if pct > 50 else "❌"
            print(f"  {status} {col:<15} {pct:>6.1f}% filled (avg: {avg_str})")


def inspect_training_labels(conn, detailed=False, symbol_filter=None):
    """Inspect training_labels table"""
    print_header("TRAINING LABELS")
    
    cur = conn.cursor()
    
    # Check if table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_labels'")
    if not cur.fetchone():
        print("⚠️ Table 'training_labels' not found")
        return
    
    # Get column info
    cur.execute("PRAGMA table_info(training_labels)")
    columns = [r[1] for r in cur.fetchall()]
    print(f"\n📋 Columns ({len(columns)}): {', '.join(columns[:10])}...")
    
    # Summary by timeframe
    print_subheader("By Timeframe")
    cur.execute('''
        SELECT 
            timeframe,
            COUNT(*) as rows,
            COUNT(DISTINCT symbol) as symbols,
            AVG(score_long) as avg_score_long,
            AVG(score_short) as avg_score_short,
            SUM(CASE WHEN exit_type_long = 'trailing' THEN 1 ELSE 0 END) as trailing_exits,
            SUM(CASE WHEN exit_type_long = 'time' THEN 1 ELSE 0 END) as time_exits
        FROM training_labels
        GROUP BY timeframe
    ''')
    
    for row in cur.fetchall():
        total = row[5] + row[6] if row[5] and row[6] else 0
        trailing_pct = (row[5] / total * 100) if total > 0 else 0
        
        print(f"\n  🏷️ {row[0]}:")
        print(f"     Rows: {row[1]:,}")
        print(f"     Symbols: {row[2]}")
        print(f"     Avg Score Long: {row[3]:.6f}" if row[3] else "     Avg Score Long: N/A")
        print(f"     Avg Score Short: {row[4]:.6f}" if row[4] else "     Avg Score Short: N/A")
        print(f"     Trailing Exits: {trailing_pct:.1f}%")
    
    # Score distribution
    print_subheader("Score Distribution")
    cur.execute('''
        SELECT 
            CASE 
                WHEN score_long > 0.02 THEN 'Strong Long (>2%)'
                WHEN score_long > 0 THEN 'Weak Long (0-2%)'
                WHEN score_long > -0.02 THEN 'Weak Short (-2-0%)'
                ELSE 'Strong Short (<-2%)'
            END as category,
            COUNT(*) as count
        FROM training_labels
        GROUP BY category
    ''')
    
    for row in cur.fetchall():
        print(f"  {row[0]:<25} {row[1]:>10,}")
    
    # By symbol (if detailed)
    if detailed or symbol_filter:
        print_subheader("By Symbol")
        
        query = '''
            SELECT 
                symbol,
                timeframe,
                COUNT(*) as rows,
                AVG(score_long) as avg_long,
                AVG(score_short) as avg_short,
                AVG(realized_return_long) as avg_return
            FROM training_labels
        '''
        if symbol_filter:
            query += f" WHERE symbol LIKE '%{symbol_filter}%'"
        query += " GROUP BY symbol, timeframe ORDER BY rows DESC"
        
        if not detailed:
            query += " LIMIT 10"
        
        cur.execute(query)
        results = cur.fetchall()
        
        print(f"\n{'Symbol':<25} {'TF':<5} {'Rows':>10} {'Avg Long':>10} {'Avg Return':>12}")
        print("-"*65)
        for r in results:
            sym = r[0].replace('/USDT:USDT', '')
            avg_long = f"{r[3]:.4f}" if r[3] else "N/A"
            avg_ret = f"{r[5]*100:.2f}%" if r[5] else "N/A"
            print(f"{sym:<25} {r[1]:<5} {r[2]:>10,} {avg_long:>10} {avg_ret:>12}")


def inspect_models():
    """Inspect saved models"""
    print_header("MODELS")
    
    model_dir = Path(__file__).parent / 'shared' / 'models'
    
    if not model_dir.exists():
        print("⚠️ Models directory not found")
        return
    
    # List all model files
    pkl_files = list(model_dir.glob("*.pkl"))
    json_files = list(model_dir.glob("*.json"))
    
    print(f"\n📁 Model files: {len(pkl_files)} .pkl, {len(json_files)} .json")
    
    # Check latest metadata
    metadata_file = model_dir / 'metadata_latest.json'
    if metadata_file.exists():
        with open(metadata_file) as f:
            meta = json.load(f)
        
        print_subheader("Latest Model")
        print(f"  Version: {meta.get('version', 'N/A')}")
        print(f"  Timeframe: {meta.get('timeframe', 'N/A')}")
        print(f"  Features: {meta.get('n_features', 0)}")
        print(f"  Train Samples: {meta.get('n_train_samples', 0):,}")
        print(f"  Test Samples: {meta.get('n_test_samples', 0):,}")
        
        print_subheader("Metrics")
        ml = meta.get('metrics_long', {})
        ms = meta.get('metrics_short', {})
        
        print(f"  LONG:")
        print(f"    R²: {ml.get('test_r2', 0):.4f}")
        print(f"    Spearman: {ml.get('ranking', {}).get('spearman_corr', 0):.4f}")
        
        print(f"  SHORT:")
        print(f"    R²: {ms.get('test_r2', 0):.4f}")
        print(f"    Spearman: {ms.get('ranking', {}).get('spearman_corr', 0):.4f}")
        
        print_subheader("Features Used")
        features = meta.get('feature_names', [])
        for i, f in enumerate(features):
            print(f"  {i+1:>2}. {f}")
    else:
        print("⚠️ No model metadata found (metadata_latest.json)")


def check_data_quality(conn):
    """Check data quality issues"""
    print_header("DATA QUALITY CHECK")
    
    cur = conn.cursor()
    issues = []
    
    # Check for NULL values in critical columns
    print_subheader("NULL Values Check")
    
    for table in ['training_data', 'training_labels']:
        cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if not cur.fetchone():
            continue
        
        cur.execute(f"PRAGMA table_info({table})")
        columns = [r[1] for r in cur.fetchall()]
        
        for col in ['close', 'volume', 'timestamp']:
            if col in columns:
                cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL")
                null_count = cur.fetchone()[0]
                if null_count > 0:
                    print(f"  ⚠️ {table}.{col}: {null_count:,} NULL values")
                    issues.append(f"{table}.{col} has NULLs")
    
    # Check for duplicate entries
    print_subheader("Duplicate Check")
    
    for table, key_cols in [
        ('training_data', 'symbol, timeframe, timestamp'),
        ('training_labels', 'symbol, timeframe, timestamp')
    ]:
        cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if not cur.fetchone():
            continue
        
        cur.execute(f'''
            SELECT {key_cols}, COUNT(*) as cnt 
            FROM {table} 
            GROUP BY {key_cols} 
            HAVING cnt > 1
        ''')
        dups = cur.fetchall()
        if dups:
            print(f"  ⚠️ {table}: {len(dups)} duplicate key combinations")
            issues.append(f"{table} has duplicates")
        else:
            print(f"  ✅ {table}: No duplicates")
    
    # Check data alignment
    print_subheader("Data Alignment")
    
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_data'")
    has_data = cur.fetchone() is not None
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_labels'")
    has_labels = cur.fetchone() is not None
    
    if has_data and has_labels:
        cur.execute('''
            SELECT td.timeframe, COUNT(DISTINCT td.symbol) as data_symbols, 
                   COUNT(DISTINCT tl.symbol) as label_symbols
            FROM training_data td
            LEFT JOIN training_labels tl ON td.symbol = tl.symbol AND td.timeframe = tl.timeframe
            GROUP BY td.timeframe
        ''')
        
        for row in cur.fetchall():
            if row[1] != row[2]:
                print(f"  ⚠️ {row[0]}: {row[1]} data symbols vs {row[2]} label symbols")
                issues.append(f"Misaligned symbols for {row[0]}")
            else:
                print(f"  ✅ {row[0]}: {row[1]} symbols aligned")
    
    # Summary
    print_subheader("Summary")
    if issues:
        print(f"  ⚠️ Found {len(issues)} issues:")
        for issue in issues:
            print(f"     - {issue}")
    else:
        print("  ✅ All quality checks passed!")


def main():
    parser = argparse.ArgumentParser(description='Database Inspector')
    parser.add_argument('--detailed', '-d', action='store_true', help='Show detailed info')
    parser.add_argument('--symbol', '-s', type=str, help='Filter by symbol (e.g., BTC)')
    parser.add_argument('--quality', '-q', action='store_true', help='Run quality checks only')
    args = parser.parse_args()
    
    print("\n" + "🔍 "*20)
    print("          DATABASE INSPECTOR")
    print("🔍 "*20)
    print(f"\n📁 Database: {DB_PATH}")
    print(f"📅 Inspected at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    conn = get_connection()
    if not conn:
        return
    
    if args.quality:
        check_data_quality(conn)
    else:
        tables = inspect_tables(conn)
        
        if 'training_data' in tables:
            inspect_training_data(conn, args.detailed, args.symbol)
        
        if 'training_labels' in tables:
            inspect_training_labels(conn, args.detailed, args.symbol)
        
        inspect_models()
        check_data_quality(conn)
    
    conn.close()
    
    print("\n" + "="*70)
    print("✅ Inspection complete!")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
