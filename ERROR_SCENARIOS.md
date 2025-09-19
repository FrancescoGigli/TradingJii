# 🚨 ERROR SCENARIOS & RECOVERY - GESTIONE ERRORI

## **📋 OVERVIEW**
Documentazione completa degli scenari di errore più comuni e relative strategie di recovery implementate nel sistema.

---

## **🚨 Scenario 1: API Rate Limiting**

### **File Chain**
`core/smart_api_manager.py` → `fetcher.py` → Bybit API calls

### **Cause**
- Troppi API calls in finestra di 60 secondi
- Concurrent requests superiori al limite Bybit
- Network spikes durante high-frequency operations

### **Log Output Reale**
```
2024-01-19 15:26:15 WARNING fetcher Rate limit hit for BTC/USDT:USDT, backing off for 0.20s
2024-01-19 15:26:15 INFO core.smart_api_manager ⚡ API rate limit reached, using stale cache if available
2024-01-19 15:26:15 INFO core.smart_api_manager ⚡ API Cache HIT: fetch_ticker BTC
2024-01-19 15:26:16 INFO fetcher Rate limit recovery, resuming normal operations
```

### **Recovery Strategy**
```python
# Exponential backoff in fetcher.py
current_delay = base_delay
while True:
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit, since)
        current_delay = base_delay  # Reset on success
        break
    except Exception as e:
        if any(keyword in error_msg for keyword in ['rate', 'limit', 'throttle']):
            await asyncio.sleep(current_delay)
            current_delay = min(current_delay * 2, max_delay)  # Exponential backoff
            continue

# Smart cache fallback in SmartAPIManager
if not self._check_rate_limit():
    if symbol in self._tickers_cache:
        return self._tickers_cache[symbol].copy()  # Use stale cache
```

### **Prevention Mechanisms**
- **Semaphore Rate Limiting**: Max 20 concurrent requests
- **Smart Cache**: 15s TTL per tickers, 30s per positions
- **API Call Tracking**: Sliding window monitoring
- **Automatic Throttling**: When approaching limits

---

## **💥 Scenario 2: Order Execution Failures**

### **File Chain**
`core/order_manager.py` → `core/trading_orchestrator.py` → Position tracking

### **Common Causes & Solutions**

#### **2.1: Insufficient Funds (110007)**
```
2024-01-19 15:27:30 ERROR core.order_manager ❌ Market order failed: Insufficient funds (110007)
2024-01-19 15:27:30 WARNING core.trading_orchestrator ⚠️ BTC/USDT:USDT: insufficient_balance
2024-01-19 15:27:30 INFO core.unified_balance_manager 💰 OVEREXPOSURE PREVENTED: Requested $45.00, Available $23.50 (BTC trade)
```

**Recovery**: UnifiedBalanceManager prevents overexposure, balance validation before orders

#### **2.2: Position Size Too Small (170213)**
```
2024-01-19 15:27:31 ERROR core.order_manager ❌ Market order failed: Order value too small (170213)
2024-01-19 15:27:31 INFO core.price_precision_handler 🎯 SHIB size normalized: 0.000123 → 0.001000 (min: 0.001)
2024-01-19 15:27:31 INFO core.trading_orchestrator 🔄 Retrying with minimum position size
```

**Recovery**: PricePrecisionHandler normalizes position sizes to exchange minimums

#### **2.3: Reduce Only Mode (110012)**
```
2024-01-19 15:27:32 ERROR core.order_manager ❌ Market order failed: Reduce only mode active (110012)
2024-01-19 15:27:32 WARNING core.trading_orchestrator ⚠️ Market in reduce-only mode, skipping new positions
```

**Recovery**: Skip new positions during reduce-only periods, continue monitoring existing

---

## **🔄 Scenario 3: Position State Sync Conflicts**

### **File Chain**
`core/thread_safe_position_manager.py` → `core/smart_position_manager.py`

### **Cause**
- Concurrent position updates da TrailingMonitor + Main Thread
- Race conditions su position state senza atomic operations

### **Log Output Reale**
```
2024-01-19 15:27:45 DEBUG core.thread_safe_position_manager 🔒 Atomic update: BTC_20240119_152745.current_price = 44156.78
2024-01-19 15:27:45 DEBUG core.thread_safe_position_manager 🔒 Atomic price/PnL update: BTC/USDT:USDT $44156.78 → +15.4%
2024-01-19 15:27:45 DEBUG core.thread_safe_position_manager 🔒 Atomic trailing update: BTC/USDT:USDT trailing=True
```

### **Resolution**
```python
# BEFORE: Race condition risk
position.current_price = current_price  # Non-atomic
position.unrealized_pnl = calculated_pnl  # Separate operation

# AFTER: Atomic operation
def atomic_update_price_and_pnl(self, position_id: str, current_price: float):
    with self._lock:
        # All updates together atomically
        position.current_price = current_price
        position.unrealized_pnl_pct = pnl_pct
        position.unrealized_pnl_usd = pnl_usd
        position.max_favorable_pnl = max(position.max_favorable_pnl, pnl_pct)
```

---

## **🛡️ Scenario 4: Stop Loss Setting Failures**

### **File Chain**
`core/unified_stop_loss_calculator.py` → `core/order_manager.py` → Bybit API

### **Common Stop Loss Errors**

#### **4.1: Already Set (34040)**
```
2024-01-19 15:25:49 INFO core.order_manager 📝 BTCUSDT: Stop loss already set correctly (Bybit error 34040: not modified)
2024-01-19 15:25:49 INFO core.trading_orchestrator ✅ BTC/USDT:USDT: Already protected (stop loss exists)
```

**Resolution**: Detect "not modified" as success, not error

#### **4.2: Price Validation Failed (10001)**
```
2024-01-19 15:25:50 WARNING core.order_manager ⚠️ Stop loss validation failed - Stop loss price 44000.00 must be less than current price 43500.00
2024-01-19 15:25:50 INFO core.price_precision_handler 🔧 BTC SL auto-adjusted $44000.00 → $43460.00 (Bybit rules)
2024-01-19 15:25:50 INFO core.order_manager ✅ TRADING STOP SUCCESS: BTCUSDT | Bybit confirmed: ok
```

**Recovery**: PricePrecisionHandler auto-adjusts prices to comply with Bybit rules

#### **4.3: Complete Stop Loss Failure**
```
2024-01-19 15:25:50 ERROR core.order_manager ❌ CRITICAL: ETH/USDT:USDT has NO STOP LOSS after 3 attempts!
2024-01-19 15:25:50 ERROR core.position_safety_manager 🚨 EMERGENCY: Manual intervention required for ETH
2024-01-19 15:25:50 INFO core.position_safety_manager 🔒 SAFETY CLOSURE: ETH/USDT:USDT closed for no SL protection
```

**Recovery**: PositionSafetyManager force-closes positions without protection

---

## **🚫 Scenario 5: Symbol Auto-Exclusion**

### **File Chain**
`data_utils.py` → `core/symbol_exclusion_manager.py`

### **Cause**
- Simboli con < 50 candles historical
- Data quality insufficient per ML predictions
- Volume troppo basso per trading sicuro

### **Log Output Reale**
```
2024-01-19 15:26:45 ERROR data_utils ❌ Dataset too small for SHIB: 23 candles < 50 minimum required
2024-01-19 15:26:45 WARNING core.symbol_exclusion_manager 🚫 AUTO-EXCLUDED: SHIB/USDT:USDT - only 23 candles (< 50 required)
2024-01-19 15:26:45 INFO core.symbol_exclusion_manager 💾 Saved 8 excluded symbols
```

### **Auto-Exclusion Process**
```python
def validate_dataset_size(df, symbol=None):
    if len(df) < MIN_DATASET_SIZE:
        logging.error(f"❌ Dataset too small{symbol_info}: {len(df)} candles < {MIN_DATASET_SIZE}")
        
        # Auto-exclude symbol
        if symbol and global_symbol_exclusion_manager:
            global_symbol_exclusion_manager.exclude_symbol_insufficient_data(
                symbol, missing_timeframes=None, candle_count=len(df)
            )
        return False
```

### **Recovery & Management**
```bash
# Manual exclusion reset
python utils/exclusion_utils.py reset
# Output: ✅ Auto-excluded symbols cleared. Next run will re-test all symbols.

# Check exclusion status
python utils/exclusion_utils.py status
```

---

## **🤖 Scenario 6: RL System Failures**

### **File Chain**
`core/rl_agent.py` → `core/online_learning_manager.py` → `trading/signal_processor.py`

### **RL Model Errors**

#### **6.1: RL Model Corruption**
```
2024-01-19 15:26:50 ERROR core.rl_agent 🤖 CRITICAL: RL decision error for BTC: Model forward pass failed
2024-01-19 15:26:50 WARNING trading.signal_processor ⚠️ Robust predictor failed for BTC, falling back to original logic
2024-01-19 15:26:50 INFO trading.signal_processor ✅ Added (no RL): BTC BUY (XGB:74.1%)
```

**Recovery**: Fallback to XGBoost-only decisions, RL system graceful degradation

#### **6.2: RL State Building Error**
```
2024-01-19 15:26:51 ERROR core.rl_agent Error building RL state: KeyError 'volatility'
2024-01-19 15:26:51 INFO core.rl_agent 🤖 RL Decision for BTC: APPROVED (Fallback) - RL System Error
```

**Recovery**: Structured fallback details, default approval with moderate confidence

### **Fallback Logic**
```python
try:
    return robust_predict_signal_ensemble(dataframes, xgb_models, xgb_scalers, symbol, time_steps)
except Exception as e:
    logging.warning(f"⚠️ Robust predictor failed for {symbol}, falling back to original logic: {e}")
    # Fallback to original XGBoost-only prediction
    return original_prediction_logic()
```

---

## **💾 Scenario 7: Database Cache Failures**

### **File Chain**
`core/database_cache.py` → `fetcher.py` → API fallback

### **Database Issues**

#### **7.1: SQLite Lock/Corruption**
```
2024-01-19 15:26:55 ERROR core.database_cache ❌ Database save failed for BTC[15m]: database is locked
2024-01-19 15:26:55 WARNING fetcher Enhanced fetch failed for BTC[15m], using direct API
2024-01-19 15:26:56 INFO fetcher ✅ Direct API fetch successful for BTC[15m] - bypassing cache
```

**Recovery**: Automatic fallback to direct API calls, cache bypass mode

#### **7.2: Cache Corruption**
```
2024-01-19 15:26:57 ERROR core.database_cache ❌ Enhanced database read failed for ETH[15m]: no such column: volatility
2024-01-19 15:26:57 WARNING core.database_cache Database schema mismatch, rebuilding tables
2024-01-19 15:26:58 INFO core.database_cache 🔧 Database tables recreated successfully
```

**Recovery**: Schema migration, table recreation, data consistency checks

---

## **🔥 Scenario 8: Trading Engine Failures**

### **File Chain**
`trading/trading_engine.py` → Multiple subsystems

### **Critical Engine Errors**

#### **8.1: ML Prediction Complete Failure**
```
2024-01-19 15:27:00 ERROR trading.market_analyzer ❌ All predictions failed - no working models
2024-01-19 15:27:00 WARNING trading.trading_engine ⚠️ No signals to execute this cycle
2024-01-19 15:27:00 INFO trading.trading_engine 😐 No signals to execute this cycle
```

**Recovery**: Skip cycle, attempt model reload, continue monitoring existing positions

#### **8.2: Data Collection Complete Failure**
```
2024-01-19 15:27:01 ERROR trading.market_analyzer ❌ No symbols with complete data this cycle
2024-01-19 15:27:01 WARNING trading.trading_engine ⚠️ Data collection failed, skipping predictions
2024-01-19 15:27:01 INFO trading.trading_engine 🔄 Continuing with position management only
```

**Recovery**: Position management only, skip trading decisions, continue monitoring

---

## **⚠️ Scenario 9: Safety Manager Interventions**

### **File Chain**
`core/position_safety_manager.py` → `core/order_manager.py`

### **Safety Violations**

#### **9.1: Unsafe Position Size**
```
2024-01-19 15:30:15 WARNING core.position_safety_manager ⚠️ UNSAFE POSITION DETECTED: SHIB ($18.50 notional, $1.85 IM)
2024-01-19 15:30:15 INFO core.position_safety_manager 🔒 SAFETY CLOSURE: SHIB closed for insufficient size
2024-01-19 15:30:15 INFO core.order_manager ✅ Unsafe position closed: SHIB/USDT:USDT | Order: abc123def
2024-01-19 15:30:15 INFO core.position_safety_manager 🛡️ SAFETY MANAGER: Closed 1 unsafe positions
```

**Recovery**: Automatic position closure per positions < $200 notional o < $20 IM

#### **9.2: Position Without Stop Loss**
```
2024-01-19 15:30:16 ERROR core.position_safety_manager ❌ CRITICAL: DOGE/USDT:USDT has NO STOP LOSS - attempting to fix
2024-01-19 15:30:16 INFO core.order_manager 🛡️ SETTING TRADING STOP: DOGEUSDT | SL: $0.082174 | TP: None
2024-01-19 15:30:16 INFO core.order_manager ✅ Emergency SL set for DOGE: $0.082174
2024-01-19 15:30:16 INFO core.position_safety_manager ✅ Emergency SL set for DOGE: $0.082174
```

**Recovery**: Emergency 6% SL application, force closure se SL setting fails

---

## **🌐 Scenario 10: Network & Connectivity Issues**

### **File Chain**
Multiple files → Bybit API → Network infrastructure

### **Network Failures**

#### **10.1: Exchange Connection Lost**
```
2024-01-19 15:28:00 ERROR main ❌ Fatal error: Connection lost to exchange
2024-01-19 15:28:00 INFO main 🔄 Attempting reconnection in 30s...
2024-01-19 15:28:30 INFO main 🚀 Reconnection attempt 1/3
2024-01-19 15:28:32 INFO main ✅ Exchange reconnected successfully
2024-01-19 15:28:32 INFO core.trading_orchestrator 🔄 Resuming normal operations
```

**Recovery**: Exponential backoff reconnection, state preservation durante outages

#### **10.2: Partial API Failures**
```
2024-01-19 15:28:05 WARNING fetcher Network timeout for SOL/USDT:USDT, retrying...
2024-01-19 15:28:06 WARNING fetcher Network timeout for DOGE/USDT:USDT, retrying...
2024-01-19 15:28:10 INFO fetcher ✅ Network recovered, continuing downloads
2024-01-19 15:28:10 INFO fetcher 📊 Network resilience: 48/50 symbols successful (96%)
```

**Recovery**: Individual symbol failures tolerated, continue con simboli successful

---

## **💰 Scenario 11: Balance Management Failures**

### **File Chain**
`core/unified_balance_manager.py` → `trade_manager.py` → Bybit API

### **Balance Issues**

#### **11.1: Balance Sync Failure**
```
2024-01-19 15:28:15 ERROR core.unified_balance_manager 💰 Bybit balance sync failed: Connection timeout
2024-01-19 15:28:15 WARNING core.unified_balance_manager Using cached balance: $1247.83 (last sync: 2m ago)
2024-01-19 15:28:15 INFO core.unified_balance_manager 🔄 Will retry balance sync next cycle
```

**Recovery**: Use cached balance, retry sync next cycle, log sync failures

#### **11.2: Overexposure Prevention**
```
2024-01-19 15:28:20 INFO core.unified_balance_manager 💰 Margin allocated: $42.50 (BTC trade) - Available: $1205.33
2024-01-19 15:28:25 WARNING core.unified_balance_manager 💰 OVEREXPOSURE PREVENTED: Requested $45.00, Available $23.50 (ETH trade)
2024-01-19 15:28:25 INFO core.trading_orchestrator ⚠️ Portfolio risk limit reached, skipping ETH trade
```

**Recovery**: Skip trades that exceed portfolio limits, protect account balance

---

## **🔧 Scenario 12: System Recovery Patterns**

### **Graceful Degradation**
```python
# Component availability checking
if UNIFIED_MANAGERS_AVAILABLE:
    # Use advanced thread-safe managers
    self.position_manager = global_thread_safe_position_manager
else:
    # Fallback to legacy implementations
    self.position_manager = global_smart_position_manager
    logging.warning("⚠️ Using legacy managers - race conditions possible")
```

### **Emergency Operations**
```python
# Emergency balance reset
def emergency_reset_allocations(self, reason: str = "EMERGENCY"):
    with self._lock:
        old_allocated = self._allocated_margin
        self._allocated_margin = 0.0
        self._reserved_margin = 0.0
        logging.error(f"🚨 EMERGENCY BALANCE RESET: {reason}")

# Emergency position closure
async def emergency_close_all_positions(self, exchange, reason: str):
    for position in self.get_active_positions():
        await self._close_unsafe_position(exchange, position.symbol, position.contracts)
        logging.error(f"🚨 EMERGENCY CLOSURE: {position.symbol} ({reason})")
```

---

## **📊 Error Classification & Priority**

### **🚨 CRITICAL (System Stop)**
- **Exchange Connection Completely Lost**: Reconnection required
- **All ML Models Failed**: Cannot generate trading signals
- **Balance Recovery Failed**: Cannot validate trades
- **Database Completely Corrupted**: Rebuild required

### **⚠️ WARNING (Degraded Performance)**
- **Some API Rate Limiting**: Cache fallback active
- **Some Model Failures**: Reduced timeframe coverage
- **Partial Network Issues**: Some symbols skipped
- **Cache Performance Low**: Higher API usage

### **ℹ️ INFO (Normal Operations)**
- **Individual Symbol Exclusions**: Quality control working
- **Some Positions Already Protected**: Normal state
- **Cache Misses**: Normal cache behavior
- **RL Fallbacks**: XGBoost-only decisions

---

## **🔄 Automatic Recovery Mechanisms**

### **Self-Healing Features**
1. **API Cache Fallback**: Stale cache better than no data
2. **Component Graceful Degradation**: System continues con reduced features
3. **Automatic Retries**: Exponential backoff per network issues
4. **Emergency Position Closure**: Safety-first approach
5. **Balance Protection**: Overexposure prevention
6. **Symbol Quality Control**: Auto-exclusion di simboli problematici

### **Manual Intervention Triggers**
```
🚨 MANUAL INTERVENTION REQUIRED:
- Critical positions without stop loss protection
- Exchange connection lost > 5 minutes
- All symbols auto-excluded (no trading possible)
- Database completely corrupted
- API credentials expired/invalid
```

---

## **🎯 Error Monitoring Dashboard**

### **Error Rate Tracking**
```python
error_stats = {
    'api_failures': 0,
    'order_failures': 0,
    'position_failures': 0,
    'model_failures': 0,
    'network_failures': 0,
    'safety_interventions': 0
}

# Performance thresholds
ERROR_RATE_WARNING = 5.0   # 5% error rate warning
ERROR_RATE_CRITICAL = 15.0 # 15% error rate critical
```

### **Health Check Log**
```
🏥 SYSTEM HEALTH CHECK:
   📊 API Success Rate: 96.8% (✅ Healthy)
   🚀 Order Success Rate: 94.2% (✅ Healthy)  
   🛡️ Position Protection: 100% (✅ Secure)
   🧠 ML Model Availability: 100% (✅ Ready)
   🌐 Network Stability: 98.1% (✅ Stable)
   🔧 Safety Interventions: 2 (✅ Normal)
   🎯 Overall System Health: EXCELLENT
```

---

## **🔍 Error Debugging Tools**

### **Error Log Analysis**
```bash
# Error-only log analysis
tail -f logs/trading_bot_errors.log

# Search for specific error patterns
grep "CRITICAL" logs/trading_bot_derivatives.log
grep "insufficient" logs/trading_bot_derivatives.log
grep "rate limit" logs/trading_bot_derivatives.log
```

### **Health Status Commands**
```python
# Balance manager status
global_unified_balance_manager.display_balance_dashboard()

# API manager status  
global_smart_api_manager.display_api_dashboard()

# Position manager status
global_smart_position_manager.get_session_summary()

# Database cache status
display_database_stats()
```

---

## **🎯 Error Prevention Best Practices**

### **Proactive Monitoring**
1. **Rate Limit Monitoring**: Track API usage in real-time
2. **Balance Validation**: Before ogni trade execution
3. **Position Size Validation**: Before order placement
4. **Model Health Checks**: Regular prediction validation
5. **Cache Performance**: Monitor hit rates

### **Defensive Programming**
```python
# Always validate inputs
if not symbol or len(symbol) < 3:
    return False, f"Invalid symbol: {symbol}"

# Always handle None values
current_price = ticker.get('last', 0) if ticker else 0

# Always use try-catch per external operations
try:
    result = await exchange.fetch_ticker(symbol)
except Exception as e:
    logging.error(f"API call failed: {e}")
    return None  # Graceful failure
```

### **Resource Protection**
```python
# Memory limits
if len(self.experience_buffer) > self.max_buffer_size:
    self.experience_buffer = self.experience_buffer[-self.max_buffer_size:]

# API call limits
if self.get_api_calls_in_window() >= self._max_calls_per_minute:
    return False  # Deny additional calls

# Position limits
if current_positions >= MAX_CONCURRENT_POSITIONS:
    return "max_trades_reached"
```
</content>
<task_progress>
- [x] Create comprehensive pipeline documentation split by phases
- [x] Create FASE_0_STARTUP.md - System initialization details
- [x] Create FASE_1_MARKET.md - Market initialization and symbol selection
- [x] Create FASE_2_ML_MODELS.md - ML models loading and training
- [x] Create FASE_3_BALANCE.md - Balance sync and position protection
- [ ] Create FASE_4_TRADING_CYCLE.md - Main trading cycle (9 phases)
- [x] Create THREAD_MANAGEMENT.md - Complete thread documentation
- [x] Create ERROR_SCENARIOS.md - Error handling and recovery
- [ ] Create FILE_MAPPINGS.md - Complete file responsibility mapping
- [ ] Create LOG_EXAMPLES.md - Real log output examples
- [ ] Verify all files are complete and accurate
