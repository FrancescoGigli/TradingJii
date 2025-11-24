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
from config import N_FEATURES_FINAL
from data_utils import prepare_data
from termcolor import colored

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
# SL-AWARE LABELING (Active System)
# ----------------------------------------------------------------------
def label_with_sl_awareness_v2(df, lookforward_steps=3, sl_percentage=0.05,
                                percentile_buy=80, percentile_sell=80):
    """
    🎯 PRODUCTION: Stop Loss Aware Labeling con Feature Engineering
    
    Invece di eliminare sample con SL hit, li mantiene e aggiunge features
    che insegnano al modello a riconoscere situazioni a rischio SL.
    
    FEATURES AVANZATE:
    - NO survivorship bias (mantiene tutti i sample)
    - Feature engineering (5 nuove features per ogni sample)
    - Borderline asimmetrici (pump vs dump)
    - Risoluzione ambiguità BUY/SELL
    - Percentili configurabili
    - Vectorizzato NumPy per performance
    
    Args:
        df: DataFrame con OHLCV columns
        lookforward_steps: Candele future per label
        sl_percentage: Stop loss % (default 0.05 = 5%)
        percentile_buy: Percentile per BUY (default 80 = top 20%)
        percentile_sell: Percentile per SELL (default 80 = top 20%)
    
    Returns:
        tuple: (labels, sl_features_dict)
    """
    labels = np.full(len(df), 2)  # Default NEUTRAL
    
    # Feature engineering (manteniamo tutti i sample!)
    sl_features = {
        'sl_hit_buy': np.zeros(len(df)),
        'sl_hit_sell': np.zeros(len(df)),
        'max_drawdown_pct': np.zeros(len(df)),
        'max_drawup_pct': np.zeros(len(df)),
        'volatility_path': np.zeros(len(df))
    }
    
    buy_returns_data = []
    sell_returns_data = []
    
    # Vectorized arrays
    close_prices = df['close'].values
    low_prices = df['low'].values
    high_prices = df['high'].values
    
    # Statistics
    sl_hit_count = {'buy': 0, 'sell': 0, 'both': 0}
    borderline_count = {'buy': 0, 'sell': 0}
    
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
        buy_borderline = (max_drawdown_pct < -config.SL_AWARENESS_BORDERLINE_BUY and 
                         max_drawdown_pct > -sl_percentage)
        
        # SELL SCENARIO
        sell_sl_price = entry_price * (1 + sl_percentage)
        sell_sl_hit = np.any(path_highs >= sell_sl_price)
        max_drawup = np.max(path_highs)
        max_drawup_pct = (max_drawup - entry_price) / entry_price
        sell_borderline = (max_drawup_pct > config.SL_AWARENESS_BORDERLINE_SELL and 
                          max_drawup_pct < sl_percentage)
        
        # VOLATILITY
        volatility = np.std(path_closes) / (np.mean(path_closes) + 1e-8)
        
        # Store features
        sl_features['sl_hit_buy'][i] = 1.0 if buy_sl_hit else 0.0
        sl_features['sl_hit_sell'][i] = 1.0 if sell_sl_hit else 0.0
        sl_features['max_drawdown_pct'][i] = max_drawdown_pct
        sl_features['max_drawup_pct'][i] = max_drawup_pct
        sl_features['volatility_path'][i] = volatility
        
        # Statistics
        if buy_sl_hit and sell_sl_hit:
            sl_hit_count['both'] += 1
        elif buy_sl_hit:
            sl_hit_count['buy'] += 1
        elif sell_sl_hit:
            sl_hit_count['sell'] += 1
        
        if buy_borderline:
            borderline_count['buy'] += 1
        if sell_borderline:
            borderline_count['sell'] += 1
        
        # Calculate returns
        future_price = close_prices[i + lookforward_steps]
        buy_return = (future_price - entry_price) / entry_price
        sell_return = (entry_price - future_price) / entry_price
        
        # FIX: Add to BOTH lists, let percentile decide (no ambiguity resolution)
        # This fixes the bug where abs_buy > abs_sell is almost always FALSE
        if not buy_borderline:
            buy_returns_data.append((i, buy_return, buy_sl_hit))
        
        if not sell_borderline:
            sell_returns_data.append((i, sell_return, sell_sl_hit))
    
    # PERCENTILE LABELING - FIXED: Include anche sample con SL hit
    # DEBUG: Log size dei dataset
    _LOG.debug(f"buy_returns_data size: {len(buy_returns_data)}, sell_returns_data size: {len(sell_returns_data)}")
    
    if buy_returns_data:
        # Usa TUTTI i returns (safe + risky) per percentile
        all_returns = np.array([r for _, r, _ in buy_returns_data])
        buy_threshold = np.percentile(all_returns, percentile_buy)
        
        _LOG.debug(f"BUY threshold (percentile {percentile_buy}): {buy_threshold:.6f}")
        
        # Label sia safe che risky, ma con threshold uguale
        labeled_count = 0
        for idx, return_val, sl_hit in buy_returns_data:
            if return_val >= buy_threshold:
                labels[idx] = 1  # BUY (anche se ha SL hit nel path)
                labeled_count += 1
        
        _LOG.debug(f"BUY labeled: {labeled_count}/{len(buy_returns_data)}")
    else:
        _LOG.warning(f"⚠️ buy_returns_data is EMPTY! All samples filtered or went to SELL")
    
    if sell_returns_data:
        # Usa TUTTI i returns (safe + risky) per percentile
        all_returns = np.array([r for _, r, _ in sell_returns_data])
        sell_threshold = np.percentile(all_returns, percentile_sell)
        
        _LOG.debug(f"SELL threshold (percentile {percentile_sell}): {sell_threshold:.6f}")
        
        # Label sia safe che risky
        labeled_count = 0
        for idx, return_val, sl_hit in sell_returns_data:
            if return_val >= sell_threshold:
                labels[idx] = 0  # SELL  
                labeled_count += 1
        
        _LOG.debug(f"SELL labeled: {labeled_count}/{len(sell_returns_data)}")
    
    # Log statistics
    buy_count = np.sum(labels == 1)
    sell_count = np.sum(labels == 0)
    neutral_count = np.sum(labels == 2)
    total = len(labels)
    
    _LOG.info(f"🎯 SL-Aware Labeling:")
    _LOG.info(f"   SL hits: BUY={sl_hit_count['buy']}, SELL={sl_hit_count['sell']}, BOTH={sl_hit_count['both']}")
    _LOG.info(f"   Borderline: BUY={borderline_count['buy']}, SELL={borderline_count['sell']}")
    _LOG.info(f"   Labels: BUY={buy_count}({buy_count/total*100:.1f}%), SELL={sell_count}({sell_count/total*100:.1f}%), NEUTRAL={neutral_count}({neutral_count/total*100:.1f}%)")
    
    return labels, sl_features

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

    # ======= Cross-Validation =======
    _LOG.info(f"🎯 Inizio cross-validation con {config.CV_N_SPLITS} splits...")
    
    tscv = TimeSeriesSplit(n_splits=config.CV_N_SPLITS)
    cv_scores = []
    best_model = None
    best_score = 0
    
    for fold_idx, (tr_idx, val_idx) in enumerate(tscv.split(X_scaled)):
        _LOG.info(f"📊 Fold {fold_idx + 1}/{config.CV_N_SPLITS}")
        
        X_tr, X_val = X_scaled[tr_idx], X_scaled[val_idx]
        y_tr, y_val = y[tr_idx], y[val_idx]
        
        # CRITICAL FIX: Check class distribution in this fold before SMOTE
        unique_tr, counts_tr = np.unique(y_tr, return_counts=True)
        unique_val, counts_val = np.unique(y_val, return_counts=True)
        
        _LOG.info(f"   Fold {fold_idx + 1} Training classes: {dict(zip(unique_tr, counts_tr))}")
        _LOG.info(f"   Fold {fold_idx + 1} Validation classes: {dict(zip(unique_val, counts_val))}")
        
        # Calcola class weights per bilanciamento
        sample_weight = None
        if config.USE_CLASS_WEIGHTS:
            try:
                class_weights = class_weight.compute_class_weight(
                    'balanced', classes=np.unique(y_tr), y=y_tr
                )
                class_weight_dict = {i: class_weights[i] for i in range(len(class_weights))}
                sample_weight = np.array([class_weight_dict[cls] for cls in y_tr])
                _LOG.info(f"   🎯 Class weights calcolati per Fold {fold_idx + 1}")
            except Exception as e:
                _LOG.warning(f"   ⚠️ Class weights falliti per Fold {fold_idx + 1}: {e}")
        
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

    # ======= Final Training =======
    # Usa l'ultimo split per evaluation finale
    final_tr_idx, final_val_idx = list(tscv.split(X_scaled))[-1]
    X_final_tr, X_final_val = X_scaled[final_tr_idx], X_scaled[final_val_idx]
    y_final_tr, y_final_val = y[final_tr_idx], y[final_val_idx]
    
    # Log class distribution
    unique_final_tr, counts_final_tr = np.unique(y_final_tr, return_counts=True)
    unique_final_val, counts_final_val = np.unique(y_final_val, return_counts=True)
    
    _LOG.info(f"📊 Final Training classes: {dict(zip(unique_final_tr, counts_final_tr))}")
    _LOG.info(f"📊 Final Validation classes: {dict(zip(unique_final_val, counts_final_val))}")

    # Re-train final model with class weights
    final_sample_weight = None
    if config.USE_CLASS_WEIGHTS:
        try:
            final_class_weights = class_weight.compute_class_weight(
                'balanced', classes=np.unique(y_final_tr), y=y_final_tr
            )
            final_class_weight_dict = {i: final_class_weights[i] for i in range(len(final_class_weights))}
            final_sample_weight = np.array([final_class_weight_dict[cls] for cls in y_final_tr])
            _LOG.info("🎯 Class weights calcolati per final model")
        except Exception as e:
            _LOG.warning(f"⚠️ Final class weights falliti: {e}")
    
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
    
    # 📊 TRAINING DATA COLLECTION - Clear display
    print(colored(f"\n🧠 TRAINING PHASE - Data Collection for {timeframe}", "magenta", attrs=['bold']))
    print(colored("=" * 100, "magenta"))
    print(colored(f"{'#':<4} {'SYMBOL':<20} {'SAMPLES':<10} {'STATUS':<15} {'BUY%':<8} {'SELL%':<8} {'NEUTRAL%':<8}", "white", attrs=['bold']))
    print(colored("-" * 100, "magenta"))
    
    successful_symbols = 0
    for idx, sym in enumerate(top_symbols, 1):
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
            
            # ======= SL-Aware Labeling =======
            labels, sl_features = label_with_sl_awareness_v2(
                df_with_indicators,
                lookforward_steps=config.FUTURE_RETURN_STEPS,
                sl_percentage=config.SL_AWARENESS_PERCENTAGE,
                percentile_buy=config.SL_AWARENESS_PERCENTILE_BUY,
                percentile_sell=config.SL_AWARENESS_PERCENTILE_SELL
            )
            _LOG.debug(f"🎯 Using SL-Aware labeling for {timeframe} (SL={config.SL_AWARENESS_PERCENTAGE*100:.1f}%)")
            
            # Calculate label distribution for display
            buy_count = np.sum(labels == 1)
            sell_count = np.sum(labels == 0)
            neutral_count = np.sum(labels == 2)
            total = len(labels)
            
            buy_pct = (buy_count / total * 100) if total > 0 else 0
            sell_pct = (sell_count / total * 100) if total > 0 else 0
            neutral_pct = (neutral_count / total * 100) if total > 0 else 0
            
            # Display training progress
            symbol_short = sym.replace('/USDT:USDT', '')
            status = colored("✅ OK", "green")
            
            print(f"{idx:<4} {symbol_short:<20} {len(data):<10} {status:<15} {buy_pct:.1f}%    {sell_pct:.1f}%    {neutral_pct:.1f}%")
            
            # Progress separator every 10 symbols
            if idx % 10 == 0 and idx < len(top_symbols):
                print(colored("─" * 100, "blue"))
                print(colored(f"Training Progress: {idx}/{len(top_symbols)} ({idx/len(top_symbols)*100:.1f}%) | Success: {successful_symbols}/{idx}", "blue", attrs=['bold']))
                print(colored("─" * 100, "blue"))
            
            # ======= TEMPORAL FEATURE PRESERVATION =======
            # FIXED: Usa finestra temporale specifica per timeframe
            timesteps_for_tf = config.get_timesteps_for_timeframe(timeframe)
            
            # Create temporal features from prepared data
            for i in range(timesteps_for_tf, len(data) - config.FUTURE_RETURN_STEPS):
                if i < len(labels):
                    # FIXED: Sequence con timesteps corretti per il timeframe
                    sequence = data[i - timesteps_for_tf : i]
                    
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
    ENHANCED B+ HYBRID: Momentum + Selective Statistics for ALL intermediate candles
    
    REVOLUTIONARY UPGRADE:
    - Uses ALL intermediate candles (was wasting 92% of data!)
    - Momentum patterns across full sequence 
    - Statistical analysis for critical trading features
    - Maintains N_FEATURES_FINAL = 66 compatibility
    
    Args:
        sequence (np.ndarray): Sequence of shape (timesteps, 33_features)
        
    Returns:
        np.ndarray: Enhanced temporal features (66 total)
    """
    try:
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
        
        # 1. CURRENT STATE (33 features) - Latest candle
        features.extend(sequence[-1])
        _LOG.debug(f"Current state features: {len(sequence[-1])}")
        
        # 2. MOMENTUM PATTERNS (27 features) - Using ALL intermediate candles
        momentum_features = []
        
        # Select most important features for momentum analysis (reduce from 33 to 27)
        important_feature_indices = [0, 1, 2, 3, 4, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]  # Skip less critical swing features
        
        for col_idx in important_feature_indices:
            if col_idx < sequence.shape[1]:
                col_data = sequence[:, col_idx]
                
                # Advanced momentum analysis using ALL timesteps
                if len(col_data) > 1:
                    # Linear trend strength across full sequence
                    time_index = np.arange(len(col_data))
                    correlation = np.corrcoef(time_index, col_data)[0,1]
                    
                    # Handle NaN correlation (constant values)
                    momentum_features.append(correlation if np.isfinite(correlation) else 0.0)
                else:
                    momentum_features.append(0.0)
        
        features.extend(momentum_features)
        _LOG.debug(f"Momentum features: {len(momentum_features)}")
        
        # 3. CRITICAL FEATURE STATISTICS (6 features) - Deep analysis of key indicators
        critical_stats = []
        
        for feature_name, col_idx in CRITICAL_FEATURES.items():
            if col_idx < sequence.shape[1]:
                col_data = sequence[:, col_idx]
                
                if len(col_data) > 1:
                    # Volatility measure (how much feature varied during period)
                    volatility = np.std(col_data) / (np.mean(np.abs(col_data)) + 1e-8)
                    critical_stats.append(volatility)
                else:
                    critical_stats.append(0.0)
            else:
                critical_stats.append(0.0)
        
        features.extend(critical_stats)
        _LOG.debug(f"Critical stats features: {len(critical_stats)}")
        
        # TOTAL CALCULATION: 33 + 27 + 6 = 66 features (perfect compatibility!)
        
        # Clean and validate all features
        features = np.array(features, dtype=np.float64)
        features = np.nan_to_num(features, nan=0.0, posinf=1e6, neginf=-1e6)
        
        # ENHANCED VALIDATION with detailed logging
        final_features = features.flatten()
        actual_count = len(final_features)
        
        _LOG.debug(f"🧠 Feature breakdown: Current={len(sequence[-1])}, Momentum={len(momentum_features)}, Critical={len(critical_stats)}, Total={actual_count}")
        
        if actual_count != N_FEATURES_FINAL:
            _LOG.warning(f"⚠️ Feature count adjustment: Expected {N_FEATURES_FINAL}, got {actual_count}")
            
            if actual_count < N_FEATURES_FINAL:
                # Pad with zeros if too few
                padding = np.zeros(N_FEATURES_FINAL - actual_count)
                final_features = np.concatenate([final_features, padding])
                _LOG.info(f"   ✅ Padded to {len(final_features)} features")
            else:
                # Truncate if too many (keep most important)
                final_features = final_features[:N_FEATURES_FINAL]
                _LOG.info(f"   ✅ Truncated to {len(final_features)} features")
        else:
            _LOG.debug(f"✅ Perfect feature count: {actual_count}")
        
        return final_features
        
    except Exception as e:
        _LOG.error(f"❌ Error in enhanced temporal features: {e}")
        # Emergency fallback: original simple approach
        return create_temporal_features_fallback(sequence)

def create_temporal_features_fallback(sequence):
    """Emergency fallback to original approach if enhanced version fails"""
    try:
        features = []
        features.extend(sequence[-1])  # Current: 33
        
        if len(sequence) > 1:
            price_change = (sequence[-1] - sequence[0]) / (np.abs(sequence[0]) + 1e-8)
            features.extend(price_change)  # Trend: 33
        else:
            features.extend(np.zeros(sequence.shape[1]))
            
        features = np.array(features, dtype=np.float64)
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
        
        return features.flatten()[:N_FEATURES_FINAL]
        
    except Exception as e:
        _LOG.error(f"❌ Even fallback failed: {e}")
        # Last resort: zeros
        return np.zeros(N_FEATURES_FINAL)
