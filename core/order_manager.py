#!/usr/bin/env python3
"""
🎯 ORDER MANAGER (versione pulita)

Responsabilità: Gestione ordini su Bybit
- Place market orders
- Imposta stop loss e take profit
- Setup protezione posizione

Nessuna logica di trading → solo esecuzione ordini
"""

import logging
import time
import pandas as pd
from typing import Optional, Dict
from termcolor import colored

class OrderExecutionResult:
    """Risultato standard per un ordine"""
    def __init__(self, success: bool, order_id: Optional[str] = None, error: Optional[str] = None):
        self.success = success
        self.order_id = order_id
        self.error = error

class OrderManager:
    """
    Gestione ordini Bybit semplificata con ATR-based dynamic SL
    """
    
    def __init__(self):
        # Track SL order IDs for verification
        self._sl_order_ids = {}  # {symbol: order_id}
        self._last_sl_updates = {}  # {symbol: timestamp} for debouncing
        
        # 🔧 FIX #4: Symbol blacklist management
        import config
        self._sl_retry_count = {}  # {symbol: retry_count}
        self._sl_blacklist = set(config.SYMBOL_BLACKLIST)  # Load from config
        self._blacklist_cooldown = {}  # {symbol: timestamp}
        logging.info(f"🚫 Loaded {len(self._sl_blacklist)} symbols in blacklist")
    
    def _is_blacklisted(self, symbol: str) -> bool:
        """
        🔧 FIX #4: Check if symbol is blacklisted (with cooldown expiration)
        
        Args:
            symbol: Trading symbol
            
        Returns:
            bool: True if blacklisted
        """
        if symbol not in self._sl_blacklist:
            return False
        
        # Check cooldown expiration
        import config
        cooldown_end = self._blacklist_cooldown.get(symbol, 0)
        if time.time() > cooldown_end:
            # Cooldown expired, remove from blacklist
            self._sl_blacklist.remove(symbol)
            self._sl_retry_count.pop(symbol, None)
            logging.info(f"✅ {symbol}: Removed from blacklist (cooldown expired)")
            return False
        
        remaining = int(cooldown_end - time.time())
        logging.debug(f"🚫 {symbol}: Still in blacklist ({remaining}s remaining)")
        return True
    
    def _normalize_price(self, price: float, symbol: str, exchange) -> float:
        """
        Normalize price to exchange tick size
        
        Args:
            price: Raw price
            symbol: Trading symbol
            exchange: Exchange instance
            
        Returns:
            float: Normalized price
        """
        try:
            market = exchange.market(symbol)
            tick_size = market['precision']['price']
            
            # Round to nearest tick
            normalized = round(price / tick_size) * tick_size
            
            return normalized
            
        except Exception as e:
            logging.error(f"❌ Price normalization failed for {symbol}: {e}")
            return price
    
    async def calculate_dynamic_sl(self, exchange, symbol: str, side: str, 
                                   entry_price: float, df: pd.DataFrame) -> Optional[float]:
        """
        Calculate ATR-based dynamic stop loss with exchange safety checks
        
        CRITICAL FIX: Adaptive SL based on market volatility
        
        Args:
            exchange: Exchange instance
            symbol: Trading symbol
            side: Position side ('long' or 'short')
            entry_price: Entry price
            df: DataFrame with technical indicators (must include ATR_14)
            
        Returns:
            Optional[float]: SL price or None if should skip
        """
        try:
            # 1. CHECK IF ATR IS AVAILABLE
            if 'ATR_14' not in df.columns or len(df) < 60:
                logging.warning(f"⚠️ {symbol}: ATR missing, using static -5% SL")
                sl_price = entry_price * (0.95 if side == 'long' else 1.05)
                return self._normalize_price(sl_price, symbol, exchange)
            
            # 2. GET ATR and calculate volatility percentile
            atr = df['ATR_14'].iloc[-1]
            vol_60d = df['ATR_14'].tail(60)
            vol_percentile = (vol_60d < atr).sum() / len(vol_60d) * 100
            
            # 3. ADAPTIVE ATR MULTIPLIER based on volatility (OPTIMIZED for balanced aggression)
            if vol_percentile < 30:  # Low volatility
                atr_mult = 1.3  # Tighter SL in calm markets
            elif vol_percentile < 70:  # Normal
                atr_mult = 1.8  # Balanced SL
            else:  # High volatility
                atr_mult = 2.5  # Wider SL in volatile markets
            
            # 4. CALCULATE SL DISTANCE
            sl_distance = atr * atr_mult
            
            if side == 'long':
                sl_price = entry_price - sl_distance
                # Bounds: -3% to -10% (safety limits)
                sl_price = max(entry_price * 0.90, min(sl_price, entry_price * 0.97))
            else:  # short
                sl_price = entry_price + sl_distance
                sl_price = min(entry_price * 1.10, max(sl_price, entry_price * 1.03))
            
            # 5. CHECK LIQUIDATION PRICE BUFFER
            try:
                positions = await exchange.fetch_positions([symbol])
                liq_price = None
                for pos in positions:
                    if pos['symbol'] == symbol and pos['contracts'] > 0:
                        liq_price = pos.get('liquidationPrice')
                        break
                
                if liq_price and liq_price > 0:
                    SAFETY_BUFFER = 0.02  # 2% buffer from liquidation
                    if side == 'long':
                        min_sl = liq_price * (1 + SAFETY_BUFFER)
                        sl_price = max(sl_price, min_sl)
                    else:
                        max_sl = liq_price * (1 - SAFETY_BUFFER)
                        sl_price = min(sl_price, max_sl)
            except Exception as e:
                logging.debug(f"⚠️ Could not check liquidation price: {e}")
            
            # 6. NORMALIZE TO TICK SIZE
            sl_price = self._normalize_price(sl_price, symbol, exchange)
            
            # 7. VERIFY MIN TRIGGER DISTANCE
            market = exchange.market(symbol)
            min_trigger_pct = 0.005  # Default 0.5%
            
            actual_distance = abs(sl_price - entry_price) / entry_price
            if actual_distance < min_trigger_pct:
                # Adjust to meet minimum
                if side == 'long':
                    sl_price = entry_price * (1 - min_trigger_pct * 1.1)
                else:
                    sl_price = entry_price * (1 + min_trigger_pct * 1.1)
                
                sl_price = self._normalize_price(sl_price, symbol, exchange)
                logging.debug(f"⚠️ {symbol}: SL adjusted to meet min distance {min_trigger_pct*100:.2f}%")
            
            # 8. VERIFY TICK DIFFERENCE (avoid churn)
            tick_size = market['precision']['price']
            if abs(sl_price - entry_price) < 0.5 * tick_size:
                logging.debug(f"🚫 {symbol}: SL too close to entry, skipping")
                return None
            
            logging.info(
                f"🎯 {symbol}: ATR-based SL ${sl_price:.6f} "
                f"(distance: {actual_distance*100:.2f}%, mult: {atr_mult}x, vol_pct: {vol_percentile:.1f})"
            )
            
            return sl_price
            
        except Exception as e:
            logging.error(f"❌ Dynamic SL calculation failed for {symbol}: {e}")
            # Fallback to static -5%
            sl_price = entry_price * (0.95 if side == 'long' else 1.05)
            return self._normalize_price(sl_price, symbol, exchange)
    
    async def set_stop_loss_with_order_tracking(self, exchange, symbol: str, 
                                                 side: str, sl_price: float) -> OrderExecutionResult:
        """
        Set SL as reduceOnly order with order ID tracking
        
        CRITICAL FIX: Use stop market orders instead of position field
        
        Args:
            exchange: Exchange instance
            symbol: Trading symbol
            side: Position side
            sl_price: Stop loss price
            
        Returns:
            OrderExecutionResult: Result of operation
        """
        try:
            # 1. DEBOUNCE: Check if recently updated
            last_update = self._last_sl_updates.get(symbol, 0)
            if time.time() - last_update < 30:  # 30s debounce
                logging.debug(f"🚫 {symbol}: SL update debounced (updated {time.time() - last_update:.0f}s ago)")
                return OrderExecutionResult(True, "debounced", None)
            
            # 2. CANCEL OLD SL ORDER if exists
            old_order_id = self._sl_order_ids.get(symbol)
            if old_order_id:
                try:
                    await exchange.cancel_order(old_order_id, symbol)
                    logging.debug(f"🗑️ {symbol}: Cancelled old SL order {old_order_id}")
                except Exception as e:
                    logging.debug(f"Old SL order already gone: {e}")
            
            # 3. GET POSITION SIZE
            positions = await exchange.fetch_positions([symbol])
            position_size = 0
            position_side = None
            # 🔧 FIX #3: DEFENSIVE GUARDS for Bybit API responses
            for pos in positions:
                if pos.get('symbol') == symbol and float(pos.get('contracts', 0) or 0) > 0:
                    position_size = float(pos.get('contracts', 0) or 0)
                    position_side = pos.get('side')
                    break
            
            if position_size == 0:
                logging.warning(f"⚠️ {symbol}: Position not found for SL order")
                return OrderExecutionResult(False, None, "Position not found")
            
            # 4. CREATE STOP MARKET ORDER (reduceOnly)
            order_side = 'sell' if side == 'long' else 'buy'
            
            order = await exchange.create_order(
                symbol=symbol,
                type='stop_market',
                side=order_side,
                amount=position_size,
                params={
                    'stopPrice': sl_price,
                    'reduceOnly': True,
                    'triggerPrice': sl_price,
                    'triggerBy': 'LastPrice'
                }
            )
            
            # 5. TRACK ORDER ID
            new_order_id = order.get('id')
            if new_order_id:
                self._sl_order_ids[symbol] = new_order_id
                self._last_sl_updates[symbol] = time.time()
                
                logging.info(colored(
                    f"✅ {symbol}: SL order created #{new_order_id} @ ${sl_price:.6f}",
                    "green", attrs=['bold']
                ))
                return OrderExecutionResult(True, new_order_id, None)
            else:
                logging.warning(f"⚠️ {symbol}: No order ID returned for SL")
                return OrderExecutionResult(False, None, "No order ID")
        
        except Exception as e:
            logging.error(f"❌ {symbol}: SL order failed - {e}")
            return OrderExecutionResult(False, None, str(e))
    
    async def verify_sl_via_orders(self, exchange, symbol: str) -> bool:
        """
        Verify SL exists by checking open stop orders (not position field)
        
        CRITICAL FIX: Check actual orders instead of position field
        
        Args:
            exchange: Exchange instance
            symbol: Trading symbol
            
        Returns:
            bool: True if SL order found
        """
        try:
            open_orders = await exchange.fetch_open_orders(symbol)
            
            # Look for stop orders
            for order in open_orders:
                if order['type'] in ['stop', 'stop_market', 'stop_limit']:
                    if order.get('reduceOnly', False):
                        # Found SL order
                        order_id = order.get('id')
                        if order_id:
                            self._sl_order_ids[symbol] = order_id
                        return True
            
            return False
        
        except Exception as e:
            logging.error(f"❌ {symbol}: Failed to verify SL orders - {e}")
            return False  # Assume missing on error (safe)

    async def place_market_order(self, exchange, symbol: str, side: str, size: float) -> OrderExecutionResult:
        """
        Esegue un market order su Bybit
        """
        try:
            logging.info(colored(f"📈 PLACING MARKET {side.upper()} ORDER: {symbol} | Size: {size:.4f}",
                                 "cyan", attrs=['bold']))

            if side.lower() == 'buy':
                order = await exchange.create_market_buy_order(symbol, size)
            else:
                order = await exchange.create_market_sell_order(symbol, size)

            if not order or not order.get('id'):
                error_msg = f"Invalid order response: {order}"
                logging.error(colored(f"❌ {error_msg}", "red"))
                return OrderExecutionResult(False, None, error_msg)

            order_id = order.get('id') or 'N/A'
            entry_price = order.get('average') or order.get('price') or 0.0
            status = order.get('status') or 'unknown'

            if entry_price and entry_price > 0:
                logging.info(colored(
                    f"✅ MARKET ORDER SUCCESS: ID {order_id} | Price: ${entry_price:.6f} | Status: {status.upper()}",
                    "green", attrs=['bold']
                ))
            else:
                logging.info(colored(
                    f"✅ MARKET ORDER SUCCESS: ID {order_id} | Price: N/A | Status: {status.upper()}",
                    "green", attrs=['bold']
                ))

            return OrderExecutionResult(True, order_id, None)

        except Exception as e:
            error_msg = f"Market order failed: {str(e)}"
            logging.error(colored(f"❌ {error_msg}", "red"))
            return OrderExecutionResult(False, None, error_msg)

    async def set_trading_stop(self, exchange, symbol: str,
                               stop_loss: float = None,
                               take_profit: float = None,
                               position_idx: int = None,
                               side: str = None) -> OrderExecutionResult:
        """
        Imposta SL/TP su Bybit (endpoint: /v5/position/trading-stop)
        
        FIX #1: Enhanced with automatic TP calculation and R/R verification
        - Calculates TP based on config.TP_ROE_TARGET if not provided
        - Verifies minimum R/R ratio (config.TP_MIN_DISTANCE_FROM_SL)
        - Validates TP covers all trading costs
        
        FIX #4: Blacklist management for problematic symbols
        """
        try:
            import config
            from core.cost_calculator import global_cost_calculator
            from core.price_precision_handler import global_price_precision_handler
            
            # 🔧 FIX #4: Check blacklist BEFORE attempting
            if self._is_blacklisted(symbol):
                logging.warning(f"🚫 {symbol}: In blacklist, skipping SL")
                return OrderExecutionResult(False, None, "symbol_blacklisted")
            
            # Converte il simbolo nel formato Bybit (BTC/USDT:USDT → BTCUSDT)
            bybit_symbol = symbol.replace('/USDT:USDT', 'USDT').replace('/', '')

            # Get position details for TP calculation
            entry_price = None
            position_side = None
            
            # CRITICAL FIX: Auto-detect position_idx and get entry price
            if position_idx is None or entry_price is None:
                try:
                    positions = await exchange.fetch_positions([symbol])
                    for pos in positions:
                        if pos.get('symbol') == symbol and float(pos.get('contracts', 0)) != 0:
                            # Get entry price for TP calculation
                            entry_price = float(pos.get('entryPrice', 0))
                            position_side = pos.get('side')
                            
                            # Get position_idx from actual position
                            pos_info = pos.get('info', {})
                            detected_idx = pos_info.get('positionIdx', 0)
                            try:
                                position_idx = int(detected_idx)
                            except:
                                position_idx = 0
                            
                            mode_name = {0: "One-Way", 1: "Hedge-Long", 2: "Hedge-Short"}.get(position_idx, "Unknown")
                            logging.debug(f"🔧 Auto-detected position_idx={position_idx} ({mode_name}) for {symbol}")
                            break
                except Exception as e:
                    logging.warning(f"⚠️ Failed to auto-detect position_idx for {symbol}: {e}")
                    position_idx = 0  # Fallback to One-Way Mode
                
                # If still None (no position found), default to 0
                if position_idx is None:
                    position_idx = 0
                    logging.debug(f"🔧 No position found, defaulting to position_idx=0 for {symbol}")
            
            # FIX #5: COST-AWARE TP Calculation 
            if take_profit is None and getattr(config, 'TP_ENABLED', False) and entry_price:
                # Determine position side if not provided
                if side is None:
                    side = position_side
                
                if side and stop_loss:
                    # CRITICAL: Normalize side format (handle both 'long'/'short' and 'buy'/'sell')
                    normalized_side = side.lower()
                    is_long = normalized_side in ['long', 'buy']
                    
                    # 🔧 FIX #5: Calculate trading costs (TP exit via limit order)
                    costs = global_cost_calculator.calculate_total_round_trip_cost(
                        1000,  # Dummy notional value
                        is_sl_exit=False,  # TP = limit order
                        is_volatile=False  # Assume normal conditions
                    )
                    costs_roe = costs['total_cost_roe']
                    
                    # Calculate SL distance in ROE
                    sl_distance_pct = abs(entry_price - stop_loss) / entry_price
                    sl_roe = sl_distance_pct * config.LEVERAGE * 100
                    
                    # Calculate minimum TP ROE that covers: SL risk + costs + min profit
                    min_rr = getattr(config, 'TP_MIN_DISTANCE_FROM_SL', 2.5)
                    min_profit_roe = getattr(config, 'MIN_PROFIT_AFTER_COSTS', 8.0)
                    
                    # TP ROE = (SL ROE × R/R) + costs + min profit
                    tp_roe = (sl_roe * min_rr) + costs_roe + min_profit_roe
                    
                    # Convert ROE back to price %
                    tp_distance_pct = tp_roe / (config.LEVERAGE * 100)
                    
                    if is_long:
                        take_profit = entry_price * (1 + tp_distance_pct)
                    else:  # short/sell
                        take_profit = entry_price * (1 - tp_distance_pct)
                    
                    # Round to exchange precision
                    take_profit = round(take_profit, 6)
                    
                    # CRITICAL VALIDATION: Verify TP is in correct direction
                    if is_long and take_profit <= entry_price:
                        logging.error(f"❌ {symbol}: Invalid TP for LONG (${take_profit} <= ${entry_price}), disabling TP")
                        take_profit = None
                    elif not is_long and take_profit >= entry_price:
                        logging.error(f"❌ {symbol}: Invalid TP for SHORT (${take_profit} >= ${entry_price}), disabling TP")
                        take_profit = None
                    else:
                        net_profit_roe = tp_roe - sl_roe - costs_roe
                        logging.info(colored(
                            f"💰 {symbol}: COST-AWARE TP ${take_profit:.6f}\n"
                            f"   TP ROE: +{tp_roe:.1f}% | SL ROE: -{sl_roe:.1f}% | Costs: -{costs_roe:.1f}%\n"
                            f"   Net Profit: +{net_profit_roe:.1f}% ROE (after all costs)",
                            "cyan"
                        ))
            
            # FIX #1: Verify R/R ratio if both SL and TP are set
            if stop_loss and take_profit and entry_price:
                sl_distance_pct = abs(entry_price - stop_loss) / entry_price
                tp_distance_pct = abs(take_profit - entry_price) / entry_price
                
                actual_rr = tp_distance_pct / sl_distance_pct if sl_distance_pct > 0 else 0
                min_rr = getattr(config, 'TP_MIN_DISTANCE_FROM_SL', 2.5)
                
                if actual_rr < min_rr:
                    logging.warning(
                        f"⚠️ {symbol}: R/R ratio {actual_rr:.2f}:1 < minimum {min_rr}:1. "
                        f"Adjusting TP to maintain proper risk/reward."
                    )
                    
                    # Adjust TP to maintain minimum R/R
                    required_tp_distance = sl_distance_pct * min_rr
                    
                    if side and side.lower() in ['long', 'buy']:
                        take_profit = entry_price * (1 + required_tp_distance)
                    else:
                        take_profit = entry_price * (1 - required_tp_distance)
                    
                    # Round to exchange precision
                    take_profit = round(take_profit, 2)
                    
                    # Recalculate actual R/R
                    tp_distance_pct = abs(take_profit - entry_price) / entry_price
                    actual_rr = tp_distance_pct / sl_distance_pct
                    
                    logging.info(f"✅ {symbol}: TP adjusted to ${take_profit:.6f} (R/R: {actual_rr:.2f}:1)")

            sl_text = f"${stop_loss:.6f}" if stop_loss else "None"
            tp_text = f"${take_profit:.6f}" if take_profit else "None"
            idx_text = {0: "Both", 1: "LONG", 2: "SHORT"}.get(position_idx, str(position_idx))

            logging.debug(colored(
                f"🛡️ SETTING TRADING STOP: {bybit_symbol} ({idx_text}) | SL: {sl_text} | TP: {tp_text}",
                "yellow", attrs=['bold']
            ))

            # Use ONLY Full mode (Partial requires slSize/tpSize which we don't have)
            params = {
                'category': 'linear',
                'symbol': bybit_symbol,
                'tpslMode': 'Full',
                'positionIdx': position_idx
            }

            if stop_loss:
                params['stopLoss'] = str(stop_loss)
            if take_profit:
                params['takeProfit'] = str(take_profit)

            # Debug log parametri API
            logging.debug(f"🔧 API params: {params}")
            
            result = await exchange.private_post_v5_position_trading_stop(params)
            
            # Debug log risposta (ridotto)  
            logging.debug(f"🔧 Bybit response: {result}")

            ret_code = result.get('retCode', -1)
            ret_msg = result.get('retMsg', 'Unknown response')

            # FIXED: Proper handling of Bybit API responses
            # retCode 0 = SUCCESS, retCode 34040 = already set correctly
            if ret_code == 0 or (isinstance(ret_code, str) and ret_code == "0"):
                # ✅ SUCCESS: Reset retry counter
                self._sl_retry_count[symbol] = 0
                
                if "ok" in ret_msg.lower():
                    logging.info(colored(
                        f"✅ TRADING STOP SUCCESS: {bybit_symbol} | Bybit confirmed: {ret_msg}",
                        "green", attrs=['bold']
                    ))
                else:
                    logging.info(colored(
                        f"✅ TRADING STOP SUCCESS: {bybit_symbol} | Response: {ret_msg}",
                        "green", attrs=['bold']
                    ))
                return OrderExecutionResult(True, f"trading_stop_{bybit_symbol}", None)
            elif ret_code == 34040 and "not modified" in ret_msg.lower():
                # ACCEPTABLE: Stop loss already exists and is correct
                self._sl_retry_count[symbol] = 0  # Reset on success
                logging.debug(colored(f"📝 {bybit_symbol}: Stop loss already set correctly ({ret_msg})", "cyan"))
                return OrderExecutionResult(True, f"trading_stop_{bybit_symbol}_existing", None)
            else:
                # 🔧 FIX #4: INCREMENT RETRY on error
                retry = self._sl_retry_count.get(symbol, 0) + 1
                self._sl_retry_count[symbol] = retry
                
                # ACTUAL ERROR: Only log as critical if it's a real error
                if ret_code != 0:
                    error_msg = f"Stop loss setting failed - Bybit error {ret_code}: {ret_msg}"
                    logging.warning(colored(f"⚠️ {error_msg} (retry {retry}/{config.SL_MAX_RETRIES})", "yellow"))
                    
                    # Check if max retries reached
                    if retry >= config.SL_MAX_RETRIES:
                        self._sl_blacklist.add(symbol)
                        self._blacklist_cooldown[symbol] = time.time() + config.SL_RETRY_COOLDOWN
                        logging.error(colored(
                            f"❌ {symbol}: Max retries reached, blacklisted for {config.SL_RETRY_COOLDOWN}s",
                            "red", attrs=['bold']
                        ))
                    
                    return OrderExecutionResult(False, None, error_msg)
                else:
                    # Fallback for edge cases
                    logging.info(colored(f"✅ {bybit_symbol}: Stop loss handled by Bybit", "green"))
                    return OrderExecutionResult(True, f"trading_stop_{bybit_symbol}_fallback", None)

        except Exception as e:
            # 🔧 SMART ERROR HANDLING: Check error types
            error_str = str(e).lower()
            
            if "34040" in error_str and "not modified" in error_str:
                # SUCCESS: Stop loss already exists and correct
                logging.debug(colored(f"📝 {symbol}: Stop loss already set correctly", "cyan"))
                return OrderExecutionResult(True, f"trading_stop_{symbol.replace('/USDT:USDT', '')}_existing", "already_set")
            elif "10001" in error_str and ("greater" in error_str or "should" in error_str):
                # WARNING: Stop loss validation error (price rules)
                error_msg = f"Stop loss validation failed - {str(e)}"
                logging.warning(colored(f"⚠️ {error_msg}", "yellow"))
                return OrderExecutionResult(False, None, error_msg)
            else:
                # Real critical error
                error_msg = f"CRITICAL: Stop loss setting failed - {str(e)}"
                logging.error(colored(f"❌ {error_msg}", "red"))
                return OrderExecutionResult(False, None, error_msg)

    async def setup_position_protection(self, exchange, symbol: str, side: str, size: float,
                                        sl_price: float, tp_price: float) -> Dict[str, OrderExecutionResult]:
        """
        Wrapper per applicare subito protezione (SL + TP) a una nuova posizione
        """
        logging.info(colored(f"🛡️ APPLYING PROTECTION: {symbol}", "yellow", attrs=['bold']))
        result = await self.set_trading_stop(exchange, symbol, sl_price, tp_price)
        return {
            'stop_loss': result,
            'take_profit': result
        }

# Istanza globale
global_order_manager = OrderManager()
