# 📘 PIPELINE COMPLETA - PARTE 2

**Continuazione da PIPELINE_COMPLETA.md**

---

## FASE 3: Signal Processing (continuazione)

```python
# trading/signal_processor.py (continuazione)

for symbol, predictions in prediction_results.items():
    # 1. Ensemble Voting Multi-Timeframe
    scores = []
    weights = []
    
    for tf in ['15m', '30m', '1h']:
        if tf not in predictions:
            continue
        
        pred = predictions[tf]
        weight = config.TIMEFRAME_WEIGHTS[tf]  # 15m=1.0, 30m=1.2, 1h=1.5
        
        if pred['signal'] == 'BUY':
            scores.append(pred['confidence'])
            weights.append(weight)
        elif pred['signal'] == 'SELL':
            scores.append(-pred['confidence'])
            weights.append(weight)
        # NEUTRAL contribuisce 0
    
    # 2. Calcola ensemble score
    if not scores:
        continue  # Tutti neutral
    
    ensemble_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
    
    # 3. Determina segnale finale
    if ensemble_score >= 0.65:
        final_signal = 'BUY'
        final_confidence = ensemble_score
    elif ensemble_score <= -0.65:
        final_signal = 'SELL'
        final_confidence = abs(ensemble_score)
    else:
        continue  # Neutral, skip
    
    # 4. Applica filtri
    if final_confidence < config.MIN_CONFIDENCE:
        continue  # Confidence troppo bassa
    
    if symbol in config.EXCLUDED_FROM_TRADING:
        continue  # BTC/ETH esclusi
    
    # 5. Create signal object
    signal = {
        'symbol': symbol,
        'signal_name': final_signal,
        'confidence': final_confidence,
        'dataframes': all_symbol_data[symbol],
        'predictions': predictions,
        'timeframe_votes': {
            tf: pred['signal'] for tf, pred in predictions.items()
        },
        'ensemble_score': ensemble_score
    }
    
    all_signals.append(signal)

return all_signals
```

**Esempio Ensemble Voting:**

```
Symbol: SOL/USDT

Predictions:
- 15m: BUY (conf=0.72)  × peso 1.0 = +0.72
- 30m: BUY (conf=0.68)  × peso 1.2 = +0.816
- 1h:  BUY (conf=0.75)  × peso 1.5 = +1.125

Ensemble = (0.72 + 0.816 + 1.125) / (1.0 + 1.2 + 1.5)
         = 2.661 / 3.7
         = 0.719 (71.9%)

✅ ensemble_score = 0.719 >= 0.65 → SIGNAL: BUY
✅ confidence = 0.719 >= MIN_CONFIDENCE (0.65) → PASS
→ Add to all_signals
```

---

## 📋 APPENDICE A: TRAINING PIPELINE DETTAGLIATA

**File:** `trainer.py`

### **Training XGBoost Model - Overview**

```python
async def train_xgboost_model_wrapper(top_symbols, exchange, timestep, timeframe):
    """
    Pipeline completa training XGBoost
    
    Steps:
    1. Data Collection (fetch historical)
    2. Labeling (SL-aware o standard)
    3. Feature Engineering (temporal features)
    4. Cross-Validation (3 folds)
    5. Training finale con SMOTE
    6. Evaluation & Metrics
    7. Save model + scaler
    """
```

### **STEP 1: Data Collection**

```python
X_all, y_all = [], []

for symbol in top_symbols:
    # Fetch dati storici con indicators
    df = await fetch_and_save_data(exchange, symbol, timeframe)
    """
    fetch_and_save_data():
        - Fetch 200 candles da Bybit
        - Calcola 33 indicators (come in produzione)
        - Return DataFrame completo
    """
    
    # Prepare data (convert to numpy)
    data = prepare_data(df)
    """
    prepare_data(df):
        columns = config.EXPECTED_COLUMNS  # 33 features
        data = df[columns].values
        data = np.nan_to_num(data, nan=0.0)
        return data  # Shape: (n_candles, 33)
    """
```

### **STEP 2: Labeling System**

#### **SL-Aware Labeling (PRODUCTION)**

```python
if config.SL_AWARENESS_ENABLED:
    labels, sl_features = label_with_sl_awareness_v2(
        df,
        lookforward_steps=config.FUTURE_RETURN_STEPS,  # 3
        sl_percentage=config.STOP_LOSS_PCT,  # 0.05 (5%)
        percentile_buy=80,   # Top 20% → BUY
        percentile_sell=80   # Top 20% → SELL
    )
```

**Algoritmo SL-Aware:**

```python
def label_with_sl_awareness_v2(df, lookforward_steps, sl_percentage, percentile_buy, percentile_sell):
    """
    Stop Loss Aware Labeling
    
    Innovazione chiave:
    - Non elimina sample con SL hit
    - Li mantiene e aggiunge features informative
    - ML impara a riconoscere situazioni rischiose
    """
    
    labels = np.full(len(df), 2)  # Default NEUTRAL
    
    # Feature engineering arrays
    sl_features = {
        'sl_hit_buy': np.zeros(len(df)),
        'sl_hit_sell': np.zeros(len(df)),
        'max_drawdown_pct': np.zeros(len(df)),
        'max_drawup_pct': np.zeros(len(df)),
        'volatility_path': np.zeros(len(df))
    }
    
    buy_returns_data = []
    sell_returns_data = []
    
    close_prices = df['close'].values
    low_prices = df['low'].values
    high_prices = df['high'].values
    
    for i in range(len(df) - lookforward_steps):
        entry_price = close_prices[i]
        
        # Path future (prossime N candles)
        path_lows = low_prices[i:i+lookforward_steps]
        path_highs = high_prices[i:i+lookforward_steps]
        path_closes = close_prices[i:i+lookforward_steps]
        
        # ═══════════════════════════════════════════════
        # BUY SCENARIO
        # ═══════════════════════════════════════════════
        buy_sl_price = entry_price * (1 - sl_percentage)  # -5%
        buy_sl_hit = np.any(path_lows <= buy_sl_price)
        
        # Max drawdown nel path
        max_drawdown = np.min(path_lows)
        max_drawdown_pct = (max_drawdown - entry_price) / entry_price
        
        # Borderline: vicino a SL ma non colpito
        buy_borderline = (
            max_drawdown_pct < -config.SL_AWARENESS_BORDERLINE_BUY and 
            max_drawdown_pct > -sl_percentage
        )
        
        # ═══════════════════════════════════════════════
        # SELL SCENARIO
        # ═══════════════════════════════════════════════
        sell_sl_price = entry_price * (1 + sl_percentage)  # +5%
        sell_sl_hit = np.any(path_highs >= sell_sl_price)
        
        # Max drawup nel path
        max_drawup = np.max(path_highs)
        max_drawup_pct = (max_drawup - entry_price) / entry_price
        
        # Borderline: vicino a SL ma non colpito
        sell_borderline = (
            max_drawup_pct > config.SL_AWARENESS_BORDERLINE_SELL and 
            max_drawup_pct < sl_percentage
        )
        
        # ═══════════════════════════════════════════════
        # VOLATILITY PATH
        # ═══════════════════════════════════════════════
        volatility = np.std(path_closes) / (np.mean(path_closes) + 1e-8)
        
        # ═══════════════════════════════════════════════
        # STORE FEATURES (manteniamo TUTTI i sample!)
        # ═══════════════════════════════════════════════
        sl_features['sl_hit_buy'][i] = 1.0 if buy_sl_hit else 0.0
        sl_features['sl_hit_sell'][i] = 1.0 if sell_sl_hit else 0.0
        sl_features['max_drawdown_pct'][i] = max_drawdown_pct
        sl_features['max_drawup_pct'][i] = max_drawup_pct
        sl_features['volatility_path'][i] = volatility
        
        # ═══════════════════════════════════════════════
        # CALCULATE RETURNS
        # ═══════════════════════════════════════════════
        future_price = close_prices[i + lookforward_steps]
        buy_return = (future_price - entry_price) / entry_price
        sell_return = (entry_price - future_price) / entry_price
        
        # Add to lists (includi ANCHE sample con SL hit!)
        if not buy_borderline:
            buy_returns_data.append((i, buy_return, buy_sl_hit))
        
        if not sell_borderline:
            sell_returns_data.append((i, sell_return, sell_sl_hit))
    
    # ═══════════════════════════════════════════════
    # PERCENTILE LABELING (include SL hit samples)
    # ═══════════════════════════════════════════════
    if buy_returns_data:
        all_returns = np.array([r for _, r, _ in buy_returns_data])
        buy_threshold = np.percentile(all_returns, percentile_buy)
        
        for idx, return_val, sl_hit in buy_returns_data:
            if return_val >= buy_threshold:
                labels[idx] = 1  # BUY
    
    if sell_returns_data:
        all_returns = np.array([r for _, r, _ in sell_returns_data])
        sell_threshold = np.percentile(all_returns, percentile_sell)
        
        for idx, return_val, sl_hit in sell_returns_data:
            if return_val >= sell_threshold:
                labels[idx] = 0  # SELL
    
    # Return labels + features addizionali
    return labels, sl_features
```

**Vantaggi SL-Aware Labeling:**

```
1. ✅ NO survivorship bias
   - Mantiene tutti i sample, anche quelli con SL hit
   
2. ✅ Feature engineering
   - ML impara quando SL è probabile
   - Riconosce pattern rischiosi
   
3. ✅ Percentile adaptativi
   - Top 20% BUY/SELL automaticamente bilanciato
   - No thresholds fissi da tuning
   
4. ✅ Production-ready
   - Addestra con stesso SL% usato in live
   - ML allineato con strategia reale
```

### **STEP 3: Temporal Features**

```python
timesteps = config.get_timesteps_for_timeframe(timeframe)

for i in range(timesteps, len(data) - FUTURE_RETURN_STEPS):
    sequence = data[i - timesteps : i]
    
    temporal_features = create_temporal_features(sequence)
    X_all.append(temporal_features)
    y_all.append(labels[i])
```

**Create Temporal Features - Breakdown:**

```python
def create_temporal_features(sequence):
    """
    Enhanced B+ Hybrid System
    
    Features totali: 66
    - Current State: 33 features
    - Momentum Patterns: 27 features
    - Critical Stats: 6 features
    """
    
    features = []
    
    # ═══════════════════════════════════════════════
    # 1. CURRENT STATE (33 features)
    # ═══════════════════════════════════════════════
    # Ultim candle completa con tutti gli indicators
    features.extend(sequence[-1])
    
    # ═══════════════════════════════════════════════
    # 2. MOMENTUM PATTERNS (27 features)
    # ═══════════════════════════════════════════════
    # Analizza trend su tutta la sequenza
    # Usa correlation per catturare momentum
    
    important_features = [0, 1, 2, 3, 4, 7, 8, 9, 10, 11, 13, 14, 15, 
                         16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]
    
    momentum_features = []
    for col_idx in important_features:
        if col_idx < sequence.shape[1]:
            col_data = sequence[:, col_idx]
            
            # Time series correlation
            time_index = np.arange(len(col_data))
            correlation = np.corrcoef(time_index, col_data)[0, 1]
            
            momentum_features.append(correlation if np.isfinite(correlation) else 0.0)
    
    features.extend(momentum_features)
    
    # ═══════════════════════════════════════════════
    # 3. CRITICAL STATS (6 features)
    # ═══════════════════════════════════════════════
    # Volatilità delle features più importanti
    
    CRITICAL_FEATURES = {
        'close': 3,
        'volume': 4,
        'rsi_fast': 13,
        'atr': 14,
        'macd': 8,
        'ema20': 7
    }
    
    critical_stats = []
    for feature_name, col_idx in CRITICAL_FEATURES.items():
        if col_idx < sequence.shape[1]:
            col_data = sequence[:, col_idx]
            
            # Volatility measure
            volatility = np.std(col_data) / (np.mean(np.abs(col_data)) + 1e-8)
            critical_stats.append(volatility)
        else:
            critical_stats.append(0.0)
    
    features.extend(critical_stats)
    
    # ═══════════════════════════════════════════════
    # VALIDATION & CLEANUP
    # ═══════════════════════════════════════════════
    features = np.array(features, dtype=np.float64)
    features = np.nan_to_num(features, nan=0.0, posinf=1e6, neginf=-1e6)
    
    final_features = features.flatten()
    
    # Ensure exactly 66 features
    if len(final_features) != config.N_FEATURES_FINAL:
        if len(final_features) < config.N_FEATURES_FINAL:
            # Pad with zeros
            padding = np.zeros(config.N_FEATURES_FINAL - len(final_features))
            final_features = np.concatenate([final_features, padding])
        else:
            # Truncate
            final_features = final_features[:config.N_FEATURES_FINAL]
    
    return final_features
```

### **STEP 4: XGBoost Training con Cross-Validation**

```python
def _train_xgb_sync_improved(X, y):
    """
    Training XGBoost con features avanzate
    """
    
    # ═══════════════════════════════════════════════
    # PREPROCESSING
    # ═══════════════════════════════════════════════
    scaler = StandardScaler().fit(X)
    X_scaled = scaler.transform(X)
    
    # ═══════════════════════════════════════════════
    # CROSS-VALIDATION (3 folds)
    # ═══════════════════════════════════════════════
    tscv = TimeSeriesSplit(n_splits=config.CV_N_SPLITS)
    cv_scores = []
    best_model = None
    best_score = 0
    
    for fold_idx, (tr_idx, val_idx) in enumerate(tscv.split(X_scaled)):
        X_tr, X_val = X_scaled[tr_idx], X_scaled[val_idx]
        y_tr, y_val = y[tr_idx], y[val_idx]
        
        # SMOTE per fold (se enabled)
        if config.USE_SMOTE:
            smote = SMOTE(k_neighbors=3, random_state=42 + fold_idx)
            X_tr, y_tr = smote.fit_resample(X_tr, y_tr)
        
        # Class weights
        sample_weight = None
        if config.USE_CLASS_WEIGHTS:
            class_weights = class_weight.compute_class_weight(
                'balanced', classes=np.unique(y_tr), y=y_tr
            )
            class_weight_dict = {i: class_weights[i] for i in range(len(class_weights))}
            sample_weight = np.array([class_weight_dict[cls] for cls in y_tr])
        
        # Train model
        model = xgb.XGBClassifier(
            n_estimators=config.XGB_N_ESTIMATORS,  # 200
            max_depth=config.XGB_MAX_DEPTH,  # 4
            learning_rate=config.XGB_LEARNING_RATE,  # 0.05
            subsample=config.XGB_SUBSAMPLE,  # 0.7
            colsample_bytree=config.XGB_COLSAMPLE_BYTREE,  # 0.7
            reg_alpha=config.XGB_REG_ALPHA,  # 0.1
            reg_lambda=config.XGB_REG_LAMBDA,  # 1.0
            num_class=3,
            objective='multi:softprob',
            eval_metric='mlogloss',
            verbosity=0,
            random_state=42,
            early_stopping_rounds=20
        )
        
        model.fit(
            X_tr, y_tr,
            eval_set=[(X_val, y_val)],
            sample_weight=sample_weight,
            verbose=False
        )
        
        # Evaluate fold
        y_pred = model.predict(X_val)
        fold_score = accuracy_score(y_val, y_pred)
        cv_scores.append(fold_score)
        
        if fold_score > best_score:
            best_score = fold_score
            best_model = model
    
    # ═══════════════════════════════════════════════
    # FINAL TRAINING (con tutti i dati)
    # ═══════════════════════════════════════════════
    final_tr_idx, final_val_idx = list(tscv.split(X_scaled))[-1]
    X_final_tr, X_final_val = X_scaled[final_tr_idx], X_scaled[final_val_idx]
    y_final_tr, y_final_val = y[final_tr_idx], y[final_val_idx]
    
    # SMOTE finale
    if config.USE_SMOTE:
        smote_final = SMOTE(k_neighbors=3, random_state=999)
        X_final_tr, y_final_tr = smote_final.fit_resample(X_final_tr, y_final_tr)
    
    # Class weights finali
    final_sample_weight = None
    if config.USE_CLASS_WEIGHTS:
        final_class_weights = class_weight.compute_class_weight(
            'balanced', classes=np.unique(y_final_tr), y=y_final_tr
        )
        final_class_weight_dict = {i: final_class_weights[i] for i in range(len(final_class_weights))}
        final_sample_weight = np.array([final_class_weight_dict[cls] for cls in y_final_tr])
    
    # Final model
    final_model = xgb.XGBClassifier(
        n_estimators=config.XGB_N_ESTIMATORS,
        max_depth=config.XGB_MAX_DEPTH,
        learning_rate=config.XGB_LEARNING_RATE,
        subsample=config.XGB_SUBSAMPLE,
        colsample_bytree=config.XGB_COLSAMPLE_BYTREE,
        reg_alpha=config.XGB_REG_ALPHA,
        reg_lambda=config.XGB_REG_LAMBDA,
        num_class=3,
        objective='multi:softprob',
        eval_metric='mlogloss',
        verbosity=1,
        random_state=42,
        early_stopping_rounds=20
    )
    
    final_model.fit(
        X_final_tr, y_final_tr,
        eval_set=[(X_final_val, y_final_val)],
        sample_weight=final_sample_weight,
        verbose=True
    )
    
    # ═══════════════════════════════════════════════
    # EVALUATION
    # ═══════════════════════════════════════════════
    y_pred_final = final_model.predict(X_final_val)
    y_pred_proba = final_model.predict_proba(X_final_val)
    
    metrics = {
        "val_accuracy": accuracy_score(y_final_val, y_pred_final),
        "val_precision": precision_score(y_final_val, y_pred_final, average="weighted"),
        "val_recall": recall_score(y_final_val, y_pred_final, average="weighted"),
        "val_f1": f1_score(y_final_val, y_pred_final, average="weighted"),
        "cv_mean_accuracy": np.mean(cv_scores),
        "cv_std_accuracy": np.std(cv_scores),
        "best_fold_score": best_score
    }
    
    # Classification Report
    class_names = ['SELL', 'BUY', 'NEUTRAL']
    report = classification_report(y_final_val, y_pred_final, target_names=class_names)
    
    # Confusion Matrix
    cm = confusion_matrix(y_final_val, y_pred_final)
    
    # Feature Importance
    importance = final_model.feature_importances_
    
    return final_model, scaler, metrics, y_final_val, y_pred_final, y_pred_proba
```

### **STEP 5: Save Model**

```python
# Save model
joblib.dump(model, f"trained_models/xgb_model_{timeframe}.pkl")
joblib.dump(scaler, f"trained_models/xgb_scaler_{timeframe}.pkl")

# Save metrics JSON
with open(f"trained_models/xgb_model_{timeframe}.json", "w") as f:
    json.dump(metrics, f, indent=4)

# Generate visualizations
from core.visualization import save_training_metrics
viz_path = save_training_metrics(
    y_true=y_final_val,
    y_pred=y_pred_final,
    y_prob=y_pred_proba,
    feature_importance=model.feature_importances_,
    feature_names=feature_names,
    timeframe=timeframe,
    metrics=metrics
)
```

---

## 🎯 CONFIGURAZIONI CHIAVE

### **Trading Parameters**

```python
# config.py

# Leverage
LEVERAGE = 8  # 8x leverage

# Max Positions
MAX_CONCURRENT_POSITIONS = 5  # Max 5 posizioni simultanee

# Trade Cycle
TRADE_CYCLE_INTERVAL = 900  # 15 minuti (900 secondi)

# Confidence
MIN_CONFIDENCE = 0.65  # 65% confidence minima
```

### **Risk Management**

```python
# Stop Loss (FISSO)
STOP_LOSS_PCT = 0.05  # 5% stop loss

# Take Profit
TP_ENABLED = True
TP_ROE_TARGET = 0.60  # +60% ROE target
TP_RISK_REWARD_RATIO = 2.5  # R/R ratio 2.5:1

# Trailing Stop
TRAILING_ENABLED = True
TRAILING_TRIGGER_ROE = 0.40  # Attiva a +40% ROE
TRAILING_DISTANCE_ROE_OPTIMAL = 0.10  # Distanza 10% ROE
TRAILING_UPDATE_INTERVAL = 60  # Update ogni 60s

# Early Exit
EARLY_EXIT_ENABLED = True
EARLY_EXIT_IMMEDIATE_TIME_MINUTES = 5
EARLY_EXIT_IMMEDIATE_DROP_ROE = -10  # -10% ROE in 5 min
EARLY_EXIT_FAST_TIME_MINUTES = 15
EARLY_EXIT_FAST_DROP_ROE = -15  # -15% ROE in 15 min
```

### **Adaptive Sizing**

```python
# Enable/Disable
ADAPTIVE_SIZING_ENABLED = True

# Wallet Structure
ADAPTIVE_WALLET_BLOCKS = 5  # 5 blocchi
ADAPTIVE_FIRST_CYCLE_FACTOR = 0.5  # 50% per primo ciclo

# Penalty System
ADAPTIVE_BLOCK_CYCLES = 3  # Blocco 3 cicli dopo loss
ADAPTIVE_CAP_MULTIPLIER = 1.0  # Cap = slot_value × 1.0

# Risk Limits
ADAPTIVE_RISK_MAX_PCT = 0.20  # Max 20% wallet a rischio
ADAPTIVE_LOSS_MULTIPLIER = 0.30  # Max loss = 30% del margin

# Fresh Start
ADAPTIVE_FRESH_START = True  # True = reset, False = historical
```

### **ML Training**

```python
# Data
TOP_ANALYSIS_CRYPTO = 50  # Top 50 simboli
TOP_TRAIN_CRYPTO = 50
DATA_LIMIT_DAYS = 180  # 180 giorni di storia

# Timeframes
ENABLED_TIMEFRAMES = ["15m", "30m", "1h"]
LOOKBACK_HOURS = 6  # 6 ore lookback

# Labeling
SL_AWARENESS_ENABLED = True
SL_AWARENESS_PERCENTAGE = 0.05  # 5% SL
SL_AWARENESS_PERCENTILE_BUY = 80  # Top 20%
SL_AWARENESS_PERCENTILE_SELL = 80  # Top 20%
FUTURE_RETURN_STEPS = 3  # 3 candles ahead

# Features
N_FEATURES_FINAL = 66  # 66 temporal features

# XGBoost
XGB_N_ESTIMATORS = 200
XGB_MAX_DEPTH = 4
XGB_LEARNING_RATE = 0.05
XGB_SUBSAMPLE = 0.7
XGB_COLSAMPLE_BYTREE = 0.7
XGB_REG_ALPHA = 0.1
XGB_REG_LAMBDA = 1.0

# Cross-Validation
CV_N_SPLITS = 3
USE_SMOTE = False
USE_CLASS_WEIGHTS = True
```

---

## 📚 RIFERIMENTI FILE SORGENTE

### **Core Files**

| File | Descrizione |
|------|-------------|
| `main.py` | Entry point, orchestrazione generale |
| `config.py` | Configurazione completa (500+ parametri) |
| `trading/trading_engine.py` | Trading loop e cicli |
| `trading/market_analyzer.py` | Selezione simboli e fetch dati |
| `trading/signal_processor.py` | Ensemble voting e filtering |

### **Position Management**

| File | Descrizione |
|------|-------------|
| `core/position_management/position_core.py` | CRUD operations thread-safe |
| `core/position_management/position_sync.py` | Sync con Bybit |
| `core/position_management/position_trailing.py` | Trailing stop system |
| `core/position_management/position_safety.py` | Safety checks |
| `core/position_management/position_io.py` | File persistence |

### **Risk & Sizing**

| File | Descrizione |
|------|-------------|
| `core/risk_calculator.py` | Calcolo margins e risk |
| `core/adaptive_position_sizing.py` | Adaptive sizing system |
| `core/cost_calculator.py` | Fee e cost calculations |

### **ML & Training**

| File | Descrizione |
|------|-------------|
| `trainer.py` | Training pipeline XGBoost |
| `model_loader.py` | Load modelli trainati |
| `data_utils.py` | Data preparation utilities |
| `fetcher.py` | Fetch OHLCV + indicators |

### **Utilities**

| File | Descrizione |
|------|-------------|
| `core/time_sync_manager.py` | Time synchronization |
| `core/smart_api_manager.py` | API cache intelligente |
| `core/database_cache.py` | SQLite caching system |
| `logging_config.py` | Logging configuration |

---

## 🎓 GLOSSARIO TERMINI TECNICI

### **Trading Terms**

- **ROE (Return on Equity)**: Profitto percentuale sul margin (con leverage)
- **PnL (Profit & Loss)**: Profitto/perdita in $ o %
- **Notional Value**: Valore totale posizione (size × prezzo)
- **Initial Margin (IM)**: Collaterale iniziale richiesto
- **Leverage**: Moltiplicatore (8x = controlli 8× il tuo capitale)

### **Stop Loss Types**

- **Fixed SL**: Stop loss fisso (5% del prezzo entry)
- **Trailing Stop**: Stop loss che segue il prezzo in profit
- **Early Exit**: Chiusura anticipata prima del SL fisso

### **Position Sizing**

- **Adaptive Sizing**: Sistema che impara da ogni trade
- **Kelly Criterion**: Formula matematica per optimal sizing
- **Slot Value**: Valore di un blocco wallet
- **Base Size**: Size di partenza per nuovo simbolo

### **ML Terms**

- **Temporal Features**: Features create da sequenze temporali
- **Ensemble Voting**: Combinazione predizioni multi-time
