"""
Analisi dettagliata degli score e dei risultati delle labels
"""
import sqlite3
import pandas as pd
import numpy as np

# Connessione al database
conn = sqlite3.connect('shared/data_cache/training_data.db')

# Ottieni statistiche dalla VIEW v_xgb_training
print("=" * 80)
print("📊 ANALISI COMPLETA LABELS - v_xgb_training VIEW")
print("=" * 80)

# Check se la VIEW esiste
check = pd.read_sql_query(
    "SELECT name FROM sqlite_master WHERE type='view' AND name='v_xgb_training'", conn
)
if len(check) == 0:
    print("❌ VIEW v_xgb_training non esiste!")
    exit()

# Statistiche generali
print("\n📈 STATISTICHE GENERALI:")
stats = pd.read_sql_query('''
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT symbol) as symbols,
        COUNT(DISTINCT timeframe) as timeframes,
        MIN(timestamp) as first_date,
        MAX(timestamp) as last_date
    FROM v_xgb_training
''', conn)
print(stats.to_string(index=False))

# Statistiche per timeframe
print("\n\n📊 STATISTICHE PER TIMEFRAME:")
tf_stats = pd.read_sql_query('''
    SELECT 
        timeframe,
        COUNT(*) as rows,
        COUNT(DISTINCT symbol) as symbols,
        ROUND(AVG(score_long), 6) as avg_score_long,
        ROUND(AVG(score_short), 6) as avg_score_short,
        ROUND(SUM(CASE WHEN score_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as pct_positive_long,
        ROUND(SUM(CASE WHEN score_short > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as pct_positive_short
    FROM v_xgb_training
    GROUP BY timeframe
''', conn)
print(tf_stats.to_string(index=False))

# Analisi degli SCORE
print("\n\n🎯 ANALISI SCORE (score_long & score_short):")
score_analysis = pd.read_sql_query('''
    SELECT 
        ROUND(AVG(score_long), 6) as mean_long,
        ROUND(MIN(score_long), 6) as min_long,
        ROUND(MAX(score_long), 6) as max_long,
        ROUND(AVG(score_short), 6) as mean_short,
        ROUND(MIN(score_short), 6) as min_short,
        ROUND(MAX(score_short), 6) as max_short
    FROM v_xgb_training
''', conn)
print(score_analysis.to_string(index=False))

# Distribuzione dei return
print("\n\n💰 DISTRIBUZIONE RETURN REALIZZATI:")
return_analysis = pd.read_sql_query('''
    SELECT 
        ROUND(AVG(realized_return_long) * 100, 4) as avg_return_long_pct,
        ROUND(MIN(realized_return_long) * 100, 4) as min_return_long_pct,
        ROUND(MAX(realized_return_long) * 100, 4) as max_return_long_pct,
        ROUND(AVG(realized_return_short) * 100, 4) as avg_return_short_pct,
        ROUND(MIN(realized_return_short) * 100, 4) as min_return_short_pct,
        ROUND(MAX(realized_return_short) * 100, 4) as max_return_short_pct
    FROM v_xgb_training
''', conn)
print(return_analysis.to_string(index=False))

# MFE e MAE
print("\n\n📉 MFE (Max Favorable) e MAE (Max Adverse) Excursion:")
mfe_mae = pd.read_sql_query('''
    SELECT 
        ROUND(AVG(mfe_long) * 100, 4) as avg_mfe_long_pct,
        ROUND(AVG(mae_long) * 100, 4) as avg_mae_long_pct,
        ROUND(AVG(mfe_short) * 100, 4) as avg_mfe_short_pct,
        ROUND(AVG(mae_short) * 100, 4) as avg_mae_short_pct
    FROM v_xgb_training
''', conn)
print(mfe_mae.to_string(index=False))

# Exit types distribution
print("\n\n🚪 DISTRIBUZIONE EXIT TYPES:")
exit_types = pd.read_sql_query('''
    SELECT 
        exit_type_long,
        COUNT(*) as count_long,
        ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM v_xgb_training), 2) as pct_long
    FROM v_xgb_training
    GROUP BY exit_type_long
    ORDER BY count_long DESC
''', conn)
print("LONG Exits:")
print(exit_types.to_string(index=False))

exit_types_short = pd.read_sql_query('''
    SELECT 
        exit_type_short,
        COUNT(*) as count_short,
        ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM v_xgb_training), 2) as pct_short
    FROM v_xgb_training
    GROUP BY exit_type_short
    ORDER BY count_short DESC
''', conn)
print("\nSHORT Exits:")
print(exit_types_short.to_string(index=False))

# Bars held
print("\n\n⏱️ BARS HELD (durata posizioni):")
bars = pd.read_sql_query('''
    SELECT 
        ROUND(AVG(bars_held_long), 1) as avg_bars_long,
        MIN(bars_held_long) as min_bars_long,
        MAX(bars_held_long) as max_bars_long,
        ROUND(AVG(bars_held_short), 1) as avg_bars_short,
        MIN(bars_held_short) as min_bars_short,
        MAX(bars_held_short) as max_bars_short
    FROM v_xgb_training
''', conn)
print(bars.to_string(index=False))

# Analisi per simbolo (Top 5)
print("\n\n🏆 TOP 5 SIMBOLI PER AVG SCORE LONG:")
top_symbols = pd.read_sql_query('''
    SELECT 
        REPLACE(symbol, '/USDT:USDT', '') as symbol,
        COUNT(*) as rows,
        ROUND(AVG(score_long), 6) as avg_score_long,
        ROUND(AVG(realized_return_long) * 100, 4) as avg_return_pct,
        ROUND(SUM(CASE WHEN exit_type_long = 'trailing' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as pct_trailing
    FROM v_xgb_training
    GROUP BY symbol
    ORDER BY avg_score_long DESC
    LIMIT 5
''', conn)
print(top_symbols.to_string(index=False))

print("\n\n🔻 BOTTOM 5 SIMBOLI PER AVG SCORE LONG:")
bottom_symbols = pd.read_sql_query('''
    SELECT 
        REPLACE(symbol, '/USDT:USDT', '') as symbol,
        COUNT(*) as rows,
        ROUND(AVG(score_long), 6) as avg_score_long,
        ROUND(AVG(realized_return_long) * 100, 4) as avg_return_pct,
        ROUND(SUM(CASE WHEN exit_type_long = 'trailing' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as pct_trailing
    FROM v_xgb_training
    GROUP BY symbol
    ORDER BY avg_score_long ASC
    LIMIT 5
''', conn)
print(bottom_symbols.to_string(index=False))

# Correlazione score vs return
print("\n\n🔗 CORRELAZIONE SCORE vs RETURN:")
df = pd.read_sql_query('''
    SELECT score_long, realized_return_long, score_short, realized_return_short
    FROM v_xgb_training
    WHERE score_long IS NOT NULL AND realized_return_long IS NOT NULL
''', conn)

if len(df) > 0:
    corr_long = df['score_long'].corr(df['realized_return_long'])
    corr_short = df['score_short'].corr(df['realized_return_short'])
    print(f"  Correlazione score_long vs realized_return_long: {corr_long:.4f}")
    print(f"  Correlazione score_short vs realized_return_short: {corr_short:.4f}")
else:
    print("  Dati insufficienti per calcolare la correlazione")

# Sample di dati per BTC
print("\n\n📋 SAMPLE DATI BTC (ultime 10 righe):")
btc_sample = pd.read_sql_query('''
    SELECT 
        timestamp,
        ROUND(close, 2) as close,
        ROUND(rsi, 1) as rsi,
        ROUND(score_long, 5) as score_long,
        ROUND(score_short, 5) as score_short,
        ROUND(realized_return_long * 100, 3) as ret_long_pct,
        exit_type_long,
        bars_held_long
    FROM v_xgb_training
    WHERE symbol LIKE '%BTC%' AND timeframe = '15m'
    ORDER BY timestamp DESC
    LIMIT 10
''', conn)
print(btc_sample.to_string(index=False))

# Verifica qualità dati
print("\n\n🔍 VERIFICA QUALITÀ DATI:")
nulls = pd.read_sql_query('''
    SELECT 
        SUM(CASE WHEN score_long IS NULL THEN 1 ELSE 0 END) as null_score_long,
        SUM(CASE WHEN score_short IS NULL THEN 1 ELSE 0 END) as null_score_short,
        SUM(CASE WHEN realized_return_long IS NULL THEN 1 ELSE 0 END) as null_return_long,
        SUM(CASE WHEN rsi IS NULL THEN 1 ELSE 0 END) as null_rsi,
        SUM(CASE WHEN atr IS NULL THEN 1 ELSE 0 END) as null_atr
    FROM v_xgb_training
''', conn)
print(nulls.to_string(index=False))

conn.close()

print("\n" + "=" * 80)
print("✅ ANALISI COMPLETATA")
print("=" * 80)
