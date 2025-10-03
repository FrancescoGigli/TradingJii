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
import logging
from pathlib import Path

# ----------------------------------------------------------------------
# Carica il file .env se presente (richiede python-dotenv)
# ----------------------------------------------------------------------
try:
    from dotenv import load_dotenv, find_dotenv

    _env_file = find_dotenv()
    if _env_file:
        load_dotenv(_env_file, override=False)  # NON sovrascrive variabili già settate
except ModuleNotFoundError:  # libreria non installata
    pass  # il codice funzionerà comunque se le variabili sono nel sistema

# ----------------------------------------------------------------------
# Modalità Demo/Test
# ----------------------------------------------------------------------
DEMO_MODE = False  # Default: False (LIVE mode), può essere modificato da ConfigManager
DEMO_BALANCE = 1000.0  # Balance USDT fittizio per modalità demo

# ----------------------------------------------------------------------
# Credenziali Bybit
# ----------------------------------------------------------------------
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

if not API_KEY or not API_SECRET:
    if not DEMO_MODE:
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
        "adjustForTimeDifference": True,  # Enable automatic time adjustment
        "recvWindow": 180_000,  # 180 seconds (3 minutes) tolerance window for timestamp sync
        "timeDifference": 0,  # Will be auto-adjusted by ccxt
    },
}

# Trading parameters
LEVERAGE = 10

# ==============================================================================
# 🎯 DYNAMIC POSITION SIZING - 3-TIER SYSTEM (50/75/100 USD)
# ==============================================================================
# Sistema intelligente che adatta la size della posizione in base a:
# - Confidence del segnale ML
# - Volatilità del mercato
# - Forza del trend (ADX)

# Position Size Tiers
POSITION_SIZE_CONSERVATIVE = 50.0   # Trade rischioso (alta volatilità o bassa confidence)
POSITION_SIZE_MODERATE = 75.0       # Trade medio (volatilità normale, confidence media)
POSITION_SIZE_AGGRESSIVE = 100.0    # Trade sicuro (bassa volatilità, alta confidence)

# Thresholds per Position Sizing
CONFIDENCE_HIGH_THRESHOLD = 0.75    # ≥75% confidence = aggressive
CONFIDENCE_LOW_THRESHOLD = 0.65     # <65% confidence = conservative
VOLATILITY_SIZING_LOW = 0.015       # <1.5% volatilità = aggressive
VOLATILITY_SIZING_HIGH = 0.035      # >3.5% volatilità = conservative
ADX_STRONG_TREND = 25.0             # ADX ≥25 = trend forte

# Dynamic Margin Range (per calcoli interni RiskCalculator)
MARGIN_MIN = 50.0                   # Margine minimo assoluto (coerente con POSITION_SIZE_CONSERVATIVE)
MARGIN_MAX = 100.0                  # Margine massimo assoluto
MARGIN_BASE = 50.0                  # Margine base di partenza

# ==============================================================================
# 🛡️ STOP LOSS CONFIGURATION
# ==============================================================================
# Stop loss basato su ATR (Average True Range) per adattarsi alla volatilità

SL_ATR_MULTIPLIER = 2.0             # Stop loss = 2x ATR dal prezzo di entrata
SL_PRICE_PCT_FALLBACK = 0.06        # 6% fallback se ATR non disponibile
SL_MIN_DISTANCE_PCT = 0.02          # Distanza minima 2% (sicurezza)
SL_MAX_DISTANCE_PCT = 0.10          # Distanza massima 10% (contenimento rischio)

# ==============================================================================
# 🎯 TAKE PROFIT CONFIGURATION
# ==============================================================================
# Take profit basato su risk-reward ratio

TP_RISK_REWARD_RATIO = 1.5          # Target 1.5x il rischio (es: rischio 4% → target 6%)
TP_MAX_PROFIT_PCT = 0.08            # Profitto massimo 8% (realismo)
TP_MIN_PROFIT_PCT = 0.02            # Profitto minimo 2% (sensatezza)

# ==============================================================================
# 📊 VOLATILITY THRESHOLDS
# ==============================================================================
# Soglie per classificare la volatilità del mercato

VOLATILITY_LOW_THRESHOLD = 0.02     # <2% ATR = bassa volatilità
VOLATILITY_HIGH_THRESHOLD = 0.04    # >4% ATR = alta volatilità
# Tra 2-4% = volatilità media

# ==============================================================================
# 🔄 TRAILING STOP CONFIGURATION
# ==============================================================================
# Trailing stop dinamico che segue il prezzo quando il trade è in profitto

# Trailing Trigger (quando attivare il trailing)
TRAILING_TRIGGER_BASE_PCT = 0.10      # 10% profitto base per attivazione
TRAILING_TRIGGER_MIN_PCT = 0.05       # 5% minimo per alta volatilità  
TRAILING_TRIGGER_MAX_PCT = 0.10       # 10% massimo per bassa volatilità

# Trailing Distance (distanza dal best price)
TRAILING_DISTANCE_LOW_VOL = 0.010     # 1.0% per bassa volatilità (tight trailing)
TRAILING_DISTANCE_MED_VOL = 0.008     # 0.8% per media volatilità
TRAILING_DISTANCE_HIGH_VOL = 0.007    # 0.7% per alta volatilità (wider trailing)

# ==============================================================================
# 🔙 LEGACY COMPATIBILITY
# ==============================================================================
# Aliases per backward compatibility con vecchi moduli (verranno deprecati)

MARGIN_BASE_USDT = MARGIN_BASE                    # For trade_manager.py
INITIAL_SL_PRICE_PCT = SL_PRICE_PCT_FALLBACK      # For trailing_stop_manager.py
INITIAL_SL_MARGIN_LOSS_PCT = 0.4                  # Legacy: 40% margin loss

# ==============================================================================
# ⚡ TRAILING MONITOR OPERATIONAL CONFIG
# ==============================================================================
# Configurazione tecnica del trailing monitor (non toccare senza motivo)

# High-frequency trailing monitor configuration
TRAILING_MONITOR_INTERVAL = 30        
TRAILING_MONITOR_ENABLED = True       # ENABLED - Real-time trailing active
TRAILING_PRICE_CACHE_TTL = 60
TRAILING_MAX_API_CALLS_PER_MIN = 120

TRAILING_ERROR_RECOVERY_DELAY = 10    
TRAILING_MAX_CONSECUTIVE_ERRORS = 5   
TRAILING_ENABLE_LOGGING = True        

# Real-time position display configuration
REALTIME_DISPLAY_ENABLED = True
REALTIME_DISPLAY_INTERVAL = 1.0
REALTIME_PRICE_CACHE_TTL = 2
REALTIME_MAX_API_CALLS = 60

REALTIME_SHOW_TRIGGERS = True
REALTIME_SHOW_TRAILING_INFO = True
REALTIME_COLOR_CODING = True

ENABLED_TIMEFRAMES: list[str] = ["15m", "30m", "1h"]
TIMEFRAME_DEFAULT: str | None = "15m"

# Uniform Time Window for Multi-Timeframe Ensemble
LOOKBACK_HOURS = 6  

TIMEFRAME_TIMESTEPS = {
    "1m": int(LOOKBACK_HOURS * 60 / 1),    
    "3m": int(LOOKBACK_HOURS * 60 / 3),    
    "5m": int(LOOKBACK_HOURS * 60 / 5),    
    "15m": int(LOOKBACK_HOURS * 60 / 15),  
    "30m": int(LOOKBACK_HOURS * 60 / 30),  
    "1h": int(LOOKBACK_HOURS / 1),         
    "4h": max(2, int(LOOKBACK_HOURS / 4)), 
    "1d": max(1, int(LOOKBACK_HOURS / 24))
}

def get_timesteps_for_timeframe(timeframe: str) -> int:
    timesteps = TIMEFRAME_TIMESTEPS.get(timeframe, 7)
    return max(2, timesteps)  # Minimo 2 candele sempre

# ----------------------------------------------------------------------
# Features
# ----------------------------------------------------------------------
EXPECTED_COLUMNS = [
    "open", "high", "low", "close", "volume",
    "ema5", "ema10", "ema20",
    "macd", "macd_signal", "macd_histogram",
    "rsi_fast", "stoch_rsi",
    "atr", "bollinger_hband", "bollinger_lband",
    "vwap", "obv",
    "adx",
    "volatility",
    "price_pos_5", "price_pos_10", "price_pos_20",
    "vol_acceleration", "atr_norm_move", "momentum_divergence",
    "volatility_squeeze", "resistance_dist_10", "resistance_dist_20",
    "support_dist_10", "support_dist_20", "price_acceleration",
    "vol_price_alignment"
]

# Numero di feature finali = 2x EXPECTED_COLUMNS (corrente + trend)
N_FEATURES_FINAL = len(EXPECTED_COLUMNS) * 2

MODEL_RATES = {"xgb": 1.0}

NEUTRAL_LOWER_THRESHOLD = 0.40
NEUTRAL_UPPER_THRESHOLD = 0.60
COLOR_THRESHOLD_GREEN = 0.65
COLOR_THRESHOLD_RED = 0.35

TRADE_CYCLE_INTERVAL = 900  # 15 minuti
DATA_LIMIT_DAYS = 180
WARMUP_PERIODS = 30    

# ----------------------------------------------------------------------
# Percorsi modelli
# ----------------------------------------------------------------------
_TRAINED_DIR = Path(__file__).resolve().with_name("trained_models")
_TRIANED_DIR = _TRAINED_DIR.mkdir(exist_ok=True)

def get_xgb_model_file(tf: str) -> str: 
    return str(_TRAINED_DIR / f"xgb_model_{tf}.pkl")

def get_xgb_scaler_file(tf: str) -> str: 
    return str(_TRAINED_DIR / f"xgb_scaler_{tf}.pkl")

# ----------------------------------------------------------------------
# Symbols
# ----------------------------------------------------------------------
EXCLUDED_SYMBOLS = []  
AUTO_EXCLUDE_INSUFFICIENT_DATA = True

# Symbols to exclude ONLY from trading (still used for training)
EXCLUDED_FROM_TRADING = ["BTC/USDT:USDT", "ETH/USDT:USDT"]
MIN_REQUIRED_CANDLES = 50
EXCLUDED_SYMBOLS_FILE = "excluded_symbols.txt"  

TOP_SYMBOLS_COUNT = 50
TOP_TRAIN_CRYPTO = TOP_SYMBOLS_COUNT
TOP_ANALYSIS_CRYPTO = TOP_SYMBOLS_COUNT

MIN_VOLUME_THRESHOLD = 1_000_000  
MIN_PRICE_THRESHOLD = 0.001      

RSI_THRESHOLDS = {"sideways": {"oversold": 30, "overbought": 70}}
TRAIN_IF_NOT_FOUND = True

# ----------------------------------------------------------------------
# Swing Points Labeling
# ----------------------------------------------------------------------
SWING_ORDER = 2
SWING_ATR_FACTOR = 0.3
SWING_VOLUME_FACTOR = 1.0

# ----------------------------------------------------------------------
# Future Returns Labeling
# ----------------------------------------------------------------------
FUTURE_RETURN_STEPS = 3      

TIMEFRAME_THRESHOLDS = {
    "15m": {"buy": 0.008, "sell": -0.008},  
    "30m": {"buy": 0.012, "sell": -0.012},  
    "1h": {"buy": 0.015, "sell": -0.015},   
    "4h": {"buy": 0.025, "sell": -0.025},   
    "1d": {"buy": 0.04, "sell": -0.04}      
}

RETURN_BUY_THRESHOLD = TIMEFRAME_THRESHOLDS["1h"]["buy"]
RETURN_SELL_THRESHOLD = TIMEFRAME_THRESHOLDS["1h"]["sell"]

def get_thresholds_for_timeframe(timeframe: str) -> tuple[float, float]:
    thresholds = TIMEFRAME_THRESHOLDS.get(timeframe, TIMEFRAME_THRESHOLDS["1h"])
    return thresholds["buy"], thresholds["sell"]

# ----------------------------------------------------------------------
# Ensemble Voting
# ----------------------------------------------------------------------
MIN_ENSEMBLE_CONFIDENCE = 0.75
ALLOW_MIXED_SIGNALS = True
NEUTRAL_SKIP_PROBABILITY = 0.7
SIGNAL_CONFIDENCE_THRESHOLD = 0.75

# ----------------------------------------------------------------------
# Class Balancing
# ----------------------------------------------------------------------
USE_SMOTE = False
USE_CLASS_WEIGHTS = True
SMOTE_K_NEIGHBORS = 3

# ----------------------------------------------------------------------
# XGBoost
# ----------------------------------------------------------------------
XGB_N_ESTIMATORS = 200
XGB_MAX_DEPTH = 4
XGB_LEARNING_RATE = 0.05
XGB_SUBSAMPLE = 0.7
XGB_COLSAMPLE_BYTREE = 0.7
XGB_REG_ALPHA = 0.1
XGB_REG_LAMBDA = 1.0

# ----------------------------------------------------------------------
# Validazione
# ----------------------------------------------------------------------
CV_N_SPLITS = 3
MIN_TRAIN_SIZE = 0.6

# ----------------------------------------------------------------------
# Backtest
# ----------------------------------------------------------------------
BACKTEST_INITIAL_BALANCE = 10000
BACKTEST_LEVERAGE = 10
BACKTEST_BASE_RISK_PCT = 3.0
BACKTEST_SLIPPAGE_PCT = 0.05
BACKTEST_TRAILING_ATR_MULTIPLIER = 1.5

if BACKTEST_LEVERAGE != LEVERAGE:
    logging.warning("⚠️ Backtest leverage (%s) diverso da live leverage (%s)", 
                    BACKTEST_LEVERAGE, LEVERAGE)

# ----------------------------------------------------------------------
# Ensemble Weights
# ----------------------------------------------------------------------
TIMEFRAME_WEIGHTS = {
    "15m": 1.0,
    "30m": 1.2,
    "1h": 1.5,
    "4h": 2.0
}

# ----------------------------------------------------------------------
# Position Limits
# ----------------------------------------------------------------------
MAX_CONCURRENT_POSITIONS = 20  

# ==============================================================================
# 🧹 FRESH START MODE
# ==============================================================================
# Modalità fresh start: chiude tutte le posizioni e resetta file all'avvio
# Utile per:
# - Testing di fix/modifiche con ambiente pulito
# - Forzare reload di codice aggiornato
# - Ripartire da zero senza posizioni esistenti

# Master switch
FRESH_START_MODE = True  # True = chiudi tutto e ripulisci all'avvio

# Opzioni granulari (cosa resettare)
FRESH_START_OPTIONS = {
    'close_all_positions': True,      # Chiudi tutte le posizioni su Bybit
    'clear_position_json': True,      # Cancella thread_safe_positions.json
    'clear_learning_state': False,    # Mantieni learning history (raccomandato)
    'clear_rl_model': True,           # Reset RL agent (threshold 0.40!)
    'clear_decisions': False,         # Mantieni decision files per analisi
    'clear_postmortem': False,        # Mantieni post-mortem files per analisi
    'log_detailed_cleanup': True      # Log dettagliato operazioni di cleanup
}

# Esempi di configurazione per diversi scenari:
#
# SCENARIO 1: Testing Fix (reset threshold RL)
# FRESH_START_MODE = True
# FRESH_START_OPTIONS = {
#     'close_all_positions': True,
#     'clear_position_json': True,
#     'clear_learning_state': False,  # Mantieni history
#     'clear_rl_model': True,         # Reset threshold vecchi!
#     'clear_decisions': False,
#     'clear_postmortem': False,
#     'log_detailed_cleanup': True
# }
#
# SCENARIO 2: Trading Normale (default)
# FRESH_START_MODE = False  # Protegge posizioni esistenti
#
# SCENARIO 3: Pulizia Settimanale
# FRESH_START_MODE = True
# FRESH_START_OPTIONS = {
#     'close_all_positions': True,
#     'clear_position_json': True,
#     'clear_learning_state': False,  # Mantieni learning!
#     'clear_rl_model': False,
#     'clear_decisions': True,        # Pulisci files vecchi
#     'clear_postmortem': True,
#     'log_detailed_cleanup': True
# }
#
# SCENARIO 4: Reset TOTALE (debugging)
# FRESH_START_MODE = True
# FRESH_START_OPTIONS = {  # Tutto True = tabula rasa completa
#     'close_all_positions': True,
#     'clear_position_json': True,
#     'clear_learning_state': True,
#     'clear_rl_model': True,
#     'clear_decisions': True,
#     'clear_postmortem': True,
#     'log_detailed_cleanup': True
# }

# ----------------------------------------------------------------------
# Data Cache
# ----------------------------------------------------------------------
ENABLE_DATA_CACHE = True
CACHE_DIR = "data_cache"
CACHE_RETENTION_DAYS = 90
CACHE_MAX_AGE_MINUTES = 3
CACHE_AUTO_CLEANUP = True

CACHE_EXPECTED_HIT_RATE = 70        
CACHE_API_SAVINGS_TARGET = 80
