# 🛡️ 05 - Position Management System

Sistema completo di gestione posizioni: sync, trailing stops, safety checks, e chiusura automatica.

---

## 📋 Indice

1. [Overview Sistema](#overview-sistema)
2. [Thread-Safe Position Manager](#thread-safe-position-manager)
3. [Sync con Bybit](#sync-con-bybit)
4. [Trailing Stops](#trailing-stops-dinamici)
5. [Auto-Fix Stop Loss](#auto-fix-stop-loss)
6. [Safety Checks](#safety-checks)
7. [Position Data Structure](#position-data-structure)

---

## 🎯 Overview Sistema

### **Responsabilità:**

```
Position Manager
  │
  ├─► Thread-Safe Operations (concorrenza sicura)
  │   ├─ Read lock: multiple threads possono leggere
  │   └─ Write lock: solo un thread può scrivere
  │
  ├─► Sync con Bybit (force refresh ogni ciclo)
  │   ├─ Detect newly opened positions
  │   ├─ Detect closed positions (calculate PnL)
  │   └─ Update existing positions (price, ROE)
  │
  ├─► Trailing Stops
  │   ├─ Activation: +15% ROE threshold
  │   ├─ Protection: ultimo 10% ROE
  │   └─ Update: solo se better SL
  │
  ├─► Auto-Fix Missing SL
  │   ├─ Detect positions senza SL
  │   └─ Apply fixed -5% SL
  │
  └─► Safety Checks
      ├─ Detect posizioni "fantasma" (non su Bybit)
      ├─ Close unsafe positions
      └─ Emergency controls
```

---

## 🔒 Thread-Safe Position Manager

### **Core Structure:**

```python
class ThreadSafePositionManager:
    """
    Thread-safe manager per posizioni attive
    
    FEATURES:
    - RWLock per concurrency safety
    - In-memory + JSON persistence
    - Sync automatico con Bybit
    - Trailing stop management
    """
    
    def __init__(self):
        # Thread-safe lock
        self.lock = threading.RLock()
        
        # In-memory storage
        self.positions = {}  # {symbol: position_dict}
        
        # Persistence
        self.positions_file = 'positions.json'
        
        # Trailing config
        self.trailing_activation_roe = 0.15  # +15%
        self.trailing_protect_roe = 0.10     # Protect last 10%
        
        # Load existing positions
        self._load_positions()
    
    def _load_positions(self):
        """Load positions from JSON file"""
        if os.path.exists(self.positions_file):
            with open(self.positions_file, 'r') as f:
                self.positions = json.load(f)
            logging.info(f"📂 Loaded {len(self.positions)} positions from file")
    
    def _save_positions(self):
        """Save positions to JSON file"""
        with open(self.positions_file, 'w') as f:
            json.dump(self.positions, f, indent=2)
```

### **Thread-Safe Operations:**

```python
    def get_active_positions(self):
        """Thread-safe read"""
        with self.lock:
            return list(self.positions.values())
    
    def get_position(self, symbol):
        """Thread-safe read single position"""
        with self.lock:
            return self.positions.get(symbol)
    
    def register_new_position(self, symbol, side, entry_price, quantity, 
                            margin, leverage, stop_loss, confidence):
        """Thread-safe write"""
        with self.lock:
            position = {
                'symbol': symbol,
                'side': side,  # 'buy' or 'sell'
                'entry_price': entry_price,
                'quantity': quantity,
                'initial_margin': margin,
                'leverage': leverage,
                'stop_loss': stop_loss,
                'confidence': confidence,
                'open_time': datetime.now().isoformat(),
                'trailing_active': False,
                'highest_roe': 0.0,
                'status': 'active'
            }
            
            self.positions[symbol] = position
            self._save_positions()
            
            logging.info(f"📝 Registered new position: {symbol}")
    
    def close_position(self, symbol, exit_price, realized_pnl):
        """Thread-safe remove"""
        with self.lock:
            if symbol in self.positions:
                pos = self.positions[symbol]
                pos['status'] = 'closed'
                pos['exit_price'] = exit_price
                pos['realized_pnl'] = realized_pnl
                pos['close_time'] = datetime.now().isoformat()
                
                # Move to history
                self._archive_position(pos)
                
                # Remove from active
                del self.positions[symbol]
                self._save_positions()
                
                logging.info(f"📤 Closed position: {symbol} | PnL: ${realized_pnl:+.2f}")
```

---

## 🔄 Sync con Bybit

### **Force Sync (Ogni Ciclo):**

```python
async def thread_safe_sync_with_bybit(self, exchange):
    """
    Force sync posizioni con Bybit API
    
    PROCESS:
    1. Fetch current positions da Bybit
    2. Compare con local state
    3. Detect newly opened (non in local)
    4. Detect closed (in local ma non su Bybit)
    5. Update existing (price, ROE, PnL)
    
    Returns:
        newly_opened: list of new positions
        newly_closed: list of closed positions
    """
    logging.debug("🔄 Syncing positions with Bybit...")
    
    # 1. Fetch positions from Bybit
    try:
        bybit_positions = await exchange.fetch_positions()
        
        # Filter active positions (size > 0)
        active_bybit = {
            pos['symbol']: pos 
            for pos in bybit_positions 
            if abs(float(pos.get('contracts', 0))) > 0
        }
        
        logging.debug(f"📊 Bybit has {len(active_bybit)} active positions")
        
    except Exception as e:
        logging.error(f"❌ Failed to fetch Bybit positions: {e}")
        return [], []
    
    # 2. Get local positions
    with self.lock:
        local_symbols = set(self.positions.keys())
        bybit_symbols = set(active_bybit.keys())
        
        # 3. Detect newly opened (on Bybit but not local)
        new_symbols = bybit_symbols - local_symbols
        newly_opened = []
        
        for symbol in new_symbols:
            bybit_pos = active_bybit[symbol]
            
            # Register in local
            self.positions[symbol] = {
                'symbol': symbol,
                'side': bybit_pos['side'],
                'entry_price': float(bybit_pos['entryPrice']),
                'quantity': abs(float(bybit_pos['contracts'])),
                'initial_margin': float(bybit_pos.get('initialMargin', 0)),
                'leverage': int(bybit_pos.get('leverage', 10)),
                'stop_loss': float(bybit_pos.get('stopLossPrice', 0)),
                'confidence': 0.5,  # Unknown
                'open_time': datetime.now().isoformat(),
                'trailing_active': False,
                'highest_roe': 0.0,
                'status': 'active'
            }
            
            newly_opened.append(self.positions[symbol])
            logging.info(f"📥 Detected NEW position: {symbol}")
        
        # 4. Detect closed (in local but not on Bybit)
        closed_symbols = local_symbols - bybit_symbols
        newly_closed = []
        
        for symbol in closed_symbols:
            pos = self.positions[symbol]
            
            # Calculate realized PnL (estimate da last price)
            try:
                ticker = await exchange.fetch_ticker(symbol)
                exit_price = ticker['last']
                
                # Calculate PnL
                if pos['side'] == 'buy':
                    pnl_pct = (exit_price - pos['entry_price']) / pos['entry_price']
                else:  # sell
                    pnl_pct = (pos['entry_price'] - exit_price) / pos['entry_price']
                
                realized_pnl = pos['initial_margin'] * pos['leverage'] * pnl_pct
                
            except:
                exit_price = pos['entry_price']
                realized_pnl = 0.0
            
            # Archive and remove
            pos['status'] = 'closed'
            pos['exit_price'] = exit_price
            pos['realized_pnl'] = realized_pnl
            pos['close_time'] = datetime.now().isoformat()
            
            self._archive_position(pos)
            newly_closed.append(pos)
            
            del self.positions[symbol]
            
            pnl_pct_val = (realized_pnl / pos['initial_margin']) * 100 if pos['initial_margin'] > 0 else 0
            emoji = "✅" if realized_pnl > 0 else "❌"
            logging.info(f"📤 {emoji} Position CLOSED: {symbol} | "
                        f"PnL: {pnl_pct_val:+.2f}% (${realized_pnl:+.2f})")
        
        # 5. Update existing positions
        for symbol in (local_symbols & bybit_symbols):
            bybit_pos = active_bybit[symbol]
            local_pos = self.positions[symbol]
            
            # Update current price and ROE
            current_price = float(bybit_pos['markPrice'])
            unrealized_pnl = float(bybit_pos.get('unrealizedPnl', 0))
            
            # Calculate ROE
            if local_pos['initial_margin'] > 0:
                roe = unrealized_pnl / local_pos['initial_margin']
            else:
                roe = 0.0
            
            # Update highest ROE
            if roe > local_pos.get('highest_roe', 0):
                local_pos['highest_roe'] = roe
            
            local_pos['current_price'] = current_price
            local_pos['unrealized_pnl'] = unrealized_pnl
            local_pos['roe'] = roe
            local_pos['last_update'] = datetime.now().isoformat()
        
        # Save changes
        self._save_positions()
    
    if newly_opened or newly_closed:
        logging.info(f"🔄 Sync complete: +{len(newly_opened)} opened, "
                    f"-{len(newly_closed)} closed")
    else:
        logging.debug("✅ Sync complete: no changes")
    
    return newly_opened, newly_closed
```

---

## 📈 Trailing Stops Dinamici

### **Activation & Update Logic:**

```python
async def update_trailing_stops(self, exchange):
    """
    Update trailing stops per posizioni in profit
    
    LOGIC:
    1. Check ogni posizione attiva
    2. If ROE >= +15%: attiva trailing
    3. Calculate new SL che protegge ultimo 10% ROE
    4. Update solo se new SL è better (più vicino a prezzo corrente)
    
    Returns:
        updates_count: numero di trailing stops aggiornati
    """
    updates_count = 0
    
    with self.lock:
        active_positions = list(self.positions.values())
    
    for pos in active_positions:
        symbol = pos['symbol']
        
        try:
            # Get current price
            ticker = await exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            
            # Calculate current ROE
            entry_price = pos['entry_price']
            side = pos['side']
            leverage = pos['leverage']
            
            if side == 'buy':
                price_change_pct = (current_price - entry_price) / entry_price
            else:  # sell
                price_change_pct = (entry_price - current_price) / entry_price
            
            current_roe = price_change_pct * leverage
            
            # Check if trailing should activate
            if current_roe < self.trailing_activation_roe:
                continue  # Not  enough profit yet
            
            # Calculate trailing SL (protect last 10% ROE)
            target_roe = current_roe - self.trailing_protect_roe
            target_price_change = target_roe / leverage
            
            if side == 'buy':
                new_sl = entry_price * (1 + target_price_change)
            else:  # sell
                new_sl = entry_price * (1 - target_price_change)
            
            # Check if new SL is better than current
            current_sl = pos.get('stop_loss', 0)
            
            if side == 'buy':
                is_better = new_sl > current_sl
            else:  # sell
                is_better = new_sl < current_sl
            
            if not is_better:
                continue  # Don't move SL backwards
            
            # Update SL on Bybit
            await exchange.set_trading_stop(
                symbol=symbol,
                params={
                    'stopLoss': str(new_sl),
                    'positionIdx': 0
                }
            )
            
            # Update local
            with self.lock:
                self.positions[symbol]['stop_loss'] = new_sl
                self.positions[symbol]['trailing_active'] = True
                self._save_positions()
            
            protected_roe = (current_roe - self.trailing_protect_roe) * 100
            logging.info(f"📈 {symbol}: Trailing SL updated to ${new_sl:.6f} "
                        f"(Current ROE: +{current_roe*100:.1f}%, Protects: +{protected_roe:.1f}%)")
            
            updates_count += 1
            
        except Exception as e:
            logging.error(f"❌ Failed to update trailing for {symbol}: {e}")
    
    return updates_count
```

---

## 🛠️ Auto-Fix Stop Loss

### **Detect & Fix Missing SL:**

```python
async def check_and_fix_stop_losses(self, exchange):
    """
    Auto-fix posizioni senza stop loss
    
    SAFETY CRITICAL:
    - Ogni posizione DEVE avere SL
    - Se mancante: applica fixed -5% SL
    - Previene loss catastrofici
    
    Returns:
        fixed_count: numero di SL fixati
    """
    fixed_count = 0
    
    with self.lock:
        active_positions = list(self.positions.values())
    
    for pos in active_positions:
        symbol = pos['symbol']
        current_sl = pos.get('stop_loss', 0)
        
        # Check if SL is missing or zero
        if current_sl == 0 or current_sl is None:
            logging.warning(f"⚠️ {symbol}: MISSING Stop Loss - auto-fixing...")
            
            try:
                # Get current price
                ticker = await exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                
                # Calculate fixed SL (-5%)
                if pos['side'] == 'buy':
                    fixed_sl = current_price * 0.95  # -5%
                else:  # sell
                    fixed_sl = current_price * 1.05  # +5%
                
                # Apply on Bybit
                await exchange.set_trading_stop(
                    symbol=symbol,
                    params={
                        'stopLoss': str(fixed_sl),
                        'positionIdx': 0
                    }
                )
                
                # Update local
                with self.lock:
                    self.positions[symbol]['stop_loss'] = fixed_sl
                    self._save_positions()
                
                logging.info(f"✅ {symbol}: Stop Loss fixed at ${fixed_sl:.6f} (-5%)")
                fixed_count += 1
                
            except Exception as e:
                logging.error(f"❌ Failed to fix SL for {symbol}: {e}")
    
    if fixed_count > 0:
        logging.warning(f"🛠️ AUTO-FIX: {fixed_count} stop losses corrected")
    
    return fixed_count
```

---

## 🚨 Safety Checks

### **Detect & Close Unsafe Positions:**

```python
async def check_and_close_unsafe_positions(self, exchange):
    """
    Safety check per posizioni anomale
    
    CHECKS:
    1. Posizioni "fantasma" (in local ma non su Bybit)
    2. Posizioni senza SL dopo 3 tentativi fix
    3. Posizioni con ROE < -100% (impossible con SL)
    4. Posizioni aperte > 24h (troppo old)
    
    Returns:
        closed_count: numero posizioni chiuse
    """
    closed_count = 0
    
    # 1. Get Bybit positions
    try:
        bybit_positions = await exchange.fetch_positions()
        bybit_symbols = {
            pos['symbol'] 
            for pos in bybit_positions 
            if abs(float(pos.get('contracts', 0))) > 0
        }
    except Exception as e:
        logging.error(f"❌ Failed to fetch Bybit positions for safety check: {e}")
        return 0
    
    with self.lock:
        local_symbols = set(self.positions.keys())
        
        # Find ghost positions (in local but not on Bybit)
        ghost_symbols = local_symbols - bybit_symbols
        
        for symbol in ghost_symbols:
            logging.warning(f"👻 GHOST position detected: {symbol} - removing from local")
            
            pos = self.positions[symbol]
            pos['status'] = 'ghost_closed'
            pos['close_time'] = datetime.now().isoformat()
            
            self._archive_position(pos)
            del self.positions[symbol]
            
            closed_count += 1
        
        # Check other safety conditions
        for symbol, pos in list(self.positions.items()):
            should_close = False
            reason = ""
            
            # Check 1: No SL after multiple fixes
            if pos.get('sl_fix_attempts', 0) >= 3 and pos.get('stop_loss', 0) == 0:
                should_close = True
                reason = "No SL after 3 fix attempts"
            
            # Check 2: Impossible ROE
            if pos.get('roe', 0) < -1.0:  # < -100% ROE
                should_close = True
                reason = "Impossible ROE < -100%"
            
            # Check 3: Too old position
            open_time = datetime.fromisoformat(pos['open_time'])
            age_hours = (datetime.now() - open_time).total_seconds() / 3600
            if age_hours > 24:
                should_close = True
                reason = f"Position too old ({age_hours:.1f}h)"
            
            if should_close:
                logging.warning(f"🚨 UNSAFE position: {symbol} - {reason}")
                logging.warning(f"   Attempting emergency close...")
                
                try:
                    # Close position on Bybit
                    if pos['side'] == 'buy':
                        close_side = 'sell'
                    else:
                        close_side = 'buy'
                    
                    await exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side=close_side,
                        amount=pos['quantity'],
                        params={'reduceOnly': True, 'positionIdx': 0}
                    )
                    
                    pos['status'] = 'emergency_closed'
                    pos['close_reason'] = reason
                    pos['close_time'] = datetime.now().isoformat()
                    
                    self._archive_position(pos)
                    del self.positions[symbol]
                    
                    logging.warning(f"✅ Emergency closed: {symbol}")
                    closed_count += 1
                    
                except Exception as e:
                    logging.error(f"❌ Failed emergency close for {symbol}: {e}")
        
        # Save changes
        self._save_positions()
    
    if closed_count > 0:
        logging.warning(f"🚨 SAFETY: {closed_count} unsafe positions handled")
    
    return closed_count
```

---

## 📊 Position Data Structure

### **Complete Position Object:**

```python
position = {
    # Identity
    'symbol': 'BTC/USDT:USDT',
    'side': 'buy',  # or 'sell'
    
    # Entry info
    'entry_price': 50000.0,
    'quantity': 0.002,
    'initial_margin': 100.0,
    'leverage': 10,
    'confidence': 0.85,
    'open_time': '2025-03-11T08:30:00',
    
    # Risk management
    'stop_loss': 47500.0,  # -5%
    'trailing_active': True,
    'highest_roe': 0.25,  # +25%
    
    # Current state
    'current_price': 52500.0,
    'unrealized_pnl': 50.0,  # $50 profit
    'roe': 0.50,  # +50%  ROE
    
    # Metadata
    'status': 'active',
    'last_update': '2025-03-11T09:00:00',
    'sl_fix_attempts': 0
}
```

### **Position States:**

```
States:
├─ active          # Posizione aperta e monitorata
├─ closed          # Chiusa normalmente (SL o TP)
├─ ghost_closed    # Rimossa (non più su Bybit)
└─ emergency_closed # Chiusa per safety check
```

---

## 📈 Performance Monitoring

### **Key Metrics:**

```python
def get_position_stats(self):
    """Get statistics sulle posizioni"""
    with self.lock:
        active = list(self.positions.values())
    
    if not active:
        return None
    
    # Calculate stats
    total_margin = sum(p['initial_margin'] for p in active)
    total_unrealized = sum(p.get('unrealized_pnl', 0) for p in active)
    
    winning_pos = [p for p in active if p.get('roe', 0) > 0]
    losing_pos = [p for p in active if p.get('roe', 0) < 0]
    
    avg_roe = np.mean([p.get('roe', 0) for p in active]) * 100
    
    return {
        'active_count': len(active),
        'total_margin_used': total_margin,
        'total_unrealized_pnl': total_unrealized,
        'winning_positions': len(winning_pos),
        'losing_positions': len(losing_pos),
        'average_roe': avg_roe,
        'trailing_active_count': sum(1 for p in active if p.get('trailing_active', False))
    }
```

---

**Prossimo:** [06 - Adaptive Position Sizing](06-ADAPTIVE-SIZING.md) →
