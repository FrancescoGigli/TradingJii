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
# Logging Mode
# ----------------------------------------------------------------------
QUIET_MODE = True  # True = minimal logs (summary only), False = detailed logs

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
TIME_SYNC_INITIAL_RECV_WINDOW = 120000 # 120 seconds for initial sync (more tolerant)
TIME_SYNC_NORMAL_RECV_WINDOW = 300000  # INCREASED: 120 seconds for normal operations (prevents desync)
MANUAL_TIME_OFFSET = 0             # CRITICAL FIX: Manual -2.5s offset to compensate for local clock drift

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
# 🎯 POSITION SIZING SYSTEM SELECTOR
# ==============================================================================
# Choose between FIXED (legacy) or ADAPTIVE (new) position sizing

ADAPTIVE_SIZING_ENABLED = True  # True = Adaptive (learns from results), False = Fixed 3-tier

# ==============================================================================
# 🎯 ADAPTIVE POSITION SIZING (NEW SYSTEM)
# ==============================================================================
# Sistema adattivo che impara dalle performance reali per simbolo
# - Premia monete vincenti aumentando size
# - Punisce monete perdenti bloccandole per 3 cicli
# - Si auto-adatta al wallet growth

# Session Management
ADAPTIVE_FRESH_START = True          # ⚠️ True = Reset stats e riparti da capo | False = Continua con stats esistenti
                                     # Se True: cancella tutte le statistiche storiche e ricomincia
                                     # Se False: mantiene win/loss rate e continua l'apprendimento

# Wallet structure
ADAPTIVE_WALLET_BLOCKS = 5           # Divide wallet in N blocks (5 blocks = wallet/5 per position)
ADAPTIVE_FIRST_CYCLE_FACTOR = 0.5    # First cycle uses 50% of block (prudent start)

# Penalty system
ADAPTIVE_BLOCK_CYCLES = 3            # Block losing symbols for N cycles
ADAPTIVE_CAP_MULTIPLIER = 1.0        # Max size = slot_value × multiplier

# Risk management
ADAPTIVE_RISK_MAX_PCT = 0.20         # Max 20% wallet at risk (total max loss)
ADAPTIVE_LOSS_MULTIPLIER = 0.30      # Stop loss = 30% of margin (with 10x leverage)

# Memory persistence
ADAPTIVE_MEMORY_FILE = "adaptive_sizing_memory.json"  # File for symbol memory

# ==============================================================================
# 🎯 FIXED POSITION SIZING (LEGACY SYSTEM)
# ==============================================================================
# Sistema semplice con sizing fisso basato su confidence
# (Used only if ADAPTIVE_SIZING_ENABLED = False)

# Fixed position sizes (margin per trade)
POSITION_SIZE_CONSERVATIVE = 15.0   # Low confidence (<65%)
POSITION_SIZE_MODERATE = 20.0       # Medium confidence (65-75%)
POSITION_SIZE_AGGRESSIVE = 25.0     # High confidence (>75%)

# Limiti assoluti
POSITION_SIZE_MIN_ABSOLUTE = 15.0   # Minimo assoluto
POSITION_SIZE_MAX_ABSOLUTE = 50.0   # Massimo assoluto

# Position sizing target (for backwards compatibility)
POSITION_SIZING_TARGET_POSITIONS = 10  # Target number of positions

# Position sizing ratios (relative to aggressive tier)
# Conservative = 60% of aggressive, Moderate = 80% of aggressive, Aggressive = 100%
POSITION_SIZING_RATIO_CONSERVATIVE = 0.6   # 15/25 = 0.6
POSITION_SIZING_RATIO_MODERATE = 0.8       # 20/25 = 0.8
POSITION_SIZING_RATIO_AGGRESSIVE = 1.0     # 25/25 = 1.0

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
# Stop Loss settings (OPTIMIZED FOR BETTER RISK/REWARD)
# NEW: -3% price = -30% ROE with 10x leverage (was -50% ROE)
SL_USE_FIXED = True                  # Use fixed percentage SL (True) or ATR-based (False)
SL_FIXED_PCT = 0.03                  # IMPROVED: 3% stop loss (was 5%) = -30% ROE max risk
SL_ATR_MULTIPLIER = 1.5              # Multiplier for ATR-based stop loss (if not using fixed)
SL_PRICE_PCT_FALLBACK = 0.04         # 4% fallback if ATR not available (was 6%)
SL_MIN_DISTANCE_PCT = 0.015          # Minimum 1.5% distance from entry (was 2%)
SL_MAX_DISTANCE_PCT = 0.08           # Maximum 8% distance from entry (was 10%)

# ==============================================================================
# 🎯 ADAPTIVE STOP LOSS (CONFIDENCE-BASED)
# ==============================================================================
# Adjust SL based on confidence levels
SL_ADAPTIVE_ENABLED = True           # Enable adaptive SL based on confidence
SL_LOW_CONFIDENCE = 0.025            # 2.5% SL (-25% ROE) for low confidence (<70%)
SL_MED_CONFIDENCE = 0.03             # 3.0% SL (-30% ROE) for medium confidence (70-80%)
SL_HIGH_CONFIDENCE = 0.035           # 3.5% SL (-35% ROE) for high confidence (>80%)

# ==============================================================================
# 🚨 EARLY EXIT SYSTEM
# ==============================================================================
# Exit trades early if they show immediate weakness
EARLY_EXIT_ENABLED = True            # Enable early exit system

# Fast reversal detection (first 15 minutes)
EARLY_EXIT_FAST_REVERSAL_ENABLED = True
EARLY_EXIT_FAST_TIME_MINUTES = 15    # Check within first 15 minutes
EARLY_EXIT_FAST_DROP_ROE = -15       # Exit if drops to -15% ROE quickly

# Immediate reversal detection (first 5 minutes)
EARLY_EXIT_IMMEDIATE_ENABLED = True
EARLY_EXIT_IMMEDIATE_TIME_MINUTES = 5  # Check within first 5 minutes
EARLY_EXIT_IMMEDIATE_DROP_ROE = -10    # Exit if drops to -10% ROE immediately

# Persistent weakness detection (first 60 minutes)
EARLY_EXIT_PERSISTENT_ENABLED = True
EARLY_EXIT_PERSISTENT_TIME_MINUTES = 60  # Check within first hour
EARLY_EXIT_PERSISTENT_DROP_ROE = -5      # Exit if stays -5% ROE persistently

# Take Profit settings (NOT USED - positions managed by trailing only)
TP_ENABLED = False                   # Take profit disabled (using trailing stop instead)
TP_RISK_REWARD_RATIO = 2.0          # 2:1 reward:risk ratio
TP_MAX_PROFIT_PCT = 0.15            # Maximum 15% profit target
TP_MIN_PROFIT_PCT = 0.03            # Minimum 3% profit target

# ==============================================================================
# 🎪 TRAILING STOP CONFIGURATION (OPTIMIZED FOR BETTER R/R)
# ==============================================================================
# Dynamic trailing stop that follows price at fixed distance

# Master switch
TRAILING_ENABLED = True              # Enable trailing stop system
TRAILING_SILENT_MODE = True          # Minimal logging (only important events)

# Activation trigger (IMPROVED: Let winners run more)
# NEW: +1.5% price = +15% ROE activation (was +10% ROE)
TRAILING_TRIGGER_PCT = 0.015         # IMPROVED: Activate at +1.5% price (+15% ROE with 10x leverage)

# Protection strategy (ROE-BASED SYSTEM)
# CRITICAL: Distances are in ROE% (Return On Equity), NOT price%!
# IMPROVED: More breathing room for profit taking
TRAILING_DISTANCE_PCT = 0.10         # Legacy (not used)
TRAILING_DISTANCE_ROE_OPTIMAL = 0.10 # IMPROVED: Protect all but last 10% ROE (was 8%)
TRAILING_DISTANCE_ROE_UPDATE = 0.12  # IMPROVED: Update when 12% ROE away (was 10%)

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

# Numero di feature finali = 66 (actual features created by temporal system)
# Breakdown: 33 current + 27 momentum + 6 critical stats = 66
N_FEATURES_FINAL = 66

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
_TRAINED_DIR.mkdir(exist_ok=True)

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
# PORTFOLIO SIZING OPTIMIZATION with IM 15%
# 
# With 10x leverage and Initial Margin = 15% of notional:
# - Margin per position = position_size × leverage × IM% = position_size × 1.5
# - Max concurrent positions depends on available balance
#
# CALCULATION EXAMPLES (with min position size $15):
# Balance $100:  100 / (15 × 1.5) = 4.4 positions
# Balance $150:  150 / (15 × 1.5) = 6.6 positions  
# Balance $200:  200 / (15 × 1.5) = 8.8 positions
# Balance $300:  300 / (15 × 1.5) = 13.3 positions
#
# STRATEGY: Set limit to 10, let RiskCalculator dynamically size positions based on:
# - Available balance
# - ML confidence (higher = more weight)
# - Volatility (lower = more weight, safer)
# - Trend strength ADX (stronger = more weight)

# ADAPTIVE SIZING: Max positions = wallet blocks (5)
# With adaptive sizing enabled, this limit must match ADAPTIVE_WALLET_BLOCKS
MAX_CONCURRENT_POSITIONS = 5  # Aligned with ADAPTIVE_WALLET_BLOCKS for adaptive sizing

# DEPRECATED: Position sizing weights (replaced by dynamic risk-weighted system)
# See: RiskCalculator.calculate_portfolio_based_margins()

# Percentage of balance to use (default 98% to leave buffer)
PORTFOLIO_BALANCE_USAGE = 0.98

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

# ==============================================================================
# 🧠 ADAPTIVE LEARNING SYSTEM - DISABLED
# ==============================================================================
ADAPTIVE_LEARNING_ENABLED = False  # Sistema disabilitato - rimosso codice complesso
