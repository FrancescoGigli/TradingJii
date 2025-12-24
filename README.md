# 🐳 Crypto Trading System - Multi-Agent Docker

Sistema modulare con architettura a microservizi per download e visualizzazione dati crypto.

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCKER COMPOSE                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐          ┌──────────────────┐         │
│  │  DATA-FETCHER    │          │    FRONTEND      │         │
│  │  (Python)        │          │   (Streamlit)    │         │
│  │                  │          │                  │         │
│  │  • Scarica OHLCV │          │  • Grafici       │         │
│  │  • Salva nel DB  │◄────────►│  • Dashboard     │         │
│  │  • Top 50 coins  │   SQLite │  • Candlestick   │         │
│  └──────────────────┘          └──────────────────┘         │
│           │                           │                      │
│           └───────────┬───────────────┘                      │
│                       │                                      │
│              ┌────────▼────────┐                            │
│              │  SHARED VOLUME  │                            │
│              │  trading_data.db│                            │
│              └──────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Struttura Progetto

```
progetto/
├── docker-compose.yml          # Orchestrazione multi-agente
├── .env                        # Credenziali API (non versionato)
├── .env.example                # Template credenziali
├── README.md
│
├── agents/
│   ├── data-fetcher/          # 🔄 AGENTE 1: Fetcher
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── config.py
│   │   ├── fetcher.py
│   │   ├── main.py
│   │   └── core/
│   │       └── database_cache.py
│   │
│   └── frontend/              # 📊 AGENTE 2: Dashboard
│       ├── Dockerfile
│       ├── requirements.txt
│       └── app.py
│
└── shared/                    # Volume condiviso
    └── data_cache/
        └── trading_data.db
```

## 🚀 Quick Start

### 1. Configura credenziali

```bash
# Copia il template
cp .env.example .env

# Modifica con le tue API keys
nano .env
```

Contenuto `.env`:
```
BYBIT_API_KEY=la_tua_api_key
BYBIT_API_SECRET=il_tuo_api_secret
```

### 2. Build delle immagini

```bash
docker-compose build
```

### 3. Scarica i dati

```bash
# Download completo (50 simboli, 3 timeframes)
docker-compose run data-fetcher

# Solo top 10 simboli
docker-compose run data-fetcher python main.py --symbols 10

# Solo timeframe 15m
docker-compose run data-fetcher python main.py --timeframe 15m

# Statistiche database
docker-compose run data-fetcher python main.py --stats
```

### 4. Avvia il Dashboard

```bash
docker-compose up frontend
```

Apri nel browser: **http://localhost:8501**

## 📊 Frontend Dashboard

Il dashboard Streamlit offre:

- **📈 Grafici Candlestick** interattivi con Plotly
- **📊 Grafici Volume** con colori buy/sell
- **💰 Metriche** - Prezzo, High/Low, Volume, Variazione %
- **🔍 Filtri** - Simbolo, Timeframe, Numero candele
- **📋 Tabella dati** - Ultimi 20 dati OHLCV

## 🔧 Comandi Utili

```bash
# Build singolo agente
docker-compose build data-fetcher
docker-compose build frontend

# Avvia in background
docker-compose up -d frontend

# Logs
docker-compose logs -f frontend
docker-compose logs data-fetcher

# Stop tutto
docker-compose down

# Rimuovi volumi (cancella dati!)
docker-compose down -v

# Rebuild e avvia
docker-compose up --build frontend
```

## ⏰ Scheduling (Cron)

Per aggiornare i dati periodicamente:

```bash
# Ogni ora
0 * * * * cd /path/to/project && docker-compose run --rm data-fetcher

# Ogni 15 minuti
*/15 * * * * cd /path/to/project && docker-compose run --rm data-fetcher python main.py --symbols 20 --timeframe 15m
```

## 🔌 Uso Standalone (senza Docker)

### Data Fetcher
```bash
cd agents/data-fetcher
pip install -r requirements.txt
python main.py --symbols 10 --timeframe 15m
```

### Frontend
```bash
cd agents/frontend
pip install -r requirements.txt
streamlit run app.py
```

## 📦 Volumi Docker

| Volume | Path Container | Descrizione |
|--------|---------------|-------------|
| shared-data | /app/shared | Database SQLite condiviso |

## 🌐 Porte

| Servizio | Porta | URL |
|----------|-------|-----|
| Frontend | 8501 | http://localhost:8501 |

## 🔐 Variabili d'Ambiente

| Variabile | Descrizione | Obbligatoria |
|-----------|-------------|--------------|
| BYBIT_API_KEY | API Key Bybit | ✅ |
| BYBIT_API_SECRET | API Secret Bybit | ✅ |
| SHARED_DATA_PATH | Path volume condiviso | Auto |

## 📈 Output Esempio

```
============================================================
🔄 DATA FETCHER AGENT - Bybit OHLCV
============================================================
⏰ Avvio: 2025-12-23 12:00:00
📊 Simboli: Top 50 per volume
⏱️  Timeframes: 15m, 30m, 1h
🕯️ Candele per simbolo: 1000
============================================================

📊 Analizzando volumi per 1831 simboli...
✅ Top 50 simboli per volume:
--------------------------------------------------
#    Simbolo                        Volume 24h
--------------------------------------------------
1    BTC                              $5825.3M
2    ETH                              $3728.3M
3    SOL                              $1077.8M
...
--------------------------------------------------

⬇️  Scaricando 50 simboli [15m]...
✅ Scaricati 50/50 simboli con successo
💾 Salvati 50 simboli nel database

✅ Data Fetcher completato con successo!
```

## 📜 Licenza

MIT License
