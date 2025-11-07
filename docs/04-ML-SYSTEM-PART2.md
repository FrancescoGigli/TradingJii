# 🤖 04 - ML Prediction System (PARTE 2/2)

Ensemble voting, confidence calibration, e real-time predictions.

**Parte 1:** [Training & Feature Engineering](04-ML-SYSTEM-PART1.md)

---

## 📋 Indice Parte 2

1. [Ensemble Voting Multi-Timeframe](#ensemble-voting-multi-timeframe)
2. [Confidence Calibration](#confidence-calibration)
3. [Real-Time Prediction Flow](#real-time-prediction-flow)
4. [Performance Analysis](#performance-analysis)

---

## 🎯 Ensemble Voting Multi-Timeframe

### **Complete Ensemble Logic:**

```python
def predict_signal_ensemble(dataframes, xgb_models, xgb_scalers, symbol, time_steps):
    """
    Multi-timeframe ensemble prediction
    
    PROCESS:
    1. Per ogni timeframe (15m, 30m, 1h):
       - Create 66 features
       - Predict con XGBoost → probabilities
       - Get prediction class + confidence
    
    2. Weighted voting:
       - 15m weight = 1.0 (fast but noisy)
       - 30m weight = 1.2 (balanced)
       - 1h weight = 1.5 (slow but reliable)
    
    3. Majority vote con weights
    4. Calibrate final confidence
    
    Returns:
        ensemble_confidence: float (calibrated win rate)
        final_signal: int (0=SELL, 1=BUY, 2=NEUTRAL)
        tf_predictions: dict {timeframe: prediction}
    """
    from config import TIMEFRAME_WEIGHTS
    
    predictions = {}
    confidences = {}
    probabilities = {}
    
    # ============================================================
    # STEP 1: Predict per ogni timeframe
    # ============================================================
    
    for tf, df in dataframes.items():
        if tf not in xgb_models or xgb_models[tf] is None:
            logging.debug(f"⚠️ {symbol}: No model for {tf}, skipping")
            continue
        
        try:
            # 1. Get timestep for this timeframe
            timestep = time_steps.get(tf, 24)
            
            # 2. Extract sequence (last N candles)
            if len(df) < timestep:
                logging.warning(f"⚠️ {symbol}[{tf}]: Insufficient data ({len(df)} < {timestep})")
                continue
            
            sequence = df.iloc[-timestep:].values[:, :33]  # Solo primi 33 indicatori
            
            # 3. Create temporal features
            features = create_temporal_features(sequence, timestep)
            
            # 4. Scale features
            X_scaled = xgb_scalers[tf].transform(features.reshape(1, -1))
            
            # 5. Predict con XGBoost
            probs = xgb_models[tf].predict_proba(X_scaled)[0]
            # probs = [prob_SELL, prob_BUY, prob_NEUTRAL]
            
            prediction = np.argmax(probs)  # Classe con probabilità massima
            confidence = np.max(probs)     # Probabilità della classe predetta
            
            # Store
            predictions[tf] = prediction
            confidences[tf] = confidence
            probabilities[tf] = probs
            
            logging.debug(f"  {tf}: pred={prediction} ({['SELL','BUY','NEUTRAL'][prediction]}), "
                         f"conf={confidence:.3f}, probs={probs}")
            
        except Exception as e:
            logging.error(f"❌ {symbol}[{tf}]: Prediction failed - {e}")
            continue
    
    # Check if we have predictions
    if not predictions:
        logging.warning(f"⚠️ {symbol}: No valid predictions")
        return None, None, {}
    
    # ============================================================
    # STEP 2: Weighted Ensemble Voting
    # ============================================================
    
    weighted_votes = {0: 0.0, 1: 0.0, 2: 0.0}  # {class: total_weight}
    total_weight = 0.0
    
    for tf, pred in predictions.items():
        # Get confidence for this prediction
        conf = confidences.get(tf, 0.5)
        
        # Get timeframe weight from config
        tf_weight = TIMEFRAME_WEIGHTS.get(tf, 1.0)
        
        # Combined weight = confidence × timeframe_importance
        combined_weight = conf * tf_weight
        
        # Accumulate vote
        weighted_votes[pred] += combined_weight
        total_weight += combined_weight
        
        logging.debug(f"  {tf}: pred={pred}, conf={conf:.3f}, "
                     f"tf_weight={tf_weight}, combined={combined_weight:.3f}")
    
    # Get winner (class with highest weight)
    final_signal = max(weighted_votes.items(), key=lambda x: x[1])[0]
    final_weight = weighted_votes[final_signal]
    
    # Calculate raw ensemble confidence
    raw_ensemble_confidence = final_weight / total_weight if total_weight > 0 else 0.0
    
    logging.debug(f"  Weighted votes: {weighted_votes}")
    logging.debug(f"  Winner: {final_signal} ({['SELL','BUY','NEUTRAL'][final_signal]})")
    logging.debug(f"  Raw confidence: {raw_ensemble_confidence:.3f}")
    
    # ============================================================
    # STEP 3: Confidence Calibration
    # ============================================================
    
    from core.confidence_calibrator import global_calibrator
    
    if global_calibrator and hasattr(global_calibrator, 'calibrate_xgb_confidence'):
        calibrated_confidence = global_calibrator.calibrate_xgb_confidence(
            raw_ensemble_confidence
        )
        logging.debug(f"  Calibrated confidence: {calibrated_confidence:.3f}")
    else:
        calibrated_confidence = raw_ensemble_confidence
    
    return calibrated_confidence, final_signal, predictions


# Timeframe weights config
TIMEFRAME_WEIGHTS = {
    '15m': 1.0,  # Fast signals, meno stabili
    '30m': 1.2,  # Medium signals, più equilibrati
    '1h': 1.5    # Slow signals, più affidabili
}
```

### **Esempio Pratico:**

```
Symbol: SOL/USDT:USDT

Individual Predictions:
├─ 15m: BUY (conf: 0.72) → weight = 0.72 × 1.0 = 0.72
├─ 30m: BUY (conf: 0.78) → weight = 0.78 × 1.2 = 0.94
└─ 1h:  BUY (conf: 0.85) → weight = 0.85 × 1.5 = 1.28

Weighted Voting:
├─ SELL votes:    0.00
├─ BUY votes:     0.72 + 0.94 + 1.28 = 2.94
├─ NEUTRAL votes: 0.00
└─ Total weight:  2.94

Winner: BUY
Raw confidence: 2.94 / 2.94 = 1.00 (100%)

After calibration: 0.85 (85% expected win rate)
```

---

## 📊 Confidence Calibration

### **Why Calibration?**

```
Problem:
├─ XGBoost dà confidence "raw" (probabilità classe)
├─ Raw confidence ≠ real win rate
├─ Esempio: 100% confidence raw → solo 85% win rate real
└─ Need mapping: raw → real expected win rate

Solution:
├─ Analizza 4051 trade storici
├─ Calcola win rate per ogni bin di confidence
├─ Create isotonic regression mapping
└─ Result: calibrated confidence = expected win rate
```

### **Calibrator Implementation:**

```python
class XGBConfidenceCalibrator:
    """
    Calibra confidence XGBoost su real win rates
    
    DATA: 4051 trade storici con:
    - raw_confidence (da XGBoost)
    - actual_outcome (WIN/LOSS)
    
    OUTPUT: Mapping raw → calibrated confidence
    """
    
    def __init__(self):
        self.isotonic_regressor = None
        self.calibration_data = None
        self.is_calibrated = False
    
    def calibrate_from_trades(self, trade_history_df):
        """
        Calibrate usando trade history
        
        Args:
            trade_history_df: DataFrame con columns:
                - 'raw_confidence': float (0
