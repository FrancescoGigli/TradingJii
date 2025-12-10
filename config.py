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
DEMO_MODE = False  # LIVE MODE - Trading con soldi veri (CONFERMATO)
DEMO_BALANCE = 1000.0  # Balance USDT fittizio per modalità demo (non usato in live)

# ----------------------------------------------------------------------
# Logging Mode - NEW: Multi-level verbosity
# ----------------------------------------------------------------------
# Possible values: "MINIMAL", "NORMAL", "DETAILED"
# MINIMAL: Only critical events (trades opened/closed, P&L summary)
# NORMAL: Standard operations (signals, risk checks, trailing updates)
# DETAILED: Full debug information (all operations, calculations, API calls)
LOG_VERBOSITY = "NORMAL"  # Changed to NORMAL for detailed tables

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
LEVERAGE = 5  # ⚡ MODIFICATO: Leva 5x per ridurre il rischio (con SL 6% = -30% ROE)

# ==============================================================================
# 🎯 FIXED POSITION SIZING (SIMPLIFIED)
# ==============================================================================
# Sistema semplificato: tutte le posizioni usano la stessa size fissa

FIXED_POSITION_SIZE_ENABLED = True   # Force fixed size for all trades
FIXED_POSITION_SIZE_AMOUNT = 15.0    # Always open at $15 Margin

# Safety limit - minimum margin to avoid too small positions on expensive assets
MIN_MARGIN = 10.0  # Minimum $10 margin per position (prevents tiny positions on high-price assets)

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
# MASTER STOP LOSS PARAMETER (used by both training and runtime)
# This ensures ML learns with the same SL that will be used in live trading
STOP_LOSS_PCT = 0.06                 # ⚡ MODIFICATO: 6% stop loss = -30% ROE con leva 5x (protezione bilanciata)

# ==============================================================================
# Stop Loss: ALWAYS FIXED at 6%
# ==============================================================================
# Simple and predictable stop loss system:
# - LONG positions: SL = entry_price × 0.94 (-6% from entry)
# - SHORT positions: SL = entry_price × 1.06 (+6% from entry)
# - With 5x leverage: -6% price = -30% ROE
# 
# Protection layers (in order):
# 1. Early Exit: Exits before SL if rapid crash detected (-10%/-15% ROE)
# 2. Fixed SL: Hard stop at -6% price / -30% ROE
# 3. Trailing Stop: Locks profits when trade goes in profit
#
# NO adaptive/confidence-based SL - keeps system simple and predictable

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
EARLY_EXIT_IMMEDIATE_DROP_ROE = -12    # ⚡ OPZIONE B: Exit if drops to -12% ROE (more patient)

# Persistent weakness detection (first 60 minutes)
EARLY_EXIT_PERSISTENT_ENABLED = True
EARLY_EXIT_PERSISTENT_TIME_MINUTES = 60  # Check within first hour
EARLY_EXIT_PERSISTENT_DROP_ROE = -5      # Exit if stays -5% ROE persistently

# ==============================================================================
# 🎯 TAKE PROFIT SYSTEM (DISABLED - Using trailing stop only)
# ==============================================================================
TP_ENABLED = False  # SPIKE OPTIMIZED: Disabled, let trailing stop manage exits
TP_ROE_TARGET = 0.60                 # +60% ROE target
TP_RISK_REWARD_RATIO = 2.5           # TP must be 2.5x farther than SL (R/R ratio)
TP_MIN_DISTANCE_FROM_SL = TP_RISK_REWARD_RATIO  # Alias for compatibility
TP_PERCENTAGE_TO_CLOSE = 1.0         # Close 100% of position at TP
TP_MAX_PROFIT_PCT = 0.15             # Maximum 15% profit target
TP_MIN_PROFIT_PCT = 0.03             # Minimum 3% profit target

# ==============================================================================
# 🎪 TRAILING STOP: SPIKE OPTIMIZED (Early activation +15% ROE)
# ==============================================================================
# Aggressive trailing stop for spike catching - NO TAKE PROFIT

# Master switch
TRAILING_ENABLED = True              # Enable trailing stop system
TRAILING_SILENT_MODE = False         # SPIKE OPTIMIZED: Verbose to see trailing action

# EARLY ACTIVATION for spike catching (+12% ROE = +2.4% price with 5x leverage)
TRAILING_TRIGGER_PCT = 0.015         # Legacy (not used with ROE system)
TRAILING_TRIGGER_ROE = 0.12          # ⚡ MODIFICATO: Activate at +12% ROE (cattura profitti aggressiva)

# BALANCED PROTECTION (8% ROE breathing room to let it run)
TRAILING_DISTANCE_PCT = 0.10         # Legacy (not used)
TRAILING_DISTANCE_ROE_OPTIMAL = 0.08 # OPTIMIZED: Protect all but last 8% ROE (was 4%)
TRAILING_DISTANCE_ROE_UPDATE = 0.12  # OPTIMIZED: Update when 12% ROE away (was 6%)

# Update settings (optimized for performance)
TRAILING_UPDATE_INTERVAL = 60        # ⚡ OTTIMIZZATO: Check ogni 60s (era 30s) - riduce chiamate API
TRAILING_MIN_CHANGE_PCT = 0.005      # SPIKE OPTIMIZED: Update if >0.5% change (was 1%)

# Performance optimizations
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
API_CACHE_POSITIONS_TTL = 60          # ⚡ Positions cache: 60s TTL (era 30s)
API_CACHE_TICKERS_TTL = 30            # ⚡ Tickers cache: 30s TTL (era 15s)
API_CACHE_BATCH_TTL = 45              # ⚡ Batch operations cache: 45s TTL (era 20s)

# Rate Limiting Protection
API_RATE_LIMIT_MAX_CALLS = 100        # Max 100 calls per minute (conservative)
API_RATE_LIMIT_WINDOW = 60            # 60 seconds window

# ==============================================================================
# 🔄 POSITION SYNC OPTIMIZATION
# ==============================================================================
# Controlla la frequenza dei sync completi con Bybit per ridurre API calls

# Position sync interval (in seconds)
POSITION_SYNC_INTERVAL = 60           # ⚡ Sync completo ogni 60s (invece che ogni ciclo trailing)
                                      # Questo riduce drasticamente le chiamate API mantenendo dati aggiornati
                                      
# Sync immediato dopo apertura/chiusura
POSITION_SYNC_AFTER_TRADE = True      # Sync immediato dopo apertura/chiusura posizione

# Sync ridondante dopo set SL
POSITION_SYNC_AFTER_SL_SET = False    # ⚡ DISABILITATO: evita sync ridondante dopo set SL (già abbiamo i dati)

# Real-time position display configuration
REALTIME_DISPLAY_ENABLED = True
REALTIME_DISPLAY_INTERVAL = 1.0
REALTIME_PRICE_CACHE_TTL = 2
REALTIME_MAX_API_CALLS = 60
REALTIME_COLOR_CODING = True

# ==============================================================================
# 🖥️ PERFORMANCE OPTIMIZATION (FIX #6: Anti-Freeze)
# ==============================================================================
# Disable heavy components if PC is freezing

DASHBOARD_ENABLED = False            # FIX #6: Disable PyQt6 dashboard (very heavy on CPU)
TRAILING_BACKGROUND_ENABLED = True   # Keep trailing monitor (lightweight)
BALANCE_SYNC_ENABLED = True          # Keep balance sync (lightweight)
DASHBOARD_UPDATE_INTERVAL = 60      # If enabled: update every 60s instead of 30s

# ==============================================================================
# 🔥 SPIKE DETECTION: OPTIMIZED TIMEFRAMES & LOOKBACK
# ==============================================================================
ENABLED_TIMEFRAMES: list[str] = ["5m", "15m", "30m"]  # Spike optimized
TIMEFRAME_DEFAULT: str | None = "5m"  # Default to fastest timeframe

# DIFFERENTIATED LOOKBACK per timeframe (spike optimization)
LOOKBACK_HOURS_5M = 2   # 5m: 2 hours = 24 candles (recent spike focus)
LOOKBACK_HOURS_15M = 4  # 15m: 4 hours = 16 candles (balance)
LOOKBACK_HOURS_30M = 6  # 30m: 6 hours = 12 candles (trend stability)
LOOKBACK_HOURS = LOOKBACK_HOURS_5M  # Default for compatibility

TIMEFRAME_TIMESTEPS = {
    "5m": int(LOOKBACK_HOURS_5M * 60 / 5),    # 24 candles (2 hours)
    "15m": int(LOOKBACK_HOURS_15M * 60 / 15), # 16 candles (4 hours)
    "30m": int(LOOKBACK_HOURS_30M * 60 / 30), # 12 candles (6 hours)
    # Legacy timeframes kept for compatibility
    "1h": int(6 / 1),
    "4h": max(2, int(6 / 4)),
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
DATA_LIMIT_DAYS = 90  # SPIKE OPTIMIZED: 90 days (2x faster training)
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

TOP_SYMBOLS_COUNT = 50  # WALK-FORWARD OPTIMIZED: 50 monete (balance quality/speed)
TOP_TRAIN_CRYPTO = TOP_SYMBOLS_COUNT
TOP_ANALYSIS_CRYPTO = TOP_SYMBOLS_COUNT

MIN_VOLUME_THRESHOLD = 1_000_000  
MIN_PRICE_THRESHOLD = 0.001      

TRAIN_IF_NOT_FOUND = True

# ----------------------------------------------------------------------
# Labeling Configuration (SL-Aware Only)
# ----------------------------------------------------------------------
FUTURE_RETURN_STEPS = 3  # Number of candles forward for SL-aware labeling

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
USE_CLASS_WEIGHTS = True

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
# Maximum number of concurrent positions allowed
# With fixed $15 per position, this determines minimum capital needed:
# - 10 positions = $150 minimum balance recommended

MAX_CONCURRENT_POSITIONS = 10  # Max 10 concurrent positions

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

# ADAPTIVE LEARNING: Sistema rimosso (non più utilizzato)

# ==============================================================================
# 🎯 STOP LOSS AWARENESS TRAINING
# ==============================================================================
# Training ML che considera se SL viene hit durante il path
SL_AWARENESS_ENABLED = True               # Enable SL-aware labeling
SL_AWARENESS_PERCENTAGE = STOP_LOSS_PCT   # Uses master SL parameter
SL_AWARENESS_PERCENTILE_BUY = 80          # Top 20% returns for BUY labels
SL_AWARENESS_PERCENTILE_SELL = 80         # Top 20% returns for SELL labels
SL_AWARENESS_BORDERLINE_BUY = STOP_LOSS_PCT * 0.5   # 50% of SL (borderline threshold)
SL_AWARENESS_BORDERLINE_SELL = STOP_LOSS_PCT * 0.5  # Symmetric borderline

# ==============================================================================
# 🌍 GLOBAL MODEL TRAINING (HYBRID APPROACH)
# ==============================================================================
# Train on all symbols together for better generalization and transfer learning
# Instead of separate models per symbol, create one unified model that learns
# universal patterns across the entire crypto market

GLOBAL_MODEL_ENABLED = True              # Enable Global Model (train on all 100 symbols together)
                                         # True: Single model learns from all symbols (recommended)
                                         # False: Traditional per-symbol training (legacy)

# ==============================================================================
# 🎯 TRIPLE BARRIER LABELING (MATHEMATICAL RIGOR)
# ==============================================================================
# Replace percentile-based labeling with mathematically rigorous Triple Barrier Method
# Simulates actual trade execution with SL/TP barriers aligned to real trading

TRIPLE_BARRIER_ENABLED = True            # Enable Triple Barrier labeling
                                         # True: Use SL/TP barrier method (recommended)
                                         # False: Use SL-Aware percentile method (legacy)

# Barrier configuration (aligned with actual trading parameters)
# ⚡ CUSTOM: Con leva 5x → TP=20% ROE richiede 4% spot, SL=35% ROE richiede 7% spot
TRIPLE_BARRIER_TP_PCT = 0.04             # Take Profit: +4% spot (con leva 5x = +20% ROE)
TRIPLE_BARRIER_SL_PCT = 0.07             # Stop Loss: -7% spot (con leva 5x = -35% ROE max loss)
TRIPLE_BARRIER_LOOKFORWARD = 8           # Lookforward window: 8 candele (5m=40min, 15m=2h)
                                         # 5m: 40 min, 15m: 2h, 30m: 4h
                                         # Shorter than original proposal (96) for faster signals

# Asymmetric TP/SL ratio provides better risk/reward after costs
# With 5x leverage:
# - SL -6% = -30% ROE
# - TP +9% = +45% ROE
# - Ratio: 1:1.5 (reward 50% higher than risk)

# ==============================================================================
# 📊 Z-SCORE ROLLING NORMALIZATION (GLOBAL MODEL REQUIREMENT)
# ==============================================================================
# Normalize indicators using rolling window statistics instead of global scaling
# This makes BTC ($100K) and PEPE ($0.0001) data comparable for Global Model
# Each value becomes "deviations from its local mean" (context-aware)

Z_SCORE_NORMALIZATION = True             # Enable Z-Score Rolling Normalization
                                         # True: Rolling z-score (required for Global Model)
                                         # False: Standard scaling (legacy, per-symbol only)

Z_SCORE_WINDOW = 96                      # Rolling window: 96 candeles
                                         # 5m: 8h, 15m: 24h, 30m: 48h
                                         # Captures recent market regime without old data

# Z-Score converts absolute values to statistical significance:
# Example: "Volume is +2.5 sigma above mean" (anomaly/breakout)
# This works regardless of whether it's BTC volume (1000 BTC) or PEPE (1M tokens)

# ==============================================================================
# ⚖️ ADVANCED CLASS WEIGHTING (MATHEMATICAL BALANCE)
# ==============================================================================
# Use inverse frequency weighting for class balance instead of generic sklearn weights
# Penalizes model more for errors on rare signals (BUY/SELL) vs common signals (NEUTRAL)

ADVANCED_CLASS_WEIGHTING = True          # Enable advanced sample weighting
                                         # True: Inverse frequency weights (recommended)
                                         # False: Generic sklearn weights (legacy)

# With inverse frequency weighting:
# - NEUTRAL (70% of data): weight = 1.0
# - BUY (15% of data): weight = ~4.7 (penalize errors 4.7x more)
# - SELL (15% of data): weight = ~4.7
# Model learns to NOT predict NEUTRAL for everything just to get 70% accuracy

# ==============================================================================
# 🎯 CONFIDENCE THRESHOLD (SIMPLIFIED)
# ==============================================================================
MIN_CONFIDENCE = 0.65  # Minimum ML confidence required to open trade (65%)

# ==============================================================================
# 🔄 WALK-FORWARD TESTING (NEW!)
# ==============================================================================
# Walk-Forward Analysis: Test model on multiple unseen periods with periodic retraining
# More robust than single train/test split - simulates real-world retraining strategy

# Master switch
WALK_FORWARD_ENABLED = True          # Enable Walk-Forward Testing during training
                                     # True: 3-round testing with retraining (recommended)
                                     # False: Legacy single train/test split

# Walk-Forward configuration (90 days total)
WALK_FORWARD_ROUNDS = 3              # Number of test rounds (3x 9-day periods)

# Round 1: Train on days 1-63 (70%), Test on days 64-72 (10%)
# Round 2: Retrain on days 1-72 (80%), Test on days 73-81 (10%) 
# Round 3: Retrain on days 1-81 (90%), Test on days 82-90 (10%)
# Final: Train on all 90 days for production use

WF_TRAIN_DAYS_ROUND_1 = 63           # Training days for Round 1
WF_TEST_DAYS_PER_ROUND = 9           # Test days per round (10% of 90)
WF_VALIDATION_PCT = 0.10             # Internal validation during each training (10%)

# Trading Simulation Parameters (uses existing config values)
# These parameters are automatically pulled from existing config:
# - LEVERAGE (5x)
# - STOP_LOSS_PCT (6%)
# - TRAILING_TRIGGER_ROE (12%)
# - TRAILING_DISTANCE_ROE_OPTIMAL (8%)
# - MIN_CONFIDENCE (65%)

# Report generation
WF_GENERATE_CHARTS = True            # Generate visual charts for each timeframe
WF_SAVE_DETAILED_TRADES = True       # Save individual trade details to JSON
WF_SAVE_AGGREGATE_REPORT = True      # Save aggregate performance report

# ==============================================================================
# 💰 COST ACCOUNTING - CORRECTED BYBIT FEES
# ==============================================================================
# Bybit Perpetual Futures fees (non-VIP):
# - Market orders (taker): 0.055% of notional
# - Limit orders (maker): 0.02% of notional (if filled as maker)
# Note: Bot primarily uses market orders (taker fees)

BYBIT_TAKER_FEE = 0.00055           # CORRECTED: 0.055% taker fee (was 0.075%)
BYBIT_MAKER_FEE = 0.0002            # CORRECTED: 0.02% maker fee (was 0.055%)
SLIPPAGE_NORMAL = 0.003             # 0.3% normal conditions
SLIPPAGE_VOLATILE = 0.010           # 1.0% high volatility
SLIPPAGE_SL_PANIC = 0.008           # 0.8% on SL triggers

# Total round trip costs (with leverage 5x):
# Entry: 0.055% + 0.3% = 0.355%
# Exit:  0.055% + 0.3% = 0.355%
# Total: 0.71% × 5 = 3.55% of margin

# Minimum profit after all costs
MIN_PROFIT_AFTER_COSTS = 5.0        # ADJUSTED: Min +5% ROE profit (was 8%, adjusted with corrected fees)

# ==============================================================================
# 🚫 PROBLEMATIC SYMBOLS MANAGEMENT (FIX #4)
# ==============================================================================
# Symbols known to cause issues (e.g., XAUT with SL infinite loops)
SYMBOL_BLACKLIST = [
    'XAUT/USDT:USDT',  # Gold-backed token - known SL issues
    'PAXG/USDT:USDT',  # Gold-backed token - known SL issues
]

# Stop Loss retry management
SL_MAX_RETRIES = 3                  # Max attempts before blacklisting
SL_RETRY_COOLDOWN = 300             # Seconds in blacklist (5 minutes)


# ==============================================================================
# 🚨 VOLUME SURGE DETECTOR (NEW!)
# ==============================================================================
# Real-time pump detection via volume spikes
VOLUME_SURGE_DETECTION = True        # Enable volume surge detection
VOLUME_SURGE_MULTIPLIER = 3.0        # Alert when volume is 3x+ normal
VOLUME_SURGE_COOLDOWN = 60           # Cooldown minutes between surges for same symbol
VOLUME_SURGE_MIN_PRICE_CHANGE = 0.02  # Min 2% price movement required
VOLUME_SURGE_PRIORITY = True         # Give priority to surge symbols in analysis

# Pump catching optimization
PUMP_CATCHING_MODE = True            # Enable aggressive pump catching
if PUMP_CATCHING_MODE:
    TOP_SYMBOLS_COUNT = 75           # Analyze more symbols for better coverage
    MIN_CONFIDENCE_BASE = 0.70       # Slightly lower threshold for pumps (was 0.65)
    VOLUME_SURGE_MIN_CONFIDENCE = 0.65  # Even lower for volume surge detection


# ==============================================================================
# 🤖 HYBRID AI SYSTEM (Rizzo Integration)
# ==============================================================================
# Integration of Rizzo project components for enhanced decision making
# Combines XGBoost ML with GPT-4o AI validation and market intelligence

# ---- MASTER SWITCH ----
AI_VALIDATION_ENABLED = True        # Enable AI validation system (requires OpenAI API key)
                                     # True: XGBoost signals validated by GPT-4o
                                     # False: Pure XGBoost mode (current behavior)

# ---- AI CONFIGURATION ----
OPENAI_MODEL = "gpt-4o"              # OpenAI model for validation
AI_MAX_SIGNALS_TO_VALIDATE = 10      # Maximum signals to send to AI (cost control)
AI_TEMPERATURE = 0.3                 # Lower = more consistent decisions

# ---- MARKET INTELLIGENCE ----
# News, sentiment, forecasts, whale alerts collection
MARKET_INTELLIGENCE_ENABLED = True   # Collect market intelligence data
                                     # Can be enabled even without AI validation for logging

# CoinMarketCap Sentiment (Fear & Greed Index)
CMC_SENTIMENT_ENABLED = True         # Enable sentiment analysis
# Requires CMC_PRO_API_KEY environment variable

# Prophet Forecasting
PROPHET_FORECASTS_ENABLED = True     # Enable price forecasting
PROPHET_MAX_SYMBOLS = 5              # Max symbols to forecast (performance control)
PROPHET_TIMEFRAME = "15m"            # Timeframe for forecasts

# News Feed
NEWS_FEED_ENABLED = True             # Enable crypto news collection
NEWS_MAX_CHARS = 4000                # Max characters for news feed

# Whale Alerts
WHALE_ALERTS_ENABLED = False         # Enable whale alert tracking (requires API subscription)
# Requires WHALE_ALERT_API_KEY environment variable

# ---- AI VALIDATION BEHAVIOR ----
# How AI validates XGBoost signals
AI_MODE = "validator"                # "validator" = AI filters XGBoost signals
                                     # "primary" = AI is primary decision maker (experimental)

AI_MIN_APPROVED_SIGNALS = 1          # Minimum signals AI must approve to proceed
AI_MAX_APPROVED_SIGNALS = 5          # Maximum signals AI can approve per cycle
AI_CONSERVATIVE_MODE = True          # Be conservative in bearish conditions

# ---- COST CONTROLS ----
# OpenAI API cost management
AI_COST_LIMIT_PER_CYCLE = 0.10       # Max $0.10 per cycle (safety limit)
AI_COST_LIMIT_DAILY = 5.00           # Max $5.00 per day (safety limit)
AI_COST_TRACKING_ENABLED = True      # Track and log AI costs

# ---- FALLBACK BEHAVIOR ----
# What to do if AI validation fails
AI_FALLBACK_TO_XGBOOST = True        # True: use XGBoost signals if AI fails
                                     # False: skip cycle if AI unavailable

# ---- LOGGING & MONITORING ----
AI_LOG_DECISIONS = True              # Log all AI decisions for analysis
AI_LOG_MARKET_INTEL = True           # Log market intelligence data
AI_VERBOSE_LOGGING = True            # ENABLE: Show AI reasoning for EACH signal (verbose)


# ==============================================================================
# 🔄 DUAL-ENGINE SYSTEM (XGBoost vs GPT-4o Parallel Analysis)
# ==============================================================================
# Enables parallel analysis where both XGBoost ML and GPT-4o AI independently
# analyze the same technical indicators and provide their own signals

# ---- MASTER SWITCH ----
DUAL_ENGINE_ENABLED = True           # Enable dual-engine parallel analysis
                                     # True: Both XGBoost and AI analyze independently
                                     # False: Use existing validator system

# ---- EXECUTION STRATEGY ----
# Determines how to combine/use the two signals
# Options:
#   "xgboost_only"  - Ignore AI, use only XGBoost (baseline for A/B testing)
#   "ai_only"       - Ignore XGBoost, use only AI (test AI standalone)
#   "consensus"     - Trade ONLY when both agree on direction
#   "weighted"      - Weighted average: 70% XGBoost, 30% AI
#   "champion"      - Use best performer based on recent win rate
DUAL_ENGINE_STRATEGY = "consensus"   # Default: consensus for maximum accuracy

# ---- CONFIDENCE THRESHOLDS ----
DUAL_ENGINE_XGB_MIN_CONFIDENCE = 65  # Min XGBoost confidence to consider (%)
DUAL_ENGINE_AI_MIN_CONFIDENCE = 70   # Min AI confidence to consider (%)
DUAL_ENGINE_CONSENSUS_MIN = 70       # Min consensus confidence to trade (%)

# ---- AI TECHNICAL ANALYST CONFIG ----
AI_ANALYST_ENABLED = True            # Enable AI Technical Analyst module
AI_ANALYST_MODEL = "gpt-4o"          # Model for AI Analyst
AI_ANALYST_TEMPERATURE = 0.2         # Lower = more consistent analysis
AI_ANALYST_MAX_SYMBOLS = 10          # Max symbols to analyze per cycle

# ---- PERFORMANCE TRACKING ----
DUAL_ENGINE_TRACK_STATS = True       # Track XGB vs AI performance
DUAL_ENGINE_LOG_DISAGREEMENTS = True # Log when XGB and AI disagree
DUAL_ENGINE_SHOW_DASHBOARD = True    # Show performance dashboard at cycle end

# ---- COST MANAGEMENT ----
# AI Analyst adds ~$0.02-0.04 per symbol analyzed
AI_ANALYST_COST_LIMIT_CYCLE = 0.50   # Max $0.50 per cycle for AI Analyst
AI_ANALYST_COST_LIMIT_DAILY = 20.00  # Max $20/day for AI Analyst
