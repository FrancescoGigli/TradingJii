# ⚙️ 08 - Configurazione Sistema

Guida completa a tutte le configurazioni del trading bot.

---

## 📋 Indice

1. [File config.py](#file-configpy)
2. [Configurazioni Bybit](#configurazioni-bybit)
3. [ML Models Config](#ml-models-config)
4. [Trading Parameters](#trading-parameters)
5. [Risk Management](#risk-management)
6. [Adaptive Sizing](#adaptive-sizing)
7. [Logging & Monitoring](#logging--monitoring)

---

## 📝 File config.py

### **Location:** `config.py` (root directory)

```python
# ============================================================
# GENERAL SETTINGS
# ============================================================

# Modalità operativa
DEMO_MODE = False  # True = Testnet, False = Live Trading
LIVE_TRADING = not DEMO_MODE

# ============================================================
# BYBIT API CREDENTIALS
# ============================================================

if DEMO_MODE:
    # Testnet credentials
    API_KEY = 'your_testnet_api_key'
    API_SECRET = 'your_testnet_secret'
    BASE_URL = 'https://api-testnet.bybit.com'
else:
    # Live credentials
    API_KEY = 'your_live_api_key'
    API_SECRET = 'your_live_secret'
    BASE_URL = 'https://api.bybit.com'

# ============================================================
# TRADING CYCLE
# ============================================================

# Intervallo tra cicli (minuti)
TRADING_INTERVAL = 15  # 15 minuti

# Timeframes abilitati per analisi
ENABLED_TIMEFRAMES = ['15m', '30m', '1h']

# Top N crypto da analizzare (per volume 24h)
TOP_ANALYSIS_CRYPTO = 50

# ============================================================
# ML MODELS CONFIGURATION
# ============================================================

# Time steps (lookback window per timeframe)
TIME_STEPS = {
    '15m': 24,  # 6 ore di dati
    '30m': 24,  # 12 ore di dati
    '1h': 24    # 24 ore (1 giorno)
}

# Prediction horizon (candele in avanti)
PREDICTION_HORIZON = {
    '15m': 8,   # 2 ore ahead
    '30m': 6,   # 3 ore ahead
    '1h': 4     # 4 ore ahead
}

# Return threshold per labeling
RETURN_THRESHOLD = 0.015  # ±1.5%
# Se future_return > +1.5%: BUY
# Se future_return < -1.5%: SELL
# Altrimenti: NEUTRAL

# Timeframe weights per ensemble
TIMEFRAME_WEIGHTS = {
    '15m': 1.0,  # Fast signals
    '30m': 1.2,  # Medium signals
    '1h': 1.5    # Slow but reliable
}

# ============================================================
# POSITION SIZING
# ============================================================

# Adaptive sizing (learning-based)
ADAPTIVE_SIZING_ENABLED = True

# Legacy portfolio-based sizing
PORTFOLIO_RISK_PER_TRADE = 0.20  # 20% balance per trade
# Se ADAPTIVE_SIZING_ENABLED = False, usa questo

# ============================================================
# RISK MANAGEMENT
# ============================================================

# Portfolio limits
MAX_POSITIONS = 5  # Max posizioni attive contemporaneamente
MAX_PORTFOLIO_RISK = 0.20  # 20% del balance max in risk

# Stop Loss
STOP_LOSS_PERCENTAGE = 0.05  # -5% price = -50% ROE (con 10x leverage)
STOP_LOSS_FIXED = True       # True = fixed SL, False = ATR-based

# Trailing Stop
TRAILING_STOP_ENABLED = True
TRAILING_ACTIVATION_ROE = 0.15    # Attiva a +15% ROE
TRAILING_PROTECT_ROE = 0.10       # Protegge ultimo 10% ROE
TRAILING_UPDATE_INTERVAL = 60     # Update ogni 60 secondi

# Leverage
LEVERAGE = 10  # 10x leverage (fixed)

# ============================================================
# SYMBOL FILTERING
# ============================================================

# Simboli esclusi (blacklist)
EXCLUDED_SYMBOLS = [
    'BTCDOM',    # Bitcoin dominance
    'ETHPERP',   # ETH perpetual (usa ETH/USDT:USDT)
    'DEFI',      # DeFi index
    'USDT',      # Tether
    'USDC',      # USD Coin
    'BUSD'       # Binance USD
]

# Min volume 24h (USD)
MIN_24H_VOLUME = 10_000_000  # $10M

# ============================================================
# EARLY EXIT SYSTEM
# ============================================================

# Early exit per low confidence dopo apertura
EARLY_EXIT_ENABLED = True
EARLY_EXIT_TIMEFRAMES = [5, 15, 30]  # Minuti dopo apertura
EARLY_EXIT_LOSS_THRESHOLD = -0.10    # -10% ROE

# ============================================================
# REINFORCEMENT LEARNING
# ============================================================

# RL Agent per filtering
RL_AGENT_ENABLED = False  # Experimental
RL_AGENT_THRESHOLD = 0.50  # Min probability per approval

# ============================================================
# CONFIDENCE CALIBRATION
# ============================================================

# Calibra confidence su real win rate
CONFIDENCE_CALIBRATION_ENABLED = True
CALIBRATION_TRADES_MIN = 100  # Min trade per calibration

# ============================================================
# DATABASE & CACHING
# ============================================================

# SQLite cache per market data
DB_CACHE_ENABLED = True
DB_CACHE_PATH = 'data_cache/trading_data.db'
DB_CACHE_EXPIRY = 900  # 15 minuti

# ============================================================
# LOGGING
# ============================================================

# Log level
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR

# Log file
LOG_FILE = 'logs/trading.log'
LOG_MAX_SIZE = 10_000_000  # 10 MB
LOG_BACKUP_COUNT = 5

# Enhanced logging
ENHANCED_LOGGING = True
LOG_TRADE_DECISIONS = True
LOG_API_CALLS = False  # Verbose

# ============================================================
# DASHBOARD
# ============================================================

# PyQt6 dashboard
DASHBOARD_ENABLED = True
DASHBOARD_UPDATE_INTERVAL = 30  # Secondi
DASHBOARD_AUTO_REFRESH = True

# Realtime display (CLI)
REALTIME_DISPLAY_ENABLED = True
REALTIME_UPDATE_INTERVAL = 60  # Secondi

# ============================================================
# ALERTS & NOTIFICATIONS
# ============================================================

# Telegram notifications (optional)
TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = 'your_bot_token'
TELEGRAM_CHAT_ID = 'your_chat_id'

# Email notifications (optional)
EMAIL_ENABLED = False
EMAIL_SMTP_SERVER = 'smtp.gmail.com'
EMAIL_SMTP_PORT = 587
EMAIL_FROM = 'your_email@gmail.com'
EMAIL_PASSWORD = 'your_app_password'
EMAIL_TO = 'recipient@email.com'

# Alert conditions
ALERT_ON_NEW_POSITION = True
ALERT_ON_POSITION_CLOSED = True
ALERT_ON_STOP_LOSS = True
ALERT_ON_TRAILING_UPDATED = False

# ============================================================
# PERFORMANCE MONITORING
# ============================================================

# Session stats tracking
SESSION_STATS_ENABLED = True
SAVE_SESSION_HISTORY = True
SESSION_HISTORY_PATH = 'logs/session_history.json'

# Trade history
SAVE_TRADE_HISTORY = True
TRADE_HISTORY_PATH = 'logs/trade_history.csv'

# ============================================================
# SAFETY & EMERGENCY
# ============================================================

# Emergency stop conditions
EMERGENCY_STOP_ENABLED = True
EMERGENCY_MAX_DAILY_LOSS = -0.15     # -15% daily loss
EMERGENCY_MAX_DRAWDOWN = -0.20       # -20% from peak
EMERGENCY_MAX_CONSECUTIVE_LOSSES = 5  # 5 loss di fila

# Auto-restart after errors
AUTO_RESTART_ON_ERROR = True
MAX_RESTART_ATTEMPTS = 3

# ============================================================
# DEVELOPMENT & DEBUG
# ============================================================

# Dry run (simula trade senza eseguire)
DRY_RUN = False

# Skip ML predictions (use random)
SKIP_ML_PREDICTIONS = False

# Force specific symbols (debug)
FORCE_SYMBOLS = None  # ['BTC/USDT:USDT', 'ETH/USDT:USDT']

# Verbose output
VERBOSE = False
```

---

## 🔑 Configurazioni Bybit

### **Setup Account:**

1. **Crea Account Bybit:**
   - Main: https://www.bybit.com
   - Testnet: https://testnet.bybit.com

2. **Genera API Keys:**
   ```
   Account → API Management → Create New Key
   
   Permissions richieste:
   ├─ ✅ Read-Write
   ├─ ✅ Contract Trading
   ├─ ✅ Spot Trading (optional)
   └─ ❌ Withdraw (NON abilitare)
   
   IP Whitelist:
   └─ Aggiungi IP del tuo server (recommended)
   ```

3. **Configura in config.py:**
   ```python
   API_KEY = 'Bxxxxxxxxxxxxxxxxxxxxx'
   API_SECRET = 'xxxxxxxxxxxxxxxxxxxxx'
   ```

4. **Test Connection:**
   ```bash
   python scripts/test_connection.py
   ```

### **Position Mode:**

```python
# CRITICAL: Usa One-Way Mode (non Hedge Mode)

# Check current mode:
python scripts/check_position_mode.py

# Output dovrebbe essere:
# ✅ Position Mode: ONE_WAY
# ✅ Ready for trading

# Se è HEDGE_MODE, cambia manualmente:
# Bybit → Derivatives → Settings → Position Mode → One-Way
```

---

## 🤖 ML Models Config

### **Training Frequency:**

```python
# Quando re-trainare i modelli:
├─ Initial setup: Obbligatorio
├─ Monthly: Raccomandato (mercato cambia)
├─ After major events: Consigliato
└─ Custom: Quando accuracy cala < 60%

# Train command:
python trainer.py --timeframes 15m 30m 1h --symbols 50
```

### **Model Files:**

```
trained_models/
├─ xgb_model_15m.pkl      # XGBoost 15m
├─ xgb_scaler_15m.pkl     # StandardScaler 15m
├─ xgb_model_30m.pkl      # XGBoost 30m
├─ xgb_scaler_30m.pkl     # StandardScaler 30m
├─ xgb_model_1h.pkl       # XGBoost 1h
└─ xgb_scaler_1h.pkl      # StandardScaler 1h
```

### **Model Performance Thresholds:**

```python
# Acceptable ranges:
├─ Test Accuracy: 62-68%
├─ F1 Score: > 0.60
├─ Cross-val std: < 0.05
└─ Calibrated win rate: 55-58%

# Se sotto questi valori: re-train!
```

---

## 💰 Trading Parameters

### **Capital Allocation:**

```python
# Esempio: $1000 initial balance

if ADAPTIVE_SIZING_ENABLED:
    # Block-based allocation
    base_block = 1000 / 5 = $200
    
    # Per simbolo:
    ├─ NEW: $100 (50% block)
    ├─ WINNER: $200-300 (100-150% block)
    └─ LOSER: $0 (blocked 3 cycles)

else:
    # Portfolio-based (legacy)
    per_trade = 1000 × 0.20 = $200
    # Fixed $200 per ogni trade
```

### **Leverage Impact:**

```python
Leverage = 10x

├─ Margin $100 → $1000 notional
├─ +10% price = +100% ROE ($100 profit)
├─ -5% price = -50% ROE ($-50 loss, SL hit)
└─ -10% price = -100% ROE (liquidation!)

IMPORTANTE: Con 10x leverage:
- Stop Loss -5% protegge da liquidation
- Mai rimuovere o spostare SL manualmente
```

---

## 🛡️ Risk Management

### **5-Layer Protection:**

```python
LAYER 1: Position Sizing (adaptive)
├─ Max 5 posizioni attive
├─ Max 20% portfolio in risk
└─ Smart allocation per simbolo

LAYER 2: Stop Loss (fixed -5%)
├─ Applicato immediatamente
├─ Auto-fix se mancante
└─ = -50% ROE con 10x leverage

LAYER 3: Trailing Stops
├─ Attivazione: +15% ROE
├─ Protezione: ultimo 10% ROE
└─ Update automatico ogni 60s

LAYER 4: Early Exit
├─ Check a 5, 15, 30 min
├─ Chiude se < -10% ROE
└─ Solo per low confidence

LAYER 5: Emergency Controls
├─ Max daily loss: -15%
├─ Max drawdown: -20%
├─ 5 loss consecutivi → stop
└─ Auto-close tutte posizioni
```

### **Esempio Real Risk:**

```
Balance: $1000
Max Positions: 5

Worst Case Scenario:
├─ 5 posizioni × $200 margin = $1000 invested
├─ All hit SL (-50% ROE each)
├─ Total loss: 5 × $100 = -$500
├─ Remaining: $500
└─ Max loss: -50% (theoretical)

Realistic Scenario (55% win rate):
├─ 3 winners: +$150
├─ 2 losers: -$100
├─ Net: +$50
└─ Daily return: +5%
```

---

## 📊 Adaptive Sizing

### **Configuration:**

```python
ADAPTIVE_SIZING_ENABLED = True

# Learning parameters:
├─ Block size: balance / 5
├─ NEW symbol: 50% block
├─ Winner scale: 1.0-1.5x
├─ Loser block: 3 cycles
└─ Performance decay: 10% per day
```

### **Performance Tracking:**

```python
# Per symbol memory:
{
    'symbol': 'SOL',
    'trades_count': 8,
    'wins': 6,
    'losses': 2,
    'win_rate': 0.75,  # 75%
    'avg_pnl_pct': 12.5,
    'last_trade': '2025-03-10',
    'is_winner': True,
    'blocked_until': None,
    'current_scale': 1.3  # 130% of block
}
```

---

## 📝 Logging & Monitoring

### **Log Files:**

```
logs/
├─ trading.log              # Main log
├─ trade_decisions.db       # SQLite trade decisions
├─ session_history.json     # Session stats
└─ trade_history.csv        # All trades CSV
```

### **Log Levels:**

```python
# DEBUG: Tutto (verbose)
LOG_LEVEL = 'DEBUG'

# INFO: Operazioni normali (raccomandato)
LOG_LEVEL = 'INFO'

# WARNING: Solo warnings + errors
LOG_LEVEL = 'WARNING'

# ERROR: Solo errori critici
LOG_LEVEL = 'ERROR'
```

### **Monitoring Dashboard:**

```python
# PyQt6 GUI
DASHBOARD_ENABLED = True

Features:
├─ Real-time positions
├─ PnL tracking
├─ Session stats
├─ Adaptive sizing status
├─ Recent trades
└─ Auto-refresh (30s)
```

---

## 🚀 Quick Setup Checklist

```
Pre-requisites:
├─ [x] Python 3.9+
├─ [x] pip install -r requirements.txt
├─ [x] Bybit account + API keys
└─ [x] $100+ balance (recommended $500+)

Configuration:
├─ [x] Edit config.py (API keys)
├─ [x] Set DEMO_MODE = False (or True for test)
├─ [x] Check position mode (One-Way)
└─ [x] Configure risk parameters

ML Models:
├─ [x] Train initial models (python trainer.py)
├─ [x] Verify accuracy > 62%
└─ [x] Check model files exist

Launch:
├─ [x] Test connection (scripts/test_connection.py)
├─ [x] Dry run first (DRY_RUN = True)
├─ [x] Monitor first cycle
└─ [x] Enable live trading

✅ READY TO TRADE!
```

---

**Prossimo:** [FILE-ANALIZZATI-CHECKLIST](FILE-ANALIZZATI-CHECKLIST.md) - Lista completa file analizzati →
