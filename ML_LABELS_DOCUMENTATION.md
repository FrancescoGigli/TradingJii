# 🎯 ML Training Labels - Documentazione Completa

Questo documento descrive il sistema di generazione e salvataggio delle **etichette di training** (labels) per il machine learning nel progetto Trae.

---

## 📋 Indice

1. [Schema Database](#-schema-database)
2. [Flusso Completo](#-flusso-completo)
3. [Regole di Labeling (Trailing Stop)](#-regole-di-labeling-trailing-stop)
4. [Formula Score](#-formula-score)
5. [Parametri Default](#-parametri-default)
6. [Significato dei Campi](#-significato-dei-campi)
7. [Avvertenze Importanti](#️-avvertenze-importanti)
8. [Query SQL di Esempio](#-query-sql-di-esempio)
9. [Uso per ML Training](#-uso-per-ml-training)

---

## 🗄️ Schema Database

### Tabella: `ml_training_labels`

```sql
CREATE TABLE IF NOT EXISTS ml_training_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    
    -- OHLCV base data
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    
    -- LONG labels
    score_long REAL,
    realized_return_long REAL,
    mfe_long REAL,
    mae_long REAL,
    bars_held_long INTEGER,
    exit_type_long TEXT,
    
    -- SHORT labels
    score_short REAL,
    realized_return_short REAL,
    mfe_short REAL,
    mae_short REAL,
    bars_held_short INTEGER,
    exit_type_short TEXT,
    
    -- Config used
    trailing_stop_pct REAL,
    max_bars INTEGER,
    time_penalty_lambda REAL,
    trading_cost REAL,
    
    -- Metadata
    generated_at TEXT,
    
    UNIQUE(symbol, timeframe, timestamp)
);

-- Indici per query veloci
CREATE INDEX IF NOT EXISTS idx_ml_labels_symbol_tf ON ml_training_labels(symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_ml_labels_timestamp ON ml_training_labels(timestamp);
```

### Tabella Completa dei Campi

| Colonna | Tipo | Descrizione |
|---------|------|-------------|
| `id` | INTEGER | Chiave primaria auto-incrementante |
| `symbol` | TEXT | Coppia trading (es. "BTC/USDT:USDT") |
| `timeframe` | TEXT | Timeframe ("15m" o "1h") |
| `timestamp` | TEXT | Data/ora candela entry (ISO format) |
| `open` | REAL | Prezzo apertura candela |
| `high` | REAL | Prezzo massimo candela |
| `low` | REAL | Prezzo minimo candela |
| `close` | REAL | Prezzo chiusura candela |
| `volume` | REAL | Volume scambiato |
| `score_long` | REAL | 🎯 **Score LONG** - target principale ML |
| `realized_return_long` | REAL | Return % effettivo trade LONG |
| `mfe_long` | REAL | Max Favorable Excursion LONG |
| `mae_long` | REAL | Max Adverse Excursion LONG |
| `bars_held_long` | INTEGER | Numero barre tenute LONG |
| `exit_type_long` | TEXT | Tipo exit: "trailing" o "time" |
| `score_short` | REAL | 🎯 **Score SHORT** - target principale ML |
| `realized_return_short` | REAL | Return % effettivo trade SHORT |
| `mfe_short` | REAL | Max Favorable Excursion SHORT |
| `mae_short` | REAL | Max Adverse Excursion SHORT |
| `bars_held_short` | INTEGER | Numero barre tenute SHORT |
| `exit_type_short` | TEXT | Tipo exit: "trailing" o "time" |
| `trailing_stop_pct` | REAL | Config: trailing stop % usato |
| `max_bars` | INTEGER | Config: max barre prima di time exit |
| `time_penalty_lambda` | REAL | Config: coefficiente λ penalità tempo |
| `trading_cost` | REAL | Config: costo trading totale |
| `generated_at` | TEXT | Timestamp generazione labels |

---

## 🔄 Flusso Completo

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ML LABELS PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────┐                              │
│  │  [1] HISTORICAL OHLCV DATABASE       │                              │
│  │  Tabella: historical_ohlcv           │                              │
│  │  - timestamp, open, high, low, close │                              │
│  │  - volume, symbol, timeframe         │                              │
│  └──────────────────┬───────────────────┘                              │
│                     │                                                   │
│                     ▼                                                   │
│  ┌──────────────────────────────────────┐                              │
│  │  [2] ML LABELS TAB (Streamlit UI)    │                              │
│  │  File: components/tabs/ml_labels.py  │                              │
│  │                                      │                              │
│  │  Configurazione:                     │                              │
│  │  • Symbol (es. BTC/USDT:USDT)       │                              │
│  │  • Timeframe (15m / 1h)             │                              │
│  │  • Trailing Stop %                   │                              │
│  │  • Max Bars                          │                              │
│  │  • Lambda (λ)                        │                              │
│  │  • Trading Cost %                    │                              │
│  └──────────────────┬───────────────────┘                              │
│                     │                                                   │
│                     │ [🚀 Generate Labels]                              │
│                     ▼                                                   │
│  ┌──────────────────────────────────────┐                              │
│  │  [3] TRAILING STOP LABELER           │                              │
│  │  File: ai/core/labels.py             │                              │
│  │                                      │                              │
│  │  Per OGNI candela:                   │                              │
│  │  ├─ Simula trade LONG con trailing   │                              │
│  │  ├─ Simula trade SHORT con trailing  │                              │
│  │  ├─ Calcola return realizzato (R)    │                              │
│  │  ├─ Applica penalità tempo           │                              │
│  │  └─ Score = R - λ·log(1+D) - costs   │                              │
│  └──────────────────┬───────────────────┘                              │
│                     │                                                   │
│                     ▼                                                   │
│  ┌──────────────────────────────────────┐                              │
│  │  [4] LABELS DATAFRAME (in memoria)   │                              │
│  │                                      │                              │
│  │  Colonne per ogni timeframe:         │                              │
│  │  • score_long, score_short           │                              │
│  │  • realized_return_long/short        │                              │
│  │  • mfe_long/short, mae_long/short    │                              │
│  │  • bars_held_long/short              │                              │
│  │  • exit_type_long/short              │                              │
│  └──────────────────┬───────────────────┘                              │
│                     │                                                   │
│                     │ [🗄️ SAVE TO DATABASE]                            │
│                     ▼                                                   │
│  ┌──────────────────────────────────────┐                              │
│  │  [5] ML_TRAINING_LABELS TABLE        │                              │
│  │  File: database.py                   │                              │
│  │                                      │                              │
│  │  1. DELETE existing labels for       │                              │
│  │     symbol/timeframe                 │                              │
│  │  2. INSERT new labels row by row     │                              │
│  │  3. Skip rows with exit_type         │                              │
│  │     = 'invalid'                      │                              │
│  └──────────────────────────────────────┘                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📐 Regole di Labeling (Trailing Stop)

### Concetto Base

Per **ogni candela** nel dataset, simuliamo due trade ipotetici:
- Un trade **LONG** (compra all'entry, vende dopo)
- Un trade **SHORT** (vende allo scoperto all'entry, riacquista dopo)

Entrambi i trade usano un **trailing stop** che:
1. Parte dal prezzo di entry
2. "Insegue" il prezzo nella direzione favorevole
3. Si attiva quando il prezzo ritraccia di una certa percentuale

### 📈 LONG Trade Simulation

```python
# Pseudocodice dettagliato

entry_price = close[i]  # Entry alla chiusura della candela corrente
highest_seen = entry_price  # Il massimo visto inizia da entry

for bar in range(1, max_bars + 1):
    # Aggiorna il massimo visto
    if high[i + bar] > highest_seen:
        highest_seen = high[i + bar]
    
    # Calcola livello trailing stop
    trailing_level = highest_seen * (1 - trailing_stop_pct)
    
    # Check se il trailing stop è stato colpito
    if low[i + bar] <= trailing_level:
        exit_price = trailing_level
        exit_type = "trailing"
        bars_held = bar
        break
else:
    # Uscita per tempo massimo raggiunto
    exit_price = close[i + max_bars]
    exit_type = "time"
    bars_held = max_bars

# Calcolo return
realized_return = (exit_price - entry_price) / entry_price
```

**Esempio LONG:**
```
Entry: $100.00
Candela 1: High=$102, Low=$99 → highest=$102, trailing=$100.47 → NO exit
Candela 2: High=$105, Low=$101 → highest=$105, trailing=$103.43 → NO exit
Candela 3: High=$104, Low=$103 → highest=$105, trailing=$103.43 → LOW≤trailing? 103≤103.43 → EXIT!

Exit price: $103.43 (trailing level)
Return: (103.43 - 100) / 100 = +3.43%
Bars held: 3
Exit type: "trailing"
```

### 📉 SHORT Trade Simulation

```python
# Pseudocodice dettagliato

entry_price = close[i]  # Entry alla chiusura della candela corrente
lowest_seen = entry_price  # Il minimo visto inizia da entry

for bar in range(1, max_bars + 1):
    # Aggiorna il minimo visto
    if low[i + bar] < lowest_seen:
        lowest_seen = low[i + bar]
    
    # Calcola livello trailing stop (per SHORT è sopra il minimo)
    trailing_level = lowest_seen * (1 + trailing_stop_pct)
    
    # Check se il trailing stop è stato colpito
    if high[i + bar] >= trailing_level:
        exit_price = trailing_level
        exit_type = "trailing"
        bars_held = bar
        break
else:
    # Uscita per tempo massimo raggiunto
    exit_price = close[i + max_bars]
    exit_type = "time"
    bars_held = max_bars

# Calcolo return (per SHORT il profitto è invertito)
realized_return = (entry_price - exit_price) / entry_price
```

**Esempio SHORT:**
```
Entry: $100.00
Candela 1: Low=$98, High=$101 → lowest=$98, trailing=$99.47 → NO exit
Candela 2: Low=$95, High=$99 → lowest=$95, trailing=$96.43 → NO exit
Candela 3: Low=$94, High=$97 → lowest=$94, trailing=$95.41 → HIGH≥trailing? 97≥95.41 → EXIT!

Exit price: $95.41 (trailing level)
Return: (100 - 95.41) / 100 = +4.59%
Bars held: 3
Exit type: "trailing"
```

---

## 🧮 Formula Score

### Formula Completa

```
score = R - λ·log(1+D) - costs
```

### Componenti

| Simbolo | Nome | Descrizione | Range |
|---------|------|-------------|-------|
| **R** | Realized Return | `(exit_price - entry_price) / entry_price` | (-∞, +∞) |
| **D** | Duration | Numero di barre tenute (`bars_held`) | [1, max_bars] |
| **λ** | Time Penalty Lambda | Coefficiente penalità tempo | Default: 0.001 |
| **costs** | Trading Costs | Costi totali (entry + exit fees) | Default: 0.001 (0.1%) |

### Spiegazione Intuitiva

1. **R (Return)**: Il guadagno/perdita effettivo del trade
   - Positivo = profitto
   - Negativo = perdita

2. **λ·log(1+D) (Time Penalty)**: Penalizza trade che durano troppo
   - Più tieni aperto, più penalità
   - Usa log() quindi la penalità cresce lentamente
   - Incoraggia trade rapidi

3. **costs (Trading Costs)**: Rappresenta le commissioni reali
   - Sottrae un costo fisso per ogni trade
   - Incentiva solo trade con rendimento sufficiente

### Esempio Calcolo

```
Trade LONG:
- Entry: $100, Exit: $103, Bars: 5

R = (103 - 100) / 100 = 0.03 (+3%)
λ·log(1+D) = 0.001 × log(1+5) = 0.001 × 1.79 = 0.00179
costs = 0.001

score = 0.03 - 0.00179 - 0.001
score = 0.02721 (+2.721%)
```

---

## ⚙️ Parametri Default

### Per Timeframe

| Parametro | 15 minuti | 1 ora | Descrizione |
|-----------|-----------|-------|-------------|
| `trailing_stop_pct` | **1.5%** | **2.5%** | % di ritracciamento per trailing |
| `max_bars` | **48** (12h) | **24** (24h) | Barre massime prima di time exit |

### Globali

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `time_penalty_lambda` | **0.001** | Coefficiente penalità tempo |
| `trading_cost` | **0.001** (0.1%) | Costi trading totali |

### Perché 15m ha Trailing più Stretto?

- **15m**: Movimenti più frequenti, serve trailing stretto per catturare profitti
- **1h**: Movimenti più ampi, serve trailing largo per evitare falsi segnali

---

## 📖 Significato dei Campi

### Score (Target ML Principale)

| Campo | Descrizione |
|-------|-------------|
| `score_long` | Score finale per entry LONG. **Questo è il target principale per ML.** |
| `score_short` | Score finale per entry SHORT. **Questo è il target principale per ML.** |

**Interpretazione Score:**
- `score > 0.01`: Buona opportunità di trade
- `score ≈ 0`: Trade neutro (costi ≈ profitti)
- `score < 0`: Trade in perdita

### Return Realizzato

| Campo | Descrizione |
|-------|-------------|
| `realized_return_long` | % di rendimento effettivo del trade LONG |
| `realized_return_short` | % di rendimento effettivo del trade SHORT |

**Nota:** Questo è il return PRIMA di sottrarre penalità e costi.

### MFE (Max Favorable Excursion)

| Campo | Descrizione |
|-------|-------------|
| `mfe_long` | Massimo profitto % raggiunto durante il trade LONG |
| `mfe_short` | Massimo profitto % raggiunto durante il trade SHORT |

**Uso:** Indica quanto il trade è andato "in verde" prima dell'uscita.

### MAE (Max Adverse Excursion)

| Campo | Descrizione |
|-------|-------------|
| `mae_long` | Massima perdita % subita durante il trade LONG |
| `mae_short` | Massima perdita % subita durante il trade SHORT |

**Uso:** Indica quanto il trade è andato "in rosso" prima dell'uscita.

### Bars Held

| Campo | Descrizione |
|-------|-------------|
| `bars_held_long` | Numero di candele dal entry all'exit per LONG |
| `bars_held_short` | Numero di candele dal entry all'exit per SHORT |

### Exit Type

| Campo | Valori | Descrizione |
|-------|--------|-------------|
| `exit_type_long` | "trailing" / "time" | Come è terminato il trade LONG |
| `exit_type_short` | "trailing" / "time" | Come è terminato il trade SHORT |

**Interpretazione:**
- `"trailing"`: Il trailing stop è stato colpito (prezzo ha ritracciato)
- `"time"`: Raggiunto max_bars senza trailing (exit forzato)

---

## ⚠️ Avvertenze Importanti

### 🚨 LOOKAHEAD BIAS

> **LE LABELS USANO DATI FUTURI!**

Le labels sono calcolate guardando le candele SUCCESSIVE all'entry. Questo significa:

❌ **NON** usare `score_long` o `score_short` come **input** del modello
✅ Usali **SOLO** come **target** (y) per il training

### Schema Corretto

```python
# ✅ CORRETTO
X = df[['rsi', 'macd', 'volume', ...]]  # Features (solo dati passati)
y = df['score_long']                     # Target (label futura)

model.fit(X, y)

# ❌ SBAGLIATO
X = df[['rsi', 'macd', 'score_long', ...]]  # MAI includere labels nelle features!
```

### 📊 Score NON Normalizzato

Lo score **NON** è normalizzato in range [-1, 1]. I valori tipici sono:

| Range Score | Interpretazione |
|-------------|-----------------|
| > +0.02 | Ottimo trade |
| +0.01 a +0.02 | Buon trade |
| 0 a +0.01 | Trade marginale |
| -0.01 a 0 | Leggera perdita |
| < -0.01 | Perdita significativa |

### 🔄 Sovrascrittura Dati

Ogni volta che salvi labels per un symbol/timeframe, i dati esistenti vengono **CANCELLATI** e sostituiti:

```sql
-- Prima del salvataggio:
DELETE FROM ml_training_labels WHERE symbol = ? AND timeframe = ?
```

---

## 🔍 Query SQL di Esempio

### Vedere tutte le labels di un symbol

```sql
SELECT timestamp, close, score_long, score_short, exit_type_long
FROM ml_training_labels
WHERE symbol = 'BTC/USDT:USDT' AND timeframe = '15m'
ORDER BY timestamp DESC
LIMIT 100;
```

### Statistiche aggregate per symbol

```sql
SELECT 
    symbol,
    timeframe,
    COUNT(*) as total_labels,
    AVG(score_long) as avg_score_long,
    AVG(score_short) as avg_score_short,
    SUM(CASE WHEN score_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pct_positive_long
FROM ml_training_labels
GROUP BY symbol, timeframe
ORDER BY avg_score_long DESC;
```

### Trade con score più alto

```sql
SELECT timestamp, symbol, score_long, realized_return_long, bars_held_long, exit_type_long
FROM ml_training_labels
WHERE timeframe = '15m'
ORDER BY score_long DESC
LIMIT 20;
```

### Distribuzione exit type

```sql
SELECT 
    exit_type_long,
    COUNT(*) as count,
    AVG(realized_return_long) as avg_return
FROM ml_training_labels
WHERE symbol = 'BTC/USDT:USDT'
GROUP BY exit_type_long;
```

### Labels con MFE alto ma score basso (analisi)

```sql
SELECT timestamp, mfe_long, mae_long, realized_return_long, score_long, bars_held_long
FROM ml_training_labels
WHERE symbol = 'BTC/USDT:USDT'
  AND mfe_long > 0.02      -- MFE > 2%
  AND score_long < 0.005   -- Ma score basso
ORDER BY mfe_long DESC
LIMIT 20;
```

---

## 🤖 Uso per ML Training

### Caricare i Dati in Python

```python
import sqlite3
import pandas as pd

# Connessione al database
conn = sqlite3.connect('path/to/crypto_data.db')

# Query labels
query = '''
    SELECT *
    FROM ml_training_labels
    WHERE symbol = 'BTC/USDT:USDT'
    AND timeframe = '15m'
    ORDER BY timestamp
'''

labels_df = pd.read_sql_query(query, conn)
labels_df['timestamp'] = pd.to_datetime(labels_df['timestamp'])
labels_df.set_index('timestamp', inplace=True)

conn.close()
```

### Preparazione Dataset per Training

```python
# Carica features (dalla tabella historical_ohlcv con indicatori)
features_df = load_historical_features(symbol, timeframe)

# Carica labels
labels_df = load_ml_labels(symbol, timeframe)

# Merge su timestamp
dataset = features_df.join(labels_df[['score_long', 'score_short']], how='inner')

# Definisci X e y
feature_columns = ['rsi', 'macd', 'volume_sma_ratio', ...]  # Solo features passate!
X = dataset[feature_columns]
y = dataset['score_long']  # Target

# Train/test split (temporale!)
split_idx = int(len(dataset) * 0.8)
X_train, X_test = X[:split_idx], X[split_idx:]
y_train, y_test = y[:split_idx], y[split_idx:]
```

### Best Practices

1. **Split Temporale**: Sempre usare split temporale (no shuffle) per evitare lookahead
2. **Filtra Invalid**: Escludere righe con `exit_type = 'invalid'`
3. **Normalizza Features**: Standardizza le features, non i target
4. **Cross-Validation Walk-Forward**: Usa walk-forward per validazione

---

## 📁 File Correlati

| File | Descrizione |
|------|-------------|
| `agents/frontend/components/tabs/ml_labels.py` | UI Streamlit per generazione labels |
| `agents/frontend/ai/core/labels.py` | Classe TrailingStopLabeler |
| `agents/frontend/database.py` | Funzioni salvataggio DB |
| `agents/historical-data/core/database.py` | Gestione dati storici |

---

## 📚 Changelog

- **2026-01-11**: Documentazione iniziale
- Sistema attuale: Trailing Stop Labeling con penalità tempo

---

*Documentazione generata automaticamente. Per domande, consulta il codice sorgente.*
