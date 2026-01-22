# 🎯 ML Labels Documentation - ATR-Based System

## Overview

Il sistema di labeling genera etichette di training per XGBoost usando simulazione ATR-based.
I parametri sono scelti per **STABILITÀ** cross-asset, non per massimizzare performance.

---

## 🔧 Logica ATR-Based

### Parametri Globali (k_*)

| Parametro | 15m | 1h | Descrizione |
|-----------|-----|-----|-------------|
| `k_fixed_sl` | 2.5 | 3.0 | Moltiplicatore ATR per Fixed Stop Loss |
| `k_trailing` | 1.2 | 1.5 | Moltiplicatore ATR per Trailing Stop |
| `max_bars` | 48 | 24 | Massimo candele di holding (12h/24h) |

### Come Funziona

```python
# Per ogni candela di entry:
atr_pct = ATR[entry] / close[entry]  # Es: BTC=1.2%, DOGE=4%

# LONG Entry:
fixed_sl = entry × (1 - k_fixed_sl × atr_pct)     # Fixed, non si muove
trailing_sl = max_seen × (1 - k_trailing × atr_pct)  # Segue il massimo
effective_sl = max(fixed_sl, trailing_sl)          # Lo stop non peggiora mai!

# SHORT Entry:
fixed_sl = entry × (1 + k_fixed_sl × atr_pct)
trailing_sl = min_seen × (1 + k_trailing × atr_pct)
effective_sl = min(fixed_sl, trailing_sl)

# Exit conditions (in ordine di priorità):
1. effective_sl viene colpito → exit_type = 'fixed_sl' o 'trailing'
2. max_bars raggiunto → exit_type = 'time'
```

### Esempio Numerico (BTC 15m)

```
Entry: $100,000
ATR%: 1.2%
k_fixed_sl: 2.5
k_trailing: 1.2

Fixed SL = $100,000 × (1 - 2.5 × 0.012) = $97,000 (fisso!)
Trailing Distance = 1.2 × 0.012 = 1.44%

Scenario 1: Prezzo sale a $102,000
  → Trailing SL = $102,000 × (1 - 0.0144) = $100,532
  → effective_sl = max($97,000, $100,532) = $100,532 ✓

Scenario 2: Prezzo scende subito
  → Trailing non si attiva (max_seen = entry)
  → effective_sl = $97,000 (Fixed SL protegge)
```

---

## 📊 Score Formula

```
score = R - λ×log(1+D) - costs
```

| Componente | Valore | Descrizione |
|------------|--------|-------------|
| R | realized_return | (exit - entry) / entry |
| λ | 0.001 | Time penalty coefficient |
| D | bars_held | Numero candele tenute |
| costs | 0.001 | Trading fees (0.1%) |

### Interpretazione Score

- `score > 0` → Trade profittevole (dopo costi e time penalty)
- `score < 0` → Trade in perdita
- `score ≈ 0` → Breakeven

---

## 📁 Output Labels (per candela)

### Targets (usati per training XGBoost)
| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `score_long` | float | Score per posizione LONG |
| `score_short` | float | Score per posizione SHORT |

### Diagnostics (per analisi, NON usati per training)
| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `realized_return_long/short` | float | Return effettivo |
| `mfe_long/short` | float | Max Favorable Excursion |
| `mae_long/short` | float | Max Adverse Excursion |
| `bars_held_long/short` | int | Candele tenute |
| `exit_type_long/short` | str | 'fixed_sl', 'trailing', 'time' |
| `atr_pct` | float | ATR% al momento dell'entry |

---

## 🔍 Exit Types

| Exit Type | Significato | Quando succede |
|-----------|-------------|----------------|
| `fixed_sl` | Fixed Stop Loss colpito | Il prezzo tocca il livello fisso iniziale |
| `trailing` | Trailing Stop colpito | Il prezzo ritraccia dopo aver fatto profitto |
| `time` | Timeout (max_bars) | Il trade viene chiuso per tempo massimo |

### Distribuzione Ideale

Per parametri stabili, cerca:
- **fixed_sl**: 20-40% (protezione funziona)
- **trailing**: 40-60% (trailing cattura profitti)
- **time**: 10-20% (pochi timeout)

⚠️ **Warning Signs:**
- `fixed_sl > 50%`: k_fixed_sl troppo stretto
- `time > 40%`: max_bars troppo basso
- `trailing < 20%`: k_trailing troppo stretto

---

## 📈 Analisi Post-Labeling

Dopo la generazione labels, usa l'**Analysis Dashboard** per validare:

### 1. MAE Analysis
- **Istogramma MAE**: Distribuzione del max drawdown subito
- **MAE vs Score**: Correlazione tra drawdown e risultato

### 2. Exit Type Analysis
- **Pie chart**: Percentuale per tipo di uscita
- **Confronto LONG/SHORT**: Bilanciamento

### 3. Score Distribution
- **Istogramma**: Distribuzione score LONG vs SHORT
- **% Positive**: Target ~40-60% positivi

### 4. Stability Report
- **Warnings automatici**: Segnala parametri problematici
- **Suggerimenti**: Come aggiustare k_*

---

## 🔄 Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Data Selection                                          │
│ ├── Seleziona symbols con >= 95% completeness                  │
│ └── Carica OHLCV da training_data                              │
├─────────────────────────────────────────────────────────────────┤
│ STEP 2: ATR Calculation                                         │
│ ├── Calcola ATR(14) per ogni candela                           │
│ └── atr_pct = ATR / close                                      │
├─────────────────────────────────────────────────────────────────┤
│ STEP 3: Trade Simulation                                        │
│ ├── Per ogni candela valida:                                   │
│ │   ├── Simula LONG con ATR-based stops                       │
│ │   └── Simula SHORT con ATR-based stops                      │
│ ├── Output: exit_price, bars_held, exit_type, mfe, mae        │
│ └── Calcola score                                              │
├─────────────────────────────────────────────────────────────────┤
│ STEP 4: Save to Database                                        │
│ ├── training_labels table                                       │
│ └── v_xgb_training VIEW (OHLCV + features + labels)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚠️ Principi Fondamentali

### 1. NO Optuna per Labeling Params
I parametri k_* sono scelti per stabilità, NON ottimizzati.
Optuna va usato SOLO per iperparametri XGBoost (learning_rate, depth, etc).

### 2. MAE/MFE Solo Diagnostica
MAE e MFE sono calcolati ex-post e NON entrano nello score o nella simulazione.
Servono solo per validare se i parametri scelti sono sensati.

### 3. Lo Stop Non Peggiora Mai
`effective_sl = max(fixed_sl, trailing_sl)` per LONG garantisce che:
- Il trailing non può abbassare lo stop sotto il fixed
- Una volta che il trailing sale, non scende più

### 4. Parametri Globali = ML-Safe
Usare gli stessi k_* per tutti i symbol garantisce:
- Nessun data leakage
- Modello che generalizza
- Training stabile

---

## 📋 Files Coinvolti

| File | Ruolo |
|------|-------|
| `ai/core/labels.py` | Logica ATR-based, ATRLabeler |
| `components/tabs/train/labeling.py` | UI principale |
| `components/tabs/train/labeling_pipeline.py` | Pipeline generazione |
| `components/tabs/train/labeling_db.py` | Database operations |
| `components/tabs/train/labeling_analysis.py` | Grafici diagnostici |
| `components/tabs/train/labeling_visualizer.py` | Preview candele+labels |

---

## 🆕 Changelog

### v2.0 (ATR-Based)
- ✅ Fixed SL basato su ATR (k_fixed_sl)
- ✅ Trailing basato su ATR (k_trailing)
- ✅ effective_sl = max/min per garantire non-peggioramento
- ✅ exit_type per diagnostica (fixed_sl/trailing/time)
- ✅ atr_pct salvato nel database
- ✅ Analysis Dashboard con MAE/MFE
- ✅ Rimosso Optuna per labeling params
- ✅ Parametri stabili per default

### v1.0 (Legacy - Percentuali Fisse)
- Trailing stop con percentuali fisse (es. 1.5%)
- Non adattivo alla volatilità
- Problemi con coin diverse (BTC vs DOGE)
