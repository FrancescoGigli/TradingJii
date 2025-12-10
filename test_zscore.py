"""
Test Script: Verifica Z-Score Normalization
Simula dati BTC e PEPE per verificare che diventino comparabili
"""

import pandas as pd
import numpy as np
from data_utils import add_z_score_normalization

print("=" * 70)
print("🧪 TEST Z-SCORE NORMALIZATION")
print("=" * 70)

# Test 1: Crea dati simulati BTC (high price, high volume)
print("\n1️⃣ CREAZIONE DATI SIMULATI BTC:")
btc_data = pd.DataFrame({
    'close': np.random.normal(100000, 1000, 200),  # $100K ± $1K
    'volume': np.random.normal(1000, 100, 200),     # 1000 BTC ± 100
    'rsi_fast': np.random.normal(50, 15, 200),
    'macd': np.random.normal(100, 50, 200),
    'atr': np.random.normal(2000, 200, 200),
    'volatility': np.random.normal(2, 1, 200),
    'obv': np.cumsum(np.random.randn(200) * 1000),
    'vwap': np.random.normal(100000, 1000, 200),
    'adx': np.random.normal(30, 10, 200),
    'stoch_rsi': np.random.uniform(0, 1, 200),
    'macd_signal': np.random.normal(95, 50, 200),
    'macd_histogram': np.random.normal(5, 20, 200)
})

print(f"   BTC Close: mean={btc_data['close'].mean():.0f}, std={btc_data['close'].std():.0f}")
print(f"   BTC Volume: mean={btc_data['volume'].mean():.0f}, std={btc_data['volume'].std():.0f}")

# Test 2: Crea dati simulati PEPE (low price, huge volume)
print("\n2️⃣ CREAZIONE DATI SIMULATI PEPE:")
pepe_data = pd.DataFrame({
    'close': np.random.normal(0.00001, 0.000001, 200),  # $0.00001 ± $0.000001
    'volume': np.random.normal(1000000000, 100000000, 200),  # 1B PEPE ± 100M
    'rsi_fast': np.random.normal(50, 15, 200),
    'macd': np.random.normal(0.0000001, 0.00000005, 200),
    'atr': np.random.normal(0.0000005, 0.00000005, 200),
    'volatility': np.random.normal(2, 1, 200),
    'obv': np.cumsum(np.random.randn(200) * 1000000),
    'vwap': np.random.normal(0.00001, 0.000001, 200),
    'adx': np.random.normal(30, 10, 200),
    'stoch_rsi': np.random.uniform(0, 1, 200),
    'macd_signal': np.random.normal(0.0000001, 0.00000005, 200),
    'macd_histogram': np.random.normal(0.00000001, 0.000000005, 200)
})

print(f"   PEPE Close: mean={pepe_data['close'].mean():.8f}, std={pepe_data['close'].std():.8f}")
print(f"   PEPE Volume: mean={pepe_data['volume'].mean():.0f}, std={pepe_data['volume'].std():.0f}")

# Test 3: Applica Z-Score normalization
print("\n3️⃣ APPLICAZIONE Z-SCORE:")
btc_normalized = add_z_score_normalization(btc_data.copy(), window=96)
pepe_normalized = add_z_score_normalization(pepe_data.copy(), window=96)

print("   ✅ Z-Score applicato a BTC")
print("   ✅ Z-Score applicato a PEPE")

# Test 4: Verifica che gli z-score siano nello stesso range
print("\n4️⃣ VERIFICA COMPARABILITÀ:")
print("\n   BTC Z-Scores:")
print(f"      close_zscore: mean={btc_normalized['close_zscore'].mean():.3f}, std={btc_normalized['close_zscore'].std():.3f}")
print(f"      volume_zscore: mean={btc_normalized['volume_zscore'].mean():.3f}, std={btc_normalized['volume_zscore'].std():.3f}")
print(f"      range: [{btc_normalized['close_zscore'].min():.2f}, {btc_normalized['close_zscore'].max():.2f}]")

print("\n   PEPE Z-Scores:")
print(f"      close_zscore: mean={pepe_normalized['close_zscore'].mean():.3f}, std={pepe_normalized['close_zscore'].std():.3f}")
print(f"      volume_zscore: mean={pepe_normalized['volume_zscore'].mean():.3f}, std={pepe_normalized['volume_zscore'].std():.3f}")
print(f"      range: [{pepe_normalized['close_zscore'].min():.2f}, {pepe_normalized['close_zscore'].max():.2f}]")

# Test 5: Verifica clipping a ±5
print("\n5️⃣ VERIFICA CLIPPING (±5 sigma):")
all_columns_btc = [col for col in btc_normalized.columns if col.endswith('_zscore')]
all_columns_pepe = [col for col in pepe_normalized.columns if col.endswith('_zscore')]

max_btc = max(btc_normalized[col].abs().max() for col in all_columns_btc)
max_pepe = max(pepe_normalized[col].abs().max() for col in all_columns_pepe)

print(f"   Max |z-score| BTC: {max_btc:.2f}")
print(f"   Max |z-score| PEPE: {max_pepe:.2f}")

assert max_btc <= 5.0, f"❌ BTC z-score non clippato: {max_btc}"
assert max_pepe <= 5.0, f"❌ PEPE z-score non clippato: {max_pepe}"
print("   ✅ Tutti i valori entro ±5 sigma")

# Test 6: Verifica assenza di NaN/Inf
print("\n6️⃣ VERIFICA NaN/Inf:")
nan_btc = btc_normalized[[col for col in btc_normalized.columns if col.endswith('_zscore')]].isna().sum().sum()
nan_pepe = pepe_normalized[[col for col in pepe_normalized.columns if col.endswith('_zscore')]].isna().sum().sum()
inf_btc = np.isinf(btc_normalized[[col for col in btc_normalized.columns if col.endswith('_zscore')]]).sum().sum()
inf_pepe = np.isinf(pepe_normalized[[col for col in pepe_normalized.columns if col.endswith('_zscore')]]).sum().sum()

print(f"   BTC: NaN={nan_btc}, Inf={inf_btc}")
print(f"   PEPE: NaN={nan_pepe}, Inf={inf_pepe}")

assert nan_btc == 0, f"❌ BTC contiene NaN: {nan_btc}"
assert nan_pepe == 0, f"❌ PEPE contiene NaN: {nan_pepe}"
assert inf_btc == 0, f"❌ BTC contiene Inf: {inf_btc}"
assert inf_pepe == 0, f"❌ PEPE contiene Inf: {inf_pepe}"
print("   ✅ Nessun NaN o Inf presente")

# Test 7: Simula anomalia (spike) e verifica detection
print("\n7️⃣ TEST ANOMALY DETECTION:")
# Aggiungi spike a BTC
btc_spike = btc_data.copy()
btc_spike.loc[150, 'volume'] = btc_spike['volume'].mean() * 4  # 4x normal volume
btc_spike_norm = add_z_score_normalization(btc_spike, window=96)

# Aggiungi spike a PEPE
pepe_spike = pepe_data.copy()
pepe_spike.loc[150, 'volume'] = pepe_spike['volume'].mean() * 4  # 4x normal volume
pepe_spike_norm = add_z_score_normalization(pepe_spike, window=96)

btc_spike_zscore = btc_spike_norm.loc[150, 'volume_zscore']
pepe_spike_zscore = pepe_spike_norm.loc[150, 'volume_zscore']

print(f"   BTC volume spike z-score: {btc_spike_zscore:.2f}")
print(f"   PEPE volume spike z-score: {pepe_spike_zscore:.2f}")
print(f"   Differenza: {abs(btc_spike_zscore - pepe_spike_zscore):.2f}")

# Entrambi dovrebbero essere ~3 sigma (anomalia significativa)
# <= 5.0 perché il clipping li porta esattamente a 5.0
assert 2.5 < btc_spike_zscore <= 5.0, f"❌ BTC spike non detectato correttamente: {btc_spike_zscore}"
assert 2.5 < pepe_spike_zscore <= 5.0, f"❌ PEPE spike non detectato correttamente: {pepe_spike_zscore}"
print("   ✅ Spike detectato correttamente su entrambi")

# Summary
print("\n" + "=" * 70)
print("✅ TUTTI I TEST PASSATI!")
print("=" * 70)
print("\n📊 RISULTATI:")
print("   • Z-Score rende BTC e PEPE comparabili")
print("   • Valori clippati correttamente a ±5 sigma")
print("   • Nessun NaN o Inf presente")
print("   • Anomalie (spike) detectate in modo uniforme")
print("   • Global Model può ora usare questi dati insieme!")
print("\n🚀 Step 2 completato! Pronto per Step 3 (Triple Barrier)\n")
