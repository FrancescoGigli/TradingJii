# 📖 10 - Guida Configurazione Completa

> **Tutti i parametri di config.py spiegati**

---

## ⚙️ Overview

Il file `config.py` contiene TUTTI i parametri configurabili del sistema. Questa guida spiega ogni parametro e quando modificarlo.

---

## 🔐 1. CREDENZIALI & MODALITÀ

### **Demo vs Live Mode**

```python
DEMO_MODE = False  # False = LIVE trading (soldi reali)
DEMO_BALANCE = 1000.0  # Balance virtuale per demo mode
```

**Quando modificare**:
- `DEMO_MODE = True` per testing senza rischio
- `DEMO_MODE = False` per trading reale

### **API Keys Bybit**

```python
# In file .env:
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
OPENAI_API_KEY=your_openai_key_here  # Per trade analyzer
```

**Setup**:
1. Crea account Bybit
2. Genera API keys (Trade + Futures permissions)
3. Whitelist IP se necessario
4. Copia keys in `.env`

---

## 💰 2. TRADING PARAMETERS

### **Leverage**

```python
LEVERAGE = 5  # 5x leverage (ridotto da 10x per risk management)
```

**Impatto**:
- 5x: -5% prezzo = -25% ROE
- 10x: -5% prezzo = -50% ROE

**Raccomandazioni**:
- Principianti: 3-5x
- Esperti: 5-10x
- ⚠️ Mai oltre 10x

### **Stop Loss**

```python
STOP_LOSS_PCT = 0.05  # -5% prezzo fisso
SL_USE_FIXED = True   # Fixed (no ATR-based)
```

**Impatto con 5x leverage**:
- -5% prezzo = -25% ROE (margin loss)
- Rischio per trade: 25% del margin

### **Timeframes**

```python
ENABLED_TIMEFRAMES = ["15m", "30m", "1h"]
TIMEFRAME_DEFAULT = "15m"
```

**Opzioni disponibili**: 1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d

**Raccomandazioni**:
- Day trading: 15m, 30m, 1h
- Swing: 1h, 4h, 1d
- Scalping: 1m, 3m, 5m

---

## 🎯 3. ADAPTIVE POSITION SIZING

### **Sistema Adaptive**

```python
ADAPTIVE_SIZING_ENABLED = True  # True = Adaptive, False = Fixed
```

**Fixed vs Adaptive**:
- Fixed: Size basato su confidence (semplice)
- Adaptive: Impara da performance + Kelly Criterion (avanzato)

### **Wallet Blocks**

```python
ADAPTIVE_WALLET_BLOCKS = 5  # Divide wallet in 5 parts
ADAPTIVE_FIRST_CYCLE_FACTOR = 0.5  # 50% del block inizialmente
```

**Esempio wallet $500**:
- Blocks: 5
- Block value: $100
- Base size: $50 (50% del block)
- Max positions: 5

### **Penalty System**

```python
ADAPTIVE_BLOCK_CYCLES = 3  # Blocca losers per 3 cicli
ADAPTIVE_CAP_MULTIPLIER = 1.0  # Max size = 1x block value
```

### **Kelly Criterion**

```python
ADAPTIVE_USE_KELLY = True  # Enable Kelly sizing
ADAPTIVE_KELLY_FRACTION = 0.25  # Use 25% of Kelly (conservativo)
ADAPTIVE_MAX_POSITION_PCT = 0.25  # Max 25% wallet per position
ADAPTIVE_MIN_POSITION_PCT = 0.05  # Min 5% wallet per position
```

**Quando abilita**: Dopo 10+ trades per simbolo

### **Fresh Start Mode**

```python
ADAPTIVE_FRESH_START = False  # False = Historical mode
```

**Quando usare True**:
- Dopo cambio strategy
- Reset completo stats
- Testing nuovi parametri

---

## 🛡️ 4. RISK MANAGEMENT

### **Portfolio Risk**

```python
MAX_CONCURRENT_POSITIONS = 5  # Max 5 posizioni simultanee
ADAPTIVE_RISK_MAX_PCT = 0.20  # Max 20% wallet at risk
ADAPTIVE_LOSS_MULTIPLIER = 0.30  # SL = 30% margin loss
```

**Calcolo risk**:
- Total margin: $200
- Max loss @ SL: $200 × 0.30 = $60
- Risk limit: $500 × 0.20 = $100
- ✓ OK ($60 < $100)

### **Early Exit System**

```python
EARLY_EXIT_ENABLED = True

# Immediate reversal (5 min)
EARLY_EXIT_IMMEDIATE_ENABLED = True
EARLY_EXIT_IMMEDIATE_TIME_MINUTES = 5
EARLY_EXIT_IMMEDIATE_DROP_ROE = -10  # -10% ROE

# Fast reversal (15 min)
EARLY_EXIT_FAST_REVERSAL_ENABLED = True
EARLY_EXIT_FAST_TIME_MINUTES = 15
EARLY_EXIT_FAST_DROP_ROE = -15  # -15% ROE

# Persistent weakness (60 min)
EARLY_EXIT_PERSISTENT_ENABLED = True
EARLY_EXIT_PERSISTENT_TIME_MINUTES = 60
EARLY_EXIT_PERSISTENT_DROP_ROE = -5  # -5% ROE
```

**Impatto**: Riduce losses medie del ~55%

### **Partial Exits**

```python
PARTIAL_EXIT_ENABLED = True
PARTIAL_EXIT_MIN_SIZE = 10.0  # Min $10 USDT

PARTIAL_EXIT_LEVELS = [
    {'roe': 50, 'pct': 0.30},   # 30% @ +50% ROE
    {'roe': 100, 'pct': 0.30},  # 30% @ +100% ROE
    {'roe': 150, 'pct': 0.20},  # 20% @ +150% ROE
]
# Remaining 20% = runner
```

**Benefit**: Profit capture rate +27% vs all-or-nothing

---

## 🤖 5. ML SYSTEM

### **Features & Training**

```python
N_FEATURES_FINAL = 66  # Total temporal features
LOOKBACK_HOURS = 6  # Uniform lookback window

# Training
TRAIN_IF_NOT_FOUND = True  # Auto-train se models missing
DATA_LIMIT_DAYS = 180  # 180 giorni historical data
```

### **Ensemble Weights**

```python
TIMEFRAME_WEIGHTS = {
    "15m": 1.0,
    "30m": 1.2,
    "1h": 1.5,
    "4h": 2.0
}
```

**Logica**: Timeframes più lunghi = maggior peso

### **Confidence Thresholds**

```python
MIN_CONFIDENCE_BASE = 0.65  # 65% minimum
MIN_CONFIDENCE_VOLATILE = 0.75  # 75% in volatile markets
MIN_CONFIDENCE_BEAR = 0.80  # 80% in bear markets
```

**Quando aumentare**:
- Win rate <50% → aumenta a 0.70-0.75
- Troppe false signals → aumenta thresholds

---

## 🤖 6. TRADE ANALYZER (AI)

### **OpenAI Configuration**

```python
LLM_ANALYSIS_ENABLED = True  # Master switch
LLM_MODEL = 'gpt-4o-mini'  # Cost-effective model
```

**Costo**: ~$0.0006 per trade

### **Analysis Triggers**

```python
LLM_ANALYZE_ALL_TRADES = False  # False = selective
LLM_ANALYZE_WINS = True  # Analyze wins
LLM_ANALYZE_LOSSES = True  # Analyze losses
LLM_MIN_TRADE_DURATION = 5  # Min 5 minutes
```

**Quando disabilitare**:
- Budget limitato OpenAI
- Primi test del sistema
- Non serve AI analysis

### **Price Tracking**

```python
TRACK_PRICE_SNAPSHOTS = True
PRICE_SNAPSHOT_INTERVAL = 900  # 15 minuti
```

---

## 📊 7. MARKET SELECTION

### **Symbol Selection**

```python
TOP_SYMBOLS_COUNT = 50  # Analizza top 50 per volume
TOP_TRAIN_CRYPTO = 50  # Train su top 50
TOP_ANALYSIS_CRYPTO = 50  # Analyze top 50

MIN_VOLUME_THRESHOLD = 1_000_000  # Min 1M USDT/24h
MIN_PRICE_THRESHOLD = 0.001  # Min $0.001
```

### **Symbol Exclusion**

```python
EXCLUDED_SYMBOLS = []  # Escludi permanentemente

# Excluded from trading (but used for training)
EXCLUDED_FROM_TRADING = ["BTC/USDT:USDT", "ETH/USDT:USDT"]

# Problematic symbols (gold-backed tokens)
SYMBOL_BLACKLIST = [
    'XAUT/USDT:USDT',
    'PAXG/USDT:USDT',
]
```

---

## 🔧 8. SYSTEM OPTIMIZATION

### **Cache Configuration**

```python
ENABLE_DATA_CACHE = True
CACHE_MAX_AGE_MINUTES = 3  # 3 min TTL
CACHE_EXPECTED_HIT_RATE = 70  # Target 70%

# API cache TTLs
API_CACHE_POSITIONS_TTL = 30  # 30s
API_CACHE_TICKERS_TTL = 15  # 15s
API_CACHE_BATCH_TTL = 20  # 20s
```

**Impatto**: Riduce API calls dell'80%

### **Time Synchronization**

```python
TIME_SYNC_MAX_RETRIES = 5
TIME_SYNC_RETRY_DELAY = 3  # seconds
TIME_SYNC_NORMAL_RECV_WINDOW = 300000  # 5 minutes
MANUAL_TIME_OFFSET = 0  # Manual offset se problemi
```

**Se fallisce sync**:
1. Sincronizza Windows time
2. Disabilita firewall temporaneamente
3. Imposta `MANUAL_TIME_OFFSET` (es. -2500 per -2.5s)

### **Logging**

```python
LOG_VERBOSITY = "NORMAL"  # MINIMAL, NORMAL, DETAILED
QUIET_MODE = True  # Legacy (deprecato)
```

**Levels**:
- MINIMAL: Solo trades e P&L
- NORMAL: Standard operations
- DETAILED: Full debug

---

## 📈 9. PERFORMANCE TUNING

### **Symbols per Risorse**

| Balance | Symbols | Positions | CPU Usage |
|---------|---------|-----------|-----------|
| $100    | 20      | 2-3       | Low       |
| $500    | 50      | 5         | Medium    |
| $1000   | 75      | 5-7       | High      |
| $5000   | 100     | 10        | Very High |

### **Timeframes per Strategy**

| Strategy    | Timeframes  | Cycle    |
|-------------|-------------|----------|
| Scalping    | 1m, 3m, 5m  | 5 min    |
| Day Trading | 15m, 30m, 1h| 15 min   |
| Swing       | 1h, 4h, 1d  | 1 hour   |

---

## 🎯 10. CONFIGURAZIONI COMUNI

### **Conservative (Principianti)**

```python
LEVERAGE = 3
STOP_LOSS_PCT = 0.04  # -4% = -12% ROE
MAX_CONCURRENT_POSITIONS = 3
MIN_CONFIDENCE_BASE = 0.75  # Higher threshold
ADAPTIVE_SIZING_ENABLED = False  # Fixed sizing
PARTIAL_EXIT_ENABLED = True
EARLY_EXIT_ENABLED = True
```

### **Balanced (Default)**

```python
LEVERAGE = 5
STOP_LOSS_PCT = 0.05  # -5% = -25% ROE
MAX_CONCURRENT_POSITIONS = 5
MIN_CONFIDENCE_BASE = 0.65
ADAPTIVE_SIZING_ENABLED = True
ADAPTIVE_USE_KELLY = True
PARTIAL_EXIT_ENABLED = True
EARLY_EXIT_ENABLED = True
```

### **Aggressive (Esperti)**

```python
LEVERAGE = 10
STOP_LOSS_PCT = 0.05  # -5% = -50% ROE!
MAX_CONCURRENT_POSITIONS = 7
MIN_CONFIDENCE_BASE = 0.60  # Lower threshold
ADAPTIVE_SIZING_ENABLED = True
ADAPTIVE_USE_KELLY = True
ADAPTIVE_KELLY_FRACTION = 0.35  # More aggressive Kelly
```

⚠️ **Warning**: Aggressive = Higher risk!

---

## 🔍 11. TROUBLESHOOTING

### **Time Sync Failures**

```python
# Problema: "Time synchronization failed"
# Fix:
MANUAL_TIME_OFFSET = -2500  # Try -2.5 seconds
TIME_SYNC_NORMAL_RECV_WINDOW = 120000  # Increase to 120s
```

### **Troppi False Signals**

```python
# Aumenta confidence thresholds
MIN_CONFIDENCE_BASE = 0.75  # Da 0.65 a 0.75
MIN_CONFIDENCE_VOLATILE = 0.85  # Da 0.75 a 0.85
```

### **Win Rate Basso**

```python
# Riduci positions e aumenta quality
MAX_CONCURRENT_POSITIONS = 3  # Da 5 a 3
MIN_CONFIDENCE_BASE = 0.70  # Da 0.65 a 0.70
TOP_ANALYSIS_CRYPTO = 30  # Da 50 a 30 (migliori)
```

### **Too Slow Execution**

```python
# Riduci symbols analyzed
TOP_ANALYSIS_CRYPTO = 30  # Da 50 a 30
ENABLE_DATA_CACHE = True  # Assicurati sia True
```

---

## 📚 Quick Reference

### **File Structure**

```
config.py          # Main configuration
.env               # API keys (NON committare su git!)
positions.json     # Position persistence
adaptive_sizing_memory.json  # Adaptive memory
trade_analysis.db  # AI analysis storage
```

### **Restart Dopo Modifiche**

**Richiede restart**:
- LEVERAGE
- TIMEFRAMES
- MAX_CONCURRENT_POSITIONS
- ADAPTIVE settings

**Non richiede restart**:
- Confidence thresholds
- Early exit thresholds
- Partial exit levels

---

## 🎯 Checklist Pre-Live Trading

- [ ] `DEMO_MODE = False`
- [ ] API keys in `.env` valide
- [ ] IP whitelisted su Bybit
- [ ] Time sync funzionante
- [ ] Models trained (o `TRAIN_IF_NOT_FOUND = True`)
- [ ] Balance sufficiente (min $100)
- [ ] Leverage impostato correttamente
- [ ] Stop loss verificato
- [ ] Max positions ragionevole
- [ ] Testato in DEMO prima

---

**🎯 SAFETY FIRST**: Inizia sempre in DEMO MODE, poi passa a LIVE con balance piccola per testare, poi scala gradualmente.

---

## 📚 Documentation Complete!

Hai completato la lettura di TUTTA la documentazione! 

**Prossimi step**:
1. Testa in DEMO mode
2. Monitora performance 1-2 settimane
3. Analizza trade
