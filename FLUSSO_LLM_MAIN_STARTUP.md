# 🚀 FLUSSO SISTEMA LLM: DA MAIN.PY AL TRADE CHIUSO

## 📋 OVERVIEW

Quando lanci `python main.py`, il sistema LLM viene inizializzato **automaticamente in background** e resta in attesa che i trade si chiudano per analizzarli.

---

## 🔄 FLUSSO COMPLETO STEP-BY-STEP

### **FASE 1: STARTUP - main.py**

```python
# 1. Avvio applicazione
python main.py

# 2. main.py esegue:
async def main():
    # A. Inizializza Config Manager
    config_manager = ConfigManager()
    
    # B. Inizializza Exchange (Bybit)
    async_exchange = await initialize_exchange()
    
    # C. Crea Trading Engine
    trading_engine = TradingEngine(config_manager)
    
    # D. Carica ML models (XGBoost)
    xgb_models, xgb_scalers = await initialize_models(...)
    
    # E. Inizializza sessione
    await trading_engine.initialize_session(async_exchange)
    
    # F. AVVIA TRADING LOOP
    await trading_engine.run_continuous_trading(
        async_exchange, xgb_models, xgb_scalers
    )
```

### **FASE 2: INIZIALIZZAZIONE IMPLICITA TRADE ANALYZER**

Il Trade Analyzer **NON viene inizializzato esplicitamente** in main.py!

Si inizializza **automaticamente** quando viene importato:

```python
# In core/position_management/position_core.py

# Import automatico all'avvio
try:
    from core.trade_analyzer import global_trade_analyzer, TradeSnapshot
    TRADE_ANALYZER_AVAILABLE = True
except ImportError:
    TRADE_ANALYZER_AVAILABLE = False
    global_trade_analyzer = None
```

E in `core/trade_analyzer.py`:

```python
# Global instance (inizializzato all'import del modulo)
global_trade_analyzer: Optional[TradeAnalyzer] = None

def initialize_trade_analyzer(config):
    """Inizializza global trade analyzer"""
    global global_trade_analyzer
    global_trade_analyzer = TradeAnalyzer(config)
    return global_trade_analyzer
```

**QUANDO VIENE INIZIALIZZATO?**

Quando il `position_core.py` viene importato per la prima volta:

```python
# In trading_engine.py → __init__()
from core.thread_safe_position_manager import global_thread_safe_position_manager

# Questo importa position_core.py che importa trade_analyzer.py
# → global_trade_analyzer viene creato automaticamente!
```

Il `TradeAnalyzer.__init__()` controlla:

```python
def __init__(self, config):
    # 1. Check se abilitato in config
    self.enabled = getattr(config, 'LLM_ANALYSIS_ENABLED', False)
    
    if not self.enabled:
        logging.info("🤖 Trade Analyzer: DISABLED")
        return
    
    # 2. Check dipendenze OpenAI
    if not OPENAI_AVAILABLE:
        logging.error("❌ OpenAI library not available")
        self.enabled = False
        return
    
    # 3. Check API Key in .env
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logging.error("❌ OPENAI_API_KEY not found")
        self.enabled = False
        return
    
    # 4. Inizializza client OpenAI
    self.client = OpenAI(api_key=api_key)
    self.model = 'gpt-4o-mini'
    
    # 5. Inizializza database SQLite
    self._init_database()  # Crea trade_analysis.db
    
    logging.info("🤖 Trade Analyzer: ENABLED | Model: gpt-4o-mini")
```

**QUINDI:**
- ✅ Trade Analyzer si inizializza **automaticamente all'avvio**
- ✅ Se config dice `LLM_ANALYSIS_ENABLED = True` + API key OK → **ATTIVO**
- ✅ Crea database `trade_analysis.db` se non esiste
- ✅ Resta in background in attesa di trade da analizzare

---

### **FASE 3: TRADING CYCLE - Loop Principale**

```python
# In trading_engine.py
async def run_continuous_trading(exchange, xgb_models, xgb_scalers):
    while True:
        # CYCLE ogni 15 minuti
        await run_trading_cycle(exchange, xgb_models, xgb_scalers)
        await asyncio.sleep(900)  # 15 min
```

**Cosa succede in ogni ciclo:**

```
┌─────────────────────────────────────────────────────────────┐
│  CYCLE 1 (ogni 15 min)                                      │
└─────────────────────────────────────────────────────────────┘
                         │
    ┌────────────────────┴────────────────────┐
    │                                         │
    ▼                                         ▼
┌──────────────┐                    ┌──────────────┐
│ 1. Data      │                    │ 2. ML        │
│ Collection   │                    │ Predictions  │
└──────┬───────┘                    └──────┬───────┘
       │                                   │
       └───────────────┬───────────────────┘
                       │
                       ▼
              ┌──────────────┐
              │ 3. Signal    │
              │ Processing   │
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ 4. Execute   │
              │ Trades       │  ← QUI APRE POSIZIONI!
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ 5. Manage    │
              │ Positions    │  ← QUI CHIUDE POSIZIONI!
              └──────────────┘
```

---

### **FASE 4: APERTURA TRADE - Salvataggio Snapshot**

Quando viene eseguito un nuovo trade (Fase 4 del cycle):

```python
# In trading_orchestrator.py → execute_new_trade()

# 1. Calcola margin, position size, SL/TP
levels = risk_calculator.calculate_position_levels(...)

# 2. Apre posizione su Bybit
order = await exchange.create_market_order(...)

# 3. Crea posizione nel position manager
position_id = position_manager.create_position(
    symbol=symbol,
    side='buy',
    entry_price=current_price,
    position_size=position_size,
    leverage=leverage,
    confidence=signal['confidence'],
    ...
)

# 4. 📸 SNAPSHOT PREDIZIONE ML (per analisi futura!)
if LLM_ANALYSIS_ENABLED:
    position_manager.save_trade_snapshot(
        position_id=position_id,
        symbol=symbol,
        signal=signal['signal_name'],  # BUY/SELL
        confidence=signal['confidence'],  # 0.75
        ensemble_votes=signal['tf_predictions'],  # {15m: BUY, 30m: BUY, 1h: NEUTRAL}
        entry_price=current_price,
        entry_features={
            'rsi': dataframes['1h']['rsi_fast'].iloc[-1],
            'macd': dataframes['1h']['macd'].iloc[-1],
            'adx': dataframes['1h']['adx'].iloc[-1],
            'atr': dataframes['1h']['atr'].iloc[-1],
            'volume': dataframes['1h']['volume'].iloc[-1],
            'volatility': market_data.volatility
        }
    )
    
    logging.info("📸 Trade snapshot saved for AI analysis: AVAX")
```

**COSA VIENE SALVATO:**

```sql
INSERT INTO trade_snapshots (
    position_id,          -- "AVAX_20251106_223000_123456"
    symbol,               -- "AVAX/USDT:USDT"
    prediction_signal,    -- "BUY"
    ml_confidence,        -- 0.75
    ensemble_votes,       -- {"15m": "BUY", "30m": "BUY", "1h": "NEUTRAL"}
    entry_price,          -- 40.00
    entry_features,       -- {rsi: 45.2, macd: 0.15, adx: 28.5, ...}
    price_snapshots       -- [] (vuoto inizialmente)
) VALUES (...)
```

**Questo snapshot contiene TUTTO quello che il ML aveva predetto!**

---

### **FASE 5: VITA DEL TRADE - Price Tracking (Opzionale)**

Durante la vita del trade, ogni 15 minuti (opzionale se `TRACK_PRICE_SNAPSHOTS = True`):

```python
# In integrated_trailing_monitor.py o position management
global_trade_analyzer.add_price_snapshot(
    position_id="AVAX_20251106_223000_123456",
    price=40.50,  # Current price
    volume=6000000,
    timestamp="2025-11-06T22:45:00"
)
```

Questo crea un "movie" del trade:

```
Entry:   $40.00
+15min:  $40.50 (+1.25%)
+30min:  $39.80 (-0.5%)
+45min:  $39.00 (STOP LOSS HIT!)
```

---

### **FASE 6: CHIUSURA TRADE - TRIGGER AUTOMATICO ANALISI LLM! 🤖**

Quando un trade chiude (per qualsiasi motivo: TP, SL, manual, trailing):

```python
# In position_core.py → close_position()

def close_position(self, position_id, exit_price, close_reason):
    # 1. Calcola PnL finale
    if position.side == 'buy':
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100 * leverage
    # pnl_pct = -12.5% (LOSS)
    
    # 2. Aggiorna posizione
    position.status = "CLOSED_STOP_LOSS"
    position.unrealized_pnl_pct = pnl_pct
    position.close_time = datetime.now()
    
    # 3. Sposta in closed_positions
    self._closed_positions[position_id] = position
    
    # 4. Aggiorna balance
    self._session_balance += pnl_usd
    
    # 5. 🤖 TRIGGER AUTOMATICO ANALISI LLM!
    self._trigger_trade_analysis(position, exit_price, pnl_pct)
    
    # Bot continua immediatamente (analisi è async!)
    return True
```

**TRIGGER ANALYSIS:**

```python
def _trigger_trade_analysis(self, position, exit_price, pnl_pct):
    """Trigger LLM analysis (non-blocking!)"""
    
    # Calcola duration
    duration_minutes = (close_time - entry_time).total_seconds() / 60
    
    # Determine outcome
    outcome = "WIN" if pnl_pct > 0 else "LOSS"
    
    # Schedule async analysis (NON-BLOCKING!)
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(
            global_trade_analyzer.analyze_complete_trade(
                position_id=position.position_id,
                outcome=outcome,           # "LOSS"
                pnl_roe=pnl_pct,          # -12.5
                exit_price=exit_price,     # 39.00
                duration_minutes=duration_minutes  # 45
            )
        )
        logging.debug(f"🤖 Trade analysis scheduled for {symbol} ({outcome})")
    except:
        logging.debug("No event loop for trade analysis")
```

**IMPORTANTE**: L'analisi è **asincrona**! Il bot **continua immediatamente** senza aspettare GPT.

---

### **FASE 7: ANALISI LLM - Background Processing**

In background (parallelo al bot), l'analisi parte:

```python
# In trade_analyzer.py → analyze_complete_trade()

async def analyze_complete_trade(position_id, outcome, pnl_roe, exit_price, duration):
    # 1. Check se deve analizzare (durata minima, config, etc)
    if not should_analyze(outcome, pnl_roe, duration):
        return None
    
    # 2. Retrieve snapshot from DB
    snapshot = get_trade_snapshot(position_id)
    # snapshot = {
    #   'symbol': 'AVAX/USDT:USDT',
    #   'prediction_signal': 'BUY',
    #   'ml_confidence': 0.75,
    #   'ensemble_votes': {'15m': 'BUY', '30m': 'BUY', '1h': 'NEUTRAL'},
    #   'entry_price': 40.00,
    #   'entry_features': {rsi: 45.2, macd: 0.15, ...},
    #   'price_snapshots': [{t: +0, p: 40.00}, {t: +15, p: 40.50}, ...]
    # }
    
    # 3. Build comprehensive prompt
    prompt = f"""
    PREDICTION (What ML expected):
      Symbol: AVAX
      Signal: BUY @ 75% confidence
      Ensemble: 15m=BUY, 30m=BUY, 1h=NEUTRAL
      Entry: $40.00
      Features: RSI=45.2, MACD=0.15, ADX=28.5...
    
    REALITY (What actually happened):
      Outcome: LOSS
      PnL: -12.5% ROE
      Exit: $39.00
      Duration: 45 minutes
      Price Path: 
        Entry: $40.00
        +15min: $40.50 (+1.25%)
        +30min: $39.80 (-0.5%)
        +45min: $39.00 (SL hit)
    
    Analyze: Was prediction correct? What went wrong?
    Provide JSON with prediction_accuracy, category, explanation, 
    recommendations, ml_feedback...
    """
    
    # 4. Call OpenAI GPT-4o-mini
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[{"role": "system", "content": "..."}, {"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.3
    )
    
    # Takes ~2-3 seconds (bot doesn't wait!)
    
    # 5. Parse response
    analysis = json.loads(response.choices[0].message.content)
    # {
    #   "prediction_accuracy": "overconfident",
    #   "analysis_category": "false_breakout",
    #   "explanation": "Breakout @ $40 failed due to insufficient volume...",
    #   "what_went_right": ["ADX correctly identified strong trend", ...],
    #   "what_went_wrong": ["Volume spike insufficient", "1h timeframe disagreement ignored", ...],
    #   "recommendations": ["Reduce confidence when 1h disagrees", "Require volume spike > 2x", ...],
    #   "ml_model_feedback": {
    #     "features_to_emphasize": ["volume_surge", "btc_correlation"],
    #     "features_to_reduce": ["single_timeframe_rsi"],
    #     "confidence_adjustment": "decrease"
    #   }
    # }
    
    # 6. Log formatted analysis in terminal
    log_analysis(analysis)
    # Output:
    # ════════════════════════════════════════════════════════════
    # 🤖 TRADE ANALYSIS: AVAX ❌
    # ════════════════════════════════════════════════════════════
    # 📊 Outcome: LOSS | PnL: -12.5% ROE | Duration: 45min
    # 🎯 Prediction: BUY @ 75% confidence | Accuracy: overconfident
    # 📊 Category: false_breakout
    # 
    # 💡 Explanation:
    #   Breakout @ $40 failed due to insufficient volume...
    # 
    # ✅ What Went Right:
    #   • ADX correctly identified strong trend
    # 
    # ❌ What Went Wrong:
    #   • Volume spike insufficient (6M vs 10M needed)
    #   • Timeframe 1h disagreement ignored
    # 
    # 🎯 Recommendations:
    #   1. Reduce confidence when 1h disagrees
    #   2. Require volume spike > 2x on breakout
    # 
    # 🧠 ML Model Feedback:
    #   📈 Emphasize: volume_surge, btc_correlation
    #   📉 Reduce: single_timeframe_rsi
    # ════════════════════════════════════════════════════════════
    
    # 7. Save to database
    save_analysis(position_id, analysis)
    # INSERT INTO trade_analyses (position_id, symbol, outcome, 
    #   pnl_roe, prediction_accuracy, analysis_category, 
    #   explanation, recommendations, ml_feedback, ...) VALUES (...)
    
    return analysis
```

**COSTO**: ~$0.0006 per analisi (~800 tokens input + 500 output)

---

## 📊 RIEPILOGO FLUSSO TEMPORALE

```
T=0:00    python main.py
          ↓
T=0:01    🤖 Trade Analyzer inizializzato (ENABLED, gpt-4o-mini)
          💾 Database trade_analysis.db ready
          ↓
T=0:05    🚀 Trading cycle inizia
          ↓
T=0:10    📈 ML predice: AVAX BUY @ 75% confidence
          📸 Snapshot salvato in DB
          ↓
T=0:11    ✅ Posizione AVAX aperta @ $40.00
          ↓
T=0:26    📊 Price snapshot: $40.50 (+1.25%)  [opzionale]
          ↓
T=0:41    📊 Price snapshot: $39.80 (-0.5%)   [opzionale]
          ↓
T=0:56    ❌ STOP LOSS HIT @ $39.00 (-2.5% price, -12.5% ROE)
          🤖 Analysis triggered (async, non-blocking!)
          🔄 Bot continua immediatamente con altre operazioni
          ↓
T=0:58    [Background] GPT analizza trade...
          ↓
T=1:00    [Background] ✅ Analisi completata
          📊 Output nel terminal
          💾 Salvata in trade_analyses table
          ↓
T=1:01    Bot continua normalmente
          Next cycle in 14 minutes...
```

---

## 🎯 PUNTI CHIAVE

### **1. Inizializzazione Automatica**
✅ Trade Analyzer si inizializza **automaticamente** all'import  
✅ Nessun setup manuale richiesto  
✅ Controlla config + API key → se OK → ENABLED

### **2. Snapshot all'Apertura**
✅ **Ogni trade aperto** salva snapshot predizione  
✅ Include: signal, confidence, votes, features  
✅ Questo è il "cosa ML aveva previsto"

### **3. Trigger Automatico alla Chiusura**
✅ **Ogni trade chiuso** trigger analisi automatica  
✅ Non importa se WIN o LOSS → analizza entrambi!  
✅ Analisi è **asincrona** → bot non aspetta

### **4. Analisi Background**
✅ GPT analizza in background (~2-3 sec)  
✅ Bot continua trading senza interruzioni  
✅ Output nel terminal + database

### **5. Learning Continuo**
✅ Database accumula analisi nel tempo  
✅ Pattern recognition automatico  
✅ Insights aggregati disponibili

---

## 💻 COMANDI UTILI

### **Check se sistema è attivo:**
```python
python -c "
from core.trade_analyzer import global_trade_analyzer
import config

if global_trade_analyzer and global_trade_analyzer.enabled:
    print('✅ Trade Analyzer ENABLED')
    print(f'   Model: {global_trade_analyzer.model}')
    print(f'   Database: {global_trade_analyzer.db_path}')
else:
    print('❌ Trade Analyzer DISABLED')
"
```

### **View analisi recenti:**
```bash
python scripts/view_trade_analysis_report.py 7  # Last 7 days
```

### **Query database:**
```bash
sqlite3 trade_analysis.db
> SELECT symbol, outcome, pnl_roe, prediction_accuracy 
  FROM trade_analyses 
  ORDER BY timestamp DESC 
  LIMIT 10;
```

---

## ✅ TUTTO AUTOMATICO!

Una volta configurato (`LLM_ANALYSIS_ENABLED = True` + `OPENAI_API_KEY`):

1. ✅ Lancio `python main.py`
2. ✅ Trade Analyzer si inizializza automaticamente
3. ✅ Ogni trade aperto → Snapshot salvato
4. ✅ Ogni trade chiuso → Analisi triggerata
5. ✅ Analisi appare nel terminal + database
6. ✅ Pattern recognition automatico nel tempo

**NON DEVI FARE NULLA!** Il sistema impara da solo da ogni trade. 🧠📈
