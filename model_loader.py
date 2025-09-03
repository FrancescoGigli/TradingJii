import os
import logging
from termcolor import colored
import joblib

# Import only XGBoost-related path functions since that's the only model used
from config import get_xgb_model_file, get_xgb_scaler_file

def load_xgboost_model_func(timeframe):
    """Load XGBoost model and scaler for a specific timeframe."""
    try:
        model_file = get_xgb_model_file(timeframe)
        scaler_file = get_xgb_scaler_file(timeframe)
        
        if os.path.exists(model_file) and os.path.exists(scaler_file):
            model = joblib.load(model_file)
            scaler = joblib.load(scaler_file)
            logging.info(f"{colored('XGBoost model loaded for', 'green')} {timeframe}")
            return model, scaler
        else:
            logging.warning(f"{colored('XGBoost model or scaler not found for', 'yellow')} {timeframe}")
            return None, None
    except Exception as e:
        logging.error(f"{colored('Errore nel caricamento del modello XGBoost per', 'red')} {timeframe}: {e}")
        return None, None
