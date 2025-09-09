#!/usr/bin/env python3
"""
🎯 TRAILING STOP MANAGER

SINGLE RESPONSIBILITY: Gestione trailing stops dinamici
- Stop catastrofico su exchange (backup ampio)
- Trailing stop interno gestito dal bot
- Attivazione condizionale sopra breakeven  
- Monotonia: stop non arretra mai
- Nessun Take Profit su exchange

GARANTISCE: Risk management sofisticato senza conflitti API
"""

import logging
from typing import Optional, Tuple, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from config import LEVERAGE

class PositionState(Enum):
    """Stati delle posizioni per trailing stop"""
    PROTECTION = "protection"      # Solo stop catastrofico attivo
    TRACKING = "tracking"          # Monitoraggio pre-attivazione
    TRAILING = "trailing"          # Trailing stop attivo

@dataclass
class TrailingData:
    """Dati trailing per ogni posizione"""
    sl_catastrofico_id: Optional[str] = None    # ID ordine exchange (backup)
    trailing_attivo: bool = False               # Boolean stato trailing
    best_price: Optional[float] = None          # Miglior prezzo favorevole
    sl_corrente: Optional[float] = None         # Stop interno bot
    breakeven_price: Optional[float] = None     # Entry + commissioni
    timer_attivazione: int = 0                  # Contatore barre sopra breakeven
    state: PositionState = PositionState.PROTECTION
    last_update: Optional[datetime] = None      # Ultimo aggiornamento

class TrailingStopManager:
    """
    Gestione avanzata trailing stops
    
    PHILOSOPHY: 
    - Exchange API solo per stop catastrofico
    - Trailing logic completamente interna
    - Attivazione condizionale sopra breakeven
    - Monotonia: stop mai arretrati
    """
    
    def __init__(self, order_manager, position_manager):
        self.order_manager = order_manager
        self.position_manager = position_manager
        
        # Parametri configurabili
        self.buffer_breakeven = 0.005           # 0.5% buffer per attivazione
        self.bars_required = 3                  # 3 candele sopra breakeven
        self.atr_multiplier = 2.0              # Moltiplicatore ATR per distanza
        self.commission_rate = 0.0006          # 0.06% commissioni totali
        self.min_trail_distance_pct = 0.01     # Minimo 1% distanza trailing
        self.max_trail_distance_pct = 0.05     # Massimo 5% distanza trailing
        
    def calculate_liquidation_price(self, entry_price: float, side: str) -> float:
        """
        Calcola prezzo di liquidazione approssimativo
        
        Args:
            entry_price: Prezzo di entrata
            side: Direzione posizione
            
        Returns:
            float: Prezzo liquidazione stimato
        """
        try:
            # Formula approssimativa Bybit per leverage 10x
            if side.lower() == 'buy':
                # Long: liquidazione quando prezzo scende ~9% (per 10x leverage)
                liquidation = entry_price * (1 - 0.09)
            else:
                # Short: liquidazione quando prezzo sale ~9% (per 10x leverage)  
                liquidation = entry_price * (1 + 0.09)
                
            return liquidation
            
        except Exception as e:
            logging.error(f"Error calculating liquidation price: {e}")
            # Fallback conservativo
            return entry_price * (0.85 if side.lower() == 'buy' else 1.15)
    
    def calculate_breakeven_price(self, entry_price: float, side: str) -> float:
        """
        Calcola prezzo di breakeven (entry + commissioni)
        
        Args:
            entry_price: Prezzo di entrata
            side: Direzione posizione
            
        Returns:
            float: Prezzo breakeven
        """
        try:
            commission_cost = entry_price * self.commission_rate
            
            if side.lower() == 'buy':
                # Long: deve superare entry + commissioni
                breakeven = entry_price + commission_cost
            else:
                # Short: deve scendere sotto entry - commissioni
                breakeven = entry_price - commission_cost
                
            return breakeven
            
        except Exception as e:
            logging.error(f"Error calculating breakeven: {e}")
            return entry_price  # Fallback: entry price
    
    async def create_catastrophic_stop(self, exchange, symbol: str, side: str, 
                                     entry_price: float) -> Optional[str]:
        """
        Crea stop catastrofico ampio su exchange come backup
        
        Args:
            exchange: Bybit exchange instance
            symbol: Trading symbol
            side: Direzione posizione
            entry_price: Prezzo di entrata
            
        Returns:
            Optional[str]: ID dell'ordine stop catastrofico
        """
        try:
            # Calcola stop catastrofico vicino alla liquidazione
            liquidation_price = self.calculate_liquidation_price(entry_price, side)
            
            # Buffer dal prezzo di liquidazione (20% del range)
            if side.lower() == 'buy':
                buffer = (entry_price - liquidation_price) * 0.2
                catastrophic_sl = liquidation_price + buffer
            else:
                buffer = (liquidation_price - entry_price) * 0.2
                catastrophic_sl = liquidation_price - buffer
            
            logging.info(f"🚨 Creating catastrophic stop for {symbol}: ${catastrophic_sl:.6f}")
            
            # Usa API esistente per impostare solo stop loss
            result = await self.order_manager.set_trading_stop(
                exchange, symbol, catastrophic_sl, None  # Solo SL, no TP
            )
            
            if result.success:
                logging.info(f"✅ Catastrophic stop set: {result.order_id}")
                return result.order_id
            else:
                logging.error(f"❌ Failed to set catastrophic stop: {result.error}")
                return None
                
        except Exception as e:
            logging.error(f"Error creating catastrophic stop: {e}")
            return None
    
    def initialize_trailing_data(self, symbol: str, side: str, entry_price: float, 
                                atr: float, catastrophic_sl_id: str) -> TrailingData:
        """
        Inizializza dati trailing per nuova posizione
        
        Args:
            symbol: Trading symbol
            side: Direzione posizione
            entry_price: Prezzo di entrata
            atr: Average True Range
            catastrophic_sl_id: ID stop catastrofico
            
        Returns:
            TrailingData: Dati trailing inizializzati
        """
        breakeven = self.calculate_breakeven_price(entry_price, side)
        
        return TrailingData(
            sl_catastrofico_id=catastrophic_sl_id,
            trailing_attivo=False,
            best_price=None,
            sl_corrente=None,
            breakeven_price=breakeven,
            timer_attivazione=0,
            state=PositionState.PROTECTION,
            last_update=datetime.now()
        )
    
    def check_activation_conditions(self, trailing_data: TrailingData, 
                                  current_price: float, side: str) -> bool:
        """
        Controlla se trailing stop può essere attivato
        
        Args:
            trailing_data: Dati trailing posizione
            current_price: Prezzo corrente
            side: Direzione posizione
            
        Returns:
            bool: True se trailing può essere attivato
        """
        try:
            if trailing_data.breakeven_price is None:
                return False
            
            # Calcola se siamo sopra breakeven + buffer
            target_price = trailing_data.breakeven_price * (
                1 + self.buffer_breakeven if side.lower() == 'buy' 
                else 1 - self.buffer_breakeven
            )
            
            if side.lower() == 'buy':
                above_target = current_price > target_price
            else:
                above_target = current_price < target_price
            
            if above_target:
                trailing_data.timer_attivazione += 1
                logging.debug(f"📊 Breakeven timer: {trailing_data.timer_attivazione}/{self.bars_required}")
                
                if trailing_data.timer_attivazione >= self.bars_required:
                    return True
            else:
                # Reset timer se torniamo sotto breakeven
                trailing_data.timer_attivazione = 0
                
            return False
            
        except Exception as e:
            logging.error(f"Error checking activation conditions: {e}")
            return False
    
    def activate_trailing(self, trailing_data: TrailingData, current_price: float, 
                         side: str, atr: float):
        """
        Attiva trailing stop
        
        Args:
            trailing_data: Dati trailing posizione
            current_price: Prezzo corrente
            side: Direzione posizione
            atr: Average True Range
        """
        try:
            trailing_data.trailing_attivo = True
            trailing_data.best_price = current_price
            trailing_data.state = PositionState.TRAILING
            
            # Calcola primo stop trailing
            trail_distance = self.calculate_trailing_distance(current_price, atr)
            
            if side.lower() == 'buy':
                trailing_data.sl_corrente = current_price - trail_distance
            else:
                trailing_data.sl_corrente = current_price + trail_distance
            
            logging.info(f"🎯 TRAILING ACTIVATED: Best ${current_price:.6f} | SL ${trailing_data.sl_corrente:.6f}")
            
        except Exception as e:
            logging.error(f"Error activating trailing: {e}")
    
    def calculate_trailing_distance(self, price: float, atr: float) -> float:
        """
        Calcola distanza trailing basata su ATR
        
        Args:
            price: Prezzo di riferimento
            atr: Average True Range
            
        Returns:
            float: Distanza trailing
        """
        try:
            # Base distance usando ATR
            distance = atr * self.atr_multiplier
            
            # Applica limiti percentuali
            min_distance = price * self.min_trail_distance_pct
            max_distance = price * self.max_trail_distance_pct
            
            distance = max(min_distance, min(distance, max_distance))
            
            return distance
            
        except Exception as e:
            logging.error(f"Error calculating trailing distance: {e}")
            return price * 0.02  # Fallback 2%
    
    def update_trailing(self, trailing_data: TrailingData, current_price: float, 
                       side: str, atr: float):
        """
        Aggiorna trailing stop attivo (monotono)
        
        Args:
            trailing_data: Dati trailing posizione
            current_price: Prezzo corrente
            side: Direzione posizione
            atr: Average True Range
        """
        try:
            if not trailing_data.trailing_attivo:
                return
            
            # Aggiorna best price (monotono)
            if side.lower() == 'buy':
                new_best = max(trailing_data.best_price, current_price)
            else:
                new_best = min(trailing_data.best_price, current_price)
            
            if new_best != trailing_data.best_price:
                trailing_data.best_price = new_best
                
                # Calcola nuovo stop trailing
                trail_distance = self.calculate_trailing_distance(new_best, atr)
                
                if side.lower() == 'buy':
                    new_sl = new_best - trail_distance
                    # Monotonia: stop non arretra mai
                    trailing_data.sl_corrente = max(trailing_data.sl_corrente, new_sl)
                else:
                    new_sl = new_best + trail_distance
                    # Monotonia: stop non arretra mai
                    trailing_data.sl_corrente = min(trailing_data.sl_corrente, new_sl)
                
                logging.debug(f"🔄 TRAILING UPDATE: Best ${new_best:.6f} | SL ${trailing_data.sl_corrente:.6f}")
            
            trailing_data.last_update = datetime.now()
            
        except Exception as e:
            logging.error(f"Error updating trailing: {e}")
    
    def is_trailing_hit(self, trailing_data: TrailingData, current_price: float, 
                       side: str) -> bool:
        """
        Controlla se trailing stop è stato colpito
        
        Args:
            trailing_data: Dati trailing posizione
            current_price: Prezzo corrente
            side: Direzione posizione
            
        Returns:
            bool: True se trailing stop colpito
        """
        try:
            if not trailing_data.trailing_attivo or trailing_data.sl_corrente is None:
                return False
            
            if side.lower() == 'buy':
                # Long: esce se prezzo scende sotto stop
                hit = current_price <= trailing_data.sl_corrente
            else:
                # Short: esce se prezzo sale sopra stop
                hit = current_price >= trailing_data.sl_corrente
            
            if hit:
                logging.info(f"🎯 TRAILING HIT: Price ${current_price:.6f} vs SL ${trailing_data.sl_corrente:.6f}")
            
            return hit
            
        except Exception as e:
            logging.error(f"Error checking trailing hit: {e}")
            return False
    
    async def execute_trailing_exit(self, exchange, symbol: str, side: str, 
                                  position_size: float, current_price: float) -> bool:
        """
        Esegue uscita market quando trailing colpito
        
        Args:
            exchange: Bybit exchange instance
            symbol: Trading symbol
            side: Direzione posizione originale
            position_size: Dimensione posizione
            current_price: Prezzo corrente
            
        Returns:
            bool: True se uscita riuscita
        """
        try:
            # Direzione opposta per chiudere
            exit_side = 'sell' if side.lower() == 'buy' else 'buy'
            
            logging.info(f"🎯 EXECUTING TRAILING EXIT: {symbol} {exit_side.upper()} {position_size}")
            
            # Usa API esistente per market order
            result = await self.order_manager.place_market_order(
                exchange, symbol, exit_side, position_size
            )
            
            if result.success:
                logging.info(f"✅ Trailing exit successful: {result.order_id}")
                return True
            else:
                logging.error(f"❌ Trailing exit failed: {result.error}")
                return False
                
        except Exception as e:
            logging.error(f"Error executing trailing exit: {e}")
            return False
    
    def get_trailing_summary(self, trailing_data: TrailingData, symbol: str, 
                           side: str) -> Dict:
        """
        Ottieni summary dello stato trailing
        
        Args:
            trailing_data: Dati trailing posizione
            symbol: Trading symbol
            side: Direzione posizione
            
        Returns:
            Dict: Summary stato trailing
        """
        try:
            return {
                'symbol': symbol,
                'side': side,
                'state': trailing_data.state.value,
                'trailing_active': trailing_data.trailing_attivo,
                'best_price': trailing_data.best_price,
                'sl_corrente': trailing_data.sl_corrente,
                'breakeven_price': trailing_data.breakeven_price,
                'timer_activation': trailing_data.timer_attivazione,
                'bars_required': self.bars_required,
                'catastrophic_sl_id': trailing_data.sl_catastrofico_id,
                'last_update': trailing_data.last_update.isoformat() if trailing_data.last_update else None
            }
            
        except Exception as e:
            logging.error(f"Error getting trailing summary: {e}")
            return {'error': str(e)}

# Global trailing stop manager instance  
global_trailing_manager = None  # Inizializzato dopo aver caricato dependencies
