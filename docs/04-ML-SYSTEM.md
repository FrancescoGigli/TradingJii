# 📖 04 - Sistema Machine Learning (XGBoost)

> **Predizioni multi-timeframe con ensemble voting**

---

## 🤖 Overview Sistema ML

Il bot utilizza **XGBoost** (Gradient Boosting) per predire movimenti di prezzo su **3 timeframes** simultaneamente, combinando le predizioni con **ensemble voting pesato**.

```
ML PREDICTION PIPELINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INPUT: OHLCV Data (6 ore lookback)
  ↓
STEP 1: Technical Indicators (35 raw features)
  • EMAs, MACD, RSI, ADX, ATR, Bollinger, VWAP, OBV
  ↓
STEP 2: Feature Engineering (66 temporal features)
  • Current state (33)
  • Momentum indicators (27)
  • Critical stats (6)
  ↓
STEP 3: Scaling (StandardScaler per timeframe)
  ↓
STEP 4: XGBoost Prediction (per timeframe)
  • 15m model → prediction + confidence
  • 30m model → prediction + confidence
  • 1h model → prediction + confidence
  ↓
STEP 5: Ensemble Voting (weighted by timeframe)
  • Weights: 15m=1.0, 30m=1.2, 1h=1.5
  • Unanimous → Strong signal
  • Majority → Moderate signal
  • Mixed → NEUTRAL (skip)
  ↓
STEP 6: Confidence Calibration
  • Volatility adjustment (-15% if high)
  • Trend strength (-10% if ADX<25)
  • Market filter (optional -20%)
  ↓
OUTPUT: Final signal + confidence
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 📊 Feature Engineering (66 Features)

### **1. Current State Features (33)**

```python
# Moving Averages
'ema5', 'ema10', 'ema20'

# Momentum
'macd', 'macd_signal', 'macd_histogram'
'rsi_fast', 'stoch_rsi'

# Trend
'adx'

# Volatility
'atr', 'volatility'
'bollinger_hband', 'bollinger_lband'

# Volume
'volume', 'obv', 'vwap'

# Price positions relative to EMAs
'price_pos_5', 'price_pos_10', 'price_pos_20'

# Support/Resistance
'resistance_dist_10', 'resistance_dist_20'
'support_dist_10', 'support_dist_20'
```

### **2. Momentum Features (27)**

```python
# Volume dynamics
'vol_acceleration'      # Rate of volume change
'vol_price_alignment'   # Volume confirms price direction

# Volatility dynamics
'atr_norm_move'        # Price move normalized by ATR
'volatility_squeeze'   # Low volatility before breakout

# Momentum
'momentum_divergence'  # Price vs RSI divergence
'price_acceleration'   # Second derivative of price
```

### **3. Critical Stats (6)**

```python
# Market regime
'trend_strength'       # Combination of ADX + EMA alignment
'market_phase'         # Trending vs ranging detection

# Additional context
'candle_pattern_score' # Bullish/bearish candle patterns
'breakout_proximity'   # Distance from key levels
```

**Total**: 66 numerical features

---

## 🎓 Training Process

### **Step 1: Data Collection**

```python
# Per ogni simbolo nel training set (top 50)
for symbol in training_symbols:
    # Fetch historical data (180 giorni)
    ohlcv = await exchange.fetch_ohlcv(
        symbol, 
        timeframe='15m',
        since=start_date,
        limit=17280  # 180 days × 96 candles/day
    )
```

**Dimensioni Dataset**:
- Simboli: 50 (BTC, ETH inclusi)
- Timespan: 180 giorni
- Candele per simbolo: ~17,000 (15m)
- Total samples: ~850,000 candele

### **Step 2: Labeling (Stop-Loss Aware)**

```python
# CRITICAL: Labels tengono conto di SL hit durante il path
def label_with_sl_awareness(
    df, 
    future_steps=3,  # Guarda 3 candele avanti
    sl_pct=0.05      # -5% SL (aligned con runtime)
):
    for i in range(len(df) - future_steps):
        # Simula cosa succederebbe aprendo trade qui
        entry_price = df.loc[i, 'close']
        
        # Path successivo (3 candele)
        future_prices = df.loc[i+1:i+future_steps+1, 'close']
        
        # Check se SL viene hit
        sl_price = entry_price * (1 - sl_pct)  # BUY example
        sl_hit = any(future_prices <= sl_price)
        
        if sl_hit:
            label = 0  # SELL (evita questo trade)
        else:
            # Calcola return finale
            final_return = (future_prices.iloc[-1] - entry_price) / entry_price
            
            # Label basato su percentile
            if final_return >= percentile_80:
                label = 1  # BUY (top 20% winners)
            elif final_return <= -percentile_80:
                label = 0  # SELL (avoid)
            else:
                label = -1  # NEUTRAL (skip in training)
```

**Vantaggi SL-Aware Labeling**:
- ML impara a evitare trade che triggereranno SL
- Labels allineati con risk management runtime
- Migliora win rate prevenendo false breakouts

### **Step 3: Class Balancing**

```python
# Usa class weights (no SMOTE per velocità)
class_weights = {
    0: 1.2,  # SELL slightly more weight (rarer)
    1: 1.0   # BUY standard weight
}
```

**Distribuzione Tipica**:
- BUY: 42%
- SELL: 38%
- NEUTRAL: 20% (esclusi dal training)

### **Step 4: XGBoost Training**

```python
# Hyperparameters ottimizzati
xgb_params = {
    'n_estimators': 200,
    'max_depth': 4,
    'learning_rate': 0.05,
    'subsample': 0.7,
    'colsample_bytree': 0.7,
    'reg_alpha': 0.1,      # L1 regularization
    'reg_lambda': 1.0,     # L2 regularization
    'scale_pos_weight': 1.0
}

model = XGBClassifier(**xgb_params)
model.fit(X_train, y_train, sample_weight=weights)
```

### **Step 5: Validation (3-Fold CV)**

```python
from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=3)
scores = cross_val_score(
    model, X, y, 
    cv=tscv, 
    scoring='f1_weighted'
)
```

**Metriche Target**:
- Accuracy: >65%
- Precision: >0.70
- Recall: >0.65
- F1: >0.67

### **Step 6: Model Persistence**

```python
import joblib

# Salva model + scaler
joblib.dump(model, f'trained_models/xgb_model_{tf}.pkl')
joblib.dump(scaler, f'trained_models/xgb_scaler_{tf}.pkl')
```

**Files Generati**:
```
trained_models/
├── xgb_model_15m.pkl
├── xgb_scaler_15m.pkl
├── xgb_model_30m.pkl
├── xgb_scaler_30m.pkl
├── xgb_model_1h.pkl
└── xgb_scaler_1h.pkl
```

---

## 🔮 Runtime Prediction

### **Step 1: Data Preparation**

```python
# Fetch latest candles
df = await fetch_ohlcv(symbol, timeframe, limit=24)  # 6h lookback

# Calculate indicators
df = add_technical_indicators(df)

# Engineer features
features = create_temporal_features(df)

# Get only last row (current state)
X = features.iloc[[-1]]  # Shape: (1, 66)
```

### **Step 2: Scaling**

```python
# Load scaler per timeframe
scaler = joblib.load(f'trained_models/xgb_scaler_{tf}.pkl')

# Transform
X_scaled = scaler.transform(X)
```

### **Step 3: Prediction**

```python
# Load model
model = joblib.load(f'trained_models/xgb_model_{tf}.pkl')

# Predict
prediction = model.predict(X_scaled)[0]  # 0 or 1
probabilities = model.predict_proba(X_scaled)[0]  # [prob_0, prob_1]

# Extract confidence
if prediction == 1:  # BUY
    confidence = probabilities[1]
else:  # SELL
    confidence = probabilities[0]
```

**Output per TF**:
```python
{
    'timeframe': '15m',
    'prediction': 1,  # BUY
    'confidence': 0.72,
    'signal_name': 'BUY'
}
```

---

## 🎯 Ensemble Voting

### **Weighted Combination**

```python
def calculate_ensemble(tf_predictions):
    """
    Combina predizioni multi-timeframe con pesi
    """
    weights = {
        '15m': 1.0,
        '30m': 1.2,
        '1h': 1.5
    }
    
    buy_score = 0
    sell_score = 0
    total_weight = 0
    
    for tf, pred_data in tf_predictions.items():
        weight = weights[tf]
        confidence = pred_data['confidence']
        
        if pred_data['prediction'] == 1:  # BUY
            buy_score += weight * confidence
        else:  # SELL
            sell_score += weight * confidence
        
        total_weight += weight
    
    # Normalize
    buy_score /= total_weight
    sell_score /= total_weight
    
    # Decide
    if buy_score > sell_score:
        return 'BUY', buy_score
    elif sell_score > buy_score:
        return 'SELL', sell_score
    else:
        return 'NEUTRAL', max(buy_score, sell_score)
```

### **Esempi Ensemble**

**Caso 1: Unanime (Strong Signal)**
```
15m: BUY 72% × 1.0 = 0.720
30m: BUY 78% × 1.2 = 0.936
1h:  BUY 81% × 1.5 = 1.215
────────────────────────────
Total weight: 3.7
Buy score: 2.871 / 3.7 = 77.6%
Sell score: 0

→ BUY 77.6% (STRONG)
```

**Caso 2: Maggioranza (Moderate)**
```
15m: BUY 68% × 1.0 = 0.680
30m: BUY 71% × 1.2 = 0.852
1h:  SELL 65% × 1.5 = 0.975
────────────────────────────
Buy score: 1.532 / 3.7 = 41.4%
Sell score: 0.975 / 3.7 = 26.4%

→ BUY 41.4% (filtered out: <65%)
```

**Caso 3: Misto (Skip)**
```
15m: BUY 70% × 1.0 = 0.700
30m: SELL 73% × 1.2 = 0.876
1h:  BUY 68% × 1.5 = 1.020
────────────────────────────
Buy score: 1.720 / 3.7 = 46.5%
Sell score: 0.876 / 3.7 = 23.7%

→ Conflitto → NEUTRAL (skip)
```

---

## 🎚️ Confidence Calibration

### **Adjustment Factors**

```python
def calibrate_confidence(confidence, market_data):
    """
    Aggiusta confidence basandosi su condizioni mercato
    """
    adjusted = confidence
    
    # 1. Volatility adjustment
    if market_data.volatility > 0.04:  # >4% ATR
        adjusted *= 0.85  # -15%
        logging.debug("High volatility: -15%")
    
    # 2. Trend strength
    if market_data.adx < 25:
        adjusted *= 0.90  # -10%
        logging.debug("Weak trend (ADX<25): -10%")
    
    # 3. Market filter (optional)
    if MARKET_FILTER_ENABLED and btc_downtrend:
        adjusted *= 0.80  # -20%
        logging.debug("BTC downtrend: -20%")
    
    return adjusted
```

### **Esempi Calibration**

```
Original: 77% confidence (ensemble BUY)

Scenario A (Normal): 
  • Volatility: 2.5% (normal)
  • ADX: 28 (strong trend)
  • BTC: neutral
  → Final: 77% × 1.0 = 77% ✓

Scenario B (Volatile):
  • Volatility: 5.2% (high)  → -15%
  • ADX: 32 (strong)
  • BTC: neutral
  → Final: 77% × 0.85 = 65.5% ✓

Scenario C (Weak + Volatile):
  • Volatility: 4.8% (high)  → -15%
  • ADX: 21 (weak)          → -10%
  • BTC: neutral
  → Final: 77% × 0.85 × 0.90 = 58.9% ❌ (filtered: <65%)
```

---

## 📈 Performance Metriche

### **Training Metrics (Tipiche)**

```
TIMEFRAME: 15m
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Accuracy:      68.5%
Precision:     0.72 (BUY), 0.70 (SELL)
Recall:        0.65 (BUY), 0.68 (SELL)
F1 Score:      0.68
ROC AUC:       0.73
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TIMEFRAME: 30m
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Accuracy:      70.2%
Precision:     0.74 (BUY), 0.71 (SELL)
Recall:        0.68 (BUY), 0.70 (SELL)
F1 Score:      0.71
ROC AUC:       0.76
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TIMEFRAME: 1h
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Accuracy:      71.8%
Precision:     0.76 (BUY), 0.73 (SELL)
Recall:        0.70 (BUY), 0.72 (SELL)
F1 Score:      0.73
ROC AUC:       0.78
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ENSEMBLE (Weighted)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Effective Accuracy:  73-75%
Win Rate (Live):     55-60%
Sharpe Ratio:        1.8-2.2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### **Feature Importance (Top 10)**

```python
# XGBoost feature importance
importance_scores = model.get_booster().get_score(importance_type='weight')

Top Features:
  1. rsi_fast          (12.5%)
  2. adx               (11.2%)
  3. macd_histogram    (9.8%)
  4. ema20             (8.5%)
  5. atr_norm_move     (7.3%)
  6. vol_acceleration  (6.9%)
  7. price_pos_20      (6.1%)
  8. volatility        (5.8%)
  9. momentum_div      (5.2%)
 10. stoch_rsi         (4.9%)
```

---

## 🔬 Model Retraining

### **Quando Retrainare**

1. **Scheduled**: Ogni 30 giorni
2. **Performance drop**: Win rate <50% per 20+ trades
3. **Market regime change**: BTC volatility >2x media
4. **New symbols**: Aggiunti nuovi top volume coins

### **Retraining Process**

```bash
# Manual retraining
python trainer.py --timeframe all --force

# Output:
🎯 Retraining all models...
  • Fetching fresh data (180 days)
  • Features: 66 temporal
  • Samples: 850,000+
  • Training 15m... ✓ (3min)
  • Training 30m... ✓ (3min)
  • Training 1h... ✓ (3min)
  • Validation: 3-fold CV
  • Saving models...
✅ Retraining complete (10min)
```

---

## 💡 Best Practices

### **DO ✅**
- Mantieni lookback uniforme (6 ore) per consistency
- Usa SL-aware labeling allineato con runtime
- Valida con time series split (no random)
- Monitora feature importance per drift detection
- Retrain periodicamente (30 giorni)

### **DON'T ❌**
- Non usare future data (lookahead bias)
- Non oversample con SMOTE (distorce time series)
- Non ignorare class imbalance
- Non usare troppi features (overfitting)
- Non testare su dati di training

---

## 📚 Next Steps

- **05-ADAPTIVE-SIZING.md** - Kelly Criterion per optimal sizing
- **06-RISK-MANAGEMENT.md** - SL, early exit, partial profits

---

**🎯 KEY TAKEAWAY**: L'ensemble multi-timeframe con SL-aware labeling crea predizioni robuste che bilanciano accuracy con risk management pratico.
