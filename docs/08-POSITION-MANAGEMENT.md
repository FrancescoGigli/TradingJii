# 📖 08 - Position Management (Thread-Safe)

> **Gestione posizioni con concurrency safety**

---

## 🔒 Overview ThreadSafePositionManager

Il sistema usa **ThreadSafePositionManager** per gestire posizioni con **thread safety** garantita tramite `threading.Lock`, permettendo accesso concorrente sicuro da multiple task asyncio.

```
POSITION LIFECYCLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
APERTURA
  ├─ create_position()
  │  • Generate unique ID
  │  • Initialize Position object
  │  • Add to _open_positions dict
  │  └─ Save to positions.json
  │
MONITORAGGIO
  ├─ Sync con Bybit (ogni 60s)
  │  • Fetch real positions
  │  • Update PnL, ROE
  │  • Detect closures
  │
  └─ Background tasks
     • Balance updates
     • Dashboard updates
     • Partial exit checks
  
CHIUSURA
  ├─ close_position()
  │  • Move to _closed_positions
  │  • Calculate final PnL
  │  • Update adaptive memory
  │  • Trigger AI analysis
  │  └─ Save to positions.json
  │
PERSISTENCE
  └─ positions.json (auto-save)
     • Open positions
     • Closed positions
     • Session stats
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🏗️ Position Data Structure

### **ThreadSafePosition Class**

```python
@dataclass
class ThreadSafePosition:
    """Thread-safe position object"""
    position_id: str              # Unique ID
    symbol: str                   # Trading pair
    side: str                     # 'buy' or 'sell'
    entry_price: float            # Entry price
    current_price: float          # Latest price
    position_size: float          # USD notional value
    leverage: int                 # Leverage (5x)
    
    # P&L
    unrealized_pnl: float         # USD P&L
    roe_percentage: float         # ROE%
    
    # Metadata
    open_time: str                # ISO timestamp
    close_time: Optional[str]     # ISO timestamp
    confidence: float             # ML confidence
    open_reason: str              # ML prediction details
    close_reason: Optional[str]   # Exit reason
    
    # Technical indicators (at entry)
    atr: Optional[float] = 0.0
    adx: Optional[float] = 0.0
    volatility: Optional[float] = 0.0
    
    # Tracking
    real_initial_margin: Optional[float] = None
    partial_exits: List[Dict] = field(default_factory=list)
```

### **File Persistence (positions.json)**

```json
{
  "open_positions": {
    "pos_abc123": {
      "position_id": "pos_abc123",
      "symbol": "SOL/USDT:USDT",
      "side": "buy",
      "entry_price": 100.50,
      "current_price": 105.20,
      "position_size": 500.0,
      "leverage": 5,
      "unrealized_pnl": 23.50,
      "roe_percentage": 23.5,
      "open_time": "2025-01-07T16:45:00",
      "confidence": 0.77,
      "open_reason": "ML BUY 77% | TF[15m:↑72% 30m:↑78% 1h:↑81%]",
      "atr": 2.3,
      "adx": 28.5,
      "volatility": 0.028
    }
  },
  "closed_positions": [],
  "session_stats": {
    "total_trades": 45,
    "wins": 27,
    "losses": 18,
    "total_pnl": 385.50,
    "win_rate": 0.60
  }
}
```

---

## 🔐 Thread Safety Implementation

### **Lock-Based Protection**

```python
class ThreadSafePositionManager:
    """
    Thread-safe position manager usando threading.Lock
    """
    
    def __init__(self):
        self._lock = threading.Lock()  # Critical section protection
        self._open_positions: Dict[str, Position] = {}
        self._closed_positions: List[Position] = []
        self.file_path = Path("positions.json")
    
    def thread_safe_create_position(self, **kwargs) -> str:
        """
        Create position con lock protection
        """
        with self._lock:  # Acquire lock
            position_id = self._generate_id()
            position = ThreadSafePosition(
                position_id=position_id,
                **kwargs
            )
            self._open_positions[position_id] = position
            self._save_to_file()  # Persist
            return position_id
        # Lock automatically released
    
    def get_active_positions(self) -> List[Position]:
        """
        Get all active positions (thread-safe)
        """
        with self._lock:
            return list(self._open_positions.values())
    
    def close_position(self, position_id: str, reason: str):
        """
        Close position (thread-safe)
        """
        with self._lock:
            if position_id not in self._open_positions:
                return False
            
            position = self._open_positions.pop(position_id)
            position.close_time = datetime.now().isoformat()
            position.close_reason = reason
            
            self._closed_positions.append(position)
            self._save_to_file()
            
            return True
```

### **Why Lock is Needed**

```python
# Multiple async tasks accessing positions concurrently:

# Task 1: Trading loop (creates positions)
await orchestrator.execute_new_trade(...)  # Modifies _open_positions

# Task 2: Balance sync (reads positions)
positions = manager.get_active_positions()  # Reads _open_positions

# Task 3: Dashboard update (reads positions)
positions = manager.get_active_positions()  # Reads _open_positions

# Task 4: Partial exit monitor (modifies positions)
manager.update_position_size(...)  # Modifies _open_positions

# WITHOUT LOCK → Race conditions, data corruption
# WITH LOCK → Safe concurrent access ✓
```

---

## 🔄 Position Sync con Bybit

### **Sync Process (ogni 60s)**

```python
async def thread_safe_sync_with_bybit(self, exchange):
    """
    Sincronizza con posizioni reali su Bybit
    
    Returns:
        Tuple[List[Position], List[str]]: (newly_opened, closed_ids)
    """
    try:
        # 1. Fetch real positions from Bybit
        bybit_positions = await exchange.fetch_positions()
        active_bybit = {
            p['symbol']: p 
            for p in bybit_positions 
            if abs(float(p.get('contracts', 0))) > 0
        }
        
        newly_opened = []
        closed_ids = []
        
        with self._lock:
            # 2. Check for new positions on Bybit (not in tracker)
            for symbol, bybit_pos in active_bybit.items():
                if not self.has_position_for_symbol(symbol):
                    # New position found on Bybit → Add to tracker
                    position = self._create_from_bybit(bybit_pos)
                    self._open_positions[position.position_id] = position
                    newly_opened.append(position)
            
            # 3. Update existing positions
            for position in list(self._open_positions.values()):
                if position.symbol in active_bybit:
                    # Update from Bybit data
                    self._update_from_bybit(position, active_bybit[position.symbol])
                else:
                    # Position closed on Bybit → Close in tracker
                    self._handle_bybit_closure(position)
                    closed_ids.append(position.position_id)
            
            # 4. Save changes
            if newly_opened or closed_ids:
                self._save_to_file()
        
        return newly_opened, closed_ids
        
    except Exception as e:
        logging.error(f"Bybit sync error: {e}")
        return [], []
```

### **Data Update from Bybit**

```python
def _update_from_bybit(self, position: Position, bybit_data: dict):
    """
    Aggiorna position con dati reali da Bybit
    """
    # Current price
    position.current_price = float(bybit_data.get('markPrice', position.current_price))
    
    # Unrealized P&L
    position.unrealized_pnl = float(bybit_data.get('unrealizedPnl', 0))
    
    # Calculate ROE
    if position.real_initial_margin and position.real_initial_margin > 0:
        position.roe_percentage = (position.unrealized_pnl / position.real_initial_margin) * 100
    else:
        # Fallback calculation
        price_change = (position.current_price - position.entry_price) / position.entry_price
        if position.side == 'sell':
            price_change = -price_change
        position.roe_percentage = price_change * position.leverage * 100
    
    # Contracts/size
    actual_contracts = abs(float(bybit_data.get('contracts', 0)))
    if actual_contracts > 0:
        position.position_size = actual_contracts * position.current_price
```

---

## 📊 Position Statistics

### **Session Summary**

```python
def get_session_summary(self) -> Dict:
    """
    Ottieni statistiche sessione corrente
    """
    with self._lock:
        active = list(self._open_positions.values())
        closed = self._closed_positions
        
        # Active positions stats
        active_count = len(active)
        used_margin = sum(p.real_initial_margin or 0 for p in active)
        unrealized_pnl = sum(p.unrealized_pnl for p in active)
        
        # Closed positions stats
        closed_wins = [p for p in closed if p.unrealized_pnl > 0]
        closed_losses = [p for p in closed if p.unrealized_pnl <= 0]
        
        total_realized_pnl = sum(p.unrealized_pnl for p in closed)
        total_pnl = unrealized_pnl + total_realized_pnl
        
        # Win rate
        total_closed = len(closed)
        win_rate = len(closed_wins) / total_closed if total_closed > 0 else 0
        
        return {
            'active_positions': active_count,
            'used_margin': used_margin,
            'unrealized_pnl': unrealized_pnl,
            'closed_trades': total_closed,
            'wins': len(closed_wins),
            'losses': len(closed_losses),
            'win_rate': win_rate,
            'total_realized_pnl': total_realized_pnl,
            'total_pnl': total_pnl,
            'balance': self._current_balance,
            'available_balance': self._current_balance - used_margin
        }
```

### **Output Example**

```python
{
    'active_positions': 3,
    'used_margin': 150.0,
    'unrealized_pnl': 45.50,
    'closed_trades': 42,
    'wins': 26,
    'losses': 16,
    'win_rate': 0.619,
    'total_realized_pnl': 340.0,
    'total_pnl': 385.50,
    'balance': 500.0,
    'available_balance': 350.0
}
```

---

## 💾 File Persistence

### **Auto-Save on Changes**

```python
def _save_to_file(self):
    """
    Salva posizioni su file JSON
    
    Called automatically after ogni modifica
    """
    try:
        data = {
            'open_positions': {
                pid: asdict(pos) 
                for pid, pos in self._open_positions.items()
            },
            'closed_positions': [
                asdict(pos) for pos in self._closed_positions
            ],
            'session_stats': self.get_session_summary(),
            'last_saved': datetime.now().isoformat()
        }
        
        # Atomic write (temp file + rename)
        temp_file = self.file_path.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        temp_file.replace(self.file_path)  # Atomic
        
    except Exception as e:
        logging.error(f"Failed to save positions: {e}")
```

### **Load on Startup**

```python
def _load_from_file(self):
    """
    Carica posizioni da file all'avvio
    """
    try:
        if not self.file_path.exists():
            logging.info("No positions file found - starting fresh")
            return
        
        with open(self.file_path, 'r') as f:
            data = json.load(f)
        
        # Restore open positions
        for pid, pos_dict in data.get('open_positions', {}).items():
            self._open_positions[pid] = ThreadSafePosition(**pos_dict)
        
        # Restore closed positions
        for pos_dict in data.get('closed_positions', []):
            self._closed_positions.append(ThreadSafePosition(**pos_dict))
        
        logging.info(
            f"Loaded {len(self._open_positions)} open, "
            f"{len(self._closed_positions)} closed positions"
        )
        
    except Exception as e:
        logging.error(f"Failed to load positions: {e}")
        # Continue with empty state
```

---

## 🎯 Partial Exits Tracking

### **Register Partial Exit**

```python
def register_partial_exit(
    self,
    position_id: str,
    exit_size: float,
    exit_price: float,
    realized_pnl: float,
    reason: str
):
    """
    Registra partial exit su posizione
    """
    with self._lock:
        if position_id not in self._open_positions:
            return False
        
        position = self._open_positions[position_id]
        
        # Record partial exit
        partial_exit = {
            'timestamp': datetime.now().isoformat(),
            'size': exit_size,
            'price': exit_price,
            'realized_pnl': realized_pnl,
            'reason': reason
        }
        
        position.partial_exits.append(partial_exit)
        
        # Update remaining size
        position.position_size -= exit_size
        
        self._save_to_file()
        
        return True
```

### **Example Tracking**

```json
{
  "position_id": "pos_xyz789",
  "symbol": "SOL/USDT:USDT",
  "position_size": 200.0,
  "partial_exits": [
    {
      "timestamp": "2025-01-07T17:15:00",
      "size": 150.0,
      "price": 110.0,
      "realized_pnl": 15.0,
      "reason": "partial_exit_50_roe"
    },
    {
      "timestamp": "2025-01-07T17:45:00",
      "size": 150.0,
      "price": 120.0,
      "realized_pnl": 30.0,
      "reason": "partial_exit_100_roe"
    }
  ]
}
```

---

## 🔍 Position Queries

### **Get Position by ID**

```python
def get_position(self, position_id: str) -> Optional[Position]:
    """Thread-safe get by ID"""
    with self._lock:
        return self._open_positions.get(position_id)
```

### **Get Position by Symbol**

```python
def get_position_for_symbol(self, symbol: str) -> Optional[Position]:
    """Thread-safe get by symbol"""
    with self._lock:
        for pos in self._open_positions.values():
            if pos.symbol == symbol:
                return pos
        return None
```

### **Check if Symbol Has Position**

```python
def has_position_for_symbol(self, symbol: str) -> bool:
    """Thread-safe symbol check"""
    with self._lock:
        return any(p.symbol == symbol for p in self._open_positions.values())
```

---

## ⚙️ Configuration

```python
# File path
POSITIONS_FILE = "positions.json"

# Sync interval
POSITION_SYNC_INTERVAL = 60  # seconds

# Max positions
MAX_CONCURRENT_POSITIONS = 5

# Backup
AUTO_BACKUP_ENABLED = True
BACKUP_INTERVAL_HOURS = 24
```

---

## 📚 Next Steps

- **09-DASHBOARD.md** - PyQt6 GUI real-time
- **10-CONFIGURAZIONE.md** - Complete config guide

---

**🎯 KEY TAKEAWAY**: ThreadSafePositionManager garantisce accesso sicuro concorrente alle posizioni da multiple task asyncio usando `threading.Lock`, con file persistence automatica per recovery dopo restart.
