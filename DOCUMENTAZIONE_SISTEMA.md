# 📊 DOCUMENTAZIONE COMPLETA SISTEMA TRADING BOT

**Bot di Trading Automatico per Criptovalute con Architettura Ibrida AI/ML**

---

## 📑 INDICE

1. [Panoramica Sistema](#1-panoramica-sistema)
2. [Architettura Tecnica](#2-architettura-tecnica)
3. [Pipeline Trading Completa](#3-pipeline-trading-completa)
4. [Sistema Machine Learning](#4-sistema-machine-learning)
5. [Dual-Engine AI System](#5-dual-engine-ai-system)
6. [Risk Management](#6-risk-management)
7. [Position Management](#7-position-management)
8. [Market Intelligence](#8-market-intelligence)
9. [Configurazione e Parametri](#9-configurazione-e-parametri)
10. [Logiche di Decisione](#10-logiche-di-decisione)

---

## 1. PANORAMICA SISTEMA

### 1.1 Descrizione Generale

Sistema di trading automatico per criptovalute progettato per operare su **Bybit Futures** con un approccio ibrido che combina:
- **Machine Learning** (XGBoost) per predizioni rapide basate su pattern storici
- **Intelligenza Artificiale** (GPT-4o) per analisi contestuale con ragionamento
- **Market Intelligence** per incorporare notizie, sentiment e previsioni

### 1.2 Caratteristiche Principali

- **Exchange**: Bybit Perpetual Futures (USDT)
- **Leva Finanziaria**: 8x
- **Dimensione Posizione**: $40 fisso per trade
- **Max Posizioni**: 10 simultanee
- **Stop Loss**: Fisso -6% prezzo = -48% ROE (con leva 8x)
- **Trailing Stop**: Attivazione a +12% ROE, protezione -8% ROE
- **Cicli Trading**: Ogni 15 minuti
- **Timeframes Analisi**: 5m, 15m, 30m

### 1.3 Modalità Operative

**LIVE MODE** (default):
- Trading reale con denaro vero su Bybit
- Credenziali API richieste (BYBIT_API_KEY, BYBIT_API_SECRET)
- Sync bidirezionale con exchange

**DEMO MODE**:
- Simulazione con balance virtuale $1000
- Nessuna connessione API reale
- Testing strategie senza rischio

---

## 2. ARCHITETTURA TECNICA

### 2.1 Stack Tecnologico

**Linguaggio**: Python 3.10+

**Librerie Core**:
- `ccxt` - Connessione exchange Bybit
- `pandas` / `numpy` - Manipolazione dati
- `ta` - Indicatori tecnici
- `xgboost` - Machine Learning
- `scikit-learn` - Preprocessing e metriche
- `openai` - GPT-4o AI integration
- `prophet` - Time series forecasting

**Architettura Async**:
- `asyncio` - Event loop principale
- Operazioni I/O non bloccanti
- Task paralleli (data fetch, AI analysis)

### 2.2 Struttura File System

```
📁 Trae - Versione modificata/
│
├── 📄 main.py                    # Entry point principale
├── 📄 config.py                  # Configurazione globale (600+ linee)
├── 📄 requirements.txt           # Dipendenze Python
│
├── 📁 bot_config/
│   └── config_manager.py         # Gestione configurazione interattiva
│
├── 📁 trading/
│   ├── trading_engine.py         # Orchestratore principale (800+ linee)
│   ├── market_analyzer.py        # Raccolta dati e predizioni ML
│   └── signal_processor.py       # Processamento segnali
│
├── 📁 core/                      # 30+ moduli core
│   ├── ai_technical_analyst.py   # GPT-4o parallel analysis
│   ├── decision_comparator.py    # XGB vs AI comparison
│   ├── ai_decision_validator.py  # Legacy AI validator
│   ├── market_intelligence.py    # News, sentiment, forecasts
│   ├── trading_orchestrator.py   # Esecuzione trade
│   ├── risk_calculator.py        # Portfolio sizing & risk
│   ├── order_manager.py          # Gestione ordini Bybit
│   ├── thread_safe_position_manager.py  # Position tracking
│   ├── smart_api_manager.py      # Cache API calls
│   ├── time_sync_manager.py      # Timestamp synchronization
│   ├── integrated_trailing_monitor.py   # Trailing stops
│   ├── session_statistics.py     # Statistiche sessione
│   ├── realtime_display.py       # Display posizioni
│   └── position_management/      # Sistema modulare posizioni
│       ├── position_core.py      # CRUD operations
│       ├── position_sync.py      # Sync con Bybit
│       ├── position_trailing.py  # Trailing logic
│       └── position_safety.py    # Safety checks
│
├── 📁 utils/
│   └── display_utils.py          # Funzioni di output
│
├── 📄 trainer.py                 # Training XGBoost
├── 📄 fetcher.py                 # Fetch dati OHLCV
├── 📄 data_utils.py              # Calcolo indicatori tecnici
├── 📄 model_loader.py            # Caricamento modelli
├── 📄 trade_manager.py           # Gestione trade (legacy)
├── 📄 logging_config.py          # Sistema logging
│
├── 📁 trained_models/            # Modelli XGBoost salvati
├── 📁 data_cache/                # Cache database
├── 📁 prompts/                   # Template AI prompts
└── 📁 visualizations/            # Grafici performance
```

### 2.3 Pattern Architetturali

**Singleton Globals**:
- `global_market_analyzer`
- `global_signal_processor`
- `global_thread_safe_position_manager`
- `global_trading_orchestrator`
- `global_smart_api_manager`

**Thread Safety**:
- `threading.RLock` per accesso atomico
- File persistence per state recovery
- Deep copy per read operations

**Cache Intelligente**:
- Database SQLite per OHLCV data
- TTL-based cache (30-60s)
- 70-90% hit rate target

---

## 3. PIPELINE TRADING COMPLETA

### 3.1 Ciclo Trading (ogni 15 minuti)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CICLO TRADING (15 min)                       │
└─────────────────────────────────────────────────────────────────┘

┌──────────── FASE 1: DATA COLLECTION ────────────┐
│ • Fetch top 50 crypto per volume                │
│ • Download OHLCV 5 thread paralleli             │
│ • Cache database (10x speedup)                  │
│ • Validazione dati chiusi                       │
└──────────────────────────────────────────────────┘
                        ↓
┌──────────── FASE 2: ML PREDICTIONS ─────────────┐
│ • Calcolo 33 indicatori tecnici                 │
│ • Feature engineering (66 features totali)      │
│ • XGBoost predictions su 3 timeframes           │
│ • Ensemble voting (confidence 0-1)              │
└──────────────────────────────────────────────────┘
                        ↓
┌──────────── FASE 3: SIGNAL PROCESSING ──────────┐
│ • Filtraggio confidence (>65%)                  │
│ • Rimozione NEUTRAL signals                     │
│ • Dynamic confidence threshold                  │
└──────────────────────────────────────────────────┘
                        ↓
┌──────────── FASE 3.5: DUAL-ENGINE AI ───────────┐
│ • GPT-4o analizza stessi indicatori             │
│ • Market Intelligence (news/sentiment)          │
│ • Confronto XGB vs AI                           │
│ • Strategy: consensus/weighted/champion         │
└──────────────────────────────────────────────────┘
                        ↓
┌──────────── FASE 4: RANKING ────────────────────┐
│ • Sort per confidence (highest first)           │
│ • Display top 10 signals                        │
│ • Filtra simboli già in posizione               │
└──────────────────────────────────────────────────┘
                        ↓
┌──────────── FASE 5: EXECUTION ──────────────────┐
│ • Pre-flight validation (size, precision)       │
│ • Market order + atomic stop loss               │
│ • Max 10 posizioni simultanee                   │
│ • Portfolio-based position sizing               │
└──────────────────────────────────────────────────┘
                        ↓
┌──────────── FASE 6: POSITION MANAGEMENT ────────┐
│ • Sync con Bybit (ogni 60s)                     │
│ • Trailing stop updates                         │
│ • Early exit detection                          │
│ • Safety checks                                 │
└──────────────────────────────────────────────────┘
                        ↓
┌──────────── FASE 7: REPORTING ──────────────────┐
│ • Statistiche ciclo                             │
│ • Display posizioni real-time                   │
│ • Session summary                               │
└──────────────────────────────────────────────────┘
                        ↓
                ⏰ Wait 15 min
```

### 3.2 Startup Sequence

```
1. ⚙️  ConfigManager → Selezione timeframes e modalità
2. 🔗 Exchange Init → Time sync + Auth Bybit
3. 📊 Market Init → Top 50 crypto per volume
4. 🧠 ML Models → Load/Train XGBoost per timeframe
5. 🔄 Position Sync → Import posizioni esistenti da Bybit
6. 💰 Balance Sync → Fetch USDT balance reale
7. 🚀 Trading Loop → Start ciclo ogni 15 min
```

---

## 4. SISTEMA MACHINE LEARNING

### 4.1 Modello: XGBoost

**Caratteristiche**:
- Classificazione multi-classe (BUY / SELL / NEUTRAL)
- 3 modelli separati (uno per timeframe: 5m, 15m, 30m)
- Ensemble voting per decisione finale

**Hyperparameters** (config.py):
```python
XGB_N_ESTIMATORS = 200       # Numero alberi
XGB_MAX_DEPTH = 4            # Profondità albero
XGB_LEARNING_RATE = 0.05     # Learning rate
XGB_SUBSAMPLE = 0.7          # Campionamento dati
XGB_COLSAMPLE_BYTREE = 0.7   # Campionamento features
XGB_REG_ALPHA = 0.1          # L1 regularization
XGB_REG_LAMBDA = 1.0         # L2 regularization
```

### 4.2 Features (66 totali)

**OHLCV Base (5)**:
- open, high, low, close, volume

**Medie Mobili (3)**:
- ema5, ema10, ema20

**MACD (3)**:
- macd, macd_signal, macd_histogram

**Momentum Oscillators (2)**:
- rsi_fast (7 periodi)
- stoch_rsi (14 periodi)

**Volatilità (4)**:
- atr (Average True Range)
- bollinger_hband, bollinger_lband
- volatility (% change)

**Volume (2)**:
- vwap (Volume Weighted Average Price)
- obv (On Balance Volume)

**Trend (1)**:
- adx (Average Directional Index)

**Advanced Features (13)**:
- price_pos_5, price_pos_10, price_pos_20
- vol_acceleration
- atr_norm_move
- momentum_divergence
- volatility_squeeze
- resistance_dist_10, resistance_dist_20
- support_dist_10, support_dist_20
- price_acceleration
- vol_price_alignment

**Temporal Encoding (33)**:
- Current state (ultimi valori tutti indicatori)
- Momentum patterns (trend su sequenza temporale)
- Critical stats (volatilità feature chiave)

### 4.3 Training Process

**SL-Aware Labeling** (trainer.py):
```python
def label_with_sl_awareness_v2(df, lookforward_steps=3, 
                                sl_percentage=0.06,
                                percentile_buy=80, 
                                percentile_sell=80):
    """
    Labeling intelligente che considera se lo stop loss 
    verrebbe hit durante il path futuro.
    
    - BUY: Top 20% returns che NON hit SL -6%
    - SELL: Top 20% returns che NON hit SL +6%  
    - NEUTRAL: Tutto il resto
    
    NO survivorship bias: mantiene tutti i sample,
    aggiunge 5 nuove features per pattern recognition
    """
```

**Data Collection**:
- Top 50 crypto per volume
- 90 giorni di storia per timeframe
- Esclusione primi 30 periodi (warmup indicators)

**Cross-Validation**:
- TimeSeriesSplit con 3 fold
- Train/Val split temporale (no shuffle)
- Class weighting per bilanciamento

**Metriche**:
- Accuracy, Precision, Recall, F1-Score
- Confusion Matrix per classe
- Feature importance (top 15)

### 4.4 Prediction Pipeline

```python
# Per ogni simbolo:
1. Fetch OHLCV data (con cache)
2. Calcola 33 indicatori tecnici
3. Crea features temporali (66 totali)
4. Normalizza con StandardScaler
5. Predict con XGBoost (3 timeframes)
6. Ensemble voting:
   - Se ≥2 timeframes concordi → Segnale
   - Confidence = media weighted
```

**Ensemble Weights** (config.py):
```python
TIMEFRAME_WEIGHTS = {
    "5m": 1.0,   # Weight più basso (rumore)
    "15m": 1.2,  # Weight medio
    "30m": 1.5   # Weight più alto (trend stabile)
}
```

---

## 5. DUAL-ENGINE AI SYSTEM

### 5.1 Architettura Parallela

**Concetto**:
- XGBoost e GPT-4o analizzano **GLI STESSI** indicatori tecnici
- Due "cervelli" indipendenti che ragionano su stessi dati
- Confronto e decisione strategica basata su agreement

**Differenze Chiave**:
- **XGBoost**: Pattern matching veloce, storico
- **GPT-4o**: Ragionamento contestuale, interpretazione qualitativa

### 5.2 AI Technical Analyst (GPT-4o)

**File**: `core/ai_technical_analyst.py`

**Input**:
- 33 indicatori tecnici (stessi di XGBoost)
- Market intelligence (news, sentiment, forecasts)
- Prezzo corrente

**Output** (`AISignal`):
```python
{
    "direction": "LONG" | "SHORT" | "NEUTRAL",
    "confidence": 0-100,
    "reasoning": "2-3 sentence explanation",
    "key_factors": ["RSI oversold", "MACD bullish", ...],
    "risk_level": "low" | "medium" | "high",
    "entry_quality": "excellent" | "good" | "fair" | "poor",
    "technical_score": 0-100,
    "fundamental_score": 0-100
}
```

**Prompt Engineering**:
- System prompt: "Professional crypto analyst con 10+ anni esperienza"
- Analisi obiettiva basata solo su dati forniti
- Decisivo (NEUTRAL solo se ADX < 15 o conflitti estremi)
- Output JSON strutturato con schema validation

### 5.3 Decision Comparator

**File**: `core/decision_comparator.py`

**Strategie di Esecuzione**:

**1. XGBOOST_ONLY**:
```python
if xgb_confidence >= 65%:
    trade()
```

**2. AI_ONLY**:
```python
if ai_direction != "NEUTRAL" and ai_confidence >= 70%:
    trade()
```

**3. CONSENSUS** (default):
```python
if xgb_direction == ai_direction and consensus_confidence >= 70%:
    trade()
```

**4. WEIGHTED**:
```python
weighted_confidence = 0.7 * xgb_confidence + 0.3 * ai_confidence
if weighted_confidence >= 65%:
    trade()
```

**5. CHAMPION**:
```python
best_performer = get_best_win_rate()  # XGB, AI, or CONSENSUS
if best_performer.confidence >= threshold:
    trade()
```

### 5.4 Performance Tracking

**DualEngineStats**:
- XGB win rate, total PnL, avg confidence
- AI win rate, total PnL, avg confidence, NEUTRAL count
- Consensus agreement rate, combined performance
- Disagreement tracking per analisi

**Dashboard**:
```
╔═══════════════════════════════════════════════════════════╗
║          DUAL-ENGINE PERFORMANCE COMPARISON               ║
╠═══════════════════════════════════════════════════════════╣
║  XGBoost ML Engine:                                       ║
║  • Win Rate: 58.3% (21W / 15L)                           ║
║  • Total PnL: $342.50                                     ║
║                                                           ║
║  GPT-4o AI Analyst:                                       ║
║  • Win Rate: 62.1% (18W / 11L)                           ║
║  • Total PnL: $287.30                                     ║
║                                                           ║
║  Consensus (Both Agree):                                  ║
║  • Agreement Rate: 67.8%                                  ║
║  • Win Rate: 71.4% (15W / 6L)                            ║
║  • Total PnL: $412.80                                     ║
║                                                           ║
║  🏆 CHAMPION: CONSENSUS                                   ║
╚═══════════════════════════════════════════════════════════╝
```

---

## 6. RISK MANAGEMENT

### 6.1 Position Sizing

**Portfolio-Based Approach**:
```python
def calculate_portfolio_based_margins(signals, available_balance, 
                                     total_wallet):
    """
    Dimensionamento intelligente basato su:
    - Confidence ML (più alta = più peso)
    - Volatilità (più bassa = più peso)
    - ADX trend strength (più forte = più peso)
    
    Formula:
    base_margin = available_balance / max_positions
    weight = (confidence * 0.4) + ((100-volatility) * 0.3) + (adx * 0.3)
    final_margin = base_margin * weight
    """
```

**Parametri**:
- **Fixed Size**: $40 per posizione (FIXED_POSITION_SIZE_AMOUNT)
- **Max Positions**: 10 simultanee (MAX_CONCURRENT_POSITIONS)
- **Leverage**: 8x (LEVERAGE)
- **Balance Usage**: 98% del capitale (PORTFOLIO_BALANCE_USAGE)

### 6.2 Stop Loss System

**Fixed Stop Loss**:
```python
STOP_LOSS_PCT = 0.06  # -6% prezzo

# LONG:  SL = entry_price * 0.94
# SHORT: SL = entry_price * 1.06

# Con leva 8x:
# -6% prezzo = -48% ROE (Return On Equity)
```

**Atomic Execution**:
- Stop loss impostato **contemporaneamente** all'apertura posizione
- Zero gap exposure
- Bybit conditional orders

### 6.3 Early Exit System

**Fast Reversal** (primi 15 min):
```python
if time_since_open < 15min and roe < -15%:
    close_position("FAST_REVERSAL")
```

**Immediate Drop** (primi 5 min):
```python
if time_since_open < 5min and roe < -12%:
    close_position("IMMEDIATE_DROP")
```

**Persistent Weakness** (prima ora):
```python
if time_since_open < 60min and roe < -5%:
    close_position("PERSISTENT_WEAKNESS")
```

### 6.4 Trailing Stop System

**Attivazione**:
```python
TRAILING_TRIGGER_ROE = 0.12  # +12% ROE

# LONG:  trigger_price = entry * 1.015 (con leva 8x)
# SHORT: trigger_price = entry * 0.985
```

**Protezione**:
```python
TRAILING_DISTANCE_ROE_OPTIMAL = 0.08  # Protegge tutto tranne ultimi 8% ROE
TRAILING_DISTANCE_ROE_UPDATE = 0.12   # Aggiorna quando 12% ROE lontano

# Esempio LONG:
# Entry: $100
# Current: $110 (+10% prezzo = +80% ROE con 8x)
# Trailing SL: $109.02 (protegge +72% ROE, lascia 8% breathing room)
```

**Update Frequency**:
```python
TRAILING_UPDATE_INTERVAL = 60  # Ogni 60 secondi
TRAILING_MIN_CHANGE_PCT = 0.005  # Update se >0.5% movimento
```

### 6.5 Portfolio Limits

**Margin Management**:
```python
# Con $1000 balance e 10 posizioni max:
# - $40 margin per posizione
# - $400 total margin used (40%)
# - $600 available balance (60%)

# Safety buffer: 2% reserve
# Effective usage: 98% = $980
```

**Risk Validation**:
```python
def validate_portfolio_margin(existing_margins, new_margin, balance):
    """
    Checks:
    1. Total margin < 98% balance
    2. Available balance > new_margin
    3. Position count < MAX_CONCURRENT_POSITIONS
    4. Min $20 margin per position
    """
```

---

## 7. POSITION MANAGEMENT

### 7.1 Thread-Safe Architecture

**File**: `core/thread_safe_position_manager.py` (facade)
**Implementation**: `core/position_management/` (modular)

**Componenti**:
- `position_core.py` - CRUD operations atomiche
- `position_sync.py` - Sync bidirezionale Bybit
- `position_trailing.py` - Trailing stop logic
- `position_safety.py` - Safety checks
- `position_io.py` - File persistence
- `position_data.py` - Data structures

**Thread Safety**:
```python
class PositionCore:
    def __init__(self):
        self._lock = threading.RLock()  # Reentrant lock
        self._open_positions = {}
        self._closed_positions = {}
    
    def atomic_update_position(self, position_id, updates):
        with self._lock:
            # Atomic update
            position = self._open_positions[position_id]
            for field, value in updates.items():
                setattr(position, field, value)
            self._save_positions()
```

### 7.2 Position Lifecycle

**1. Creation** (from signal):
```python
position_id = create_position(
    symbol="BTC/USDT:USDT",
    side="buy",
    entry_price=50000.0,
    position_size=400.0,  # USD notional
    leverage=8,
    confidence=0.75,
    open_reason="ML BUY 75% | TF[15m:↑72% 30m:↑78%] | @$50000",
    atr=1250.0,
    adx=32.5,
    volatility=0.025
)
```

**2. Tracking**:
```python
# Aggiornamento continuo:
- current_price (ogni sync)
- unrealized_pnl_pct (calcolato da price)
- unrealized_pnl_usd (in USD)
- max_favorable_pnl (peak ROE)
- trailing_active (bool)
- highest_price / lowest_price
```

**3. Closure**:
```python
close_position(
    position_id,
    exit_price=52000.0,
    close_reason="TRAILING_STOP" | "STOP_LOSS" | "MANUAL" | "FAST_REVERSAL"
)

# Calcola PnL finale:
# LONG: pnl_pct = ((exit - entry) / entry) * 100 * leverage
# SHORT: pnl_pct = ((entry - exit) / entry) * 100 * leverage
```

### 7.3 Sync con Bybit

**Frequency**:
```python
POSITION_SYNC_INTERVAL = 60  # Ogni 60 secondi
POSITION_SYNC_AFTER_TRADE = True  # Immediato dopo open/close
```

**Bidirezionale**:
```python
async def thread_safe_sync_with_bybit(exchange):
    """
    1. Fetch posizioni reali da Bybit
    2. Confronta con tracker locale
    
    Newly Opened:
    - Posizioni su Bybit NON in tracker
    - Import in tracker con protective levels
    
    Newly Closed:
    - Posizioni in tracker NON più su Bybit
    - Mark as closed, calculate final PnL
    
    Updates:
    - Sync unrealized PnL
    - Update current price
    - Check SL/TP existence
    """
```

**Import Posizioni Esistenti** (startup):
```python
# All'avvio, se ci sono posizioni su Bybit:
1. Crea position_id: "imported_{symbol}_{timestamp}"
2. Calcola protective levels (SL -5%, TP +10%)
3. Import in tracker
4. Place protective orders su Bybit
5. Enable trailing stop management
```

### 7.4 Safety Checks

**Auto-Fix Stop Losses**:
```python
async def check_and_fix_stop_losses(exchange):
    """
    Ogni ciclo verifica:
    - SL esiste su Bybit
    - SL è al livello corretto
    - Se mancante o errato → correggi automaticamente
    """
```

**Close Unsafe Positions**:
```python
async def check_and_close_unsafe_positions(exchange):
    """
    Chiude posizioni se:
    - ROE < -60% (disaster scenario)
    - Dimensione anomala (>2x expected)
    - SL impossible to set (asset problematico)
    """
```

**Blacklist Management**:
```python
# Simboli problematici (es. XAUT, PAXG):
SYMBOL_BLACKLIST = ['XAUT/USDT:USDT', 'PAXG/USDT:USDT']

# Auto-blacklist se:
- SL retry > 3 volte
- API errors persistenti
- Cooldown 300 secondi
```

---

## 8. MARKET INTELLIGENCE

### 8.1 Market Intelligence Hub

**File**: `core/market_intelligence.py`

**Componenti**:
1. News Collector
2. Sentiment Analyzer
3. Crypto Forecaster (Prophet)
4. Whale Alert Collector (opzionale)

### 8.2 News Feed

**Source**: CoinJournal RSS Feed

```python
class NewsCollector:
    async def fetch_latest_news(max_chars=4000):
        """
        Fetch RSS feed CoinJournal
        Parse ultimi articoli
        Strip HTML tags
        Return: aggregated text (max 4000 chars)
        """
```

**Utilizzo**:
- Context per AI decision validator
- Identificazione catalizzatori di mercato
- Sentiment qualitativo

### 8.3 Sentiment Analysis

**Source**: CoinMarketCap Fear & Greed Index

```python
class SentimentAnalyzer:
    async def get_sentiment():
        """
        Fetch CMC Fear & Greed Index
        
        Returns:
        {
            "value": 0-100,
            "classification": "Extreme Fear" | "Fear" | 
                            "Neutral" | "Greed" | "Extreme Greed"
        }
        
        Interpretation:
        - 0-25: Extreme Fear (buying opportunity?)
        - 26-45: Fear
        - 46-54: Neutral
        - 55-74: Greed
        - 75-100: Extreme Greed (reversal risk?)
        """
```

**Impact su Trading**:
- **Extreme Fear/Greed**: -5 confidence penalty
- **Risk Level**: aumenta a "high"
- **NO directional bias**: sentiment è risk modifier, non indica direzione

### 8.4 Price Forecasting (Prophet)

**Libreria**: Facebook Prophet

```python
class CryptoForecaster:
    async def forecast_symbol(symbol, timeframe="15m"):
        """
        1. Fetch ultimi 1000 candles
        2. Train Prophet model on close prices
        3. Forecast next 5 periodi
        4. Calculate % change vs current
        
        Returns:
        {
            "symbol": "BTC/USDT:USDT",
            "forecast_change_pct": +2.3,  # +2.3% expected
            "direction": "BULLISH",
            "confidence": 0.75
        }
        """
```

**Utilizzo**:
- Validation AI signals (forecast allinea con ML?)
- Confidence boost se allineato
- Early warning se contraddice segnale forte

**Limitations**:
- CPU intensive (max 5 simboli)
- Timeframe 15m (short-term)
- Historical patterns (no fundamental events)

### 8.5 Integration con AI

**Market Intelligence Object**:
```python
@dataclass
class MarketIntelligence:
    news: str  # Aggregated news text
    sentiment: Dict  # Fear & Greed
    forecasts: Dict  # Prophet predictions per symbol
    whale_alerts: str  # Large transactions (optional)
    
    timestamp: datetime
```

**Usage in AI Prompts**:
```python
prompt = f"""
TECHNICAL INDICATORS:
... (33 indicators)

FUNDAMENTAL CONTEXT:
News: {market_intel.news[:500]}
Sentiment: {market_intel.sentiment['value']}/100 
          ({market_intel.sentiment['classification']})
Forecast: {market_intel.forecasts[symbol]} 
          ({forecast_direction} {forecast_pct:+.1f}%)

YOUR TASK: Analyze and provide trading signal...
"""
```

---

## 9. CONFIGURAZIONE E PARAMETRI

### 9.1 File .env (Credenziali)

```bash
# Bybit API Credentials
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here

# OpenAI API (per AI features)
OPENAI_API_KEY=sk-your_openai_key_here

# CoinMarketCap API (per sentiment)
CMC_PRO_API_KEY=your_cmc_key_here

# Whale Alert API (opzionale)
WHALE_ALERT_API_KEY=your_whale_key_here
```

### 9.2 config.py - Sezioni Principali

**Modalità Operativa**:
```python
DEMO_MODE = False  # False = LIVE trading reale
DEMO_BALANCE = 1000.0  # Balance virtuale per demo
```

**Leverage e Position Sizing**:
```python
LEVERAGE = 8  # Leva finanziaria
FIXED_POSITION_SIZE_AMOUNT = 40.0  # $40 per trade
MAX_CONCURRENT_POSITIONS = 10  # Max posizioni simultanee
```

**Stop Loss & Take Profit**:
```python
STOP_LOSS_PCT = 0.06  # -6% stop loss
TP_ENABLED = False  # TP disabilitato, usa trailing
```

**Trailing Stop**:
```python
TRAILING_ENABLED = True
TRAILING_TRIGGER_ROE = 0.12  # Attiva a +12% ROE
TRAILING_DISTANCE_ROE_OPTIMAL = 0.08  # Protegge tutto tranne 8% ROE
TRAILING_UPDATE_INTERVAL = 60  # Check ogni 60s
```

**Early Exit**:
```python
EARLY_EXIT_ENABLED = True
EARLY_EXIT_FAST_DROP_ROE = -15  # Exit se -15% ROE in 15min
EARLY_EXIT_IMMEDIATE_DROP_ROE = -12  # Exit se -12% ROE in 5min
EARLY_EXIT_PERSISTENT_DROP_ROE = -5  # Exit se -5% ROE in 60min
```

**Timeframes**:
```python
ENABLED_TIMEFRAMES = ["5m", "15m", "30m"]
LOOKBACK_HOURS_5M = 2   # 2 ore per 5m (24 candele)
LOOKBACK_HOURS_15M = 4  # 4 ore per 15m (16 candele)
LOOKBACK_HOURS_30M = 6  # 6 ore per 30m (12 candele)
```

**Dual-Engine AI**:
```python
DUAL_ENGINE_ENABLED = True
DUAL_ENGINE_STRATEGY = "consensus"  # consensus|weighted|champion
AI_ANALYST_ENABLED = True
AI_ANALYST_MODEL = "gpt-4o"
AI_ANALYST_TEMPERATURE = 0.2
```

**Market Intelligence**:
```python
MARKET_INTELLIGENCE_ENABLED = True
CMC_SENTIMENT_ENABLED = True
PROPHET_FORECASTS_ENABLED = True
PROPHET_MAX_SYMBOLS = 5
NEWS_FEED_ENABLED = True
```

**Cache & Performance**:
```python
API_CACHE_POSITIONS_TTL = 60  # 60s cache positions
API_CACHE_TICKERS_TTL = 30  # 30s cache tickers
POSITION_SYNC_INTERVAL = 60  # Sync ogni 60s
```

**Logging**:
```python
LOG_VERBOSITY = "NORMAL"  # MINIMAL | NORMAL | DETAILED
```

### 9.3 Modifiche Comuni

**Aumentare aggressività**:
```python
LEVERAGE = 10  # Da 8x a 10x
FIXED_POSITION_SIZE_AMOUNT = 50.0  # Da $40 a $50
MIN_CONFIDENCE = 0.60  # Da 65% a 60%
```

**Protezione maggiore**:
```python
STOP_LOSS_PCT = 0.05  # Da -6% a -5%
TRAILING_TRIGGER_ROE = 0.15  # Da +12% a +15% (più conservativo)
MAX_CONCURRENT_POSITIONS = 7  # Da 10 a 7
```

**Disabilitare AI (XGBoost puro)**:
```python
DUAL_ENGINE_ENABLED = False
AI_VALIDATION_ENABLED = False
MARKET_INTELLIGENCE_ENABLED = False
```

**Demo Mode Testing**:
```python
DEMO_MODE = True
DEMO_BALANCE = 5000.0
TRADE_CYCLE_INTERVAL = 300  # 5 min per test veloci
```

---

## 10. LOGICHE DI DECISIONE

### 10.1 Quando Aprire Posizione

**Condizioni TUTTE necessarie**:

1. **ML Confidence > 65%**
   ```python
   if ensemble_confidence < MIN_CONFIDENCE:
       skip_signal()
   ```

2. **Segnale Non-NEUTRAL**
   ```python
   if final_signal == 2:  # NEUTRAL
       skip_signal()
   ```

3. **No Posizione Esistente su Simbolo**
   ```python
   if has_position_for_symbol(symbol):
       skip_signal()
   ```

4. **Slot Disponibili (< 10 posizioni)**
   ```python
   if active_positions >= MAX_CONCURRENT_POSITIONS:
       skip_signal()
   ```

5. **Balance Sufficiente**
   ```python
   if available_balance < FIXED_POSITION_SIZE_AMOUNT:
       skip_signal()
   ```

6. **AI Approval** (se Dual-Engine attivo):
   ```python
   # CONSENSUS strategy:
   if xgb_direction != ai_direction:
       skip_signal()
   if consensus_confidence < 70%:
       skip_signal()
   ```

7. **Notional Minimo Bybit** ($100):
   ```python
   position_size = (margin * leverage) / price
   if position_size * price < 100:
       skip_signal()  # Prezzo troppo alto per il margin
   ```

### 10.2 Quando Chiudere Posizione

**1. Stop Loss Hit** (-6% prezzo = -48% ROE):
```python
# LONG: current_price <= entry_price * 0.94
# SHORT: current_price >= entry_price * 1.06
close_reason = "STOP_LOSS"
```

**2. Trailing Stop Hit**:
```python
# Se trailing attivo e prezzo ritraccia:
# LONG: current_price <= trailing_sl_price
# SHORT: current_price >= trailing_sl_price
close_reason = "TRAILING_STOP"
```

**3. Early Exit - Fast Reversal**:
```python
if time_open < 15min and roe < -15%:
    close_reason = "FAST_REVERSAL"
```

**4. Early Exit - Immediate Drop**:
```python
if time_open < 5min and roe < -12%:
    close_reason = "IMMEDIATE_DROP"
```

**5. Early Exit - Persistent Weakness**:
```python
if time_open < 60min and roe < -5%:
    close_reason = "PERSISTENT_WEAKNESS"
```

**6. Safety Close** (emergenza):
```python
if roe < -60% or size_anomaly or sl_impossible:
    close_reason = "UNSAFE_POSITION"
```

**7. Manual Close** (user intervention):
```python
# Via dashboard o comando manuale
close_reason = "MANUAL"
```

### 10.3 Quando Attivare Trailing

**Condizioni**:
```python
if TRAILING_ENABLED:
    if roe >= TRAILING_TRIGGER_ROE:  # +12% ROE
        activate_trailing()
        
        # Calculate trailing SL:
        optimal_distance = TRAILING_DISTANCE_ROE_OPTIMAL  # 8% ROE
        trailing_sl = calculate_price_from_roe(
            current_roe - optimal_distance
        )
```

**Update Trailing**:
```python
# Ogni 60 secondi:
if trailing_active:
    new_roe = calculate_current_roe()
    
    # Update se ≥12% ROE di distanza:
    if new_roe - trailing_roe >= TRAILING_DISTANCE_ROE_UPDATE:
        trailing_sl = recalculate_trailing_sl(new_roe)
        update_position(trailing_sl)
```

### 10.4 Filtri Esclusione

**Simboli Esclusi**:
```python
SYMBOL_BLACKLIST = ['XAUT/USDT:USDT', 'PAXG/USDT:USDT']

# Auto-esclusione se:
- Dati insufficienti (< 50 candles)
- SL errors ripetuti (> 3 retry)
- API errors persistenti
```

**Condizioni Mercato**:
```python
# Extreme sentiment penalty:
if sentiment < 25 or sentiment > 75:
    confidence_penalty = -5  # -5% confidence
    risk_level = "high"

# High volatility:
if volatility > 6%:
    confidence_threshold += 5%  # Richiede confidence più alta
```

### 10.5 Priorità Esecuzione

**Sorting Signals**:
```python
# Sort per confidence (highest first):
signals.sort(key=lambda x: x['confidence'], reverse=True)

# Priority execution:
for signal in signals[:available_slots]:
    execute_signal(signal)
```

**Portfolio Margin Distribution**:
```python
# Peso basato su:
weight = (
    confidence * 0.4 +           # 40% peso confidence
    (100 - volatility) * 0.3 +   # 30% peso stabilità
    adx * 0.3                    # 30% peso trend strength
)

margin = base_margin * weight
```

### 10.6 Example Decision Flow

```
Signal: BTC/USDT:USDT BUY
ML Confidence: 78%
Price: $50,000

Step 1: ML Filter
✅ Confidence 78% > 65% threshold

Step 2: AI Analysis (Dual-Engine)
GPT-4o: LONG 82% confidence
Reasoning: "RSI oversold (32), MACD bullish cross, 
           strong volume surge, Prophet forecast +2.1%"
✅ Consensus LONG, combined 80%

Step 3: Market Intelligence
News: Positive (ETF approval rumors)
Sentiment: 45/100 (Fear - neutral zone)
Forecast: +2.1% bullish
✅ Context supportive

Step 4: Portfolio Check
Active Positions: 7/10
Available Balance: $320
Required Margin: $40
✅ Slot available, balance sufficient

Step 5: Risk Validation
Volatility: 2.8% (normal)
ADX: 28 (tradeable trend)
Existing exposure: BTC 0%
✅ Risk acceptable

Step 6: Pre-Flight Check
Position Size: 0.008 BTC
Notional: $400 > $100 min
Precision: Valid tick size
✅ Technical validation passed

Step 7: EXECUTE
Market Order: BUY 0.008 BTC @ $50,000
Entry: $50,000
Stop Loss: $47,000 (-6% price, -48% ROE with 8x)
Trailing Trigger: $51,200 (+2.4% price, +12% ROE)

Result: POSITION OPENED ✅
Position ID: BTC_20250812_110530_1234
Status: TRACKING with trailing enabled
```

---

## 📌 APPENDICE A: Glossario Tecnico

**ROE (Return On Equity)**: Rendimento percentuale sul margine investito
- Formula: `(PnL / Initial_Margin) * 100`
- Con leva 8x: 1% movimento prezzo = 8% ROE

**Notional Value**: Valore nominale totale della posizione
- Formula: `Margin * Leverage`
- Es: $40 margin × 8x = $320 notional

**Initial Margin (IM)**: Margine iniziale richiesto per aprire posizione
- Bybit Perpetuals: 15% del notional con leva 8x
- Es: $320 notional × 15% = $48 IM effettivo

**Atomic Operation**: Operazione indivisibile e immediata
- Es: Market order + SL nello stesso API call
- Zero gap time = zero esposizione non protetta

**Ensemble Voting**: Aggregazione predizioni multiple modelli
- Weighted average di predictions XGBoost su 3 timeframes
- Confidence finale = media ponderata

**Consensus Strategy**: Esecuzione solo con accordo XGB + AI
- Entrambi devono concordare su direzione
- Confidence combinata ≥ 70%

**Trailing Stop**: Stop loss dinamico che segue il prezzo
- Si muove solo verso profit, mai contro
- "Locks in" profitti man mano che prezzo avanza

**SL-Aware Labeling**: Labeling ML che considera stop loss hit
- Esclude scenari dove SL verrebbe colpito nel path futuro
- Riduce false positive da pattern temporanei

---

## 📌 APPENDICE B: Formule Chiave

### PnL Calculation

**LONG Position**:
```
Price_Change_Pct = ((Exit_Price - Entry_Price) / Entry_Price) * 100
ROE = Price_Change_Pct * Leverage
PnL_USD = (ROE / 100) * Initial_Margin
```

**SHORT Position**:
```
Price_Change_Pct = ((Entry_Price - Exit_Price) / Entry_Price) * 100
ROE = Price_Change_Pct * Leverage
PnL_USD = (ROE / 100) * Initial_Margin
```

### Stop Loss Prices

**LONG**:
```
SL_Price = Entry_Price * (1 - STOP_LOSS_PCT)
SL_Price = Entry_Price * 0.94  # -6%
```

**SHORT**:
```
SL_Price = Entry_Price * (1 + STOP_LOSS_PCT)
SL_Price = Entry_Price * 1.06  # +6%
```

### Trailing Stop Calculation

**LONG**:
```
Current_ROE = ((Current_Price - Entry_Price) / Entry_Price) * Leverage * 100
Protected_ROE = Current_ROE - TRAILING_DISTANCE_ROE_OPTIMAL
Protected_Price_Change = (Protected_ROE / Leverage) / 100
Trailing_SL = Entry_Price * (1 + Protected_Price_Change)
```

**SHORT**:
```
Current_ROE = ((Entry_Price - Current_Price) / Entry_Price) * Leverage * 100
Protected_ROE = Current_ROE - TRAILING_DISTANCE_ROE_OPTIMAL
Protected_Price_Change = (Protected_ROE / Leverage) / 100
Trailing_SL = Entry_Price * (1 - Protected_Price_Change)
```

### Position Sizing

**Fixed Size**:
```
Margin = FIXED_POSITION_SIZE_AMOUNT  # $40
Notional = Margin * LEVERAGE  # $40 * 8 = $320
Position_Size = Notional / Price  # $320 / $50000 = 0.0064 BTC
```

**Portfolio-Based**:
```
Base_Margin = Available_Balance / MAX_POSITIONS
Weight = (Confidence * 0.4) + ((100 - Volatility) * 0.3) + (ADX * 0.3)
Final_Margin = Base_Margin * (Weight / 100)
```

### Ensemble Confidence

```
Weights = {"5m": 1.0, "15m": 1.2, "30m": 1.5}
Total_Weight = sum(Weights.values())  # 3.7

Weighted_Sum = sum(Confidence[tf] * Weights[tf] for tf in timeframes)
Ensemble_Confidence = Weighted_Sum / Total_Weight
```

---

## 📌 APPENDICE C: Troubleshooting

### Problema: "Insufficient Balance"

**Cause**:
- Balance reale < margin richiesto
- Troppe posizioni aperte (margin allocato)
- Errore sync balance

**Soluzioni**:
```python
# 1. Check real balance:
real_balance = await get_real_balance(exchange)
print(f"Real balance: ${real_balance:.2f}")

# 2. Check used margin:
session = position_manager.get_session_summary()
print(f"Used margin: ${session['used_margin']:.2f}")
print(f"Available: ${session['available_balance']:.2f}")

# 3. Reduce position size:
FIXED_POSITION_SIZE_AMOUNT = 30.0  # Da $40 a $30

# 4. Close some positions manually
```

### Problema: "Timestamp Error"

**Cause**:
- Clock locale non sincronizzato
- Time drift > 5 secondi

**Soluzioni**:
```python
# 1. Enable auto time sync (Windows):
Settings > Time & Language > Set time automatically

# 2. Manual offset in config.py:
MANUAL_TIME_OFFSET = -2500  # -2.5 secondi

# 3. Force time sync:
await global_time_sync_manager.force_time_sync(exchange)
```

### Problema: "Position Not Found After Open"

**Cause**:
- Delay processing Bybit
- Network latency
- Order rejected silently

**Soluzioni**:
```python
# 1. Check order was filled:
orders = await exchange.fetch_orders(symbol)
print(f"Recent orders: {orders}")

# 2. Force position sync:
await position_manager.thread_safe_sync_with_bybit(exchange)

# 3. Increase wait time after order:
await asyncio.sleep(5)  # Da 3s a 5s
```

### Problema: "AI Validation Costs Too High"

**Cause**:
- Troppi simboli analizzati
- Troppi cicli al giorno

**Soluzioni**:
```python
# 1. Limit symbols analyzed:
AI_ANALYST_MAX_SYMBOLS = 5  # Da 10 a 5

# 2. Use XGBoost-only mode:
DUAL_ENGINE_ENABLED = False

# 3. Increase cycle interval:
TRADE_CYCLE_INTERVAL = 1800  # Da 15min a 30min

# 4. Set cost limits:
AI_COST_LIMIT_DAILY = 2.00  # Max $2/day
```

### Problema: "Stop Loss Not Set"

**Cause**:
- Precision error (tick size)
- Symbol blacklisted
- Rate limit hit

**Soluzioni**:
```python
# 1. Check blacklist:
if symbol in SYMBOL_BLACKLIST:
    print(f"{symbol} is blacklisted")

# 2. Manual SL correction:
await position_manager.check_and_fix_stop_losses(exchange)

# 3. Check Bybit orders:
orders = await exchange.fetch_orders(symbol, params={'type': 'stop_market'})
print(f"Stop orders: {orders}")
```

---

## 📌 APPENDICE D: Best Practices

### Performance Optimization

1. **Enable Database Cache**:
```python
ENABLE_DATA_CACHE = True
CACHE_MAX_AGE_MINUTES = 3
```

2. **Optimize API Calls**:
```python
API_CACHE_POSITIONS_TTL = 60
API_CACHE_TICKERS_TTL = 30
TRAILING_UPDATE_INTERVAL = 60
```

3. **Parallel Data Fetch**:
```python
# Already optimized in fetcher.py
# 5 parallel threads, ~10x speedup
```

### Risk Management

1. **Start Conservative**:
```python
FIXED_POSITION_SIZE_AMOUNT = 30.0  # Start with $30
MAX_CONCURRENT_POSITIONS = 5  # Limit to 5 positions
MIN_CONFIDENCE = 0.70  # Higher threshold (70%)
```

2. **Monitor Performance**:
```python
# Check session stats every cycle
session = position_manager.get_session_summary()
win_rate = session_statistics.get_win_rate()
print(f"Win Rate: {win_rate:.1f}%")
```

3. **Use Demo First**:
```python
DEMO_MODE = True
DEMO_BALANCE = 5000.0
# Test strategy for 7+ days before live
```

### Operational

1. **Regular Backups**:
```bash
# Backup position data:
cp positions.json positions_backup_$(date +%Y%m%d).json

# Backup trade history:
cp data_cache/trade_history.json backups/
```

2. **Monitor Logs**:
```python
# Set appropriate verbosity:
LOG_VERBOSITY = "NORMAL"  # Balance tra info e spam

# Watch for warnings:
tail -f bot.log | grep "⚠️"
```

3. **Balance Checks**:
```python
# Daily balance reconciliation:
bybit_balance = await get_real_balance(exchange)
tracker_balance = position_manager.get_session_summary()['balance']
discrepancy = abs(bybit_balance - tracker_balance)

if discrepancy > 10:
    print(f"WARNING: Balance mismatch ${discrepancy:.2f}")
```

---

## 🎓 CONCLUSIONI

Questo documento ha coperto l'intera architettura e logica operativa del bot di trading. 

**Punti Chiave da Ricordare**:

1. **Dual-Engine Approach**: XGBoost (veloce) + GPT-4o (contestuale) = decisioni più robuste
2. **Risk Management Rigoroso**: Stop loss fissi, trailing stops, early exit = protezione capitale
3. **Thread-Safe Design**: Operazioni atomiche, sync bidirezionale = no race conditions
4. **Market Intelligence**: News + sentiment + forecasts = context awareness
5. **Performance Optimization**: Cache, parallel fetch, API reduction = efficienza

**Per Iniziare**:
1. Configura `.env` con API keys
2. Testa in DEMO_MODE per familiarizzare
3. Start con parametri conservativi
4. Monitor performance per 7+ giorni
5. Adjust configurazione basato su risultati

**Supporto e Modifiche**:
- Il codice è ben commentato e modulare
- Ogni componente ha responsabilità chiara (SRP)
- Facile disabilitare feature non necessarie
- Logging dettagliato per debugging

---

**Documento creato**: 2025-01-08  
**Versione sistema**: 3.0 (Dual-Engine AI Integration)  
**Ultimo aggiornamento documentazione**: 2025-01-08

---
