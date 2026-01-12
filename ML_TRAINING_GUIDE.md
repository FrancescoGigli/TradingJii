# 🚀 Guida ML Training Pipeline

## 📋 Architettura del Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PIPELINE ML COMPLETA                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1️⃣ DATI STORICI (historical_ohlcv)                                │
│     │ - OHLCV candles per ogni symbol/timeframe                    │
│     │ - 64 indicatori tecnici calcolati                            │
│     │ - SMA, EMA, RSI, MACD, Bollinger, ATR, etc.                  │
│     ▼                                                               │
│  2️⃣ LABELS (ml_training_labels)                                    │
│     │ - score_long: punteggio trade LONG                           │
│     │ - score_short: punteggio trade SHORT                         │
│     │ - Calcolati con Trailing Stop Simulation                     │
│     ▼                                                               │
│  3️⃣ DATASET UNITO (INNER JOIN)                                     │
│     │ - 88 colonne totali                                          │
│     │ - Features (X) + Labels (y)                                  │
│     │ - Filtro righe con NaN                                       │
│     ▼                                                               │
│  4️⃣ TRAINING (train.py)                                            │
│     │ - Split temporale 80/20                                      │
│     │ - StandardScaler                                             │
│     │ - 2 modelli XGBoost (LONG + SHORT)                          │
│     ▼                                                               │
│  5️⃣ MODELLI SALVATI (shared/models/)                               │
│     - model_long_latest.pkl                                        │
│     - model_short_latest.pkl                                       │
│     - scaler_latest.pkl                                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Cosa Predice il Modello

### Target: `score_long` e `score_short`

Questi score sono calcolati con **Trailing Stop Simulation**:

Per ogni candela, si simula:
1. Un trade LONG: entra al close, trailing stop segue i massimi
2. Un trade SHORT: entra al close, trailing stop segue i minimi

**Formula dello Score:**
```
score = R - λ * log(1 + D) - costs

Dove:
- R = realized_return = (exit_price - entry_price) / entry_price
- D = bars_held (numero di candele tenute)
- λ = time_penalty_lambda (0.001) - penalizza trade lunghi
- costs = trading_cost (0.001 = 0.1%)
```

**Parametri (15m timeframe):**
- `trailing_stop_pct`: 1.5% trailing stop
- `max_bars`: 48 candele (12 ore max)

**Exit Types:**
- `trailing`: uscito per trailing stop (prezzo sceso di 1.5% dal max)
- `time`: uscito per timeout (48 candele raggiunte)

**Interpretazione:**
- `score > 0` → Trade profittevole (dopo costi e time penalty)
- `score < 0` → Trade in perdita
- `score ≈ 0` → Trade neutro

---

## 📊 Features (X) - Cosa "vede" il modello

Il modello usa **69 features** che descrivono lo stato del mercato al tempo `t`:

### OHLCV Base (5)
```
open, high, low, close, volume
```

### Trend / Medie Mobili (4)
```
sma_20, sma_50, ema_12, ema_26
```

### Bollinger Bands (5)
```
bb_upper, bb_mid, bb_lower, bb_width, bb_position
```

### Momentum (6)
```
rsi, macd, macd_signal, macd_hist, stoch_k, stoch_d
```

### Volatilità (2)
```
atr, atr_pct
```

### Volume (2)
```
obv, volume_sma
```

### ADX (2)
```
adx_14, adx_14_norm
```

### Returns (3)
```
ret_5, ret_10, ret_20
```

### EMA Distances (5)
```
ema_20_dist, ema_50_dist, ema_200_dist, ema_20_50_cross, ema_50_200_cross
```

### Altre (35+)
```
rsi_14_norm, macd_hist_norm, trend_direction, momentum_10, momentum_20,
vol_5, vol_10, vol_20, range_pct_5, range_pct_10, range_pct_20,
vol_percentile, vol_ratio, vol_change, obv_slope, vwap_dist, vol_stability,
body_pct, candle_direction, upper_shadow_pct, lower_shadow_pct,
gap_pct, consecutive_up, consecutive_down, speed_5, speed_20, accel_5, accel_20,
ret_percentile_50, ret_percentile_100, price_position_20, price_position_50,
price_position_100, dist_from_high_20, dist_from_low_20
```

---

## ⛔ Colonne ESCLUSE (mai usare come feature!)

Queste colonne contengono **informazioni future** → data leakage!

```
❌ score_long, score_short          # Target (y)
❌ realized_return_long/short       # Risultato futuro
❌ mfe_long/short                   # Max favorable excursion (futuro)
❌ mae_long/short                   # Max adverse excursion (futuro)
❌ bars_held_long/short             # Durata trade (futuro)
❌ exit_type_long/short             # Come è uscito (futuro)
❌ trailing_stop_pct, max_bars      # Config labeling
❌ timestamp, symbol, timeframe     # Identificatori
```

---

## 🔀 Split Temporale (FONDAMENTALE!)

```
┌──────────────────────────────────────────────────────────────────┐
│                    TIMELINE DEI DATI                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  2025-01-07 ─────────────────────────────────────> 2026-01-07   │
│                                                                  │
│  ├─────────────── TRAIN 80% ───────────────┼──── TEST 20% ─────┤│
│  │           2.67M samples                 │    668K samples   ││
│  │        (Jan 2025 → Nov 2025)           │  (Nov 2025 →      ││
│  │                                        │    Jan 2026)       ││
│  └─────────────────────────────────────────┴────────────────────┘│
│                                                                  │
│  ⚠️ MAI SHUFFLARE! Il modello non deve "vedere il futuro"       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Come Eseguire il Training

### Prerequisiti
```bash
pip install xgboost scikit-learn pandas numpy
```

### Comando base
```bash
cd agents/ml-training
python train.py
```

### Con filtri
```bash
# Solo BTC
python train.py --symbol BTC

# Solo timeframe 15m
python train.py --timeframe 15m

# Entrambi
python train.py --symbol BTC --timeframe 15m
```

### Output
```
shared/models/
├── model_long_latest.pkl      # Modello LONG
├── model_short_latest.pkl     # Modello SHORT
├── scaler_latest.pkl          # StandardScaler
└── metadata_latest.json       # Config + metriche
```

---

## 📈 Metriche Training (ultimo run)

### Metriche Standard (R², RMSE)

| Modello | R² Train | R² Test | RMSE Train | RMSE Test |
|---------|----------|---------|------------|-----------|
| LONG    | 0.0393   | 0.0346  | 0.0143     | 0.0151    |
| SHORT   | 0.0848   | 0.0234  | 0.0142     | 0.0143    |

---

## 🎯 Metriche di Ranking (QUELLE CHE CONTANO!)

**Queste metriche rispondono alla domanda chiave:**
> "Quando il modello dice 'questo trade è migliore di quello', ha ragione?"

### Spearman Rank Correlation

| Modello | Spearman | Qualità |
|---------|----------|---------|
| LONG    | **0.0540** | 🟡 GOOD |
| SHORT   | 0.0369   | 🟠 WEAK |

**Interpretazione:**
- `> 0.10` → 🟢 EXCELLENT (segnale forte)
- `> 0.05` → 🟡 GOOD (segnale reale)
- `> 0.02` → 🟠 WEAK (segnale debole)
- `< 0.02` → 🔴 NO SIGNAL

### Precision@K (la metrica più pratica!)

**LONG Model:**
| Top K% | Avg Score | % Positive |
|--------|-----------|------------|
| **1%** | **0.0197** | **60.2%** ✅ |
| 5%     | 0.0038    | 41.9%      |
| 10%    | -0.0007   | 33.6%      |
| 20%    | -0.0030   | 29.5%      |

**SHORT Model:**
| Top K% | Avg Score | % Positive |
|--------|-----------|------------|
| **1%** | **0.0185** | **61.8%** ✅ |
| 5%     | 0.0027    | 41.2%      |
| 10%    | -0.0009   | 35.1%      |
| 20%    | -0.0028   | 31.9%      |

**🔥 Risultato chiave:** Se fai SOLO i trade nel **top 1%** predetto dal modello:
- Score medio **positivo** (~0.02)
- **60%** probabilità che il trade sia profittevole
- Questo è un edge reale!

---

### Top 10 Features (LONG model)
| Feature | Importance |
|---------|------------|
| atr_pct | 8.27% |
| range_pct_5 | 5.99% |
| bb_position | 4.54% |
| ema_20_dist | 3.34% |
| bb_width | 3.22% |
| vol_change | 2.31% |
| stoch_k | 2.27% |
| vol_ratio | 2.11% |
| stoch_d | 1.87% |
| dist_from_high_20 | 1.86% |

---

## 🔮 Come Usare i Modelli per Previsioni

```python
import pickle
import pandas as pd
from sklearn.preprocessing import StandardScaler

# 1. Carica modelli
with open('shared/models/model_long_latest.pkl', 'rb') as f:
    model_long = pickle.load(f)

with open('shared/models/scaler_latest.pkl', 'rb') as f:
    scaler = pickle.load(f)

# 2. Prepara nuovi dati (stesse 69 features!)
new_data = pd.DataFrame([{
    'open': 94000,
    'high': 94500,
    'low': 93800,
    'close': 94200,
    'volume': 1000,
    'sma_20': 93500,
    # ... tutte le altre 64 features
}])

# 3. Scala
X_scaled = scaler.transform(new_data)

# 4. Predici
predicted_score_long = model_long.predict(X_scaled)

print(f"Predicted score LONG: {predicted_score_long[0]:.4f}")
# > 0 = segnale bullish
# < 0 = segnale bearish
```

---

## ⚠️ Note Importanti

### Perché R² è basso (3-4%)?

È **normale** per mercati finanziari:
- I mercati sono rumorosi e quasi-random
- R² = 3% significa che il modello cattura il 3% della varianza
- Anche piccoli edge (1-2%) possono essere profittevoli nel lungo termine

### Come migliorare?

1. **Feature Engineering**: aggiungere nuove features
2. **Hyperparameter Tuning**: ottimizzare max_depth, learning_rate, etc.
3. **Ensemble**: combinare più modelli
4. **Walk-Forward Validation**: ritraining periodico

---

## 📁 File del Progetto

```
agents/ml-training/
├── train.py                  # 🎯 Script principale
├── config.py                 # Configurazione
├── requirements.txt          # Dipendenze
└── core/
    ├── dataset.py           # DatasetBuilder, TemporalSplitter
    └── trainer.py           # (per uso futuro)

shared/models/                # 📦 Modelli salvati
├── model_long_*.pkl
├── model_short_*.pkl
├── scaler_*.pkl
└── metadata_*.json
```
