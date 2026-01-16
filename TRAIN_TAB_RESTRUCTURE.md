# 🎓 PIANO DI RISTRUTTURAZIONE - TAB TRAIN

> Documento di riferimento per la ristrutturazione delle tab ML Labels e XGB Models in un'unica tab "Train".

---

## 📋 INDICE
1. [Obiettivo](#obiettivo)
2. [Struttura Attuale](#struttura-attuale)
3. [Nuova Struttura](#nuova-struttura)
4. [Mappatura File](#mappatura-file)
5. [Database Schema](#database-schema)
6. [Specifiche per Step](#specifiche-per-step)
7. [Checklist Implementazione](#checklist-implementazione)

---

## 🎯 OBIETTIVO

Unificare le tab **"ML Labels"** e **"XGB Models"** in un'unica tab **"Train"** con 4 step sequenziali:

1. **Data** - Fetch e pulizia dati storici
2. **Labeling** - Generazione labels con Trailing Stop
3. **Training** - Addestramento modelli XGBoost
4. **Models** - Visualizzazione e gestione modelli

---

## 📁 STRUTTURA ATTUALE

### File da riorganizzare:

```
agents/frontend/components/tabs/
├── ml_labels.py                    # Entry point ML Labels (da rimuovere)
├── ml/
│   ├── __init__.py                 # Export funzioni
│   ├── generator.py                # Genera labels per tutte le coin
│   ├── explorer.py                 # Database explorer
│   ├── visualization.py            # Visualizzazione singola coin
│   └── export.py                   # Export dataset
│
├── xgb_models/
│   ├── __init__.py                 # Export render_xgb_models_tab
│   ├── main.py                     # Entry point XGB
│   ├── training.py                 # Training manuale + Optuna
│   ├── viewer.py                   # Visualizza modelli
│   └── utils.py                    # Utility functions

agents/frontend/services/
└── ml_training.py                  # Logica training XGBoost

agents/frontend/ai/core/
└── labels.py                       # TrailingStopLabeler
```

---

## 🆕 NUOVA STRUTTURA

```
agents/frontend/components/tabs/train/
├── __init__.py                     # Export render_train_tab
├── main.py                         # Entry point con 4 sub-tabs
├── data.py                         # Step 1: Fetch + Clean + Validate
├── labeling.py                     # Step 2: Generate labels
├── training.py                     # Step 3: XGB Training
└── models.py                       # Step 4: View Models

agents/frontend/services/
└── training_service.py             # Refactored ml_training.py (opzionale)
```

---

## 🔄 MAPPATURA FILE (Vecchio → Nuovo)

| Vecchio File | Nuovo File | Note |
|--------------|------------|------|
| `historical_data.py` | `train/data.py` | Adattare fetch + aggiungere filtri |
| `ml/generator.py` | `train/labeling.py` | Semplificare, una sola tabella |
| `ml/explorer.py` | ❌ Rimuovere | Non più necessario |
| `ml/visualization.py` | ❌ Rimuovere | Non più necessario |
| `ml/export.py` | ❌ Rimuovere | Integrato in data.py |
| `xgb_models/training.py` | `train/training.py` | Semplificare UI |
| `xgb_models/viewer.py` | `train/models.py` | Mantenere metriche |
| `xgb_models/utils.py` | `train/models.py` | Merge con models |
| `services/ml_training.py` | ✅ Mantenere | Logica backend |
| `ai/core/labels.py` | ✅ Mantenere | TrailingStopLabeler |

---

## 🗄️ DATABASE SCHEMA

### Tabelle:

| Tabella | Descrizione | Colonne Principali |
|---------|-------------|-------------------|
| `training_features` | OHLCV + indicatori puliti | timestamp, symbol, timeframe, open, high, low, close, volume, + 64 indicatori |
| `training_labels` | Features + Labels | Tutto da training_features + score_long, score_short, mfe, mae, bars_held, exit_type |

### Flusso Dati:

```
Bybit API → training_features (pulito, allineato) → training_labels (con labels) → XGB Model
```

---

## 📊 SPECIFICHE PER STEP

### 📊 STEP 1: DATA (`data.py`)

**Input**: Nessuno (fetch da API)

**Processo**:
1. Fetch OHLCV da Bybit per top 100 coin
2. Periodo fisso: `2025-01-01 00:00:00` → `2026-01-01 00:00:00`
3. Timeframes: 15m + 1h
4. Calcola 64 indicatori tecnici
5. **Warm-up Filter**: Rimuovi prime N righe con NULL (EMA200 richiede ~200 candele)
6. **Allineamento**: 15m e 1h devono iniziare allo stesso timestamp (allinea al maggiore)
7. **Validazione**: Verifica consecutività timestamp, nessun NULL
8. **Salva** in DB: `training_features`

**Output**: Tabella `training_features` con dati puliti

**UI**:
- Progress bar durante fetch
- Tabella status per coin (✅ Complete, ⚠️ Issues)
- Data Preview (prime e ultime righe dal DB)
- Metriche: righe totali, date range, conferma 0 NULL

---

### 🏷️ STEP 2: LABELING (`labeling.py`)

**Input**: Tabella `training_features`

**Processo**:
1. Carica dati da `training_features`
2. Configura parametri:
   - `trailing_stop_pct_15m`: 1.5%
   - `trailing_stop_pct_1h`: 2.5%
   - `max_bars_15m`: 48 (12 ore)
   - `max_bars_1h`: 24 (24 ore)
   - `lambda`: 0.001 (time penalty)
   - `trading_cost`: 0.1%
3. Genera labels con `TrailingStopLabeler`
4. **Lookahead Removal**: Rimuovi ultime N righe (15m comanda → 48 candele = 12 ore)
5. **Allineamento**: Entrambi i timeframe finiscono allo stesso timestamp
6. **Salva** in DB: `training_labels` (features + labels insieme)

**Output**: Tabella `training_labels` pronta per training

**UI**:
- Sliders per configurazione parametri
- Progress bar durante labeling
- Data Preview risultato
- Statistiche labels (avg score, % positive, etc.)

**Formula Score**:
```
score = R - λ*log(1+D) - costs

Dove:
- R = realized return (exit_price - entry_price) / entry_price
- λ = time_penalty_lambda (0.001)
- D = bars_held
- costs = trading_cost (0.001)
```

---

### 🚀 STEP 3: TRAINING (`training.py`)

**Input**: Tabella `training_labels`

**Processo**:
1. Carica dati da `training_labels`
2. Split temporale: 80% train / 20% test (o 70/15/15 per Optuna)
3. Features: tutte le colonne eccetto labels
4. Targets: `score_long`, `score_short`
5. **Mode Manual**: XGBoost con parametri manuali
6. **Mode Optuna**: Auto-tuning con TPE sampler
7. Train modello LONG + modello SHORT
8. Calcola metriche: R², RMSE, Spearman, Precision@K
9. **Salva** in `shared/models/`:
   - `model_long_{version}.pkl`
   - `model_short_{version}.pkl`
   - `scaler_{version}.pkl`
   - `metadata_{version}.json`

**Output**: Modelli salvati + metriche

**UI**:
- Toggle Manual/Optuna
- Sliders parametri (Manual)
- Slider n_trials (Optuna)
- Progress bar durante training
- Risultati: R², Spearman, Precision@K

---

### 📊 STEP 4: MODELS (`models.py`)

**Input**: File in `shared/models/`

**Processo**:
1. Lista modelli disponibili
2. Carica metadata selezionato
3. Mostra metriche dettagliate

**Output**: Visualizzazione modelli

**UI**:
- Dropdown selezione modello
- Training Overview (features, date, split)
- Regression Metrics (R², RMSE, MAE)
- Ranking Metrics (Spearman, p-value)
- Precision@K Analysis (tabella + grafico)
- Features List
- Model Files
- Delete button

---

## ✅ CHECKLIST IMPLEMENTAZIONE

### FASE 1: Struttura Base ✅ COMPLETATA
- [x] Creare cartella `components/tabs/train/`
- [x] Creare `train/__init__.py`
- [x] Creare `train/main.py` con 4 sub-tabs vuote

### FASE 2: Step 1 - Data
- [ ] Creare `train/data.py`
- [ ] Implementare fetch con periodo fisso
- [ ] Implementare warm-up filter
- [ ] Implementare allineamento timestamp
- [ ] Implementare validazione
- [ ] Implementare salvataggio in `training_features`
- [ ] Implementare UI (progress, tabella status, preview)

### FASE 3: Step 2 - Labeling
- [ ] Creare `train/labeling.py`
- [ ] Implementare config UI
- [ ] Implementare generazione labels
- [ ] Implementare lookahead removal
- [ ] Implementare allineamento
- [ ] Implementare salvataggio in `training_labels`
- [ ] Implementare UI (progress, preview, stats)

### FASE 4: Step 3 - Training
- [ ] Creare `train/training.py`
- [ ] Implementare mode selector (Manual/Optuna)
- [ ] Implementare Manual training
- [ ] Implementare Optuna training
- [ ] Implementare salvataggio modelli
- [ ] Implementare UI (parametri, progress, risultati)

### FASE 5: Step 4 - Models
- [ ] Creare `train/models.py`
- [ ] Implementare lista modelli
- [ ] Implementare visualizzazione metriche
- [ ] Implementare delete modello
- [ ] Implementare UI completa

### FASE 6: Integrazione ✅ COMPLETATA
- [x] Aggiornare `sidebar.py` (non necessita modifiche - gestisce solo control panel)
- [x] Aggiornare `app.py` (rimuovere vecchie tab, aggiungere 🎓 Train)
- [x] Aggiornare `components/tabs/__init__.py`

### FASE 7: Pulizia
- [ ] Rimuovere `ml_labels.py`
- [ ] Rimuovere cartella `ml/`
- [ ] Rimuovere cartella `xgb_models/`
- [ ] Aggiornare import ovunque

---

## 📝 NOTE AGGIUNTIVE

### Allineamento Timestamp

- **15m comanda**: Il taglio finale è basato su max_bars_15m (48 candele = 12 ore)
- Entrambi i timeframe devono:
  - Iniziare dallo stesso timestamp (dopo warm-up)
  - Finire allo stesso timestamp (dopo lookahead removal)

### Warm-up Filter

- EMA200 richiede ~200 candele per inizializzarsi
- Per 1h: 200 ore = ~8 giorni da rimuovere
- Per 15m: allineare all'1h (stessa data di inizio)

### Lookahead Removal

- 15m: max_bars=48 → rimuovi ultime 48 candele (12 ore)
- 1h: allinea alla stessa fine del 15m → rimuovi ultime 12 candele

---

## 🔗 FILE CORRELATI DA MANTENERE

- `ai/core/labels.py` - TrailingStopLabeler (non modificare)
- `services/ml_training.py` - Logica backend (riutilizzare)
- `database/` - Funzioni DB esistenti (estendere se necessario)

---

*Documento creato: 15-01-2026*
*Ultimo aggiornamento: 15-01-2026*
