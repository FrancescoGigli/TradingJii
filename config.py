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
# ----------------------------------------------------------------------
# Time Synchronization Configuration
# ----------------------------------------------------------------------
TIME_SYNC_MAX_RETRIES = 5              # Maximum sync attempts before giving up
TIME_SYNC_RETRY_DELAY = 3              # Seconds between retry attempts
TIME_SYNC_INITIAL_RECV_WINDOW = 60000  # 60 seconds for initial sync (more tolerant)
TIME_SYNC_NORMAL_RECV_WINDOW = 60000   # INCREASED: 60 seconds for normal operations (prevents desync)
MANUAL_TIME_OFFSET = None              # Optional manual offset in milliseconds (None = auto)

exchange_config = {
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "enableRateLimit": True,
    "options": {
        "adjustForTimeDifference": True,  # Enable automatic time adjustment
        "recvWindow": TIME_SYNC_NORMAL_RECV_WINDOW,  # Use consistent window (60s)
        "timeDifference": 0,  # Will be auto-adjusted by ccxt
    },
}

# Trading parameters
LEVERAGE = 10

# ==============================================================================
# 🎯 DYNAMIC POSITION SIZING - BALANCE-ADAPTIVE SYSTEM
# ==============================================================================
# Sistema dinamico che scala le position size in base al balance disponibile
# Garantisce sempre un numero minimo di posizioni possibili

# Target: numero minimo di posizioni aggressive possibili
# INCREASED: 10 positions for safer sizing with better margin buffer
POSITION_SIZING_TARGET_POSITIONS = 10  # Garantisce almeno 10 posizioni aggressive (più sicuro di 8)

# Ratios tra i tier (mantiene proporzioni 60% / 75% / 100%)
POSITION_SIZING_RATIO_AGGRESSIVE = 1.0      # Base (100%)
POSITION_SIZING_RATIO_MODERATE = 0.75       # 75% dell'aggressive
POSITION_SIZING_RATIO_CONSERVATIVE = 0.60   # 60% dell'aggressive

# Limiti di sicurezza assoluti
POSITION_SIZE_MIN_ABSOLUTE = 15.0   # Mai sotto $15 (troppo piccolo per Bybit)
POSITION_SIZE_MAX_ABSOLUTE = 150.0  # Mai sopra $150 (singola pos troppo grande)

# DEPRECATED: Position Size Tiers fissi (usati solo come fallback)
POSITION_SIZE_CONSERVATIVE = 20.0   # Fallback se dynamic calculation fails
POSITION_SIZE_MODERATE = 30.0       # Fallback se dynamic calculation fails
POSITION_SIZE_AGGRESSIVE = 40.0     # Fallback se dynamic calculation fails

# Thresholds per Position Sizing
CONFIDENCE_HIGH_THRESHOLD = 0.75    # ≥75% confidence = aggressive
CONFIDENCE_LOW_THRESHOLD = 0.65     # <65% confidence = conservative
VOLATILITY_SIZING_LOW = 0.015       # <1.5% volatilità = aggressive
VOLATILITY_SIZING_HIGH = 0.035      # >3.5% volatilità = conservative
ADX_STRONG_TREND = 25.0             # ADX ≥25 = trend forte

# Dynamic Margin Range (per calcoli interni RiskCalculator)
MARGIN_MIN = 15.0                   # Margine minimo assoluto (coerente con POSITION_SIZE_MIN_ABSOLUTE)
MARGIN_MAX = 150.0                  # Margine massimo assoluto (coerente con POSITION_SIZE_MAX_ABSOLUTE)
MARGIN_BASE = 40.0                  # Margine base di partenza (valore medio realistico)

# ==============================================================================
# 📊 VOLATILITY THRESHOLDS
# ==============================================================================
# Soglie per classificare la volatilità del mercato

VOLATILITY_LOW_THRESHOLD = 0.02     # <2% ATR = bassa volatilità
VOLATILITY_HIGH_THRESHOLD = 0.04    # >4% ATR = alta volatilità
# Tra 2-4% = volatilità media

# ==============================================================================
# 🛡️ STOP LOSS & TAKE PROFIT CONFIGURATION
# ==============================================================================
# Stop Loss settings
SL_USE_FIXED = True                  # Use fixed percentage SL (True) or ATR-based (False)
SL_FIXED_PCT = 0.05                  # Fixed 5% stop loss against position
SL_ATR_MULTIPLIER = 1.5              # Multiplier for ATR-based stop loss (if not using fixed)
SL_PRICE_PCT_FALLBACK = 0.06        # 6% fallback if ATR not available
SL_MIN_DISTANCE_PCT = 0.02          # Minimum 2% distance from entry
SL_MAX_DISTANCE_PCT = 0.10          # Maximum 10% distance from entry

# Take Profit settings (NOT USED - positions managed by trailing only)
TP_ENABLED = False                   # Take profit disabled (using trailing stop instead)
TP_RISK_REWARD_RATIO = 2.0          # 2:1 reward:risk ratio
TP_MAX_PROFIT_PCT = 0.15            # Maximum 15% profit target
TP_MIN_PROFIT_PCT = 0.03            # Minimum 3% profit target

# ==============================================================================
# 🎪 TRAILING STOP CONFIGURATION (OPTIMIZED)
# ==============================================================================
# Dynamic trailing stop that follows price at fixed distance

# Master switch
TRAILING_ENABLED = True              # Enable trailing stop system

# Activation trigger
TRAILING_TRIGGER_PCT = 0.01          # Activate at +1% price movement (+10% with 10x leverage)

# Protection strategy (NEW SYSTEM)
TRAILING_DISTANCE_PCT = 0.10         # Keep SL at -10% from CURRENT price (not max profit)
TRAILING_DISTANCE_OPTIMAL = 0.08     # Optimal position: -8% from current price
TRAILING_DISTANCE_UPDATE = 0.10      # Update threshold: when SL reaches -10% from current

# Update settings (optimized for performance)
TRAILING_UPDATE_INTERVAL = 30        # Check every 30 seconds (more responsive)
TRAILING_MIN_CHANGE_PCT = 0.01       # Only update SL if change >1% (reduce API calls)

# Performance optimizations
TRAILING_SILENT_MODE = True          # Minimal logging (only important events)
TRAILING_USE_BATCH_FETCH = True      # Batch fetch prices for multiple positions
TRAILING_USE_CACHE = True            # Leverage SmartAPIManager cache (70-90% hit rate)

# Safety limits
TRAILING_MAX_POSITIONS = 20          # Max positions to monitor simultaneously
TRAILING_MIN_PROFIT_TO_ACTIVATE = 0.005  # Minimum 0.5% profit before activation check

# ==============================================================================
# 📡 SMART API MANAGER CACHE CONFIG
# ==============================================================================
# Configurazione cache intelligente per riduzione API calls

# Cache TTL (Time To Live) in secondi
API_CACHE_POSITIONS_TTL = 30          # Positions cache: 30s TTL
API_CACHE_TICKERS_TTL = 15            # Tickers cache: 15s TTL
API_CACHE_BATCH_TTL = 20              # Batch operations cache: 20s TTL

# Rate Limiting Protection
API_RATE_LIMIT_MAX_CALLS = 100        # Max 100 calls per minute (conservative)
API_RATE_LIMIT_WINDOW = 60            # 60 seconds window

# Real-time position display configuration
REALTIME_DISPLAY_ENABLED = True
REALTIME_DISPLAY_INTERVAL = 1.0
REALTIME_PRICE_CACHE_TTL = 2
REALTIME_MAX_API_CALLS = 60
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
# Position Limits & Sizing Strategy
# ----------------------------------------------------------------------
# NUOVO SISTEMA: Portfolio-based dynamic sizing
# - Max 10 posizioni per volta (balance diviso per 10)
# - Usa tutto il balance disponibile
# - Più margin ai segnali migliori (ordinati per confidence)

MAX_CONCURRENT_POSITIONS = 10  # INCREASED: 10 positions for safer risk distribution

# Pesi per position sizing (da posizione 1 a 10)
# Posizione 1 = migliore confidence, riceve più margin
# Posizione 10 = peggiore confidence, riceve meno margin
POSITION_SIZING_WEIGHTS = [1.5, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6]

# Percentuale del balance da usare (default 98% per lasciare buffer)
PORTFOLIO_BALANCE_USAGE = 0.98

# ==============================================================================
# 🧹 FRESH START MODE
# ==============================================================================
# Modalità fresh start: chiude tutte le posizioni e resetta file all'avvio
# Utile per:
# - Testing di fix/modifiche con ambiente pulito
# - Forzare reload di codice aggiornato
# - Ripartire da zero senza posizioni esistenti

# Master switch
FRESH_START_MODE = False  # False = NON chiudere posizioni all'avvio (raccomandato)

# Opzioni granulari (cosa resettare)
FRESH_START_OPTIONS = {
    'close_all_positions': True,      # Chiudi tutte le posizioni su Bybit
    'clear_position_json': True,      # Cancella thread_safe_positions.json
    'clear_learning_state': False,    # Mantieni learning history (raccomandato)
    'clear_rl_model': False,          # MANTIENI RL agent addestrato (NON cancellare!)
    'log_detailed_cleanup': True      # Log dettagliato operazioni di cleanup
}

# Esempi di configurazione per diversi scenari:
#
# SCENARIO 1: Trading Normale (raccomandato)
# FRESH_START_MODE = False  # Protegge posizioni esistenti e modello RL
#
# SCENARIO 2: Chiusura Posizioni (senza reset modelli)
# FRESH_START_MODE = True
# FRESH_START_OPTIONS = {
#     'close_all_positions': True,
#     'clear_position_json': True,
#     'clear_learning_state': False,  # Mantieni history!
#     'clear_rl_model': False,        # Mantieni modello addestrato!
#     'log_detailed_cleanup': True
# }
#
# SCENARIO 3: Reset TOTALE (solo per debugging)
# FRESH_START_MODE = True
# FRESH_START_OPTIONS = {
#     'close_all_positions': True,
#     'clear_position_json': True,
#     'clear_learning_state': True,   # Reset learning
#     'clear_rl_model': True,         # Reset RL (attenzione!)
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
