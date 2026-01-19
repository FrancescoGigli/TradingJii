# 📁 Database Schema - crypto_data.db

Documentazione completa della struttura del database SQLite utilizzato dal sistema di trading crypto.

---

## 🗄️ Informazioni Generali

| Proprietà | Valore |
|-----------|--------|
| **Tipo** | SQLite |
| **Nome file** | `crypto_data.db` |
| **Percorso** | `shared/crypto_data.db` |
| **N° Tabelle principali** | 2 (training_data, training_labels) |

---

## 📊 Panoramica Tabelle

| Tabella | Script/Agente | Scopo |
|---------|---------------|-------|
| `training_data` | `run_full_training_pipeline.py` | OHLCV + 16 indicatori tecnici |
| `training_labels` | `run_full_training_pipeline.py` | Labels per training ML (score, MFE, MAE) |

---

## 📋 Schema Dettagliato delle Tabelle

---

### 1️⃣ `training_data` ⭐ DATI ML

**Descrizione:** Dati storici OHLCV con 16 indicatori tecnici calcolati.

**Creato da:** `run_full_training_pipeline.py`

**Schema SQL:**
```sql
CREATE TABLE IF NOT EXISTS training_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    sma_20 REAL, sma_50 REAL, ema_12 REAL, ema_26 REAL,
    bb_upper REAL, bb_middle REAL, bb_lower REAL,
    rsi REAL, macd REAL, macd_signal REAL, macd_hist REAL,
    atr REAL, adx REAL, cci REAL, willr REAL, obv REAL,
    UNIQUE(symbol, timeframe, timestamp)
);
```

**Colonne OHLCV:**

| Colonna | Tipo | Descrizione |
|---------|------|-------------|
| `id` | INTEGER | Auto-increment (PK) |
| `timestamp` | TEXT | Data/ora della candela |
| `symbol` | TEXT | Trading pair (es. `BTC/USDT:USDT`) |
| `timeframe` | TEXT | `15m` o `1h` |
| `open` | REAL | Prezzo di apertura |
| `high` | REAL | Prezzo massimo |
| `low` | REAL | Prezzo minimo |
| `close` | REAL | Prezzo di chiusura |
| `volume` | REAL | Volume scambiato |

**Indicatori Tecnici (16 totali):**

| Categoria | Colonna | Descrizione |
|-----------|---------|-------------|
| **Trend** | `sma_20` | Simple Moving Average 20 periodi |
| **Trend** | `sma_50` | Simple Moving Average 50 periodi |
| **Trend** | `ema_12` | Exponential Moving Average 12 periodi |
| **Trend** | `ema_26` | Exponential Moving Average 26 periodi |
| **Volatilità** | `bb_upper` | Bollinger Band superiore (2 std) |
| **Volatilità** | `bb_middle` | Bollinger Band centrale (SMA 20) |
| **Volatilità** | `bb_lower` | Bollinger Band inferiore (2 std) |
| **Momentum** | `rsi` | RSI 14 periodi (0-100) |
| **Trend** | `macd` | MACD Line (EMA12 - EMA26) |
| **Trend** | `macd_signal` | MACD Signal Line (EMA9 del MACD) |
| **Trend** | `macd_hist` | MACD Histogram (MACD - Signal) |
| **Volatilità** | `atr` | Average True Range 14 periodi |
| **Trend** | `adx` | Average Directional Index 14 periodi |
| **Momentum** | `cci` | Commodity Channel Index 20 periodi |
| **Momentum** | `willr` | Williams %R 14 periodi |
| **Volume** | `obv` | On Balance Volume (cumulativo) |

**Indici:**
```sql
CREATE INDEX idx_td_sym_tf ON training_data(symbol, timeframe);
```

---

### 2️⃣ `training_labels` ⭐ LABELS ML

**Descrizione:** Labels generati con simulazione trailing stop per training modelli ML.

**Creato da:** `run_full_training_pipeline.py`

**Schema SQL:**
```sql
CREATE TABLE IF NOT EXISTS training_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    score_long REAL, score_short REAL,
    realized_return_long REAL, realized_return_short REAL,
    mfe_long REAL, mfe_short REAL,
    mae_long REAL, mae_short REAL,
    bars_held_long INTEGER, bars_held_short INTEGER,
    exit_type_long TEXT, exit_type_short TEXT,
    UNIQUE(symbol, timeframe, timestamp)
);
```

**Colonne Labels LONG:**

| Colonna | Tipo | Descrizione |
|---------|------|-------------|
| `score_long` | REAL | Score calcolato: `return - λ*log(1+bars) - cost` |
| `realized_return_long` | REAL | Ritorno realizzato (exit_price - entry) / entry |
| `mfe_long` | REAL | Maximum Favorable Excursion (max profitto potenziale) |
| `mae_long` | REAL | Maximum Adverse Excursion (max perdita potenziale) |
| `bars_held_long` | INTEGER | Numero di barre prima dell'exit |
| `exit_type_long` | TEXT | `trailing` o `time` |

**Colonne Labels SHORT:** (stesse con suffisso `_short`)

**Indici:**
```sql
CREATE INDEX idx_tl_sym_tf ON training_labels(symbol, timeframe);
```

---

## 📊 Parametri Generazione Labels

I labels sono generati con questi parametri (in `run_full_training_pipeline.py`):

| Parametro | 15m | 1h |
|-----------|-----|-----|
| `trailing_pct` | 1.5% | 2.5% |
| `max_bars` | 48 | 24 |
| `time_penalty` (λ) | 0.001 | 0.001 |
| `trading_cost` | 0.001 | 0.001 |

**Formula Score:**
```
score = realized_return - 0.001 * log(1 + bars_held) - 0.001
```

---

## 🔄 Flusso Dati

```
┌─────────────────────────────────────────────────────────────────┐
│                         BYBIT API                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   run_full_training_pipeline  │
              │                               │
              │  STEP 1: Fetch OHLCV          │
              │  STEP 2: Calculate Indicators │
              │  STEP 3: Generate Labels      │
              │  STEP 4: Train XGBoost        │
              └───────────────────────────────┘
                    │                 │
                    ▼                 ▼
           ┌──────────────┐   ┌─────────────────┐
           │ training_data│   │ training_labels │
           │  (OHLCV +    │   │  (score, MFE,   │
           │   16 ind.)   │   │   MAE, etc.)    │
           └──────────────┘   └─────────────────┘
                    │                 │
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │   XGBoost JOIN  │
                    │                 │
                    │ training_data   │
                    │     INNER JOIN  │
                    │ training_labels │
                    └─────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  shared/models/ │
                    │                 │
                    │ model_long.pkl  │
                    │ model_short.pkl │
                    │ scaler.pkl      │
                    │ metadata.json   │
                    └─────────────────┘
```

---

## 📈 Query per ML Training

**Dataset completo con features + labels:**
```sql
SELECT 
    td.timestamp, td.symbol, td.timeframe,
    td.open, td.high, td.low, td.close, td.volume,
    td.sma_20, td.sma_50, td.ema_12, td.ema_26,
    td.bb_upper, td.bb_middle, td.bb_lower,
    td.rsi, td.macd, td.macd_signal, td.macd_hist,
    td.atr, td.adx, td.cci, td.willr, td.obv,
    tl.score_long, tl.score_short
FROM training_data td
INNER JOIN training_labels tl ON 
    td.symbol = tl.symbol AND 
    td.timeframe = tl.timeframe AND 
    td.timestamp = tl.timestamp
WHERE td.timeframe = '15m'
ORDER BY td.symbol, td.timestamp;
```

**Features usate per training (21 totali):**
```python
feature_cols = [
    'open', 'high', 'low', 'close', 'volume',      # 5 OHLCV
    'sma_20', 'sma_50', 'ema_12', 'ema_26',         # 4 MA
    'bb_upper', 'bb_middle', 'bb_lower',           # 3 BB
    'rsi', 'macd', 'macd_signal', 'macd_hist',     # 4 Momentum
    'atr', 'adx', 'cci', 'willr', 'obv'            # 5 Altro
]
```

---

## 🕐 Comandi Utili

**Verificare dati:**
```bash
python inspect_database.py
```

**Popolare database:**
```bash
python run_full_training_pipeline.py --symbols 30 --timeframe 15m --days 180
```

**Statistiche quick:**
```sql
-- Conteggio per timeframe
SELECT timeframe, COUNT(*) as rows, COUNT(DISTINCT symbol) as symbols 
FROM training_data GROUP BY timeframe;

-- Controllo NULL
SELECT COUNT(*) as total, 
       SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as null_close
FROM training_data;
```

---

## 📝 Note Importanti

- **Timeframe nella stessa tabella**: I dati 15m e 1h sono nella stessa tabella, distinti dalla colonna `timeframe`
- **Labels separati**: `training_labels` contiene SOLO labels, non indicatori
- **JOIN necessario**: Per il training ML serve fare JOIN tra le due tabelle
- **Warmup scartato**: Gli indicatori con NaN vengono droppati in fase di calcolo

---

*Ultima modifica: Gennaio 2026*
