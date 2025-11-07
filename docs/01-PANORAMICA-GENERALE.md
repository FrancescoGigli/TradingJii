# 📖 01 - Panoramica Generale

## 🎯 Cos'è questo Trading Bot?

Questo è un **bot di trading automatico per criptovalute** che opera su **Bybit Perpetual Futures** utilizzando intelligenza artificiale e machine learning per:

1. ✅ **Analizzare il mercato** in tempo reale (top 50 crypto per volume)
2. ✅ **Predire movimenti di prezzo** con XGBoost (ensemble multi-timeframe)
3. ✅ **Eseguire trade automatici** con leva 10x
4. ✅ **Gestire rischio dinamicamente** con adaptive position sizing
5. ✅ **Proteggere i profitti** con trailing stops intelligenti

---

## 🏗️ Architettura High-Level

```
┌─────────────────────────────────────────────────────────────┐
│                    TRADING BOT SYSTEM                        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Bybit API  │  │  Market Data │  │  ML Models   │     │
│  │  (Exchange)  │◄─┤  Analyzer    │◄─┤  (XGBoost)   │     │
│  └──────┬───────┘  └──────────────┘  └──────────────┘     │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         TRADING ENGINE (Orchestrator)                 │  │
│  │  • Data Collection    • ML Predictions                │  │
│  │  • Signal Processing  • Trade Execution               │  │
│  │  • Position Mgmt      • Risk Management               │  │
│  └───────────────────────┬──────────────────────────────┘  │
│                          │                                   │
│         ┌────────────────┼────────────────┐                │
│         ▼                ▼                ▼                 │
│  ┌───────────┐  ┌───────────────┐  ┌──────────┐          │
│  │ Position  │  │  Adaptive      │  │ Trailing │          │
│  │ Manager   │  │  Sizing        │  │ Stops    │          │
│  │(Thread-   │  │  (Learning)    │  │ (Dynamic)│          │
│  │ Safe)     │  └───────────────┘  └──────────┘          │
│  └───────────┘                                             │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────────────┐ │
│  │         PyQt6 Dashboard (Real-time GUI)              │ │
│  └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## 🔄 Ciclo di Funzionamento

### **Loop Principale (15 minuti)**

```
START
  │
  ├─► FASE 1: Data Collection (45s)
  │   • Fetch candele da Bybit (15m, 30m, 1h)
  │   • Calcola indicatori tecnici
  │   • Cache DB per efficienza
  │
  ├─► FASE 2: ML Predictions (3-4min)
  │   • Crea 66 temporal features
  │   • Predice con XGBoost (per timeframe)
  │   • Ensemble voting pesato
  │   • Calibra confidence
  │
  ├─► FASE 3: Signal Processing (10s)
  │   • Filtra con RL agent
  │   • Rank per confidence
  │   • Valida condizioni portfolio
  │
  ├─► FASE 4: Trade Execution (30s)
  │   • Calcola position sizing (adaptive)
  │   • Esegue market orders
  │   • Applica Stop Loss (-5%)
  │   • Registra posizioni
  │
  ├─► FASE 5: Position Management (ongoing)
  │   • Sync con Bybit
  │   • Update trailing stops (ogni 60s)
  │   • Monitor PnL
  │   • Safety checks
  │
  └─► WAIT 15 MIN → REPEAT
```

---

## 🤖 Tecnologie Utilizzate

### **Core Stack:**
- **Python 3.11+** - Linguaggio principale
- **asyncio + qasync** - Programmazione asincrona + Qt integration
- **PyQt6** - Dashboard grafica real-time
- **ccxt** - Libreria exchange (Bybit API)

### **Machine Learning:**
- **XGBoost** - Gradient boosting per predizioni
- **scikit-learn** - Preprocessing (StandardScaler)
- **pandas** - Data manipulation
- **ta (technical analysis)** - Indicatori tecnici

### **Data & Persistence:**
- **SQLite** - Cache dati di mercato
- **JSON** - Persistenza posizioni, memory adaptive
- **joblib** - Serializzazione modelli ML

### **Utility:**
- **termcolor** - Output colorato
- **python-dotenv** - Gestione credenziali

---

## 📊 Caratteristiche Principali

### **1. Multi-Timeframe Analysis**
- Analizza **3 timeframes** simultaneamente (15m, 30m, 1h)
- **Ensemble voting** pesato per decisione finale
- Coherence check tra timeframes

### **2. Adaptive Position Sizing** 🎯
- Sistema di **apprendimento automatico**
- Premia simboli vincenti (aumenta size)
- Blocca simboli perdenti (3 cicli penalty)
- Si adatta al crescita del wallet

### **3. Risk Management Avanzato**
- Stop Loss fisso **-5%** (= -50% ROE con 10x leva)
- Stop Loss **adattivo** basato su confidence
- **Trailing stops** dinamici (+15% ROE activation)
- **Early exit** per posizioni deboli

### **4. Thread-Safe Architecture**
- Gestione posizioni **thread-safe** con lock
- **4 task paralleli** (asyncio):
  - Trading loop (15 min)
  - Trailing monitor (60s)  
  - Dashboard update (30s)
  - Balance sync (60s)

### **5. Real-time Dashboard**
- GUI **PyQt6** responsive
- 4 tab: Active, Closed, Stats, Adaptive Memory
- Aggiornamento automatico ogni 30s

---

## 💰 Modalità Operative

### **DEMO MODE** 🧪
```python
DEMO_MODE = True
DEMO_BALANCE = 1000.0  # USDT virtuali
```
- **Paper trading** (no real money)
- Balance virtuale $1000
- Perfetto per **testing e learning**
- Nessuna connessione API richiesta

### **LIVE MODE** 💵
```python
DEMO_MODE = False
# Richiede API keys Bybit in .env
```
- **Trading reale** su Bybit
- Usa balance effettivo
- Rischio capitale reale
- ⚠️ **Usa con cautela!**

---

## 📈 Performance Tipiche

### **Timing Ciclo (15 min):**
```
Data Collection:     45-50s
ML Predictions:      3-4 min
Signal Processing:   10s
Trade Execution:     20-30s
Position Management: 10s
---------------------------------
TOTALE:             ~5-6 min
IDLE WAIT:          ~9-10 min
```

### **API Efficiency:**
```
Cache Hit Rate:     70-90%
API Calls Saved:    80% (con cache)
Concurrent Threads: 5 (download dati)
Max Positions:      5 simultanee
```

### **Resource Usage:**
```
CPU:      10-30% (durante predictions)
RAM:      ~500MB
Network:  Moderate (batch requests)
Disk:     ~100MB (cache + models)
```

---

## 🎓 Livello di Complessità

### **Beginner-Friendly:**
- ✅ Configurazione via menu interattivo
- ✅ DEMO mode per testing sicuro
- ✅ Dashboard visuale intuitiva
