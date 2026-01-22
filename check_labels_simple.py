import sqlite3
import pandas as pd

conn = sqlite3.connect('/app/shared/data_cache/trading_data.db')

print("=" * 70)
print("TABELLE NEL DATABASE:")
tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn)
print(tables.to_string(index=False))

print("\n" + "=" * 70)
print("ANALISI TRAINING_LABELS:")
try:
    stats = pd.read_sql_query("""
        SELECT 
            COUNT(*) as total_rows,
            COUNT(DISTINCT symbol) as symbols,
            ROUND(AVG(score_long), 6) as avg_score_long,
            ROUND(AVG(score_short), 6) as avg_score_short,
            ROUND(AVG(realized_return_long) * 100, 4) as avg_ret_long_pct,
            ROUND(AVG(realized_return_short) * 100, 4) as avg_ret_short_pct
        FROM training_labels
    """, conn)
    print(stats.to_string(index=False))
    
    print("\n" + "-" * 70)
    print("PER TIMEFRAME:")
    tf = pd.read_sql_query("""
        SELECT 
            timeframe,
            COUNT(*) as rows,
            ROUND(AVG(score_long), 6) as avg_score_long,
            ROUND(AVG(score_short), 6) as avg_score_short,
            ROUND(SUM(CASE WHEN score_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as pct_pos_long
        FROM training_labels
        GROUP BY timeframe
    """, conn)
    print(tf.to_string(index=False))
    
    print("\n" + "-" * 70)
    print("EXIT TYPES LONG:")
    exits = pd.read_sql_query("""
        SELECT 
            exit_type_long,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM training_labels), 2) as pct
        FROM training_labels
        GROUP BY exit_type_long
        ORDER BY count DESC
    """, conn)
    print(exits.to_string(index=False))
    
    print("\n" + "-" * 70)
    print("SCORE RANGE:")
    scores = pd.read_sql_query("""
        SELECT 
            ROUND(MIN(score_long), 6) as min_score_long,
            ROUND(MAX(score_long), 6) as max_score_long,
            ROUND(MIN(score_short), 6) as min_score_short,
            ROUND(MAX(score_short), 6) as max_score_short
        FROM training_labels
    """, conn)
    print(scores.to_string(index=False))
    
    print("\n" + "-" * 70)
    print("RETURN RANGE:")
    rets = pd.read_sql_query("""
        SELECT 
            ROUND(MIN(realized_return_long) * 100, 4) as min_ret_long_pct,
            ROUND(MAX(realized_return_long) * 100, 4) as max_ret_long_pct,
            ROUND(MIN(realized_return_short) * 100, 4) as min_ret_short_pct,
            ROUND(MAX(realized_return_short) * 100, 4) as max_ret_short_pct
        FROM training_labels
    """, conn)
    print(rets.to_string(index=False))
    
    print("\n" + "-" * 70)
    print("TOP 5 SIMBOLI PER SCORE LONG:")
    top = pd.read_sql_query("""
        SELECT 
            REPLACE(symbol, '/USDT:USDT', '') as symbol,
            COUNT(*) as rows,
            ROUND(AVG(score_long), 6) as avg_score
        FROM training_labels
        GROUP BY symbol
        ORDER BY avg_score DESC
        LIMIT 5
    """, conn)
    print(top.to_string(index=False))
    
except Exception as e:
    print(f"Errore: {e}")

conn.close()
print("\n" + "=" * 70)
