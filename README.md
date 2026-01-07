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
│   ├── data-fetcher/          # 🔄 AGENTE 1: Fetcher Real-time
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── config.py
│   │   ├── fetcher.py
│   │   ├── main.py
│   │   └── core/
│   │       └── database_cache.py
│   │
│   ├── historical-data/       # 📚 AGENTE 2: Historical Data
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── config.py
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── database.py
│   │   │   └── validation.py
│   │   └── fetcher/
│   │       └── bybit_historical.py
│   │
│   ├── ml-features/           # 🧮 AGENTE 3: ML Features
│   │   ├── requirements.txt
│   │   ├── config.py
│   │   └── core/
│   │       ├── features.py
│   │       ├── market_features.py
│   │       └── labels.py
│   │
│   ├── ml-training/           # 🤖 AGENTE 4: ML Training
│   │   ├── requirements.txt
│   │   ├── config.py
│   │   └── core/
│   │       ├── dataset.py
│   │       └── trainer.py
│   │
│   └── frontend/              # 📊 AGENTE 5: Dashboard
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── app.py
│       ├── database.py
│       ├── charts.py
│       ├── indicators.py
│       ├── components/
│       │   ├── tabs/
│       │   │   ├── top_coins.py
│       │   │   ├── analysis.py
│       │   │   ├── backtest.py
│       │   │   └── historical_data.py
│       │   └── ...
│       ├── services/
│       ├── styles/
│       ├── ai/
│       └── trading/
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

### Tab 1: Top 100 Coins
- **🏆 Classifica** - Top 100 crypto per volume 24h
- **📊 Market Overview** - Grafici a barre e pie chart
- **🔍 Ricerca e filtri** - Cerca e ordina per volume

### Tab 2: Coin Analysis
- **📈 Grafici Candlestick** interattivi con Plotly
- **📊 Grafici Volume** con colori buy/sell
- **💰 Metriche** - Prezzo, High/Low, Volume, Variazione %
- **🔬 Indicatori Tecnici** - RSI, MACD, Bollinger Bands, ATR, VWAP
- **🎯 Segnali Trading** - BUY/SELL/NEUTRAL basati sugli indicatori

### Tab 3: Backtest 🆕
- **🔄 Visual Backtesting** - Simula strategie sui dati storici
- **🎯 Confidence Score** - Score da -100 (SHORT) a +100 (LONG)
- **📈 Grafico con Marker** - Entry/Exit visualizzati sul candlestick
- **📊 Statistiche** - Win Rate, Total Return, Average Trade
- **📋 Trade History** - Lista dettagliata dei trade simulati

#### Come funziona il Backtest:
1. Il sistema calcola un **Confidence Score** basato su:
   - **RSI** (±33.33 punti): Ipervenduto = LONG, Ipercomprato = SHORT
   - **MACD** (±33.33 punti): MACD > Signal = LONG, MACD < Signal = SHORT
   - **Bollinger** (±33.33 punti): Prezzo vicino lower = LONG, vicino upper = SHORT

2. **Regole di Entry**:
   - LONG quando score > +60
   - SHORT quando score < -60

3. **Regole di Exit**:
   - Exit LONG quando score < -30
   - Exit SHORT quando score > +30

### Tab 4: Historical Data 🆕
- **📊 Progress Rings** - Visualizzazione circolare del progresso backfill
- **🕯️ Statistiche** - Simboli, Candele totali, Dimensione DB, Interpolazioni
- **📅 Data Range** - Intervallo temporale dei dati ML training

#### Sub-tabs:
1. **📋 Backfill Status**
   - Progress ring globale e per timeframe (15m, 1h)
   - Indicatore simbolo attualmente in download
   - Coda simboli pending

2. **📊 Data Quality**
   - Grafico a barre completezza per simbolo
   - Filtro per timeframe
   - Statistiche qualità (≥99%, media, gap totali)

3. **📈 Price Verify**
   - Grafico candlestick dati storici
   - Selettore simbolo/timeframe/limite candles
   - Evidenziazione candele interpolate
   - Statistiche intervallo dati

4. **⚠️ Gap Detector**
   - Lista simboli con gap nei dati
   - Ordinamento per numero gap
   - Grafico top 20 simboli con più gap

#### Historical Data Agent:
```bash
# Avvia il backfill dei dati storici per ML training
docker-compose up -d historical-data

# Questo agent scarica 2 anni di dati per tutti i simboli top 100
# nei timeframe 15m e 1h, necessari per il training ML
```

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
