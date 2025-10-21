# 🔍 VERIFICA COMPORTAMENTO BOT - Fase per Fase

Questa guida ti spiega **cosa fa il codice** in ogni fase, così puoi confermare se è il comportamento che ti aspetti.

---

## 🚀 FASE 0: AVVIO DEL BOT

### File: `main.py`

#### Cosa Fa il Codice:

1. **Setup UTF-8** (righe 6-7):
   ```python
   sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
   ```
   - Forza encoding UTF-8 per supportare emoji 🎪 📊 nei log

2. **Crea QApplication** (riga 173):
   ```python
   app = QApplication(sys.argv)
   ```
   - Necessario per dashboard PyQt6

3. **Crea QEventLoop** (riga 176):
   ```python
   loop = QEventLoop(app)
   ```
   - Gestisce operazioni async + GUI insieme

4. **Chiama main()** (riga 180):
   ```python
   loop.run_until_complete(main())
   ```

### ✅ COMPORTAMENTO ATTESO:
- Il bot parte senza errori
- Vedi emoji nei log correttamente

### ❓ DOMANDA PER TE:
**È questo il comportamento che ti aspetti all'avvio?**
- [ ] SÌ, va bene così
- [ ] NO, vorrei modificare qualcosa

---

## 📋 FASE 1: CONFIGURAZIONE INIZIALE

### File: `main.py` → `ConfigManager.select_config()`
### Codice: `bot_config/config_manager.py`

#### Cosa Fa il Codice:

1. **Controlla Variabile BOT_INTERACTIVE** (riga 27):
   ```python
   interactive_mode = os.getenv('BOT_INTERACTIVE', 'false').lower() == 'true'
   ```
   - Se `BOT_INTERACTIVE=true` → Menu interattivo
   - Altrimenti → Headless mode (auto-avvio)

2. **Headless Mode** (default):
   ```python
   mode_input = os.getenv('BOT_MODE', '2')  # Default: LIVE
   tf_input = os.getenv('BOT_TIMEFRAMES', '15m,30m,1h')
   ```
   - Legge da variabili d'ambiente
   - Se non trova variabili, usa default

3. **Interactive Mode** (se abilitato):
   - Mostra menu con countdown 5 secondi
   - Se non premi nulla, usa default

4. **Applica Configurazione** (riga 68):
   ```python
   config.DEMO_MODE = self.demo_mode
   config.ENABLED_TIMEFRAMES = self.selected_timeframes
   ```
   - Modifica le variabili globali in `config.py`

### ✅ COMPORTAMENTO ATTESO:
- **Headless**: Parte automaticamente in LIVE con 15m,30m,1h
- **Interactive**: Ti chiede e attende 5 secondi

### ❓ DOMANDA PER TE:
**Preferisci headless o interactive mode?**
- [ ] Headless (parte subito senza chiedere)
- [ ] Interactive (menu con countdown)
- [ ] Attuale va bene

---

## 🔌 FASE 2: CONNESSIONE BYBIT

### File: `main.py` → `initialize_exchange()`

#### Cosa Fa il Codice (4 FASI):

### **FASE 1: Pre-authentication Time Sync** (righe 54-111)

```python
for attempt in range(1, TIME_SYNC_MAX_RETRIES + 1):
    server_time = await async_exchange.fetch_time()
    local_time = async_exchange.milliseconds()
    time_diff = server_time - local_time
```

**Cosa fa**:
1. Chiama API pubblica Bybit per ottenere server time
2. Confronta con orario locale del PC
3. Calcola differenza in millisecondi
4. Applica offset manuale se configurato
5. Salva differenza: `exchange.options['timeDifference'] = time_diff`
6. Verifica: refetch e controlla che differenza < 2 secondi
7. Se fallisce, retry con exponential backoff

**Perché è CRITICO**:
- Bybit rifiuta richieste se timestamp è sballato >1 secondo
- Senza sync corretto, TUTTE le chiamate API autenticate falliscono

### **FASE 2: Ottimizza recv_window** (riga 114)

```python
async_exchange.options['recvWindow'] = TIME_SYNC_NORMAL_RECV_WINDOW  # 60s
```

**Cosa fa**:
- Imposta finestra temporale accettabile per richieste
- 60 secondi = margine di sicurezza contro desync

### **FASE 3: Load Markets** (riga 119)

```python
await async_exchange.load_markets()
```

**Cosa fa**:
- Scarica lista di TUTTE le coppie trading disponibili su Bybit
- Include info: tick size, min amount, precision, ecc.
- Necessario prima di qualsiasi trading operation

### **FASE 4: Test Authenticated API** (riga 128)

```python
balance = await async_exchange.fetch_balance()
```

**Cosa fa**:
- Testa che le chiavi API funzionino
- Fetch del balance come test
- Se fallisce qui, credenziali sono sbagliate

### ✅ COMPORTAMENTO ATTESO:
- Time sync riesce al primo tentativo (differenza ~300-500ms)
- Markets caricati senza errori
- Balance fetchato correttamente

### ❓ DOMANDA PER TE:
**Questa sincronizzazione temporale è corretta per te?**
- [ ] SÌ, mi serve per evitare errori API
- [ ] NO, vorrei skipparla (NON consigliato)
- [ ] Vorrei capire meglio perché serve

---

## 🧠 FASE 3: CARICAMENTO MODELLI ML

### File: `main.py` → `initialize_models()`

#### Cosa Fa il Codice:

```python
for tf in config_manager.get_timeframes():  # 15m, 30m, 1h
    xgb_models[tf], xgb_scalers[tf] = load_xgboost_model_func(tf)
    
    if not xgb_models[tf]:  # Modello non trovato
        if TRAIN_IF_NOT_FOUND:
            # TRAINING NUOVO MODELLO
            xgb_models[tf], xgb_scalers[tf], metrics = train_xgboost_model_wrapper(...)
```

### **SE MODELLO ESISTE** (file trovato):

1. **Carica modello** da `trained_models/xgb_model_15m.pkl`
2. **Carica scaler** da `trained_models/xgb_scaler_15m.pkl`
3. Verifica che abbiano 70 features corrette
4. Pronto per predictions

### **SE MODELLO NON ESISTE** (prima volta):

1. **Scarica dati storici** per top 50 crypto:
   ```python
   fetch_ohlcv(symbol, timeframe, since=180_days_ago)
   ```
   - 180 giorni di dati per ogni simbolo

2. **Calcola 35 features tecniche**:
   - EMA (5, 10, 20)
   - MACD + signal + histogram
   - RSI fast + Stochastic RSI
   - ATR, Bollinger Bands
   - VWAP, OBV, ADX
   - 15+ features custom (volatility, momentum, ecc.)

3. **Calcola trend features**:
   - Per ogni feature, calcola `current - previous`
   - Risultato: 35 × 2 = 70 features

4. **Labeling**:
   ```python
   future_return = (close[i+3] - close[i]) / close[i]
   if future_return > threshold: label = BUY
   elif future_return < -threshold: label = SELL
   else: label = NEUTRAL
   ```

5. **Training XGBoost**:
   ```python
   model = xgb.XGBClassifier(
       n_estimators=200,
       max_depth=4,
       learning_rate=0.05,
       ...
   )
   model.fit(X_train, y_train)
   ```

6. **Validation**:
   - Cross-validation 3-fold
   - Calcola accuracy, precision, recall, F1

7. **Salva modello** in `trained_models/`

### ✅ COMPORTAMENTO ATTESO:
- Se modelli esistono: Caricamento < 10 secondi
- Se non esistono: Training 10-20 minuti

### ❓ DOMANDA PER TE:
**Il sistema di training automatico va bene?**
- [ ] SÌ, voglio che addestri automaticamente se non trova modelli
- [ ] NO, preferisco addestrare manualmente
- [ ] Vorrei modificare i parametri di training

---

## 🏁 FASE 4: INIZIALIZZAZIONE SESSIONE

### File: `trading_engine.py` → `initialize_session()`

#### Cosa Fa il Codice:

```python
async def initialize_session(self, exchange):
    # 1. Reset position manager
    if self.clean_modules_available:
        self.position_manager.reset_session()
    
    # 2. Sync balance reale da Bybit
    if not config.DEMO_MODE:
        real_balance = await get_real_balance(exchange)
        self.position_manager.update_real_balance(real_balance)
    
    # 3. Proteggi posizioni esistenti
    await self.global_trading_orchestrator.protect_existing_positions(exchange)
```

### **Dettaglio Step 3: protect_existing_positions()**

```python
# Fetch posizioni reali da Bybit
positions = await exchange.fetch_positions()

for position in positions:
    # Registra nel tracker interno
    self.position_manager.register_synced_position(...)
    
    # Controlla se ha Stop Loss
    if not has_stop_loss:
        # Applica SL -5% automatico
        sl_price = entry_price * 0.95  # LONG
        await exchange.set_trading_stop(symbol, stop_loss=sl_price)
```

### ✅ COMPORTAMENTO ATTESO:
- Balance sincronizzato da Bybit
- Posizioni esistenti registrate
- SL -5% applicato se mancante

### ❓ DOMANDA PER TE:
**La protezione automatica delle posizioni esistenti va bene?**
- [ ] SÌ, voglio che applichi SL -5% automaticamente
- [ ] NO, voglio gestire manualmente gli SL
- [ ] Vorrei modificare la percentuale SL

---

## 🔄 FASE 5: TRADING CYCLE (ogni 15 min)

### File: `trading_engine.py` → `run_trading_cycle()`

Questa è la fase principale. Ti spiego ogni sottofase:

### **PHASE 1: Data Collection**

```python
all_symbol_data, complete_symbols = await market_analyzer.collect_market_data(
    exchange, timeframes, TOP_ANALYSIS_CRYPTO, EXCLUDED_SYMBOLS
)
```

**Cosa fa**:
1. Fetch tickers per volume 24h: `exchange.fetch_tickers()`
2. Ordina per volume, prende top 50
3. Per ogni simbolo:
   - Per ogni timeframe (15m, 30m, 1h):
     - **Controlla cache** SQLite prima
     - Se cache valida (< 3 min): usa cache
     - Altrimenti: `exchange.fetch_ohlcv(symbol, tf, limit=180_days)`
     - Calcola 35 features tecniche
     - Verifica >= 50 candele valide
4. Filtra simboli con dati incompleti

### ❓ DOMANDA:
**Cache SQLite di 3 minuti va bene?**
- [ ] SÌ, risparmia API calls
- [ ] NO, voglio dati sempre freschi
- [ ] Vorrei modificare la durata cache

---

### **PHASE 2: ML Predictions**

```python
prediction_results = await market_analyzer.generate_ml_predictions(
    xgb_models, xgb_scalers, timesteps
)
```

**Cosa fa**:
1. Per ogni simbolo con dati completi:
2. Per ogni timeframe:
   ```python
   # Estrai ultimo valore dataframe
   latest_candle = df.iloc[-1]
   
   # Crea feature vector (70 features)
   features = extract_features(latest_candle)
   
   # Normalizza con scaler
   features_scaled = scaler.transform(features)
   
   # Predizione XGBoost
   prediction = model.predict(features_scaled)  # 0=SELL, 1=BUY, 2=NEUTRAL
   confidence = model.predict_proba(features_scaled).max()  # 0.0-1.0
   ```

3. Risultato: `{symbol: {timeframe: {prediction, confidence}}}`

### ❓ DOMANDA:
**Il sistema di predictions va bene?**
- [ ] SÌ, 3 classi (BUY/SELL/NEUTRAL) è corretto
- [ ] Vorrei solo BUY/SELL (no NEUTRAL)
- [ ] Vorrei modificare la confidenza minima

---

### **PHASE 3: Signal Processing**

```python
all_signals = await signal_processor.process_prediction_results(
    prediction_results, all_symbol_data
)
```

**Cosa fa - Ensemble Voting**:
```python
# Per ogni simbolo
for symbol in symbols:
    votes = []
    confidences = []
    
    # Raccogli voti weighted per timeframe
    for tf in ['15m', '30m', '1h']:
        prediction = predictions[symbol][tf]['prediction']
        confidence = predictions[symbol][tf]['confidence']
        weight = TIMEFRAME_WEIGHTS[tf]  # 15m:1.0, 30m:1.2, 1h:1.5
        
        votes.append(prediction * weight)
        confidences.append(confidence * weight)
    
    # Calcola voto finale
    final_vote = sum(votes) / sum(weights)
    final_confidence = sum(confidences) / sum(weights)
    
    # Determina segnale
    if final_vote > 1.5: signal = "BUY"
    elif final_vote < 0.5: signal = "SELL"
    else: signal = "NEUTRAL"
```

**Filtri applicati**:
1. **Skip NEUTRAL** con 70% probabilità (riduce overtrading)
2. **Skip segnali misti** (es. 15m:BUY, 30m:SELL, 1h:BUY)
3. **Skip confidence < 75%**

### ❓ DOMANDA:
**L'ensemble voting va bene?**
- [ ] SÌ, mi piace che 1h pesi più di 15m
- [ ] NO, vorrei pesi uguali per tutti i timeframes
- [ ] Vorrei modificare i pesi

---

### **PHASE 4: Ranking & Selection**

```python
# Ordina per confidence decrescente
signals.sort(key=lambda x: x["confidence"], reverse=True)

# Filtra BTC/ETH (training only)
tradeable = [s for s in signals if s["symbol"] not in EXCLUDED_FROM_TRADING]

# Limita a max 5 posizioni
max_positions = MAX_CONCURRENT_POSITIONS - open_positions_count
signals_to_execute = tradeable[:max_positions]
```

### ❓ DOMANDA:
**MAX 5 posizioni contemporanee va bene?**
- [ ] SÌ, 5 è un buon limite
- [ ] NO, vorrei più posizioni
- [ ] NO, vorrei meno posizioni

---

### **PHASE 5: Trade Execution**

**Calcolo Position Size** (Portfolio-Based):
```python
# Margin base per 10 posizioni target
margin_base = balance_totale / 10

# Applica ratio basato su confidence
if confidence >= 0.75:
    margin = margin_base * 1.0  # Aggressive
elif confidence >= 0.65:
    margin = margin_base * 0.75  # Moderate
else:
    margin = margin_base * 0.60  # Conservative

# Rispetta limiti
margin = max(15, min(150, margin))
```

**Apertura Posizione**:
```python
# 1. Set leverage
await exchange.set_leverage(10, symbol)

# 2. Set isolated margin
await exchange.set_margin_mode('isolated', symbol)

# 3. Calcola contracts
notional = margin * 10  # leva 10x
contracts = notional / current_price

# 4. Apri market order
order = await exchange.create_market_order(symbol, side, contracts)

# 5. Applica SL -5%
sl_price = entry_price * 0.95  # LONG
await exchange.set_trading_stop(symbol, stop_loss=sl_price)
```

### ❓ DOMANDA:
**System position sizing va bene?**
- [ ] SÌ, portfolio-based con 10 target è corretto
- [ ] Vorrei position sizes fisse
- [ ] Vorrei modificare TARGET_POSITIONS

**Leva 10x va bene?**
- [ ] SÌ
- [ ] NO, vorrei leva diversa

**SL fisso -5% va bene?**
- [ ] SÌ
- [ ] NO, vorrei SL dinamico (ATR-based)
- [ ] NO, vorrei altra percentuale

---

### **PHASE 6: Position Management**

```python
# 1. Sync con Bybit
await position_manager.sync_with_bybit(exchange)

# 2. Trailing stops (se abilitato)
if config.TRAILING_ENABLED:
    await position_manager.update_trailing_stops(exchange)

# 3. Auto-fix SL
await position_manager.check_and_fix_stop_losses(exchange)

# 4. Safety check
await position_manager.check_and_close_unsafe_positions(exchange)
```

### ❓ DOMANDA:
**Trailing stops ROE-based va bene?**
- [ ] SÌ, +1% trigger e -8% ROE protection è corretto
- [ ] NO, vorrei modificare i parametri
- [ ] NO, voglio trailing disabilitato

**Safety manager (chiude posizioni < $100) va bene?**
- [ ] SÌ
- [ ] NO, vorrei modificare la soglia
- [ ] NO, voglio gestire manualmente

---

## ⏰ FASE 6: WAITING & BACKGROUND TASKS

### Cosa Fa:

**Main Loop** (ogni 15 min):
```python
while True:
    await self.run_trading_cycle(...)
    await self._wait_with_countdown(900)  # 15 minuti
```

**Background Tasks Paralleli**:

1. **Trailing Monitor** (ogni 30s):
   ```python
   await run_integrated_trailing_monitor(exchange, position_manager)
   ```

2. **Dashboard Update** (ogni 30s):
   ```python
   await dashboard.run_live_dashboard(exchange, update_interval=30)
   ```

3. **Balance Sync** (ogni 60s):
   ```python
   real_balance = await get_real_balance(exchange)
   position_manager.update_real_balance(real_balance)
   ```

### ❓ DOMANDA:
**Intervallo 15 minuti va bene?**
- [ ] SÌ
- [ ] NO, vorrei cicli più frequenti
- [ ] NO, vorrei cicli meno frequenti

---

## 📝 RIEPILOGO DOMANDE CHIAVE

Per aiutarti a verificare, ecco le domande più importanti:

1. **Time sync automatico** è necessario? ➜ [ ] SÌ / [ ] NO
2. **Training automatico modelli** va bene? ➜ [ ] SÌ / [ ] NO
3. **SL automatico -5%** su posizioni esistenti? ➜ [ ] SÌ / [ ] NO
4. **Ensemble voting multi-timeframe**? ➜ [ ] SÌ / [ ] NO
5. **MAX 5 posizioni** contemporanee? ➜ [ ] SÌ / [ ] NO
6. **Portfolio-based sizing** (target 10)? ➜ [ ] SÌ / [ ] NO
7. **Leva 10x**? ➜ [ ] SÌ / [ ] NO
8. **SL fisso -5%**? ➜ [ ] SÌ / [ ] NO
9. **Trailing stops ROE-based**? ➜ [ ] SÌ / [ ] NO
10. **Cicli ogni 15 minuti**? ➜ [ ] SÌ / [ ] NO

---

## 🎯 PROSSIMI PASSI

Rispondimi per ogni fase se:
- ✅ VA BENE COSÌ
- ⚠️ VORREI MODIFICARE (dimmi cosa)
- ❌ NON VA BENE (dimmi perché)

Poi posso fare le modifiche che vuoi o confermare che è tutto corretto!
