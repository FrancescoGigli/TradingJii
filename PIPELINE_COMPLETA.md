# 📘 PIPELINE COMPLETA DEL TRADING BOT - DOCUMENTAZIONE TECNICA

**Versione:** 1.0  
**Data:** 11 Gennaio 2025  
**Sistema:** Trading Bot Automatizzato per Criptovalute con ML

---

## 📑 INDICE

1. [Panoramica Sistema](#panoramica-sistema)
2. [Fase 0: Avvio del Bot](#fase-0-avvio-del-bot)
3. [Fase 1: Continuous Trading Loop](#fase-1-continuous-trading-loop)
4. [Fase 2: Trading Cycle (7 Fasi)](#fase-2-trading-cycle)
5. [Appendice A: Training Pipeline](#appendice-a-training-pipeline)
6. [Appendice B: Execute Signals](#appendice-b-execute-signals)
7. [Appendice C: Position Management](#appendice-c-position-management)
8. [Appendice D: Trailing Stop System](#appendice-d-trailing-stop-system)
9. [Configurazioni Chiave](#configurazioni-chiave)
10. [Riferimenti File Sorgente](#riferimenti-file-sorgente)

---

## 🎯 PANORAMICA SISTEMA

### **Architettura Generale**

```
┌─────────────────────────────────────────────────────────┐
│                     MAIN.PY                              │
│  (Entry point - coordina tutto il sistema)              │
└──────────────────┬──────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
┌───────▼────────┐   ┌───────▼─────────┐
│  CONFIG.PY     │   │ TRADING ENGINE  │
│  (Parametri)   │   │  (Orchestrator) │
└────────────────┘   └─────────┬───────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
┌───────▼────────┐   ┌────────▼────────┐   ┌────────▼──────────┐
│ ML PREDICTOR   │   │ POSITION MGR    │   │ RISK CALCULATOR   │
│ (XGBoost)      │   │ (Thread-safe)   │   │ (Adaptive Sizing) │
└────────────────┘   └─────────────────┘   └───────────────────┘
```

### **Componenti Principali**

| Componente | File | Scopo |
|------------|------|-------|
| Entry Point | `main.py` | Avvio sistema, init componenti |
| Trading Engine | `trading/trading_engine.py` | Orchestrazione trading loop |
| Market Analyzer | `trading/market_analyzer.py` | Analisi mercato, selezione simboli |
| Signal Processor | `trading/signal_processor.py` | Elaborazione segnali ML |
| Position Manager | `core/position_management/` | Gestione posizioni thread-safe |
| Risk Calculator | `core/risk_calculator.py` | Calcolo margins, risk management |
| Adaptive Sizing | `core/adaptive_position_sizing.py` | Position sizing adattivo |
| ML Models | `model_loader.py`, `trainer.py` | Caricamento/training XGBoost |
| Config | `config.py` | Tutti i parametri configurabili |

---

## 🚀 FASE 0: AVVIO DEL BOT

**File:** `main.py`

### **Entry Point**

```python
if __name__ == "__main__":
    # 1. Setup PyQt6 per dashboard
    app = QApplication(sys.argv)
    
    # 2. Setup qasync event loop (gestisce PyQt + asyncio)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # 3. Avvia main() asincrono
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("👋 Interrupted by user")
    finally:
        loop.close()
```

### **Funzione main() - Inizializzazione Sistema**

#### **STEP 1: CONFIGURAZIONE**

```python
async def main():
    # Inizializza config manager
    config_manager = ConfigManager()
    selected_timeframes, selected_models, demo_mode = config_manager.select_config()
    
    # Parametri selezionati:
    # - selected_timeframes: ["15m", "30m", "1h"]
    # - selected_models: ["xgb"]
    # - demo_mode: False (LIVE MODE) o True (DEMO MODE)
    
    # Registra sistemi core per startup display
    global_startup_collector.set_core_system("position_manager", "FILE PERSISTENCE")
    global_startup_collector.set_core_system("signal_processor", "")
    global_startup_collector.set_core_system("trade_manager", "")
    global_startup_collector.set_core_system("trade_logger", "data_cache/trade_decisions.db")
    global_startup_collector.set_core_system("session_stats", "")
    
    # Registra configurazione
    mode_str = "LIVE (Trading reale)" if not demo_mode else "DEMO MODE"
    global_startup_collector.set_configuration(
        excluded_count=len(EXCLUDED_SYMBOLS),
        excluded_list=EXCLUDED_SYMBOLS,
        mode=mode_str,
        timeframes=selected_timeframes,
        model_type="XGBoost"
    )
```

#### **STEP 2: INIZIALIZZAZIONE EXCHANGE**

```python
async_exchange = await initialize_exchange()
```

**Dettaglio `initialize_exchange()`:**

```python
async def initialize_exchange():
    """
    Inizializza connessione con Bybit exchange
    
    Fasi:
    1. Time Synchronization
    2. Load Markets
    3. Authentication Test
    """
    
    # FASE 1: Time Synchronization
    from core.time_sync_manager import global_time_sync_manager
    
    # Configura aiohttp resolver
    import aiohttp
    from aiohttp.resolver import ThreadedResolver
    
    resolver = ThreadedResolver()
    connector = aiohttp.TCPConnector(resolver=resolver, use_dns_cache=False)
    session = aiohttp.ClientSession(connector=connector)
    
    # Crea exchange con sessione custom
    exchange_config_with_session = {**exchange_config, 'session': session}
    async_exchange = ccxt_async.bybit(exchange_config_with_session)
    
    # Sincronizza timestamp
    sync_success = await global_time_sync_manager.initialize_exchange_time_sync(async_exchange)
    
    if not sync_success:
        raise RuntimeError("Time synchronization failed")
    
    # FASE 2: Load Markets
    await async_exchange.load_markets()
    logging.debug("✅ Markets loaded")
    
    # FASE 3: Test Authentication
    balance = await async_exchange.fetch_balance()
    logging.debug("✅ Bybit authenticated")
    
    # Registra dati connessione
    stats = global_time_sync_manager.get_stats()
    final_time_diff = async_exchange.options.get('timeDifference', 0)
    
    global_startup_collector.set_exchange_connection(
        time_offset=final_time_diff,
        markets=True,
        auth=True
    )
    
    return async_exchange
```

**Time Sync Manager - Dettaglio:**

```python
# core/time_sync_manager.py

async def initialize_exchange_time_sync(exchange):
    """
    Sincronizza timestamp locale con server Bybit
    
    Processo:
    1. Fetch server time: GET /v5/market/time
    2. Calcola offset: server_time - local_time
    3. Retry fino a MAX_RETRIES (5) se fallisce
    4. Imposta timeDifference in exchange.options
    
    Parametri (config.py):
    - TIME_SYNC_MAX_RETRIES = 5
    - TIME_SYNC_RETRY_DELAY = 3 secondi
    - TIME_SYNC_INITIAL_RECV_WINDOW = 120000ms
    - TIME_SYNC_NORMAL_RECV_WINDOW = 300000ms
    - MANUAL_TIME_OFFSET = 0ms (offset manuale)
    """
    
    for attempt in range(TIME_SYNC_MAX_RETRIES):
        try:
            # Fetch server time
            server_time = await exchange.fetch_time()
            local_time = int(time.time() * 1000)
            
            # Calcola offset
            time_diff = server_time - local_time
            
            # Applica offset manuale se configurato
            if MANUAL_TIME_OFFSET != 0:
                time_diff += MANUAL_TIME_OFFSET
            
            # Imposta in exchange
            exchange.options['timeDifference'] = time_diff
            exchange.options['recvWindow'] = TIME_SYNC_NORMAL_RECV_WINDOW
            
            logging.debug(f"✅ Time sync successful: offset={time_diff}ms")
            return True
            
        except Exception as e:
            logging.warning(f"⚠️ Time sync attempt {attempt+1} failed: {e}")
            if attempt < TIME_SYNC_MAX_RETRIES - 1:
                await asyncio.sleep(TIME_SYNC_RETRY_DELAY)
    
    return False
```

#### **STEP 3: INIZIALIZZAZIONE TRADING ENGINE**

```python
trading_engine = TradingEngine(config_manager)
```

**Dettaglio `TradingEngine.__init__()`:**

```python
class TradingEngine:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.first_cycle = True
        
        # 1. CORE COMPONENTS
        self.market_analyzer = global_market_analyzer
        self.signal_processor = global_signal_processor
        
        # 2. DATABASE SYSTEM (optional)
        self.database_system_loaded = self._init_database_system()
        """
        _init_database_system():
            - Importa global_db_cache
            - SQLite database per cache dati
            - display_database_stats per statistiche
        """
        
        # 3. CLEAN MODULES (mandatory)
        self.clean_modules_available = self._init_clean_modules()
        """
        _init_clean_modules():
            - global_order_manager: Gestione ordini Bybit
            - global_risk_calculator: Calcolo margins/risk
            - global_trading_orchestrator: Coordinazione trade
            - global_thread_safe_position_manager: Gestione posizioni
            
            CRITICAL: ThreadSafePositionManager è obbligatorio
        """
        
        # 4. ADAPTIVE SIZING
        self._init_adaptive_sizing()
        """
        _init_adaptive_sizing():
            if ADAPTIVE_SIZING_ENABLED:
                - Inizializza AdaptivePositionSizing(config)
                - Carica memoria da adaptive_sizing_memory.json
                - Modalità: FRESH_START o HISTORICAL
                - Display stats: simboli, win rate, blocked
        """
        
        # 5. INTEGRATED SYSTEMS
        if INTEGRATED_SYSTEMS_AVAILABLE:
            self.session_stats = global_session_statistics
            self.dashboard = TradingDashboard(position_manager, session_stats)
            """
            - session_stats: Traccia performance sessione
            - dashboard: PyQt6 GUI con realtime display
            - trailing monitor: Background task per trailing stops
            """
```

**Adaptive Position Sizing - Dettaglio:**

```python
# core/adaptive_position_sizing.py

class AdaptivePositionSizing:
    """
    Sistema adattivo che impara dalle performance
    
    Regole:
    1. Wallet diviso in 5 blocchi (ADAPTIVE_WALLET_BLOCKS)
    2. Base size = blocco × 0.5 (ADAPTIVE_FIRST_CYCLE_FACTOR)
    3. WIN → size aumenta proporzionalmente al gain
    4. LOSS → reset a base + blocco 3 cicli (ADAPTIVE_BLOCK_CYCLES)
    5. Cap massimo = slot_value × multiplier (ADAPTIVE_CAP_MULTIPLIER)
    """
    
    def __init__(self, config):
        # Parametri da config
        self.wallet_blocks = config.ADAPTIVE_WALLET_BLOCKS  # 5
        self.first_cycle_factor = config.ADAPTIVE_FIRST_CYCLE_FACTOR  # 0.5
        self.block_cycles = config.ADAPTIVE_BLOCK_CYCLES  # 3
        self.cap_multiplier = config.ADAPTIVE_CAP_MULTIPLIER  # 1.0
        self.risk_max_pct = config.ADAPTIVE_RISK_MAX_PCT  # 0.20
        self.loss_multiplier = config.ADAPTIVE_LOSS_MULTIPLIER  # 0.30
        self.fresh_start = config.ADAPTIVE_FRESH_START  # True/False
        
        # Memoria simboli
        self.symbol_memory: Dict[str, SymbolMemory] = {}
        
        # Contatore cicli
        self.current_cycle = 0
        
        # File persistenza
        self.memory_file = Path("adaptive_sizing_memory.json")
        
        # Carica o reset memoria
        self._load_memory()

@dataclass
class SymbolMemory:
    """Memoria persistente per simbolo"""
    symbol: str
    base_size: float              # Size base (ricalcolata ogni ciclo)
    current_size: float           # Size attuale (dopo premi/reset)
    blocked_cycles_left: int      # Cicli blocco rimanenti (0 = sbloccato)
    last_pnl_pct: float          # Ultimo PnL% per audit
    last_cycle_updated: int       # Numero ciclo ultimo update
    total_trades: int             # Totale trade eseguiti
    wins: int                     # Trade vincenti
    losses: int                   # Trade perdenti
    last_updated: str             # Timestamp ultimo update
```

**Esempio Adaptive Sizing:**

```python
# Wallet = $1000
# Blocks = 5
# Slot value = $1000 / 5 = $200
# Base size = $200 × 0.5 = $100

# TRADE 1: SOL/USDT
# - Apertura: $100 margin
# - Risultato: +15% ROE
# - Azione: PREMIO
#   new_size = $100 × 1.15 = $115
# - Prossimo trade SOL: $115 margin

# TRADE 2: MATIC/USDT
# - Apertura: $100 margin (nuovo simbolo)
# - Risultato: -8% ROE
# - Azione: PUNIZIONE
#   new_size = $100 (reset)
#   blocked_cycles = 3
# - Prossimi 3 cicli: MATIC bloccato
# - Dopo 3 cicli: Sblocco con base $100

# TRADE 3: SOL/USDT (secondo trade)
# - Apertura: $115 margin (size aumentata)
# - Risultato: +20% ROE
# - Azione: PREMIO
#   new_size = $115 × 1.20 = $138
# - Prossimo trade SOL: $138 margin (capped a $200)
```

#### **STEP 4: MARKET INITIALIZATION**

```python
await trading_engine.market_analyzer.initialize_markets(
    async_exchange, TOP_ANALYSIS_CRYPTO, EXCLUDED_SYMBOLS
)
```

**Dettaglio `initialize_markets()`:**

```python
# trading/market_analyzer.py

async def initialize_markets(self, exchange, top_n, excluded_symbols):
    """
    Seleziona top N simboli per volume
    
    Processo:
    1. Fetch tutti i markets da Bybit
    2. Filtra solo USDT perpetual
    3. Fetch volume 24h per ogni simbolo
    4. Applica filtri:
       - Volume > MIN_VOLUME_THRESHOLD ($1M)
       - Prezzo > MIN_PRICE_THRESHOLD ($0.001)
       - Non in SYMBOL_BLACKLIST
       - Non in excluded_symbols
    5. Ordina per volume (decrescente)
    6. Prendi top N (default 50)
    
    Parametri config.py:
    - TOP_ANALYSIS_CRYPTO = 50
    - MIN_VOLUME_THRESHOLD = 1_000_000
    - MIN_PRICE_THRESHOLD = 0.001
    - SYMBOL_BLACKLIST = ['XAUT/USDT:USDT', 'PAXG/USDT:USDT']
    """
    
    # Fetch markets
    markets = await exchange.load_markets()
    
    # Filtra USDT perpetual
    usdt_perpetuals = [
        symbol for symbol, market in markets.items()
        if market.get('type') == 'swap' and 
           market.get('quote') == 'USDT' and
           market.get('settle') == 'USDT'
    ]
    
    # Fetch tickers per volume
    tickers = await exchange.fetch_tickers(usdt_perpetuals)
    
    # Prepara lista con volume
    symbols_with_volume = []
    for symbol in usdt_perpetuals:
        ticker = tickers.get(symbol)
        if ticker:
            volume_24h = ticker.get('quoteVolume', 0)
            price = ticker.get('last', 0)
            
            # Applica filtri
            if (volume_24h >= MIN_VOLUME_THRESHOLD and
                price >= MIN_PRICE_THRESHOLD and
                symbol not in SYMBOL_BLACKLIST and
                symbol not in excluded_symbols):
                
                symbols_with_volume.append({
                    'symbol': symbol,
                    'volume': volume_24h,
                    'price': price
                })
    
    # Ordina per volume
    symbols_with_volume.sort(key=lambda x: x['volume'], reverse=True)
    
    # Prendi top N
    self.top_symbols = [s['symbol'] for s in symbols_with_volume[:top_n]]
    
    logging.info(f"✅ Selected {len(self.top_symbols)} symbols")
    
    return self.top_symbols
```

**Esempio Output:**

```
Top 50 symbols selected:
1. SOL/USDT:USDT     - Volume: $2.5B
2. DOGE/USDT:USDT    - Volume: $1.8B
3. AVAX/USDT:USDT    - Volume: $1.2B
4. MATIC/USDT:USDT   - Volume: $980M
5. ADA/USDT:USDT     - Volume: $850M
...
50. FTM/USDT:USDT    - Volume: $120M

Excluded from trading (training only):
- BTC/USDT:USDT
- ETH/USDT:USDT
```

#### **STEP 5: ML MODELS INITIALIZATION**

```python
xgb_models, xgb_scalers = await initialize_models(
    config_manager, top_symbols_training, async_exchange
)
```

**Dettaglio `initialize_models()`:**

```python
async def initialize_models(config_manager, top_symbols_training, exchange):
    """
    Carica o allena modelli XGBoost
    
    Per ogni timeframe in [15m, 30m, 1h]:
        1. Cerca file: trained_models/xgb_model_{tf}.pkl
        2. Se esiste:
           - Carica con joblib.load()
           - Carica scaler con joblib.load()
           - Verifica integrità
        3. Se NON esiste:
           - Controlla TRAIN_IF_NOT_FOUND
           - Se True: avvia training automatico
           - Se False: RuntimeError
    """
    
    xgb_models = {}
    xgb_scalers = {}
    model_status = {}
    
    for tf in config_manager.get_timeframes():  # [15m, 30m, 1h]
        model_path = config.get_xgb_model_file(tf)
        scaler_path = config.get_xgb_scaler_file(tf)
        
        # Prova a caricare modello esistente
        try:
            xgb_models[tf] = joblib.load(model_path)
            xgb_scalers[tf] = joblib.load(scaler_path)
            model_status[tf] = True
            logging.info(f"✅ Loaded model for {tf}")
            
        except FileNotFoundError:
            if config.TRAIN_IF_NOT_FOUND:
                logging.info(f"🎯 Training new model for {tf}")
                
                # Avvia training
                model, scaler, metrics = await train_xgboost_model_wrapper(
                    top_symbols_training,
                    exchange,
                    timestep=config.get_timesteps_for_timeframe(tf),
                    timeframe=tf,
                    use_future_returns=True
                )
                
                xgb_models[tf] = model
                xgb_scalers[tf] = scaler
                model_status[tf] = bool(model and metrics)
            else:
                raise RuntimeError(f"No model for {tf}, TRAIN_IF_NOT_FOUND disabled")
    
    # Display status
    logging.info("🤖 ML MODELS STATUS:")
    for tf, ok in model_status.items():
        status = "✅ READY" if ok else "❌ FAILED"
        logging.info(f"{tf:>5}: {status}")
    
    return xgb_models, xgb_scalers
```

#### **STEP 6: SESSION INITIALIZATION**

```python
await trading_engine.initialize_session(async_exchange)
```

**Dettaglio `initialize_session()`:**

```python
async def initialize_session(self, exchange):
    """
    Inizializza fresh session con position sync
    
    Fasi:
    1. Reset Session
    2. Balance Sync (centralized)
    3. Protect Existing Positions (live mode)
    """
    
    logging.info("🧹 FRESH SESSION STARTUP")
    
    # FASE 1: Reset Session
    if self.clean_modules_available:
        self.position_manager.reset_session()
        """
        reset_session():
            - Pulisce _open_positions
            - Pulisce _closed_positions
            - Reset balance a default
            - Reset counters
        """
    
    # FASE 2: Balance Sync (Single Source of Truth)
    real_balance = None
    if not config.DEMO_MODE:
        # Live Mode: Fetch da Bybit
        real_balance = await get_real_balance(exchange)
        """
        get_real_balance(exchange):
            balance_data = await exchange.fetch_balance()
            usdt_balance = balance_data['USDT']['free']
            return usdt_balance
        """
        
        if real_balance and real_balance > 0:
            # Aggiorna SOLO position manager (single source)
            self.position_manager.update_real_balance(real_balance)
            logging.info(f"💰 Balance synced: ${real_balance:.2f}")
    else:
        # Demo Mode: Usa balance virtuale
        self.position_manager.update_real_balance(config.DEMO_BALANCE)
        logging.info(f"🧪 DEMO MODE: Using ${config.DEMO_BALANCE:.2f}")
    
    # FASE 3: Protect Existing Positions (solo live mode)
    if not config.DEMO_MODE and self.clean_modules_available:
        logging.info("🔄 SYNCING WITH REAL BYBIT POSITIONS")
        
        try:
            protection_results = await self.global_trading_orchestrator.protect_existing_positions(exchange)
            """
            protect_existing_positions(exchange):
                1. Fetch posizioni aperte da Bybit
                   positions = await exchange.fetch_positions()
                
                2. Per ogni posizione:
                   a. Verifica se già in position_manager
                   b. Se NO: importa posizione
                      - Crea ThreadSafePosition
                      - Imposta origin="BYBIT_SYNC"
                      - Calcola PnL corrente
                      - Setta SL/TP corretti
                   c. Se YES: aggiorna dati
                      - Sync current_price
                      - Ricalcola PnL
                      - Verifica SL/TP corretti
                
                3. Registra trailing stops se necessario
                
                Return: Dict[symbol] = ProtectionResult
            """
            
            if protection_results:
                successful = sum(1 for r in protection_results.values() if r.success)
                total = len(protection_results)
                logging.info(f"🛡️ Protected {successful}/{total} existing positions")
            else:
                logging.info("🆕 No existing positions - starting fresh")
                
        except Exception as e:
            logging.warning(f"⚠️ Error during position protection: {e}")
    
    logging.info("✅ Ready for fresh sync")
```

#### **STEP 7-9: FINALIZZAZIONE**

```python
# STEP 7: Realtime Display
initialize_global_realtime_display(trading_engine.position_manager)

# STEP 8: Startup Summary
global_startup_collector.display_startup_summary()
"""
Display bellissimo con ASCII art:
╔═══════════════════════════════════════════════════════════╗
║        🚀 TRADING BOT - STARTUP SUMMARY 🚀                ║
╚═══════════════════════════════════════════════════════════╝

📡 EXCHANGE CONNECTION
  ├─ Exchange: Bybit
  ├─ Time Offset: -1250ms
  ├─ Markets: ✅ Loaded
  └─ Authentication: ✅ Success

🔧 CORE SYSTEMS
  ├─ Position Manager: FILE PERSISTENCE
  ├─ Signal Processor: ✅
  ├─ Trade Manager: ✅
  ├─ Trade Logger: data_cache/trade_decisions.db
  └─ Session Stats: ✅

⚙️ CONFIGURATION
  ├─ Mode: LIVE (Trading reale)
  ├─ Timeframes: 15m, 30m, 1h
  ├─ Model Type: XGBoost
  └─ Excluded Symbols: 0

📊 MARKET ANALYSIS
  ├─ Total Symbols Analyzed: 50
  └─ Active Symbols: 50

🎯 MODULES
  ├─ Orchestrator: ✅ Available
  ├─ Dashboard: PyQt6 + qasync
  └─ Subsystems: stats, dashboard, trailing
"""

# STEP 9: Start Trading Loop
await trading_engine.run_continuous_trading(
    async_exchange, xgb_models, xgb_scalers
)
```

---

## 🔄 FASE 1: CONTINUOUS TRADING LOOP

**File:** `trading/trading_engine.py`

### **Run Continuous Trading**

```python
async def run_continuous_trading(self, exchange, xgb_models, xgb_scalers):
    """
    Trading continuo con sistemi integrati
    
    Task paralleli:
    1. Trading Cycle (ogni 15 min)
    2. Trailing Monitor (ogni 60s)
    3. Dashboard Display (ogni 30s)
    4. Balance Sync (ogni 60s)
    """
    
    # ═══════════════════════════════════════════════════
    # INIZIALIZZAZIONE STATISTICS
    # ═══════════════════════════════════════════════════
    if self.session_stats:
        if not config.DEMO_MODE:
            real_balance = await get_real_balance(exchange)
            if real_balance and real_balance > 0:
                self.session_stats.initialize_balance(real_balance)
                logging.info(f"📊 Session stats: ${real_balance:.2f}")
        else:
            self.session_stats.initialize_balance(config.DEMO_BALANCE)
            logging.info(f"📊 Session stats: ${config.DEMO_BALANCE:.2f} (DEMO)")
    
    # ═══════════════════════════════════════════════════
    # AVVIO TASK PARALLELI
    # ═══════════════════════════════════════════════════
    if INTEGRATED_SYSTEMS_AVAILABLE and self.dashboard and self.session_stats:
        logging.info("🚀 Starting INTEGRATED SYSTEMS")
        
        # Task 1: Trading Loop (ogni 15 min)
        trading_task = asyncio.create_task(
            self._trading_loop(exchange, xgb_models, xgb_scalers)
        )
        
        # Task 2: Trailing Monitor (ogni 60s)
        trailing_task = asyncio.create_task(
            run_integrated_trailing_monitor(
                exchange, self.position_manager, self.session_stats
            )
        )
        
        # Task 3: Dashboard (ogni 30s)
        dashboard_task = asyncio.create_task(
            self.dashboard.run_live_dashboard(exchange, update_interval=30)
        )
        
        # Task 4: Balance Sync (ogni 60s)
        balance_sync_task = asyncio.create_task(
            self._balance_sync_loop(exchange)
        )
        
        try:
            # Esegui tutti in parallelo
            await asyncio.gather(
                trading_task,
                trailing_task,
                dashboard_task,
                balance_sync_task
            )
        except KeyboardInterrupt:
            logging.info("⛔ Trading stopped by user")
            # Cancel gracefully
            for task in [trading_task, trailing_task, dashboard_task, balance_sync_task]:
                task.cancel()
            await asyncio.gather(*[trading_task, trailing_task, dashboard_task, balance_sync_task], return_exceptions=True)
    else:
        # Fallback: Basic mode
        logging.warning("⚠️ Running in BASIC MODE")
        await self._trading_loop(exchange, xgb_models, xgb_scalers)
```

### **Task 1: Trading Loop**

```python
async def _trading_loop(self, exchange, xgb_models, xgb_scalers):
    """
    Loop principale trading (ogni 15 minuti)
    """
    cycle_count = 0
    
    while True:
        try:
            cycle_count += 1
            
            # Time sync ogni 5 cicli (ogni ~75 minuti)
            if cycle_count % 5 == 0:
                from core.time_sync_manager import global_time_sync_manager
                logging.info(f"🕐 CYCLE {cycle_count}: Forcing timestamp sync...")
                sync_success = await global_time_sync_manager.force_time_sync(exchange)
                if sync_success:
                    logging.info("✅ Timestamp sync successful")
            
            # Esegui ciclo trading completo
            await self.run_trading_cycle(exchange, xgb_models, xgb_scalers)
            
            # Attendi 15 minuti con countdown
            await self._wait_with_countdown(config.TRADE_CYCLE_INTERVAL)
            
        except KeyboardInterrupt:
            logging.info("⛔ Trading loop stopped")
            break
        except Exception as e:
            logging.error(f"❌ Error in trading cycle: {e}", exc_info=True)
            await asyncio.sleep(60)
```

### **Task 2: Trailing Monitor**

```python
# core/integrated_trailing_monitor.py

async def run_integrated_trailing_monitor(exchange, position_manager, session_stats):
    """
    Background task per trailing stops (ogni 60s)
    
    Monitora posizioni in profit e aggiorna trailing stops
    """
    logging.info("🎪 Trailing Monitor started (60s interval)")
    
    while True:
        try:
            await asyncio.sleep(config.TRAILING_UPDATE_INTERVAL)  # 60s
            
            if not config.TRAILING_ENABLED:
                continue
            
            # Update trailing stops
            updates_count = await position_manager.update_trailing_stops(exchange)
            
            if updates_count > 0 and not config.TRAILING_SILENT_MODE:
                logging.info(f"🎪 Trailing stops updated: {updates_count} positions")
                
        except asyncio.CancelledError:
            logging.info("🎪 Trailing Monitor stopped")
            break
        except Exception as e:
            logging.error(f"❌ Trailing monitor error: {e}")
            await asyncio.sleep(60)
```

### **Task 3: Dashboard Display**

```python
# core/trading_dashboard.py

async def run_live_dashboard(self, exchange, update_interval=30):
    """
    Dashboard PyQt6 con realtime updates (ogni 30s)
    """
    logging.info(f"📊 Dashboard started ({update_interval}s updates)")
    
    while True:
        try:
            await asyncio.sleep(update_interval)
            
            # Fetch dati aggiornati
            session_summary = self.position_manager.safe_get_session_summary()
            active_positions = self.position_manager.safe_get_all_active_positions()
            
            # Update GUI
            self.update_dashboard(session_summary, active_positions)
            
        except asyncio.CancelledError:
            logging.info("📊 Dashboard stopped")
            break
        except Exception as e:
            logging.error(f"❌ Dashboard error: {e}")
            await asyncio.sleep(30)
```

### **Task 4: Balance Sync**

```python
async def _balance_sync_loop(self, exchange):
    """
    Background sync balance da Bybit (ogni 60s)
    
    Mantiene balance aggiornato senza race conditions
    """
    if config.DEMO_MODE:
        logging.info("🧪 DEMO MODE: Balance sync disabled")
        return
    
    SYNC_INTERVAL = 60  # 60 secondi
    logging.info(f"💰 Balance sync started (interval: {SYNC_INTERVAL}s)")
    
    while True:
        try:
            await asyncio.sleep(SYNC_INTERVAL)
            
            # Fetch real balance
            real_balance = await get_real_balance(exchange)
            
            if real_balance and real_balance > 0:
                # Update position manager (single source)
                old_balance = self.position_manager.safe_get_session_summary().get('balance', 0.0)
                self.position_manager.update_real_balance(real_balance)
                
                # Log solo se cambio significativo (> $1)
                balance_change = abs(real_balance - old_balance)
                if balance_change > 1.0:
                    logging.info(f"💰 Balance: ${old_balance:.2f} → ${real_balance:.2f} ({real_balance - old_balance:+.2f})")
                
        except asyncio.CancelledError:
            logging.info("💰 Balance sync stopped")
            break
        except Exception as e:
            logging.error(f"❌ Balance sync error: {e}")
            await asyncio.sleep(SYNC_INTERVAL)
```

---

## 🎯 FASE 2: TRADING CYCLE

**File:** `trading/trading_engine.py`

Il ciclo di trading si ripete ogni 15 minuti ed è diviso in 7 fasi sequenziali.

### **Overview Trading Cycle**

```
Cycle Start (t=0)
│
├─ [FASE 1] Data Collection (30-60s)
│   └─ Download OHLCV + calcolo indicators
│
├─ [FASE 2] ML Predictions (10-20s)
│   └─ XGBoost inference multi-timeframe
│
├─ [FASE 3] Signal Processing (5s)
│   └─ Ensemble voting + filtering
│
├─ [FASE 4] Ranking (1s)
│   └─ Ordina per confidence
│
├─ [FASE 5] Trade Execution (30-60s)
│   └─ Apre posizioni con adaptive sizing
│
├─ [FASE 6] Position Management (20-40s)
│   └─ Sync, trailing, safety checks
│
└─ [FASE 7] Reporting (5s)
    └─ Performance summary + display

Total: ~2-3 minuti
Wait: 15 minuti - cycle_time
```

### **FASE 1: Data Collection & Market Analysis**

```python
all_symbol_data, complete_symbols, data_fetch_time = \
    await self.market_analyzer.collect_market_data(
        exchange,
        self.config_manager.get_timeframes(),  # [15m, 30m, 1h]
        config.TOP_ANALYSIS_CRYPTO,            # 50
        config.EXCLUDED_SYMBOLS
    )
```

**Dettaglio `collect_market_data()`:**

```python
# trading/market_analyzer.py

async def collect_market_data(self, exchange, timeframes, top_n, excluded):
    """
    Raccoglie dati OHLCV + indicators per tutti i simboli
    
    Per ogni simbolo:
        Per ogni timeframe:
            1. Controlla cache database
            2. Se cache valida (<3 min): usa cached
            3. Altrimenti: fetch da Bybit
            4. Calcola 33 indicators
            5. Salva in cache
            6. Store in all_symbol_data
    
    Returns:
        all_symbol_data: Dict[symbol][timeframe] = DataFrame
        complete_symbols: List simboli con dati completi
        fetch_time: Tempo totale operazione
    """
    
    start_time = time.time()
    all_symbol_data = {}
    complete_symbols = []
    
    for symbol in self.top_symbols:
        if symbol in excluded:
            continue
        
        symbol_data = {}
        has_all_timeframes = True
        
        for tf in timeframes:
            try:
                # Fetch con cache intelligente
                df = await fetch_and_save_data(exchange, symbol, tf)
                
                if df is not None and len(df) > 0:
                    symbol_data[tf] = df
                else:
                    has_all_timeframes = False
                    break
                    
            except Exception as e:
                logging.warning(f"⚠️ {symbol} {tf}: {e}")
                has_all_timeframes = False
                break
        
        if has_all_timeframes:
            all_symbol_data[symbol] = symbol_data
            complete_symbols.append(symbol)
    
    fetch_time = time.time() - start_time
    
    logging.info(f"📊 Data collected: {len(complete_symbols)}/{len(self.top_symbols)} symbols in {fetch_time:.1f}s")
    
    return all_symbol_data, complete_symbols, fetch_time
```

**Calcolo 33 Indicators:**

```python
# fetcher.py

async def fetch_and_save_data(exchange, symbol, timeframe):
    """
    Fetch OHLCV e calcola indicators
    """
    
    # 1. Controlla cache
    if ENABLE_DATA_CACHE:
        cached_df = load_from_cache(symbol, timeframe)
        if cached_df is not None and is_cache_valid(cached_df):
            return cached_df
    
    # 2. Fetch da Bybit
    ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=200)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # 3. Calcola indicators
    df = calculate_all_indicators(df)
    """
    calculate_all_indicators():
        # Trend
        df['ema5'] = ta.trend.ema_indicator(close, 5)
        df['ema10'] = ta.trend.ema_indicator(close, 10)
        df['ema20'] = ta.trend.ema_indicator(close, 20)
        
        # MACD
        macd = ta.trend.MACD(close)
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_histogram'] = macd.macd_diff()
        
        # Momentum
        df['rsi_fast'] = ta.momentum.rsi(close, 14)
        df['stoch_rsi'] = ta.momentum.stochrsi(close, 14)
        
        # Volatility
        df['atr'] = ta.volatility.average_true_range(high, low, close, 14)
        bollinger = ta.volatility.BollingerBands(close, 20, 2)
        df['bollinger_hband'] = bollinger.bollinger_hband()
        df['bollinger_lband'] = bollinger.bollinger_lband()
        
        # Volume
        df['vwap'] = ta.volume.volume_weighted_average_price(high, low, close, volume)
        df['obv'] = ta.volume.on_balance_volume(close, volume)
        
        # Trend Strength
        df['adx'] = ta.trend.adx(high, low, close, 14)
        
        # Volatility
        df['volatility'] = df['close'].pct_change().rolling(20).std()
        
        # Price Position vs EMAs
        df['price_pos_5'] = (df['close'] - df['ema5']) / df['ema5']
        df['price_pos_10'] = (df['close'] - df['ema10']) / df['ema10']
        df['price_pos_20'] = (df['close'] - df['ema20']) / df['ema20']
        
        # Custom Features
        df['vol_acceleration'] = df['volume'].pct_change()
        df['atr_norm_move'] = (df['high'] - df['low']) / df['atr']
        df['momentum_divergence'] = df['rsi_fast'].diff()
        df['volatility_squeeze'] = (df['bollinger_hband'] - df['bollinger_lband']) / df['close']
        
        # Support/Resistance distances
        df['resistance_dist_10'] = (df['high'].rolling(10).max() - df['close']) / df['close']
        df['resistance_dist_20'] = (df['high'].rolling(20).max() - df['close']) / df['close']
        df['support_dist_10'] = (df['close'] - df['low'].rolling(10).min()) / df['close']
        df['support_dist_20'] = (df['close'] - df['low'].rolling(20).min()) / df['close']
        
        # Price acceleration
        df['price_acceleration'] = df['close'].pct_change().diff()
        
        # Volume-price alignment
        df['vol_price_alignment'] = df['volume'].pct_change() * df['close'].pct_change()
        
        # Fill NaN
        df = df.fillna(0)
        
        Return df with 33 indicators
    """
    
    # 4. Salva in cache
    if ENABLE_DATA_CACHE:
        save_to_cache(df, symbol, timeframe)
    
    return df
```

### **FASE 2: ML Predictions & AI Analysis**

```python
prediction_results, ml_time = \
    await self.market_analyzer.generate_ml_predictions(
        xgb_models,
        xgb_scalers,
        timestep=config.get_timesteps_for_timeframe("15m")
    )
```

**Dettaglio `generate_ml_predictions()`:**

```python
async def generate_ml_predictions(self, xgb_models, xgb_scalers, timestep):
    """
    Genera predizioni ML per tutti simboli e timeframes
    
    Per ogni simbolo:
        Per ogni timeframe:
            1. Prepara data (numpy array)
            2. Crea sequenza temporale
            3. Create temporal features (66)
            4. Scala features
            5. Predizione XGBoost
            6. Store risultati
    """
    
    start_time = time.time()
    prediction_results = {}
    
    for symbol, symbol_data in self.all_symbol_data.items():
        predictions = {}
        
        for tf in ['15m', '30m', '1h']:
            df = symbol_data.get(tf)
            if df is None:
                continue
            
            # 1. Prepare data
            data = prepare_data(df)
            """
            prepare_data(df):
                # Estrai solo EXPECTED_COLUMNS (33)
                columns = config.EXPECTED_COLUMNS
                data = df[columns].values
                
                # Replace NaN/Inf
                data = np.nan_to_num(data, nan=0.0, posinf=1e6, neginf=-1e6)
                
                return data  # Shape: (n_candles, 33)
            """
            
            if len(data) < timestep + 3:
                continue
            
            # 2. Crea sequenza temporale
            timesteps = config.get_timesteps_for_timeframe(tf)
            sequence = data[-timesteps:]  # Ultimi N candles
            
            # 3. Create temporal features
            temporal_features = create_temporal_features(sequence)
            """
            create_temporal_features(sequence):
                # (Vedi dettaglio in Appendice A: Training)
                
                features = []
                
                # Current State (33)
                features.extend(sequence[-1])
                
                # Momentum Patterns (27)
                for col_idx in important_features:
                    col_data = sequence[:, col_idx]
                    time_index = np.arange(len(col_data))
                    correlation = np.corrcoef(time_index, col_data)[0,1]
                    features.append(correlation if np.isfinite(correlation) else 0.0)
                
                # Critical Stats (6)
                for feature_name in ['close', 'volume', 'rsi', 'atr', 'macd', 'ema20']:
                    col_data = sequence[:, col_idx]
                    volatility = np.std(col_data) / (np.mean(np.abs(col_data)) + 1e-8)
                    features.append(volatility)
                
                # Clean & validate
                features = np.array(features, dtype=np.float64)
                features = np.nan_to_num(features, nan=0.0, posinf=1e6, neginf=-1e6)
                
                return features.flatten()[:66]  # Exactly 66 features
            """
            
            # 4. Scala features
            X = temporal_features.reshape(1, -1)
            X_scaled = xgb_scalers[tf].transform(X)
            
            # 5. Predizione XGBoost
            y_pred = xgb_models[tf].predict(X_scaled)[0]
            y_prob = xgb_models[tf].predict_proba(X_scaled)[0]
            
            # y_pred: 0=SELL, 1=BUY, 2=NEUTRAL
            # y_prob: [p_sell, p_buy, p_neutral]
            
            signal_map = {0: 'SELL', 1: 'BUY', 2: 'NEUTRAL'}
            signal = signal_map[y_pred]
            confidence = y_prob[y_pred]
            
            # 6. Store risultati
            predictions[tf] = {
                'signal': signal,
                'confidence': float(confidence),
                'probabilities': y_prob.tolist()
            }
        
        if predictions:
            prediction_results[symbol] = predictions
    
    ml_time = time.time() - start_time
    
    logging.info(f"🧠 ML predictions: {len(prediction_results)} symbols in {ml_time:.1f}s")
    
    return prediction_results, ml_time
```

### **FASE 3: Signal Processing & Filtering**

```python
all_signals = await self.signal_processor.process_prediction_results(
    prediction_results, all_symbol_data
)
```

**Dettaglio `process_prediction_results()`:**

```python
# trading/signal_processor.py

async def process_prediction_results(self, prediction_results, all_symbol_data):
    """
    Processa predizioni ML con ensemble voting
    
    Per ogni simbolo:
        1. Ensemble voting multi-timeframe
        2. Calcola confidence finale
        3. Determina segnale finale
        4. Applica filtri
        5. Crea signal object
    """
    
    all_signals = []
