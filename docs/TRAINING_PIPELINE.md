# 🎓 ML Training Pipeline - Documentazione Completa

Questo documento descrive in dettaglio tutte le fasi del processo di training del modello XGBoost per la predizione dei segnali di trading.

---

## 📊 Architettura Database

### Database Unico
Il sistema utilizza **un solo database SQLite**: `shared/crypto_data.db`

I dati 15m e 1h sono distinti dalla colonna `timeframe`:

```sql
-- Esempio query
SELECT * FROM training_data WHERE timeframe = '15m'
SELECT * FROM training_labels WHERE timeframe = '1h'
```

### Tabelle Principali

| Tabella | Descrizione | Colonne Chiave |
|---------|-------------|----------------|
| `training_data` | OHLCV + 16 indicatori | symbol, timeframe, timestamp, close, rsi, macd, etc. |
| `training_labels` | Labels generati | score_long, score_short, mfe, mae, exit_type |

---

## 🚀 Fasi del Pipeline

### Fase 1: Data Collection (OHLCV + Indicatori)

**Scopo:** Scaricare dati storici e calcolare indicatori tecnici.

**Input:**
- Lista symbols (es. top 30 per volume)
- Timeframe (15m o 1h)
- Periodo (es. 180 giorni)

**Processo:**
1. Connessione a Bybit API via `ccxt`
2. Download candele OHLCV (Open, High, Low, Close, Volume)
3. Calcolo 16 indicatori tecnici:

| Categoria | Indicatori |
|-----------|------------|
| **Trend** | SMA(20), SMA(50), EMA(12), EMA(26), ADX |
| **Momentum** | RSI(14), MACD, MACD Signal, Williams %R, CCI |
| **Volatilità** | Bollinger Bands (upper, middle, lower), ATR |
| **Volume** | OBV |

**Output:** Tabella `training_data` con 21 colonne:
```
id, timestamp, symbol, timeframe, 
open, high, low, close, volume,
sma_20, sma_50, ema_12, ema_26,
bb_upper, bb_middle, bb_lower,
rsi, macd, macd_signal, macd_hist,
atr, adx, cci, willr, obv
```

**Validazione Step 1:**
- ✅ Almeno 10,000 righe totali
- ✅ Nessun NULL nelle colonne critiche (close, volume)
- ✅ Range date corretto

---

### Fase 2: Label Generation (Trailing Stop Simulation)

**Scopo:** Generare target per il modello ML simulando un trailing stop.

**Input:**
- Dati da `training_data`
- Parametri trailing: `trailing_pct` (1.5% per 15m, 2.5% per 1h)
- Max barre lookforward: `max_bars` (48 per 15m, 24 per 1h)

**Algoritmo Trailing Stop:**

```
Per ogni candela i:
  entry_price = close[i]
  
  LONG:
    best_price = entry_price
    trailing_stop = entry_price * (1 - trailing_pct)
    
    Per ogni candela futura j in [i+1, i+max_bars]:
      Se high[j] > best_price:
        best_price = high[j]
        trailing_stop = best_price * (1 - trailing_pct)
      
      Se low[j] <= trailing_stop:
        exit_price = trailing_stop
        exit_type = 'trailing'
        bars_held = j - i
        BREAK
    Altrimenti:
      exit_price = close[i + max_bars]
      exit_type = 'time'
      bars_held = max_bars
```

**Formula Score:**
```
score = realized_return - λ * log(1 + bars_held) - costs

Dove:
  realized_return = (exit_price - entry_price) / entry_price
  λ = 0.001 (time penalty)
  costs = 0.001 (trading costs ~0.1%)
```

**Metriche Aggiuntive:**
- **MFE** (Maximum Favorable Excursion): Massimo profitto potenziale
- **MAE** (Maximum Adverse Excursion): Massima perdita potenziale

**Output:** Tabella `training_labels` con 20 colonne:
```
id, timestamp, symbol, timeframe,
open, high, low, close, volume,
score_long, score_short,
realized_return_long, realized_return_short,
mfe_long, mfe_short, mae_long, mae_short,
bars_held_long, bars_held_short,
exit_type_long, exit_type_short
```

**Validazione Step 2:**
- ✅ Almeno 10,000 labels
- ✅ Trailing exits > 30% (indica che il trailing sta catturando i movimenti)
- ✅ Score medio vicino a 0 (bilanciato)

---

### Fase 3: Model Training (XGBoost)

**Scopo:** Addestrare un modello per predire score_long e score_short.

**Input:**
- JOIN tra `training_data` e `training_labels`
- 21 features (OHLCV + 16 indicatori)
- 2 target: score_long, score_short

**Processo:**

1. **Data Preparation:**
   ```sql
   SELECT td.*, tl.score_long, tl.score_short
   FROM training_data td
   INNER JOIN training_labels tl ON 
     td.symbol = tl.symbol AND 
     td.timeframe = tl.timeframe AND 
     td.timestamp = tl.timestamp
   WHERE td.timeframe = '15m'
   ```

2. **Feature Scaling:**
   - StandardScaler (mean=0, std=1)

3. **Train/Test Split:**
   - 80% train, 20% test
   - Split temporale (no shuffle per time series)

4. **XGBoost Training:**
   ```python
   params = {
       'n_estimators': 500,
       'max_depth': 6,
       'learning_rate': 0.05,
       'min_child_weight': 10,
       'subsample': 0.8,
       'colsample_bytree': 0.8,
       'objective': 'reg:squarederror'
   }
   ```

5. **Metriche di Valutazione:**

| Metrica | Descrizione | Target |
|---------|-------------|--------|
| R² | Varianza spiegata | > 0.05 |
| Spearman Correlation | Correlazione dei ranking | > 0.10 |
| Precision@K | Accuracy sui top K segnali | > 60% |

**Output:**
- `shared/models/model_long_latest.pkl`
- `shared/models/model_short_latest.pkl`
- `shared/models/scaler_latest.pkl`
- `shared/models/metadata_latest.json`

**Validazione Step 3:**
- ✅ Modello salvato correttamente
- ✅ R² > 0 (meglio di random)
- ✅ Spearman > 0.05 (ranking significativo)

---

## 🛠️ Strumenti Disponibili

### 1. Script Automatico
```bash
# Training completo (consigliato per iniziare)
python run_full_training_pipeline.py --symbols 30 --days 180 --timeframe 15m

# Opzioni disponibili
--symbols N     # Numero di symbols (default: 10)
--timeframe X   # 15m o 1h (default: 15m)
--days N        # Giorni di dati (default: 365)
```

### 2. Inspector CLI
```bash
# Report completo
python inspect_database.py

# Report dettagliato
python inspect_database.py --detailed

# Filtra per symbol
python inspect_database.py --symbol BTC

# Solo quality check
python inspect_database.py --quality
```

### 3. Frontend Dashboard
```
http://localhost:8501 → Tab "🎓 Train"

Sub-tabs:
  📊 1. Data      - Download OHLCV
  🏷️ 2. Labeling - Genera labels
  🚀 3. Training  - Addestra modello
  📈 4. Models    - Visualizza modelli
  🗄️ 5. Explorer  - Esplora dati
```

---

## 📋 Checklist di Validazione

### Prima del Training
- [ ] Docker running (`docker-compose up -d`)
- [ ] API Bybit accessibile
- [ ] Spazio disco sufficiente

### Dopo Step 1 (Data)
- [ ] training_data ha ≥10,000 righe
- [ ] Nessun NULL in close, volume
- [ ] Date range corretto

### Dopo Step 2 (Labels)
- [ ] training_labels ha ≥10,000 righe
- [ ] Score medio ≈ 0
- [ ] Trailing exits ≥ 30%

### Dopo Step 3 (Model)
- [ ] File .pkl creati
- [ ] R² > 0
- [ ] Spearman > 0.05

---

## 🔧 Troubleshooting

### "No data in database"
```bash
# Verifica database
python inspect_database.py

# Se vuoto, esegui pipeline
python run_full_training_pipeline.py --symbols 10 --days 30
```

### "Model not found"
```bash
# Controlla directory models
ls shared/models/

# Se vuota, riesegui training
python run_full_training_pipeline.py
```

### "API Error"
- Verifica connessione internet
- Bybit potrebbe avere rate limits
- Riprova dopo qualche minuto

---

## 📊 Diagramma Flusso

```
┌─────────────────────────────────────────────────────────────┐
│                    BYBIT API                                 │
│                       │                                      │
│                       ▼                                      │
│  ┌─────────────────────────────────────┐                    │
│  │   STEP 1: DATA COLLECTION           │                    │
│  │   - Download OHLCV (15m o 1h)       │                    │
│  │   - Calculate 16 indicators          │                    │
│  │   - Save to training_data           │                    │
│  └─────────────────────────────────────┘                    │
│                       │                                      │
│                       ▼                                      │
│  ┌─────────────────────────────────────┐                    │
│  │   STEP 2: LABEL GENERATION          │                    │
│  │   - Simulate trailing stop          │                    │
│  │   - Calculate score_long/short      │                    │
│  │   - Calculate MFE, MAE              │                    │
│  │   - Save to training_labels         │                    │
│  └─────────────────────────────────────┘                    │
│                       │                                      │
│                       ▼                                      │
│  ┌─────────────────────────────────────┐                    │
│  │   STEP 3: MODEL TRAINING            │                    │
│  │   - JOIN data + labels              │                    │
│  │   - Train XGBoost LONG              │                    │
│  │   - Train XGBoost SHORT             │                    │
│  │   - Evaluate (R², Spearman)         │                    │
│  │   - Save models + metadata          │                    │
│  └─────────────────────────────────────┘                    │
│                       │                                      │
│                       ▼                                      │
│  ┌─────────────────────────────────────┐                    │
│  │   OUTPUT                            │                    │
│  │   - model_long_latest.pkl           │                    │
│  │   - model_short_latest.pkl          │                    │
│  │   - scaler_latest.pkl               │                    │
│  │   - metadata_latest.json            │                    │
│  └─────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📈 Uso in Produzione

Una volta trainato il modello, puoi usarlo per:

1. **Backtest** - Tab Backtest nel frontend
2. **Inference Real-time** - Container ml-inference
3. **Trading Signals** - Integrazione con Bybit API

---

*Documentazione generata il 19/01/2026*
