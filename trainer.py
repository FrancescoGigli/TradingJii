"""
Utility di training per modelli XGBoost.

Il sistema ora usa esclusivamente XGBoost per le previsioni di trading.
Tutto il codice LSTM e RandomForest è stato rimosso per eliminare ridondanze.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.utils import class_weight
import xgboost as xgb
from sklearn.metrics import classification_report, confusion_matrix

import config
from data_utils import prepare_data
from scipy.signal import argrelextrema
from imblearn.over_sampling import SMOTE

_LOG = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Directory modelli
# ----------------------------------------------------------------------
def _trained_dir() -> Path:
    return Path(config.get_xgb_model_file("tmp")).parent

def _ensure_trained_models_dir() -> None:
    _trained_dir().mkdir(exist_ok=True)

# --- wrapper di compatibilità richiesto da main.py --------------------
def ensure_trained_models_dir() -> str:
    """Mantiene la compatibilità con main.py: crea la cartella e ne restituisce il path."""
    _ensure_trained_models_dir()
    return str(_trained_dir())
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# LABELING METHOD: Future Returns Only (Dual labeling removed)
# ----------------------------------------------------------------------
# CRITICAL FIX: Removed swing points labeling to eliminate confusion
# Using only future returns approach for consistency

# ----------------------------------------------------------------------
# Future Returns Labeling (No Lookahead Bias)
# ----------------------------------------------------------------------
def label_with_future_returns(df, lookforward_steps=3, buy_threshold=0.02, sell_threshold=-0.02):
    """
    Etichetta BUY/SELL/NEUTRAL basandosi sui returns futuri SENZA lookahead bias.
    Questo metodo può essere usato per training perché usa dati storici completi.
    
    Args:
        df (pd.DataFrame): DataFrame con dati OHLC
        lookforward_steps (int): Steps nel futuro per calcolare return
        buy_threshold (float): Threshold per label BUY (es. 0.02 = 2%)
        sell_threshold (float): Threshold per label SELL (es. -0.02 = -2%)
        
    Returns:
        np.ndarray: Array di labels [0=SELL, 1=BUY, 2=NEUTRAL]
    """
    labels = np.full(len(df), 2)  # Default = NEUTRAL
    
    try:
        # Calcola returns futuri per ogni punto temporale
        for i in range(len(df) - lookforward_steps):
            current_price = df.iloc[i]['close']
            future_price = df.iloc[i + lookforward_steps]['close']
            
            # Calcola return percentuale
            future_return = (future_price - current_price) / current_price
            
            # Assegna label basato sui threshold
            if future_return >= buy_threshold:
                labels[i] = 1  # BUY
            elif future_return <= sell_threshold:
                labels[i] = 0  # SELL
            # else: rimane NEUTRAL (2)
        
        # Log statistiche future returns
        buy_count = np.sum(labels == 1)
        sell_count = np.sum(labels == 0)
        neutral_count = np.sum(labels == 2)
        total = len(labels)
        
        _LOG.info(f"Future returns labels: BUY={buy_count} ({buy_count/total*100:.1f}%), SELL={sell_count} ({sell_count/total*100:.1f}%), NEUTRAL={neutral_count} ({neutral_count/total*100:.1f}%)")
        
    except Exception as e:
        _LOG.error(f"Errore nel calcolo future returns: {e}")
        # Fallback: tutto NEUTRAL
        labels = np.full(len(df), 2)
    
    return labels

# ----------------------------------------------------------------------
# XGBOOST TRAINING
# ----------------------------------------------------------------------

def _train_xgb_sync_improved(X, y):
    """
    Versione migliorata del training XGBoost che risolve i problemi critici:
    1. Cross-validation robusta su tutti i fold
    2. Class balancing con SMOTE e class weights
    3. Hyperparameters ottimizzati
    4. Early stopping
    """
    _LOG.info("🔧 Preparazione dati per XGBoost training (versione migliorata)...")
    
    # Preprocessing
    scaler = StandardScaler().fit(X)
    X_scaled = scaler.transform(X)
    
    _LOG.info(f"📊 Dataset shape: {X_scaled.shape} samples, {X_scaled.shape[1]} features")
    
    # Log distribuzione classi prima del balancing
    unique, counts = np.unique(y, return_counts=True)
    _LOG.info("📈 Distribuzione classi originale:")
    for cls, count in zip(unique, counts):
        cls_name = {0: 'SELL', 1: 'BUY', 2: 'NEUTRAL'}[cls]
        _LOG.info(f"   {cls_name}: {count} ({count/len(y)*100:.1f}%)")

    # ======= Class Balancing con SMOTE =======
    if config.USE_SMOTE and len(np.unique(y)) > 1:
        _LOG.info("🔄 Applicando SMOTE per class balancing...")
        try:
            smote = SMOTE(
                k_neighbors=config.SMOTE_K_NEIGHBORS, 
                random_state=42,
                sampling_strategy='auto'  # Bilancia automaticamente tutte le classi minoritarie
            )
            X_balanced, y_balanced = smote.fit_resample(X_scaled, y)
            X_scaled, y = X_balanced, y_balanced
            
            # Log distribuzione post-SMOTE
            unique_post, counts_post = np.unique(y, return_counts=True)
            _LOG.info("📈 Distribuzione classi post-SMOTE:")
            for cls, count in zip(unique_post, counts_post):
                cls_name = {0: 'SELL', 1: 'BUY', 2: 'NEUTRAL'}[cls]
                _LOG.info(f"   {cls_name}: {count} ({count/len(y)*100:.1f}%)")
                
        except Exception as e:
            _LOG.warning(f"SMOTE fallito: {e}. Continuo senza balancing.")

    # ======= Cross-Validation Robusta =======
    _LOG.info(f"🎯 Inizio cross-validation con {config.CV_N_SPLITS} splits...")
    
    tscv = TimeSeriesSplit(n_splits=config.CV_N_SPLITS)
    cv_scores = []
    best_model = None
    best_score = 0
    
    for fold_idx, (tr_idx, val_idx) in enumerate(tscv.split(X_scaled)):
        _LOG.info(f"📊 Fold {fold_idx + 1}/{config.CV_N_SPLITS}")
        
        X_tr, X_val = X_scaled[tr_idx], X_scaled[val_idx]
        y_tr, y_val = y[tr_idx], y[val_idx]
        
        # Calcola class weights se abilitato
        sample_weight = None
        if config.USE_CLASS_WEIGHTS:
            class_weights = class_weight.compute_class_weight(
                'balanced', classes=np.unique(y_tr), y=y_tr
            )
            class_weight_dict = {i: class_weights[i] for i in range(len(class_weights))}
            sample_weight = np.array([class_weight_dict[cls] for cls in y_tr])
        
        # Modello con parametri ottimizzati
        model = xgb.XGBClassifier(
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
            verbosity=0,  # Silenzioso per CV
            random_state=42,
            early_stopping_rounds=20
        )
        
        # Training con early stopping
        model.fit(
            X_tr, y_tr,
            eval_set=[(X_val, y_val)],
            sample_weight=sample_weight,
            verbose=False
        )
        
        # Valutazione fold
        y_pred = model.predict(X_val)
        fold_score = accuracy_score(y_val, y_pred)
        cv_scores.append(fold_score)
        
        _LOG.info(f"   Fold {fold_idx + 1} Accuracy: {fold_score:.4f}")
        
        # Salva il miglior modello
        if fold_score > best_score:
            best_score = fold_score
            best_model = model

    # ======= Risultati Cross-Validation =======
    cv_mean = np.mean(cv_scores)
    cv_std = np.std(cv_scores)
    _LOG.info("🏆 Risultati Cross-Validation:")
    _LOG.info(f"   📊 CV Accuracy: {cv_mean:.4f} ± {cv_std:.4f}")
    _LOG.info(f"   🥇 Best Fold Score: {best_score:.4f}")

    # ======= Final Evaluation sul Best Model =======
    # Usa l'ultimo split per evaluation finale
    final_tr_idx, final_val_idx = list(tscv.split(X_scaled))[-1]
    X_final_tr, X_final_val = X_scaled[final_tr_idx], X_scaled[final_val_idx]
    y_final_tr, y_final_val = y[final_tr_idx], y[final_val_idx]
    
    # Re-train il modello sui dati finali con i parametri del best model
    final_sample_weight = None
    if config.USE_CLASS_WEIGHTS:
        final_class_weights = class_weight.compute_class_weight(
            'balanced', classes=np.unique(y_final_tr), y=y_final_tr
        )
        final_class_weight_dict = {i: final_class_weights[i] for i in range(len(final_class_weights))}
        final_sample_weight = np.array([final_class_weight_dict[cls] for cls in y_final_tr])
    
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
    
    _LOG.info("🚀 Training final XGBoost model...")
    _LOG.info(f"   📝 Parametri ottimizzati: n_estimators={config.XGB_N_ESTIMATORS}, max_depth={config.XGB_MAX_DEPTH}, lr={config.XGB_LEARNING_RATE}")
    
    final_model.fit(
        X_final_tr, y_final_tr,
        eval_set=[(X_final_val, y_final_val)],
        sample_weight=final_sample_weight,
        verbose=True
    )
    
    _LOG.info("✅ Final training XGBoost completato!")
    
    # Valutazione dettagliata finale
    y_pred_final = final_model.predict(X_final_val)
    y_pred_proba = final_model.predict_proba(X_final_val)
    
    # Metriche dettagliate
    m = {
        "val_accuracy":  accuracy_score(y_final_val, y_pred_final),
        "val_precision": precision_score(y_final_val, y_pred_final, average="weighted"),
        "val_recall":    recall_score(y_final_val, y_pred_final, average="weighted"),
        "val_f1":        f1_score(y_final_val, y_pred_final, average="weighted"),
        "cv_mean_accuracy": cv_mean,
        "cv_std_accuracy": cv_std,
        "best_fold_score": best_score
    }
    
    _LOG.info("📊 Risultati Final Validation:")
    _LOG.info(f"   🎯 Accuracy:  {m['val_accuracy']:.4f}")
    _LOG.info(f"   🎯 Precision: {m['val_precision']:.4f}")
    _LOG.info(f"   🎯 Recall:    {m['val_recall']:.4f}")
    _LOG.info(f"   🎯 F1-Score:  {m['val_f1']:.4f}")
    
    # Classification report dettagliato
    _LOG.info("📋 Classification Report:")
    class_names = ['SELL', 'BUY', 'NEUTRAL']
    report = classification_report(y_final_val, y_pred_final, target_names=class_names, zero_division=0)
    for line in report.split('\n'):
        if line.strip():
            _LOG.info(f"   {line}")
    
    # Confusion Matrix
    _LOG.info("🔍 Confusion Matrix:")
    cm = confusion_matrix(y_final_val, y_pred_final)
    for i, true_class in enumerate(class_names):
        for j, pred_class in enumerate(class_names):
            _LOG.info(f"   True {true_class} -> Pred {pred_class}: {cm[i,j]}")
    
    # Feature importance (top 15 ora che abbiamo più features)
    try:
        importance = final_model.feature_importances_
        top_features_idx = np.argsort(importance)[-15:][::-1]
        _LOG.info("🏆 Top 15 Feature Importance:")
        for i, idx in enumerate(top_features_idx):
            feature_name = config.EXPECTED_COLUMNS[idx] if idx < len(config.EXPECTED_COLUMNS) else f"Feature_{idx}"
            _LOG.info(f"   {i+1}. {feature_name}: {importance[idx]:.4f}")
    except Exception as e:
        _LOG.warning(f"Non riesco a calcolare feature importance: {e}")
    
    # Return also visualization data
    return final_model, scaler, m, y_final_val, y_pred_final, y_pred_proba

# ----------------------------------------------------------------------
# WRAPPER TRAINING - DUAL MODE LABELING
# ----------------------------------------------------------------------
async def train_xgboost_model_wrapper(top_symbols, exchange, timestep, timeframe, use_future_returns=False):
    """
    Wrapper per training XGBoost con dual-mode labeling.
    
    FIXED: Now uses fetch_and_save_data instead of get_data_async to get data with indicators
    
    Args:
        use_future_returns (bool): Se True, usa future returns. Se False, usa swing points.
    """
    from fetcher import fetch_and_save_data

    X_all, y_all = [], []
    
    labeling_method = "future returns" if use_future_returns else "swing points"
    _LOG.info(f"🎯 Training XGBoost con {labeling_method} labeling per {timeframe}")
    
    successful_symbols = 0
    for sym in top_symbols:
        try:
            # CRITICAL FIX: Use fetch_and_save_data to get data WITH indicators
            df_with_indicators = await fetch_and_save_data(exchange, sym, timeframe)
            if df_with_indicators is None:
                _LOG.warning(f"No data returned for {sym} {timeframe}")
                continue
            
            # Prepare data for ML (convert to numpy with expected columns)
            data = prepare_data(df_with_indicators)
            if not np.isfinite(data).all() or len(data) < timestep + config.FUTURE_RETURN_STEPS:
                _LOG.warning(f"Invalid or insufficient data for {sym}: shape={data.shape}, finite={np.isfinite(data).all()}")
                continue
                
            successful_symbols += 1
            _LOG.info(f"✅ Processing {sym} ({successful_symbols}/{len(top_symbols)}): {data.shape[0]} samples")
            
            # ======= UNIFIED LABELING: Only Future Returns =======
            # FIXED: Removed dual mode, using only future returns for consistency
            labels = label_with_future_returns(
                df_with_indicators,
                lookforward_steps=config.FUTURE_RETURN_STEPS,
                buy_threshold=config.RETURN_BUY_THRESHOLD,
                sell_threshold=config.RETURN_SELL_THRESHOLD
            )
            
            # ======= TEMPORAL FEATURE PRESERVATION =======
            # Create temporal features from prepared data
            for i in range(timestep, len(data) - config.FUTURE_RETURN_STEPS):
                if i < len(labels):
                    # Sequence di timestep frames
                    sequence = data[i - timestep : i]
                    
                    # Crea features temporali strutturate invece del semplice flattening
                    temporal_features = create_temporal_features(sequence)
                    
                    X_all.append(temporal_features)
                    y_all.append(labels[i])
                    
        except Exception as e:
            _LOG.error(f"Errore processing {sym}: {e}")
            continue

    _LOG.info(f"💾 Total samples collected: {len(X_all)} from {successful_symbols} symbols")

    if not X_all:
        _LOG.error(f"❌ No valid training data for {timeframe} - check data quality or threshold settings")
        return None, None, None

    # Converti in numpy arrays
    X_all = np.array(X_all)
    y_all = np.array(y_all)
    
    # Log distribuzione finale delle classi
    unique, counts = np.unique(y_all, return_counts=True)
    class_distribution = {int(cls): int(count) for cls, count in zip(unique, counts)}
    total_samples = len(y_all)
    _LOG.info(f"📊 Distribuzione classi finale per {timeframe}: {class_distribution}")
    for cls, count in class_distribution.items():
        cls_name = {0: 'SELL', 1: 'BUY', 2: 'NEUTRAL'}[cls]
        _LOG.info(f"   {cls_name}: {count} ({count/total_samples*100:.1f}%)")

    # USA LA FUNZIONE MIGLIORATA
    model, scaler, metrics, y_final_val, y_pred_final, y_pred_proba = _train_xgb_sync_improved(X_all, y_all)

    _ensure_trained_models_dir()
    joblib.dump(model,  config.get_xgb_model_file(timeframe))
    joblib.dump(scaler, config.get_xgb_scaler_file(timeframe))
    Path(config.get_xgb_model_file(timeframe)).with_suffix(".json").write_text(json.dumps(metrics, indent=4))
    
    # ======= AUTOMATIC VISUALIZATION SAVE =======
    # Save comprehensive training metrics as images
    try:
        from core.visualization import save_training_metrics
        
        # Prepare feature names for visualization
        feature_names = []
        for i in range(len(config.EXPECTED_COLUMNS)):
            feature_names.append(f"current_{config.EXPECTED_COLUMNS[i]}")
        for i in range(len(config.EXPECTED_COLUMNS)):
            feature_names.append(f"trend_{config.EXPECTED_COLUMNS[i]}")
        
        # Generate comprehensive training visualizations
        # FIXED: Use correct variable names from the training function
        viz_path = save_training_metrics(
            y_true=y_final_val,
            y_pred=y_pred_final, 
            y_prob=y_pred_proba,
            feature_importance=model.feature_importances_,  # FIXED: Use 'model' from current scope
            feature_names=feature_names,
            timeframe=timeframe,
            metrics=metrics  # FIXED: Use 'metrics' from current scope
        )
        
        if viz_path:
            _LOG.info(f"📊 Training visualization saved: {viz_path}")
            _LOG.info(f"📂 Chart location: visualizations/training/")
        
    except Exception as viz_error:
        _LOG.warning(f"Failed to create training visualization: {viz_error}")
        _LOG.info(f"📊 Charts will be saved to: visualizations/training/training_metrics_{timeframe}_[timestamp].png")
    
    _LOG.info(f"🎉 XGBoost model per {timeframe} salvato con successo!")
    return model, scaler, metrics

def create_temporal_features(sequence):
    """
    SIMPLIFIED temporal features to fix dimensionality explosion.
    
    BEFORE: 7 timesteps * 34 features * 7 operations = 1,666 features! 
    AFTER: Only essential features for trading signals (~68 features max)
    
    Args:
        sequence (np.ndarray): Sequenza di shape (timesteps, features)
        
    Returns:
        np.ndarray: Compact temporal features
    """
    try:
        features = []
        
        # 1. CURRENT STATE: Most recent values (most important for trading)
        features.extend(sequence[-1])  # Latest candle: 34 features
        
        # 2. TREND: Simple trend indicators (price momentum)  
        if len(sequence) > 1:
            # Price change from first to last
            price_change = (sequence[-1] - sequence[0]) / (np.abs(sequence[0]) + 1e-8)
            features.extend(price_change)  # Trend direction: 34 features
        else:
            features.extend(np.zeros(sequence.shape[1]))
        
        # TOTAL: ~68 features (34 current + 34 trend) instead of 1600+
        # This is manageable for XGBoost with 100 estimators
        
        # Clean and validate
        features = np.array(features, dtype=np.float64)
        features = np.nan_to_num(features, nan=0.0, posinf=1e6, neginf=-1e6)
        
        return features.flatten()
        
    except Exception as e:
        _LOG.error(f"Error in create_temporal_features: {e}")
        # Emergency fallback: just use last timestep
        return np.nan_to_num(sequence[-1].flatten(), nan=0.0, posinf=0.0, neginf=0.0)
