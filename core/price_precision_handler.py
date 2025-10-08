#!/usr/bin/env python3
"""
🎯 PRICE PRECISION HANDLER

SINGLE RESPONSIBILITY: Gestione accurata delle precisioni di prezzo per tutti i simboli
- Gestisce tick size specifici per ogni simbolo  
- Rispetta le regole Bybit per stop loss (buy < last, sell > last)
- Cache per migliorare le performance
- Fallback robusto per simboli problematici

GARANTISCE: Stop loss sempre validi indipendentemente dal simbolo
"""

import logging
from typing import Dict, Optional, Tuple
from decimal import Decimal, ROUND_DOWN, ROUND_UP
import asyncio

class PricePrecisionHandler:
    """
    Gestione intelligente della precisione dei prezzi
    
    PHILOSOPHY: 
    - Ogni simbolo ha le sue regole di precisione
    - Cache per evitare chiamate API ripetute
    - Validazione rigorosa contro le regole Bybit
    - Fallback automatici per casi edge
    """
    
    def __init__(self):
        self._symbol_precision_cache: Dict[str, Dict] = {}
        self._last_prices_cache: Dict[str, float] = {}
        self._cache_timeout = 300  # 5 minuti cache
        
    async def get_symbol_precision(self, exchange, symbol: str) -> Dict:
        """
        Ottiene informazioni di precisione per un simbolo con cache
        
        Args:
            exchange: Bybit exchange instance
            symbol: Trading symbol (es. BTC/USDT:USDT)
            
        Returns:
            Dict con informazioni di precisione
        """
        try:
            if symbol not in self._symbol_precision_cache:
                # Fetch market info
                markets = await exchange.load_markets()
                if symbol in markets:
                    market = markets[symbol]
                    precision_info = {
                        'price_precision': market.get('precision', {}).get('price', 8),
                        'amount_precision': market.get('precision', {}).get('amount', 8),
                        'tick_size': market.get('limits', {}).get('price', {}).get('min', 0.01),
                        'min_price': market.get('limits', {}).get('price', {}).get('min', 0.01),
                        'max_price': market.get('limits', {}).get('price', {}).get('max', 1000000),
                        'min_amount': market.get('limits', {}).get('amount', {}).get('min', 0.001),
                        'max_amount': market.get('limits', {}).get('amount', {}).get('max', 1000000),
                        'amount_step': market.get('limits', {}).get('amount', {}).get('min', 0.001),
                    }
                    self._symbol_precision_cache[symbol] = precision_info
                    logging.debug(f"💾 Cached precision for {symbol}: {precision_info}")
                else:
                    # Fallback generico
                    self._symbol_precision_cache[symbol] = {
                        'price_precision': 6,
                        'amount_precision': 6, 
                        'tick_size': 0.01,
                        'min_price': 0.01,
                        'max_price': 1000000,
                        'min_amount': 1.0,  # CRITICAL: Conservative minimum amount
                        'max_amount': 1000000,
                        'amount_step': 1.0,
                    }
                    logging.warning(f"⚠️ Using fallback precision for {symbol}")
            
            return self._symbol_precision_cache[symbol]
            
        except Exception as e:
            logging.error(f"Error getting precision for {symbol}: {e}")
            # Fallback estremo
            return {
                'price_precision': 6,
                'amount_precision': 6,
                'tick_size': 0.01, 
                'min_price': 0.01,
                'max_price': 1000000,
            }
    
    def round_to_tick_size(self, price: float, tick_size: float, round_down: bool = False) -> float:
        """
        Arrotonda il prezzo al tick size più vicino
        
        Args:
            price: Prezzo da arrotondare
            tick_size: Tick size minimo
            round_down: Se True, arrotonda sempre verso il basso
            
        Returns:
            float: Prezzo arrotondato al tick size
        """
        try:
            if tick_size <= 0:
                return round(price, 6)
            
            # Usa Decimal per precisione matematica
            price_decimal = Decimal(str(price))
            tick_decimal = Decimal(str(tick_size))
            
            # Calcola multiplo del tick size
            if round_down:
                multiplier = (price_decimal / tick_decimal).quantize(Decimal('1'), rounding=ROUND_DOWN)
            else:
                multiplier = (price_decimal / tick_decimal).quantize(Decimal('1'), rounding=ROUND_UP)
            
            rounded_price = float(multiplier * tick_decimal)
            
            logging.debug(f"🎯 Price {price:.8f} → {rounded_price:.8f} (tick: {tick_size}, down: {round_down})")
            return rounded_price
            
        except Exception as e:
            logging.error(f"Error rounding price to tick size: {e}")
            return round(price, 6)  # Fallback
    
    async def get_current_price(self, exchange, symbol: str) -> float:
        """
        Ottiene il prezzo corrente con cache temporanea
        
        Args:
            exchange: Bybit exchange instance
            symbol: Trading symbol
            
        Returns:
            float: Prezzo corrente
        """
        try:
            ticker = await exchange.fetch_ticker(symbol)
            current_price = float(ticker.get('last', 0))
            
            if current_price > 0:
                self._last_prices_cache[symbol] = current_price
                return current_price
            else:
                # Usa cache se disponibile
                return self._last_prices_cache.get(symbol, 0.0)
                
        except Exception as e:
            logging.error(f"Error fetching current price for {symbol}: {e}")
            return self._last_prices_cache.get(symbol, 0.0)
    
    async def normalize_stop_loss_price(self, exchange, symbol: str, side: str, 
                                      entry_price: float, raw_sl: float) -> Tuple[float, bool]:
        """
        🔧 PRECISION FIX: Normalizza stop loss mantenendo esattamente 6% dopo arrotondamento
        
        Algoritmo iterativo che compensa l'effetto dell'arrotondamento per garantire
        che lo stop loss finale sia sempre vicino al 6% target.
        
        Args:
            exchange: Bybit exchange instance
            symbol: Trading symbol
            side: Direzione posizione ('buy' o 'sell')
            entry_price: Prezzo di entrata
            raw_sl: Stop loss calcolato grezzo (6%)
            
        Returns:
            Tuple[float, bool]: (stop_loss_normalizzato, successo)
        """
        try:
            # 1. Ottieni precisione del simbolo
            precision_info = await self.get_symbol_precision(exchange, symbol)
            tick_size = precision_info['tick_size']
            
            # 2. Ottieni prezzo corrente
            current_price = await self.get_current_price(exchange, symbol)
            
            if current_price <= 0:
                logging.error(f"❌ Invalid current price for {symbol}: {current_price}")
                return raw_sl, False
            
            # 3. TARGET: 6% esatto
            target_percentage = 0.06
            tolerance = 0.001  # ±0.1% tolleranza
            max_iterations = 10
            
            # 4. ALGORITMO ITERATIVO per compensare arrotondamento
            best_sl = raw_sl
            best_deviation = float('inf')
            
            for i in range(max_iterations):
                # Prova questo SL candidato
                if side.lower() == 'buy':
                    # LONG: Arrotonda verso il basso
                    candidate_sl = self.round_to_tick_size(raw_sl, tick_size, round_down=True)
                    
                    # Verifica regola Bybit: SL < current_price
                    if candidate_sl >= current_price:
                        candidate_sl = current_price - tick_size
                        candidate_sl = self.round_to_tick_size(candidate_sl, tick_size, round_down=True)
                else:
                    # SHORT: Arrotonda verso l'alto
                    candidate_sl = self.round_to_tick_size(raw_sl, tick_size, round_down=False)
                    
                    # Verifica regola Bybit: SL > current_price
                    if candidate_sl <= current_price:
                        candidate_sl = current_price + tick_size
                        candidate_sl = self.round_to_tick_size(candidate_sl, tick_size, round_down=False)
                
                # Calcola percentuale effettiva dopo arrotondamento
                actual_percentage = abs((candidate_sl - entry_price) / entry_price)
                deviation = abs(actual_percentage - target_percentage)
                
                # Tieni traccia del migliore
                if deviation < best_deviation:
                    best_sl = candidate_sl
                    best_deviation = deviation
                
                # Se abbastanza vicino al target, ferma iterazione
                if deviation <= tolerance:
                    logging.debug(f"✅ {symbol} SL perfect match at iteration {i+1}: {actual_percentage*100:.3f}%")
                    break
                
                # Aggiusta raw_sl per il prossimo tentativo
                if actual_percentage < target_percentage:
                    # SL troppo vicino → allontana
                    if side.lower() == 'buy':
                        raw_sl -= tick_size * 0.5
                    else:
                        raw_sl += tick_size * 0.5
                else:
                    # SL troppo lontano → avvicina
                    if side.lower() == 'buy':
                        raw_sl += tick_size * 0.5
                    else:
                        raw_sl -= tick_size * 0.5
            
            normalized_sl = best_sl
            final_percentage = abs((normalized_sl - entry_price) / entry_price) * 100
            
            # 5. Validazioni finali
            min_price = precision_info['min_price']
            max_price = precision_info['max_price']
            
            if normalized_sl < min_price:
                normalized_sl = min_price
                logging.warning(f"⚠️ {symbol} SL adjusted to min price: {normalized_sl}")
            elif normalized_sl > max_price:
                normalized_sl = max_price
                logging.warning(f"⚠️ {symbol} SL adjusted to max price: {normalized_sl}")
            
            # 6. Log dettagliato con percentuale finale
            symbol_short = symbol.replace('/USDT:USDT', '')
            if best_deviation > tolerance:
                logging.info(f"🎯 {symbol_short} SL: ${entry_price:.6f} → ${normalized_sl:.6f} ({final_percentage:.2f}% vs 6.00% target)")
            else:
                logging.debug(f"✅ {symbol_short} SL perfect: ${normalized_sl:.6f} ({final_percentage:.3f}%)")
            
            return normalized_sl, True
            
        except Exception as e:
            logging.error(f"❌ Error normalizing SL for {symbol}: {e}")
            return raw_sl, False
    
    async def normalize_position_size(self, exchange, symbol: str, size: float) -> Tuple[float, bool]:
        """
        Normalizza la dimensione della posizione secondo le regole del simbolo
        
        Args:
            exchange: Bybit exchange instance
            symbol: Trading symbol
            size: Dimensione posizione grezza
            
        Returns:
            Tuple[float, bool]: (size_normalizzata, successo)
        """
        try:
            precision_info = await self.get_symbol_precision(exchange, symbol)
            amount_precision = precision_info.get('amount_precision', 6)
            min_amount = precision_info.get('min_amount', 0.001)
            max_amount = precision_info.get('max_amount', 1000000)
            amount_step = precision_info.get('amount_step', 0.001)
            
            # 1. Arrotonda alla precisione dell'amount
            # CRITICAL FIX: Ensure amount_precision is an integer
            amount_precision = int(amount_precision) if amount_precision else 6
            normalized_size = round(size, amount_precision)
            
            # 2. CRITICAL FIX: Ensure size respects amount_step (like tick size for amounts)
            if amount_step > 0:
                # Round to nearest amount_step using floor division
                from decimal import Decimal, ROUND_DOWN
                size_decimal = Decimal(str(normalized_size))
                step_decimal = Decimal(str(amount_step))
                step_multiplier = (size_decimal / step_decimal).quantize(Decimal('1'), rounding=ROUND_DOWN)
                normalized_size = float(step_multiplier * step_decimal)
                # Round again to avoid floating point errors
                normalized_size = round(normalized_size, amount_precision)
            
            # 3. CRITICAL FIX: Enforce minimum amount
            if normalized_size < min_amount:
                logging.warning(f"⚠️ {symbol}: Size {normalized_size:.6f} < min {min_amount}, adjusting to minimum")
                normalized_size = min_amount
            
            # 4. Enforce maximum amount  
            if normalized_size > max_amount:
                logging.warning(f"⚠️ {symbol}: Size {normalized_size:.6f} > max {max_amount}, adjusting to maximum")
                normalized_size = max_amount
            
            # 5. Final validation
            if normalized_size <= 0:
                logging.error(f"❌ {symbol}: Invalid normalized size: {normalized_size}")
                return size, False
            
            # 6. Log normalization if significant change
            if abs(normalized_size - size) > amount_step:
                logging.info(f"🎯 {symbol} size normalized: {size:.8f} → {normalized_size:.8f} (min: {min_amount}, step: {amount_step})")
            
            return normalized_size, True
            
        except Exception as e:
            logging.error(f"Error normalizing size for {symbol}: {e}")
            return round(size, 6), False
    
    def validate_price_rules(self, symbol: str, side: str, stop_loss: float, current_price: float) -> bool:
        """
        Valida che il prezzo rispetti le regole Bybit
        
        Args:
            symbol: Trading symbol
            side: Direzione posizione  
            stop_loss: Prezzo stop loss
            current_price: Prezzo corrente
            
        Returns:
            bool: True se valido
        """
        try:
            if side.lower() == 'buy':
                # LONG: Stop loss deve essere minore del prezzo corrente
                valid = stop_loss < current_price
                if not valid:
                    logging.error(f"❌ {symbol} LONG SL validation failed: {stop_loss:.6f} >= {current_price:.6f}")
            else:
                # SHORT: Stop loss deve essere maggiore del prezzo corrente
                valid = stop_loss > current_price
                if not valid:
                    logging.error(f"❌ {symbol} SHORT SL validation failed: {stop_loss:.6f} <= {current_price:.6f}")
            
            return valid
            
        except Exception as e:
            logging.error(f"Error validating price rules for {symbol}: {e}")
            return False
    
    def clear_cache(self):
        """Pulisce la cache (utile per test o reset)"""
        self._symbol_precision_cache.clear()
        self._last_prices_cache.clear()
        logging.info("🧹 Price precision cache cleared")


# Global price precision handler instance
global_price_precision_handler = PricePrecisionHandler()
