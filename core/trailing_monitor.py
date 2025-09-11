#!/usr/bin/env python3
"""
⚡ TRAILING MONITOR - High Frequency Stop Loss Management

RESPONSABILITÀ:
- Thread separato per monitoraggio trailing ogni 30 secondi
- Esecuzione ordini di chiusura quando trailing colpito  
- Aggiornamento real-time prezzi e trailing stops
- Coordinamento con ciclo principale senza interferenze

GARANTISCE: Trailing stops rapidi e precisi
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional
from termcolor import colored

class TrailingMonitor:
    """
    Monitor dedicato per trailing stops ad alta frequenza
    
    Funziona in parallelo al ciclo principale del bot (300s)
    Monitora trailing stops ogni 30 secondi per reattività massima
    """
    
    def __init__(self, position_manager, trailing_manager, order_manager):
        self.position_manager = position_manager
        self.trailing_manager = trailing_manager
        self.order_manager = order_manager
        
        # Configurazione monitoraggio
        self.monitor_interval = 30  # 30 secondi (molto più veloce del ciclo principale)
        self.is_running = False
        self.monitor_task = None
        
        # Cache trailing data per ogni posizione
        self.trailing_cache: Dict[str, any] = {}
        
        logging.info("⚡ TRAILING MONITOR: Initialized for high-frequency stop monitoring")
    
    async def start_monitoring(self, exchange):
        """
        Avvia il thread di monitoraggio trailing
        
        Args:
            exchange: Bybit exchange instance
        """
        if self.is_running:
            logging.warning("⚡ Trailing monitor already running")
            return
            
        self.is_running = True
        logging.info(f"⚡ TRAILING MONITOR: Starting high-frequency monitoring (every {self.monitor_interval}s)")
        
        # Avvia il task asincrono di monitoraggio
        self.monitor_task = asyncio.create_task(self._monitoring_loop(exchange))
    
    async def stop_monitoring(self):
        """Ferma il monitoraggio trailing"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logging.info("⚡ TRAILING MONITOR: Stopped")
    
    async def _monitoring_loop(self, exchange):
        """
        Loop principale di monitoraggio ad alta frequenza
        
        Args:
            exchange: Bybit exchange instance
        """
        try:
            while self.is_running:
                try:
                    # Monitora tutte le posizioni attive
                    await self._monitor_all_positions(exchange)
                    
                    # Aspetta il prossimo ciclo
                    await asyncio.sleep(self.monitor_interval)
                    
                except Exception as e:
                    logging.error(f"⚡ Error in monitoring loop: {e}")
                    # Continua il monitoraggio anche in caso di errore
                    await asyncio.sleep(self.monitor_interval)
                    
        except asyncio.CancelledError:
            logging.info("⚡ TRAILING MONITOR: Monitoring loop cancelled")
        except Exception as e:
            logging.error(f"⚡ Fatal error in monitoring loop: {e}")
        finally:
            self.is_running = False
    
    async def _monitor_all_positions(self, exchange):
        """
        Monitora tutte le posizioni attive per trailing stops
        
        Args:
            exchange: Bybit exchange instance
        """
        try:
            active_positions = self.position_manager.get_active_positions()
            
            if not active_positions:
                return  # Nessuna posizione da monitorare
            
            # Log ogni 5 cicli per evitare spam
            if datetime.now().second % 150 == 0:  # 5 cicli * 30s = 150s
                logging.debug(f"⚡ MONITORING: {len(active_positions)} active positions")
            
            for position in active_positions:
                await self._monitor_single_position(exchange, position)
                
        except Exception as e:
            logging.error(f"⚡ Error monitoring all positions: {e}")
    
    async def _monitor_single_position(self, exchange, position):
        """
        Monitora una singola posizione per trailing stops
        
        Args:
            exchange: Bybit exchange instance
            position: Position object to monitor
        """
        try:
            symbol = position.symbol
            
            # 1. Ottieni prezzo corrente real-time
            current_price = await self._get_current_price(exchange, symbol)
            if current_price is None:
                return
            
            # 2. Ottieni/inizializza trailing data
            trailing_data = await self._get_or_create_trailing_data(position, current_price)
            if trailing_data is None:
                return
            
            # 3. Controlla se trigger è raggiunto (attivazione trailing)
            if not trailing_data.trailing_attivo:
                if self.trailing_manager.check_activation_conditions(trailing_data, current_price):
                    # Attiva trailing stop
                    atr = await self._estimate_atr(exchange, symbol)
                    self.trailing_manager.activate_trailing(
                        trailing_data, current_price, position.side, atr
                    )
                    logging.info(colored(f"⚡ TRAILING ACTIVATED: {symbol} at ${current_price:.6f}", "green"))
            
            # 4. Se trailing è attivo, aggiorna e controlla hit
            if trailing_data.trailing_attivo:
                atr = await self._estimate_atr(exchange, symbol)
                
                # Aggiorna trailing stop
                self.trailing_manager.update_trailing(
                    trailing_data, current_price, position.side, atr
                )
                
                # Controlla se trailing stop è colpito
                if self.trailing_manager.is_trailing_hit(trailing_data, current_price, position.side):
                    # ESEGUI USCITA IMMEDIATA
                    success = await self._execute_trailing_exit(exchange, position, current_price)
                    if success:
                        # Rimuovi dalla cache
                        if position.position_id in self.trailing_cache:
                            del self.trailing_cache[position.position_id]
                        
                        logging.info(colored(f"⚡ TRAILING EXIT EXECUTED: {symbol} at ${current_price:.6f}", "yellow"))
            
            # 5. Aggiorna cache
            self.trailing_cache[position.position_id] = trailing_data
            
        except Exception as e:
            logging.error(f"⚡ Error monitoring position {position.symbol}: {e}")
    
    async def _get_current_price(self, exchange, symbol: str) -> Optional[float]:
        """
        Ottieni prezzo corrente real-time
        
        Args:
            exchange: Bybit exchange instance
            symbol: Trading symbol
            
        Returns:
            Optional[float]: Current price or None if error
        """
        try:
            ticker = await exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            logging.warning(f"⚡ Could not fetch price for {symbol}: {e}")
            return None
    
    async def _get_or_create_trailing_data(self, position, current_price):
        """
        Ottieni o crea trailing data per la posizione
        
        Args:
            position: Position object
            current_price: Current market price
            
        Returns:
            TrailingData or None
        """
        try:
            position_id = position.position_id
            
            # Se già in cache, usa quello
            if position_id in self.trailing_cache:
                return self.trailing_cache[position_id]
            
            # Altrimenti crea nuovo trailing data
            atr = await self._estimate_atr(None, position.symbol)  # Stima ATR
            trailing_data = self.trailing_manager.initialize_trailing_data(
                position.symbol, position.side, position.entry_price, atr
            )
            
            return trailing_data
            
        except Exception as e:
            logging.error(f"⚡ Error getting trailing data for {position.symbol}: {e}")
            return None
    
    async def _estimate_atr(self, exchange, symbol: str) -> float:
        """
        Stima ATR per il simbolo (fallback se non disponibile)
        
        Args:
            exchange: Bybit exchange instance  
            symbol: Trading symbol
            
        Returns:
            float: Estimated ATR
        """
        try:
            # Cerca di ottenere ATR real-time se possibile
            if exchange:
                ticker = await exchange.fetch_ticker(symbol)
                price = float(ticker['last'])
                # Stima ATR come % del prezzo (2% tipico per crypto)
                return price * 0.02
            else:
                # Fallback: usa 2% del prezzo entry
                return 0.02
                
        except Exception as e:
            logging.debug(f"⚡ ATR estimation failed for {symbol}: {e}")
            return 0.02  # Fallback conservativo
    
    async def _execute_trailing_exit(self, exchange, position, current_price: float) -> bool:
        """
        Esegue uscita quando trailing stop è colpito
        
        Args:
            exchange: Bybit exchange instance
            position: Position to exit
            current_price: Current market price
            
        Returns:
            bool: True if exit successful
        """
        try:
            # Usa il trailing manager per eseguire l'uscita
            success = await self.trailing_manager.execute_trailing_exit(
                exchange, position.symbol, position.side, 
                position.position_size, current_price
            )
            
            if success:
                # Aggiorna position manager
                self.position_manager.close_position_manual(
                    position.position_id, current_price, "TRAILING"
                )
            
            return success
            
        except Exception as e:
            logging.error(f"⚡ Error executing trailing exit for {position.symbol}: {e}")
            return False
    
    def get_monitoring_status(self) -> Dict:
        """
        Ottieni stato del monitoraggio
        
        Returns:
            Dict: Status information
        """
        return {
            'is_running': self.is_running,
            'monitor_interval': self.monitor_interval,
            'cached_positions': len(self.trailing_cache),
            'last_check': datetime.now().isoformat() if self.is_running else None
        }

# Global trailing monitor instance
global_trailing_monitor = None  # Inizializzato nel main
