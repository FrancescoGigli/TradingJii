#!/usr/bin/env python3
"""
💰 BALANCE MANAGER

Centralized balance management to eliminate duplications
- Single source of truth for balance
- Automatic sync with Bybit
- Thread-safe operations
- Prevents double-counting issues
"""

import logging
import asyncio
from typing import Optional
from termcolor import colored
import config


class BalanceManager:
    """
    Centralized balance manager
    
    FEATURES:
    - Single source of truth (delegates to position_manager)
    - Automatic sync with Bybit
    - Validation to prevent double-counting
    - Thread-safe operations
    """
    
    def __init__(self, position_manager=None):
        """
        Initialize balance manager
        
        Args:
            position_manager: ThreadSafePositionManager instance (single source of truth)
        """
        self.position_manager = position_manager
        self._last_sync_time = 0
        self._sync_interval = 60  # Default 60 seconds
    
    async def sync_balance(self, exchange, force: bool = False) -> Optional[float]:
        """
        Sync balance from Bybit
        
        Args:
            exchange: ccxt exchange instance
            force: Force sync even if recently synced
            
        Returns:
            float: Current balance, or None if sync failed
        """
        import time
        
        # Check if we need to sync
        current_time = time.time()
        time_since_sync = current_time - self._last_sync_time
        
        if not force and time_since_sync < self._sync_interval:
            logging.debug(f"💰 Balance sync skipped (last sync {time_since_sync:.0f}s ago)")
            return self.get_balance()
        
        # DEMO MODE: Use demo balance
        if config.DEMO_MODE:
            if self.position_manager:
                self.position_manager.update_real_balance(config.DEMO_BALANCE)
            self._last_sync_time = current_time
            return config.DEMO_BALANCE
        
        # LIVE MODE: Fetch from Bybit
        try:
            from trade_manager import get_real_balance
            
            real_balance = await get_real_balance(exchange)
            
            if real_balance and real_balance > 0:
                # Update position manager (single source of truth)
                if self.position_manager:
                    old_balance = self.get_balance()
                    self.position_manager.update_real_balance(real_balance)
                    
                    # Log only significant changes (> $1)
                    balance_change = abs(real_balance - old_balance)
                    if balance_change > 1.0:
                        logging.info(colored(
                            f"💰 Balance synced: ${old_balance:.2f} → ${real_balance:.2f} "
                            f"({real_balance - old_balance:+.2f})",
                            "cyan"
                        ))
                    else:
                        logging.debug(f"💰 Balance synced: ${real_balance:.2f}")
                
                self._last_sync_time = current_time
                return real_balance
            else:
                logging.warning("⚠️ Balance sync returned invalid value")
                return None
                
        except Exception as e:
            logging.error(f"❌ Balance sync failed: {e}")
            return None
    
    def get_balance(self) -> float:
        """
        Get current balance from position manager (single source of truth)
        
        Returns:
            float: Current balance
        """
        if not self.position_manager:
            return config.DEMO_BALANCE if config.DEMO_MODE else 0.0
        
        session_summary = self.position_manager.get_session_summary()
        return session_summary.get('balance', config.DEMO_BALANCE if config.DEMO_MODE else 0.0)
    
    def get_available_balance(self) -> float:
        """
        Get available balance (total - used margin)
        
        Returns:
            float: Available balance
        """
        if not self.position_manager:
            return config.DEMO_BALANCE if config.DEMO_MODE else 0.0
        
        session_summary = self.position_manager.get_session_summary()
        available = session_summary.get('available_balance', 0.0)
        
        # Validate calculation to prevent double-counting
        total = session_summary.get('balance', 0.0)
        used = session_summary.get('used_margin', 0.0)
        calculated = total - used
        
        balance_diff = abs(available - calculated)
        if balance_diff > 0.01:  # Tolerance: 1 cent
            logging.error(
                f"❌ BALANCE MISMATCH DETECTED!\n"
                f"   Reported available: ${available:.2f}\n"
                f"   Calculated (balance - used): ${calculated:.2f}\n"
                f"   Difference: ${balance_diff:.2f}\n"
                f"   Total balance: ${total:.2f}\n"
                f"   Used margin: ${used:.2f}"
            )
            # Use calculated value as safe fallback
            return max(0, calculated)
        
        return available
    
    def get_used_margin(self) -> float:
        """
        Get currently used margin
        
        Returns:
            float: Used margin
        """
        if not self.position_manager:
            return 0.0
        
        session_summary = self.position_manager.get_session_summary()
        return session_summary.get('used_margin', 0.0)
    
    def get_balance_info(self) -> dict:
        """
        Get comprehensive balance information
        
        Returns:
            dict: Balance information
        """
        if not self.position_manager:
            return {
                'total': config.DEMO_BALANCE if config.DEMO_MODE else 0.0,
                'available': config.DEMO_BALANCE if config.DEMO_MODE else 0.0,
                'used_margin': 0.0,
                'active_positions': 0,
                'demo_mode': config.DEMO_MODE
            }
        
        session_summary = self.position_manager.get_session_summary()
        
        return {
            'total': session_summary.get('balance', 0.0),
            'available': self.get_available_balance(),  # Use validated method
            'used_margin': session_summary.get('used_margin', 0.0),
            'active_positions': session_summary.get('active_positions', 0),
            'demo_mode': config.DEMO_MODE
        }
    
    async def initialize_balance(self, exchange) -> bool:
        """
        Initialize balance at startup
        
        Args:
            exchange: ccxt exchange instance
            
        Returns:
            bool: True if initialization successful
        """
        logging.info(colored("💰 Initializing balance...", "cyan"))
        
        if config.DEMO_MODE:
            if self.position_manager:
                self.position_manager.update_real_balance(config.DEMO_BALANCE)
            logging.info(colored(f"🧪 DEMO MODE: Using ${config.DEMO_BALANCE:.2f}", "yellow"))
            return True
        
        # LIVE MODE: Sync with Bybit
        balance = await self.sync_balance(exchange, force=True)
        
        if balance and balance > 0:
            logging.info(colored(f"💰 Balance initialized: ${balance:.2f}", "green"))
            return True
        else:
            logging.error("❌ Failed to initialize balance")
            return False


# Global balance manager (will be initialized with position_manager)
_global_balance_manager: Optional[BalanceManager] = None


def initialize_global_balance_manager(position_manager):
    """
    Initialize global balance manager
    
    Args:
        position_manager: ThreadSafePositionManager instance
    """
    global _global_balance_manager
    _global_balance_manager = BalanceManager(position_manager)
    logging.debug("💰 Global balance manager initialized")
    return _global_balance_manager


def get_global_balance_manager() -> Optional[BalanceManager]:
    """
    Get global balance manager instance
    
    Returns:
        BalanceManager: Global instance, or None if not initialized
    """
    return _global_balance_manager
