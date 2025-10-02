# 🧹 FRESH START MODE - Guida Completa

## Data Creazione
10/02/2025 - 15:51

---

## 📖 Cos'è il Fresh Start Mode?

**Fresh Start Mode** è una modalità che chiude **tutte le posizioni esistenti** su Bybit e **resetta i file locali** all'avvio del bot, garantendo un riavvio completamente pulito.

### 🎯 Quando Usarlo

**✅ Usa Fresh Start quando:**
- Hai modificato il codice e vuoi forzare il reload completo
- Vuoi testare fix/modifiche con ambiente pulito
- Hai posizioni vecchie che vuoi chiudere tutte insieme
- Vuoi ripartire da zero senza tracking di posizioni esistenti

**❌ NON usare Fresh Start quando:**
- Hai posizioni aperte profittevoli che vuoi mantenere
- Stai facendo trading normale senza modifiche al codice
- Vuoi preservare la storia di learning del bot

---

## ⚙️ Configurazione

### File da Modificare
**`config.py`** - Sezione Fresh Start Mode

### Master Switch

```python
FRESH_START_MODE = False  # Default: OFF (trading normale)
```

**Cambia in `True` per attivare:**
```python
FRESH_START_MODE = True  # Attiva fresh start all'avvio
```

---

### Opzioni Granulari

```python
FRESH_START_OPTIONS = {
    'close_all_positions': True,      # Chiudi posizioni su Bybit
    'clear_position_json': True,      # Cancella thread_safe_positions.json
    'clear_learning_state': False,    # Mantieni learning history
    'clear_rl_model': False,          # Mantieni RL agent training
    'clear_decisions': False,         # Mantieni decision files
    'clear_postmortem': False,        # Mantieni post-mortem files
    'log_detailed_cleanup': True      # Log dettagliato
}
```

---

## 📊 Scenari di Utilizzo

### Scenario 1: Testing Fix (IL TUO CASO)

**Situazione:** Hai modificato threshold RL e vuoi testare con codice fresco

```python
FRESH_START_MODE = True

FRESH_START_OPTIONS = {
    'close_all_positions': True,      # ✅ Chiudi MNT/SUPER/XPL
    'clear_position_json': True,      # ✅ Reset positions file
    'clear_learning_state': False,    # ⏭️ Mantieni history
    'clear_rl_model': True,           # ✅ RESET RL (threshold vecchi!)
    'clear_decisions': False,         # ⏭️ Mantieni per analisi
    'clear_postmortem': False,        # ⏭️ Mantieni per analisi
    'log_detailed_cleanup': True      # ✅ Log tutto
}
```

**Risultato:**
- Chiude tutte le posizioni esistenti
- Cancella RL model (usa threshold freschi 0.40/0.60)
- Mantiene learning history e analisi
- Riavvio pulito per testing

---

### Scenario 2: Trading Normale (Default)

**Situazione:** Trading normale senza modifiche

```python
FRESH_START_MODE = False  # Tutto disabilitato
```

**Risultato:**
- Protegge posizioni esistenti
- Comportamento normale del bot
- Non cancella nulla

---

### Scenario 3: Pulizia Settimanale

**Situazione:** Vuoi ripartire pulito ma mantenere learning

```python
FRESH_START_MODE = True

FRESH_START_OPTIONS = {
    'close_all_positions': True,
    'clear_position_json': True,
    'clear_learning_state': False,    # ✅ Mantieni learning!
    'clear_rl_model': False,          # ✅ Mantieni RL training
    'clear_decisions': True,          # ❌ Pulisci decision vecchie
    'clear_postmortem': True,         # ❌ Pulisci post-mortem vecchi
    'log_detailed_cleanup': True
}
```

**Risultato:**
- Fresh start MA mantiene intelligenza del bot
- Pulisce solo file analisi vecchi

---

### Scenario 4: Reset TOTALE (Debugging)

**Situazione:** Problemi seri, vuoi tabula rasa

```python
FRESH_START_MODE = True

FRESH_START_OPTIONS = {  # TUTTO True
    'close_all_positions': True,
    'clear_position_json': True,
    'clear_learning_state': True,     # ❌ Reset learning
    'clear_rl_model': True,           # ❌ Reset RL
    'clear_decisions': True,          # ❌ Reset decisions
    'clear_postmortem': True,         # ❌ Reset post-mortem
    'log_detailed_cleanup': True
}
```

**Risultato:**
- Reset COMPLETO
- Bot riparte come nuovo
- Perde tutta la storia

---

## 🚀 Come Usare

### Step 1: Modifica Config

```python
# config.py

# Attiva fresh start
FRESH_START_MODE = True

# Scegli cosa resettare (vedi scenari sopra)
FRESH_START_OPTIONS = {
    'close_all_positions': True,
    'clear_position_json': True,
    'clear_learning_state': False,
    'clear_rl_model': True,  # Per testare threshold fix
    'clear_decisions': False,
    'clear_postmortem': False,
    'log_detailed_cleanup': True
}
```

### Step 2: Avvia Bot

```bash
python main.py
```

### Step 3: Verifica Log

All'avvio vedrai:

```
================================================================================
🧹 FRESH START MODE ENABLED
================================================================================

📋 Fresh Start Options:
  • close_all_positions: ✅ ENABLED
  • clear_position_json: ✅ ENABLED
  • clear_learning_state: ⏭️ DISABLED
  • clear_rl_model: ✅ ENABLED
  • clear_decisions: ⏭️ DISABLED
  • clear_postmortem: ⏭️ DISABLED
  • log_detailed_cleanup: ✅ ENABLED

--------------------------------------------------------------------------------
📊 Checking Bybit positions...
⚠️ Found 3 positions to close
  • MNT SHORT @ $1.965700 | PnL: $-8.36
  • SUPER LONG @ $0.672900 | PnL: $-32.43
  • XPL SHORT @ $0.992600 | PnL: $-5.44

🔄 Closing all positions at market...
  ✅ MNT closed
  ✅ SUPER closed
  ✅ XPL closed

✅ Closed 3 positions

  ✅ thread_safe_positions.json deleted
  ⏭️ learning_db not found (already clean)
  ✅ rl_agent.pth deleted (will use fresh threshold)
  ⏭️ trade_decisions empty (already clean)
  ⏭️ trade_postmortem empty (already clean)

--------------------------------------------------------------------------------
📊 FRESH START SUMMARY
--------------------------------------------------------------------------------
  Positions closed:  3
  Files deleted:     2
  Files backed up:   2
  Errors:            0

📦 Backups saved in: fresh_start_backups/

================================================================================
✅ FRESH START COMPLETE
================================================================================
Starting fresh session...
```

### Step 4: Disattiva Fresh Start

**IMPORTANTE:** Dopo il primo avvio, **disattiva fresh start** per trading normale!

```python
# config.py

FRESH_START_MODE = False  # ✅ Torna a False!
```

---

## 📂 File Coinvolti

### File che Vengono Chiusi/Cancellati

| File/Directory | Opzione | Descrizione |
|---|---|---|
| **Posizioni Bybit** | `close_all_positions` | Chiude tutte le posizioni market |
| `thread_safe_positions.json` | `clear_position_json` | Tracking posizioni locali |
| `learning_db/online_learning_state.json` | `clear_learning_state` | Storia learning (100 trade) |
| `trained_models/rl_agent.pth` | `clear_rl_model` | Modello RL con threshold |
| `trade_decisions/*.json` | `clear_decisions` | Decision files apertura |
| `trade_postmortem/*.json` | `clear_postmortem` | Post-mortem analisi perdite |

---

## 💾 Backup Automatico

**Prima di cancellare qualsiasi file, il sistema crea backup automatici!**

### Directory Backup
```
fresh_start_backups/
├── thread_safe_positions_20251002_155107.json
├── rl_agent_20251002_155107.pth
├── trade_decisions_20251002_155107/
└── trade_postmortem_20251002_155107/
```

### Recupero Backup

Se hai cancellato qualcosa per errore:

```bash
# Vedi i backup disponibili
ls fresh_start_backups/

# Recupera un file
cp fresh_start_backups/rl_agent_20251002_155107.pth trained_models/rl_agent.pth
```

---

## ⚠️ Attenzioni

### 🔴 PERICOLO: Chiusura Posizioni

**Fresh start chiude TUTTE le posizioni a MARKET!**

- ✅ Utile se hai posizioni in perdita che vuoi chiudere
- ❌ PERICOLOSO se hai posizioni profittevoli aperte
- ⚠️ Chiusura a market (no limite di prezzo)

**Controlla sempre le posizioni aperte prima di attivare!**

```bash
# Vedi posizioni correnti
python view_current_status.py
```

---

### 🟡 ATTENZIONE: Learning State

Se resetti `clear_learning_state = True`:
- ❌ Perdi tutta la storia dei 100 trade
- ❌ Pattern identificati cancellati
- ❌ Adaptive threshold resettati

**Raccomandazione:** Lascia `False` per preservare intelligenza!

---

### 🟢 SICURO: RL Model Reset

Resettare `clear_rl_model = True` è **sicuro** quando:
- Hai modificato threshold nel codice
- Vuoi forzare uso dei nuovi valori
- Il modello vecchio usa parametri obsoleti

Il bot ricreerà il modello automaticamente.

---

## 🐛 Troubleshooting

### Errore: "Fresh start failed"

**Causa:** Errore durante chiusura posizioni o cleanup

**Soluzione:**
1. Controlla log per dettagli errore
2. Bot prosegue comunque (safe)
3. Chiudi posizioni manualmente se necessario
4. Riprova fresh start

---

### Errore: "Position closure failed for SYMBOL"

**Causa:** API Bybit non risponde o symbol invalido

**Soluzione:**
1. Verifica connessione internet
2. Controlla API keys Bybit valide
3. Chiudi manualmente quella posizione su Bybit
4. Riprova

---

### Warning: "Backup failed"

**Causa:** Problemi permessi file o disco pieno

**Soluzione:**
1. Controlla spazio disco disponibile
2. Verifica permessi directory `fresh_start_backups/`
3. Non critico - cancellazione prosegue comunque

---

## 📊 Verifiche Post Fresh Start

### 1. Controlla Posizioni Bybit

```bash
# Sul sito Bybit o via API
# Verifica che non ci siano posizioni aperte
```

### 2. Verifica File Locali

```bash
# Dovrebbero essere stati cancellati/resettati
ls thread_safe_positions.json        # Non deve esistere
ls trained_models/rl_agent.pth       # Non deve esistere (se clear_rl_model=True)
ls learning_db/*.json                # Non deve esistere (se clear_learning_state=True)
```

### 3. Controlla Backup

```bash
# Verifica backup creati
ls -lh fresh_start_backups/
```

### 4. Testa Bot

```bash
# Avvia bot e verifica che parta pulito
python main.py

# Dovrebbe vedere:
# - Balance iniziale corretto
# - 0 posizioni attive
# - Fresh session
```

---

## 🎓 Best Practices

### ✅ DO (Fai)

1. **Controlla posizioni prima** - Usa `view_current_status.py`
2. **Disattiva dopo primo avvio** - Torna `FRESH_START_MODE = False`
3. **Usa scenario appropriato** - Vedi scenari sopra
4. **Verifica backup** - Controlla `fresh_start_backups/`
5. **Test in DEMO prima** - Se possibile

### ❌ DON'T (Non Fare)

1. **Non lasciare sempre attivo** - Solo per testing/cleanup
2. **Non usare se posizioni profit** - Perderesti profitti
3. **Non resettare learning senza motivo** - Perdi intelligenza
4. **Non ignorare errori** - Controlla sempre i log
5. **Non usare in produzione** - Solo per testing

---

## 🚀 Quick Reference

### Attiva Fresh Start
```python
# config.py
FRESH_START_MODE = True
```

### Disattiva Fresh Start
```python
# config.py
FRESH_START_MODE = False  # ✅ Ricordati!
```

### Vedi Posizioni Correnti
```bash
python view_current_status.py
```

### Avvia Bot
```bash
python main.py
```

### Controlla Backup
```bash
ls fresh_start_backups/
```

---

## 📚 Files Correlati

- **`config.py`** - Configurazione fresh start
- **`core/fresh_start_manager.py`** - Logica implementazione
- **`main.py`** - Integrazione all'avvio
- **`view_current_status.py`** - Verifica stato posizioni

---

## ❓ FAQ

**Q: Posso usare fresh start con DEMO_MODE?**  
A: Sì! Skipperà chiusura posizioni Bybit (non esistono in demo).

**Q: Fresh start cancella i modelli XGBoost?**  
A: No, solo RL agent se `clear_rl_model = True`.

**Q: Posso recuperare file cancellati?**  
A: Sì, controlla `fresh_start_backups/` directory.

**Q: Fresh start influenza balance?**  
A: No, balance viene risincronizzato da Bybit dopo fresh start.

**Q: Quanto tempo richiede?**  
A: 5-10 secondi per chiusura posizioni + cleanup.

---

## 🎯 Riepilogo

**Fresh Start Mode = Riavvio Pulito Garantito**

✅ Chiude tutte le posizioni  
✅ Resetta file locali selettivamente  
✅ Backup automatico  
✅ Forzato reload codice  
✅ Perfetto per testing fix  

**Usa con intelligenza e disattiva dopo il primo avvio!** 🚀
