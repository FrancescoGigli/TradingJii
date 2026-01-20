#!/usr/bin/env python3
"""
Ispeziona il database per vedere le tabelle ML
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path('shared/crypto_data.db')

if not DB_PATH.exists():
    print(f'Database non trovato: {DB_PATH}')
    exit()

print(f'Database: {DB_PATH} ({DB_PATH.stat().st_size / 1024 / 1024:.2f} MB)')
print('='*80)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Lista tabelle
print('\n📋 TABELLE NEL DATABASE:')
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM {t}')
    count = cur.fetchone()[0]
    print(f'  • {t}: {count:,} righe')

print('\n' + '='*80)

# Check training_data
print('\n📊 TRAINING_DATA (Features/Indicatori):')
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_data'")
if cur.fetchone():
    cur.execute('SELECT COUNT(*) FROM training_data')
    total = cur.fetchone()[0]
    print(f'  Righe totali: {total:,}')
    
    cur.execute('SELECT COUNT(DISTINCT symbol) FROM training_data')
    print(f'  Symbols: {cur.fetchone()[0]}')
    
    cur.execute('SELECT DISTINCT symbol FROM training_data LIMIT 5')
    symbols = [r[0] for r in cur.fetchall()]
    print(f'  Primi 5 symbols: {symbols}')
    
    cur.execute('PRAGMA table_info(training_data)')
    cols = [r[1] for r in cur.fetchall()]
    print(f'  Colonne ({len(cols)}): {cols}')
    
    if total > 0:
        print('\n  📝 Sample (ultime 3 righe BTC 15m):')
        df = pd.read_sql_query('''
            SELECT timestamp, symbol, timeframe, close, rsi, macd, atr
            FROM training_data 
            WHERE symbol LIKE '%BTC%' AND timeframe='15m'
            ORDER BY timestamp DESC LIMIT 3
        ''', conn)
        print(df.to_string(index=False))
else:
    print('  ❌ Tabella non trovata!')

# Check ml_training_labels
print('\n' + '='*80)
print('\n🎯 ML_TRAINING_LABELS (Labels da Tab ML):')
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ml_training_labels'")
if cur.fetchone():
    cur.execute('SELECT COUNT(*) FROM ml_training_labels')
    count = cur.fetchone()[0]
    print(f'  Righe totali: {count:,}')
    
    if count > 0:
        cur.execute('SELECT COUNT(DISTINCT symbol) FROM ml_training_labels')
        print(f'  Symbols: {cur.fetchone()[0]}')
        
        cur.execute('SELECT AVG(score_long), AVG(score_short) FROM ml_training_labels')
        avg = cur.fetchone()
        print(f'  Avg score_long: {(avg[0] or 0)*100:.4f}%')
        print(f'  Avg score_short: {(avg[1] or 0)*100:.4f}%')
        
        cur.execute('PRAGMA table_info(ml_training_labels)')
        cols = [r[1] for r in cur.fetchall()]
        print(f'  Colonne ({len(cols)}): {cols}')
        
        print('\n  📝 Sample labels (ultime 5 righe BTC):')
        df = pd.read_sql_query('''
            SELECT timestamp, symbol, score_long, score_short, mfe_long, mae_long, bars_held_long, exit_type_long
            FROM ml_training_labels 
            WHERE symbol LIKE '%BTC%' 
            ORDER BY timestamp DESC LIMIT 5
        ''', conn)
        print(df.to_string(index=False))
    else:
        print('  ⚠️ Tabella vuota - nessun label generato dalla Tab ML')
else:
    print('  ❌ Tabella non trovata!')

# Check training_labels (alternativa da run_full_training_pipeline)
print('\n' + '='*80)
print('\n🏷️ TRAINING_LABELS (da run_full_training_pipeline):')
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_labels'")
if cur.fetchone():
    cur.execute('SELECT COUNT(*) FROM training_labels')
    count = cur.fetchone()[0]
    print(f'  Righe totali: {count:,}')
    if count > 0:
        cur.execute('SELECT COUNT(DISTINCT symbol) FROM training_labels')
        print(f'  Symbols: {cur.fetchone()[0]}')
        
        cur.execute('PRAGMA table_info(training_labels)')
        cols = [r[1] for r in cur.fetchall()]
        print(f'  Colonne ({len(cols)}): {cols}')
        
        print('\n  📝 Sample (ultime 5 righe BTC):')
        df = pd.read_sql_query('''
            SELECT timestamp, symbol, score_long, score_short, mfe_long, mae_long
            FROM training_labels 
            WHERE symbol LIKE '%BTC%' 
            ORDER BY timestamp DESC LIMIT 5
        ''', conn)
        print(df.to_string(index=False))
else:
    print('  ❌ Tabella non trovata!')

# Test JOIN tra training_data e ml_training_labels
print('\n' + '='*80)
print('\n🔗 TEST JOIN (training_data + ml_training_labels):')
try:
    df = pd.read_sql_query('''
        SELECT 
            l.timestamp, l.symbol, l.score_long, l.score_short,
            h.close, h.rsi, h.macd
        FROM ml_training_labels l
        INNER JOIN training_data h 
            ON l.symbol = h.symbol 
            AND l.timeframe = h.timeframe 
            AND l.timestamp = h.timestamp
        WHERE l.symbol LIKE '%BTC%'
        ORDER BY l.timestamp DESC
        LIMIT 5
    ''', conn)
    if len(df) > 0:
        print(f'  ✅ JOIN funziona! ({len(df)} righe)')
        print(df.to_string(index=False))
    else:
        print('  ⚠️ JOIN vuoto - possibili problemi di allineamento timestamp')
except Exception as e:
    print(f'  ❌ Errore JOIN: {e}')

conn.close()
print('\n' + '='*80)
print('✅ Ispezione completata!')
