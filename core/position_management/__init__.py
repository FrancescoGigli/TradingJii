#!/usr/bin/env python3
"""
🏛️ POSITION MANAGEMENT FACADE

Provides backward-compatible API while using modular architecture internally.
This FACADE pattern ensures 100% compatibility with existing code.
"""

from .position_data import ThreadSafePosition, TrailingStopData
from .position_io import PositionIO
from .position_core import PositionCore
from .position_sync import PositionSync
from .position_trailing import PositionTrailing
from .position_safety import PositionSafety


class ThreadSafePositionManager:
    """
    FACADE for position management system
    
    Provides backward-compatible API while using modular components internally.
    All existing code will work without changes.
    """
    
    def __init__(self, storage_file: str = "thread_safe_positions.json"):
        # Initialize components
        self.io = PositionIO(storage_file)
        self.core = PositionCore(io=self.io)
        self.sync = PositionSync(core=self.core)
        self.trailing = PositionTrailing(core=self.core)
        self.safety = PositionSafety(core=self.core)
    
    # ========================================
    # POSITION LIFECYCLE (Core operations)
    # ========================================
    
    def create_position(self, *args, **kwargs):
        """Create new position - delegated to core"""
        return self.core.create_position(*args, **kwargs)
    
    def close_position_manual(self, position_id: str, exit_price: float, close_reason: str = "MANUAL"):
        """Close position manually - delegated to core"""
        return self.core.close_position(position_id, exit_price, close_reason)
    
    # ========================================
    # ATOMIC UPDATES (Core operations)
    # ========================================
    
    def atomic_update_position(self, position_id: str, updates: dict):
        """Atomic position update - delegated to core"""
        return self.core.atomic_update_position(position_id, updates)
    
    def atomic_update_price_and_pnl(self, position_id: str, current_price: float):
        """Atomic price/PnL update - delegated to core"""
        return self.core.atomic_update_price_and_pnl(position_id, current_price)
    
    # ========================================
    # SAFE READS (Core operations)
    # ========================================
    
    def safe_get_position(self, position_id: str):
        """Get position copy - delegated to core"""
        return self.core.safe_get_position(position_id)
    
    def safe_get_all_active_positions(self):
        """Get all active positions - delegated to core"""
        return self.core.safe_get_all_active_positions()
    
    def safe_get_positions_by_origin(self, origin: str):
        """Get positions by origin - delegated to core"""
        return self.core.safe_get_positions_by_origin(origin)
    
    def safe_get_closed_positions(self):
        """Get closed positions - delegated to core"""
        return self.core.safe_get_closed_positions()
    
    def safe_has_position_for_symbol(self, symbol: str):
        """Check if position exists for symbol - delegated to core"""
        return self.core.safe_has_position_for_symbol(symbol)
    
    def safe_get_position_count(self):
        """Get active position count - delegated to core"""
        return self.core.safe_get_position_count()
    
    def safe_get_session_summary(self):
        """Get session statistics - delegated to core"""
        return self.core.safe_get_session_summary()
    
    def get_session_summary(self):
        """Get session summary (alias for safe_get_session_summary) - delegated to core"""
        return self.core.safe_get_session_summary()
    
    def has_position_for_symbol(self, symbol: str):
        """Check if position exists (alias for safe_has_position_for_symbol) - delegated to core"""
        return self.core.safe_has_position_for_symbol(symbol)
    
    def get_active_positions(self):
        """Get active positions (alias for safe_get_all_active_positions) - delegated to core"""
        return self.core.safe_get_all_active_positions()
    
    def get_position_count(self):
        """Get position count (alias for safe_get_position_count) - delegated to core"""
        return self.core.safe_get_position_count()
    
    def thread_safe_create_position(self, *args, **kwargs):
        """Create position (alias for create_position) - delegated to core"""
        return self.core.create_position(*args, **kwargs)
    
    # ========================================
    # BALANCE OPERATIONS (Core operations)
    # ========================================
    
    def update_balance(self, new_balance: float):
        """Update session balance - delegated to core"""
        return self.core.update_balance(new_balance)
    
    def update_real_balance(self, new_balance: float):
        """Update real balance (alias for update_balance) - delegated to core"""
        return self.core.update_balance(new_balance)
    
    def get_available_balance(self):
        """Get available balance - delegated to core"""
        return self.core.get_available_balance()
    
    def reset_session(self):
        """Reset session - delegated to core"""
        return self.core.reset_session()
    
    def reset_session_closed_positions(self):
        """Reset only closed positions for fresh session - delegated to core"""
        return self.core.reset_session_closed_positions()
    
    # ========================================
    # BYBIT SYNC (Sync operations)
    # ========================================
    
    async def sync_with_bybit(self, exchange):
        """Sync positions with Bybit - delegated to sync"""
        return await self.sync.sync_with_bybit(exchange)
    
    async def thread_safe_sync_with_bybit(self, exchange):
        """Sync with Bybit (alias for sync_with_bybit) - delegated to sync"""
        return await self.sync.sync_with_bybit(exchange)
    
    # ========================================
    # TRAILING STOPS (Trailing operations)
    # ========================================
    
    async def update_trailing_stops(self, exchange):
        """Update trailing stops - delegated to trailing"""
        return await self.trailing.update_trailing_stops(exchange)
    
    # ========================================
    # SAFETY CHECKS (Safety operations)
    # ========================================
    
    async def check_and_fix_stop_losses(self, exchange):
        """Check and fix stop losses - delegated to safety"""
        return await self.safety.check_and_fix_stop_losses(exchange)
    
    async def check_and_close_unsafe_positions(self, exchange):
        """Check and close unsafe positions - delegated to safety"""
        return await self.safety.check_and_close_unsafe_positions(exchange)
    
    # ========================================
    # DIRECT ACCESS (for internal use)
    # ========================================
    
    @property
    def _lock(self):
        """Access internal lock - for compatibility"""
        return self.core.get_lock()
    
    @property
    def _open_positions(self):
        """Direct access to open positions - for internal use only"""
        return self.core._get_open_positions_unsafe()
    
    @property
    def _closed_positions(self):
        """Direct access to closed positions - for internal use only"""
        return self.core._get_closed_positions_unsafe()
    
    @property
    def _session_balance(self):
        """Access session balance"""
        return self.core._session_balance
    
    @_session_balance.setter
    def _session_balance(self, value):
        """Set session balance"""
        self.core._session_balance = value
    
    @property
    def _session_start_balance(self):
        """Access session start balance"""
        return self.core._session_start_balance
    
    @_session_start_balance.setter
    def _session_start_balance(self, value):
        """Set session start balance"""
        self.core._session_start_balance = value


# ========================================
# GLOBAL INSTANCE (Backward compatibility)
# ========================================

global_thread_safe_position_manager = ThreadSafePositionManager()


# ========================================
# PUBLIC EXPORTS
# ========================================

__all__ = [
    'ThreadSafePositionManager',
    'ThreadSafePosition',
    'TrailingStopData',
    'global_thread_safe_position_manager'
]
