import os
import logging
from termcolor import colored
import joblib

# Import only XGBoost-related path functions since that's the only model used
from config import get_xgb_model_file, get_xgb_scaler_file

def load_xgboost_model_func(timeframe):
    """
    Load XGBoost model and scaler for a specific timeframe.
    
    CRITICAL FIX: Check file existence BEFORE loading to prevent exceptions
    """
    try:
        model_file = get_xgb_model_file(timeframe)
        scaler_file = get_xgb_scaler_file(timeframe)
        
        # 1. CHECK FILES EXIST FIRST (before attempting load)
        if not os.path.exists(model_file):
            logging.warning(f"{colored(f'Model file not found: {model_file}', 'yellow')}")
            return None, None
        
        if not os.path.exists(scaler_file):
            logging.warning(f"{colored(f'Scaler file not found: {scaler_file}', 'yellow')}")
            return None, None
        
        # 2. LOAD FILES (only if they exist)
        model = joblib.load(model_file)
        scaler = joblib.load(scaler_file)
        
        # 3. VALIDATE LOADED OBJECTS
        if model is None:
            logging.error(f"{colored(f'Model loaded as None for {timeframe}', 'red')}")
            return None, None
        
        if scaler is None:
            logging.error(f"{colored(f'Scaler loaded as None for {timeframe}', 'red')}")
            return None, None
        
        # 4. TEST PREDICTION (validate model works)
        try:
            import numpy as np
            from config import N_FEATURES_FINAL
            
            dummy_features = np.random.random(N_FEATURES_FINAL)
            dummy_scaled = scaler.transform(dummy_features.reshape(1, -1))
            dummy_pred = model.predict_proba(dummy_scaled)
            
            if dummy_pred is None or len(dummy_pred) == 0:
                logging.error(f"{colored(f'Model test prediction failed for {timeframe}', 'red')}")
                return None, None
        except Exception as test_error:
            logging.error(f"{colored(f'Model validation test failed for {timeframe}: {test_error}', 'red')}")
            return None, None
        
        # 5. SUCCESS
        logging.info(f"{colored('XGBoost model loaded for', 'green')} {timeframe}")
        return model, scaler
        
    except Exception as e:
        logging.error(f"{colored('Errore nel caricamento del modello XGBoost per', 'red')} {timeframe}: {e}")
        return None, None
