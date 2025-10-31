# 🚨 PROBLEMI CRITICI IDENTIFICATI - Stop Loss Non Persistenti

## 📋 SINTOMI DAL LOG

Ogni ~5 minuti il sistema rileva posizioni SENZA stop loss e le ricrea:
```
2025-10-29 13:51:14,126 WARNING ⚠️ PUMPFUN: NO STOP LOSS! Setting -5% SL...
2025-10-29 13:51:14,667 INFO ✅ PUMPFUN: SL FIXED - $0.005156 (-3.02%)
```

Ma dopo pochi minuti, lo stesso stop loss risulta mancante di nuovo.

---

## 🔍 PROBLEMA #1: MISMATCH TRA SET E VERIFY (CRITICO!)

### Causa
`position_safety.py` verifica gli SL leggendo il campo `stopLoss` della posizione:
```python
# Line 76 in position_safety.py
current_sl = float(position.get('stopLoss', 0) or 0)

if current_sl == 0:
    # Interpreta come "NO STOP LOSS"
```

**MA** se gli stop loss vengono impostati come **ordini stop_market separati** (metodo `set_stop_loss_with_order_tracking`), questi NON appaiono nel campo `stopLoss` della posizione!

### Risultato
- Sistema imposta SL come ordine separato ✅
- Sistema verifica campo posizione → trova 0 ❌
- Sistema pensa SL mancante → ricrea ❌
- **LOOP INFINITO di creazione SL**

---

## 🔍 PROBLEMA #2: POSITION MODE NON VERIFICATO

### Causa
`order_manager.py` assume **One-Way Mode** (position_idx=0):
```python
# Line 304 in order_manager.py
if position_idx is None:
    position_idx = 0  # ONE-WAY MODE (default for most accounts)
```

**MA** se l'account Bybit è in **Hedge Mode**:
- position_idx=1 per LONG
- position_idx=2 per SHORT

### Risultato
- Bybit potrebbe rifiutare o ignorare l'impostazione SL
- SL non viene applicato alla posizione corretta
- Sistema non riceve errori ma SL non persiste

---

## 🔍 PROBLEMA #3: NESSUNA VERIFICA POST-SET

### Causa
Dopo aver impostato lo stop loss, il sistema NON verifica se è stato effettivamente applicato:
```python
# In position_safety.py, dopo set_trading_stop():
if result.success:
    logging.info(f"✅ {symbol_short}: SL FIXED")
    # MA non verifica se Bybit ha accettato!
```

### Risultato
- Sistema pensa SL impostato ✅
- Bybit lo rifiuta silenziosamente ❌
- Posizione rimane senza protezione ❌

---

## ✅ SOLUZIONI PROPOSTE

### SOLUZIONE 1: Unificare Set e Verify (PRIORITÀ ALTA)
```python
# Usare SEMPRE lo stesso metodo:
# - Impostare con set_trading_stop() (campo posizione)
# - Verificare leggendo position.get('stopLoss')
# 
# OPPURE:
# - Impostare con stop_market orders
# - Verificare con verify_sl_via_orders()
```

**CONSIGLIO**: Usare `set_trading_stop()` perché è più stabile su Bybit.

### SOLUZIONE 2: Auto-detect Position Mode (PRIORITÀ ALTA)
```python
async def detect_position_mode(exchange, symbol):
    """
    Rileva se l'account è in One-Way o Hedge Mode
    """
    positions = await exchange.fetch_positions([symbol])
    for pos in positions:
        if 'positionIdx' in pos:
            # Hedge Mode se positionIdx != 0
            return "hedge" if pos['positionIdx'] in [1, 2] else "oneway"
    return "oneway"  # Default
```

### SOLUZIONE 3: Verifica Post-Set (PRIORITÀ MEDIA)
```python
async def set_and_verify_sl(exchange, symbol, sl_price):
    """
    Imposta SL e verifica che sia stato applicato
    """
    # 1. Imposta SL
    result = await set_trading_stop(exchange, symbol, stop_loss=sl_price)
    
    if not result.success:
        return False
    
    # 2. Attendi 2-3 secondi
    await asyncio.sleep(2)
    
    # 3. Verifica
    positions = await exchange.fetch_positions([symbol])
    for pos in positions:
        if pos['symbol'] == symbol:
            actual_sl = float(pos.get('stopLoss', 0) or 0)
            if abs(actual_sl - sl_price) / sl_price < 0.01:  # 1% tolerance
                return True
    
    return False
```

### SOLUZIONE 4: Debouncing più Aggressivo (PRIORITÀ BASSA)
```python
# Aumentare debounce da 30s a 5 minuti
if time.time() - last_update < 300:  # 5 minuti invece di 30s
    return  # Skip update
```

---

## 🎯 PIANO DI AZIONE IMMEDIATO

1. **[CRITICO]** Modificare `position_safety.py` per usare SEMPRE `set_trading_stop()`
2. **[CRITICO]** Aggiungere auto-detection del Position Mode
3. **[IMPORTANTE]** Implementare verifica post-set con retry
4. **[OPZIONALE]** Aumentare debounce per ridurre API calls

---

## 📊 EVIDENZA DAI LOG

```
13:47:21 - Check SL → NESSUNO trovato
13:47:52 - SL FIXED con successo
13:48:00 - Check SL → NESSUNO trovato (52 secondi dopo!)
13:51:14 - Check SL → NESSUNO trovato
13:51:48 - SL FIXED con successo
13:56:41 - Check SL → NESSUNO trovato (5 minuti dopo!)
```

**PATTERN**: SL viene "fixato" ma scompare entro 1-5 minuti.

**DIAGNOSI**: Bybit NON sta accettando/persistendo gli SL perché:
- Position mode errato (usando 0 invece di 1/2)
- Oppure metodo di verifica errato (legge campo invece di ordini)
