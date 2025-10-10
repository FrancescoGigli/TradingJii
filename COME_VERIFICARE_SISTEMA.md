# 🔍 COME VERIFICARE CHE IL SISTEMA FUNZIONI

**Problema:** Non vedi stop loss applicato e trailing stop in azione

**Soluzione:** Segui questi step di verifica

---

## ✅ STEP 1: Verifica Configurazione

Controlla che in `config.py` ci sia:

```python
# STOP LOSS
SL_USE_FIXED = True              # ✅ DEVE essere True
SL_FIXED_PCT = 0.05              # ✅ 5% fisso

# TRAILING STOP
TRAILING_ENABLED = True          # ✅ DEVE essere True
TRAILING_TRIGGER_PCT = 0.01      # ✅ +1% attivazione
TRAILING_UPDATE_INTERVAL = 60    # Check ogni 60s
```

✅ **La tua configurazione è CORRETTA!**

---

## ✅ STEP 2: Verifica che il Bot Stia Girando

### **Check Logs:**

Quando il bot gira, dovresti vedere nei log:

```
🚀 TRADING CYCLE STARTED
📈 PHASE 1: DATA COLLECTION & MARKET ANALYSIS
📊 PHASE 2: ML PREDICTIONS & AI ANALYSIS
...
✅ TRADING CYCLE COMPLETED SUCCESSFULLY
```

**Se NON vedi questi log:**
- Il bot non è in esecuzione
- Avvia con: `python main.py` o `python runner.py`

---

## ✅ STEP 3: Verifica Apertura Posizioni

### **Log da Cercare quando Apri Posizione:**

```python
🎯 EXECUTING NEW TRADE: ETH/USDT BUY
💰 Using PORTFOLIO SIZING: $150.00 margin (precalculated)
📈 PLACING MARKET BUY ORDER: ETH/USDT | Size: 0.75

# POI VEDRAI:
🛡️ ETH/USDT: Stop Loss set at $1900.00
   📊 Rischio REALE: 5.00% prezzo × 10x leva = -50.0% MARGIN

✅ ETH/USDT: Position opened with fixed SL protection
```

**Se NON vedi questi log:**
- Non stai aprendo posizioni
- Controlla che ci siano segnali ML validi
- Verifica balance disponibile

---

## ✅ STEP 4: Verifica Stop Loss su Bybit

### **Metodo 1: Log Bot**

Cerca nel log:
```
🛡️ [SYMBOL]: Stop Loss set at $[PRICE]
```

### **Metodo 2: Interfaccia Bybit**

1. Vai su Bybit.com → Derivatives → Positions
2. Clicca sulla posizione aperta
3. Controlla sezione **"TP/SL"**
4. Dovresti vedere: **SL: $[PRICE]** (≈ -5% dal entry)

**Esempio:**
- Entry: $100
- SL dovrebbe essere: $95 (per LONG) o $105 (per SHORT)

---

## ✅ STEP 5: Verifica Trailing Stop Activation

### **Condizioni per Attivazione:**

Il trailing si attiva SOLO quando:
1. ✅ Posizione aperta
2. ✅ Profit ≥ +1% price (+10% margin con leva 10x)

### **Log da Cercare:**

```python
🎪 TRAILING ACTIVATED: ETH @ 1.05% profit (price $101.10)
```

**Se NON vedi questo log:**
- La posizione non ha ancora raggiunto +1% profit
- **QUESTO È NORMALE** - il trailing si attiva solo in profit!

---

## ✅ STEP 6: Verifica Update Trailing

Una volta attivato, cerca questi log **ogni 60 secondi**:

```python
🎪 Trailing updated: ETH SL $95.05 → $101.20 (sl_too_far) | Distance: -8.0% | Profit protected: +1.2%
```

**Se vedi:**
```
[Trailing] ETH: Skip - would lower SL
```

Questo è **CORRETTO** → Il sistema protegge il tuo profit non abbassando mai lo SL!

---

## 🔧 TROUBLESHOOTING

### **Problema 1: "Non vedo log di apertura posizioni"**

**Possibili Cause:**
1. Bot non in esecuzione
2. Nessun segnale ML valido
3. Balance insufficiente
4. Max posizioni già raggiunto (5)

**Soluzione:**
```bash
# Controlla se il bot gira
python main.py

# Verifica log iniziali:
# Dovresti vedere:
🚀 TRADING CYCLE STARTED
```

---

### **Problema 2: "Posizioni aperte ma no SL visibile"**

**Causa:** SL c'è ma non lo vedi nei log perché `TRAILING_SILENT_MODE = True`

**Soluzione:**
```python
# In config.py, cambia:
TRAILING_SILENT_MODE = False  # Abilita log dettagliati

# Poi riavvia bot
```

---

### **Problema 3: "Trailing non si attiva"**

**Causa:** Profit < +1%

**Verifica:**
```python
# Calcola profit corrente:
profit_pct = (current_price - entry_price) / entry_price

# Esempio:
Entry: $100
Current: $100.50
Profit: 0.5% → TRAILING NON SI ATTIVA (serve ≥1%)

Entry: $100
Current: $101.10
Profit: 1.1% → TRAILING SI ATTIVA ✅
```

---

### **Problema 4: "Trailing attivo ma SL non si aggiorna"**

**Causa:** SL ancora dentro "safe range" (-10%)

**Spiegazione:**
```python
Current Price: $102
Current SL: $95
Trigger Threshold: $102 × 0.90 = $91.80

$95 > $91.80 → SL still OK, no update needed
```

Questo è **NORMALE** e **CORRETTO** → Riduce API calls inutili!

---

## 📊 TEST MANUALE

### **Come Testare se Funziona:**

1. **Apri Posizione:**
   ```
   Attendi che il bot apra una posizione
   Controlla log: "Position opened with fixed SL protection"
   ```

2. **Verifica SL Iniziale su Bybit:**
   ```
   Vai su Bybit → Positions
   Controlla che SL = Entry × 0.95 (LONG) o × 1.05 (SHORT)
   ```

3. **Attendi Profit +1%:**
   ```
   Monitora prezzo
   Quando raggiunge +1% cerca: "🎪 TRAILING ACTIVATED"
   ```

4. **Verifica Update Trailing:**
   ```
   Attendi 60-120 secondi
   Cerca: "🎪 Trailing updated"
   ```

---

## 📝 LOG FILE COMPLETO DA CERCARE

Quando tutto funziona correttamente, vedrai questa sequenza:

```log
# 1. APERTURA
🎯 EXECUTING NEW TRADE: ETH/USDT BUY
💰 Using PORTFOLIO SIZING: $150.00 margin
📈 PLACING MARKET BUY ORDER
✅ MARKET ORDER SUCCESS: ID 12345 | Price: $100.00

# 2. STOP LOSS APPLICATO
🛡️ ETH/USDT: Stop Loss set at $95.00
   📊 Rischio REALE: 5.00% prezzo × 10x leva = -50.0% MARGIN

# 3. POSIZIONE CREATA
✅ ETH/USDT: Position opened with fixed SL protection

# 4. ATTESA PROFIT...
# (price sale a $101.10)

# 5. TRAILING ACTIVATED
🎪 TRAILING ACTIVATED: ETH @ 1.05% profit (price $101.10)

# 6. TRAILING UPDATE (dopo 60s+)
🎪 Trailing updated: ETH SL $95.00 → $93.01 (sl_too_far) | Distance: -8.0% | Profit protected: +1.2%
```

---

## 🎯 VERIFICA RAPIDA: 3 DOMANDE

### **1. Il bot sta girando?**
   → Vedi log "TRADING CYCLE STARTED"? 
   - ✅ SI → OK
   - ❌ NO → Avvia con `python main.py`

### **2. Hai posizioni aperte?**
   → Vedi log "Position opened with fixed SL protection"?
   - ✅ SI → OK, controlla SL su Bybit
   - ❌ NO → Attendi ciclo trading (15 min)

### **3. Hai profit ≥ +1%?**
   → Vedi log "TRAILING ACTIVATED"?
   - ✅ SI → Trailing attivo, attendi updates
   - ❌ NO → NORMALE, attendi profit

---

## ✅ CHECKLIST FINALE

- [ ] `SL_USE_FIXED = True` in config.py
- [ ] `SL_FIXED_PCT = 0.05` in config.py
- [ ] `TRAILING_ENABLED = True` in config.py
- [ ] Bot in esecuzione (vedi log "TRADING CYCLE")
- [ ] Posizione aperta (vedi log "Position opened")
- [ ] SL visibile su Bybit (≈ -5% da entry)
- [ ] Profit ≥ +1% per trailing activation
- [ ] Log trailing ogni 60s (se profit ≥ +1%)

---

## 🆘 SE ANCORA NON FUNZIONA

### **Raccogli Queste Info:**

1. **Ultimo log del bot** (ultime 50 righe)
2. **Posizioni su Bybit** (screenshot)
3. **Config attuale:**
   ```python
   SL_USE_FIXED = ?
   SL_FIXED_PCT = ?
   TRAILING_ENABLED = ?
   ```

4. **Situazione:**
   - Bot in esecuzione? SI/NO
   - Posizioni aperte? SI/NO (quante?)
   - Profit corrente? % per ogni posizione

Con queste info posso aiutarti meglio a capire il problema specifico!

---

**Documento Creato:** 10 Gennaio 2025  
**Autore:** System Verification Guide
