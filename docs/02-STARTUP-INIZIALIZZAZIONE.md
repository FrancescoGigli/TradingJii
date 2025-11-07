# 🚀 02 - Startup e Inizializzazione

Questo documento spiega in dettaglio il processo di avvio del bot, dalle primissime righe di codice fino al primo ciclo di trading.

---

## 📋 Indice

1. [Main Entry Point](#main-entry-point)
2. [Configurazione Iniziale](#configurazione-iniziale)
3. [Time Sync con Bybit](#time-sync-con-bybit)
4. [Caricamento Modelli ML](#caricamento-modelli-ml)
5. [Inizializzazione Sessione](#inizializzazione-sessione)
6. [Avvio Task Paralleli](#avvio-task-paralleli)
7. [Log Reali di Startup](#log-reali-di-startup)

---

## 1️⃣ Main Entry Point

### **Codice (main.py):**

```python
if __name__ == "__main__":
    # 1. Crea QApplication per dashboard PyQt6
    app = QApplication(sys.argv)
    
    # 2. Crea qasync event loop (integra asyncio + Qt)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    try:
        # 3. Esegue funzione main() in modo async
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("👋 Interrupted by user")
    finally:
        loop.close()
```

### **Cosa fa:**

1. **QApplication**: Crea applicazione Qt per la dashboard grafica
2. **QEventLoop**: Integra asyncio con Qt (permette GUI responsive + async tasks)
3. **run_until_complete()**: Esegue `main()` e aspetta completamento
4. **Error handling**: Gestisce Ctrl+C e chiusura pulita

### **Perché qasync?**

```
PROBLEMA: PyQt6 usa event loop sincrono
          asyncio usa event loop asincrono
          → Incompatibili!

SOLUZIONE: qasync fonde i due event loop
           → Dashboard resta responsive mentre esegui operazioni async
```

---

## 2️⃣ Configurazione Iniziale

### **Step 2.1: ConfigManager Selection**

```python
async def main():
    # Log startup
    logging.debug("🚀 Starting Trading Bot")
    
    # Menu interattivo
    config_manager = ConfigManager()
    selected_timeframes, selected_models, demo_mode = config_manager.select_config()
```

### **Menu Interattivo:**

```
═══════════════════════════════════════════════
🤖  TRAE TRADING BOT - Configuration Menu
═══════════════════════════════════════════════

Select Operating Mode:
1. 💵 LIVE Trading (Real money on Bybit)
2. 🧪 DEMO Mode (Paper trading - $1000 virtual)

Enter choice (1-2): 2

───────────────────────────────────────────────
📊 Timeframe Selection
───────────────────────────────────────────────
Available timeframes:
  [x] 15m (Fast signals)
  [x] 30m (Medium signals)
  [x] 1h  (Slow signals)
  [ ] 4h  (Very slow signals)

Press Enter to continue with selected...

───────────────────────────────────────────────
🤖 Model Selection
───────────────────────────────────────────────
1. XGBoost (Recommended - Gradient Boosting)

Enter choice (1): 1

✅ Configuration saved!
   Mode: DEMO MODE ($1000 virtual)
   Timeframes: 15m, 30m, 1h
   Model: XGBoost
```

### **Cosa succede:**

```python
# ConfigManager modifica config.py runtime
import config
config.DEMO_MODE = True  # Se selezioni DEMO
config.DEMO_BALANCE = 1000.0

# Registra configurazione nel startup collector
global_startup_collector.set_configuration(
    excluded_count=len(EXCLUDED_SYMBOLS),
    excluded_list=EXCLUDED_SYMBOLS,
    mode="DEMO MODE" if demo_mode else "LIVE (Trading reale)",
    timeframes=selected_timeframes,
    model_type="XGBoost"
)
```

---

## 3️⃣ Time Sync con Bybit

### **Il Problema del Timestamp:**

```
❌ PROBLEMA:
   Bybit API richiede timestamp sincronizzato
   Se clock locale è SBALLATO → API rejection!
   
   Error: "timestamp for this request is outside of the recvWindow"
```

### **La Soluzione (Time Sync):**

```python
async def initialize_exchange():
    """Initialize and test exchange connection with robust timestamp sync"""
    
    logging.debug("⏰ Starting time sync...")
    
    # FASE 1: Pre-authentication time sync
    for attempt in range(1, TIME_SYNC_MAX_RETRIES + 1):
        try:
            # Step 1: Fetch server time (API pubblica, no auth)
            server_time = await async_exchange.fetch_time()
            local_time = async_exchange.milliseconds()
            
            # Step 2: Calcola differenza
            time_diff = server_time - local_time
            
            # Step 3: Applica offset manuale (se configurato)
            if MANUAL_TIME_OFFSET is not None:
                time_diff += MANUAL_TIME_OFFSET
            
            # Step 4: Salva in exchange options
            async_exchange.options['timeDifference'] = time_diff
            
            # Step 5: Verifica con secondo fetch
            await asyncio.sleep(0.5)  # Delay per network latency
            verify_server_time = await async_exchange.fetch_time()
            verify_local_time = async_exchange.milliseconds()
            verify_adjusted_time = verify_local_time + time_diff
            verify_diff = abs(verify_server_time - verify_adjusted_time)
            
            # Step 6: Accetta se < 2 secondi
            if verify_diff < 2000:
                logging.info(f"✅ Time sync OK (offset: {time_diff}ms)")
                sync_success = True
                break
            else:
                logging.debug(f"⚠️ Verification failed: {verify_diff}ms")
                if attempt < TIME_SYNC_MAX_RETRIES:
                    delay = TIME_SYNC_RETRY_DELAY * attempt  # Exponential backoff
                    await asyncio.sleep(delay)
                    
        except Exception as e:
            logging.error(f"❌ Sync attempt {attempt} failed: {e}")
            if attempt < TIME_SYNC_MAX_RETRIES:
                delay = TIME_SYNC_RETRY_DELAY * attempt
                await asyncio.sleep(delay)
    
    if not sync_success:
        raise RuntimeError("Time synchronization failed after 5 attempts")
    
    # FASE 2: Load markets (ora safe con tempo sincronizzato)
    await async_exchange.load_markets()
    
    # FASE 3: Test authenticated API
    balance = await async_exchange.fetch_balance()
    logging.debug("✅ Bybit authenticated")
    
    return async_exchange
```

### **Parametri Configurabili (config.py):**

```python
TIME_SYNC_MAX_RETRIES = 5         # Max tentativi sync
TIME_SYNC_RETRY_DELAY = 3         # Secondi tra retry
TIME_SYNC_NORMAL_RECV_WINDOW = 300000  # 300s finestra ricezione
MANUAL_TIME_OFFSET = 0            # Offset manuale (ms)
```

### **Scenario Reale:**

```
Laptop con Windows 10
Clock locale: 08:26:49 (3 secondi INDIETRO)
Server Bybit: 08:26:52

SYNC PROCESS:
1. Fetch server time: 1699012012000 ms
2. Local time:        1699012009000 ms
3. Diff:              +3000 ms
4. Apply offset:      time_diff = 3000 + MANUAL_TIME_OFFSET(0) = 3000
5. Save:              exchange.options['timeDifference'] = 3000
6. Verify:            |server - (local + 3000)| = 500ms < 2000ms ✅

RESULT: ✅ Time sync OK (offset: 3000ms)
```

---

## 4️⃣ Caricamento Modelli ML

### **Step 4.1: Check Modelli Esistenti**

```python
async def initialize_models(config_manager, top_symbols_training, exchange):
    """Load or train ML models"""
    
    ensure_trained_models_dir()  # Crea cartella trained_models/ se non esiste
    
    logging.debug("🧠 Initializing ML models...")
    
    xgb_models, xgb_scalers = {}, {}
    
    for tf in config_manager.get_timeframes():  # ['15m', '30m', '1h']
        # 1. Prova a caricare da disco
        xgb_models[tf], xgb_scalers[tf] = await asyncio.to_thread(
            load_xgboost_model_func, tf
        )
        
        if not xgb_models[tf]:
            # 2. Se manca, addestra nuovo modello
            if TRAIN_IF_NOT_FOUND:
                logging.info(f"🎯 Training new model for {tf}")
                xgb_models[tf], xgb_scalers[tf], metrics = await train_xgboost_model_wrapper(
                    top_symbols_training,
                    exchange,
                    timestep=get_timesteps_for_timeframe(tf),
                    timeframe=tf
                )
            else:
                raise RuntimeError(f"No model for {tf}, and TRAIN_IF_NOT_FOUND disabled")
    
    return xgb_models, xgb_scalers
```

### **File Modelli:**

```
trained_models/
├── xgb_model_15m.pkl    → Modello XGBoost per 15m (~2MB)
├── xgb_scaler_15m.pkl   → StandardScaler per 15m (~50KB)
├── xgb_model_30m.pkl    → Modello XGBoost per 30m
├── xgb_scaler_30m.pkl   → StandardScaler per 30m
├── xgb_model_1h.pkl     → Modello XGBoost per 1h
└── xgb_scaler_1h.pkl    → StandardScaler per 1h
```

### **Training Process (se modelli mancano):**

```python
async def train_xgboost_model_wrapper(symbols, exchange, timestep, timeframe):
    """
    1. Download dati storici (180 giorni)
    2. Calcola indicatori tecnici (33 features)
    3. Crea temporal features (66 features totali)
    4. Label data (future returns)
    5. Split train/test (80/20)
    6. Train XGBoost con cross-validation
    7. Salva model + scaler
    """
    # ... (dettagli in documento 04-ML-PREDICTION-SYSTEM.md)
```

**Timing:**
- Load modello esistente: ~100ms per timeframe
- Train nuovo modello: ~10-15 minuti per timeframe

---

## 5️⃣ Inizializzazione Sessione

### **Step 5.1: Fresh Session Startup**

```python
async def initialize_session(self, exchange):
    """Initialize fresh session with position sync"""
    
    logging.info("🧹 FRESH SESSION STARTUP")
    
    # 1. Reset position manager
    if self.clean_modules_available:
        self.position_manager.reset_session()
    
    # 2. Sync balance from Bybit
    real_balance = None
    if not config.DEMO_MODE:
        real_balance = await get_real_balance(exchange)
        
        if real_balance and real_balance > 0:
            # Update position manager (single source of truth)
            self.position_manager.update_real_balance(real_balance)
            logging.info(f"💰 Balance synced: ${real_balance:.2f}")
    else:
        # Demo mode
        self.position_manager.update_real_balance(config.DEMO_BALANCE)
        logging.info(f"🧪 DEMO MODE: Using ${config.DEMO_BALANCE:.2f}")
    
    logging.info("✅ Ready for fresh sync")
    
    # 3. Sync existing positions from Bybit
    if not config.DEMO_MODE:
        logging.info("🔄 SYNCING WITH REAL BYBIT POSITIONS")
        try:
            protection_results = await self.global_trading_orchestrator.protect_existing_positions(exchange)
            
            if protection_results:
                successful = sum(1 for r in protection_results.values() if r.success)
                total = len(protection_results)
                logging.info(f"🛡️ Protected {successful}/{total} existing positions")
            else:
                logging.info("🆕 No existing positions - starting fresh")
                
        except Exception as e:
            logging.warning(f"⚠️ Error during position protection: {e}")
```

### **Step 5.2: Protect Existing Positions**

```python
async def protect_existing_positions(self, exchange):
    """
    Sync posizioni reali da Bybit e applica Stop Loss -5%
    """
    # 1. Fetch posizioni da Bybit
    real_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
    active_positions = [p for p in real_positions if float(p.get('contracts', 0) or 0) != 0]
    
    if not active_positions:
        logging.info("🆕 No existing positions on Bybit - starting fresh")
        return {}
    
    # 2. Sync con ThreadSafePositionManager
    newly_opened, _ = await self.position_manager.thread_safe_sync_with_bybit(exchange)
    
    if newly_opened:
        logging.info(f"📥 Synced {len(newly_opened)} positions from Bybit")
        
    # 3. Applica Stop Loss a posizioni sincronizzate
    for position in newly_opened:
        try:
            symbol = position.symbol
            
            # Calcola SL -5% dal prezzo di entrata
            stop_loss_price = self.risk_calculator.calculate_stop_loss_fixed(
                position.entry_price, position.side
            )
            
            # Applica SL su Bybit
            sl_result = await self.order_manager.set_trading_stop(
                exchange, symbol,
                stop_loss=stop_loss_price,
                take_profit=None
            )
            
            if sl_result.success:
                logging.info(f"✅ {symbol}: Stop Loss set at ${stop_loss_price:.6f}")
                
        except Exception as e:
            logging.error(f"❌ Error applying SL to {symbol}: {e}")
    
    return protection_results
```

**Esempio Scenario Reale:**
```
Bot si riavvia dopo crash
Bybit ha 2 posizioni aperte:
  1. SOL/USDT:USDT - LONG @ $23.45
  2. AVAX/USDT:USDT - SHORT @ $12.30

PROCESSO:
1. Fetch posizioni da Bybit          → 2 found
2. Sync con position_manager         → 2 registered
3. Calcola SL per SOL:  $23.45 × 0.95 = $22.28 (-5%)
4. Calcola SL per AVAX: $12.30 × 1.05 = $12.92 (+5%)
5. Applica SL su Bybit               → 2 protected
6. Log: 🛡️ Protected 2/2 positions   → ✅ Success
```

---

## 6️⃣ Avvio Task Paralleli

### **I 4 Task Async:**

```python
async def run_continuous_trading(self, exchange, xgb_models, xgb_scalers):
    """
    Run continuous trading with integrated systems
    
    4 parallel tasks:
    - Trading cycle (every 15 min)
    - Trailing monitor (every 60s)
    - Dashboard display (every 30s)
    - Balance sync (every 60s)
    """
    
    # Initialize session balance
    if self.session_stats:
        if not config.DEMO_MODE:
            real_balance = await get_real_balance(exchange)
            self.session_stats.initialize_balance(real_balance)
        else:
            self.session_stats.initialize_balance(config.DEMO_BALANCE)
    
    logging.info("🚀 Starting with INTEGRATED SYSTEMS (4 parallel tasks)")
    
    # Create parallel tasks
    trading_task = asyncio.create_task(
        self._trading_loop(exchange, xgb_models, xgb_scalers)
    )
    
    trailing_task = asyncio.create_task(
        run_integrated_trailing_monitor(exchange, self.position_manager, self.session_stats)
    )
    
    dashboard_task = asyncio.create_task(
        self.dashboard.run_live_dashboard(exchange, update_interval=30)
    )
    
    balance_sync_task = asyncio.create_task(
        self._balance_sync_loop(exchange)
    )
    
    try:
        # Run all tasks in parallel
        await asyncio.gather(
            trading_task, 
            trailing_task, 
            dashboard_task, 
            balance_sync_task
        )
    except KeyboardInterrupt:
        logging.info("⛔ Trading stopped by user")
        # Cancel all tasks gracefully
        for task in [trading_task, trailing_task, dashboard_task, balance_sync_task]:
            task.cancel()
```

### **Task Diagram:**

```
┌─────────────────────────────────────────────────────────────┐
│                    ASYNCIO EVENT LOOP                        │
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐                 │
│  │ TRADING LOOP    │  │ TRAILING MONITOR│                 │
│  │ (15 min cycle)  │  │ (60s interval)  │                 │
│  │                 │  │                 │                 │
│  │ • Data fetch    │  │ • Check prices  │                 │
│  │ • ML predict    │  │ • Update SL     │                 │
│  │ • Execute       │  │ • Protect roi   │                 │
│  └─────────────────┘  └─────────────────┘                 │
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐                 │
│  │ DASHBOARD       │  │ BALANCE SYNC    │                 │
│  │ (30s refresh)   │  │ (60s interval)  │                 │
│  │                 │  │                 │                 │
│  │ • Show positions│  │ • Fetch balance │                 │
│  │ • Update GUI    │  │ • Update mgr    │                 │
│  │ • Stats display │  │ • Log changes   │                 │
│  └─────────────────┘  └─────────────────┘                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 7️⃣ Log Reali di Startup

### **Log da output.html (Startup reale - 03/11/2025):**

```
2025-11-03 08:26:49,611 INFO ℹ️ 📊 Calibrazione caricata:
2025-11-03 08:26:49,611 INFO ℹ️    Data creazione: 2025-10-27T15:45:17.881580
2025-11-03 08:26:49,611 INFO ℹ️    Trade analizzati: 4051
2025-11-03 08:26:49,611 INFO ℹ️    Periodo: 2025-09-28T00:30:00 to 2025-10-27T14:15:00

2025-11-03 08:27:02,926 INFO ℹ️ ✅ Time sync OK (offset: 998ms)

2025-11-03 08:27:06,164 INFO ℹ️ 🔒 TradingOrchestrator using ThreadSafePositionManager ONLY

2025-11-03 08:27:06,166 WARNING ⚠️ 🔄 FRESH START: Previous memory deleted - Starting from scratch

2025-11-03 08:27:06,167 INFO ℹ️ 🎯 Adaptive Position Sizing initialized | Mode: FRESH START MODE | Blocks: 5 | Block cycles: 3

2025-11-03 08:27:06,198 INFO ℹ️ 📊 TradingDashboard initialized (PyQt6 + qasync version)

2025-11-03 08:28:01,744 INFO ℹ️ XGBoost model loaded for 15m
2025-11-03 08:28:01,714 INFO ℹ️ XGBoost model loaded for 30m
2025-11-03 08:28:01,744 INFO ℹ️ XGBoost model loaded for 1h

2025-11-03 08:28:02,024 INFO ℹ️ 💰 Balance synced (centralized): $306.03

2025-11-03 08:28:02,502 WARNING ⚠️ 🚨 LINK opened WITHOUT stop loss!
2025-11-03 08:28:02,502 WARNING ⚠️ 🚨 PUMPFUN opened WITHOUT stop loss!
2025-11-03 08:28:02,502 WARNING ⚠️ 🚨 ADA opened WITHOUT stop loss!
2025-11-03 08:28:02,502 WARNING ⚠️ 🚨 ICP opened WITHOUT stop loss!

2025-11-03 08:28:06,114 INFO ℹ️ 📥 Synced 4 positions from Bybit
2025-11-03 08:28:10,032 INFO ℹ️ 🛡️ Protected 4/4 existing positions

2025-11-03 08:28:10,299 INFO ℹ️ 🚀 Starting with INTEGRATED SYSTEMS (Trading + Trailing + Dashboard + Balance Sync)
```

### **Analisi Log:**

```
⏱️ 08:26:49 → Carica calibrazione ML (4051 trade storici)
⏱️ 08:27:02 → Time sync completato (998ms offset)
⏱️ 08:27:06 → Position manager inizializzato
⏱️ 08:27:06 → Adaptive sizing FRESH START (reset memory)
⏱️ 08:27:06 → Dashboard PyQt6 pronta

TOTALE STARTUP: ~17 secondi
```

---

## ✅ Checklist Startup

### **Pre-Startup:**
- [ ] File `.env` configurato con API keys
- [ ] Modelli ML presenti in `trained_models/`
- [ ] Python 3.11+ installato
- [ ] Dipendenze installate (`pip install -r requirements.txt`)

### **During Startup:**
- [ ] Configurazione selezionata (DEMO/LIVE)
- [ ] Time sync successful (offset < 2s)
- [ ] Modelli caricati per tutti i timeframes
- [ ] Position manager inizializzato
- [ ] Adaptive sizing configurato
- [ ] Dashboard avviata

### **Post-Startup:**
- [ ] 4 task paralleli running
- [ ] Balance sincronizzato
- [ ] Nessun errore nei log
- [ ] Dashboard mostra "Waiting for first cycle..."

---

## 🚨 Troubleshooting Startup

### **Errore: Time Sync Failed**
```bash
❌ Time synchronization failed after 5 attempts
```
**Soluzione:**
1. Verifica connessione internet
2. Sincronizza clock Windows (Settings > Time)
3. Imposta `MANUAL_TIME_OFFSET` in config.py

### **Errore: Model Not Found**
```bash
❌ No model for 15m, and TRAIN_IF_NOT_FOUND disabled
```
**Soluzione:**
1. Imposta `TRAIN_IF_NOT_FOUND = True` in config.py
2. Oppure scarica modelli pre-trained

### **Errore: API Authentication Failed**
```bash
❌ Failed to authenticate with Bybit
```
**Soluzione:**
1. Verifica API keys in `.env`
2. Check permissions API (read + trade)
3. Verifica IP whitelist su Bybit

---

**Prossimo:** [03 - Ciclo Trading Completo](03-CICLO-TRADING-COMPLETO.md) →
