#!/usr/bin/env python3
"""
🏥 ACCOUNT HEALTH MONITOR

Monitors API health and disables trading if account endpoints are failing.

CRITICAL FIX: Prevents trading with stale/missing balance/position data

FEATURES:
- Error tracking with sliding window
- Automatic trading disable on repeated failures
- Exponential backoff with jitter
- Health status reporting
"""

import logging
import time
import random
import asyncio
from typing import Optional, Dict, Tuple, Any, Callable
from datetime import datetime

class AccountHealthMonitor:
    """
    Monitor account API health and disable trading if degraded
    
    Prevents dangerous situations where trading continues without
    accurate balance/position information.
    """
    
    def __init__(self, error_threshold: int = 5, window_seconds: int = 120):
        """
        Initialize health monitor (OPTIMIZED: more tolerant to transient errors)
        
        Args:
            error_threshold: Number of errors before disabling trading (5 = balanced tolerance)
            window_seconds: Time window for error counting
        """
        self.error_threshold = error_threshold
        self.window_seconds = window_seconds
        self.error_log = []  # [(timestamp, error_type)]
        self.trading_disabled = False
        self.last_balance = None
        self.last_positions = None
        self.last_successful_fetch = {}  # {endpoint: timestamp}
        
        logging.info(f"🏥 AccountHealthMonitor initialized (threshold={error_threshold}, window={window_seconds}s)")
    
    def record_error(self, error_type: str, endpoint: str = "unknown"):
        """
        Record API error and check if threshold exceeded
        
        Args:
            error_type: Type of error (timeout, connection, etc)
            endpoint: API endpoint that failed
        """
        now = time.time()
        self.error_log.append((now, error_type, endpoint))
        
        # Clean old errors outside window
        cutoff = now - self.window_seconds
        self.error_log = [(t, e, ep) for t, e, ep in self.error_log if t > cutoff]
        
        # Check threshold
        if len(self.error_log) >= self.error_threshold:
            if not self.trading_disabled:
                self.trading_disabled = True
                logging.error(
                    f"🚨 TRADING DISABLED: {len(self.error_log)} account API errors "
                    f"in {self.window_seconds}s (threshold: {self.error_threshold})"
                )
                
                # Log error details
                recent_errors = self.error_log[-5:]
                for t, e, ep in recent_errors:
                    age = now - t
                    logging.error(f"   📍 {age:.1f}s ago: {e} on {ep}")
    
    def record_success(self, endpoint: str = "unknown"):
        """
        Record successful API call
        
        Args:
            endpoint: API endpoint that succeeded
        """
        now = time.time()
        self.last_successful_fetch[endpoint] = now
        
        # If trading was disabled and errors have cleared, re-enable
        if self.trading_disabled and len(self.error_log) == 0:
            self.trading_disabled = False
            logging.info("✅ Trading re-enabled: Account health restored")
    
    async def fetch_with_health_check(
        self, 
        exchange, 
        fetch_func: Callable, 
        endpoint: str = "unknown",
        *args, 
        **kwargs
    ) -> Tuple[Any, Optional[str]]:
        """
        Wrapper for fetch with health monitoring and backoff
        
        Args:
            exchange: Exchange instance
            fetch_func: Function to call (e.g., exchange.fetch_balance)
            endpoint: Endpoint name for tracking
            *args, **kwargs: Arguments for fetch_func
            
        Returns:
            Tuple[Any, Optional[str]]: (result, error)
        """
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Add jitter to avoid thundering herd
                if attempt > 0:
                    jitter = random.uniform(0, 0.5)
                    delay = base_delay * (2 ** attempt) + jitter
                    logging.debug(f"🔄 Retry {attempt+1}/{max_retries} after {delay:.2f}s")
                    await asyncio.sleep(delay)
                
                # Execute fetch
                result = await fetch_func(*args, **kwargs)
                
                # Success!
                self.record_success(endpoint)
                return result, None
            
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                
                logging.warning(
                    f"⚠️ {endpoint} error (attempt {attempt+1}/{max_retries}): "
                    f"{error_type} - {error_msg[:100]}"
                )
                
                # On final retry, record error
                if attempt == max_retries - 1:
                    self.record_error(error_type, endpoint)
                    return None, error_msg
        
        return None, "Max retries exceeded"
    
    def can_trade(self) -> bool:
        """
        Check if trading is allowed based on health status
        
        Returns:
            bool: True if trading enabled
        """
        return not self.trading_disabled
    
    def get_status(self) -> Dict:
        """
        Get detailed health status for monitoring
        
        Returns:
            Dict: Health status information
        """
        now = time.time()
        
        # Calculate time since last successful fetch for each endpoint
        time_since_fetch = {}
        for endpoint, timestamp in self.last_successful_fetch.items():
            time_since_fetch[endpoint] = now - timestamp
        
        return {
            'trading_enabled': not self.trading_disabled,
            'error_count': len(self.error_log),
            'error_threshold': self.error_threshold,
            'window_seconds': self.window_seconds,
            'recent_errors': [
                {'time_ago': now - t, 'type': e, 'endpoint': ep} 
                for t, e, ep in self.error_log[-5:]
            ],
            'time_since_fetch': time_since_fetch,
            'last_balance_cached': self.last_balance is not None,
            'last_positions_cached': self.last_positions is not None
        }
    
    def get_status_summary(self) -> str:
        """
        Get brief status summary for logging
        
        Returns:
            str: Status summary
        """
        status = self.get_status()
        
        if status['trading_enabled']:
            return f"✅ Healthy ({status['error_count']}/{status['error_threshold']} errors)"
        else:
            return f"🚨 DISABLED ({status['error_count']}/{status['error_threshold']} errors)"
    
    def force_disable(self, reason: str):
        """
        Manually disable trading with a reason
        
        Args:
            reason: Reason for manual disable
        """
        self.trading_disabled = True
        logging.warning(f"⚠️ Trading manually disabled: {reason}")
    
    def force_enable(self):
        """
        Manually re-enable trading (clears errors)
        """
        self.error_log.clear()
        self.trading_disabled = False
        logging.info("✅ Trading manually re-enabled")
    
    def update_cache(self, balance: Optional[Dict] = None, positions: Optional[list] = None):
        """
        Update cached balance/positions for monitoring
        
        Args:
            balance: Balance dict from exchange
            positions: Positions list from exchange
        """
        if balance is not None:
            self.last_balance = balance
            logging.debug("💰 Balance cache updated")
        
        if positions is not None:
            self.last_positions = positions
            logging.debug("📊 Positions cache updated")
    
    def get_cached_data(self) -> Tuple[Optional[Dict], Optional[list]]:
        """
        Get cached balance/positions (fallback if fetch fails)
        
        Returns:
            Tuple[Optional[Dict], Optional[list]]: (balance, positions)
        """
        return self.last_balance, self.last_positions


# Global instance
global_health_monitor = AccountHealthMonitor()
