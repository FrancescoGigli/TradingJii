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
        "recvWindow": 120_000,  # INCREASED: da 60s a 120s per timestamp issues
    },
}

# ----------------------------------------------------------------------
# Parametri di trading
# ----------------------------------------------------------------------
# DYNAMIC MARGIN: 20-50 USDT based on confidence and risk
MARGIN_BASE_USDT = 20.0    # Minimum margin per trade
MARGIN_MAX_USDT = 50.0     # Maximum margin per trade  
LEVERAGE = 10

# Legacy compatibility (will be calculated dynamically)
MARGIN_USDT = 25.0  # Average for fallback calculations

# ----------------------------------------------------------------------
# NUOVA LOGICA - Stop Loss e Trailing Management
# ----------------------------------------------------------------------
# Stop Loss iniziale: 60% perdita sul margine (6% sul prezzo con leva 10x)
INITIAL_SL_MARGIN_LOSS_PCT = 0.6      # 60% perdita sul margine
INITIAL_SL_PRICE_PCT = 0.06           # 6% dal prezzo (equivalente con leva 10x)

# Trigger dinamico per attivazione trailing (5-10% profitto)
TRAILING_TRIGGER_BASE_PCT = 0.10      # 10% base per bassa volatilità
TRAILING_TRIGGER_MIN_PCT = 0.05       # 5% minimo per alta volatilità  
TRAILING_TRIGGER_MAX_PCT = 0.10       # 10% massimo per media volatilità

# Distanza trailing dinamica basata su volatilità
TRAILING_DISTANCE_LOW_VOL = 0.02      # 2% per bassa volatilità (ATR < 2%)
TRAILING_DISTANCE_MED_VOL = 0.03      # 3% per media volatilità (ATR 2-4%)
TRAILING_DISTANCE_HIGH_VOL = 0.04     # 4% per alta volatilità (ATR > 4%)

# Soglie volatilità per classificazione ATR
VOLATILITY_LOW_THRESHOLD = 0.02       # 2% ATR
VOLATILITY_HIGH_THRESHOLD = 0.04      # 4% ATR

# ----------------------------------------------------------------------
# HIGH-FREQUENCY TRAILING MONITOR CONFIGURATION
# ----------------------------------------------------------------------
# Monitor dedicato per trailing stops ad alta frequenza
TRAILING_MONITOR_INTERVAL = 30        # 30 secondi (vs 300s ciclo principale)
TRAILING_MONITOR_ENABLED = True       # Enable/disable high-freq monitoring
TRAILING_PRICE_CACHE_TTL = 60        # Cache prezzi per 60 secondi
TRAILING_MAX_API_CALLS_PER_MIN = 120 # Limite API calls per non superare rate limits

# Performance e sicurezza
TRAILING_ERROR_RECOVERY_DELAY = 10    # Delay dopo errore (secondi)
TRAILING_MAX_CONSECUTIVE_ERRORS = 5   # Max errori consecutivi prima di fermare
TRAILING_ENABLE_LOGGING = True        # Enable detailed trailing logs

# ----------------------------------------------------------------------
# REAL-TIME POSITION DISPLAY CONFIGURATION
# ----------------------------------------------------------------------
# Display real-time delle posizioni con aggiornamento ogni secondo  
REALTIME_DISPLAY_ENABLED = True      # RIABILITATO con fix
REALTIME_DISPLAY_INTERVAL = 1.0      # 1 secondo aggiornamento
REALTIME_PRICE_CACHE_TTL = 2         # Cache TTL per prezzi (secondi)
REALTIME_MAX_API_CALLS = 60          # Max API calls per minuto per display

# Display avanzato
REALTIME_SHOW_TRIGGERS = True        # Mostra distanza da trigger
REALTIME_SHOW_TRAILING_INFO = True   # Mostra info trailing quando attivo
REALTIME_COLOR_CODING = True         # Color coding avanzato per PNL

ENABLED_TIMEFRAMES: list[str] = ["15m", "30m", "1h"]
TIMEFRAME_DEFAULT: str | None = "15m"
TIME_STEPS = 7  # DEPRECATED: Use get_timesteps_for_timeframe() instead

# ----------------------------------------------------------------------
# FIXED: Uniform Time Window for Multi-Timeframe Ensemble
# ----------------------------------------------------------------------
LOOKBACK_HOURS = 6  # Finestra temporale uniforme per tutti i timeframes

# Calcolo dinamico timesteps per ogni timeframe (stessa finestra temporale)
TIMEFRAME_TIMESTEPS = {
    "1m": int(LOOKBACK_HOURS * 60 / 1),    # 360 candele = 6 ore
    "3m": int(LOOKBACK_HOURS * 60 / 3),    # 120 candele = 6 ore
    "5m": int(LOOKBACK_HOURS * 60 / 5),    # 72 candele = 6 ore
    "15m": int(LOOKBACK_HOURS * 60 / 15),  # 24 candele = 6 ore
    "30m": int(LOOKBACK_HOURS * 60 / 30),  # 12 candele = 6 ore
    "1h": int(LOOKBACK_HOURS / 1),         # 6 candele = 6 ore
    "4h": max(2, int(LOOKBACK_HOURS / 4)), # 2 candele = 8 ore (minimo 2)
    "1d": max(1, int(LOOKBACK_HOURS / 24)) # 1 candela = 24 ore (minimo 1)
}

def get_timesteps_for_timeframe(timeframe: str) -> int:
    """
    Restituisce il numero di timesteps necessari per coprire LOOKBACK_HOURS
    per il timeframe specificato. Questo garantisce che tutti i modelli 
    dell'ensemble guardino la stessa finestra temporale.
    
    Args:
        timeframe: Timeframe (es. "15m", "1h")
        
    Returns:
        int: Numero di candele necessarie
    """
    timesteps = TIMEFRAME_TIMESTEPS.get(timeframe, 7)
    return max(2, timesteps)  # Minimo 2 candele sempre

# ----------------------------------------------------------------------
# CRITICAL FIX: Feature Count Consistency
# ----------------------------------------------------------------------
N_FEATURES_FINAL = 66  # Feature count dopo create_temporal_features()
"""
CRITICAL COMPATIBILITY CONSTANT:
- Training: create_temporal_features() produces exactly 66 features
- Prediction: Must expect exactly 66 features  
- Formula: 33 (current) + 33 (trend) = 66 total features
- Based on len(EXPECTED_COLUMNS) = 33

DO NOT CHANGE unless you modify create_temporal_features() logic or EXPECTED_COLUMNS!
"""

MODEL_RATES = {"xgb": 1.0}

NEUTRAL_LOWER_THRESHOLD = 0.40
NEUTRAL_UPPER_THRESHOLD = 0.60
COLOR_THRESHOLD_GREEN = 0.65
COLOR_THRESHOLD_RED = 0.35

TRADE_CYCLE_INTERVAL = 300
DATA_LIMIT_DAYS = 180  # 6 mesi per più dati storici e migliori pattern ML
WARMUP_PERIODS = 30    # Candele di warmup da scartare per indicatori affidabili

# ----------------------------------------------------------------------
# Percorsi dei modelli (solo XGBoost)
# ----------------------------------------------------------------------
_TRAINED_DIR = Path(__file__).resolve().with_name("trained_models")
_TRAINED_DIR.mkdir(exist_ok=True)

def get_xgb_model_file(tf: str)   -> str: return str(_TRAINED_DIR / f"xgb_model_{tf}.pkl")
def get_xgb_scaler_file(tf: str)  -> str: return str(_TRAINED_DIR / f"xgb_scaler_{tf}.pkl")


EXCLUDED_SYMBOLS = []  # No symbols excluded - include all for analysis

# CONSOLIDATED: Single configuration for symbols count
TOP_SYMBOLS_COUNT = 10  # Main configuration for symbol count

# UNIFIED: Both training and analysis use same symbols to prevent overfitting
TOP_TRAIN_CRYPTO = TOP_SYMBOLS_COUNT    # Training symbols (unified with analysis)
TOP_ANALYSIS_CRYPTO = TOP_SYMBOLS_COUNT  # Analysis symbols (unified with training)

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
DEMO_MODE = False  # Default: False (LIVE mode), can be overridden by user selection
DEMO_BALANCE = 1000.0  # Balance USDT fittizio per modalità demo

# ----------------------------------------------------------------------
# Parametri Swing Points Labeling (RESO PIÙ AGGRESSIVO)
# ----------------------------------------------------------------------
SWING_ORDER = 2           # RIDOTTO: da 3 a 2 candele → più swing points trovati
SWING_ATR_FACTOR = 0.3    # RIDOTTO: da 0.5 a 0.3 → swing più piccoli accettati
SWING_VOLUME_FACTOR = 1.0 # RIDOTTO: da 1.2 a 1.0 → meno filtro volume

# ----------------------------------------------------------------------
# Parametri Future Returns Labeling (CRITICAL FIX - TIMEFRAME ADAPTIVE)
# ----------------------------------------------------------------------
FUTURE_RETURN_STEPS = 3      # Steps nel futuro per calcolare return

# DYNAMIC THRESHOLDS: Adjust based on timeframe volatility
TIMEFRAME_THRESHOLDS = {
    "15m": {"buy": 0.008, "sell": -0.008},  # 0.8% for high-frequency timeframe
    "30m": {"buy": 0.012, "sell": -0.012},  # 1.2% for medium timeframe  
    "1h": {"buy": 0.015, "sell": -0.015},   # 1.5% for longer timeframe
    "4h": {"buy": 0.025, "sell": -0.025},   # 2.5% for macro timeframe
    "1d": {"buy": 0.04, "sell": -0.04}      # 4.0% for daily timeframe
}

# Backward compatibility - use 1h thresholds as default
RETURN_BUY_THRESHOLD = TIMEFRAME_THRESHOLDS["1h"]["buy"]    # Default: 1.5%
RETURN_SELL_THRESHOLD = TIMEFRAME_THRESHOLDS["1h"]["sell"]   # Default: -1.5%

def get_thresholds_for_timeframe(timeframe: str) -> tuple:
    """
    Get appropriate BUY/SELL thresholds for specific timeframe
    
    Returns:
        tuple: (buy_threshold, sell_threshold)
    """
    thresholds = TIMEFRAME_THRESHOLDS.get(timeframe, TIMEFRAME_THRESHOLDS["1h"])
    return thresholds["buy"], thresholds["sell"]

# ----------------------------------------------------------------------
# Parametri Ensemble Voting (QUICK WIN OPTIMIZED)
# ----------------------------------------------------------------------
MIN_ENSEMBLE_CONFIDENCE = 0.75   # QUICK WIN: Raised from 0.6 to 0.75 for higher quality
ALLOW_MIXED_SIGNALS = True       # Permetti segnali anche se timeframes discordano
NEUTRAL_SKIP_PROBABILITY = 0.7   # 70% di skipare segnali neutral → più BUY/SELL

# Signal quality parameters
SIGNAL_CONFIDENCE_THRESHOLD = 0.75  # Central configuration for all ensemble systems

# ----------------------------------------------------------------------
# Parametri Class Balancing (UPDATED FOR PERCENTILE LABELING)
# ----------------------------------------------------------------------
USE_SMOTE = False            # DISABLED: Not needed with percentile labeling (guaranteed balance)
USE_CLASS_WEIGHTS = True     # Keep enabled for fine-tuning model training
SMOTE_K_NEIGHBORS = 3        # Kept for potential future use

# ----------------------------------------------------------------------
# Parametri XGBoost Ottimizzati (IMPROVED PERFORMANCE)
# ----------------------------------------------------------------------
XGB_N_ESTIMATORS = 200       # INCREASED: More trees for better learning
XGB_MAX_DEPTH = 4            # REDUCED: Prevent overfitting
XGB_LEARNING_RATE = 0.05     # REDUCED: Slower learning for better generalization
XGB_SUBSAMPLE = 0.7          # REDUCED: More regularization
XGB_COLSAMPLE_BYTREE = 0.7   # REDUCED: Feature bagging for robustness
XGB_REG_ALPHA = 0.1          # INCREASED: More L1 regularization
XGB_REG_LAMBDA = 1.0         # INCREASED: More L2 regularization

# ----------------------------------------------------------------------
# Parametri Validazione
# ----------------------------------------------------------------------
CV_N_SPLITS = 3             # Ridotto da 5 per velocità
MIN_TRAIN_SIZE = 0.6        # Minimum size del training set

# ----------------------------------------------------------------------
# CRITICAL FIX: Centralized Backtest Parameters
# ----------------------------------------------------------------------
BACKTEST_INITIAL_BALANCE = 10000  # Starting capital for backtests
BACKTEST_LEVERAGE = 10            # Leverage for backtest simulation
BACKTEST_BASE_RISK_PCT = 3.0     # Base risk percentage for TP/SL
BACKTEST_SLIPPAGE_PCT = 0.05     # 5% slippage and fees
BACKTEST_TRAILING_ATR_MULTIPLIER = 1.5  # ATR multiplier for trailing

# Ensure consistency between live trading and backtest
assert BACKTEST_LEVERAGE == LEVERAGE, "Backtest and live leverage must match!"

# ----------------------------------------------------------------------
# CRITICAL FIX: Ensemble Voting Weights
# ----------------------------------------------------------------------
TIMEFRAME_WEIGHTS = {
    "15m": 1.0,  # Micro-patterns, high frequency
    "30m": 1.2,  # Balanced view, slight preference
    "1h": 1.5,   # Macro-trends, highest weight (more reliable)
    "4h": 2.0    # Strong trends, maximum weight if used
}
"""
Ensemble voting weights by timeframe:
- Higher timeframes get more weight (more reliable, less noise)
- 1h has 50% more influence than 15m
- Configurable per strategy requirements
"""

# ----------------------------------------------------------------------
# CRITICAL FIX: Centralized Position Limits
# ----------------------------------------------------------------------
MAX_CONCURRENT_POSITIONS = 20  # EMERGENCY FIX: Increased to allow execution despite duplicate positions
"""
Position limits configuration:
- TEMPORARY: 20 positions to work around duplicate position bug
- Risk consideration: Higher exposure but allows bot to function
- TODO: Fix duplicate position tracking bug and reduce back to 3-5
- WARNING: Monitor risk exposure with higher position count
"""

# ----------------------------------------------------------------------
# DATA CACHE SYSTEM CONFIGURATION
# ----------------------------------------------------------------------
ENABLE_DATA_CACHE = True           # Enable/disable cache system
CACHE_DIR = "data_cache"            # Cache directory
CACHE_RETENTION_DAYS = 90           # Days to keep cached data
CACHE_MAX_AGE_MINUTES = 3           # Max age before incremental update
CACHE_AUTO_CLEANUP = True           # Auto cleanup old cache files

# Cache performance thresholds
CACHE_EXPECTED_HIT_RATE = 70        # Expected cache hit rate %
CACHE_API_SAVINGS_TARGET = 80       # Target % of API calls to save

"""
Cache system configuration:
- ENABLE_DATA_CACHE: Master switch for cache system
- CACHE_RETENTION_DAYS: How long to keep historical data in cache
- CACHE_MAX_AGE_MINUTES: How old data can be before requiring update
- Auto-cleanup removes old cache files to save disk space

Performance targets:
- 70%+ cache hit rate expected after warm-up period
- 80%+ API calls savings vs non-cached approach
"""
