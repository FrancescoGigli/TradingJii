# 📖 02 - Startup e Inizializzazione

> **Processo completo di avvio del trading bot**

---

## 🚀 Sequenza Startup Completa

Il sistema segue una sequenza precisa di inizializzazione per garantire che tutti i componenti siano ready prima di iniziare il trading.

```
STARTUP FLOW (main.py)
  │
  ├─► 1. ENVIRONMENT SETUP (1s)
  │   • UTF-8 encoding (Windows compatibility)
  │   • Warnings suppression
  │   • Signal handlers
  │
  ├─► 2. CONFIG MANAGER (Interactive)
  │   • Menu selezione modalità (DEMO/LIVE)
  │   • Selezione timeframes (15m, 30m, 1h)
  │   • Conferma settings
  │
  ├─► 3. STARTUP COLLECTOR INIT (0s)
  │   • Inizializza logging strutturato
  │   • Registra core systems
  │   • Prepara summary display
  │
  ├─► 4. EXCHANGE CONNECTION (3-5s)
  │   • Time synchronization (3 attempts max)
  │   • Markets loading
  │   • Authentication test
  │   • Balance fetch
  │
  ├─► 5. MANAGER INITIALIZATION (1s)
  │   • ThreadSafePositionManager
  │   • SmartAPIManager (cache system)
  │   • OrderManager
  │   • RiskCalculator
  │
  ├─► 6. MARKET ANALYSIS (10-15s)
  │   • Fetch top 50 crypto by volume
  │   • Filter excluded symbols
  │   • Sort by volume
  │
  ├─► 7. ML MODELS LOADING (5-10s)
  │   • Load XGBoost models (15m, 30m, 1h)
  │   • Load scalers
  │   • Or train if missing
  │
  ├─► 8. ADAPTIVE SIZING INIT (1s)
  │   • Load memory from JSON
  │   • Initialize Kelly Criterion
  │   • Fresh start check
  │
  ├─► 9. TRADE ANALYZER INIT (1s)
  │   • OpenAI client setup
  │   • Database initialization
  │   • Enable/disable check
  │
  ├─► 10. TRADING ENGINE INIT (1s)
  │   • Orchestrator setup
  │   • Signal processor
  │   • Dashboard launch
  │
  ├─► 11. POSITION SYNC (2-3s)
  │   • Fetch existing positions from Bybit
  │   • Apply SL protection if missing
  │   • Register in tracker
  │
  ├─► 12. STARTUP SUMMARY DISPLAY (1s)
  │   • Print configuration
  │   • Print market analysis
  │   • Print system status
  │
  └─► ✅ READY TO TRADE
      • Start trading loop (15 min cycle)
      • Launch background tasks
      • Monitor positions
```

**Tempo totale startup**: 30-45 secondi (con connessione stabile)

---

## 🔧 1. Environment Setup

```python
# UTF-8 Encoding (Windows fix)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Warnings suppression
warnings.filterwarnings("ignore", category=RuntimeWarning, module="ta")
np.seterr(divide="ignore", invalid="ignore")

# qasync event loop (PyQt6 integration)
app = QApplication(sys.argv)
loop = QEventLoop(app)
asyncio.set_event_loop(loop)
```

**Perché importante**:
- UTF-8 permette emoji e simboli Unicode nel logging
- Warnings suppression evita spam da libreria `ta`
- qasync loop integra asyncio con PyQt6 (necessario per dashboard)

---

## ⚙️ 2. Config Manager (Interactive)

```python
from bot_config import ConfigManager

config_manager = ConfigManager()
selected_timeframes, selected_models, demo_mode = config_manager.select_config()
```

**Menu Interattivo**:
```
═══════════════════════════════════════════════════
🚀 TRADING BOT CONFIGURATION
═══════════════════════════════════════════════════

Select trading mode:
  1. 📊 DEMO MODE (Paper trading, no real money)
  2. 💵 LIVE MODE (Real trading on Bybit)

Your choice: _

Select timeframes (space-separated):
Available: 15m 30m 1h

Your selection: 15m 30m 1h

═══════════════════════════════════════════════════
CONFIGURATION SUMMARY
═══════════════════════════════════════════════════
Mode: DEMO MODE
Timeframes: 15m, 30m, 1h
Models: XGBoost ensemble

Confirm? (y/n): y
```

**Outputs**:
- `selected_timeframes`: Lista timeframes es. ['15m', '30m', '1h']
- `selected_models`: ['xgb'] (solo XGBoost attualmente)
- `demo_mode`: True/False

---

## 🌐 3. Exchange Connection & Time Sync

```python
async def initialize_exchange():
    """Critical: Time sync MUST happen BEFORE authentication"""
```

### **Phase 1: Time Synchronization** ⏰

**Problema**: Bybit rifiuta requests se timestamp locale differisce >5s dal server.

**Soluzione**: Fetch server time e calcola offset.

```python
# Step 1: Fetch server time (public API)
server_time = await async_exchange.fetch_time()
local_time = async_exchange.milliseconds()

# Step 2: Calculate difference
time_diff = server_time - local_time

# Step 3: Apply manual offset if configured
if MANUAL_TIME_OFFSET is not None:
    time_diff += MANUAL_TIME_OFFSET

# Step 4: Store in exchange options
async_exchange.options['timeDifference'] = time_diff
```

**Retry Logic**:
- Max 5 attempts
- Exponential backoff (3s, 6s, 9s, 12s, 15s)
- Verifica con secondo fetch time
- Tolleranza: ±2 secondi post-adjustment

**Se fallisce**:
```
❌ Time synchronization failed after 5 attempts
💡 Troubleshooting tips:
   1. Check Windows time sync: Settings > Time & Language
   2. Enable 'Set time automatically' and sync now
   3. Restart bot after fixing
   4. Set MANUAL_TIME_OFFSET in config.py if issue persists
```

### **Phase 2: Markets Loading** 📊

```python
await async_exchange.load_markets()
```

Carica tutti i mercati disponibili (USDT perpetual futures).

### **Phase 3: Authentication Test** 🔐

```python
balance = await async_exchange.fetch_balance()
```

Verifica che API keys siano valide.

**Possibili errori**:
- `❌ Invalid API key`: Chiavi sbagliate
- `❌ IP not whitelisted`: IP non autorizzato su Bybit
- `❌ Insufficient permissions`: Permessi mancanti (richiede trade + futures)

---

## 🔒 4. Manager Initialization

### **ThreadSafePositionManager**
```python
from core.thread_safe_position_manager import global_thread_safe_position_manager

position_manager = global_thread_safe_position_manager
```

- Gestisce posizioni con **threading.Lock**
- File persistence: `positions.json`
- Thread-safe operations per concurrent tasks

### **SmartAPIManager**
```python
from core.smart_api_manager import global_smart_api_manager

api_manager = global_smart_api_manager
```

- **Cache intelligente** per ridurre API calls
- Hit rate target: 70-90%
- TTL configurabili per diversi endpoint

### **Altri Manager**
- `OrderManager`: Piazzamento ordini e trading stops
- `RiskCalculator`: Calcolo margin, SL, risk validation
- `CostCalculator`: Fee tracking e cost analysis

---

## 📊 5. Market Analysis

```python
await trading_engine.market_analyzer.initialize_markets(
    async_exchange, TOP_ANALYSIS_CRYPTO, EXCLUDED_SYMBOLS
)
```

**Processo**:
1. Fetch tutti i markets USDT perpetual
2. Filtra per volume minimo (1M USDT/24h)
3. Escludi simboli blacklist (es. XAUT, PAXG)
4. Sort per volume decrescente
5. Prendi top 50

**Output**:
```
═══════════════════════════════════════════════════
📊 SELECTED SYMBOLS FOR LIVE ANALYSIS
═══════════════════════════════════════════════════
Total symbols: 50
Top 10 by volume:
  1. BTC/USDT:USDT   - $15.2B volume
  2. ETH/USDT:USDT   - $8.5B volume
  3. SOL/USDT:USDT   - $2.1B volume
  ...
Excluded: 2 symbols (BTC, ETH - training only)
═══════════════════════════════════════════════════
```

---

## 🤖 6. ML Models Loading

```python
xgb_models, xgb_scalers = await initialize_models(
    config_manager, top_symbols_training, async_exchange
)
```

**Per ogni timeframe**:
1. Cerca file `trained_models/xgb_model_{tf}.pkl`
2. Se trovato → Load
3. Se mancante:
   - Se `TRAIN_IF_NOT_FOUND = True` → Train nuovo modello
   - Altrimenti → Errore FATAL

**Training Steps** (se necessario):
```
🎯 Training new model for 15m
  • Fetching data: BTC, ETH, SOL, ... (50 symbols)
  • Timespan: 180 days
  • Features: 66 temporal features
  • Labeling: Stop-Loss aware with future returns
  • Training: XGBoost classifier
  • Validation: 3-fold CV
  • Saving model: trained_models/xgb_model_15m.pkl
  
✅ Model trained | Accuracy: 68.5% | Precision: 0.72
```

**Tempo training**: 3-5 minuti per timeframe (15-20 min totale per 3 TF)

---

## 🎯 7. Adaptive Sizing Initialization

```python
from core.adaptive_position_sizing import initialize_adaptive_sizing

global_adaptive_sizing = initialize_adaptive_sizing(config)
```

**Fresh Start Check**:
```python
if ADAPTIVE_FRESH_START:
    # Reset completo: cancella memory e ricomincia
    os.remove('adaptive_sizing_memory.json')
    logging.warning("🔄 FRESH START: Previous memory deleted")
else:
    # Historical mode: carica stats esistenti
    with open('adaptive_sizing_memory.json') as f:
        memory = json.load(f)
```

**Output (Historical Mode)**:
```
📂 HISTORICAL MODE: Loaded 12 symbols
    Cycle 45 | Stats: 27W/18L (60% WR)
    
Active symbols: 10
Blocked symbols: 2 (DOGE/USDT, SHIB/USDT)
```

**Output (Fresh Start)**:
```
🆕 FRESH START: No previous memory
    Starting fresh session with default base sizing
```

---

## 🤖 8. Trade Analyzer Initialization

```python
from core.trade_analyzer import initialize_trade_analyzer

trade_analyzer = initialize_trade_analyzer(config)
```

**Checks**:
1. `LLM_ANALYSIS_ENABLED = True` in config?
2. OpenAI library installed?
3. `OPENAI_API_KEY` in environment?
4. OpenAI client connection OK?

**Database Setup**:
```sql
CREATE TABLE IF NOT EXISTS trade_snapshots (...)
CREATE TABLE IF NOT EXISTS trade_analyses (...)
```

**Output**:
```
🤖 Trade Analyzer: ENABLED
    Model: gpt-4o-mini
    Analyze: Wins+Losses
    Database: trade_analysis.db (initialized)
```

O se disabled:
```
🤖 Trade Analyzer: DISABLED (check config)
```

---

## 🔄 9. Position Sync (Existing Positions)

```python
await trading_engine.orchestrator.protect_existing_positions(async_exchange)
```

**Processo**:
1. Fetch open positions da Bybit
2. Per ogni posizione trovata:
   - Sync in ThreadSafePositionManager
   - Verifica se ha Stop Loss
   - Se mancante → Applica SL -5%
   - Registra in tracker

**Output (con posizioni esistenti)**:
```
📥 Synced 2 positions from Bybit
🛡️ Applying Stop Loss protection...

✅ ETH/USDT: Stop Loss set at $3,250.50 (-5.0% price, -25% margin)
✅ SOL/USDT: Stop Loss set at $95.20 (-5.0% price, -25% margin)
```

**Output (nessuna posizione)**:
```
🆕 No existing positions on Bybit - starting fresh
```

---

## 📊 10. Startup Summary Display

```python
global_startup_collector.display_startup_summary()
```

**Output Completo**:
```
════════════════════════════════════════════════════════════════
🚀 TRADING BOT STARTUP SUMMARY
════════════════════════════════════════════════════════════════

⚙️  CONFIGURATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mode:              LIVE (Trading reale)
Timeframes:        15m, 30m, 1h
Model Type:        XGBoost ensemble
Excluded Symbols:  0 (none)

🌐 EXCHANGE CONNECTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Exchange:          Bybit (authenticated ✓)
Time Offset:       -250ms (synchronized ✓)
Markets:           Loaded ✓

🔧 CORE SYSTEMS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Position Manager:  FILE PERSISTENCE (positions.json)
Signal Processor:  ✓
Trade Manager:     ✓
Trade Logger:      data_cache/trade_decisions.db
Session Stats:     ✓

📊 MARKET ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Symbols:     50
Active for Trade:  48 (BTC, ETH excluded - training only)
Top by Volume:     BTC ($15.2B), ETH ($8.5B), SOL ($2.1B)

🧠 MODULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Orchestrator:      ✓ Clean modules
Dashboard:         PyQt6 + qasync
Subsystems:        stats, dashboard, trailing

════════════════════════════════════════════════════════════════
✅ STARTUP COMPLETE - Ready to trade!
════════════════════════════════════════════════════════════════
```

---

## ✅ 11. Background Tasks Launch

Dopo startup, vengono lanciati **4 task asyncio paralleli**:

```python
tasks = [
    asyncio.create_task(trading_loop()),           # Main trading cycle
    asyncio.create_task(balance_sync_task()),      # Balance updates
    asyncio.create_task(dashboard_update_task()),  # GUI refresh
    asyncio.create_task(partial_exit_monitor())    # Profit taking
]

await asyncio.gather(*tasks)
```

### **Task 1: Trading Loop** (15 min)
- Data collection
- ML predictions
- Signal processing
- Trade execution

### **Task 2: Balance Sync** (60s)
- Fetch balance da Bybit
- Update available margin
- Validate portfolio limits

### **Task 3: Dashboard Update** (30s)
- Fetch positions data
- Update GUI tables
- Refresh statistics

### **Task 4: Partial Exit Monitor** (30s)
- Check ROE targets
- Execute partial exits
- Update remaining position

---

## 🎯 Post-Startup: Primo Ciclo Trading

Dopo startup completo, il bot entra nel suo primo ciclo trading (15 minuti).

Vedi **03-CICLO-TRADING.md** per dettagli completi del loop operativo.

---

## ❌ Troubleshooting Startup Errors

### **Time Sync Failed**
```
❌ Time synchronization failed after 5 attempts
```
**Fix**:
1. Sincronizza clock Windows
2. Disabilita firewall temporaneamente
3. Imposta `MANUAL_TIME_OFFSET` in config.py

### **Authentication Failed**
```
❌ Authentication failed: Invalid API key
```
**Fix**:
1. Verifica `.env` contiene keys corrette
2. Controlla permissions API su Bybit (trade + futures)
3. Verifica IP whitelisting

### **Models Not Found**
```
❌ No model for 15m, and TRAIN_IF_NOT_FOUND disabled
```
**Fix**:
1. Imposta `TRAIN_IF_NOT_FOUND = True`
2. O scarica models pretrained
3. Attendi 15-20 min per training completo

### **OpenAI Connection Failed**
```
❌ Failed to initialize OpenAI client
```
**Fix**:
1. Aggiungi `OPENAI_API_KEY` in `.env`
2. Verifica credito OpenAI account
3. O disabilita: `LLM_ANALYSIS_ENABLED = False`

---

## 📚 Next: Ciclo Trading

Vai a **03-CICLO-TRADING.md** per capire come funziona il loop operativo principale.
