# 📱 TELEGRAM NOTIFICATIONS - GUIDA SETUP

**Sistema di notifiche real-time per il trading bot**

---

## ✅ FEATURES IMPLEMENTATE

### **Notifiche Automatiche**
- 🟢 **Posizione Aperta** - Entry, size, SL, confidence
- 💰 **Posizione Chiusa** - P&L, duration, reason
- 🔥 **Trailing Attivato** - Profit protetto, nuovo SL
- 🚨 **Errori Critici** - Alert immediati per problemi
- 📊 **Summary Giornaliero** - Win rate, P&L totale

### **Comandi Interattivi**
- `/status` - Posizioni attive e P&L
- `/balance` - Balance disponibile/usato
- `/summary` - Riepilogo sessione completo
- `/help` - Lista comandi disponibili

---

## 🚀 SETUP (10 Minuti)

### **STEP 1: Crea Bot Telegram** (3 min)

1. Apri Telegram e cerca **@BotFather**
2. Invia il comando: `/newbot`
3. Scegli un nome per il bot (es: "MyTradingBot")
4. Scegli uno username (es: "my_trading_bot")
5. Riceverai un messaggio con il **BOT TOKEN**:
   ```
   Use this token to access the HTTP API:
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
6. **Salva questo token!** Lo userai dopo

### **STEP 2: Ottieni Chat ID** (2 min)

1. Cerca il tuo bot su Telegram (username che hai scelto)
2. Clicca "START" o invia `/start`
3. Apri nel browser:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
   (sostituisci `<TOKEN>` con il token che hai ricevuto)

4. Vedrai una risposta JSON. Cerca questa parte:
   ```json
   "chat": {
     "id": 123456789,
     "first_name": "YourName",
     ...
   }
   ```

5. **Salva questo numero** (es: `123456789`) - è il tuo **CHAT_ID**

### **STEP 3: Installa Libreria** (1 min)

Apri terminale nella cartella del bot ed esegui:

```bash
pip install python-telegram-bot
```

### **STEP 4: Configura il Bot** (2 min)

Apri `config.py` e aggiungi alla fine:

```python
# ========================================
# 📱 TELEGRAM NOTIFICATIONS
# ========================================
TELEGRAM_ENABLED = True  # Attiva/disattiva notifications
TELEGRAM_BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"  # Il tuo token
TELEGRAM_CHAT_ID = "123456789"  # Il tuo chat ID
TELEGRAM_NOTIFY_ON_OPEN = True  # Notifica apertura posizioni
TELEGRAM_NOTIFY_ON_CLOSE = True  # Notifica chiusura posizioni
TELEGRAM_NOTIFY_ON_TRAILING = True  # Notifica trailing attivato
TELEGRAM_NOTIFY_ON_ERROR = True  # Notifica errori critici
TELEGRAM_ENABLE_COMMANDS = True  # Abilita comandi interattivi
```

**IMPORTANTE**: Sostituisci i valori con i tuoi!

### **STEP 5: Test** (2 min)

1. Riavvia il bot:
   ```bash
   python main.py
   ```

2. Controlla i log per:
   ```
   📱 Telegram Notifier initialized
   📱 Telegram commands enabled
   ```

3. Invia `/status` al tuo bot su Telegram
   - Dovresti ricevere risposta immediata!

4. Quando apri una posizione → ricevi notifica automatica 🎉

---

## 📱 ESEMPIO NOTIFICHE

### **Apertura Posizione**
```
🟢 NUOVA POSIZIONE
━━━━━━━━━━━━━━
📊 Symbol: BTC
🟢 Side: LONG
💵 Entry: $45,234.50
📏 Size: $75 (10x)
🛑 SL: $42,821.25 (-6.0%)
🎯 Confidence: 78.5%
⏰ 23:45:12
```

### **Chiusura Posizione**
```
✅ POSIZIONE CHIUSA (PROFIT)
━━━━━━━━━━━━━━
📊 Symbol: ETH
💰 P&L: +$12.45 (+8.3%)
📝 Reason: TRAILING STOP
⏱️ Duration: 2h 34m
⏰ 01:19:46
```

### **Trailing Attivato**
```
🔥 TRAILING STOP ATTIVO
━━━━━━━━━━━━━━
📊 Symbol: AVAX
📈 Profit Attuale: +12.5%
🛡️ New SL: $28.45
✅ Profitto Protetto: +8.7%
⏰ 00:52:31
```

---

## 🎮 COMANDI DISPONIBILI

### **/status**
Mostra posizioni attive:
```
📊 STATUS

🔄 Posizioni Attive: 4

• BTC
  📈 P&L: +6.8%
• ETH
  📉 P&L: -4.9%
• SOL
  📈 P&L: +3.2%
...
```

### **/balance**
Mostra balance corrente:
```
💰 BALANCE

💵 Total: $591.00
📊 Available: $296.00
🔒 Used: $295.00
📈 P&L: +$9.70 (+1.6%)
```

### **/summary**
Riepilogo completo:
```
📊 SESSION SUMMARY

🔄 Active: 4
✅ Closed: 12
💰 Total P&L: +$45.80
📈 P&L %: +7.7%
💵 Balance: $591.00
```

---

## ⚙️ CONFIGURAZIONE AVANZATA

### **Disabilita Notifiche Specifiche**
```python
# In config.py
TELEGRAM_NOTIFY_ON_OPEN = False  # No notifiche apertura
TELEGRAM_NOTIFY_ON_TRAILING = False  # No notifiche trailing
```

### **Solo Comandi (no notifiche automatiche)**
```python
TELEGRAM_NOTIFY_ON_OPEN = False
TELEGRAM_NOTIFY_ON_CLOSE = False
TELEGRAM_NOTIFY_ON_TRAILING = False
TELEGRAM_ENABLE_COMMANDS = True  # Solo comandi /status /balance
```

### **Disabilita Temporaneamente**
```python
TELEGRAM_ENABLED = False  # Spegne tutto
```

---

## 🔧 TROUBLESHOOTING

### **Problema: Bot non risponde**
**Soluzione**:
1. Verifica TOKEN e CHAT_ID corretti in `config.py`
2. Controlla che hai fatto `/start` al bot
3. Riavvia il bot Python

### **Problema: "Telegram library not available"**
**Soluzione**:
```bash
pip install python-telegram-bot --upgrade
```

### **Problema: Comandi non funzionano**
**Soluzione**:
1. Verifica `TELEGRAM_ENABLE_COMMANDS = True`
2. Controlla nei log: "📱 Telegram commands enabled"
3. Aspetta 30s dopo l'avvio del bot

### **Problema: Troppe notifiche**
**Soluzione**:
```python
# Disabilita trailing notifications
TELEGRAM_NOTIFY_ON_TRAILING = False
```

---

## 📊 STATISTICHE

Il sistema traccia automaticamente:
- Numero notifiche inviate
- Numero comandi ricevuti
- Ultima notifica
- Success rate invio

Accessibili via:
```python
from core.telegram_notifier import global_telegram_notifier
stats = global_telegram_notifier.get_stats()
```

---

## 🚀 PROSSIMI STEP

### **Hai completato il setup? Ora puoi:**

1. ✅ **Testare in Demo Mode**
   ```python
   # config.py
   DEMO_MODE = True
   ```

2. ✅ **Aprire posizioni di test**
   - Riceverai notifiche immediate

3. ✅ **Usare comandi interattivi**
   - Prova `/status`, `/balance`, `/summary`

4. ✅ **Passare a Live Trading**
   ```python
   DEMO_MODE = False
   ```

---

## 💡 SUGGERIMENTI

### **Privacy**
- Token e Chat ID sono **sensibili** - non condividerli!
- Aggiungi `config.py` al `.gitignore` se usi Git

### **Sicurezza**
- Il bot può rispondere **solo a te** (tuo Chat ID)
- Nessun altro può usare i comandi
- I messaggi sono criptati end-to-end

### **Performance**
- Le notifiche sono **asincrone** - non rallentano il bot
- Errori di invio non bloccano il trading
- Graceful degradation se Telegram non disponibile

---

## ✨ FEATURES FUTURE (Opzionali)

Potrebbero essere aggiunte:
- 📸 Screenshot grafici P&L
- 📈 Chart delle posizioni
- ⚡ Notifiche personalizzate per ogni symbol
- 🌐 Multi-chat support (gruppo + chat personale)
- 🤖 Comandi per chiudere posizioni da Telegram

---

## 📞 SUPPORTO

**Tutto funziona?** 
- Dovresti ricevere notifiche ad ogni apertura/chiusura
- Comandi `/status` `/balance` dovrebbero rispondere

**Hai problemi?**
- Controlla i log per errori
- Verifica TOKEN e CHAT_ID corretti
- Assicurati di aver fatto `/start` al bot

**Sistema pronto!** 🎉

---

**Creato da**: Cline AI Assistant  
**Versione**: 1.0  
**Data**: 10 Gennaio 2025
