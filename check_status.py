#!/usr/bin/env python3
"""Check database and model status"""
import sqlite3
import json
from pathlib import Path

db_path = Path('shared/crypto_data.db')

if not db_path.exists():
    print("❌ Database not found at:", db_path)
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("="*60)
print("📊 DATABASE STATUS")
print("="*60)

# List all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"\n📋 Tables in database: {len(tables)}")
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    print(f"   - {t}: {count:,} rows")

# Check training_data if exists
if 'training_data' in tables:
    print("\n🗄️ training_data details:")
    cur.execute('SELECT COUNT(*), COUNT(DISTINCT symbol) FROM training_data WHERE timeframe="15m"')
    r = cur.fetchone()
    print(f"   15m: {r[0]:,} rows, {r[1]} symbols")
    cur.execute('SELECT COUNT(*), COUNT(DISTINCT symbol) FROM training_data WHERE timeframe="1h"')
    r = cur.fetchone()
    print(f"   1h: {r[0]:,} rows, {r[1]} symbols")

# Check training_labels if exists
if 'training_labels' in tables:
    print("\n🏷️ training_labels details:")
    cur.execute('SELECT COUNT(*), COUNT(DISTINCT symbol) FROM training_labels WHERE timeframe="15m"')
    r = cur.fetchone()
    print(f"   15m: {r[0]:,} rows, {r[1]} symbols")
    cur.execute('SELECT COUNT(*), COUNT(DISTINCT symbol) FROM training_labels WHERE timeframe="1h"')
    r = cur.fetchone()
    print(f"   1h: {r[0]:,} rows, {r[1]} symbols")

conn.close()

# Check models
print("\n" + "="*60)
print("🤖 MODELS STATUS")
print("="*60)

model_dir = Path('shared/models')
if model_dir.exists():
    metadata_file = model_dir / 'metadata_latest.json'
    if metadata_file.exists():
        with open(metadata_file) as f:
            meta = json.load(f)
        print(f"\n✅ Latest model: {meta.get('version', 'unknown')}")
        print(f"   Timeframe: {meta.get('timeframe', 'unknown')}")
        print(f"   Features: {meta.get('n_features', 0)}")
        print(f"   Train samples: {meta.get('n_train_samples', 0):,}")
        print(f"   Test samples: {meta.get('n_test_samples', 0):,}")
        
        features = meta.get('feature_names', [])
        print(f"\n📐 Feature columns ({len(features)}):")
        for f in features:
            print(f"   - {f}")
        
        ml = meta.get('metrics_long', {})
        ms = meta.get('metrics_short', {})
        print(f"\n📊 LONG Metrics:")
        print(f"   R²: {ml.get('test_r2', 0):.4f}")
        print(f"   Spearman: {ml.get('ranking', {}).get('spearman_corr', 0):.4f}")
        
        print(f"\n📊 SHORT Metrics:")
        print(f"   R²: {ms.get('test_r2', 0):.4f}")
        print(f"   Spearman: {ms.get('ranking', {}).get('spearman_corr', 0):.4f}")
    else:
        print("\n❌ No model found (metadata_latest.json missing)")
else:
    print("\n❌ Models directory not found")
