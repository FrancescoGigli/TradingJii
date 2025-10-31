#!/usr/bin/env python3
"""
🔄 UPDATE MANAGER

Gestisce aggiornamenti dashboard e cache per ottimizzare performance.
Riduce chiamate ridondanti e mantiene dati sincronizzati.
"""

import time
import logging
from typing import Dict, List, Optional
import asyncio


class UpdateManager:
    """Gestisce cache e aggiornamenti del dashboard"""
    
    def __init__(self, cache_ttl: int = 15):
        """
        Args:
            cache_ttl: Time-to-live della cache in secondi (default: 15s)
        """
        self.cache_ttl = cache_ttl
        
        # Cache separate per ogni tipo di dato
        self._cached_synced = []
        self._cached_session = []
        self._cached_closed = []
        self._cached_stats = {}
        
        # Timestamp ultimo aggiornamento
        self._cache_time = 0
        
        # Track last data hash per evitare update non necessari
        self._last_data_hash = {
            'synced': 0,
            'session': 0,
            'closed': 0
        }
        
        logging.debug(f"UpdateManager initialized with cache TTL: {cache_ttl}s")
    
    def should_refresh_cache(self) -> bool:
        """
        Determina se la cache deve essere aggiornata
        
        Returns:
            True se cache è scaduta, False altrimenti
        """
        current_time = time.time()
        elapsed = current_time - self._cache_time
        
        return elapsed >= self.cache_ttl
    
    def update_cache(self, position_manager):
        """
        Aggiorna cache con dati freschi dal position manager
        
        Args:
            position_manager: Position manager da cui leggere dati
        """
        current_time = time.time()
        
        try:
            # Fetch fresh data
            self._cached_synced = position_manager.safe_get_positions_by_origin("SYNCED")
            self._cached_session = position_manager.safe_get_positions_by_origin("SESSION")
            self._cached_closed = position_manager.safe_get_closed_positions()
            
            # Update timestamp
            self._cache_time = current_time
            
            # Calculate new hashes
            self._update_data_hashes()
            
            logging.debug(
                f"Cache updated: {len(self._cached_synced)} synced, "
                f"{len(self._cached_session)} session, "
                f"{len(self._cached_closed)} closed"
            )
            
        except Exception as e:
            logging.error(f"Error updating cache: {e}")
    
    def _update_data_hashes(self):
        """Aggiorna hash dei dati per detect changes"""
        try:
            self._last_data_hash['synced'] = hash(tuple(
                (p.symbol, p.position_size, p.unrealized_pnl_usd) 
                for p in self._cached_synced
            ))
            
            self._last_data_hash['session'] = hash(tuple(
                (p.symbol, p.position_size, p.unrealized_pnl_usd) 
                for p in self._cached_session
            ))
            
            self._last_data_hash['closed'] = hash(tuple(
                (t.symbol, t.pnl_usd) 
                for t in self._cached_closed
            ))
        except Exception as e:
            logging.debug(f"Error calculating data hashes: {e}")
    
    def get_cached_positions(self, data_type: str) -> List:
        """
        Ottiene posizioni dalla cache
        
        Args:
            data_type: 'synced', 'session', 'all_active', or 'closed'
            
        Returns:
            Lista di posizioni cached
        """
        if data_type == 'synced':
            return self._cached_synced
        elif data_type == 'session':
            return self._cached_session
        elif data_type == 'all_active':
            return self._cached_synced + self._cached_session
        elif data_type == 'closed':
            return self._cached_closed
        else:
            logging.warning(f"Unknown data type: {data_type}")
            return []
    
    def get_cache_info(self) -> Dict:
        """
        Ottiene info sullo stato della cache
        
        Returns:
            Dict con: age, is_valid, counts
        """
        current_time = time.time()
        cache_age = current_time - self._cache_time
        is_valid = cache_age < self.cache_ttl
        
        return {
            'age_seconds': cache_age,
            'is_valid': is_valid,
            'ttl': self.cache_ttl,
            'counts': {
                'synced': len(self._cached_synced),
                'session': len(self._cached_session),
                'closed': len(self._cached_closed),
            }
        }
    
    async def async_update_all(self, update_callback, current_balance: float):
        """
        Aggiorna dashboard in modo asincrono (non-blocking)
        
        Args:
            update_callback: Callback da chiamare per ogni sezione
            current_balance: Balance corrente
        """
        try:
            # Update in chunks per mantenere GUI responsive
            await update_callback('header')
            await asyncio.sleep(0)  # Yield to event loop
            
            await update_callback('stats', current_balance)
            await asyncio.sleep(0)
            
            await update_callback('positions')
            await asyncio.sleep(0)
            
            await update_callback('closed')
            await asyncio.sleep(0)
            
            await update_callback('footer')
            
        except Exception as e:
            logging.error(f"Error in async update: {e}")
    
    def force_cache_refresh(self):
        """Forza refresh immediato della cache al prossimo update"""
        self._cache_time = 0
        logging.debug("Cache refresh forced")
    
    def clear_cache(self):
        """Pulisce completamente la cache"""
        self._cached_synced = []
        self._cached_session = []
        self._cached_closed = []
        self._cached_stats = {}
        self._cache_time = 0
        self._last_data_hash = {
            'synced': 0,
            'session': 0,
            'closed': 0
        }
        logging.debug("Cache cleared")
    
    def data_has_changed(self, data_type: str) -> bool:
        """
        Verifica se i dati sono cambiati dall'ultimo update
        
        Args:
            data_type: 'synced', 'session', or 'closed'
            
        Returns:
            True se dati sono cambiati
        """
        try:
            if data_type == 'synced':
                new_hash = hash(tuple(
                    (p.symbol, p.position_size, p.unrealized_pnl_usd) 
                    for p in self._cached_synced
                ))
                return new_hash != self._last_data_hash.get('synced', 0)
                
            elif data_type == 'session':
                new_hash = hash(tuple(
                    (p.symbol, p.position_size, p.unrealized_pnl_usd) 
                    for p in self._cached_session
                ))
                return new_hash != self._last_data_hash.get('session', 0)
                
            elif data_type == 'closed':
                new_hash = hash(tuple(
                    (t.symbol, t.pnl_usd) 
                    for t in self._cached_closed
                ))
                return new_hash != self._last_data_hash.get('closed', 0)
                
        except Exception as e:
            logging.debug(f"Error checking data changes: {e}")
            return True  # Assume changed on error
        
        return True
