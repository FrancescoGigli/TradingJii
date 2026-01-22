import sqlite3
import pandas as pd

conn = sqlite3.connect('/app/shared/data_cache/trading_data.db')

print("=" * 70)
print("📊 QUALITÀ DELLE LABEL - ANALISI APPROFONDITA")
print("=" * 70)

# Analisi delle label POSITIVE (score > 0) vs NEGATIVE
print("\n🎯 CONFRONTO LABEL POSITIVE vs NEGATIVE:")
quality = pd.read_sql_query("""
    SELECT 
        CASE WHEN score_long > 0 THEN 'POSITIVE (entry)' ELSE 'NEGATIVE (skip)' END as label_type,
        COUNT(*) as samples,
        ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM training_labels), 1) as pct,
        ROUND(AVG(realized_return_long) * 100, 3) as avg_return_pct,
        ROUND(AVG(score_long), 5) as avg_score,
        ROUND(MIN(realized_return_long) * 100, 2) as min_return_pct,
        ROUND(MAX(realized_return_long) * 100, 2) as max_return_pct
    FROM training_labels
    GROUP BY CASE WHEN score_long > 0 THEN 'POSITIVE (entry)' ELSE 'NEGATIVE (skip)' END
""", conn)
print(quality.to_string(index=False))

# Analisi solo label positive - distribuzione return
print("\n" + "-" * 70)
print("📈 DISTRIBUZIONE RETURN DELLE LABEL POSITIVE (score > 0):")
positive = pd.read_sql_query("""
    SELECT 
        CASE 
            WHEN realized_return_long > 0.05 THEN '5+ > +5%'
            WHEN realized_return_long > 0.02 THEN '4. +2% to +5%'
            WHEN realized_return_long > 0.01 THEN '3. +1% to +2%'
            WHEN realized_return_long > 0 THEN '2. 0% to +1%'
            ELSE '1. Negative'
        END as return_bucket,
        COUNT(*) as count,
        ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM training_labels WHERE score_long > 0), 1) as pct_of_positive,
        ROUND(AVG(realized_return_long) * 100, 3) as avg_return_pct
    FROM training_labels
    WHERE score_long > 0
    GROUP BY return_bucket
    ORDER BY return_bucket DESC
""", conn)
print(positive.to_string(index=False))

# Win rate teorico se il modello fosse perfetto
print("\n" + "-" * 70)
print("🏆 POTENZIALE TEORICO (se il modello fosse perfetto):")
theoretical = pd.read_sql_query("""
    SELECT 
        SUM(CASE WHEN realized_return_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate_positive_labels,
        SUM(CASE WHEN realized_return_long > 0 THEN realized_return_long ELSE 0 END) * 100 / COUNT(*) as gross_profit_pct,
        SUM(CASE WHEN realized_return_long < 0 THEN ABS(realized_return_long) ELSE 0 END) * 100 / COUNT(*) as gross_loss_pct
    FROM training_labels
    WHERE score_long > 0
""", conn)
theoretical['profit_factor'] = theoretical['gross_profit_pct'] / theoretical['gross_loss_pct']
print(f"  Win Rate Label Positive: {theoretical['win_rate_positive_labels'].values[0]:.1f}%")
print(f"  Profit Factor Label Positive: {theoretical['profit_factor'].values[0]:.2f}")

# Top scoring ranges
print("\n" + "-" * 70)
print("🔥 PERFORMANCE PER RANGE DI SCORE:")
ranges = pd.read_sql_query("""
    SELECT 
        CASE 
            WHEN score_long > 0.1 THEN 'A. Score > 0.10 (excellent)'
            WHEN score_long > 0.05 THEN 'B. Score 0.05-0.10 (very good)'
            WHEN score_long > 0.02 THEN 'C. Score 0.02-0.05 (good)'
            WHEN score_long > 0 THEN 'D. Score 0-0.02 (marginal)'
            WHEN score_long > -0.02 THEN 'E. Score -0.02-0 (avoid)'
            ELSE 'F. Score < -0.02 (bad)'
        END as score_range,
        COUNT(*) as samples,
        ROUND(AVG(realized_return_long) * 100, 3) as avg_return_pct,
        ROUND(SUM(CASE WHEN realized_return_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate
    FROM training_labels
    GROUP BY score_range
    ORDER BY score_range
""", conn)
print(ranges.to_string(index=False))

# Correlazione score vs return
print("\n" + "-" * 70)
print("📊 CORRELAZIONE SCORE vs RETURN:")
df = pd.read_sql_query("SELECT score_long, realized_return_long FROM training_labels", conn)
corr = df['score_long'].corr(df['realized_return_long'])
print(f"  Pearson Correlation: {corr:.4f}")

if corr > 0.8:
    print("  → 🟢 ECCELLENTE - Lo score predice molto bene il return")
elif corr > 0.5:
    print("  → 🟡 BUONO - Lo score ha un buon potere predittivo")
elif corr > 0.3:
    print("  → 🟠 MODERATO - Lo score ha un potere predittivo discreto")
else:
    print("  → 🔴 DEBOLE - Lo score ha basso potere predittivo")

conn.close()
print("\n" + "=" * 70)
