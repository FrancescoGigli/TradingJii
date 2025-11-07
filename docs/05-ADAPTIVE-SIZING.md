# 📖 05 - Adaptive Position Sizing

> **Kelly Criterion + Learning System**

---

## 🎯 Overview Sistema Adaptive

Il sistema **Adaptive Position Sizing** dinamicamente aggiusta le size delle posizioni basandosi su **performance reali**, utilizzando il **Kelly Criterion** quando disponibile storico sufficiente.

**Filosofia**: *"Premia chi ti fa guadagnare, congela chi ti fa perdere."*

```
ADAPTIVE SIZING FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WALLET EQUITY ($500)
  ↓
DIVIDE IN 5 BLOCKS ($100 each)
  ↓
FOR EACH SIGNAL:
  ├─ Check Memory
  │  ├─ New Symbol → Base Size (50% block = $50)
  │  ├─ 10+ Trades → Kelly Criterion Sizing
  │  └─ <10 Trades → Memory-based Size
  │
  ├─ Apply Multipliers
  │  ├─ Winners → Size grows with gains
  │  └─ Losers → BLOCKED 3 cycles
  │
  └─ Validate Risk
     └─ Max 20% wallet at risk total
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 📊 Wallet Blocks System

### **Concetto Base**

```python
ADAPTIVE_WALLET_BLOCKS = 5  # Divide wallet in 5 parts

# Example con $500 wallet:
Wallet: $500
Blocks: 5
Block Value: $500 / 5 = $100

# First cycle (prudent):
Base Size = $100 × 0.5 = $50 margin per position
Max Positions = 5 (one per block)
```

### **Perché 5 Blocks?**

- **Diversificazione**: Max 5 posizioni simultanee
- **Risk Control**: Ogni block = 20% wallet
- **Flexibility**: Permette sizing dinamico entro limiti
- **Kelly-compatible**: Si integra con Kelly Criterion

---

## 🧮 Kelly Criterion Integration

### **Formula Kelly**

```
f* = (p × b - q) / b

Dove:
  f* = frazione wallet da rischiare (Kelly fraction)
  p  = probabilità vittoria (win rate)
  q  = probabilità perdita (1 - p)
  b  = payoff ratio (avg_win / avg_loss)
```

### **Implementazione**

```python
def _calculate_kelly_size(memory, wallet_equity, base_size):
    """
    Kelly Criterion per optimal sizing
    
    Richiede: 10+ trades history
    """
    if memory.total_trades < 10:
        return base_size  # Not enough data
    
    # 1. Calculate win rate
    win_rate = memory.wins / memory.total_trades
    loss_rate = 1 - win_rate
    
    # 2. Expected values (with 5x leverage)
    avg_win_roe = 60.0   # +60% ROE target (TP)
    avg_loss_roe = 25.0  # -25% ROE (SL at -5% price)
    
    # 3. Add costs
    costs = calculate_round_trip_cost()  # ~3% ROE
    effective_win = avg_win_roe - costs
    effective_loss = avg_loss_roe + costs
    
    # 4. Payoff ratio
    payoff_ratio = effective_win / effective_loss
    
    # 5. Kelly formula
    kelly_fraction = (win_rate * payoff_ratio - loss_rate) / payoff_ratio
    
    # 6. Conservative Kelly (25% of full Kelly)
    conservative_kelly = kelly_fraction * 0.25
    
    # 7. Clamp to reasonable range
    conservative_kelly = max(0.05, min(conservative_kelly, 0.30))
    
    # 8. Calculate size
    kelly_size = wallet_equity * conservative_kelly
    
    return kelly_size
```

### **Esempio Calco Kelly**

```
Symbol: SOL/USDT
History: 15 trades (10W / 5L)

1. Win Rate:
   p = 10 / 15 = 0.667 (66.7%)
   q = 5 / 15 = 0.333 (33.3%)

2. Expected ROE:
   Win:  +60% - 3% costs = +57%
   Loss: -25% - 3% costs = -28%

3. Payoff Ratio:
   b = 57 / 28 = 2.04:1

4. Kelly Fraction:
   f* = (0.667 × 2.04 - 0.333) / 2.04
   f* = (1.361 - 0.333) / 2.04
   f* = 1.028 / 2.04
   f* = 0.504 (50.4% full Kelly)

5. Conservative (25% Kelly):
   f = 0.504 × 0.25 = 0.126 (12.6%)

6. Position Size con Wallet $500:
   Size = $500 × 0.126 = $63.00
```

---

## 🎯 Memory System

### **SymbolMemory Structure**

```python
@dataclass
class SymbolMemory:
    symbol: str
    base_size: float              # Recalculated ogni ciclo
    current_size: float           # Size attuale (con premi/reset)
    blocked_cycles_left: int      # Cicli blocco rimanenti
    last_pnl_pct: float          # Ultimo P&L%
    last_cycle_updated: int       # Ultimo ciclo update
    total_trades: int             # Totale trade
    wins: int                     # Vincenti
    losses: int                   # Perdenti
    last_updated: str             # Timestamp ISO
```

### **File Persistence**

```json
// adaptive_sizing_memory.json
{
  "current_cycle": 45,
  "symbols": {
    "SOL/USDT:USDT": {
      "symbol": "SOL/USDT:USDT",
      "base_size": 50.0,
      "current_size": 63.5,
      "blocked_cycles_left": 0,
      "last_pnl_pct": 8.5,
      "last_cycle_updated": 45,
      "total_trades": 15,
      "wins": 10,
      "losses": 5,
      "last_updated": "2025-01-07T16:45:00"
    },
    "AVAX/USDT:USDT": {
      "symbol": "AVAX/USDT:USDT", 
      "base_size": 50.0,
      "current_size": 50.0,
      "blocked_cycles_left": 2,
      "last_pnl_pct": -5.2,
      "last_cycle_updated": 43,
      "total_trades": 8,
      "wins": 3,
      "losses": 5,
      "last_updated": "2025-01-07T15:30:00"
    }
  },
  "last_saved": "2025-01-07T16:45:30"
}
```

---

## 📈 Size Adjustment Logic

### **1. New Symbol**

```python
# Prima volta che appare
if symbol not in memory:
    size = base_size  # $50 (50% del block)
    reason = "new_symbol"
```

### **2. Winner (Size Grows)**

```python
# Dopo trade vincente
def update_after_win(pnl_pct):
    old_size = current_size
    growth_factor = 1 + (pnl_pct / 100.0)
    new_size = old_size * growth_factor
    
    # Apply cap (max = 1x block value)
    new_size = min(new_size, block_value * 1.0)
    
    current_size = new_size
    wins += 1
```

**Esempio**:
```
Trade: WIN +8.5% P&L
Old size: $50.00
Growth: 1 + (8.5 / 100) = 1.085
New size: $50.00 × 1.085 = $54.25
Capped: min($54.25, $100) = $54.25 ✓

Log: "✅ SOL WIN +8.5% | Size: $50.00 → $54.25 (+8.5%)"
```

### **3. Loser (Reset + Block)**

```python
# Dopo trade perdente
def update_after_loss(pnl_pct):
    current_size = base_size       # Reset to base
    blocked_cycles_left = 3        # Block 3 cycles
    losses += 1
```

**Esempio**:
```
Trade: LOSS -5.2% P&L
Old size: $63.50
Reset: $50.00 (back to base)
Block: 3 cycles

Log: "❌ AVAX LOSS -5.2% | Size: $63.50 → $50.00 (RESET) | BLOCKED 3 cycles"
```

### **4. Blocked Symbol**

```python
# Durante cicli di blocco
if blocked_cycles_left > 0:
    return (0.0, True, f"blocked_{blocked_cycles_left}_cycles")

# Ad ogni nuovo ciclo
def increment_cycle():
    for memory in all_memories:
        if memory.blocked_cycles_left > 0:
            memory.blocked_cycles_left -= 1
```

---

## 🎪 Fresh Start vs Historical Mode

### **Fresh Start Mode**

```python
ADAPTIVE_FRESH_START = True  # Reset tutto

# All'avvio:
if ADAPTIVE_FRESH_START:
    # Cancella file memory
    os.remove('adaptive_sizing_memory.json')
    
    # Ricomincia da zero
    symbol_memory = {}
    current_cycle = 0
```

**Output**:
```
🔄 FRESH START: Previous memory deleted - Starting from scratch
```

**Quando usare**:
- Dopo cambio strategy significativo
- Dopo lungo periodo offline
- Reset performance stats
- Testing nuovi parametri

### **Historical Mode**

```python
ADAPTIVE_FRESH_START = False  # Continua storia

# All'avvio:
if not ADAPTIVE_FRESH_START:
    # Carica memory esistente
    with open('adaptive_sizing_memory.json') as f:
        data = json.load(f)
    
    symbol_memory = restore_from_json(data)
    current_cycle = data['current_cycle']
```

**Output**:
```
📂 HISTORICAL MODE: Loaded 12 symbols | Cycle 45
    Stats: 27W/18L (60% WR)
    
Active: 10 symbols
Blocked: 2 symbols
```

**Quando usare**:
- Operazioni continue
- Accumulo statistiche long-term
- Learning progressivo

---

## 💰 Portfolio Risk Validation

### **Max Risk Check**

```python
# Config
ADAPTIVE_RISK_MAX_PCT = 0.20      # Max 20% wallet at risk
ADAPTIVE_LOSS_MULTIPLIER = 0.30   # SL = 30% margin loss

# Validation
total_margin = sum(margins)
max_loss = total_margin * ADAPTIVE_LOSS_MULTIPLIER
risk_limit = wallet_equity * ADAPTIVE_RISK_MAX_PCT

if max_loss > risk_limit:
    # Scale down proporzionalmente
    scale_factor = risk_limit / max_loss
    margins = [m * scale_factor for m in margins]
```

**Esempio**:
```
Wallet: $500
Positions planned: 4
Margins: [$63, $54, $50, $48] = $215 total

Max Loss: $215 × 0.30 = $64.50
Risk Limit: $500 × 0.20 = $100.00

Check: $64.50 < $100.00 ✓ OK
```

**Esempio con Scaling**:
```
Wallet: $500
Positions planned: 5
Margins: [$80, $75, $70, $65, $60] = $350 total

Max Loss: $350 × 0.30 = $105.00
Risk Limit: $500 × 0.20 = $100.00

Check: $105 > $100 ❌ EXCEED

Scale: $100 / $105 = 0.952 (95.2%)
New Margins: [$76.2, $71.4, $66.6, $61.9, $57.1] = $333.2
New Max Loss: $333.2 × 0.30 = $99.96 ✓ OK
```

---

## 📊 Evolution Report

### **Terminal Output (Ogni Ciclo)**

```
════════════════════════════════════════════════════════════════
📊 ADAPTIVE SIZING EVOLUTION REPORT - CYCLE #45
════════════════════════════════════════════════════════════════

✅ ACTIVE SYMBOLS (10):
────────────────────────────────────────────────────────────────
  SOL      | 📈 GROWING    | Size: $63.50 (+27%) | Base: $50.00 | 10W-5L (67%) | Last: +8.5%
  AVAX     | 📊 STABLE     | Size: $51.20 (+2%)  | Base: $50.00 | 6W-4L (60%)  | Last: +1.2%
  MATIC    | 📈 GROWING    | Size: $58.30 (+17%) | Base: $50.00 | 8W-3L (73%)  | Last: +5.8%
  LINK     | 📉 SHRINKING  | Size: $47.50 (-5%)  | Base: $50.00 | 4W-5L (44%)  | Last: -2.5%
  ...

🚫 BLOCKED SYMBOLS (2):
────────────────────────────────────────────────────────────────
  DOGE     | 🔒 BLOCKED 2 cycles left | Will return: $50.00 | 3W-6L (33%) | Last: -5.8% (LOSS)
  SHIB     | 🔒 BLOCKED 1 cycle left  | Will return: $50.00 | 2W-5L (29%) | Last: -4.2% (LOSS)

────────────────────────────────────────────────────────────────
📈 OVERALL: 27W / 18L | Win Rate: 60.0% | Total: 45 | Active: 10 | Blocked: 2
════════════════════════════════════════════════════════════════
```

---

## 🎯 Use Cases Pratici

### **Case 1: Nuovo Simbolo (First Trade)**

```
Ciclo #20: ETH/USDT appare per prima volta

Input:
  • Wallet: $500
  • Signal: BUY 72% confidence
  • Memory: NON ESISTE

Calculation:
  • Block value: $500 / 5 = $100
  • Base size: $100 × 0.5 = $50
  • No Kelly (< 10 trades)
  
Output:
  • Margin: $50.00
  • Reason: "new_symbol"
  
Log: "🆕 ETH/USDT: New symbol, using base size $50.00"
```

### **Case 2: Winner Streak (Growth)**

```
Ciclo #25: SOL/USDT (5 wins, 1 loss)

History:
  • Trade 1: +6.2% → Size $50 → $53.10
  • Trade 2: +4.8% → Size $53.10 → $55.65
  • Trade 3: +8.5% → Size $55.65 → $60.38
  • Trade 4: -3.2% → Size $60.38 → $50 (RESET + BLOCK 3)
  • [3 cycles blocked]
  • Trade 5: +7.1% → Size $50 → $53.55
  • Trade 6: +5.9% → Size $53.55 → $56.71

Current Size: $56.71
Status: GROWING
```

### **Case 3: Kelly Criterion (10+ Trades)**

```
Ciclo #30: AVAX/USDT (10W, 5L)

History:
  • Total: 15 trades
  • Win rate: 66.7%
  • Eligible for Kelly!

Calculation:
  • Kelly sizing: $63.00 (12.6% wallet)
  • Performance multiplier: 1.15x (recent wins)
  • Final size: $63.00 × 1.15 = $72.45
  • Capped: min($72.45, $100) = $72.45

Output:
  • Margin: $72.45
  • Reason: "kelly_criterion"
  
Log: "💎 AVAX: Kelly-based size $72.45 (Kelly: $63.00 × 1.15x, W:10 L:5)"
```

---

## ⚙️ Configuration Parameters

```python
# Wallet structure
ADAPTIVE_WALLET_BLOCKS = 5           # 5 blocks = 20% each
ADAPTIVE_FIRST_CYCLE_FACTOR = 0.5    # First cycle = 50% block

# Penalty system
ADAPTIVE_BLOCK_CYCLES = 3            # Block losers 3 cycles
ADAPTIVE_CAP_MULTIPLIER = 1.0        # Max size = 1x block value

# Risk management
ADAPTIVE_RISK_MAX_PCT = 0.20         # Max 20% wallet at risk
ADAPTIVE_LOSS_MULTIPLIER = 0.30      # SL = 30% margin

# Kelly Criterion
ADAPTIVE_USE_KELLY = True            # Enable Kelly sizing
ADAPTIVE_KELLY_FRACTION = 0.25       # Use 25% of Kelly
ADAPTIVE_MAX_POSITION_PCT = 0.25     # Max 25% wallet per position
ADAPTIVE_MIN_POSITION_PCT = 0.05     # Min 5% wallet per position

# Memory
ADAPTIVE_MEMORY_FILE = "adaptive_sizing_memory.json"
ADAPTIVE_FRESH_START = False         # Historical mode
```

---

## 📚 Next Steps

- **06-RISK-MANAGEMENT.md** - Stop loss, early exit, partial exits
- **07-TRADE-ANALYZER.md** - AI analysis per learning

---

**🎯 KEY TAKEAWAY**: Adaptive sizing con Kelly Criterion massimizza growth rate a lungo termine premiando winners e isolando losers, mentre il risk validation previene overexposure.
