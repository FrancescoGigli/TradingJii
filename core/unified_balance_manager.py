#!/usr/bin/env python3
"""
💰 UNIFIED BALANCE MANAGER

CRITICAL FIX: Single source of truth per balance management
- Eliminazione delle 7 fonti diverse di balance
- Atomic operations per allocazioni margin
- Real-time sync con Bybit
- Protection contro overexposure
- Thread-safe balance operations

GARANTISCE: Calcoli balance consistency, zero overexposure risk
"""

import threading
import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from termcolor import colored


class UnifiedBalanceManager:
    """
    CRITICAL FIX: Single source of truth per balance management
    
    ELIMINA FONTI MULTIPLE:
    1. SmartPositionManager.session_balance  ❌
    2. SmartPositionManager.real_balance_cache  ❌  
    3. SmartPositionManager.session_start_balance  ❌
    4. RiskCalculator balance parameter  ❌
    5. RealTimeDisplay._get_total_wallet_balance()  ❌
    6. TradeManager.get_real_balance()  ❌
    7. ConfigManager DEMO_BALANCE  ❌
    
    SOSTITUISCE CON:
    ✅ Single UnifiedBalanceManager instance
    ✅ Atomic balance operations
    ✅ Real-time Bybit sync
    ✅ Overexposure protection
    """
    
    def __init__(self, demo_mode: bool = False, demo_balance: float = 1000.0):
        # THREAD SAFETY
        self._lock = threading.RLock()  # Reentrant lock for nested operations
        
        # SINGLE SOURCE OF TRUTH
        self._real_balance = demo_balance if demo_mode else 0.0
        self._allocated_margin = 0.0  # Currently allocated margin
        self._reserved_margin = 0.0   # Reserved for pending orders
        self._session_start_balance = demo_balance if demo_mode else 0.0
        
        # Mode tracking
        self._demo_mode = demo_mode
        self._demo_balance = demo_balance
        
        # Balance history for tracking
        self._balance_history = []
        self._last_bybit_sync = None
        self._sync_failures = 0
        
        # Performance tracking
        self._allocation_count = 0
        self._release_count = 0
        self._overexposure_prevented = 0
        
        # Cache for frequent operations
        self._available_balance_cache = 0.0
        self._cache_timestamp = 0
        self._cache_ttl = 1.0  # 1 second cache for performance
        

    
    # ========================================
    # CORE BALANCE OPERATIONS (Atomic)
    # ========================================
    
    def atomic_allocate_margin(self, amount: float, description: str = "") -> bool:
        """
        💰 ATOMIC: Alloca margin per nuovo trade (operazione critica)
        
        Args:
            amount: Amount di margin da allocare
            description: Descrizione dell'allocazione (per logging)
            
        Returns:
            bool: True se allocazione riuscita, False se insufficient balance
        """
        try:
            with self._lock:
                available = self._real_balance - self._allocated_margin - self._reserved_margin
                
                if available >= amount:
                    self._allocated_margin += amount
                    self._allocation_count += 1
                    
                    logging.info(f"💰 Margin allocated: ${amount:.2f} ({description}) - Available: ${available - amount:.2f}")
                    self._invalidate_cache()
                    return True
                else:
                    self._overexposure_prevented += 1
                    logging.warning(f"💰 OVEREXPOSURE PREVENTED: Requested ${amount:.2f}, Available ${available:.2f} ({description})")
                    return False
                    
        except Exception as e:
            logging.error(f"💰 Margin allocation failed: {e}")
            return False
    
    def atomic_release_margin(self, amount: float, pnl_usd: float = 0.0, description: str = "") -> bool:
        """
        💰 ATOMIC: Rilascia margin da trade chiuso (operazione critica)
        
        Args:
            amount: Amount di margin da rilasciare
            pnl_usd: PnL del trade (può essere negativo)
            description: Descrizione del rilascio
            
        Returns:
            bool: True se rilascio riuscito
        """
        try:
            with self._lock:
                # Release allocated margin
                self._allocated_margin = max(0, self._allocated_margin - amount)
                self._release_count += 1
                
                # Apply PnL to real balance
                old_balance = self._real_balance
                self._real_balance += pnl_usd
                
                # Prevent negative balance in demo mode
                if self._demo_mode and self._real_balance < 0:
                    logging.warning(f"💰 Demo balance would go negative: ${self._real_balance:.2f}, clamping to 0")
                    self._real_balance = 0.0
                
                available_after = self._real_balance - self._allocated_margin - self._reserved_margin
                
                logging.info(f"💰 Margin released: ${amount:.2f} + PnL ${pnl_usd:+.2f} ({description})")
                logging.info(f"💰 Balance: ${old_balance:.2f} → ${self._real_balance:.2f}, Available: ${available_after:.2f}")
                
                self._invalidate_cache()
                return True
                
        except Exception as e:
            logging.error(f"💰 Margin release failed: {e}")
            return False
    
    def atomic_reserve_margin(self, amount: float, description: str = "") -> bool:
        """
        💰 ATOMIC: Riserva margin per ordine pending
        
        Args:
            amount: Amount da riservare temporaneamente
            description: Descrizione della prenotazione
            
        Returns:
            bool: True se reservazione riuscita
        """
        try:
            with self._lock:
                available = self._real_balance - self._allocated_margin - self._reserved_margin
                
                if available >= amount:
                    self._reserved_margin += amount
                    logging.debug(f"💰 Margin reserved: ${amount:.2f} ({description})")
                    self._invalidate_cache()
                    return True
                else:
                    logging.warning(f"💰 Insufficient balance for reservation: ${amount:.2f} > ${available:.2f}")
                    return False
                    
        except Exception as e:
            logging.error(f"💰 Margin reservation failed: {e}")
            return False
    
    def atomic_release_reservation(self, amount: float, description: str = "") -> bool:
        """
        💰 ATOMIC: Rilascia reservation (ordine completato/cancellato)
        
        Args:
            amount: Amount da rilasciare dalla reservazione
            description: Descrizione del rilascio
            
        Returns:
            bool: True se rilascio riuscito
        """
        try:
            with self._lock:
                self._reserved_margin = max(0, self._reserved_margin - amount)
                logging.debug(f"💰 Reservation released: ${amount:.2f} ({description})")
                self._invalidate_cache()
                return True
                
        except Exception as e:
            logging.error(f"💰 Reservation release failed: {e}")
            return False
    
    # ========================================
    # BALANCE QUERIES (Fast, Cached)
    # ========================================
    
    def get_available_balance(self) -> float:
        """
        💰 FAST: Ottieni balance disponibile (con cache per performance)
        
        Returns:
            float: Balance disponibile per nuovi trade
        """
        try:
            current_time = time.time()
            
            # Check cache validity
            if (current_time - self._cache_timestamp) < self._cache_ttl:
                return self._available_balance_cache
            
            # Calculate fresh available balance
            with self._lock:
                available = max(0, self._real_balance - self._allocated_margin - self._reserved_margin)
                
                # Update cache
                self._available_balance_cache = available
                self._cache_timestamp = current_time
                
                return available
                
        except Exception as e:
            logging.error(f"💰 Available balance query failed: {e}")
            return 0.0
    
    def get_total_balance(self) -> float:
        """
        💰 FAST: Ottieni balance totale
        
        Returns:
            float: Balance totale (real balance)
        """
        try:
            with self._lock:
                return self._real_balance
        except Exception as e:
            logging.error(f"💰 Total balance query failed: {e}")
            return 0.0
    
    def get_allocated_margin(self) -> float:
        """
        💰 FAST: Ottieni margin attualmente allocato
        
        Returns:
            float: Margin allocato per posizioni attive
        """
        try:
            with self._lock:
                return self._allocated_margin
        except Exception as e:
            logging.error(f"💰 Allocated margin query failed: {e}")
            return 0.0
    
    def get_balance_summary(self) -> Dict:
        """
        💰 FAST: Ottieni summary completo balance
        
        Returns:
            Dict: Summary dettagliato balance status
        """
        try:
            with self._lock:
                available = self._real_balance - self._allocated_margin - self._reserved_margin
                allocation_pct = (self._allocated_margin / self._real_balance * 100) if self._real_balance > 0 else 0
                
                return {
                    'mode': 'DEMO' if self._demo_mode else 'LIVE',
                    'total_balance': self._real_balance,
                    'allocated_margin': self._allocated_margin,
                    'reserved_margin': self._reserved_margin,
                    'available_balance': max(0, available),
                    'allocation_percentage': allocation_pct,
                    'session_pnl': self._real_balance - self._session_start_balance,
                    'session_pnl_pct': ((self._real_balance - self._session_start_balance) / self._session_start_balance * 100) if self._session_start_balance > 0 else 0,
                    'last_bybit_sync': self._last_bybit_sync,
                    'operations_count': self._allocation_count + self._release_count,
                    'overexposure_prevented': self._overexposure_prevented
                }
                
        except Exception as e:
            logging.error(f"💰 Balance summary failed: {e}")
            return {'error': str(e)}
    
    # ========================================
    # BYBIT SYNC OPERATIONS (Live Mode)
    # ========================================
    
    async def sync_balance_with_bybit(self, exchange) -> bool:
        """
        💰 SYNC: Sincronizza balance con Bybit (solo LIVE mode)
        
        Args:
            exchange: Bybit exchange instance
            
        Returns:
            bool: True se sync riuscito
        """
        if self._demo_mode:
            logging.debug("💰 Demo mode - skipping Bybit balance sync")
            return True
        
        try:
            # Get real balance from Bybit (outside lock per minimizzare lock time)
            balance_data = await exchange.fetch_balance()
            
            if not isinstance(balance_data, dict):
                logging.error(f"💰 Invalid balance response from Bybit: {type(balance_data)}")
                self._sync_failures += 1
                return False
            
            # Extract USDT balance (try multiple sources)
            usdt_balance = None
            source_used = "unknown"
            
            # Try Unified Account balance first
            try:
                if 'info' in balance_data and isinstance(balance_data['info'], dict):
                    info_data = balance_data['info']
                    if 'result' in info_data and isinstance(info_data['result'], dict):
                        result_data = info_data['result']
                        if 'list' in result_data and isinstance(result_data['list'], list) and len(result_data['list']) > 0:
                            account_data = result_data['list'][0]
                            
                            if 'totalWalletBalance' in account_data and account_data['totalWalletBalance']:
                                usdt_balance = float(account_data['totalWalletBalance'])
                                source_used = "totalWalletBalance"
                            elif 'totalEquity' in account_data and account_data['totalEquity']:
                                usdt_balance = float(account_data['totalEquity'])
                                source_used = "totalEquity"
            except Exception as nested_error:
                logging.debug(f"💰 Could not extract from nested structure: {nested_error}")
            
            # Fallback to direct keys
            if usdt_balance is None:
                for key in ['totalWalletBalance', 'totalEquity', 'USDT']:
                    if key in balance_data:
                        try:
                            if isinstance(balance_data[key], dict):
                                # USDT specific balance
                                usdt_data = balance_data[key]
                                for balance_key in ['total', 'free', 'available']:
                                    if balance_key in usdt_data and usdt_data[balance_key] is not None:
                                        usdt_balance = float(usdt_data[balance_key])
                                        source_used = f"{key}.{balance_key}"
                                        break
                            else:
                                usdt_balance = float(balance_data[key])
                                source_used = key
                            break
                        except (ValueError, TypeError):
                            continue
            
            if usdt_balance is None or usdt_balance <= 0:
                logging.error("💰 Could not extract valid USDT balance from Bybit")
                self._sync_failures += 1
                return False
            
            # ATOMIC BALANCE UPDATE
            with self._lock:
                old_balance = self._real_balance
                
                # Preserve allocated margin during balance updates
                # Only update the "real" balance, don't touch allocations
                if self._session_start_balance == 0.0 or self._session_start_balance == 1000.0:
                    # First sync - set start balance
                    self._session_start_balance = usdt_balance
                
                self._real_balance = usdt_balance
                self._last_bybit_sync = datetime.now().isoformat()
                self._sync_failures = 0  # Reset failure counter on success
                
                # Add to balance history
                self._balance_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'balance': usdt_balance,
                    'source': source_used,
                    'allocated_margin': self._allocated_margin
                })
                
                # Keep only last 100 balance records
                if len(self._balance_history) > 100:
                    self._balance_history = self._balance_history[-100:]
                
                self._invalidate_cache()
                
                available = self._real_balance - self._allocated_margin - self._reserved_margin
                
                logging.info(f"💰 Balance synced with Bybit: ${old_balance:.2f} → ${usdt_balance:.2f} (source: {source_used})")
                logging.info(f"💰 Available: ${available:.2f}, Allocated: ${self._allocated_margin:.2f}, Reserved: ${self._reserved_margin:.2f}")
                
                return True
                
        except Exception as e:
            logging.error(f"💰 Bybit balance sync failed: {e}")
            self._sync_failures += 1
            return False
    
    # ========================================
    # VALIDATION & SAFETY CHECKS
    # ========================================
    
    def validate_new_trade_margin(self, requested_margin: float, symbol: str = "") -> Tuple[bool, str]:
        """
        💰 VALIDATION: Valida se nuovo trade può essere aperto
        
        Args:
            requested_margin: Margin richiesto per nuovo trade
            symbol: Symbol del trade (per logging)
            
        Returns:
            Tuple[bool, str]: (approved, reason)
        """
        try:
            with self._lock:
                available = self._real_balance - self._allocated_margin - self._reserved_margin
                
                # Safety checks
                if requested_margin <= 0:
                    return False, f"Invalid margin amount: ${requested_margin:.2f}"
                
                if available < requested_margin:
                    return False, f"Insufficient balance: ${available:.2f} < ${requested_margin:.2f}"
                
                # Portfolio risk check (max 80% allocation)
                max_allocation = self._real_balance * 0.8
                total_after_allocation = self._allocated_margin + requested_margin
                
                if total_after_allocation > max_allocation:
                    return False, f"Portfolio risk limit: ${total_after_allocation:.2f} > ${max_allocation:.2f} (80% max)"
                
                # Minimum available balance check (keep 10% free)
                min_free_balance = self._real_balance * 0.1
                available_after = available - requested_margin
                
                if available_after < min_free_balance:
                    return False, f"Minimum balance protection: ${available_after:.2f} < ${min_free_balance:.2f} (10% min free)"
                
                symbol_info = f" for {symbol}" if symbol else ""
                return True, f"Validation passed{symbol_info}: ${requested_margin:.2f} margin approved"
                
        except Exception as e:
            logging.error(f"💰 Trade validation failed: {e}")
            return False, f"Validation error: {e}"
    
    def get_max_position_size(self, price: float, leverage: int = 10) -> float:
        """
        💰 CALCULATOR: Calcola dimensione massima posizione con safety margins
        
        Args:
            price: Prezzo entry della posizione
            leverage: Leverage da usare
            
        Returns:
            float: Dimensione massima posizione in contracts
        """
        try:
            with self._lock:
                available = self._real_balance - self._allocated_margin - self._reserved_margin
                
                # Apply safety factor (use max 70% of available)
                safe_available = available * 0.7
                
                # Calculate max notional value
                max_notional = safe_available * leverage
                
                # Calculate max position size in contracts
                max_contracts = max_notional / price if price > 0 else 0
                
                logging.debug(f"💰 Max position calc: Available ${available:.2f} * 0.7 * {leverage}x / ${price:.6f} = {max_contracts:.4f} contracts")
                
                return max_contracts
                
        except Exception as e:
            logging.error(f"💰 Max position calculation failed: {e}")
            return 0.0
    
    # ========================================
    # PERFORMANCE & MONITORING
    # ========================================
    
    def _invalidate_cache(self):
        """Invalida cache per forzare ricalcolo"""
        self._cache_timestamp = 0
    
    def get_balance_performance_stats(self) -> Dict:
        """
        💰 STATS: Ottieni statistiche performance balance management
        
        Returns:
            Dict: Statistiche dettagliate
        """
        try:
            with self._lock:
                return {
                    'allocation_operations': self._allocation_count,
                    'release_operations': self._release_count,
                    'total_operations': self._allocation_count + self._release_count,
                    'overexposure_prevented': self._overexposure_prevented,
                    'sync_failures': self._sync_failures,
                    'last_sync': self._last_bybit_sync,
                    'balance_history_length': len(self._balance_history),
                    'current_allocation_pct': (self._allocated_margin / self._real_balance * 100) if self._real_balance > 0 else 0,
                    'mode': 'DEMO' if self._demo_mode else 'LIVE'
                }
                
        except Exception as e:
            logging.error(f"💰 Performance stats failed: {e}")
            return {'error': str(e)}
    

    # ========================================
    # EMERGENCY OPERATIONS
    # ========================================
    
    def emergency_reset_allocations(self, reason: str = "EMERGENCY"):
        """
        🚨 EMERGENCY: Reset tutte le allocazioni (use with caution!)
        
        Args:
            reason: Ragione del reset di emergenza
        """
        try:
            with self._lock:
                old_allocated = self._allocated_margin
                old_reserved = self._reserved_margin
                
                self._allocated_margin = 0.0
                self._reserved_margin = 0.0
                self._invalidate_cache()
                
                logging.error(f"🚨 EMERGENCY BALANCE RESET: {reason}")
                logging.error(f"🚨 Cleared ${old_allocated:.2f} allocated + ${old_reserved:.2f} reserved margin")
                logging.error(f"🚨 Available balance: ${self._real_balance:.2f}")
                
        except Exception as e:
            logging.error(f"🚨 Emergency reset failed: {e}")
    
    def force_balance_update(self, new_balance: float, reason: str = "MANUAL"):
        """
        🔧 FORCE: Forza aggiornamento balance (manual override)
        
        Args:
            new_balance: Nuovo balance da impostare
            reason: Ragione dell'override manuale
        """
        try:
            with self._lock:
                old_balance = self._real_balance
                self._real_balance = new_balance
                self._invalidate_cache()
                
                logging.warning(f"🔧 FORCED balance update: ${old_balance:.2f} → ${new_balance:.2f} ({reason})")
                
        except Exception as e:
            logging.error(f"🔧 Forced balance update failed: {e}")
    
    # ========================================
    # MIGRATION & COMPATIBILITY
    # ========================================
    
    def migrate_from_old_system(self, session_balance: float, allocated_positions: List[Dict]) -> bool:
        """
        🔄 MIGRATION: Migra dal vecchio sistema multi-balance
        
        Args:
            session_balance: Balance dal vecchio sistema
            allocated_positions: Lista posizioni allocate
            
        Returns:
            bool: True se migrazione riuscita
        """
        try:
            with self._lock:
                # Set initial balance
                self._real_balance = session_balance
                self._session_start_balance = session_balance
                
                # Calculate total allocated margin from positions
                total_allocated = 0.0
                for pos in allocated_positions:
                    try:
                        position_size = pos.get('position_size', 0.0)
                        leverage = pos.get('leverage', 10)
                        margin = position_size / leverage
                        total_allocated += margin
                    except Exception as pos_error:
                        logging.warning(f"💰 Could not migrate position: {pos_error}")
                
                self._allocated_margin = total_allocated
                self._invalidate_cache()
                
                logging.info(f"🔄 Migration completed: Balance ${session_balance:.2f}, Allocated ${total_allocated:.2f}")
                return True
                
        except Exception as e:
            logging.error(f"🔄 Migration failed: {e}")
            return False


# Global unified balance manager instance  
global_unified_balance_manager = None

def initialize_balance_manager(demo_mode: bool = False, demo_balance: float = 1000.0):
    """Initialize global unified balance manager"""
    global global_unified_balance_manager
    if global_unified_balance_manager is None:
        global_unified_balance_manager = UnifiedBalanceManager(demo_mode, demo_balance)
    return global_unified_balance_manager

def get_global_balance_manager():
    """Get global balance manager instance"""
    global global_unified_balance_manager
    if global_unified_balance_manager is None:
        # Default initialization
        global_unified_balance_manager = UnifiedBalanceManager(demo_mode=True)
    return global_unified_balance_manager
