# Guida al Setup e Lancio del Trading Agent

## 📋 Panoramica

Questo documento spiega come configurare e lanciare il Trading Agent. Il bot può essere eseguito su diverse piattaforme:

- **Locale** (Windows, Linux, macOS)
- **Railway** (Cloud - consigliato per produzione)
- **Altri servizi cloud** (Heroku, VPS, ecc.)

---

## 🛠️ Prerequisiti

### Software Richiesto

1. **Python 3.9+** 
   - Download: https://www.python.org/downloads/
   - Verifica installazione: `python --version`

2. **PostgreSQL** (per il database)
   - Opzione A: Installazione locale - https://www.postgresql.org/download/
   - Opzione B: Servizio cloud (Supabase, ElephantSQL, Railway)

3. **Git** (opzionale, per clonare repository)
   - Download: https://git-scm.com/downloads

### Account e API Keys Necessarie

#### 1. Hyperliquid (Exchange)
- **Testnet** (per testing): https://app.hyperliquid-testnet.xyz/
- **Mainnet** (produzione): https://app.hyperliquid.xyz/
- Cosa serve:
  - `PRIVATE_KEY`: chiave privata del wallet
  - `WALLET_ADDRESS`: indirizzo del wallet

#### 2. OpenAI (LLM)
- Registrati su: https://platform.openai.com/
- Crea API key: https://platform.openai.com/api-keys
- Cosa serve:
  - `OPENAI_API_KEY`: la tua chiave API

#### 3. CoinMarketCap (Sentiment)
- Registrati su: https://coinmarketcap.com/api/
- Piano gratuito disponibile (fino a 10.000 chiamate/mese)
- Cosa serve:
  - `CMC_PRO_API_KEY`: la tua chiave API

#### 4. Database PostgreSQL
- Cosa serve:
  - `DATABASE_URL`: stringa di connessione
  - Formato: `postgresql://username:password@host:port/database_name`

---

## 🚀 Setup Locale (Windows/Linux/Mac)

### Passo 1: Prepara il Progetto

```bash
# Naviga nella directory del progetto
cd rizzo-trading-agent-main

# Crea ambiente virtuale Python (consigliato)
python -m venv venv

# Attiva l'ambiente virtuale
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### Passo 2: Installa le Dipendenze

```bash
pip install -r requirements.txt
```

### Passo 3: Configura le Variabili d'Ambiente

Crea un file `.env` nella root del progetto:

```env
# HYPERLIQUID - Exchange
PRIVATE_KEY=0x...tua_chiave_privata_qui
WALLET_ADDRESS=0x...tuo_indirizzo_wallet_qui

# OPENAI - LLM
OPENAI_API_KEY=sk-...tua_chiave_openai_qui

# COINMARKETCAP - Sentiment
CMC_PRO_API_KEY=...tua_chiave_cmc_qui

# DATABASE - PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/trading_db
```

⚠️ **IMPORTANTE**: Il file `.env` è nel `.gitignore` e non verrà caricato su Git.

### Passo 4: Setup Database

#### Opzione A: PostgreSQL locale

```bash
# Installa PostgreSQL se non lo hai
# Windows: scarica installer da postgresql.org
# Linux: sudo apt-get install postgresql
# Mac: brew install postgresql

# Crea il database
psql -U postgres
CREATE DATABASE trading_db;
\q
```

#### Opzione B: Database cloud

**Supabase** (consigliato - gratuito):
1. Vai su https://supabase.com/
2. Crea un progetto
3. Copia la connection string da Settings > Database
4. Usala come `DATABASE_URL`

**ElephantSQL**:
1. Vai su https://www.elephantsql.com/
2. Crea un'istanza gratuita
3. Copia l'URL del database
4. Usala come `DATABASE_URL`

### Passo 5: Inizializza le Tabelle del Database

```bash
python -c "import db_utils; db_utils.init_db()"
```

Questo comando creerà tutte le tabelle necessarie nel database.

### Passo 6: Configura Testnet/Mainnet

Apri `main.py` e verifica questa riga:

```python
TESTNET = True   # True = testnet, False = mainnet
```

🔴 **ATTENZIONE**: Usa SEMPRE `TESTNET = True` quando fai i primi test!

### Passo 7: Test di Funzionamento

Prima di lanciare il bot completo, testa la connessione a Hyperliquid:

```bash
python test_trading.py
```

Questo script:
- Si connette a Hyperliquid (testnet)
- Mostra limiti di trading per BTC
- Esegue un ordine di test
- Verifica che tutto funzioni

### Passo 8: Lancio del Bot

```bash
python main.py
```

Il bot farà:
1. ✅ Raccogliere dati di mercato (indicatori tecnici)
2. ✅ Leggere news crypto
3. ✅ Ottenere sentiment Fear & Greed
4. ✅ Calcolare previsioni di prezzo
5. ✅ Costruire prompt per LLM
6. ✅ Ricevere decisione da OpenAI
7. ✅ Eseguire operazione su Hyperliquid
8. ✅ Salvare tutto nel database

---

## ☁️ Deploy su Railway (Produzione)

Railway è una piattaforma cloud che semplifica il deploy. Il progetto include già `railway.json`.

### Setup Railway

#### 1. Crea Account Railway
- Vai su https://railway.app/
- Registrati (gratuito con $5 di credito)

#### 2. Crea Nuovo Progetto
- Clicca "New Project"
- Seleziona "Deploy from GitHub repo"
- Collega il tuo repository

#### 3. Aggiungi PostgreSQL
- Nel progetto Railway, clicca "New"
- Seleziona "Database" > "PostgreSQL"
- Railway crea automaticamente il database e imposta `DATABASE_URL`

#### 4. Configura Variabili d'Ambiente
- Nel progetto Railway, vai su "Variables"
- Aggiungi:
  ```
  PRIVATE_KEY=0x...
  WALLET_ADDRESS=0x...
  OPENAI_API_KEY=sk-...
  CMC_PRO_API_KEY=...
  ```
- `DATABASE_URL` è già configurata automaticamente

#### 5. Deploy
- Railway eseguirà automaticamente:
  1. `pip install -r requirements.txt`
  2. `python main.py` (come da `railway.json`)

#### 6. Inizializza Database (una sola volta)
Nel terminale Railway:
```bash
python -c "import db_utils; db_utils.init_db()"
```

#### 7. Monitoring
- Visualizza i log in tempo reale su Railway
- Controlla errori e operazioni

### Schedulazione su Railway

Railway esegue `main.py` una volta. Per esecuzione continua:

**Opzione 1: Railway Cron Jobs**
- Vai su railway.app
- Aggiungi Cron Job che esegue `python main.py` ogni X minuti

**Opzione 2: Loop Interno** (modifica `main.py`)
```python
import time

while True:
    try:
        # ... codice esistente del bot ...
        
        # Attendi 15 minuti prima del prossimo ciclo
        time.sleep(15 * 60)
    except Exception as e:
        print(f"Errore: {e}")
        time.sleep(60)  # Attendi 1 minuto prima di riprovare
```

---

## 🔧 Altre Piattaforme

### Heroku

```bash
# Installa Heroku CLI
# https://devcenter.heroku.com/articles/heroku-cli

# Login
heroku login

# Crea app
heroku create nome-tuo-bot

# Aggiungi PostgreSQL
heroku addons:create heroku-postgresql:hobby-dev

# Configura variabili
heroku config:set PRIVATE_KEY=...
heroku config:set WALLET_ADDRESS=...
heroku config:set OPENAI_API_KEY=...
heroku config:set CMC_PRO_API_KEY=...

# Deploy
git push heroku main

# Inizializza DB
heroku run python -c "import db_utils; db_utils.init_db()"
```

### VPS/Server Linux

```bash
# Connettiti al server
ssh user@your-server-ip

# Installa dipendenze
sudo apt update
sudo apt install python3 python3-pip postgresql

# Clona progetto
git clone your-repo-url
cd trading-agent

# Setup come descritto in "Setup Locale"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configura .env
nano .env
# ... inserisci le chiavi ...

# Inizializza DB
python -c "import db_utils; db_utils.init_db()"

# Usa screen o tmux per esecuzione persistente
screen -S trading-bot
python main.py
# Ctrl+A+D per detach
```

---

## 📊 Monitoraggio e Debugging

### Controllare i Log

Il bot stampa informazioni su stdout/stderr. Controlla:
- Stato connessioni
- Dati raccolti
- Decisioni del LLM
- Esecuzione ordini

### Query Database

```sql
-- Ultime 10 operazioni del bot
SELECT * FROM bot_operations 
ORDER BY created_at DESC 
LIMIT 10;

-- Ultimi snapshot account
SELECT * FROM account_snapshots 
ORDER BY created_at DESC 
LIMIT 5;

-- Errori recenti
SELECT * FROM errors 
ORDER BY created_at DESC 
LIMIT 5;

-- Contesti AI (prompt usati)
SELECT id, created_at, LEFT(system_prompt, 100) 
FROM ai_contexts 
ORDER BY created_at DESC 
LIMIT 5;
```

### Tool Utili

1. **pgAdmin** (per PostgreSQL): https://www.pgadmin.org/
2. **DBeaver** (multi-DB): https://dbeaver.io/
3. **Supabase Dashboard** (se usi Supabase)

---

## ⚙️ Configurazione Avanzata

### Schedulazione Automatica

#### Linux/Mac (Cron)

```bash
# Apri crontab
crontab -e

# Esegui ogni 15 minuti
*/15 * * * * cd /path/to/trading-agent && /path/to/venv/bin/python main.py >> /var/log/trading-bot.log 2>&1

# Esegui ogni ora
0 * * * * cd /path/to/trading-agent && /path/to/venv/bin/python main.py
```

#### Windows (Task Scheduler)

1. Apri Task Scheduler
2. "Create Basic Task"
3. Nome: "Trading Bot"
4. Trigger: "Daily" o "Custom"
5. Action: "Start a program"
   - Program: `C:\path\to\python.exe`
   - Arguments: `C:\path\to\main.py`
   - Start in: `C:\path\to\trading-agent`

### Modifica Ticker

In `main.py`, cambia i ticker da analizzare:

```python
tickers = ['BTC', 'ETH', 'SOL']  # Aggiungi/rimuovi ticker
```

⚠️ Ricorda di aggiornare anche l'enum in `trading_agent.py` se aggiungi nuovi ticker.

### Modifica Timeframe

In `indicators.py`, modifica i parametri di fetch:

```python
# Per più storico
df_15m = self.fetch_ohlcv(coin, "15m", limit=500)  # invece di 200

# Oppure cambia timeframe principale
df_1h = self.fetch_ohlcv(coin, "1h", limit=200)
```

---

## ❓ FAQ e Troubleshooting

### Il bot non si connette a Hyperliquid
- ✅ Verifica `PRIVATE_KEY` e `WALLET_ADDRESS` nel `.env`
- ✅ Controlla di avere fondi sul testnet
- ✅ Verifica `TESTNET = True` in `main.py`

### Errore OpenAI API
- ✅ Verifica `OPENAI_API_KEY` valida
- ✅ Controlla crediti disponibili su OpenAI
- ✅ Il modello `gpt-5.1` potrebbe non esistere - usa `gpt-4` o altro

### Errore Database
- ✅ Verifica `DATABASE_URL` corretta
- ✅ Controlla che il database esista
- ✅ Esegui `db_utils.init_db()` per creare tabelle

### Il bot decide sempre "hold"
- ⚠️ Normale in mercati stabili
- ✅ Controlla i log per vedere i dati in input
- ✅ Verifica che indicatori, news, sentiment siano presenti

### Size troppo piccola su Hyperliquid
- ✅ Aumenta `target_portion_of_balance` nel prompt
- ✅ Verifica minimo size per il simbolo con `debug_symbol_limits()`
- ✅ Assicurati di avere abbastanza fondi

---

## 🔒 Sicurezza

⚠️ **IMPORTANTE**:

1. **Mai committare `.env`** su Git
2. **Testa SEMPRE su testnet** prima di usare mainnet
3. **Usa chiavi separate** per testnet e mainnet
4. **Limita i fondi** sull'account di trading
5. **Monitora regolarmente** le operazioni
6. **Backup del database** periodico

---

## 📈 Passaggio a Mainnet

Quando sei pronto per trading reale:

1. ✅ Testa ampiamente su testnet (almeno 1 settimana)
2. ✅ Analizza performance nel database
3. ✅ Crea nuovo wallet Hyperliquid mainnet
4. ✅ Aggiorna `.env` con chiavi mainnet
5. ✅ Cambia `TESTNET = False` in `main.py`
6. ✅ **Inizia con somme molto piccole**
7. ✅ Monitora costantemente le prime 24-48 ore

---

## 📞 Supporto

Per problemi tecnici:
- Controlla i log del bot
- Interroga la tabella `errors` nel database
- Verifica le variabili d'ambiente

Risorse utili:
- Hyperliquid Docs: https://hyperliquid.gitbook.io/
- OpenAI API Docs: https://platform.openai.com/docs/
- Railway Docs: https://docs.railway.app/
