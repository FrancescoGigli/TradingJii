#!/usr/bin/env python3
"""
🛡️ POSITION SAFETY MANAGER

Sistema di sicurezza per posizioni:
- Chiusura automatica posizioni troppo piccole
- Blocco trading senza stop loss
- Enforcement regole di sicurezza
"""

import logging
from termcolor import colored


class PositionSafetyManager:
    """
    Manager per la sicurezza delle posizioni
    """
    
    def __init__(self):
        self.min_position_usd = 200.0  # Minimum $200 notional value
        self.min_im_usd = 20.0        # Minimum $20 initial margin
        self.max_positions_without_sl = 0  # ZERO tolerance for positions without SL
        
    async def check_and_close_unsafe_positions(self, exchange, position_manager):
        """
        Controlla e chiude automaticamente posizioni non sicure
        
        Args:
            exchange: Bybit exchange instance
            position_manager: Smart position manager
            
        Returns:
            int: Number of positions closed for safety
        """
        closed_count = 0
        
        try:
            # Get real positions from Bybit
            bybit_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_positions = [p for p in bybit_positions if float(p.get('contracts', 0)) > 0]
            
            for position in active_positions:
                try:
                    symbol = position.get('symbol')
                    contracts = abs(float(position.get('contracts', 0)))
                    entry_price = float(position.get('entryPrice', 0))
                    leverage = float(position.get('leverage', 10))
                    
                    # Calculate position metrics
                    position_usd = contracts * entry_price
                    initial_margin = position_usd / leverage
                    
                    # Check if position is too small for safe trading
                    if position_usd < self.min_position_usd or initial_margin < self.min_im_usd:
                        symbol_short = symbol.replace('/USDT:USDT', '')
                        
                        logging.warning(colored(
                            f"⚠️ UNSAFE POSITION DETECTED: {symbol_short} "
                            f"(${position_usd:.2f} notional, ${initial_margin:.2f} IM)", 
                            "red", attrs=['bold']
                        ))
                        
                        # Close the unsafe position
                        await self._close_unsafe_position(exchange, symbol, contracts, position_manager)
                        closed_count += 1
                        
                        logging.info(colored(
                            f"🔒 SAFETY CLOSURE: {symbol_short} closed for insufficient size", 
                            "yellow", attrs=['bold']
                        ))
                
                except Exception as pos_error:
                    logging.error(f"Error checking position safety: {pos_error}")
                    continue
            
            if closed_count > 0:
                logging.info(colored(f"🛡️ SAFETY MANAGER: Closed {closed_count} unsafe positions", "cyan"))
            
            return closed_count
            
        except Exception as e:
            logging.error(f"Error in position safety check: {e}")
            return 0
    
    async def _close_unsafe_position(self, exchange, symbol, contracts, position_manager):
        """
        Chiude una posizione non sicura
        """
        try:
            # Determine side for closing order
            side = 'sell' if contracts > 0 else 'buy'  # Opposite side to close
            close_size = abs(contracts)
            
            # Place closing market order
            if side == 'sell':
                order = await exchange.create_market_sell_order(symbol, close_size)
            else:
                order = await exchange.create_market_buy_order(symbol, close_size)
            
            if order and order.get('id'):
                logging.info(f"✅ Unsafe position closed: {symbol} | Order: {order['id']}")
                
                # Update position manager if the position was tracked
                if position_manager.has_position_for_symbol(symbol):
                    exit_price = float(order.get('average', 0) or order.get('price', 0))
                    if exit_price > 0:
                        # Find and close the tracked position
                        for pos_id, pos in position_manager.open_positions.items():
                            if pos.symbol == symbol:
                                position_manager.close_position_manual(pos_id, exit_price, "SAFETY_CLOSURE")
                                break
            
        except Exception as e:
            logging.error(f"Error closing unsafe position {symbol}: {e}")
    
    def validate_position_safety(self, symbol: str, position_usd: float, has_stop_loss: bool) -> tuple[bool, str]:
        """
        Valida se una posizione è sicura prima di permetterne l'apertura
        
        Args:
            symbol: Trading symbol
            position_usd: Valore notional della posizione in USD
            has_stop_loss: Se la posizione ha uno stop loss settato
            
        Returns:
            tuple[bool, str]: (is_safe, reason)
        """
        try:
            # Check minimum position size
            if position_usd < self.min_position_usd:
                return False, f"Position too small: ${position_usd:.2f} < ${self.min_position_usd:.2f} minimum"
            
            # Check stop loss requirement
            if not has_stop_loss:
                return False, f"CRITICAL: Position without stop loss is FORBIDDEN"
            
            # Calculate IM
            initial_margin = position_usd / 10.0  # Assuming 10x leverage
            if initial_margin < self.min_im_usd:
                return False, f"Initial margin too low: ${initial_margin:.2f} < ${self.min_im_usd:.2f}"
            
            return True, "Position safety validated"
            
        except Exception as e:
            return False, f"Safety validation error: {e}"
    
    async def enforce_stop_loss_for_all_positions(self, exchange, position_manager, order_manager):
        """
        Forza l'impostazione di stop loss per tutte le posizioni senza protezione
        """
        try:
            positions_without_sl = 0
            positions_fixed = 0
            
            # Get real positions from Bybit
            bybit_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_positions = [p for p in bybit_positions if float(p.get('contracts', 0)) > 0]
            
            for position in active_positions:
                try:
                    symbol = position.get('symbol')
                    stop_loss_price = position.get('stopLoss') or position.get('stopLossPrice')
                    
                    if not stop_loss_price or float(stop_loss_price) == 0:
                        positions_without_sl += 1
                        symbol_short = symbol.replace('/USDT:USDT', '')
                        
                        logging.error(colored(
                            f"❌ CRITICAL: {symbol_short} has NO STOP LOSS - attempting to fix", 
                            "red", attrs=['bold']
                        ))
                        
                        # Calculate emergency stop loss (6% from entry)
                        entry_price = float(position.get('entryPrice', 0))
                        side = position.get('side', '').lower()
                        
                        if entry_price > 0:
                            emergency_sl = entry_price * (0.94 if side in ['buy', 'long'] else 1.06)
                            
                            # Attempt to set emergency stop loss
                            sl_result = await order_manager.set_trading_stop(exchange, symbol, emergency_sl, None)
                            
                            if sl_result.success:
                                positions_fixed += 1
                                logging.info(colored(f"✅ Emergency SL set for {symbol_short}: ${emergency_sl:.6f}", "green"))
                            else:
                                logging.error(colored(
                                    f"❌ FAILED to set emergency SL for {symbol_short}: {sl_result.error}", 
                                    "red"
                                ))
                                
                                # Last resort: close the position
                                await self._close_unsafe_position(exchange, symbol, float(position.get('contracts', 0)), position_manager)
                                logging.error(colored(f"🔒 EMERGENCY CLOSURE: {symbol_short} closed due to no SL", "red"))
                
                except Exception as pos_error:
                    logging.error(f"Error enforcing SL for position: {pos_error}")
                    continue
            
            if positions_without_sl > 0:
                logging.error(colored(
                    f"🚨 SAFETY REPORT: {positions_without_sl} positions without SL detected, {positions_fixed} fixed", 
                    "red", attrs=['bold']
                ))
            
        except Exception as e:
            logging.error(f"Error enforcing stop losses: {e}")


# Global safety manager
global_position_safety_manager = PositionSafetyManager()
