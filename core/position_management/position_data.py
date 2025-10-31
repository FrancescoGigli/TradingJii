#!/usr/bin/env python3
"""
📦 POSITION DATA STRUCTURES

Dataclasses for position management system.
Extracted from thread_safe_position_manager.py for better modularity.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TrailingStopData:
    """Trailing stop tracking data for position protection"""
    enabled: bool = False
    trigger_price: float = 0.0
    trigger_pct: float = 0.01  # +1% default trigger
    protection_pct: float = 0.50  # Protect 50% of max profit
    max_favorable_price: float = 0.0
    current_stop_loss: float = 0.0
    last_update_time: float = 0.0
    activation_time: Optional[str] = None


@dataclass
class ThreadSafePosition:
    """Position data structure ottimizzata per thread safety"""
    position_id: str
    symbol: str
    side: str
    entry_price: float
    position_size: float
    leverage: int
    
    # Protection levels
    stop_loss: float
    take_profit: Optional[float]
    trailing_trigger: float
    
    # Runtime data (protected by lock)
    current_price: float = 0.0
    unrealized_pnl_pct: float = 0.0
    unrealized_pnl_usd: float = 0.0
    max_favorable_pnl: float = 0.0
    exit_price: Optional[float] = None  # Set when position closes
    
    # Aliases for closed positions (for dashboard compatibility)
    pnl_pct: float = 0.0  # Alias for unrealized_pnl_pct
    pnl_usd: float = 0.0  # Alias for unrealized_pnl_usd
    
    # Trailing stop system (OPTIMIZED)
    trailing_data: Optional[TrailingStopData] = None
    
    # Metadata
    confidence: float = 0.7
    entry_time: str = ""
    close_time: Optional[str] = None
    status: str = "OPEN"
    origin: str = "SESSION"  # "SYNCED" (from Bybit at startup) or "SESSION" (opened in this session)
    open_reason: str = "Unknown"  # Motivo di apertura (es. "ML: High confidence SHORT")
    close_snapshot: Optional[str] = None  # Snapshot dati al momento della chiusura (JSON string)
    
    # Technical indicators (for dashboard display)
    atr: float = 0.0  # Average True Range
    adx: float = 0.0  # ADX trend strength
    volatility: float = 0.0  # Market volatility
    
    # Real Initial Margin from Bybit (FIX: Read actual IM instead of calculating)
    real_initial_margin: Optional[float] = None  # Actual IM from Bybit
    
    # Real Stop Loss from Bybit (FIX: Read actual SL instead of calculating)
    real_stop_loss: Optional[float] = None  # Actual SL from Bybit
    
    # Order tracking
    sl_order_id: Optional[str] = None
    tp_order_id: Optional[str] = None
    
    # Migration flags
    _migrated: bool = False
    _needs_sl_update_on_bybit: bool = False
