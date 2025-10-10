# 🔍 GUIDA AL MONITORAGGIO BOT

Questa guida ti aiuta a capire se il bot sta funzionando correttamente guardando i log.

---

## ✅ **1. TIMESTAMP SYNC - COME VERIFICARE**

### **✅ FUNZIONA SE:**

**Nel log NON vedi errori `retCode: 10002`:**
```
✅ BUONO: Nessun messaggio di errore timestamp
✅ BUONO: API calls completate con successo
✅ BUONO: "🔄 Synchronizing positions with Bybit" → SUCCESSO
```

### **🔧 AUTO-RECOVERY SE:**

**Se vedi timestamp error + auto-fix:**
```log
⚠️ TIMESTAMP ERROR DETECTED (attempt 1/3)
⏰ FORCING TIME SYNC (attempt #1)...
✅ TIME SYNC SUCCESS: Offset +1180ms | Success rate: 100.0%
🔄 RETRYING operation after time sync...
✅ Operation successful!
```

**Questo è NORMALE e indica che il sistema si auto-recupera! ✅**

### **❌ PROBLEMA SE:**

**Vedi errori 10002 SENZA auto-recovery:**
```log
❌ bybit {"retCode":10002,"retMsg":"invalid request, please check your server timestamp...
❌ Thread-safe Bybit sync failed
(NESSUN "⏰ FORCING TIME SYNC" dopo)
```

**Azione:** Il TimeSyncManager non è integrato. Verifica che sia importato nel trading engine.

---

## 🎪 **2. TRAILING STOP - COME VERIFICARE**

### **✅ FUNZIONA SE:**

**Vedi questi log quando una posizione va in profit ≥ +1%:**

```log
🎪 TRAILING ACTIVATED: SYMBOL @ 1.2% profit (price $123.45)
```

**Poi ogni 60 secondi quando prezzo continua a salire:**
```log
🎪 Trailing updated: SYMBOL SL $120.00 → $125.00 (sl_too_far) | Distance: -8.0% | Profit protected: +5.1%
```

**Log silente se nessun aggiornamento necessario:**
```log
[Trailing] 0 activated, 0 updated (5 total)
```

### **⏸️ NON ATTIVO ANCORA SE:**

**Posizioni non hanno ancora +1% profit:**
```log
Nessun log "🎪 TRAILING" → Normale, aspetta profit!
```

**Nel display posizioni:**
```
SYMBOL | +0.8% profit  ← Manca ancora 0.2% per attivare trailing
```

### **❌ PROBLEMA SE:**

**Posizioni con +5% profit ma nessun log trailing:**
```log
SYMBOL | +5.2% profit
(Nessun "🎪 TRAILING" nei log)
```

**Azione:** Verifica che `TRAILING_ENABLED = True` in config.py

---

## 🛡️ **3. STOP LOSS - COME VERIFICARE**

### **✅ CORRETTI SE:**

**Alla creazione posizione vedi:**
```log
🛡️ APPLYING PROTECTION: SYMBOL
✅ TRADING STOP SUCCESS: SYMBOL | Bybit confirmed
```

**Nel display Bybit:**
```
SL % (±$): -0.48% (-$0.50)  ← OK! Vicino a -0.5% = -5% target
```

**Range accettabile:**
- **-0.40%** a **-0.55%** (equivale a -4% a -5.5% prezzo con leva 10x)

### **⚠️ TROPPO STRETTO SE:**

**Nel display vedi:**
```
SL % (±$): -0.04% (-$0.38)  ← ❌ 10x troppo stretto!
```

**Questo indica che lo SL è a -0.4% invece di -5%!**

**Azione:** Verifica che PrecisionHandler sia stato applicato.

### **❌ PROBLEMA SE:**

**Alla creazione posizione:**
```log
⚠️ Stop loss setting failed - Bybit error 34040
❌ CRITICAL: Stop loss setting failed
```

**Azione:** Problema con validazione prezzi. Controlla PrecisionHandler.

---

## 💰 **4. PORTFOLIO SIZING - COME VERIFICARE**

### **✅ CORRETTI SE:**

**Alla apertura posizioni vedi:**
```log
💰 CONFIDENCE-PROPORTIONAL SIZING:
   Total Wallet: $563.31
   Base Size: $112.66 per position
   5 positions: range $88-118 (15.6%-20.9%)
```

**Posizioni proporzionali a confidence:**
```
Pos 1 (100% conf) → $118 margin ✅
Pos 2 (100% conf) → $118 margin ✅
Pos 3 (90% conf)  → $106 margin ✅
Pos 4 (80% conf)  → $94 margin ✅
Pos 5 (70% conf)  → $88 margin ✅
```

### **❌ PROBLEMA SE:**

**Tutti margin uguali:**
```
Pos 1 → $100 margin
Pos 2 → $100 margin  ← Tutti uguali, NON confidence-proportional!
Pos 3 → $100 margin
```

---

## 📊 **5. CYCLE COMPLETO - CHECKLIST**

### **✅ Cycle Sano:**

```log
[Fase 1] ✅ Data fetching completato (260s)
[Fase 2] ✅ ML predictions completate (150s)
[Fase 3] ✅ TOP SIGNALS identificati
[Fase 4] ✅ Portfolio sizing calcolato
[Fase 5] ✅ Trade execution: 1-5 posizioni aperte
[Fase 6] ✅ Position sync con Bybit
[Fase 7] ✅ Trailing stop check (se posizioni in profit)
[Fase 8] ✅ Display posizioni aggiornato

Total cycle: ~470s
Next cycle in: 15m00s ✅
```

### **⚠️ Cycle con Problemi:**

```log
[Fase 5] ❌ Market order failed: retCode 10002
[Fase 6] ❌ Thread-safe Bybit sync failed
[Fase 7] (Skipped - sync failed)

Total cycle: ~470s
Next cycle in: 15m00s
```

**Se vedi molti ❌ = timestamp desync non risolto!**

---

## 🎯 **SUMMARY - COSA GUARDARE**

### **Durante ogni ciclo (15 minuti):**

1. **Fase Execution:**
   - ✅ Ordini piazzati con successo
   - ✅ Stop loss impostati
   - ❌ Nessun retCode 10002

2. **Fase Sync:**
   - ✅ Posizioni sincronizzate
   - ✅ Balance aggiornato
   - ❌ Nessun sync failed

3. **Trailing (ogni 60s):**
   - ✅ Log "🎪 TRAILING" se posizioni in profit
   - ⏸️ Log silente se nessuna posizione >+1%

4. **Display Finale:**
   - ✅ SL tra -0.40% e -0.55%
   - ✅ Margin proporzionali
   - ✅ P&L coerente

---

## 🚨 **TROUBLESHOOTING RAPIDO**

| SINTOMO | CAUSA | SOLUZIONE |
|---------|-------|-----------|
| retCode 10002 costante | Timestamp desync | Riavvia bot |
| retCode 10002 + auto-recovery | Sistema funziona! | Nessuna azione |
| Nessun trailing su +5% profit | TRAILING_ENABLED = False | Verifica config |
| SL a -0.04% invece di -0.5% | SL calculation bug | Check risk_calculator |
| Margin tutti uguali | Confidence-proportional OFF | Check risk_calculator |
| Posizione non apre | "ab not enough" | Lascia 2% buffer |

---

## 📝 **LOG DA SALVARE PER DEBUG**

**Se chiedi supporto, manda:**

1. **Ultime 100 righe del log** (da quando parte "PHASE 1" fino a "Next cycle")
2. **Screenshot display posizioni** (con SL % visibili)
3. **Config rilevanti:**
   - `TRAILING_ENABLED`
   - `SL_FIXED_PCT`
   - `FRESH_START_MODE`

---

## ✅ **SISTEMA SANO - ESEMPIO COMPLETO**

```log
2025-10-09 23:00:00 INFO 📈 PHASE 5: TRADE EXECUTION
2025-10-09 23:00:05 INFO 📈 PLACING MARKET BUY ORDER: ZEC/USDT:USDT | Size: 5.0000
2025-10-09 23:00:06 INFO ✅ MARKET ORDER SUCCESS: ID 123456 | Price: $213.15
2025-10-09 23:00:07 INFO 🛡️ APPLYING PROTECTION: ZEC/USDT:USDT
2025-10-09 23:00:08 INFO ✅ TRADING STOP SUCCESS: ZECUSDT | Bybit confirmed

2025-10-09 23:01:00 INFO 🔄 Synchronizing positions with Bybit
2025-10-09 23:01:01 INFO 🔒 Sync: NEW position ZEC/USDT:USDT 🟢 LONG

2025-10-09 23:02:00 INFO [Trailing] 0 activated, 0 updated (1 total)  ← Normale, aspetta +1%

(10 minuti dopo, prezzo sale)

2025-10-09 23:12:00 INFO 🎪 TRAILING ACTIVATED: ZEC @ 1.2% profit (price $215.70)  ← ✅!
2025-10-09 23:13:00 INFO 🎪 Trailing updated: ZEC SL $202.00 → $208.50 (sl_too_far)  ← ✅!

2025-10-09 23:15:00 INFO ✅ TRADING CYCLE COMPLETED SUCCESSFULLY
2025-10-09 23:15:00 INFO ⏸️ WAITING 15m until next cycle...
```

**Questo è un cycle PERFETTO! 🎉**
