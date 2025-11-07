# 🔄 03 - Ciclo Trading Completo (Le 9 Fasi)

Questo è il documento **CORE** che spiega come funziona il bot dal momento in cui si avvia il ciclo fino all'esecuzione dei trade. Ogni 15 minuti, il bot esegue queste 9 fasi.

---

## 📋 Indice delle Fasi

1. [**FASE 1**: Data Collection](#fase-1-data-collection-45-50s)
2. [**FASE 2**: ML Predictions](#fase-2-ml-predictions-3-4-min)
3. [**FASE 3**: Signal Processing](#fase-3-signal-processing-10s)
4. [**FASE 4**: Ranking](#fase-4-ranking-5s)
5. [**FASE 5**: Trade Execution](#fase-5-trade-execution-20-30s)
6. [**FASE 6**: Position Management](#fase-6-position-management-10s)
7. [**FASE 7**: Performance Analysis](#fase-7-performance-analysis-5s)
8. [**FASE 8**: Realtime Display](#fase-8-realtime-display-5s)
9. [**FASE 9**: Portfolio Overview](#fase-9-portfolio-overview-ongoing)

**Tempo totale:** ~5-6 minuti  
**Idle time:** ~9-10 minuti (wait 15 min cycle)

---

## 📊 Overview del Ciclo

```
CYCLE START (00:00)
  │
  ├─► [00:00-00:50] FASE 1: Data Collection
  │   ├─ Fetch top 50 simboli per volume
  │   ├─ Download candele (15m, 30m, 1h) - 5 thread paralleli
  │   ├─ Calcola indicatori tecnici (33 features)
  │   └─ Cache DB (70-90% hit rate)
  │
  ├─► [00:50-04:50] FASE 2: ML Predictions
  │   ├─ Per ogni simbolo:
  │   │   ├─ Crea 66 temporal features
  │   │   ├─ Predice con XGBoost (15m, 30m, 1h)
  │   │   ├─ Ensemble voting pesato
  │   │   └─ Calibra confidence
  │   └─ Output: {symbol: (confidence, signal, tf_predictions)}
  │
  ├─► [04:50-05:00] FASE 3: Signal Processing
  │   ├─ Filtra segnali ML con RL agent
  │   ├─ Elimina NEUTRAL signals
  │   └─ Crea execution queue
  │
  ├─► [05:00-05:05] FASE 4: Ranking
  │   └─ Ordina per confidence (highest first)
  │
  ├─► [05:05-05:35] FASE 5: Trade Execution
  │   ├─ Pre-execution sync (posizioni + balance)
  │   ├─ Calcola position sizing (adaptive/portfolio)
  │   ├─ Esegue market orders
  │   ├─ Applica Stop Loss (-5%)
  │   └─ Registra posizioni
  │
  ├─► [05:35-05:45] FASE 6: Position Management
  │   ├─ Sync forzato con Bybit
  │   ├─ Update trailing stops (se necessario)
  │   ├─ Auto-fix SL
  │   └─ Safety checks
  │
  ├─► [05:45-05:50] FASE 7: Performance Analysis
  │   └─ Summary: timing, API efficiency, symbols processed
  │
  ├─► [05:50-05:55] FASE 8: Realtime Display
  │   └─ Snapshot statico posizioni
  │
  └─► [05:55-15:00] FASE 9: Portfolio Overview
      └─ Dashboard PyQt6 (aggiornamento ogni 30s)
  │
CYCLE END (15:00) → REPEAT
```

---

## 📈 FASE 1: Data Collection (45-50s)

### **Obiettivo:**
Scaricare dati di mercato per i top 50 simboli, calcolare indicatori tecnici, e preparare dataframes per le predizioni ML.

### **Step 1.1: Fetch Markets & Filter**

```python
async def collect_market_data(exchange, enabled_timeframes, top_analysis_crypto, excluded_symbols):
    """
    Collect and organize market data for analysis
    """
    logging.info("🚀 PHASE 1: PARALLEL DATA COLLECTION")
    
    # 1. Fetch all markets from Bybit
    markets = await fetch_markets(exchange)
    
    # 2. Filter: solo USDT perpetuals attivi
    all_symbols = [
        m['symbol'] for m in markets.values()
        if m.get('quote') == 'USDT'              # Solo USDT quote
        and m.get('active')                       # Attivo
        and m.get('type') == 'swap'              # Perpetual futures
        and not any(excl in m['symbol'] for excl in excluded_symbols)
    ]
    
    # Output: ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', ...]
    logging.info(f"📊 Found {len(all_symbols)} USDT perpetuals")
```

### **Step 1.2: Get Top 50 by Volume**

```python
# Fetch volumes in parallel (20 concurrent requests)
semaphore = Semaphore(20)

async def fetch_with_semaphore(symbol):
    async with semaphore:
        ticker = await exchange.fetch_ticker(symbol)
        return (symbol, ticker.get('quoteVolume', 0))

# Parallel fetch
tasks = [fetch_with_semaphore(symbol) for symbol in all_symbols]
results = await asyncio.gather(*tasks, return_exceptions=True)

# Sort by volume
symbol_volumes = [(s, v) for s, v in results if v is not None]
symbol_volumes.sort(key=lambda x: x[1], reverse=True)

# Top 50
top_symbols = [x[0] for x in symbol_volumes[0:50]]
```

**Output esempio:**
```
Top 50 by 24h Volume:
 1. BTC/USDT:USDT    $15.2B
 2. ETH/USDT:USDT    $8.5B
 3. SOL/USDT:USDT    $2.1B
 4. XRP/USDT:USDT    $1.8B
 5. ADA/USDT:USDT    $1.5B
...
50. DOGE/USDT:USDT   $120M
```

### **Step 1.3: Download Candele (5 Thread Paralleli)**

**Sistema di download organizzato:**

```python
# Divide 50 simboli in 5 gruppi (10 per thread)
Thread 1: [BTC, ETH, SOL, XRP, ADA, ...]  (10 symbols)
Thread 2: [MATIC, DOT, AVAX, LINK, ...]   (10 symbols)
Thread 3: [...]                            (10 symbols)
Thread 4: [...]                            (10 symbols)
Thread 5: [...]                            (10 symbols)

# Progress bar per ogni thread
┌────────────────────────────────────────────────────────┐
│ [Thread 1]  BTC 🔄       ██████████ 100%              │
│ [Thread 2]  MATIC 🔄     ████░░░░░░  40%              │
│ [Thread 3]  ALGO 🔄      ██████░░░░  60%              │
│ [Thread 4]  APT 🔄       ███░░░░░░░  30%              │
│ [Thread 5]  ✅ Complete (10/10)                        │
└────────────────────────────────────────────────────────┘
📊 Overall: 42/50 (84%)
```

### **Step 1.4: Download & Process Single Symbol**

```python
async def fetch_and_save_data(exchange, symbol, timeframe):
    """
    Download candele e calcola indicatori per un simbolo
    """
    # 1. Check cache DB prima
    cached_df = load_from_cache(symbol, timeframe)
    if cached_df and is_fresh(cached_df):
        logging.debug(f"✅ {symbol}[{timeframe}] - CACHE HIT")
        return cached_df  # 70-90% dei casi!
    
    # 2. Fetch da Bybit API
    ohlcv = await exchange.fetch_ohlcv(
        symbol,
        timeframe,
        limit=500  # Ultime 500 candele
    )
    
    # 3. Converti in DataFrame
    df = pd.DataFrame(
        ohlcv,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )
    
    # 4. Calcola TUTTI gli indicatori tecnici
    df = calculate_all_indicators(df)
    
    # 5. Salva in cache DB
    save_to_cache(df, symbol, timeframe)
    
    logging.debug(f"✅ {symbol}[{timeframe}] - Downloaded & cached")
    return df
```

### **Step 1.5: Calcolo Indicatori Tecnici (33 features)**

```python
def calculate_all_indicators(df):
    """
    Calcola tutti gli indicatori tecnici necessari per ML
    
    OUTPUT: 33 colonne di features
    """
    # 1. EMAs (Exponential Moving Averages)
    df['ema5'] = ta.trend.ema_indicator(df['close'], window=5)
    df['ema10'] = ta.trend.ema_indicator(df['close'], window=10)
    df['ema20'] = ta.trend.ema_indicator(df['close'], window=20)
    
    # 2. MACD (Moving Average Convergence Divergence)
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_histogram'] = macd.macd_diff()
    
    # 3. RSI (Relative Strength Index)
    df['rsi_fast'] = ta.momentum.RSIIndicator(
        df['close'], window=14
    ).rsi()
    
    # 4. Stochastic RSI
    stoch_rsi = ta.momentum.StochRSIIndicator(df['close'])
    df['stoch_rsi'] = stoch_rsi.stochrsi()
    
    # 5. ATR (Average True Range) - Volatilità
    df['atr'] = ta.volatility.AverageTrueRange(
        df['high'], df['low'], df['close']
    ).average_true_range()
    
    # 6. Bollinger Bands
    bollinger = ta.volatility.BollingerBands(df['close'])
    df['bollinger_hband'] = bollinger.bollinger_hband()
    df['bollinger_lband'] = bollinger.bollinger_lband()
    
    # 7. VWAP (Volume Weighted Average Price)
    df['vwap'] = ta.volume.VolumeWeightedAveragePrice(
        df['high'], df['low'], df['close'], df['volume']
    ).volume_weighted_average_price()
    
    # 8. OBV (On-Balance Volume)
    df['obv'] = ta.volume.OnBalanceVolumeIndicator(
        df['close'], df['volume']
    ).on_balance_volume()
    
    # 9. ADX (Average Directional Index) - Trend strength
    df['adx'] = ta.trend.ADXIndicator(
        df['high'], df['low'], df['close']
    ).adx()
    
    # 10. Volatility (rolling std dev)
    df['volatility'] = df['close'].pct_change().rolling(window=10).std()
    
    # 11. Custom Features
    # Price position relative to recent highs/lows
    df['price_pos_5'] = (df['close'] - df['close'].rolling(5).min()) / \
                        (df['close'].rolling(5).max() - df['close'].rolling(5).min())
    
    df['price_pos_10'] = (df['close'] - df['close'].rolling(10).min()) / \
                         (df['close'].rolling(10).max() - df['close'].rolling(10).min())
    
    df['price_pos_20'] = (df['close'] - df['close'].rolling(20).min()) / \
                         (df['close'].rolling(20).max() - df['close'].rolling(20).min())
    
    # Volume acceleration
    df['vol_acceleration'] = df['volume'].pct_change()
    
    # ATR normalized move
    df['atr_norm_move'] = (df['close'] - df['close'].shift(1)) / df['atr']
    
    # Momentum divergence
    df['momentum_divergence'] = df['rsi_fast'] - df['rsi_fast'].shift(5)
    
    # Volatility squeeze
    df['volatility_squeeze'] = (df['bollinger_hband'] - df['bollinger_lband']) / df['close']
    
    # Resistance/Support distance
    df['resistance_dist_10'] = (df['close'].rolling(10).max() - df['close']) / df['close']
    df['support_dist_10'] = (df['close'] - df['close'].rolling(10).min()) / df['close']
    df['resistance_dist_20'] = (df['close'].rolling(20).max() - df['close']) / df['close']
    df['support_dist_20'] = (df['close'] - df['close'].rolling(20).min()) / df['close']
    
    # Price acceleration
    df['price_acceleration'] = df['close'].pct_change() - df['close'].pct_change().shift(1)
    
    # Volume-price alignment
    df['vol_price_alignment'] = np.sign(df['close'].pct_change()) * np.sign(df['volume'].pct_change())
    
    # Remove NaN values
    df = df.fillna(0)
    
    return df
```

### **Output FASE 1:**

```python
all_symbol_data = {
    'BTC/USDT:USDT': {
        '15m': DataFrame(500 rows × 33 columns),
        '30m': DataFrame(500 rows × 33 columns),
        '1h':  DataFrame(500 rows × 33 columns)
    },
    'ETH/USDT:USDT': {
        '15m': DataFrame(500 rows × 33 columns),
        '30m': DataFrame(500 rows × 33 columns),
        '1h':  DataFrame(500 rows × 33 columns)
    },
    ...  (50 simboli totali)
}

complete_symbols = [simboli con dati completi per tutti i timeframe]
# Tipicamente 45-50 simboli (alcuni potrebbero avere dati mancanti)
```

### **Performance FASE 1:**

```
├─ Fetch markets:           ~2s
├─ Get top 50 volumes:      ~5s (20 concurrent)
├─ Download candele:        ~35-40s (5 thread, cache 70-90%)
├─ Calculate indicators:    Incluso nel download
└─ TOTALE FASE 1:          ~45-50s
```

---

## 🤖 FASE 2: ML Predictions (3-4 min)

### **Obiettivo:**
Generare predizioni ML per ogni simbolo utilizzando XGBoost su 3 timeframes, poi aggregare con ensemble voting.

### **Step 2.1: Per Ogni Simbolo (sequenziale)**

```python
async def generate_ml_predictions(xgb_models, xgb_scalers, time_steps):
    """Generate ML predictions for all symbols"""
    
    logging.info("🎯 PHASE 2: AI MARKET INTELLIGENCE ANALYSIS")
    logging.info(f"📊 Scanning {total_symbols} crypto assets")
    
    prediction_results = {}
    
    # Per ogni simbolo con dati completi
    for i, symbol in enumerate(complete_symbols, 1):
        symbol_short = symbol.replace('/USDT:USDT', '')
        
        logging.info(f"🎯 [{i}/{total_symbols}] {symbol_short} • Deep Learning Analysis")
        
        # Get dataframes
        dataframes = all_symbol_data[symbol]  # {'15m': df, '30m': df, '1h': df}
        
        # Predict con ensemble
        ensemble_confidence, final_signal, tf_predictions = predict_signal_ensemble(
            dataframes, xgb_models, xgb_scalers, symbol, time_steps
        )
        
        # Store result
        prediction_results[symbol] = (ensemble_confidence, final_signal, tf_predictions)
        
        # Log result
        signal_names = {0: 'SELL 🔴', 1: 'BUY 🟢', 2: 'NEUTRAL 🟡'}
        if ensemble_confidence and final_signal is not None:
            signal_name = signal_names[final_signal]
            logging.info(f"   💡 Prediction: {signal_name} • Confidence: {ensemble_confidence:.1%}")
        
        await asyncio.sleep(3)  # Rate limiting tra simboli
```

### **Step 2.2: Predizione Single Symbol**

```python
def predict_signal_ensemble(dataframes, xgb_models, xgb_scalers, symbol, time_steps):
    """
    Predice segnale per un simbolo usando ensemble multi-timeframe
    
    Returns:
        ensemble_confidence: float (0.0-1.0)
        final_signal: int (0=SELL, 1=BUY, 2=NEUTRAL)
        tf_predictions: dict {timeframe: prediction}
    """
    predictions = {}
    confidences = {}
    
    # Per ogni timeframe (15m, 30m, 1h)
    for tf, df in dataframes.items():
        if tf not in xgb_models or xgb_models[tf] is None:
            continue  # Skip se modello manca
        
        # 1. Crea temporal features (66 features)
        features = create_temporal_features(df, time_steps)
        
        # 2. Normalizza con scaler
        X_scaled = xgb_scalers[tf].transform(features.reshape(1, -1))
        
        # 3. Predici con XGBoost
        probs = xgb_models[tf].predict_proba(X_scaled)[0]
        # probs = [prob_SELL, prob_BUY, prob_NEUTRAL]
        
        prediction = np.argmax(probs)  # 0, 1, o 2
        confidence = np.max(probs)     # 0.0-1.0
        
        predictions[tf] = prediction
        confidences[tf] = confidence
    
    # 4. Ensemble voting pesato
    ensemble_confidence, final_signal = ensemble_vote(predictions, confidences)
    
    return ensemble_confidence, final_signal, predictions
```

### **Step 2.3: Creazione Temporal Features (66 features)**

```python
def create_temporal_features(sequence):
    """
    REVOLUTIONARY: Usa TUTTE le candele intermedie (non solo prima/ultima)
    
    INPUT: sequence = ultimi N timesteps di dati (es. 24 candele per 1h con 6h window)
    OUTPUT: 66 features temporali
    
    BREAKDOWN:
    - 33 features correnti (stato attuale)
    - 27 features momentum (variazioni temporali)
    - 6 features statistiche critiche
    """
    features = []
    
    # 1. CURRENT STATE (33 features)
    # Stato attuale del mercato (ultima candela)
    current = sequence[-1]
    features.extend(current)  # Tutti i 33 indicatori correnti
    
    # 2. MOMENTUM PATTERNS (27 features)
    # Variazioni tra inizio e fine periodo
    if len(sequence) > 1:
        first = sequence[0]
        last = sequence[-1]
        
        # Price momentum
        price_change = (last[3] - first[3]) / (first[3] + 1e-8)  # close change
        features.append(price_change)
        
        # Volume momentum
        vol_change = (last[4] - first[4]) / (first[4] + 1e-8)
        features.append(vol_change)
        
        # EMA trends
        ema5_trend = (last[5] - first[5]) / (first[5] + 1e-8)
        ema10_trend = (last[6] - first[6]) / (first[6] + 1e-8)
        ema20_trend = (last[7] - first[7]) / (first[7] + 1e-8)
        features.extend([ema5_trend, ema10_trend, ema20_trend])
        
        # MACD evolution
        macd_change = last[8] - first[8]
        features.append(macd_change)
        
        # RSI progression
        rsi_change = last[11] - first[11]
        features.append(rsi_change)
        
        # ATR volatilità change
        atr_change = (last[13] - first[13]) / (first[13] + 1e-8)
        features.append(atr_change)
        
        # ... (altre 19 features momentum)
    else:
        # Fallback: zeros se solo 1 candela
        features.extend(np.zeros(27))
    
    # 3. CRITICAL STATS (6 features)
    # Statistiche sull'intero periodo
    
    # Volatility (std dev di price changes)
    close_prices = sequence[:, 3]  # column 3 = close
    returns = np.diff(close_prices) / close_prices[:-1]
    volatility_stat = np.std(returns) if len(returns) > 0 else 0
    features.append(volatility_stat)
    
    # Trend consistency (% candles moving in same direction)
    up_candles = np.sum(returns > 0) if len(returns) > 0 else 0
    trend_consistency = up_candles / len(returns) if len(returns) > 0 else 0.5
    features.append(trend_consistency)
    
    # Volume stability (std dev of volume)
    volumes = sequence[:, 4]  # column 4 = volume
    vol_stability = np.std(volumes) / (np.mean(volumes) + 1e-8)
    features.append(vol_stability)
    
    # Price range (max-min) / current
    price_range = (np.max(close_prices) - np.min(close_prices)) / close_prices[-1]
    features.append(price_range)
    
    # Recent acceleration (last 25% vs first 25%)
    quarter = len(sequence) // 4
    recent_avg = np.mean(close_prices[-quarter:])
    early_avg = np.mean(close_prices[:quarter])
    acceleration = (recent_avg - early_avg) / early_avg if early_avg > 0 else 0
    features.append(acceleration)
    
    # Mean reversion indicator
    current_price = close_prices[-1]
    mean_price = np.mean(close_prices)
    mean_reversion = (current_price - mean_price) / mean_price
    features.append(mean_reversion)
    
    # Convert to array and clean
    features = np.array(features, dtype=np.float64)
    features = np.nan_to_num(features, nan=0.0, posinf=1e6, neginf=-1e6)
    
    # Ensure exactly 66 features
    if len(features) < 66:
        padding = np.zeros(66 - len(features))
        features = np.concatenate([features, padding])
    elif len(features) > 66:
        features = features[:66]
    
    return features
```

### **Step 2.4: Ensemble Voting Pesato**

```python
def ensemble_vote(predictions, confidences):
    """
    Weighted ensemble voting con timeframe importance
    
    WEIGHTS (da config.py):
    - 15m: 1.0  (fast signals, meno affidabili)
    - 30m: 1.2  (medium signals, più stabili)
    - 1h:  1.5  (slow signals, più affidabili)
    """
    from config import TIMEFRAME_WEIGHTS
    
    weighted_votes = {}
    total_weight = 0.0
    
    for tf, pred in predictions.items():
        confidence = confidences.get(tf, 0.5)
        tf_weight = TIMEFRAME_WEIGHTS.get(tf, 1.0)
        
        # Combined weight = confidence × timeframe importance
        combined_weight = confidence * tf_weight
        
        # Accumulate votes
        weighted_votes[pred] = weighted_votes.get(pred, 0.0) + combined_weight
        total_weight += combined_weight
    
    # Get majority vote
    majority_vote = max(weighted_votes.items(), key=lambda x: x[1])[0]
    majority_weight = weighted_votes[majority_vote]
    
    # Calculate ensemble confidence
    ensemble_confidence = majority_weight / total_weight if total_weight > 0 else 0.0
    
    # Calibrate confidence (converte raw → real win rate)
    from core.confidence_calibrator import global_calibrator
    ensemble_confidence = global_calibrator.calibrate_xgb_confidence(ensemble_confidence)
    
    return ensemble_confidence, majority_vote
```

**Esempio pratico:**
```
Symbol: SOL/USDT:USDT

Predictions per timeframe:
├─ 15m: BUY (conf: 0.72) → weight = 0.72 × 1.0 = 0.72
├─ 30m: BUY (conf: 0.78) → weight = 0.78 × 1.2 = 0.94
└─ 1h:  BUY (conf: 0.85) → weight = 0.85 × 1.5 = 1.28

Ensemble voting:
├─ BUY total weight: 0.72 + 0.94 + 1.28 = 2.94
├─ SELL total weight: 0.0
├─ Total weight: 2.94
└─ Ensemble confidence: 2.94 / 2.94 = 1.0 (100%)

After calibration: 0.85 (85% - realistic win rate)
```

### **Output FASE 2:**

```python
prediction_results = {
    'SOL/USDT:USDT': (0.85, 1, {'15m': 1, '30m': 1, '1h': 1}),  # BUY 85%
    'AVAX/USDT:USDT': (0.78, 1, {'15m': 1, '30m': 1, '1h': 0}), # BUY 78% (mixed)
    'XRP/USDT:USDT': (0.45, 2, {'15m': 2, '30m': 2, '1h': 2}),  # NEUTRAL 45%
    'ADA/USDT:USDT': (0.72, 0, {'15m': 0, '30m': 0, '1h': 0}),  # SELL 72%
    ...
}
```

---

## 🔧 FASE 3: Signal Processing & Filtering (10s)

### **Obiettivo:**
Filtrare i segnali ML con Reinforcement Learning agent e preparare execution queue validata.

### **Step 3.1: Signal Creation da ML Results**

```python
async def process_signals(prediction_results, all_symbol_data, session_stats):
    """
    Transform ML predictions into actionable trading signals
    
    INPUT: prediction_results (da FASE 2)
    OUTPUT: validated_signals (pronti per execution)
    """
    logging.info("📈 PHASE 3: SIGNAL PROCESSING & FILTERING")
    
    all_signals = []
    skipped_count = {'neutral': 0, 'low_confidence': 0, 'excluded': 0}
    
    for symbol, (ensemble_conf, final_signal, tf_predictions) in prediction_results.items():
        symbol_short = symbol.replace('/USDT:USDT', '')
        
        # FILTER 1: Skip NEUTRAL signals (no directional edge)
        if final_signal == 2:
            skipped_count['neutral'] += 1
            logging.debug(f"⏭️ {symbol_short}: NEUTRAL signal - skipped")
            continue
        
        # FILTER 2: Skip low confidence (< 50%)
        if ensemble_conf is None or ensemble_conf < 0.50:
            skipped_count['low_confidence'] += 1
            logging.debug(f"⏭️ {symbol_short}: Low confidence {ensemble_conf:.1%} - skipped")
            continue
        
        # FILTER 3: Skip excluded symbols
        if symbol_short in EXCLUDED_SYMBOLS:
            skipped_count['excluded'] += 1
            continue
        
        # Create signal object
        signal_data = {
            'symbol': symbol,
            'symbol_short': symbol_short,
            'signal': final_signal,  # 0=SELL, 1=BUY
            'signal_name': 'BUY' if final_signal == 1 else 'SELL',
            'confidence': ensemble_conf,
            'tf_predictions': tf_predictions,  # {'15m': 1, '30m': 1, '1h': 1}
            'dataframes': all_symbol_data[symbol],  # Per calcoli aggiuntivi
            'timestamp': datetime.now()
        }
        
        all_signals.append(signal_data)
    
    logging.info(f"✅ Created {len(all_signals)} signals")
    logging.info(f"⏭️ Skipped: {skipped_count['neutral']} neutral, "
                 f"{skipped_count['low_confidence']} low conf, "
                 f"{skipped_count['excluded']} excluded")
    
    # Apply RL filter (if available)
    if RL_AGENT_ENABLED:
        validated_signals = await apply_rl_filter_batch(all_signals, session_stats)
    else:
        validated_signals = all_signals
    
    return validated_signals
```

### **Step 3.2: Reinforcement Learning Filter**

```python
async def apply_rl_filter_batch(signals, session_stats):
    """
    RL agent filters signals based on learned patterns
    
    INPUT STATE VECTOR (12 features per signal):
    - XGBoost confidence & timeframe predictions (4 features)
    - Market context: volatility, volume surge, trend strength, RSI (4 features)
    - Portfolio state: balance %, active positions, PnL (4 features)
    
    OUTPUT: Filtered signals (approved by RL)
    """
    from core.rl_agent import global_rl_agent
    
    if not global_rl_agent:
        return signals  # Fallback: accept all
    
    approved_signals = []
    rejected_count = {'weak_signal': 0, 'high_volatility': 0, 'weak_trend': 0, 'low_balance': 0}
    
    for signal in signals:
        # Build state vector
        state_vector = build_rl_state_vector(signal, session_stats)
        
        # RL prediction (0.0-1.0 probability of success)
        rl_probability = global_rl_agent.predict(state_vector)
        
        # Decision threshold: 50%
        if rl_probability >= 0.50:
            signal['rl_probability'] = rl_probability
            approved_signals.append(signal)
            logging.debug(f"✅ RL APPROVED: {signal['symbol_short']} "
                         f"(ML: {signal['confidence']:.1%}, RL: {rl_probability:.1%})")
        else:
            # Log rejection reason
            rejection_reason = analyze_rejection(state_vector, signal)
            rejected_count[rejection_reason] += 1
            logging.debug(f"❌ RL REJECTED: {signal['symbol_short']} "
                         f"(RL: {rl_probability:.1%}, Reason: {rejection_reason})")
    
    logging.info(f"🤖 RL Filter: {len(approved_signals)}/{len(signals)} approved")
    if rejected_count:
        reasons = [f"{k}: {v}" for k, v in rejected_count.items() if v > 0]
        logging.info(f"   Rejections: {', '.join(reasons)}")
    
    return approved_signals


def build_rl_state_vector(signal, session_stats):
    """
    Build 12-feature state vector for RL agent
    
    FEATURES:
    [0-3] XGBoost context
    [4-7] Market context  
    [8-11] Portfolio context
    """
    # XGBoost context (4 features)
    xgb_confidence = signal['confidence']
    tf_15m = 0.5 if signal['tf_predictions'].get('15m') == signal['signal'] else 0.0
    tf_30m = 0.5 if signal['tf_predictions'].get('30m') == signal['signal'] else 0.0
    tf_1h = 0.5 if signal['tf_predictions'].get('1h') == signal['signal'] else 0.0
    
    # Market context (4 features)
    latest_df = signal['dataframes']['15m'].iloc[-1]
    volatility = latest_df['volatility'] * 100  # As percentage
    volume_surge = latest_df['vol_acceleration']  # Volume change %
    trend_strength = latest_df['adx']  # 0-100
    rsi = latest_df['rsi_fast'] / 100.0  # Normalize to 0-1
    
    # Portfolio context (4 features)
    available_balance_pct = session_stats.get_available_balance_pct()
    active_positions = len(session_stats.active_positions)
    realized_pnl = session_stats.get_realized_pnl()
    unrealized_pnl_pct = session_stats.get_unrealized_pnl_pct()
    
    state_vector = np.array([
        xgb_confidence, tf_15m, tf_30m, tf_1h,
        volatility, volume_surge, trend_strength, rsi,
        available_balance_pct, active_positions, realized_pnl, unrealized_pnl_pct
    ], dtype=np.float32)
    
    return state_vector
```

### **Output FASE 3:**

```python
validated_signals = [
    {
        'symbol': 'SOL/USDT:USDT',
        'symbol_short': 'SOL',
        'signal': 1,  # BUY
        'signal_name': 'BUY',
        'confidence': 0.85,
        'rl_probability': 0.72,
        'tf_predictions': {'15m': 1, '30m': 1, '1h': 1},
        'timestamp': datetime(...)
    },
    {
        'symbol': 'AVAX/USDT:USDT',
        'signal': 1,
        'confidence': 0.78,
        'rl_probability': 0.68,
        ...
    },
    # ... altri segnali approvati
]

# Tipicamente 10-20 segnali validati su 40-50 iniziali
```

---

## 📊 FASE 4: Ranking & Priority Selection (5s)

### **Obiettivo:**
Ordinare segnali per confidence e selezionare top candidates per execution.

### **Step 4.1: Sort by Confidence**

```python
def rank_signals(validated_signals):
    """
    Rank signals by confidence (highest first)
    Priority execution ensures best opportunities executed first
    """
    logging.info("📈 PHASE 4: RANKING & TOP SIGNAL SELECTION")
    
    # Sort by confidence descending
    ranked_signals = sorted(
        validated_signals,
        key=lambda x: x['confidence'],
        reverse=True
    )
    
    # Log top 10
    logging.info("🏆 TOP SIGNALS BY CONFIDENCE:")
    logging.info("-" * 100)
    logging.info(f"{'RANK':<6}{'SYMBOL':<18}{'SIGNAL':<8}{'CONFIDENCE':<12}{'EXPLANATION'}")
    logging.info("-" * 100)
    
    for i, signal in enumerate(ranked_signals[:10], 1):
        consensus = "3/3" if all(
            signal['tf_predictions'].get(tf) == signal['signal'] 
            for tf in ['15m', '30m', '1h']
        ) else "2/3"
        
        explanation = f"Confidence {signal['confidence']:.1%} = {consensus} timeframes agree on {signal['signal_name']}"
        
        logging.info(
            f"{i:<6}{signal['symbol_short']:<18}"
            f"{signal['signal_name']:<8}{signal['confidence']:.1%:<12}"
            f"{explanation}"
        )
    
    logging.info("-" * 100)
    
    return ranked_signals
```

### **Top 10 Example (Real Log):**

```
🏆 TOP SIGNALS BY CONFIDENCE:
────────────────────────────────────────────────────────────────────────────
RANK  SYMBOL            SIGNAL  CONFIDENCE  EXPLANATION
────────────────────────────────────────────────────────────────────────────
1     ADA               SELL    100.0%      3/3 timeframes agree on SELL
2     LINK              SELL    100.0%      3/3 timeframes agree on SELL  
3     DOT               SELL    100.0%      3/3 timeframes agree on SELL
4     WLD               SELL    100.0%      3/3 timeframes agree on SELL
5     SOL               SELL    100.0%      3/3 timeframes agree on SELL
6     TRUMP             BUY     100.0%      3/3 timeframes agree on BUY
7     MNT               SELL    100.0%      3/3 timeframes agree on SELL
8     PENGU             SELL    100.0%      3/3 timeframes agree on SELL
9     1000PEPE          SELL    100.0%      3/3 timeframes agree on SELL
10    ASTER             SELL    100.0%      3/3 timeframes agree on SELL
────────────────────────────────────────────────────────────────────────────
```

---

## 🎯 FASE 5: Trade Execution (20-30s)

### **Obiettivo:**
Eseguire trade su Bybit per i segnali validati, con position sizing adattivo e gestione rischio.

### **Step 5.1: Pre-Execution Sync**

```python
async def execute_trading_signals(ranked_signals, exchange, position_manager):
    """Execute validated trading signals"""
    
    logging.info("📈 PHASE 5: TRADE EXECUTION")
