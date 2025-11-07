# 🛡️ 07 - Risk Management

Il **Risk Management** è fondamentale per proteggere il capitale. Questo documento spiega come il bot gestisce il rischio a ogni livello.

---

## 📋 Indice

1. [Filosofia Risk Management](#filosofia-risk-management)
2. [Stop Loss Strategy](#stop-loss-strategy)
3. [Trailing Stops](#trailing-stops)
4. [Portfolio Limits](#portfolio-limits)
5. [Early Exit System](#early-exit-system)
6. [Position Sizing](#position-sizing)
7. [Emergency Controls](#emergency-controls)

---

## 💭 Filosofia Risk Management

### **Principi Chiave:**

```
1. CAPITAL PRESERVATION FIRST
   └─ Proteggere capitale > Massimizzare profitti

2. RISK PER TRADE LIMITATO
   └─ Max -5% prezzo = -50% ROE (con 10x leva)

3. PORTFOLIO EXPOSURE CONTROLLED
   └─ Max 20% wallet at risk simultaneously

4. DYNAMIC RISK ADJUSTMENT
   └─ Trailing protegge profitti automaticamente

5. AUTOMATIC SAFETY CHECKS
   └─ System chiude posizioni unsafe
```

---

## 🛑 Stop Loss Strategy

### **Fixed Stop Loss: -5% prezzo**

```python
# Configurazione (config.py)
SL_USE_FIXED = True          # Use fixed % SL
SL_FIXED_PCT = 0.03          # 3% stop loss
LEVERAGE = 10                # 10x leverage

# Calcolo impact
Price SL: -3%
ROE Impact: -3% × 10x = -30% margin loss
```

**Perché -5%?**

```
PROBLEMA con SL -10% (vecchio sistema):
├─ -10% prezzo = -100% ROE
├─ Margin liquidato completamente
└─ Rischio troppo alto!

SOLUZIONE con SL -5%:
├─ -5% prezzo = -50% ROE
├─ Margin parziale preservato
├─ Rischio controllato
└─ Più trade possibili prima di bust
```

### **Adaptive Stop Loss (basato su confidence):**

```python
SL_ADAPTIVE_ENABLED = True

# Se enabled:
SL_LOW_CONFIDENCE = 0.025    # 2.5% SL per confidence <70%
SL_MED_CONFIDENCE = 0.03     # 3.0% SL per confidence 70-80%
SL_HIGH_CONFIDENCE = 0.035   # 3.5% SL per confidence >80%

# Logic:
if confidence < 0.70:
    sl_pct = 0.025  # Più tight per protezione
elif confidence < 0.80:
    sl_pct = 0.03   # Standard
else:
    sl_pct = 0.035  # Più breathing room per high conf
```

### **Applicazione Stop Loss:**

```python
async def execute_new_trade(exchange, signal_data, market_data):
    """Execute trade with SL protection"""
    
    # 1. Execute market order
    await place_market_order(exchange, symbol, side, size)
    
    # 2. Calculate SL price
    if SL_ADAPTIVE_ENABLED:
        sl_pct = get_adaptive_sl_pct(confidence)
    else:
        sl_pct = SL_FIXED_PCT
    
    if side == 'buy':
        sl_price = entry_price * (1 - sl_pct)  # -5% per LONG
    else:
        sl_price = entry_price * (1 + sl_pct)  # +5% per SHORT
    
    # 3. Apply SL on Bybit
    await set_trading_stop(exchange, symbol, stop_loss=sl_price)
    
    # 4. Log actual risk
    margin_loss_pct = sl_pct * LEVERAGE
    logging.info(f"🛡️ SL set: {sl_pct*100:.1f}% price = {margin_loss_pct:.0f}% ROE risk")
```

**Esempio pratico:**

```
Symbol: SOL/USDT:USDT
Entry: $100.00
Side: LONG (BUY)
Leverage: 10x
Margin: $200

Stop Loss Calculation:
├─ SL price: $100 × (1 - 0.05) = $95.00
├─ Price change: -5%
├─ ROE impact: -5% × 10x = -50%
└─ Margin loss: $200 × 0.50 = $100

If hit SL:
├─ Posizione chiusa @ $95
├─ Loss: $100 margin
├─ Remaining: $100 margin
└─ Balance: -$100
```

---

## 🎪 Trailing Stops

### **Dynamic Profit Protection:**

```python
# Configuration
TRAILING_ENABLED = True              # Enable trailing
TRAILING_TRIGGER_PCT = 0.015         # +1.5% price activation
TRAILING_DISTANCE_ROE_OPTIMAL = 0.10 # Protect last 10% ROE
TRAILING_UPDATE_INTERVAL = 30        # Check every 30s
```

### **Come Funziona:**

```
Stage 1: Position Opens
├─ Entry: $100
├─ Initial SL: $95 (-5%)
└─ Trailing: NOT ACTIVE (waiting trigger)

Stage 2: Price Goes Up (+1.5%)
├─ Current: $101.50 (+1.5% = +15% ROE)
├─ Trigger hit: +15% ROE ≥ +15% trigger
└─ Trailing: ACTIVATED ✅

Stage 3: Trailing Active
├─ Current price: $105 (+5% = +50% ROE)
├─ Protect last 10% ROE = 40% ROE safe
├─ New SL: Price for +40% ROE
└─ SL moves up to $104 (+4% from entry)

Stage 4: Price Drops Back
├─ Price drops to $104.50
├─ SL still @ $104 (doesn't move down)
└─ Still protecting +40% ROE ✅

Stage 5: SL Hit
├─ Price hits $104
├─ Position closes
├─ Profit: +4% price = +40% ROE
└─ Win secured! 🎉
```

### **Trailing Update Logic:**

```python
async def update_trailing_stops(exchange):
    """Update trailing stops for all positions"""
    
    for position in active_positions:
        # 1. Check if trailing should activate
        current_roe = calculate_roe(position, current_price)
        
        if not position.trailing_active:
            if current_roe >= TRAILING_TRIGGER_PCT * LEVERAGE * 100:
                position.trailing_active = True
                logging.info(f"🎪 {symbol}: Trailing ACTIVATED @ +{current_roe:.0f}% ROE")
        
        # 2. If active, check if SL should update
        if position.trailing_active:
            # Calculate new SL to protect profit
            target_roe = current_roe - TRAILING_DISTANCE_ROE_OPTIMAL * 100
            
            # Only update if significant improvement
            if target_roe > position.current_sl_roe + 12:  # 12% ROE gap
                new_sl_price = calculate_price_for_roe(position, target_roe)
                
                # Update SL on Bybit
                await set_trading_stop(exchange, symbol, stop_loss=new_sl_price)
                
                position.current_sl_roe = target_roe
                logging.info(f"🎪 {symbol}: SL moved to +{target_roe:.0f}% ROE")
```

**Performance Impact:**

```
WITHOUT Trailing:
├─ Position: SOL +50% ROE
├─ Price reverses
├─ Hit initial SL: -50% ROE
└─ Net: -50% ❌

WITH Trailing:
├─ Position: SOL +50% ROE
├─ Trailing activates @ +15% ROE
├─ SL moves to +40% ROE
├─ Price reverses
├─ Hit trailing SL: +40% ROE
└─ Net: +40% ✅
```

---

## 🎯 Portfolio Limits

### **Max Concurrent Positions:**

```python
MAX_CONCURRENT_POSITIONS = 5  # Max 5 posizioni simultanee

# Con Adaptive Sizing:
ADAPTIVE_WALLET_BLOCKS = 5    # Must match max positions

# Logic:
if len(active_positions) >= MAX_CONCURRENT_POSITIONS:
    skip_new_signals()
```

### **Portfolio Risk Limit:**

```python
ADAPTIVE_RISK_MAX_PCT = 0.20  # Max 20% wallet at total risk

# Calculation:
total_at_risk = sum(position.margin * 0.50 for position in active_positions)
wallet_risk_pct = total_at_risk / wallet_balance

if wallet_risk_pct > ADAPTIVE_RISK_MAX_PCT:
    logging.warning("⚠️ Portfolio risk limit exceeded!")
    skip_new_signals()
```

**Esempio:**

```
Wallet: $1000
Max risk: 20% = $200

Positions:
├─ SOL:  $200 margin × 50% risk = $100 at risk
├─ AVAX: $200 margin × 50% risk = $100 at risk
├─ Total at risk: $200 (20% of wallet)
└─ LIMIT REACHED: No new positions allowed
```

### **Balance Check Before Trade:**

```python
# Pre-execution validation
available_balance = wallet_balance - used_margin

if margin_needed > available_balance:
    logging.warning(f"⚠️ Insufficient balance: need ${margin_needed}, have ${available_balance}")
    skip_trade()
```

---

## 🚨 Early Exit System

### **Fast Reversal Detection (15 min):**

```python
EARLY_EXIT_FAST_REVERSAL_ENABLED = True
EARLY_EXIT_FAST_TIME_MINUTES = 15
EARLY_EXIT_FAST_DROP_ROE = -15  # Exit if -15% ROE in 15min

# Logic:
if position.age_minutes < 15:
    if current_roe < -15:
        logging.warning(f"🚨 {symbol}: Fast reversal @ {current_roe:.0f}% ROE")
        await close_position(exchange, position, reason="EARLY_EXIT_FAST")
```

### **Immediate Reversal Detection (5 min):**

```python
EARLY_EXIT_IMMEDIATE_ENABLED = True
EARLY_EXIT_IMMEDIATE_TIME_MINUTES = 5
EARLY_EXIT_IMMEDIATE_DROP_ROE = -10  # Exit if -10% ROE in 5min

# Even more aggressive protection
```

### **Persistent Weakness Detection (60 min):**

```python
EARLY_EXIT_PERSISTENT_ENABLED = True
EARLY_EXIT_PERSISTENT_TIME_MINUTES = 60
EARLY_EXIT_PERSISTENT_DROP_ROE = -5  # Exit if stays -5% ROE for 60min

# Cuts losses on weak positions
```

**Rationale:**

```
SCENARIO: ML predicts BUY, ma mercato immediately reverses

WITHOUT Early Exit:
├─ Entry @ $100
├─ Drops to $90 in 10 min (-10% price = -100% ROE)
├─ Waits for SL @ $95 (-5%)
└─ Hit SL: -50% ROE loss

WITH Early Exit:
├─ Entry @ $100
├─ Drops to $97 in 5 min (-3% price = -30% ROE)
├─ Early exit triggers @ -10% ROE
└─ Exit @ $97: -30% ROE loss ✅ (saved 20%)
```

---

## 📊 Position Sizing

### **Risk-Based Sizing:**

```python
def calculate_position_levels(market_data, side, confidence, balance):
    """
    Calculate position size with risk considerations
    """
    # 1. Base margin (from adaptive or fixed)
    if adaptive_enabled:
        margin = calculate_adaptive_margin(symbol, balance)
    else:
        margin = get_fixed_margin(confidence)  # 15-25 range
    
    # 2. Adjust for volatility
    if market_data.volatility > HIGH_VOLATILITY_THRESHOLD:
        margin *= 0.8  # Reduce size in volatile markets
    
    # 3. Adjust for trend strength (ADX)
    if market_data.adx < 20:  # Weak trend
        margin *= 0.9  # Reduce size
    
    # 4. Portfolio check
    used_margin = sum(pos.margin for pos in active_positions)
    available = balance - used_margin
    
    if margin > available:
        margin = available * 0.98  # Use max 98% available
    
    # 5. Absolute limits
    margin = max(MARGIN_MIN, min(margin, MARGIN_MAX))
    
    return margin
```

### **Kelly Criterion (Advanced):**

```python
# Optional: Kelly-based sizing
def kelly_criterion(win_rate, avg_win, avg_loss):
    """
    Optimal position size based on edge
    
    f = (win_rate × avg_win - (1 - win_rate) × avg_loss) / avg_win
    """
    if avg_win <= 0:
        return 0
    
    edge = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    kelly_pct = edge / avg_win
    
    # Use fractional Kelly (0.25x) for safety
    return kelly_pct * 0.25
```

---

## 🆘 Emergency Controls

### **Auto Safety Checks:**

```python
async def check_and_close_unsafe_positions(exchange):
    """
    Automatic safety system
    """
    for position in active_positions:
        # 1. Check for extreme loss (beyond SL somehow)
        if position.unrealized_pnl_pct < -60:
            logging.error(f"🆘 {symbol}: EMERGENCY CLOSE @ {pnl:.0f}% ROE")
            await emergency_close(exchange, position)
        
        # 2. Check for stuck positions (no SL set)
        if position.stop_loss is None or position.stop_loss == 0:
            logging.warning(f"⚠️ {symbol}: Missing SL - applying now")
            await fix_stop_loss(exchange, position)
        
        # 3. Check for age (stale positions - over 24h)
        age_hours = (datetime.now() - position.entry_time).total_seconds() / 3600
        if age_hours > 24 and position.unrealized_pnl_pct < 0:
            logging.warning(f"⏰ {symbol}: Stale losing position (24h+)")
            await close_position(exchange, position, reason="STALE")
```

### **Manual Emergency Close:**

```python
# Available commands (if needed)
def emergency_close_all_positions():
    """Close ALL positions immediately"""
    for position in active_positions:
        await close_position(exchange, position, reason="EMERGENCY")

def emergency_stop_bot():
    """Stop bot completely"""
    logging.critical("🆘 EMERGENCY STOP activated")
    sys.exit(0)
```

---

## ✅ Risk Management Checklist

### **Before Trading:**
- [ ] Stop Loss configurato (-5% o adaptive)
- [ ] Trailing stops abilitato
- [ ] Max positions limit (5)
- [ ] Portfolio risk limit (20%)
- [ ] Early exit system enabled

### **During Trading:**
- [ ] Monitor dashboard regolarmente
- [ ] Check SL applicati su tutte le posizioni
- [ ] Verify trailing activation on profitable positions
- [ ] Watch for emergency alerts

### **After Session:**
- [ ] Review closed positions
- [ ] Analyze win rate per symbol
- [ ] Check adaptive sizing performance
- [ ] Adjust config se necessario

---

## 📈 Performance Metrics

### **Risk-Adjusted Returns:**

```python
# Sharpe Ratio
sharpe_ratio = (avg_return - risk_free_rate) / std_dev_returns

# Max Drawdown
max_drawdown = max(peak_balance - current_balance) / peak_balance

# Risk/Reward Ratio
avg_win = sum(wins) / len(wins)
avg_loss = sum(losses) / len(losses)
risk_reward = avg_win / abs(avg_loss)
```

### **Target Metrics:**

```
✅ Good Risk Management:
├─ Sharpe Ratio: > 1.5
├─ Max Drawdown: < 15%
├─ Risk/Reward: > 2.0
├─ Win Rate: > 55%
└─ Recovery Factor: > 3.0

❌ Poor Risk Management:
├─ Sharpe Ratio: < 0.8
├─ Max Drawdown: > 25%
├─ Risk/Reward: < 1.0
├─ Win Rate: < 45%
└─ Recovery Factor: < 1.5
```

---

## 🎓 Best Practices

### **1. Start Conservative:**

```python
# Initial config (first weeks)
SL_FIXED_PCT = 0.04              # -4% SL (tight)
MAX_CONCURRENT_POSITIONS = 3     # Only 3 positions
ADAPTIVE_WALLET_BLOCKS = 10      # Smaller sizes
```

### **2. Scale Gradually:**

```python
# After profitable weeks
SL_FIXED_PCT = 0.05              # -5% SL (balanced)
MAX_CONCURRENT_POSITIONS = 5     # Full 5 positions
ADAPTIVE_WALLET_BLOCKS = 5       # Standard sizes
```

### **3. Monitor Daily:**

```
Daily checks:
├─ Balance evolution
├─ Open positions (count & PnL)
├─ Recent closed trades
├─ Adaptive sizing stats
└─ System health (no errors)
```

### **4. Review Weekly:**

```
Weekly review:
├─ Overall PnL (%)
├─ Win rate per symbol
├─ Best/worst performers
├─ Adjust excluded symbols
└─ Fine-tune config
```

---

## ⚠️ Common Mistakes

### **1. Disabling Stop Loss:**

```
❌ NEVER do this:
SL_USE_FIXED = False  # EXTREMELY DANGEROUS!

✅ Always keep SL active:
SL_USE_FIXED = True
SL_FIXED_PCT = 0.05  # Or higher for safety
```

### **2. Over-leveraging:**

```
❌ AVOID:
MAX_CONCURRENT_POSITIONS = 20  # Too many!
LEVERAGE = 20                  # Too high!

✅ Keep reasonable:
MAX_CONCURRENT_POSITIONS = 5   # Manageable
LEVERAGE = 10                  # Balanced risk
```

### **3. Ignoring Drawdowns:**

```
❌ Don't ignore:
- Multiple consecutive losses
- Increasing drawdown
- Low win rate

✅ Take action:
- Reduce position sizes
- Pause trading
- Review strategy
```

### **4. Emotional Trading:**

```
❌ Manual interventions based on fear/greed
✅ Trust the system, follow the rules
```

---

**Conclusione:** Il Risk Management è **NON NEGOZIABILE**. Protegge il capitale e permette longevità nel trading.

---

**Indice:** [← Torna all'indice](README.md)
