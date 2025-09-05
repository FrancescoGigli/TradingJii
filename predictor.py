import logging
from termcolor import colored
import numpy as np
import config
import pandas as pd
from config import (
    EXPECTED_COLUMNS,
    NEUTRAL_UPPER_THRESHOLD,
    NEUTRAL_LOWER_THRESHOLD,
    RSI_THRESHOLDS,
    COLOR_THRESHOLD_GREEN,
    COLOR_THRESHOLD_RED
)
from data_utils import prepare_data

# Import the robust ML predictor
try:
    from core.ml_predictor import predict_signal_ensemble as robust_predict_signal_ensemble
    ROBUST_PREDICTOR_AVAILABLE = True
except ImportError as e:
    logging.warning(f"⚠️ Robust ML Predictor not available: {e}")
    ROBUST_PREDICTOR_AVAILABLE = False

def get_color_normal(value):
    if value > COLOR_THRESHOLD_GREEN:
        return "green"
    elif value < COLOR_THRESHOLD_RED:
        return "red"
    else:
        return "yellow"

def get_color_rsi(rsi_value):
    if rsi_value < RSI_THRESHOLDS['sideways']['oversold']:
        return "green"
    elif rsi_value > RSI_THRESHOLDS['sideways']['overbought']:
        return "red"
    else:
        return "yellow"

def predict_signal_for_model(df, model, scaler, symbol, time_steps, expected_features=None, timeframe=""):
    if expected_features is None:
        expected_features = len(EXPECTED_COLUMNS)
    if model is None or scaler is None:
        logging.error(f"{symbol} [{timeframe}]: modello o scaler non disponibili.")
        return None
    try:
        # FIXED: Usa finestra temporale uniforme per ensemble coerente
        timesteps_needed = config.get_timesteps_for_timeframe(timeframe) if timeframe else time_steps
        
        # Verifica che il DataFrame contenga esattamente le colonne attese
        if not set(df.columns) == set(EXPECTED_COLUMNS):
            missing_cols = set(EXPECTED_COLUMNS) - set(df.columns)
            extra_cols = set(df.columns) - set(EXPECTED_COLUMNS)
            error_msg = f"{symbol} [{timeframe}]: DataFrame con colonne non corrette."
            if missing_cols:
                error_msg += f" Mancanti: {missing_cols}."
            if extra_cols:
                error_msg += f" Extra: {extra_cols}."
            logging.error(error_msg)
            return None
            
        # Assicurati che le colonne siano nell'ordine corretto
        df = df[EXPECTED_COLUMNS]
        data = df.values
        # Assicurati che non ci siano NaN o infiniti nei dati
        data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)

        if len(data) < timesteps_needed:
            logging.error(f"{symbol} [{timeframe}]: dati insufficienti ({len(data)} elementi, richiesti {timesteps_needed} per {config.LOOKBACK_HOURS}h).")
            return None

        # FIXED: Usa la finestra temporale corretta per ogni timeframe
        sequence = data[-timesteps_needed:]
        
        # Log per debug dell'ensemble fix
        logging.debug(f"{symbol} [{timeframe}]: Using {timesteps_needed} timesteps = {config.LOOKBACK_HOURS}h window")
        
        # Verifica che non ci siano NaN o infiniti prima del processing
        if np.isnan(sequence).any() or np.isinf(sequence).any():
            logging.warning(f"{symbol} [{timeframe}]: valori NaN o infiniti trovati nei dati, sostituiti con 0.0")
            sequence = np.nan_to_num(sequence, nan=0.0, posinf=0.0, neginf=0.0)
            
        # Crea temporal features strutturate come nel training
        from trainer import create_temporal_features
        temporal_features = create_temporal_features(sequence)
        
        # Reshape per il modello (1 sample)
        X_temporal = temporal_features.reshape(1, -1)
        
        # Scale le features
        X_scaled = scaler.transform(X_temporal)
        
        # Predizione
        probs = model.predict_proba(X_scaled)[0]
        pred = np.argmax(probs)
        return pred
    except Exception as e:
        logging.error(f"Errore in prediction per {symbol} [{timeframe}]: {e}")
        return None

def predict_signal_ensemble(dataframes, xgb_models, xgb_scalers, symbol, time_steps):
    """
    Enhanced predict_signal_ensemble with robust error handling
    
    PRIORITY: Use robust predictor if available, fallback to original logic if needed
    """
    
    # Try robust predictor first if available
    if ROBUST_PREDICTOR_AVAILABLE:
        try:
            return robust_predict_signal_ensemble(dataframes, xgb_models, xgb_scalers, symbol, time_steps)
        except Exception as e:
            logging.warning(f"⚠️ Robust predictor failed for {symbol}, falling back to original logic: {e}")
    
    # FALLBACK: Original logic with enhanced error checking
    logging.info(f"🔄 Using fallback prediction logic for {symbol}")
    
    # Enhanced model/scaler validation
    working_timeframes = []
    for tf in dataframes.keys():
        if (tf in xgb_models and tf in xgb_scalers and 
            xgb_models[tf] is not None and xgb_scalers[tf] is not None):
            working_timeframes.append(tf)
        else:
            logging.warning(f"⚠️ Skipping {tf} for {symbol}: model or scaler not available")
    
    if not working_timeframes:
        logging.error(f"❌ No working models available for {symbol}")
        return None, None, {}
    
    xgb_preds = {}
    
    for tf in working_timeframes:
        df = dataframes[tf]
        model = xgb_models[tf]
        scaler = xgb_scalers[tf]
        
        try:
            # FIXED: Usa timesteps corretti per ogni timeframe
            timesteps_needed = config.get_timesteps_for_timeframe(tf)
            
            # Validate DataFrame structure
            if not set(df.columns) >= set(EXPECTED_COLUMNS):
                missing_cols = set(EXPECTED_COLUMNS) - set(df.columns)
                logging.error(f"{symbol} [{tf}]: Missing columns {missing_cols}")
                continue
            
            # Prepare data with extra safety
            df_xgb = df[EXPECTED_COLUMNS]
            data_xgb = df_xgb.values
            
            if len(data_xgb) < timesteps_needed:
                logging.warning(f"{symbol} [{tf}]: Insufficient data {len(data_xgb)} < {timesteps_needed} for {config.LOOKBACK_HOURS}h")
                continue
                
            # Clean data aggressively
            data_xgb = np.nan_to_num(data_xgb, nan=0.0, posinf=0.0, neginf=0.0)
            sequence_xgb = data_xgb[-timesteps_needed:]
            
            # Log ensemble fix
            logging.debug(f"{symbol} [{tf}]: Using {timesteps_needed} timesteps = {config.LOOKBACK_HOURS}h window")
            
            # Create temporal features with error handling
            try:
                from trainer import create_temporal_features
                temporal_features_xgb = create_temporal_features(sequence_xgb)
            except Exception as feat_error:
                logging.error(f"Feature creation failed for {symbol}[{tf}]: {feat_error}")
                # Fallback: use simple flattened features
                temporal_features_xgb = sequence_xgb.flatten()
            
            # Reshape and scale
            X_xgb = temporal_features_xgb.reshape(1, -1)
            
            # Extra safety check for scaler
            try:
                X_xgb_scaled = scaler.transform(X_xgb)
            except Exception as scale_error:
                logging.error(f"Scaling failed for {symbol}[{tf}]: {scale_error}")
                continue
            
            # Predict with extra validation
            try:
                probs = model.predict_proba(X_xgb_scaled)[0]
                xgb_pred = np.argmax(probs)
                xgb_preds[tf] = xgb_pred
                logging.debug(f"{symbol} [{tf}] - XGB: {xgb_pred} (confidence: {np.max(probs):.3f})")
            except Exception as pred_error:
                logging.error(f"Model prediction failed for {symbol}[{tf}]: {pred_error}")
                continue
                
        except Exception as e:
            logging.error(f"❌ Prediction error for {symbol}[{tf}]: {e}")
            continue

    # If no predictions succeeded
    if not xgb_preds:
        logging.error(f"❌ All predictions failed for {symbol}")
        return None, None, {}
    
    # Simple ensemble voting
    all_votes = list(xgb_preds.values())
    votes_counter = {}
    for vote in all_votes:
        votes_counter[vote] = votes_counter.get(vote, 0) + 1
    
    final_signal = max(votes_counter.items(), key=lambda x: x[1])[0]
    total_votes = sum(votes_counter.values())
    confidence_value = votes_counter[final_signal] / total_votes
    
    # Log results
    logging.info(f"{symbol}: Final signal {final_signal} with {confidence_value:.3f} confidence (votes: {votes_counter})")
    
    # Apply confidence threshold
    if confidence_value < 0.6:  # Simple threshold
        logging.info(f"{symbol}: Low confidence {confidence_value:.3f}, returning None")
        return confidence_value, None, xgb_preds
    
    return confidence_value, final_signal, xgb_preds
