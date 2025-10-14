#!/usr/bin/env python3
"""
🎪 INTEGRATED TRAILING MONITOR

Integrated trailing stop monitor with:
- Robust error handling and retry logic
- 30-second update interval
- Auto-fix stop losses every 5 minutes
- Integration with dashboard and statistics
- Non-blocking operation

Runs as parallel asyncio task alongside main trading cycle
"""

import logging
import asyncio
import time
from datetime import datetime
from typing import Optional
import ccxt.async_support as ccxt


class IntegratedTrailingMonitor:
    """
    Integrated trailing monitor with robust error handling
    
    Features:
    - Updates trailing stops every 30s
    - Auto-fix SL every 5 minutes
    - Retry logic for network errors
    - Tracks newly closed positions for statistics
    - Non-blocking parallel execution
    """
    
    def __init__(self, position_manager, session_stats=None):
        self.position_manager = position_manager
        self.session_stats = session_stats
        
        # Timing trackers
        self.last_trailing_update = 0
        self.last_autofix_time = 0
        self.cycle_count = 0
        
        # Error tracking
        self.consecutive_errors = 0
        self.MAX_CONSECUTIVE_ERRORS = 5
        
        # Configuration
        self.UPDATE_INTERVAL = 30  # 30 seconds
        self.AUTOFIX_INTERVAL = 300  # 5 minutes
        
        logging.info("🎪 IntegratedTrailingMonitor initialized (30s interval)")
    
    async def run_monitor_loop(self, exchange):
        """
        Main monitoring loop - runs continuously in parallel
        
        Args:
            exchange: Bybit exchange instance
        """
        logging.info("🎪 TRAILING MONITOR: Started (integrated mode)")
        
        while True:
            try:
                self.cycle_count += 1
                current_time = time.time()
                
                # 1. CHECK FOR NEWLY CLOSED POSITIONS (update stats)
                await self._check_and_update_closed_positions(exchange)
                
                # 2. UPDATE TRAILING STOPS (every 30s)
                updates_count = await self._update_trailing_stops_safe(exchange)
                
                if updates_count > 0:
                    logging.info(f"🎪 Trailing: {updates_count} positions updated (cycle #{self.cycle_count})")
                else:
                    logging.debug(f"🎪 Trailing: No updates needed (cycle #{self.cycle_count})")
                
                # 3. AUTO-FIX STOP LOSSES (every 5 minutes)
                if current_time - self.last_autofix_time >= self.AUTOFIX_INTERVAL:
                    fixed_count = await self._autofix_stop_losses_safe(exchange)
                    
                    if fixed_count > 0:
                        logging.info(f"🔧 Auto-Fix: Corrected {fixed_count} stop losses")
                    
                    self.last_autofix_time = current_time
                
                # 4. Reset error counter on success
                self.consecutive_errors = 0
                
                # 5. Wait for next cycle
                await asyncio.sleep(self.UPDATE_INTERVAL)
                
            except ccxt.NetworkError as net_error:
                await self._handle_network_error(net_error)
                
            except Exception as e:
                await self._handle_general_error(e)
    
    async def _update_trailing_stops_safe(self, exchange) -> int:
        """
        Update trailing stops with error handling
        
        Returns:
            int: Number of positions updated
        """
        try:
            updates_count = await self.position_manager.update_trailing_stops(exchange)
            return updates_count
            
        except ccxt.NetworkError as e:
            logging.warning(f"Network error updating trailing stops: {e}")
            return 0
            
        except Exception as e:
            logging.error(f"Error updating trailing stops: {e}")
            return 0
    
    async def _autofix_stop_losses_safe(self, exchange) -> int:
        """
        Auto-fix stop losses with error handling
        
        Returns:
            int: Number of SL fixed
        """
        try:
            fixed_count = await self.position_manager.check_and_fix_stop_losses(exchange)
            return fixed_count
            
        except ccxt.NetworkError as e:
            logging.warning(f"Network error in auto-fix: {e}")
            return 0
            
        except Exception as e:
            logging.error(f"Error in auto-fix: {e}")
            return 0
    
    async def _check_and_update_closed_positions(self, exchange):
        """
        Check for newly closed positions and update statistics
        
        This method syncs with Bybit to detect positions that closed
        since last check, then updates session statistics.
        """
        if not self.session_stats:
            return  # No stats tracking
        
        try:
            # Sync with Bybit to detect newly closed
            newly_opened, newly_closed = await self.position_manager.thread_safe_sync_with_bybit(exchange)
            
            # Update statistics for each closed position
            for closed_position in newly_closed:
                self.session_stats.update_from_closed_position(closed_position)
                
            if newly_closed:
                logging.debug(f"📊 Updated stats for {len(newly_closed)} newly closed positions")
                
        except Exception as e:
            logging.error(f"Error checking closed positions: {e}")
    
    async def _handle_network_error(self, error):
        """Handle network errors with retry logic"""
        self.consecutive_errors += 1
        
        logging.warning(
            f"⚠️ Network error ({self.consecutive_errors}/{self.MAX_CONSECUTIVE_ERRORS}): {error}"
        )
        
        if self.consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
            logging.error(
                f"❌ Too many consecutive network errors ({self.consecutive_errors}) - "
                f"pausing trailing for 5 minutes"
            )
            await asyncio.sleep(300)  # Pause 5 minutes
            self.consecutive_errors = 0  # Reset after pause
        else:
            # Exponential backoff: 30s, 60s, 90s, 120s, 150s
            wait_time = self.UPDATE_INTERVAL * self.consecutive_errors
            logging.info(f"⏳ Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
    
    async def _handle_general_error(self, error):
        """Handle general errors"""
        self.consecutive_errors += 1
        
        logging.error(
            f"❌ Trailing monitor error ({self.consecutive_errors}/{self.MAX_CONSECUTIVE_ERRORS}): {error}",
            exc_info=True
        )
        
        if self.consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
            logging.error("❌ Too many consecutive errors - pausing for 5 minutes")
            await asyncio.sleep(300)
            self.consecutive_errors = 0
        else:
            # Wait and retry
            await asyncio.sleep(self.UPDATE_INTERVAL)
    
    def get_status(self) -> dict:
        """Get current monitor status"""
        return {
            'cycle_count': self.cycle_count,
            'consecutive_errors': self.consecutive_errors,
            'last_update': datetime.fromtimestamp(self.last_trailing_update).isoformat() if self.last_trailing_update > 0 else 'Never',
            'last_autofix': datetime.fromtimestamp(self.last_autofix_time).isoformat() if self.last_autofix_time > 0 else 'Never',
            'update_interval': self.UPDATE_INTERVAL,
            'autofix_interval': self.AUTOFIX_INTERVAL
        }


async def run_integrated_trailing_monitor(exchange, position_manager, session_stats=None):
    """
    Convenience function to run integrated trailing monitor
    
    Args:
        exchange: Bybit exchange instance
        position_manager: Position manager instance
        session_stats: Optional session statistics instance
    """
    monitor = IntegratedTrailingMonitor(position_manager, session_stats)
    await monitor.run_monitor_loop(exchange)
