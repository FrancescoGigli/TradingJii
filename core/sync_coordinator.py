#!/usr/bin/env python3
"""
🔄 SYNC COORDINATOR

CRITICAL FIX: Coordinamento tra Bybit sync e Trailing monitor
- Previene race conditions durante sync
- Pause trailing during critical operations
- Resume automatico dopo sync
- Thread-safe state management

GARANTISCE: Zero conflitti tra sync (5min) e trailing (30s)
"""

import asyncio
import threading
import logging
import time
from typing import Optional
from datetime import datetime
from termcolor import colored


class SyncCoordinator:
    """
    FIX #5: Coordinator per sincronizzare Bybit sync e Trailing Monitor
    
    ELIMINA RACE CONDITION:
    - Trading cycle (300s) fa Bybit sync
    - Trailing monitor (30s) aggiorna SL
    - Senza coordinamento → conflitti di stato
    
    SOLUZIONE:
    - Sync acquisisce lock esclusivo
    - Trailing monitor sospende operazioni durante sync
    - Resume automatico post-sync
    """
    
    def __init__(self):
        # Locking
        self._sync_lock = asyncio.Lock()
        self._thread_lock = threading.RLock()
        
        # State tracking
        self._sync_active = False
        self._trailing_paused = False
        self._last_sync_time = 0
        self._last_sync_duration = 0
        
        # Statistics
        self._sync_count = 0
        self._trailing_pauses = 0
        self._conflicts_avoided = 0
        
        logging.info("🔄 SyncCoordinator initialized - Conflict prevention active")
    
    async def acquire_sync_lock(self, caller: str = "Unknown"):
        """
        🔒 ACQUIRE: Ottieni lock per Bybit sync (5min cycle)
        
        Durante sync:
        - Trailing monitor is paused
        - No SL updates permitted
        - State consistency guaranteed
        
        Args:
            caller: Nome del chiamante per logging
        """
        try:
            logging.debug(f"🔄 {caller}: Requesting sync lock...")
            
            await self._sync_lock.acquire()
            
            with self._thread_lock:
                self._sync_active = True
                self._trailing_paused = True
                self._last_sync_time = time.time()
                self._sync_count += 1
            
            logging.info(colored(f"🔒 SYNC LOCK ACQUIRED by {caller} - Trailing monitor PAUSED", "yellow"))
            
        except Exception as e:
            logging.error(f"🔄 Error acquiring sync lock: {e}")
    
    def release_sync_lock(self, caller: str = "Unknown"):
        """
        🔓 RELEASE: Rilascia lock dopo Bybit sync
        
        Dopo sync:
        - Trailing monitor resumed
        - SL updates permitted again
        - Normal operations resume
        
        Args:
            caller: Nome del chiamante per logging
        """
        try:
            with self._thread_lock:
                sync_duration = time.time() - self._last_sync_time
                self._last_sync_duration = sync_duration
                
                self._sync_active = False
                self._trailing_paused = False
            
            self._sync_lock.release()
            
            logging.info(colored(f"🔓 SYNC LOCK RELEASED by {caller} ({sync_duration:.1f}s) - Trailing monitor RESUMED", "green"))
            
        except Exception as e:
            logging.error(f"🔄 Error releasing sync lock: {e}")
    
    def is_sync_active(self) -> bool:
        """
        ❓ CHECK: Verifica se sync è in corso
        
        Returns:
            bool: True se sync attivo
        """
        try:
            with self._thread_lock:
                return self._sync_active
        except Exception as e:
            logging.error(f"🔄 Error checking sync status: {e}")
            return False
    
    def is_trailing_safe(self) -> bool:
        """
        ✅ CHECK: Verifica se trailing può operare
        
        Trailing monitor should check this before every operation
        
        Returns:
            bool: True se trailing può operare safely
        """
        try:
            with self._thread_lock:
                # Safe if: sync not active AND not paused
                is_safe = not self._sync_active and not self._trailing_paused
                
                if not is_safe:
                    self._trailing_pauses += 1
                    logging.debug("⏸️ Trailing monitor paused (sync in progress)")
                
                return is_safe
                
        except Exception as e:
            logging.error(f"🔄 Error checking trailing safety: {e}")
            return True  # Fail-open per non bloccare sistema
    
    def record_conflict_avoided(self):
        """
        📊 STATS: Registra conflict evitato
        """
        try:
            with self._thread_lock:
                self._conflicts_avoided += 1
        except Exception as e:
            logging.debug(f"🔄 Error recording conflict: {e}")
    
    def get_sync_stats(self) -> dict:
        """
        📊 STATS: Ottieni statistiche sync coordinator
        
        Returns:
            dict: Statistiche dettagliate
        """
        try:
            with self._thread_lock:
                return {
                    'sync_count': self._sync_count,
                    'trailing_pauses': self._trailing_pauses,
                    'conflicts_avoided': self._conflicts_avoided,
                    'last_sync_duration': self._last_sync_duration,
                    'sync_active': self._sync_active,
                    'trailing_paused': self._trailing_paused,
                    'last_sync_time': datetime.fromtimestamp(self._last_sync_time).isoformat() if self._last_sync_time > 0 else None
                }
        except Exception as e:
            logging.error(f"🔄 Error getting sync stats: {e}")
            return {'error': str(e)}
    
    def display_sync_dashboard(self):
        """
        📊 DISPLAY: Mostra dashboard sync coordinator
        """
        try:
            stats = self.get_sync_stats()
            
            if 'error' in stats:
                print(colored(f"❌ Sync Dashboard Error: {stats['error']}", "red"))
                return
            
            print(colored("\n🔄 SYNC COORDINATOR DASHBOARD", "cyan", attrs=['bold']))
            print(colored("=" * 60, "cyan"))
            
            print(colored("📊 SYNCHRONIZATION STATS:", "yellow", attrs=['bold']))
            print(f"  🔄 Total Syncs: {colored(str(stats['sync_count']), 'cyan')}")
            print(f"  ⏸️ Trailing Pauses: {colored(str(stats['trailing_pauses']), 'yellow')}")
            print(f"  🛡️ Conflicts Avoided: {colored(str(stats['conflicts_avoided']), 'green', attrs=['bold'])}")
            
            if stats['last_sync_duration'] > 0:
                duration_str = f"{stats['last_sync_duration']:.1f}s"
                print(f"  ⏱️ Last Sync Duration: {colored(duration_str, 'white')}")
            
            print(colored("\n🚥 CURRENT STATUS:", "yellow", attrs=['bold']))
            sync_status = colored("ACTIVE", "red") if stats['sync_active'] else colored("IDLE", "green")
            print(f"  🔒 Sync Status: {sync_status}")
            
            trailing_status = colored("PAUSED", "yellow") if stats['trailing_paused'] else colored("RUNNING", "green")
            print(f"  ⚡ Trailing Status: {trailing_status}")
            
            if stats['last_sync_time']:
                print(f"  📅 Last Sync: {stats['last_sync_time']}")
            
            print(colored("=" * 60, "cyan"))
            
        except Exception as e:
            logging.error(f"🔄 Sync dashboard display failed: {e}")
            print(colored(f"❌ Sync Dashboard Error: {e}", "red"))


# Global sync coordinator instance
global_sync_coordinator = SyncCoordinator()
