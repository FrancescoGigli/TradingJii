#!/usr/bin/env python3
"""
⏰ TIME SYNC MANAGER

CRITICAL FIX: Auto-recovery da timestamp desync
- Rileva errori 10002 (invalid timestamp)
- Re-sincronizza automaticamente con Bybit
- Retry automatico dopo sync
- Logging dettagliato per debugging

GARANTISCE: Bot continua a funzionare anche con drift temporale
"""

import logging
import time
import asyncio
from typing import Callable, Any, Optional
from functools import wraps
from termcolor import colored

class TimeSyncManager:
    """
    Gestisce la sincronizzazione temporale con Bybit e auto-recovery
    
    FEATURES:
    - Auto-detect timestamp errors (retCode 10002)
    - Automatic re-sync with Bybit server
    - Retry failed operations after sync
    - Performance tracking
    """
    
    def __init__(self):
        self._sync_count = 0
        self._error_count = 0
        self._last_sync_time = 0
        self._sync_success_rate = 100.0
    
    async def initialize_exchange_time_sync(self, exchange) -> bool:
        """
        Initialize exchange time synchronization (for startup)
        
        CRITICAL FIX: Override exchange.milliseconds() method to apply offset automatically
        
        This method performs the initial time sync with retry logic,
        using configuration from config.py for consistency.
        
        Args:
            exchange: ccxt exchange instance
            
        Returns:
            bool: True if sync successful
        """
        import config
        
        # Import configuration (avoid circular imports)
        max_retries = getattr(config, 'TIME_SYNC_MAX_RETRIES', 5)
        retry_delay = getattr(config, 'TIME_SYNC_RETRY_DELAY', 3)
        recv_window_normal = getattr(config, 'TIME_SYNC_NORMAL_RECV_WINDOW', 300000)
        manual_offset = getattr(config, 'MANUAL_TIME_OFFSET', 0)
        
        sync_success = False
        final_offset = 0
        
        for attempt in range(1, max_retries + 1):
            try:
                # Fetch server time using public API
                server_time = await exchange.fetch_time()
                local_time = int(time.time() * 1000)  # Use raw local time for calculation
                
                # Calculate time difference
                time_diff = server_time - local_time
                
                # Apply manual offset if configured
                if manual_offset is not None:
                    time_diff += manual_offset
                
                # Store the time difference
                final_offset = time_diff
                
                # Verify the sync by fetching time again
                await asyncio.sleep(0.5)  # Small delay for network latency
                verify_server_time = await exchange.fetch_time()
                verify_local_time = int(time.time() * 1000)
                verify_adjusted_time = verify_local_time + time_diff
                verify_diff = abs(verify_server_time - verify_adjusted_time)
                
                # Accept if difference is less than 2 seconds
                if verify_diff < 2000:
                    self._sync_count += 1
                    self._last_sync_time = time.time()
                    self._sync_success_rate = (self._sync_count / (self._sync_count + self._error_count)) * 100
                    
                    logging.info(colored(f"✅ Time sync OK (offset: {time_diff}ms)", "green"))
                    sync_success = True
                    break
                else:
                    logging.debug(f"⚠️ Verification failed: adjusted diff {verify_diff}ms")
                    if attempt < max_retries:
                        delay = retry_delay * attempt  # Exponential backoff
                        await asyncio.sleep(delay)
                        
            except Exception as e:
                self._error_count += 1
                logging.error(f"❌ Sync attempt {attempt} failed: {e}")
                if attempt < max_retries:
                    delay = retry_delay * attempt
                    await asyncio.sleep(delay)
        
        if sync_success:
            # 🔧 CRITICAL FIX: Override milliseconds() method to apply offset automatically
            def fixed_milliseconds():
                return int(time.time() * 1000 + final_offset)
            
            exchange.milliseconds = fixed_milliseconds
            
            # Store offset in options for reference
            exchange.options['timeDifference'] = final_offset
            
            # Set recv_window for normal operations
            exchange.options['recvWindow'] = recv_window_normal
            
            logging.debug(colored(f"🔧 Overridden exchange.milliseconds() with offset: {final_offset}ms", "cyan"))
        
        return sync_success
        
    def is_timestamp_error(self, error_msg: str) -> bool:
        """
        Verifica se l'errore è un timestamp desync
        
        Args:
            error_msg: Messaggio di errore da Bybit
            
        Returns:
            bool: True se è un timestamp error
        """
        error_str = str(error_msg).lower()
        
        # Check for retCode 10002 or timestamp-related keywords
        return (
            '"retcode":10002' in error_str or
            'retcode: 10002' in error_str or
            'timestamp' in error_str or
            'recv_window' in error_str
        )
    
    async def force_time_sync(self, exchange) -> bool:
        """
        Forza re-sincronizzazione con Bybit server
        
        CRITICAL FIX: Also override milliseconds() method during re-sync
        
        Args:
            exchange: ccxt exchange instance
            
        Returns:
            bool: True se sync riuscito
        """
        try:
            self._sync_count += 1
            
            logging.info(colored(
                f"⏰ FORCING TIME SYNC (attempt #{self._sync_count})...",
                "yellow", attrs=['bold']
            ))
            
            # Get Bybit server time
            response = await exchange.public_get_v5_market_time()
            
            if response and 'result' in response:
                server_time = int(response['result']['timeSecond']) * 1000  # Convert to ms
                local_time = int(time.time() * 1000)
                time_diff = server_time - local_time
                
                # 🔧 CRITICAL FIX: Override milliseconds() method to apply offset automatically
                def fixed_milliseconds():
                    return int(time.time() * 1000 + time_diff)
                
                exchange.milliseconds = fixed_milliseconds
                
                # Update exchange config with new time difference
                exchange.options['timeDifference'] = time_diff
                
                self._last_sync_time = time.time()
                self._sync_success_rate = (self._sync_count / (self._sync_count + self._error_count)) * 100
                
                logging.info(colored(
                    f"✅ TIME SYNC SUCCESS: Offset {time_diff}ms | "
                    f"Success rate: {self._sync_success_rate:.1f}%",
                    "green", attrs=['bold']
                ))
                logging.debug(colored(f"🔧 Re-overridden exchange.milliseconds() with offset: {time_diff}ms", "cyan"))
                
                return True
            else:
                self._error_count += 1
                logging.error(f"❌ TIME SYNC FAILED: Invalid response from Bybit")
                return False
                
        except Exception as e:
            self._error_count += 1
            self._sync_success_rate = (self._sync_count / (self._sync_count + self._error_count)) * 100
            logging.error(f"❌ TIME SYNC EXCEPTION: {e}")
            return False
    
    async def execute_with_auto_recovery(self, exchange, func: Callable, *args, max_retries: int = 3, **kwargs) -> Any:
        """
        Esegue una funzione con auto-recovery da timestamp errors
        
        Args:
            exchange: ccxt exchange instance
            func: Funzione da eseguire (può essere sync o async)
            max_retries: Numero massimo di retry dopo sync
            *args, **kwargs: Argomenti per la funzione
            
        Returns:
            Any: Risultato della funzione
            
        Raises:
            Exception: Se tutti i retry falliscono
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Execute function (handle both sync and async)
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                return result
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                # Check if it's a timestamp error
                if self.is_timestamp_error(error_msg):
                    logging.warning(colored(
                        f"⚠️ TIMESTAMP ERROR DETECTED (attempt {attempt + 1}/{max_retries}): {error_msg[:100]}",
                        "yellow"
                    ))
                    
                    # Force time sync
                    sync_success = await self.force_time_sync(exchange)
                    
                    if sync_success:
                        logging.info(f"🔄 RETRYING operation after time sync...")
                        await asyncio.sleep(1)  # Brief pause before retry
                        continue
                    else:
                        logging.error(f"❌ Time sync failed, cannot retry")
                        raise
                else:
                    # Not a timestamp error, propagate immediately
                    raise
        
        # All retries exhausted
        logging.error(colored(
            f"❌ ALL RETRIES EXHAUSTED: {last_error}",
            "red", attrs=['bold']
        ))
        raise last_error
    
    def get_stats(self) -> dict:
        """
        Ottieni statistiche sincronizzazione
        
        Returns:
            dict: Statistiche sync
        """
        return {
            'sync_count': self._sync_count,
            'error_count': self._error_count,
            'success_rate': self._sync_success_rate,
            'last_sync_time': self._last_sync_time,
            'seconds_since_sync': time.time() - self._last_sync_time if self._last_sync_time > 0 else 0
        }


# Global time sync manager instance
global_time_sync_manager = TimeSyncManager()


def with_auto_recovery(max_retries: int = 3):
    """
    Decorator per aggiungere auto-recovery a funzioni async
    
    Usage:
        @with_auto_recovery(max_retries=3)
        async def my_api_call(exchange, symbol):
            return await exchange.fetch_ticker(symbol)
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find exchange instance in args
            exchange = None
            for arg in args:
                if hasattr(arg, 'fetch_ticker'):  # Duck typing for exchange
                    exchange = arg
                    break
            
            if exchange is None:
                # No exchange found, execute normally
                return await func(*args, **kwargs)
            
            # Execute with auto-recovery
            return await global_time_sync_manager.execute_with_auto_recovery(
                exchange, func, *args, max_retries=max_retries, **kwargs
            )
        
        return wrapper
    return decorator
