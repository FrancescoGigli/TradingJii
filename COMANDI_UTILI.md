# 📖 GUIDA COMPLETA AI COMANDI DEL TRADING BOT

## 🚀 COMANDI PRINCIPALI

### 1. **Avviare il Bot**
```bash
python main.py
```

**Cosa fa:**
- Avvia il trading bot in modalità LIVE
- Connette a Bybit con le tue API keys
- Inizia il ciclo di trading automatico ogni 15 minuti
- Apre la dashboard PyQt6 per visualizzazione realtime

**What to expect:**
- Sistema completa startup in ~10 secondi
- Download dati: ~4-5 minuti (50 symbols × 3 timeframes)
- ML predictions: ~2-3 minuti
- Primo ciclo completo: ~8-10 minuti
- Dashboard si aggiorna ogni 30 secondi

**Output tipico:**
```
🚀 SYSTEM FULLY OPERATIONAL — LIVE TRADING STARTED
📊 Analyzing symbols: 50 total
📈 PHASE 1: DATA COLLECTION & MARKET ANALYSIS
✅ Market filter DISABLED - proceeding with cycle
📈 PHASE 2: ML PREDICTIONS & AI ANALYSIS
...
```

---

### 2. **Test Suite - Validazione Sistema**
```bash
python scripts/test_new_version.py
```

**Cosa fa:**
- Esegue 12 test automatici su tutti i sistemi critici
- Verifica TP direction (LONG/SHORT)
- Controlla R/R ratio minimo (2.5:1)
- Testa NoneType handling
- Valida position size minima
- Conferma market filter disabilitato

**Quando usarlo:**
- ✅ Dopo ogni modifica al codice
- ✅ Prima di fare trading live
- ✅ Dopo aggiornamento dipendenze
- ✅ Per debug problemi

**Output tipico:**
```
🧪 TRADING BOT - NEW VERSION TEST SUITE
✅ PASS: LONG TP > Entry
✅ PASS: SHORT TP < Entry
...
🎉 ALL TEST SUITES PASSED!
✅ Bot ready for production with new version
```

---

### 3. **View Current Status - Snapshot Posizioni**
```bash
python scripts/view_current_status.py
```

**Cosa fa:**
- Mostra **snapshot** delle posizioni LIVE da Bybit
- Visualizza PnL realtime per ogni posizione
- Calcola statistiche portfolio (ROE, win rate, ecc)
- Mostra balance disponibile e allocato

**Informazioni mostrate:**
- 📊 Posizioni APERTE con entry price, current price, PnL %
- 💰 Balance: totale, allocato, disponibile
- 📈 Stop Loss e Take Profit per ogni posizione
- 🎯 ROE (Return on Equity) calcolato con leva
- ⏱️ Tempo di apertura posizione

**Esempio output:**
```
====================================================================================================
📊 LIVE POSITIONS (Bybit) — snapshot
┌─────┬────────┬──────┬──────┬─────────────┬─────────────┬──────────┬───────────┬──────────────┬───────────┐
│  #  │ SYMBOL │ SIDE │ LEV  │    ENTRY    │   CURRENT   │  PNL %   │   PNL $   │   SL % (±$)  │   IM $    │
├─────┼────────┼──────┼──────┼─────────────┼─────────────┼──────────┼───────────┼──────────────┼───────────┤
│  1  │  KITE  │SHORT │  10  │  $0.075970  │  $0.075800  │  +2.2%   │     +$0.71│-0.2% (-$0.08)│    $32    │
│  2  │   4    │ LONG │  10  │  $0.071057  │  $0.071500  │  +6.2%   │     +$2.00│-0.3% (-$0.08)│    $32    │
│  3  │  ERA   │SHORT │  10  │  $0.260453  │  $0.259000  │  +5.6%   │     +$1.79│-0.2% (-$0.08)│    $32    │
└─────┴────────┴──────┴──────┴─────────────┴─────────────┴──────────┴───────────┴──────────────┴───────────┘
💰 LIVE: 3 pos | P&L: +$4.50 | Wallet Allocated: $96 | Available: $226 | Next Cycle: 12m30s
🏦 Total Wallet: $322 | Allocation: 29.8%
```

**Quando usarlo:**
- ✅ Per check veloce situazione portfolio
- ✅ Prima di chiudere manualmente posizioni
- ✅ Per vedere se SL/TP sono impostati correttamente
- ✅ Durante il ciclo per monitorare PnL

---

### 4. **View Trade Decisions - Database Decisioni ML**
```bash
python scripts/view_trade_decisions.py
```

**Cosa fa:**
- Accede al database SQLite `trade_decisions.db`
- Mostra **tutte le decisioni ML** prese dal bot
- Per ogni trade: ML predictions, market context, portfolio state
- Utile per **analisi post-mortem** e debugging

**Informazioni mostrate:**
- 🧠 **ML Signals**: Buy/Sell per ogni timeframe (15m, 30m, 1h)
- 📊 **Market Context**: RSI, ADX, volatility al momento decisione
- 💰 **Position Details**: Entry price, size, margin, stop loss
- 📈 **Portfolio State**: Balance disponibile, posizioni attive
- 🎯 **Consensus**: Quanti timeframe d'accordo (es: 3/3 = forte segnale)

**Esempio output:**
```
================================================================================
📊 TRADE DECISION ANALYSIS
================================================================================

Decision ID: 1234567890
Symbol: KITE/USDT:USDT
Timestamp: 2025-11-06 09:49:54
Action: SELL

ML PREDICTIONS:
  15m: SELL (100.0% confidence)
  30m: SELL (100.0% confidence)
  1h:  SELL (100.0% confidence)
  → Consensus: 3/3 timeframes agree (STRONG)

MARKET CONTEXT:
  RSI: 62.5 (neutral-overbought)
  ADX: 28.3 (trending)
  Volatility: 0.023 (2.3%)

POSITION DETAILS:
  Entry: $0.075970
  Size: 4276 coins
  Margin: $32.25
  Stop Loss: $0.077860 (+2.5%)

PORTFOLIO STATE:
  Available Balance: $161.24
  Active Positions: 4/5 slots
```

**Quando usarlo:**
- ✅ Per capire **perché** il bot ha aperto una posizione
- ✅ Per analizzare trade vincenti/perdenti
- ✅ Per ottimizzare parametri ML
- ✅ Per debug segnali "strani"

---

### 5. **View Complete Session - Statistiche Sessione**
```bash
python scripts/view_complete_session.py
```

**Cosa fa:**
- Carica file JSON `positions.json` (database posizioni locale)
- Mostra **tutta la sessione corrente** dall'avvio bot
- Calcola win rate, average hold time, best/worst trades
- Statistiche dettagliate per ogni symbol tradato

**Informazioni mostrate:**
- 📊 **Posizioni Aperte**: Tutte le posizioni ancora attive
- 🔒 **Posizioni Chiuse**: Storia completa trade chiusi
- 📈 **Win Rate**: % trade vincenti vs perdenti
- ⏱️ **Hold Time**: Tempo medio di permanenza in posizione
- 🎯 **Best/Worst**: Trade più profittevole e più perdente
- 💰 **Total PnL**: Profitto/perdita totale sessione

**Esempio output:**
```
================================================================================
📊 COMPLETE SESSION ANALYSIS
================================================================================

SESSION SUMMARY:
  Start Time: 2025-11-06 09:22:48
  Duration: 1h 45m
  Total Trades: 8
  Currently Open: 3
  Closed: 5

PERFORMANCE:
  Win Rate: 60% (3W - 2L)
  Total PnL: +$12.50 (+3.9% ROE)
  Average Hold: 23 minutes
  Best Trade: ERA (+8.5%, $2.72)
  Worst Trade: ZK (-5.9%, -$1.89)

CLOSED POSITIONS:
┌──────────┬──────┬─────────────┬─────────────┬──────────┬───────────┬──────────────┐
│  SYMBOL  │ SIDE │    ENTRY    │    EXIT     │  PNL %   │   PNL $   │  HOLD TIME   │
├──────────┼──────┼─────────────┼─────────────┼──────────┼───────────┼──────────────┤
│   ERA    │SHORT │  $0.260453  │  $0.238000  │  +8.5%   │   +$2.72  │   18m 30s    │
│   ZK     │SHORT │  $0.069840  │  $0.070010  │  -5.9%   │   -$1.89  │    1m 07s    │
│   XAUT   │SHORT │ $4000.845   │ $4001.000   │  -0.1%   │   -$0.02  │   24s        │
└──────────┴──────┴─────────────┴─────────────┴──────────┴───────────┴──────────────┘
```

**Quando usarlo:**
- ✅ Fine giornata per review performance
- ✅ Per analizzare pattern vincenti/perdenti
- ✅ Per ottimizzare strategia
- ✅ Report settimanale/mensile

---

### 6. **Runner Script - Avvio Veloce con Log**
```bash
python scripts/runner.py
```

**Cosa fa:**
- Wrapper avanzato per `main.py`
- Aggiunge **logging su file** automatico
- Cattura errori e salva crash logs
- Useful per **production deployment**

**Features:**
- 📝 Log salvati in `logs/bot_YYYYMMDD_HHMMSS.log`
- 🔄 Auto-restart on crash (opzionale)
- 📊 Statistiche uptime
- ⚠️ Alert email on critical errors (se configurato)

**Quando usarlo:**
- ✅ Deployment production (VPS, server)
- ✅ Se vuoi avere log persistenti
- ✅ Per debugging problemi intermittenti
- ✅ Trading unattended (24/7)

---

### 7. **Check Position Mode - Verifica Configurazione**
```bash
python scripts/check_position_mode.py
```

**Cosa fa:**
- Verifica **position mode** su Bybit (One-Way vs Hedge)
- Controlla se leverage è impostato correttamente
- Valida margin mode (Isolated vs Cross)
- Diagnostica problemi comuni configurazione

**Output tipico:**
```
🔍 CHECKING BYBIT POSITION CONFIGURATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Account Settings:
  Position Mode: One-Way Mode ✅
  Margin Mode: Isolated ✅
  
Symbol Checks:
  BTC/USDT:USDT
    ├─ Leverage: 10x ✅
    ├─ Margin: Isolated ✅
    └─ Status: Ready for trading
    
  ETH/USDT:USDT
    ├─ Leverage: 10x ✅
    ├─ Margin: Isolated ✅
    └─ Status: Ready for trading
    
✅ All systems configured correctly!
```

**Quando usarlo:**
- ✅ Prima del primo trading live
- ✅ Se compaiono errori di leverage/margin
- ✅ Dopo cambio configurazione Bybit
- ✅ Diagnostica problemi ordini

---

## 🎯 WORKFLOW CONSIGLIATO

### **Primo Avvio (Setup)**
```bash
# 1. Verifica configurazione
python scripts/check_position_mode.py

# 2. Esegui test suite
python scripts/test_new_version.py

# 3. Avvia bot
python main.py
```

### **Monitoring Durante Trading**
```bash
# Check rapido posizioni
python scripts/view_current_status.py

# Analisi decisioni ML
python scripts/view_trade_decisions.py

# Review sessione completa
python scripts/view_complete_session.py
```

### **Fine Giornata Review**
```bash
# Statistiche complete
python scripts/view_complete_session.py

# Check decisioni importanti
python scripts/view_trade_decisions.py
```

---

## 🚨 TROUBLESHOOTING

### **Bot non apre posizioni**
```bash
# 1. Check market filter
grep "MARKET_FILTER_ENABLED" config.py
# Dovrebbe essere: False

# 2. Check balance
python scripts/view_current_status.py
# Verifica available balance > $30

# 3. Check decisioni ML
python scripts/view_trade_decisions.py
# Vedi se ML genera segnali
```

### **Errori di prezzo/tick size**
```bash
# Check position mode
python scripts/check_position_mode.py
```

### **Dashboard non si apre**
```bash
# Il bot funziona SENZA dashboard (è opzionale)
# Dashboard richiede display grafico (non funziona su SSH)
# Usa view_current_status.py per monitoring
```

---

## 📊 FILE IMPORTANTI

### **Database Posizioni**
```
data_cache/positions.json
```
- Tutte le posizioni (aperte + chiuse)
- Usato da view_complete_session.py
- Backup automatico

### **Database Decisioni ML**
```
data_cache/trade_decisions.db
```
- SQLite database con tutte decisioni ML
- Usato da view_trade_decisions.py
- Cresce nel tempo (pulire periodicamente)

### **Logs**
```
logs/bot_YYYYMMDD_HHMMSS.log
```
- Log dettagliati se usi runner.py
- Per debug problemi

---

## 💡 TIPS & TRICKS

### **Monitoring Realtime**
```bash
# Loop infinito per monitoring continuo
while true; do 
  clear
  python scripts/view_current_status.py
  sleep 30
done
```

### **Export Statistiche**
```bash
# Salva output su file
python scripts/view_complete_session.py > report_$(date +%Y%m%d).txt
```

### **Check Veloce Balance**
```bash
python -c "import asyncio; from trade_manager import get_real_balance; import ccxt; e = ccxt.bybit({'apiKey': 'YOUR_KEY', 'secret': 'YOUR_SECRET'}); print(f'Balance: ${asyncio.run(get_real_balance(e)):.2f}')"
```

---

## 🎓 COMANDI AVANZATI

### **Pulizia Database Decisioni**
```bash
# Mantieni solo ultimi 30 giorni
sqlite3 data_cache/trade_decisions.db "DELETE FROM trade_decisions WHERE timestamp < datetime('now', '-30 days')"
```

### **Backup Posizioni**
```bash
cp data_cache/positions.json backups/positions_$(date +%Y%m%d_%H%M%S).json
```

### **Force Sync Posizioni**
```python
# In Python shell
import asyncio
from core.thread_safe_position_manager import global_thread_safe_position_manager
import ccxt

exchange = ccxt.bybit({...})
asyncio.run(global_thread_safe_position_manager.thread_safe_sync_with_bybit(exchange))
```

---

**🎯 Per qualsiasi dubbio, consulta questa guida!**
