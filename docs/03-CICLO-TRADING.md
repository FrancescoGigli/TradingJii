# 📖 03 - Ciclo Trading Completo

> **Loop operativo principale (15 minuti)**

---

## 🔄 Overview Ciclo Trading

Il bot opera in cicli di **15 minuti**, eseguendo 5 fasi sequenziali:

```
┌──────────────────────────────────────────────────┐
│         CICLO TRADING (15 MINUTI)                │
├──────────────────────────────────────────────────┤
│                                                  │
│  FASE 1: DATA COLLECTION          (60s)         │
│  ├─ Fetch OHLCV da Bybit                        │
│  ├─ Calcola indicatori tecnici                  │
│  └─ Cache SQLite (hit rate 70-90%)              │
│                                                  │
│  FASE 2: ML PREDICTIONS           (3-4min)      │
│  ├─ Feature engineering (66 features)           │
│  ├─ XGBoost predictions per TF                  │
│  ├─ Ensemble voting                             │
│  └─ Confidence calibration                      │
│                                                  │
│  FASE 3: SIGNAL PROCESSING        (10s)         │
│  ├─ Filtra confidence > 65%                     │
│  ├─ Rank per quality                            │
│  └─ Adaptive sizing calculation                 │
│                                                  │
│  FASE 4: TRADE EXECUTION          (30s)         │
│  ├─ Portfolio validation                        │
│  ├─ Market orders                               │
│  ├─ Stop Loss -5%                               │
│  └─ Trade snapshot (AI analysis)                │
│                                                  │
│  FASE 5: MONITORING               (continuo)    │
│  ├─ Balance sync (60s)                          │
│  ├─ Dashboard update (30s)                      │
│  ├─ Partial exits check (30s)                   │
│  └─ Early exit monitoring                       │
│                                                  │
│  WAIT 15 MINUTI → RICOMINCIA                    │
└──────────────────────────────────────────────────┘
```

---

## 📊 FASE 1: Data Collection (60 secondi)

### **Step 1.1: Fetch OHLCV Data**

```python
# Per ogni simbolo e timeframe
for symbol in top_symbols:
    for timeframe in ['15m', '30m', '1h']:
        ohlcv = await exchange.fetch_ohlcv(
            symbol, timeframe, 
            limit=get_timesteps_for_timeframe(timeframe)
        )
```

**Parametri**:
- **Timeframes**: 15m, 30m, 1h (ensemble multi-TF)
- **Lookback**: 6 ore uniformi (24 candele 15m, 12 candele 30m, 6 candele 1h)
- **Simboli**: Top 50 per volume
- **Parallel fetch**: 5 richieste simultanee

### **Step 1.2: Cache Check**

```python
# SQLite cache per efficienza
if cached_data := cache.get(symbol, timeframe):
    if cache.is_fresh(cached_data, max_age=180):  # 3 min TTL
        return cached_data  # Hit!
```

**Cache Performance**:
- Hit rate: 70-90%
- API calls saved: 80%
- TTL: 3 minuti per OHLCV

### **Step 1.3: Calcolo Indicatori Tecnici**

```python
# 50+ indicatori tecnici con libreria 'ta'
df['ema5'] = ta.ema(df['close'], window=5)
df['ema10'] = ta.ema(df['close'], window=10)
df['ema20'] = ta.ema(df['close'], window=20)
df['rsi_fast'] = ta.rsi(df['close'], window=14)
df['macd'] = ta.macd(df['close'])
df['adx'] = ta.adx(df['high'], df['low'], df['close'])
df['atr'] = ta.atr(df['high'], df['low'], df['close'])
df['bollinger_hband'] = ta.bollinger_hband(df['close'])
df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
# ... +40 altri indicatori
```

**Output**: DataFrame con ~35 raw indicators per simbolo/TF

---

## 🤖 FASE 2: ML Predictions (3-4 minuti)

### **Step 2.1: Feature Engineering (66 Features)**

```python
# Temporal Feature System
features = create_temporal_features(df)
```

**Feature Categories**:
1. **Current State** (33 features)
   - EMAs (5, 10, 20)
   - MACD, RSI, Stochastic RSI
   - ADX, ATR, Bollinger Bands
   - VWAP, OBV
   - Volatility, price positions

2. **Momentum** (27 features)
   - Volume acceleration
   - ATR normalized moves
   - Momentum divergence
   - Volatility squeeze
   - Resistance/support distances
   - Price acceleration

3. **Critical Stats** (6 features)
   - Volume/price alignment
   - Trend strength
   - Market regime indicators

**Total**: 66 numerical features per candela

### **Step 2.2: XGBoost Predictions Per Timeframe**

```python
for tf in ['15m', '30m', '1h']:
    # Scale features
    X_scaled = scaler[tf].transform(features)
    
    # Predict
    pred = xgb_model[tf].predict(X_scaled)  # 0=SELL, 1=BUY
    conf = xgb_model[tf].predict_proba(X_scaled)
```

**Per ogni timeframe**:
- Input: 66 features scaled
- Output: 
  - `prediction`: 0 (SELL) o 1 (BUY)
  - `confidence`: 0.0-1.0 (probabilità classe)

### **Step 2.3: Ensemble Voting**

```python
# Weighted ensemble con pesi timeframe
votes = {
    '15m': (pred_15m, conf_15m, weight=1.0),
    '30m': (pred_30m, conf_30m, weight=1.2),
    '1h': (pred_1h, conf_1h, weight=1.5)
}

# Calcola ensemble
ensemble_signal, ensemble_confidence = calculate_ensemble(votes)
```

**Regole Ensemble**:
- **Unanime**: Tutti BUY → BUY forte (confidence alta)
- **Maggioranza**: 2/3 BUY → BUY moderato
- **Misto**: BUY=SELL → NEUTRAL (skip)
- **Pesi**: TF lunghi contano di più (1h > 30m > 15m)

**Output Esempio**:
```
ETH/USDT Ensemble:
  15m: BUY 72% (weight 1.0)
  30m: BUY 78% (weight 1.2)
  1h:  BUY 81% (weight 1.5)
  → Ensemble: BUY 77% (strong agreement)
```

### **Step 2.4: Confidence Calibration**

```python
# Adjustment based on market conditions
if high_volatility:
    confidence *= 0.85  # -15% in volatile markets
    
if adx < 25:  # Weak trend
    confidence *= 0.90  # -10% for weak trends
```

**Filtri Confidence**:
- Volatility adjustment: -15% se ATR > 4%
- Trend strength: -10% se ADX < 25
- Market filter: -20% se BTC downtrend (opzionale)

---

## 🎯 FASE 3: Signal Processing (10 secondi)

### **Step 3.1: Confidence Filtering**

```python
# Filtra segnali sotto soglia
MIN_CONFIDENCE = 0.65  # 65% minimum

valid_signals = [
    sig for sig in signals 
    if sig['confidence'] >= MIN_CONFIDENCE
]
```

**Soglie**:
- Base: 65%
- Volatile markets: 75%
- Bear markets: 80%

### **Step 3.2: Signal Ranking**

```python
# Rank per quality score
def calculate_quality_score(signal):
    score = (
        signal['confidence'] * 0.6 +      # 60% peso confidence
        signal['volume_score'] * 0.2 +    # 20% peso volume
        signal['trend_strength'] * 0.2    # 20% peso trend (ADX)
    )
    return score

ranked_signals = sorted(signals, key=calculate_quality_score, reverse=True)
```

### **Step 3.3: Adaptive Position Sizing**

```python
from core.adaptive_position_sizing import global_adaptive_sizing

# Calcola margins per ogni segnale
margins, symbols, stats = global_adaptive_sizing.calculate_adaptive_margins(
    signals=ranked_signals,
    wallet_equity=current_balance,
    max_positions=5
)
```

**Adaptive Logic** (vedi doc 05 per dettagli):
1. Wallet diviso in 5 blocks (20% each)
2. Kelly Criterion se 10+ trades history
3. Premia winners: +size proporzionale a gain
4. Blocca losers: -3 cicli penalty
5. Risk validation: max 20% wallet at risk

**Output**:
```
[
  (symbol='SOL/USDT', margin=45.00, reason='kelly_criterion'),
  (symbol='AVAX/USDT', margin=38.50, reason='from_memory'),
  (symbol='MATIC/USDT', margin=50.00, reason='new_symbol'),
  ...
]
```

---

## 💼 FASE 4: Trade Execution (30 secondi)

### **Step 4.1: Portfolio Validation**

```python
# Check limiti portfolio
current_positions = position_manager.get_position_count()
if current_positions >= MAX_CONCURRENT_POSITIONS:
    return  # No space for new positions

used_margin = sum(pos.margin for pos in active_positions)
available = balance - used_margin
if available < min_required_margin:
    return  # Insufficient balance
```

### **Step 4.2: Trade Execution Loop**

```python
for i, (symbol, margin) in enumerate(zip(symbols, margins)):
    # Execute trade via orchestrator
    result = await orchestrator.execute_new_trade(
        exchange=exchange,
        signal_data={
            'symbol': symbol,
            'signal_name': 'buy',  # or 'sell'
            'confidence': signals[i]['confidence'],
            'tf_predictions': signals[i]['tf_predictions']
        },
        market_data=MarketData(
            price=current_price,
            atr=atr_value,
            volatility=volatility
        ),
        balance=current_balance,
        margin_override=margin  # Use adaptive margin
    )
```

### **Step 4.3: Order Placement**

**Sequenza per ogni trade**:

1. **Set Leverage + Isolated Margin**
```python
await exchange.set_leverage(5, symbol)
await exchange.set_margin_mode('isolated', symbol)
```

2. **Market Order**
```python
order = await exchange.create_market_order(
    symbol=symbol,
    side='buy',  # or 'sell'
    amount=position_size  # Normalized
)
```

3. **Wait 3s** (race condition fix)
```python
await asyncio.sleep(3)  # Bybit processing time
```

4. **Apply Stop Loss -5%**
```python
sl_price = entry_price * 0.95  # -5% for BUY
sl_price_normalized = normalize_price(sl_price)  # Precision handler

await exchange.set_trading_stop(
    symbol=symbol,
    stop_loss=sl_price_normalized
)
```

5. **Register in Tracker**
```python
position_id = position_manager.create_position(
    symbol=symbol,
    side='buy',
    entry_price=entry_price,
    position_size=margin * 5,  # With 5x leverage
    leverage=5,
    confidence=confidence,
    open_reason="ML BUY 77% | TF[15m:↑72% 30m:↑78% 1h:↑81%]"
)
```

6. **Save Trade Snapshot (AI)**
```python
trade_analyzer.save_trade_snapshot(
    position_id=position_id,
    snapshot=TradeSnapshot(
        symbol=symbol,
        prediction_signal='BUY',
        ml_confidence=confidence,
        ensemble_votes={'15m': 'BUY', '30m': 'BUY', '1h': 'BUY'},
        entry_price=entry_price,
        entry_features={'rsi': 55.2, 'macd': 0.15, 'adx': 28.5}
    )
)
```

**Log Output**:
```
🎯 EXECUTING NEW TRADE: SOL/USDT BUY
💰 CALCULATED LEVELS:
   Margin: $45.00 | Size: 1.2345 SOL | Notional: $225.00
   SL(calc): $91.50 | TP(calc): $0.00 (disabled)
   
✅ Pre-flight OK: size 1.2345 within [0.1, 10000]
📏 Position size: 1.2345 → 1.2345 (normalized)
✅ SOL/USDT: Stop Loss set at $91.50 (-5.0% price, -25% margin)
📸 Trade snapshot saved for AI analysis
✅ SOL/USDT: Position opened with fixed SL protection
```

---

## 👁️ FASE 5: Position Monitoring (Continuo)

### **Background Task 1: Balance Sync (ogni 60s)**

```python
while True:
    balance = await exchange.fetch_balance()
    position_manager.update_available_balance(balance)
    await asyncio.sleep(60)
```

### **Background Task 2: Dashboard Update (ogni 30s)**

```python
while True:
    positions = position_manager.get_active_positions()
    dashboard.update_tables(positions)
    await asyncio.sleep(30)
```

### **Background Task 3: Partial Exit Monitor (ogni 30s)**

```python
while True:
    for position in active_positions:
        current_roe = calculate_roe(position)
        
        # Check exit levels
        for level in PARTIAL_EXIT_LEVELS:
            if current_roe >= level['roe'] and not level['executed']:
                # Execute partial exit
                exit_size = position.size * level['pct']
                await execute_partial_exit(position, exit_size)
                level['executed'] = True
    
    await asyncio.sleep(30)
```

**Partial Exit Levels** (5x leverage):
- 30% a +50% ROE (+10% prezzo)
- 30% a +100% ROE (+20% prezzo)
- 20% a +150% ROE (+30% prezzo)
- 20% runner (trailing stop)

### **Background Task 4: Early Exit Monitor**

```python
for position in active_positions:
    duration = now - position.open_time
    current_roe = calculate_roe(position)
    
    # Immediate reversal (5 min)
    if duration < 5*60 and current_roe <= -10:
        await close_position(position, "early_exit_immediate")
    
    # Fast reversal (15 min)
    elif duration < 15*60 and current_roe <= -15:
        await close_position(position, "early_exit_fast")
    
    # Persistent weakness (60 min)
    elif duration < 60*60 and current_roe <= -5:
        await close_position(position, "early_exit_persistent")
```

---

## ⏱️ Timing Breakdown Tipico

```
CICLO COMPLETO (15 minuti)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
00:00 - 01:00   Data Collection (60s)
01:00 - 05:00   ML Predictions (4min)
05:00 - 05:10   Signal Processing (10s)
05:10 - 05:40   Trade Execution (30s)
05:40 - 15:00   Idle Wait + Monitoring (9min 20s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                TOTALE: 15:00
                
Durante idle wait:
  • Balance sync ogni 60s
  • Dashboard update ogni 30s  
  • Partial exits check ogni 30s
  • Early exit monitoring continuo
```

---

## 🔄 Esempio Ciclo Completo

```
════════════════════════════════════════════════════════════
🔄 TRADING CYCLE #45 - 16:45:00
════════════════════════════════════════════════════════════

[16:45:00] 📊 PHASE 1: Data Collection
  • Fetching 50 symbols × 3 timeframes = 150 requests
  • Cache hit rate: 82% (123/150 from cache)
  • Actual API calls: 27
  • Duration: 52 seconds ✓

[16:45:52] 🤖 PHASE 2: ML Predictions  
  • Feature engineering: 66 features × 50 symbols
  • XGBoost predictions: 15m, 30m, 1h
  • Ensemble voting: 50 symbols
  • Signals generated: 12 BUY, 8 SELL, 30 NEUTRAL
  • Duration: 3min 45s ✓

[16:49:37] 🎯 PHASE 3: Signal Processing
  • Confidence filter (>65%): 8 BUY, 5 SELL pass
  • Ranked by quality score
  • Adaptive sizing calculated
  • Duration: 8 seconds ✓

[16:49:45] 💼 PHASE 4: Trade Execution
  • Portfolio check: 2/5 slots available
  • Selected trades:
    1. SOL/USDT BUY 77% → $45.00 margin (Kelly)
    2. AVAX/USDT BUY 72% → $38.50 margin (Memory)
  • Orders executed: 2 ✓
  • SL applied: 2/2 ✓
  • Snapshots saved: 2/2 ✓
  • Duration: 28 seconds ✓

[16:50:13] 👁️ PHASE 5: Monitoring Active
  • Active positions: 4/5
  • Margin used: $165.00 / $500.00 (33%)
  • PnL session: +$45.50 (+9.1%)
  • Next cycle: 17:00:00 (9min 47s)

════════════════════════════════════════════════════════════
✅ Cycle #45 completed in 5min 13s
════════════════════════════════════════════════════════════
```

---

## 📚 Next Steps

- **04-ML-SYSTEM.md** - Deep dive XGBoost predictions
- **05-ADAPTIVE-SIZING.md** - Kelly Criterion e learning
- **06-RISK-MANAGEMENT.md** - SL, early exit, partial exits

---

**🎯 KEY TAKEAWAY**: Il ciclo 15 minuti bilancia efficienza (10 min idle) con reattività (analisi ogni 15 min), permettendo al sistema di cogliere opportunità senza overtrading.
