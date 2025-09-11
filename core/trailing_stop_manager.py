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
from config import (LEVERAGE, INITIAL_SL_PRICE_PCT, TRAILING_TRIGGER_MIN_PCT, 
                   TRAILING_TRIGGER_MAX_PCT, TRAILING_DISTANCE_LOW_VOL,
                   TRAILING_DISTANCE_MED_VOL, TRAILING_DISTANCE_HIGH_VOL,
                   VOLATILITY_LOW_THRESHOLD, VOLATILITY_HIGH_THRESHOLD)

class PositionState(Enum):
    """Stati delle posizioni per trailing stop"""
    FIXED_SL = "fixed_sl"          # Stop loss fisso al 6% attivo
    MONITORING = "monitoring"       # Monitoraggio per trigger trailing
    TRAILING = "trailing"          # Trailing stop attivo

@dataclass
class TrailingData:
    """Dati trailing per ogni posizione - NUOVA LOGICA"""
    entry_price: float                          # Prezzo di entrata
    side: str                                   # Direzione posizione ('buy'/'sell')
    trailing_trigger_price: Optional[float] = None  # Prezzo per attivare trailing
    trailing_attivo: bool = False               # Boolean stato trailing
    best_price: Optional[float] = None          # Miglior prezzo favorevole
    sl_corrente: Optional[float] = None         # Stop interno bot
    fixed_sl_price: Optional[float] = None      # Stop loss fisso al 6%
    state: PositionState = PositionState.FIXED_SL
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
        Calcola prezzo di liquidazione accurato per Bybit leverage 10x
        
        Formula Bybit: Liquidazione = Entry ± (Entry / Leverage) × 0.95
        Per 10x leverage: ~9.5% movement trigger liquidazione
        
        Args:
            entry_price: Prezzo di entrata
            side: Direzione posizione
            
        Returns:
            float: Prezzo liquidazione preciso
        """
        try:
            # ACCURATE Bybit liquidation formula for 10x leverage
            # Liquidation happens when unrealized loss ≈ 95% of initial margin
            liquidation_pct = 0.095  # 9.5% more accurate than 9%
            
            if side.lower() == 'buy':
                # Long: liquidazione quando prezzo scende 9.5%
                liquidation = entry_price * (1 - liquidation_pct)
            else:
                # Short: liquidazione quando prezzo sale 9.5%
                liquidation = entry_price * (1 + liquidation_pct)
            
            logging.debug(f"💀 Liquidation calc: Entry ${entry_price:.6f} | Liq ${liquidation:.6f} ({liquidation_pct*100:.1f}%)")
            return liquidation
            
        except Exception as e:
            logging.error(f"Error calculating liquidation price: {e}")
            # AGGIORNATO: Fallback coerente con 6% SL logic
            return entry_price * (0.94 if side.lower() == 'buy' else 1.06)
    
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
    
    def calculate_dynamic_trigger(self, entry_price: float, side: str, atr: float) -> float:
        """
        NUOVA FUNZIONE: Calcola trigger dinamico per attivazione trailing (5-10%)
        
        Args:
            entry_price: Prezzo di entrata
            side: Direzione posizione  
            atr: Average True Range per volatilità
            
        Returns:
            float: Prezzo trigger per attivare trailing
        """
        try:
            # Classifica volatilità basata su ATR
            atr_pct = atr / entry_price
            
            if atr_pct < VOLATILITY_LOW_THRESHOLD:      # Bassa volatilità
                trigger_pct = TRAILING_TRIGGER_MAX_PCT  # 10% (più conservativo)
            elif atr_pct > VOLATILITY_HIGH_THRESHOLD:   # Alta volatilità  
                trigger_pct = TRAILING_TRIGGER_MIN_PCT  # 5% (più aggressivo)
            else:                                       # Media volatilità
                trigger_pct = (TRAILING_TRIGGER_MIN_PCT + TRAILING_TRIGGER_MAX_PCT) / 2  # 7.5%
            
            if side.lower() == 'buy':
                trigger_price = entry_price * (1 + trigger_pct)
            else:
                trigger_price = entry_price * (1 - trigger_pct)
            
            logging.debug(f"🎯 Dynamic trigger: ATR={atr_pct*100:.1f}%, Trigger={trigger_pct*100:.1f}%, Price=${trigger_price:.6f}")
            return trigger_price
            
        except Exception as e:
            logging.error(f"Error calculating dynamic trigger: {e}")
            # Fallback: usa trigger medio
            fallback_pct = (TRAILING_TRIGGER_MIN_PCT + TRAILING_TRIGGER_MAX_PCT) / 2
            return entry_price * (1 + fallback_pct if side.lower() == 'buy' else 1 - fallback_pct)
    
    def initialize_trailing_data(self, symbol: str, side: str, entry_price: float, 
                                atr: float) -> TrailingData:
        """
        AGGIORNATO: Inizializza dati trailing per nuova posizione con nuova logica
        
        Args:
            symbol: Trading symbol
            side: Direzione posizione
            entry_price: Prezzo di entrata  
            atr: Average True Range
            
        Returns:
            TrailingData: Dati trailing inizializzati
        """
        try:
            # Calcola stop loss fisso al 6%
            if side.lower() == 'buy':
                fixed_sl = entry_price * (1 - INITIAL_SL_PRICE_PCT)  # 6% sotto
            else:
                fixed_sl = entry_price * (1 + INITIAL_SL_PRICE_PCT)  # 6% sopra
            
            # Calcola trigger dinamico per trailing
            trigger_price = self.calculate_dynamic_trigger(entry_price, side, atr)
            
            trailing_data = TrailingData(
                entry_price=entry_price,
                side=side,
                trailing_trigger_price=trigger_price,
                trailing_attivo=False,
                best_price=None,
                sl_corrente=None,
                fixed_sl_price=fixed_sl,
                state=PositionState.FIXED_SL,
                last_update=datetime.now()
            )
            
            logging.info(f"🔧 TRAILING INIT: {symbol} {side.upper()} | Entry=${entry_price:.6f} | Fixed SL=${fixed_sl:.6f} | Trigger=${trigger_price:.6f}")
            return trailing_data
            
        except Exception as e:
            logging.error(f"Error initializing trailing data: {e}")
            # Fallback data
            return TrailingData(
                entry_price=entry_price,
                side=side,
                state=PositionState.FIXED_SL,
                last_update=datetime.now()
            )
    
    def check_activation_conditions(self, trailing_data: TrailingData, 
                                  current_price: float) -> bool:
        """
        AGGIORNATO: Controlla se trailing stop può essere attivato con nuova logica
        
        Args:
            trailing_data: Dati trailing posizione
            current_price: Prezzo corrente
            
        Returns:
            bool: True se trailing può essere attivato
        """
        try:
            if trailing_data.trailing_trigger_price is None:
                logging.warning("Trailing trigger price not set")
                return False
            
            # NUOVA LOGICA: Controlla se abbiamo raggiunto il trigger dinamico (5-10%)
            if trailing_data.side.lower() == 'buy':
                # LONG: attiva se prezzo >= trigger
                trigger_reached = current_price >= trailing_data.trailing_trigger_price
            else:
                # SHORT: attiva se prezzo <= trigger
                trigger_reached = current_price <= trailing_data.trailing_trigger_price
            
            if trigger_reached:
                # Cambia stato a MONITORING per preparare attivazione
                if trailing_data.state == PositionState.FIXED_SL:
                    trailing_data.state = PositionState.MONITORING
                
                profit_pct = abs(current_price - trailing_data.entry_price) / trailing_data.entry_price * 100
                logging.info(f"🎯 TRIGGER REACHED: Price=${current_price:.6f}, Profit={profit_pct:.1f}%, Ready for trailing")
                return True
            
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
        AGGIORNATO: Calcola distanza trailing dinamica basata su volatilità
        
        Args:
            price: Prezzo di riferimento
            atr: Average True Range per classificare volatilità
            
        Returns:
            float: Distanza trailing dinamica
        """
        try:
            # Classifica volatilità basata su ATR
            atr_pct = atr / price
            
            if atr_pct < VOLATILITY_LOW_THRESHOLD:      # Bassa volatilità
                distance_pct = TRAILING_DISTANCE_LOW_VOL  # 2%
            elif atr_pct > VOLATILITY_HIGH_THRESHOLD:   # Alta volatilità
                distance_pct = TRAILING_DISTANCE_HIGH_VOL # 4%
            else:                                       # Media volatilità
                distance_pct = TRAILING_DISTANCE_MED_VOL  # 3%
            
            distance = price * distance_pct
            
            logging.debug(f"📏 Trailing distance: ATR={atr_pct*100:.1f}%, Distance={distance_pct*100:.1f}%, Value=${distance:.6f}")
            return distance
            
        except Exception as e:
            logging.error(f"Error calculating trailing distance: {e}")
            return price * TRAILING_DISTANCE_MED_VOL  # Fallback: 3%
    
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
        AGGIORNATO: Summary dello stato trailing con nuova logica
        
        Args:
            trailing_data: Dati trailing posizione
            symbol: Trading symbol
            side: Direzione posizione
            
        Returns:
            Dict: Summary stato trailing aggiornato
        """
        try:
            return {
                'symbol': symbol,
                'side': side,
                'state': trailing_data.state.value,
                'entry_price': trailing_data.entry_price,
                'fixed_sl_price': trailing_data.fixed_sl_price,
                'trailing_trigger_price': trailing_data.trailing_trigger_price,
                'trailing_active': trailing_data.trailing_attivo,
                'best_price': trailing_data.best_price,
                'sl_corrente': trailing_data.sl_corrente,
                'last_update': trailing_data.last_update.isoformat() if trailing_data.last_update else None
            }
            
        except Exception as e:
            logging.error(f"Error getting trailing summary: {e}")
            return {'error': str(e)}

# Global trailing stop manager instance  
global_trailing_manager = None  # Inizializzato dopo aver caricato dependencies
