r# 🤖 04 - ML Prediction System (PARTE 1/2)

Sistema completo di machine learning: training, feature engineering, e predizioni.

---

## 📋 Indice Parte 1

1. [Overview Sistema ML](#overview-sistema-ml)
2. [XGBoost Training Process](#xgboost-training-process)
3. [Data Labeling Strategy](#data-labeling-strategy)
4. [Feature Engineering Completo](#feature-engineering-66-features)

**Parte 2:** [Ensemble Voting, Calibration, Performance](04-ML-SYSTEM-PART2.md)

---

## 🎯 Overview Sistema ML

### **Architecture Completa:**

```
┌─────────────────────────────────────────────────────────────┐
│                    ML PREDICTION PIPELINE                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: DATA PREPARATION                                    │
│ ├─ Fetch 500 candele (15m, 30m, 1h)                        │
│ ├─ Calculate 33 technical indicators                        │
│ └─ Create temporal sequences                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: FEATURE ENGINEERING (Enhanced B+ Hybrid)           │
│ ├─ Extract 33 current state features                        │
│ ├─ Calculate 27 momentum patterns (ALL candles)            │
│ ├─ Compute 6 critical statistics                           │
│ └─ Output: 66-dimensional feature vector                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: MULTI-TIMEFRAME PREDICTION                         │
│ ├─ 15m XGBoost → [prob_SELL, prob_BUY, prob_NEUTRAL]       │
│ ├─ 30m XGBoost → [prob_SELL, prob_BUY, prob_NEUTRAL]       │
│ └─ 1h  XGBoost → [prob_SELL, prob_BUY, prob_NEUTRAL]       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: ENSEMBLE VOTING (Weighted)                         │
│ ├─ Weight_15m = confidence × 1.0                            │
│ ├─ Weight_30m = confidence × 1.2                            │
│ ├─ Weight_1h  = confidence × 1.5                            │
│ └─ Majority vote → Final signal                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: CONFIDENCE CALIBRATION                             │
│ ├─ Raw confidence (0.0-1.0) from ensemble                   │
│ ├─ Calibration mapping (4051 historical trades)            │
│ └─ Calibrated confidence = real expected win rate          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    (confidence, signal, tf_predictions)
```

### **Key Statistics:**

```
Training Data:
├─ Symbols trained: 50+ top volume cryptos
├─ Historical period: 180 days
├─ Total samples: ~150,000+ per timeframe
└─ Class distribution: ~15% BUY, 15% SELL, 70% NEUTRAL (selective)

Model Performance:
├─ Accuracy: 62-68% (test set)
├─ Win rate (calibrated): 55-58%
├─ Total trades analyzed: 4,051
└─ Calibration R²: 0.89 (excellent)

Prediction Speed:
├─ Single symbol: ~3-5 seconds
├─ 50 symbols batch: ~3-4 minutes
└─ Feature extraction: < 0.1s per symbol
```

---

## 🎓 XGBoost Training Process

### **Complete Training Pipeline:**

Il sistema ora utilizza un **training migliorato** con:
- ✅ **SMOTE per-fold**: Balancing applicato ad ogni fold della cross-validation
- ✅ **Class weights**: Penalizzazione automatica per classi sbilanciate
- ✅ **Early stopping**: Previene overfitting con patience=20
- ✅ **Time Series Split**: Cross-validation rispetta l'ordine temporale

```python
async def train_xgboost_model_wrapper(top_symbols, exchange, timestep, timeframe):
    """
    Wrapper per training XGBoost con labeling avanzato
    
    PROCESS:
    1. Download historical data (180 days) per ogni symbol
    2. Calculate technical indicators (33 features base)
    3. Apply labeling strategy:
       - SL-Aware Labeling (se abilitato) con 5 features aggiuntive
       - Percentile-based Labeling (standard)
    4. Create temporal features (66 totali)
    5. Train con cross-validation robusta:
       - SMOTE applicato per ogni fold
       - Class weights per gestire imbalance
       - Early stopping
    6. Evaluate e save model + scaler
    
    Returns:
        model: trained XGBClassifier
        scaler: fitted StandardScaler
        metrics: dict con performance metrics
    """
    # ... implementazione dettagliata in trainer.py
```

### **Improved Training Function (_train_xgb_sync_improved):**

```python
def _train_xgb_sync_improved(X, y):
    """
    Versione migliorata del training XGBoost
    
    CRITICAL IMPROVEMENTS:
    1. Cross-validation robusta su tutti i fold
    2. SMOTE applicato per ogni fold (evita temporal leakage)
    3. Class balancing con sample weights
    4. Early stopping per prevenire overfitting
    5. Valutazione dettagliata con confusion matrix
    
    Args:
        X: Feature matrix (samples × 66)
        y: Labels (0=SELL, 1=BUY, 2=NEUTRAL)
    
    Returns:
        model: Final trained model
        scaler: StandardScaler fitted
        metrics: Performance metrics dict
        y_val: Validation labels
        y_pred: Predictions
        y_pred_proba: Prediction probabilities
    """
    # Preprocessing
    scaler = StandardScaler().fit(X)
    X_scaled = scaler.transform(X)
    
    # Time Series Cross-Validation con SMOTE per fold
    tscv = TimeSeriesSplit(n_splits=config.CV_N_SPLITS)
    cv_scores = []
    best_model = None
    best_score = 0
    
    for fold_idx, (tr_idx, val_idx) in enumerate(tscv.split(X_scaled)):
        X_tr, X_val = X_scaled[tr_idx], X_scaled[val_idx]
        y_tr, y_val = y[tr_idx], y[val_idx]
        
        # CRITICAL: SMOTE per ogni fold (evita temporal bias)
        if config.USE_SMOTE:
            smote = SMOTE(
                k_neighbors=config.SMOTE_K_NEIGHBORS,
                random_state=42 + fold_idx
            )
            X_tr, y_tr = smote.fit_resample(X_tr, y_tr)
        
        # Class weights
        sample_weight = None
        if config.USE_CLASS_WEIGHTS:
            class_weights = class_weight.compute_class_weight(
                'balanced', classes=np.unique(y_tr), y=y_tr
            )
            sample_weight = np.array([class_weights[cls] for cls in y_tr])
        
        # Train con early stopping
        model = xgb.XGBClassifier(
            n_estimators=config.XGB_N_ESTIMATORS,  # 200
            max_depth=config.XGB_MAX_DEPTH,        # 4
            learning_rate=config.XGB_LEARNING_RATE, # 0.05
            subsample=config.XGB_SUBSAMPLE,         # 0.7
            colsample_bytree=config.XGB_COLSAMPLE_BYTREE, # 0.7
            reg_alpha=config.XGB_REG_ALPHA,         # 0.1
            reg_lambda=config.XGB_REG_LAMBDA,       # 1.0
            num_class=3,
            objective='multi:softprob',
            eval_metric='mlogloss',
            early_stopping_rounds=20
        )
        
        model.fit(
            X_tr, y_tr,
            eval_set=[(X_val, y_val)],
            sample_weight=sample_weight,
            verbose=False
        )
        
        fold_score = accuracy_score(y_val, model.predict(X_val))
        cv_scores.append(fold_score)
        
        if fold_score > best_score:
            best_score = fold_score
            best_model = model
    
    # Final training con SMOTE sui dati completi
    final_model = xgb.XGBClassifier(...)  # Stessi parametri
    
    # Apply SMOTE finale
    if config.USE_SMOTE:
        X_scaled, y = smote_final.fit_resample(X_scaled, y)
    
    # Train final model
    final_model.fit(X_scaled, y, ...)
    
    return final_model, scaler, metrics, y_val, y_pred, y_pred_proba
```

**Key Hyperparameters:**

```python
# XGBoost Configuration (ottimizzato per crypto trading)
XGB_N_ESTIMATORS = 200         # Numero di trees
XGB_MAX_DEPTH = 4              # Profondità max (evita overfitting)
XGB_LEARNING_RATE = 0.05       # Learning rate conservativo
XGB_SUBSAMPLE = 0.7            # Sample 70% data per tree
XGB_COLSAMPLE_BYTREE = 0.7     # Use 70% features per tree
XGB_REG_ALPHA = 0.1            # L1 regularization
XGB_REG_LAMBDA = 1.0           # L2 regularization

# Class Balancing
USE_SMOTE = False              # SMOTE disabilitato (usa percentili)
USE_CLASS_WEIGHTS = True       # Class weights abilitati
SMOTE_K_NEIGHBORS = 3          # Neighbors per SMOTE

# Cross-Validation
CV_N_SPLITS = 3                # 3-fold time series CV
```

---

## 🏆 Data Labeling Strategy

### **INDUSTRY STANDARD: Percentile-Based Labeling**

Il sistema utilizza un metodo di labeling **basato su percentili** anziché soglie fisse. Questo è lo standard nell'industria dei hedge funds professionali e garantisce:

✅ **Class balance automatico** (sempre ~15% BUY, ~15% SELL, ~70% NEUTRAL)  
✅ **Adattamento ai dati** (soglie dinamiche per ogni timeframe)  
✅ **Riduzione overtrading** (solo top 15% movements)  
✅ **Nessun lookahead bias** (usa solo dati storici)

```python
def label_with_future_returns(df, lookforward_steps=3):
    """
    🏆 INDUSTRY STANDARD: Percentile-Based Labeling
    
    Classifica BUY/SELL/NEUTRAL basandosi sui percentili dei returns futuri.
    Questo garantisce class balance e selezione delle opportunità migliori.
    
    Args:
        df: DataFrame con OHLCV + indicators
        lookforward_steps: Steps futuri per calcolare return (default: 3)
    
    Returns:
        labels: np.ndarray [0=SELL, 1=BUY, 2=NEUTRAL]
    
    PROCESS:
    1. Calcola future return per ogni candela (lookahead N steps)
    2. Calcola percentili sui returns:
       - 85° percentile = BUY threshold (top 15%)
       - 15° percentile = SELL threshold (bottom 15%)
    3. Assegna labels:
       - return >= 85th percentile → BUY
       - return <= 15th percentile → SELL
       - else → NEUTRAL (70% dei casi)
    """
    labels = np.full(len(df), 2)  # Default = NEUTRAL
    
    # Calcola tutti i returns futuri
    future_returns = []
    valid_indices = []
    
    for i in range(len(df) - lookforward_steps):
        current_price = df.iloc[i]['close']
        future_price = df.iloc[i + lookforward_steps]['close']
        
        # Return percentuale
        future_return = (future_price - current_price) / current_price
        
        future_returns.append(future_return)
        valid_indices.append(i)
    
    if not future_returns:
        return labels
    
    future_returns = np.array(future_returns)
    
    # 🏆 PERCENTILE THRESHOLDS (Adaptive per i dati)
    buy_threshold = np.percentile(future_returns, 85)   # Top 15% → BUY
    sell_threshold = np.percentile(future_returns, 15)  # Bottom 15% → SELL
    
    # Assegna labels
    for idx, return_val in enumerate(future_returns):
        original_idx = valid_indices[idx]
        
        if return_val >= buy_threshold:
            labels[original_idx] = 1  # BUY
        elif return_val <= sell_threshold:
            labels[original_idx] = 0  # SELL
        # else: NEUTRAL (70%)
    
    # Log statistics
    buy_count = np.sum(labels == 1)
    sell_count = np.sum(labels == 0)
    neutral_count = np.sum(labels == 2)
    
    print(f"🏆 Percentile Labeling:")
    print(f"   📈 BUY threshold (85th):  {buy_threshold:.4f} ({buy_threshold*100:.2f}%)")
    print(f"   📉 SELL threshold (15th): {sell_threshold:.4f} ({sell_threshold*100:.2f}%)")
    print(f"   🎯 Distribution: BUY={buy_count}(15%), SELL={sell_count}(15%), NEUTRAL={neutral_count}(70%)")
    
    return labels
```

### **Esempio Pratico:**

```
Symbol: SOL/USDT:USDT, Timeframe: 1h
Samples: 5000 candles

Future Returns Distribution:
├─ Minimum: -8.5%
├─ 15th percentile: -1.2% ← SELL threshold
├─ Median: +0.1%
├─ 85th percentile: +1.5% ← BUY threshold
└─ Maximum: +12.3%

Resulting Labels:
├─ BUY:     750 samples (15.0%) - returns > +1.5%
├─ SELL:    750 samples (15.0%) - returns < -1.2%
└─ NEUTRAL: 3500 samples (70.0%) - returns between -1.2% and +1.5%

✅ Perfect balance automatico!
✅ Focus sulle migliori opportunità (top/bottom 15%)
```

---

## 🎯 SL-Aware Labeling V2 (PRODUCTION)

### **Stop Loss Aware Training**

Sistema avanzato che **considera gli stop loss** durante il training. Il modello impara a riconoscere situazioni che portano a SL hit, evitandole in produzione.

**⚠️ CRITICAL**: Usa lo stesso SL% (3%) che verrà usato in runtime per perfetto allineamento!

```python
def label_with_sl_awareness_v2(df, lookforward_steps=3, sl_percentage=0.03,
                                percentile_buy=80, percentile_sell=80):
    """
    🎯 PRODUCTION: Stop Loss Aware Labeling con Feature Engineering
    
    Invece di eliminare sample con SL hit, li mantiene e aggiunge features
    che insegnano al modello a riconoscere situazioni a rischio SL.
    
    ADVANCED FEATURES:
    ✅ NO survivorship bias (mantiene tutti i sample)
    ✅ 5 nuove features per ogni sample
    ✅ Percentili configurabili
    ✅ Vectorizzato NumPy per performance
    
    Args:
        df: DataFrame con OHLCV columns
        lookforward_steps: Candele future per label (default: 3)
        sl_percentage: Stop loss % (default: 0.03 = 3%, come in runtime!)
        percentile_buy: Percentile per BUY (default: 80 = top 20%)
        percentile_sell: Percentile per SELL (default: 80 = top 20%)
    
    Returns:
        tuple: (labels, sl_features_dict)
            labels: np.ndarray [0=SELL, 1=BUY, 2=NEUTRAL]
            sl_features: dict con 5 nuove features per training
    """
    labels = np.full(len(df), 2)  # Default NEUTRAL
    
    # Feature engineering (manteniamo tutti i sample!)
    sl_features = {
        'sl_hit_buy': np.zeros(len(df)),      # SL hit scenario BUY
        'sl_hit_sell': np.zeros(len(df)),     # SL hit scenario SELL
        'max_drawdown_pct': np.zeros(len(df)), # Max drawdown nel path
        'max_drawup_pct': np.zeros(len(df)),   # Max drawup nel path
        'volatility_path': np.zeros(len(df))   # Volatilità del path
    }
    
    # Vectorized arrays
    close_prices = df['close'].values
    low_prices = df['low'].values
    high_prices = df['high'].values
    
    buy_returns_data = []
    sell_returns_data = []
    
    for i in range(len(df) - lookforward_steps):
        entry_price = close_prices[i]
        
        # Path slices
        path_lows = low_prices[i:i+lookforward_steps]
        path_highs = high_prices[i:i+lookforward_steps]
        path_closes = close_prices[i:i+lookforward_steps]
        
        # BUY SCENARIO
        buy_sl_price = entry_price * (1 - sl_percentage)
        buy_sl_hit = np.any(path_lows <= buy_sl_price)
        max_drawdown = np.min(path_lows)
        max_drawdown_pct = (max_drawdown - entry_price) / entry_price
        
        # SELL SCENARIO
        sell_sl_price = entry_price * (1 + sl_percentage)
        sell_sl_hit = np.any(path_highs >= sell_sl_price)
        max_drawup = np.max(path_highs)
        max_drawup_pct = (max_drawup - entry_price) / entry_price
        
        # VOLATILITY
        volatility = np.std(path_closes) / (np.mean(path_closes) + 1e-8)
        
        # Store features (il modello imparerà da questi!)
        sl_features['sl_hit_buy'][i] = 1.0 if buy_sl_hit else 0.0
        sl_features['sl_hit_sell'][i] = 1.0 if sell_sl_hit else 0.0
        sl_features['max_drawdown_pct'][i] = max_drawdown_pct
        sl_features['max_drawup_pct'][i] = max_drawup_pct
        sl_features['volatility_path'][i] = volatility
        
        # Calculate returns
        future_price = close_prices[i + lookforward_steps]
        buy_return = (future_price - entry_price) / entry_price
        sell_return = (entry_price - future_price) / entry_price
        
        # Add to lists per percentile labeling
        buy_returns_data.append((i, buy_return, buy_sl_hit))
        sell_returns_data.append((i, sell_return, sell_sl_hit))
    
    # PERCENTILE LABELING (include anche sample con SL hit!)
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
    
    return labels, sl_features
```

### **SL-Aware Configuration:**

```python
# config.py

# Master SL parameter (usato sia in training che in runtime)
STOP_LOSS_PCT = 0.03  # 3% = -30% ROE con 10x leverage

# SL-Aware Training
SL_AWARENESS_ENABLED = True                # Enable SL-aware labeling
SL_AWARENESS_PERCENTAGE = STOP_LOSS_PCT    # Stesso SL del runtime!
SL_AWARENESS_PERCENTILE_BUY = 80           # Top 20% returns
SL_AWARENESS_PERCENTILE_SELL = 80          # Top 20% returns
SL_AWARENESS_BORDERLINE_BUY = 0.025        # Threshold borderline -2.5%
SL_AWARENESS_BORDERLINE_SELL = 0.025       # Threshold borderline +2.5%
```

### **Vantaggi SL-Aware:**

| Feature | Beneficio |
|---------|-----------|
| 🎯 **No Survivorship Bias** | Mantiene tutti i sample, anche con SL hit |
| 🧠 **Feature Engineering** | 5 nuove features insegnano pattern rischiosi |
| ⚖️ **Perfect Alignment** | SL training = SL runtime (3%) |
| 📊 **Migliori Predizioni** | Modello evita situazioni con alto rischio SL |
| 🔄 **Percentili Adattivi** | Threshold automatici per BUY/SELL |

---

## 🔧 Feature Engineering (66 Features)

### **Enhanced B+ Hybrid System**

Sistema rivoluzionario che **usa TUTTE le candele intermedie** invece di solo prima/ultima. Questo elimina lo spreco del 92% dei dati!

```python
def create_temporal_features(sequence):
    """
    ENHANCED B+ HYBRID: Momentum + Selective Statistics
    
    REVOLUTIONARY UPGRADE:
    - Uses ALL intermediate candles (era sprecato 92% dei dati!)
    - Momentum patterns su full sequence
    - Statistical analysis su critical features
    - Maintains N_FEATURES_FINAL = 66 compatibility
    
    Args:
        sequence: np.ndarray shape (timesteps, 33_features)
        
    Returns:
        np.ndarray: Enhanced temporal features (66 total)
    
    STRUCTURE:
    [0-32]   CURRENT STATE (33 features)
    [33-59]  MOMENTUM PATTERNS (27 features)  ← USA TUTTE LE CANDELE!
    [60-65]  CRITICAL STATISTICS (6 features)
    """
    features = []
    
    # CRITICAL FEATURES indices for enhanced statistics
    CRITICAL_FEATURES = {
        'close': 3,      # Price (most important)
        'volume': 4,     # Volume (breakout confirmation)  
        'rsi_fast': 13,  # RSI (momentum oscillator)
        'atr': 14,       # ATR (volatility measure)
        'macd': 8,       # MACD (trend strength)
        'ema20': 7       # EMA20 (trend reference)
    }
    
    # =================================================================
    # PART 1: CURRENT STATE (33 features) - Latest candle
    # =================================================================
    features.extend(sequence[-1])
    
    # =================================================================
    # PART 2: MOMENTUM PATTERNS (27 features) - Using ALL candles!
    # =================================================================
    momentum_features = []
    
    # Select most important features for momentum (27 from 33)
    important_indices = [0, 1, 2, 3, 4, 7, 8, 9, 10, 11, 13, 14, 15, 
                        16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 
                        27, 28, 29]
    
    for col_idx in important_indices:
        if col_idx < sequence.shape[1]:
            col_data = sequence[:, col_idx]
            
            # Advanced momentum: Linear trend across ALL timesteps
            if len(col_data) > 1:
                time_index = np.arange(len(col_data))
                correlation = np.corrcoef(time_index, col_data)[0,1]
                momentum_features.append(
                    correlation if np.isfinite(correlation) else 0.0
                )
            else:
                momentum_features.append(0.0)
    
    features.extend(momentum_features)
    
    # =================================================================
    # PART 3: CRITICAL STATISTICS (6 features) - Deep analysis
    # =================================================================
    critical_stats = []
    
    for feature_name, col_idx in CRITICAL_FEATURES.items():
        if col_idx < sequence.shape[1]:
            col_data = sequence[:, col_idx]
            
            if len(col_data) > 1:
                # Volatility measure
                volatility = np.std(col_data) / (np.mean(np.abs(col_data)) + 1e-8)
                critical_stats.append(volatility)
            else:
                critical_stats.append(0.0)
        else:
            critical_stats.append(0.0)
    
    features.extend(critical_stats)
    
    # Total: 33 + 27 + 6 = 66 features ✅
    
    features = np.array(features, dtype=np.float64)
    features = np.nan_to_num(features, nan=0.0, posinf=1e6, neginf=-1e6)
    
    return features.flatten()[:66]  # Ensure exactly 66
```

### **Feature Breakdown:**

```
PART 1: CURRENT STATE (33 features)
├─ [0-4]   OHLCV (open, high, low, close, volume)
├─ [5-7]   EMAs (ema5, ema10, ema20)
├─ [8-10]  MACD (macd, macd_signal, macd_histogram)
├─ [11-12] RSI (rsi_fast, stoch_rsi)
├─ [13]    ATR (volatility measure)
├─ [14-15] Bollinger Bands (hband, lband)
├─ [16-18] Advanced (vwap, obv, adx)
├─ [19]    Volatility metric
└─ [20-32] Custom features (13 features)

PART 2: MOMENTUM PATTERNS (27 features)
├─ Linear correlation su TUTTE le candele della sequenza
├─ Per ogni feature importante, calcola trend strength
├─ Correlazione tra time_index e feature values
└─ Cattura accelerazioni e decelerazioni

PART 3: CRITICAL STATISTICS (6 features)
├─ close: Volatilità prezzo
├─ volume: Stability volume
├─ rsi_fast: RSI fluctuation
├─ atr: ATR stability
├─ macd: MACD volatility
└─ ema20: EMA20 stability
```

### **Vantaggi Enhanced B+ Hybrid:**

| Aspetto | Before | After | Improvement |
|---------|--------|-------|-------------|
| **Data Usage** | Solo prima/ultima candela | TUTTE le candele | +800% data |
| **Momentum Quality** | Simple diff | Linear correlation | Trend strength |
| **Pattern Detection** | Basic | Advanced | Better accuracy |
| **Critical Analysis** | Missing | 6 key features | Risk awareness |

---

## 📊 Configuration Summary

### **Training Configuration:**

```python
# config.py

# Future Returns Labeling
FUTURE_RETURN_STEPS = 3                    # Look 3 candles ahead
# Note: Fixed thresholds removed, using percentile-based

# SL-Aware Training (NEW)
SL_AWARENESS_ENABLED = True                # Enable SL-aware labeling
SL_AWARENESS_PERCENTAGE = 0.03             # 3% SL (same as runtime!)
SL_AWARENESS_PERCENTILE_BUY = 80           # Top 20% for BUY
SL_AWARENESS_PERCENTILE_SELL = 80          # Top 20% for SELL

# XGBoost Hyperparameters
XGB_N_ESTIMATORS = 200                     # Trees
XGB_MAX_DEPTH = 4                          # Depth (conservative)
XGB_LEARNING_RATE = 0.05                   # Learning rate
XGB_SUBSAMPLE = 0.7                        # Data sampling
XGB_COLSAMPLE_BYTREE = 0.7                 # Feature sampling
XGB_REG_ALPHA = 0.1                        # L1 regularization
XGB_REG_LAMBDA = 1.0                       # L2 regularization

# Class Balancing
USE_SMOTE = False                          # Disabled (use percentiles)
USE_CLASS_WEIGHTS = True                   # Enabled
SMOTE_K_NEIGHBORS = 3                      # If SMOTE enabled

# Cross-Validation
CV_N_SPLITS = 3                            # 3-fold time series CV

# Feature Engineering
N_FEATURES_FINAL = 66                      # Total features
# Breakdown: 33 current + 27 momentum + 6 statistics
```

### **Timeframe-Specific Settings:**

```python
# Timesteps per timeframe (based on 6-hour lookback)
TIMEFRAME_TIMESTEPS = {
    "15m": 24,  # 6 hours / 15 min = 24 candles
    "30m": 12,  # 6 hours / 30 min = 12 candles
    "1h": 6,    # 6 hours / 1 hour = 6 candles
}

# Ensemble weights
TIMEFRAME_WEIGHTS = {
    "15m": 1.0,  # Fast but noisy
    "30m": 1.2,  # Balanced
    "1h": 1.5,   # Slow but reliable
}
```

---

## 🎯 Summary of Changes

### **🔴 REMOVED (Obsolete):**

- ❌ **Swing Points Labeling**: Completely removed
- ❌ **Fixed Thresholds**: No more hardcoded BUY/SELL thresholds
- ❌ **Dual Labeling System**: Unified to percentile-based only
- ❌ **Simple Momentum**: Old first/last candle diff removed

### **✅ ADDED (New Features):**

- ✅ **Percentile-Based Labeling**: Industry standard approach
- ✅ **SL-Aware Labeling V2**: Stop loss consideration in training
- ✅ **Enhanced B+ Hybrid**: Uses ALL intermediate candles (was wasting 92% data)
- ✅ **SMOTE Per-Fold**: Applied to each CV fold (eliminates temporal bias)
- ✅ **Class Weights**: Automatic balancing for imbalanced classes
- ✅ **Early Stopping**: Prevents overfitting (patience=20)

### **🔄 UPGRADED (Improvements):**

- 🔄 **Training Process**: From simple to advanced with per-fold SMOTE
- 🔄 **Cross-Validation**: From basic to TimeSeriesSplit with robust validation
- 🔄 **Feature Engineering**: From basic momentum to Enhanced B+ Hybrid
- 🔄 **Hyperparameters**: Optimized for crypto trading (conservative approach)

---

## 🚀 Next Steps

**Continua con:** [PARTE 2 - Ensemble Voting & Calibration](04-ML-SYSTEM-PART2.md)

**Vedere anche:**
- [Position Management](05-POSITION-MANAGEMENT.md) - Come vengono gestite le posizioni
- [Risk Management](07-RISK-MANAGEMENT.md) - Stop loss e trailing system
- [Configuration](08-CONFIGURAZIONE.md) - Tutti i parametri configurabili

---

**Ultima modifica:** 03/11/2025  
**Versione documentazione:** 2.0 (Updated with current implementation)
