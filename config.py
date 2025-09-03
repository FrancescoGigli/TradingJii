"""
Configurazione generale del bot con supporto a file .env.

Ordine di ricerca credenziali
-----------------------------
1. Se esistono variabili d’ambiente BYBIT_API_KEY / BYBIT_API_SECRET,
   usiamo quelle (override).
2. Altrimenti le leggiamo da .env nella root del progetto.
"""

from __future__ import annotations

import os
from pathlib import Path

# ----------------------------------------------------------------------
# Carica il file .env se presente (richiede python-dotenv)
# ----------------------------------------------------------------------
try:
    from dotenv import load_dotenv, find_dotenv

    _env_file = find_dotenv(usecwd=True)
    if _env_file:
        load_dotenv(_env_file, override=False)  # NON sovrascrive variabili già settate
except ModuleNotFoundError:  # libreria non installata
    pass  # il codice funzionerà comunque se le variabili sono nel sistema

# ----------------------------------------------------------------------
# Credenziali Bybit
# ----------------------------------------------------------------------
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

if not API_KEY or not API_SECRET:
    raise RuntimeError(
        "Chiavi API mancanti: definisci BYBIT_API_KEY e BYBIT_API_SECRET "
        "nel file .env o tra le variabili d’ambiente."
    )

# ----------------------------------------------------------------------
# Configurazione exchange
# ----------------------------------------------------------------------
exchange_config = {
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "enableRateLimit": True,
    "options": {
        "adjustForTimeDifference": True,
        "recvWindow": 60_000,
    },
}

# ----------------------------------------------------------------------
# Parametri di trading
# ----------------------------------------------------------------------
MARGIN_USDT = 40.0
LEVERAGE = 10

ENABLED_TIMEFRAMES: list[str] = ["15m", "30m", "1h"]
TIMEFRAME_DEFAULT: str | None = "15m"
TIME_STEPS = 7

MODEL_RATES = {"xgb": 1.0}

NEUTRAL_LOWER_THRESHOLD = 0.40
NEUTRAL_UPPER_THRESHOLD = 0.60
COLOR_THRESHOLD_GREEN = 0.65
COLOR_THRESHOLD_RED = 0.35

TRADE_CYCLE_INTERVAL = 300
DATA_LIMIT_DAYS = 90  # Ridotto da 180 per training più veloce

# ----------------------------------------------------------------------
# Percorsi dei modelli (solo XGBoost)
# ----------------------------------------------------------------------
_TRAINED_DIR = Path(__file__).resolve().with_name("trained_models")
_TRAINED_DIR.mkdir(exist_ok=True)

def get_xgb_model_file(tf: str)   -> str: return str(_TRAINED_DIR / f"xgb_model_{tf}.pkl")
def get_xgb_scaler_file(tf: str)  -> str: return str(_TRAINED_DIR / f"xgb_scaler_{tf}.pkl")


EXCLUDED_SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]

# CRITICAL FIX: Unify training and inference datasets to prevent overfitting
# The model should train and predict on the SAME set of symbols
TOP_SYMBOLS_COUNT = 50  # Unified count for both training and analysis
TOP_TRAIN_CRYPTO = TOP_SYMBOLS_COUNT    # Same symbols for training
TOP_ANALYSIS_CRYPTO = TOP_SYMBOLS_COUNT  # Same symbols for analysis

# Additional symbol filtering for better quality
MIN_VOLUME_THRESHOLD = 1000000  # Minimum daily volume in USDT
MIN_PRICE_THRESHOLD = 0.001     # Minimum price to avoid dust tokens

# ----------------------------------------------------------------------
# Feature
# ----------------------------------------------------------------------
EXPECTED_COLUMNS = [
    # Dati base OHLCV (5)
    "open", "high", "low", "close", "volume",
    # Medie mobili esponenziali (3)
    "ema5", "ema10", "ema20",
    # MACD (3)
    "macd", "macd_signal", "macd_histogram",
    # Oscillatori momentum (2)
    "rsi_fast", "stoch_rsi",
    # Volatilità (3) 
    "atr", "bollinger_hband", "bollinger_lband",
    # Volume (2)
    "vwap", "obv",
    # Forza trend (1)
    "adx",
    # Volatilità aggiuntiva (1)
    "volatility",
    # Swing Probability Features (13) - No lookahead bias
    "price_pos_5", "price_pos_10", "price_pos_20",
    "vol_acceleration", "atr_norm_move", "momentum_divergence",
    "volatility_squeeze", "resistance_dist_10", "resistance_dist_20",
    "support_dist_10", "support_dist_20", "price_acceleration",
    "vol_price_alignment"
]

RSI_THRESHOLDS = {"sideways": {"oversold": 30, "overbought": 70}}

TRAIN_IF_NOT_FOUND = True

# ----------------------------------------------------------------------
# Modalità Demo/Test
# ----------------------------------------------------------------------
DEMO_MODE = True  # Set to True per vedere solo i segnali senza eseguire trade
DEMO_BALANCE = 1000.0  # Balance USDT fittizio per modalità demo

# ----------------------------------------------------------------------
# Parametri Swing Points Labeling (RESO PIÙ AGGRESSIVO)
# ----------------------------------------------------------------------
SWING_ORDER = 2           # RIDOTTO: da 3 a 2 candele → più swing points trovati
SWING_ATR_FACTOR = 0.3    # RIDOTTO: da 0.5 a 0.3 → swing più piccoli accettati
SWING_VOLUME_FACTOR = 1.0 # RIDOTTO: da 1.2 a 1.0 → meno filtro volume

# ----------------------------------------------------------------------
# Parametri Future Returns Labeling (RESO PIÙ SENSIBILE)
# ----------------------------------------------------------------------
FUTURE_RETURN_STEPS = 3      # Steps nel futuro per calcolare return
RETURN_BUY_THRESHOLD = 0.008 # RIDOTTO: da 1.5% a 0.8% → più segnali BUY
RETURN_SELL_THRESHOLD = -0.008 # RIDOTTO: da -1.5% a -0.8% → più segnali SELL

# ----------------------------------------------------------------------
# Parametri Ensemble Voting (NUOVI - PER PIÙ SEGNALI)
# ----------------------------------------------------------------------
MIN_ENSEMBLE_CONFIDENCE = 0.6    # Confidenza minima per segnali (60% invece del 100%)
ALLOW_MIXED_SIGNALS = True       # Permetti segnali anche se timeframes discordano
NEUTRAL_SKIP_PROBABILITY = 0.7   # 70% di skipare segnali neutral → più BUY/SELL

# ----------------------------------------------------------------------
# Parametri Class Balancing
# ----------------------------------------------------------------------
USE_SMOTE = False            # Disabilitato temporaneamente per velocità
USE_CLASS_WEIGHTS = True     # Abilita class weights in XGBoost
SMOTE_K_NEIGHBORS = 5        # Parametro SMOTE

# ----------------------------------------------------------------------
# Parametri XGBoost Ottimizzati (per velocità)
# ----------------------------------------------------------------------
XGB_N_ESTIMATORS = 100       # Ridotto per velocità
XGB_MAX_DEPTH = 6           # Ridotto per velocità
XGB_LEARNING_RATE = 0.1     # Aumentato per convergenza più veloce
XGB_SUBSAMPLE = 0.8         # Subsample delle righe
XGB_COLSAMPLE_BYTREE = 0.8  # Subsample delle feature
XGB_REG_ALPHA = 0.01        # Ridotta regularization per più aggressività
XGB_REG_LAMBDA = 0.1        # Ridotta regularization per più aggressività

# ----------------------------------------------------------------------
# Parametri Validazione
# ----------------------------------------------------------------------
CV_N_SPLITS = 3             # Ridotto da 5 per velocità
MIN_TRAIN_SIZE = 0.6        # Minimum size del training set
