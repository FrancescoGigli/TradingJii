#!/usr/bin/env python3
"""
🚀 TRADING ORCHESTRATOR

SINGLE RESPONSIBILITY: Coordinamento trading workflow
- Orchestrate signal execution
- Coordinate risk management
- Manage position lifecycle
- Handle existing position protection
- Clean error handling and logging

GARANTISCE: Flusso trading semplice e affidabile
"""

import logging
import asyncio
from typing import Dict, List, Tuple
from termcolor import colored

import config

# Import clean modules
from core.order_manager import global_order_manager
from core.risk_calculator import global_risk_calculator, MarketData
# STEP 1 FIX: Import ThreadSafePositionManager instead of SmartPositionManager
from core.thread_safe_position_manager import global_thread_safe_position_manager, ThreadSafePosition as Position
from core.price_precision_handler import global_price_precision_handler


# CRITICAL FIX: Import new unified managers
try:
    from core.thread_safe_position_manager import global_thread_safe_position_manager
    from core.smart_api_manager import global_smart_api_manager
    UNIFIED_MANAGERS_AVAILABLE = True
    logging.debug("🔧 Unified managers integration enabled in TradingOrchestrator")
except ImportError as e:
    UNIFIED_MANAGERS_AVAILABLE = False
    logging.warning(f"⚠️ Unified managers not available: {e}")

# Import trade history logger
try:
    from core.trade_history_logger import log_trade_opened_from_position
    TRADE_HISTORY_LOGGER_AVAILABLE = True
except ImportError:
    TRADE_HISTORY_LOGGER_AVAILABLE = False
    logging.warning("⚠️ Trade History Logger not available in TradingOrchestrator")

# COORDINATORS: Removed unused position_opening_coordinator (part of code simplification)


class TradingResult:
    """Simple result for trading operations"""
    def __init__(self, success: bool, position_id: str = "", error: str = "", order_ids: Dict = None):
        self.success = success
        self.position_id = position_id
        self.error = error
        self.order_ids = order_ids or {}


# ----------------------------- utilities ------------------------------------ #

async def _normalize_sl_price_new(exchange, symbol: str, side: str, entry: float, raw_sl: float) -> float:
    """
    🔧 FIXED: Usa il nuovo PricePrecisionHandler per normalizzazione accurata
    """
    try:
        normalized_sl, success = await global_price_precision_handler.normalize_stop_loss_price(
            exchange, symbol, side, entry, raw_sl
        )
        
        if success:
            logging.debug(f"✅ {symbol} SL normalized with precision handler: {raw_sl:.6f} → {normalized_sl:.6f}")
            return normalized_sl
        else:
            logging.warning(f"⚠️ {symbol} SL normalization failed, using fallback")
            return raw_sl
            
    except Exception as e:
        logging.error(f"❌ Error in SL normalization for {symbol}: {e}")
        return raw_sl


# --------------------------- orchestrator ----------------------------------- #

class TradingOrchestrator:
    """
    Clean trading workflow coordinator

    PHILOSOPHY: Simple orchestration, clear results, minimal complexity
    """

    def __init__(self):
        self.order_manager = global_order_manager
        self.risk_calculator = global_risk_calculator
        
        # STEP 1 FIX: Use ONLY ThreadSafePositionManager (eliminate SmartPositionManager fallback)
        if global_thread_safe_position_manager is None:
            raise ImportError("CRITICAL: ThreadSafePositionManager required for TradingOrchestrator")
        
        self.position_manager = global_thread_safe_position_manager
        logging.info("🔒 TradingOrchestrator using ThreadSafePositionManager ONLY")
        
        # Initialize unified managers
        if UNIFIED_MANAGERS_AVAILABLE:
            self.api_manager = global_smart_api_manager
            logging.debug("🔧 TradingOrchestrator: Unified managers initialized")

    # --------------------------------------------------------------------- #
    #                      NEW TRADE (open + SL 6%)                         #
    # --------------------------------------------------------------------- #
    async def execute_new_trade(self, exchange, signal_data: Dict, market_data: MarketData, balance: float, margin_override: float = None) -> TradingResult:
        """
        Esegue un nuovo trade completo di protezione iniziale:
        - imposta leva e margine isolato
        - piazza market order
        - applica SL iniziale = ±6% sul prezzo (≈60% del margine con leva 10)
        - registra la posizione per il trailing
        
        Args:
            margin_override: Se fornito, usa questo margin invece di calcolarlo (portfolio sizing)
        """
        try:
            # 🔧 FIX #3: DEFENSIVE GUARDS - Validate signal_data inputs
            symbol = signal_data.get('symbol', 'UNKNOWN')
            if symbol == 'UNKNOWN' or not symbol:
                return TradingResult(False, "", "Invalid signal_data: missing or empty symbol")
            
            side = signal_data.get('signal_name', 'buy')
            if not side:
                return TradingResult(False, "", f"Invalid signal_data: missing signal_name for {symbol}")
            side = side.lower()
            
            if side not in ['buy', 'sell', 'long', 'short']:
                return TradingResult(False, "", f"Invalid signal side '{side}' for {symbol}")
            
            # Normalize to buy/sell
            if side == 'long':
                side = 'buy'
            elif side == 'short':
                side = 'sell'
            
            confidence = float(signal_data.get('confidence', 0.7) or 0.7)

            logging.info(colored(f"🎯 EXECUTING NEW TRADE: {symbol} {side.upper()}", "cyan", attrs=['bold']))

            # Evita doppie aperture (tracker + Bybit)
            if self.position_manager.has_position_for_symbol(symbol):
                error = f"Position already exists for {symbol} in tracker"
                logging.warning(colored(f"⚠️ {error}", "yellow"))
                return TradingResult(False, "", error)

            try:
                bybit_positions = await exchange.fetch_positions([symbol])
                for pos in bybit_positions:
                    contracts = float(pos.get('contracts', 0) or 0)
                    if abs(contracts) > 0:
                        error = f"Position already exists for {symbol} on Bybit ({contracts:+.4f} contracts)"
                        logging.warning(colored(f"⚠️ BYBIT CHECK: {error}", "yellow"))
                        return TradingResult(False, "", error)
            except Exception as bybit_check_error:
                logging.warning(f"Could not verify Bybit positions for {symbol}: {bybit_check_error}")

            # 1) 🆕 PORTFOLIO SIZING: Usa margin precalcolato se fornito
            if margin_override is not None:
                # Portfolio sizing: usa margin fornito
                notional_value = margin_override * config.LEVERAGE
                position_size = notional_value / market_data.price
                
                # 🔧 CRITICAL FIX: Calculate SL immediately when using portfolio sizing
                stop_loss_price_calculated = self.risk_calculator.calculate_stop_loss_fixed(
                    market_data.price, side
                )
                
                # Crea PositionLevels con margin override E SL già calcolato
                from core.risk_calculator import PositionLevels
                levels = PositionLevels(
                    margin=margin_override,
                    position_size=position_size,
                    stop_loss=stop_loss_price_calculated,  # ✅ FIX: SL calcolato subito
                    take_profit=0,  # Non usato
                    risk_pct=5.0,  # Fixed -5%
                    reward_pct=0,
                    risk_reward_ratio=0
                )
                logging.info(colored(f"💰 Using PORTFOLIO SIZING: ${margin_override:.2f} margin (precalculated)", "cyan"))
                logging.debug(colored(f"🛡️ SL calculated (portfolio): ${stop_loss_price_calculated:.6f} (-5% from ${market_data.price:.6f})", "cyan"))
            else:
                # Fallback: calcolo classico
                levels = self.risk_calculator.calculate_position_levels(market_data, side, confidence, balance)
                logging.debug(f"⚠️ Using fallback margin calculation: ${levels.margin:.2f}")

            # 2) Portfolio check
            existing_margins = [pos.position_size / pos.leverage for pos in self.position_manager.get_active_positions()]
            ok, reason = self.risk_calculator.validate_portfolio_margin(existing_margins, levels.margin, balance)
            if not ok:
                logging.warning(colored(f"⚠️ {reason}", "yellow"))
                return TradingResult(False, "", reason)

            # 3) Imposta leva + isolated
            try:
                await exchange.set_leverage(config.LEVERAGE, symbol)
                await exchange.set_margin_mode('isolated', symbol)
            except Exception as e:
                logging.warning(colored(f"⚠️ {symbol}: leverage/margin setup failed: {e}", "yellow"))

            # 4) Log livelli
            notional = levels.margin * config.LEVERAGE
            logging.info(colored(f"💰 CALCULATED LEVELS for {symbol}:", "white"))
            logging.info(colored(f"   Margin: ${levels.margin:.2f} | Size: {levels.position_size:.4f} | Notional: ${notional:.2f}", "white"))
            logging.info(colored(f"   SL(calc): ${levels.stop_loss:.6f} | TP(calc): ${levels.take_profit:.6f}", "white"))

            # 5) 🔧 CRITICAL FIX: Normalize position size before placing order
            normalized_size, size_success = await global_price_precision_handler.normalize_position_size(
                exchange, symbol, levels.position_size
            )
            
            if not size_success:
                logging.warning(f"⚠️ {symbol}: Size normalization failed, using original")
                normalized_size = levels.position_size
            
            # 🔧 FIX #2: PRE-FLIGHT VALIDATION - Check size requirements BEFORE placing order
            precision_info = await global_price_precision_handler.get_symbol_precision(exchange, symbol)
            min_amount = precision_info.get('min_amount', 0.001)
            max_amount = precision_info.get('max_amount', 1000000)
            
            # Check minimum - CRITICAL FIX: Skip expensive symbols instead of forcing minimum
            if normalized_size < min_amount:
                # Calculate what margin would be needed
                required_margin = (min_amount * market_data.price) / config.LEVERAGE
                error_msg = f"Symbol too expensive: need ${required_margin:.2f} margin but have ${levels.margin:.2f} - SKIPPING"
                logging.warning(colored(f"⏭️ {symbol}: {error_msg}", "yellow"))
                logging.warning(colored(f"   Size {normalized_size:.6f} < minimum {min_amount}", "yellow"))
                return TradingResult(False, "", error_msg)
            
            # Check maximum
            if normalized_size > max_amount:
                error_msg = f"Position size {normalized_size:.6f} exceeds maximum {max_amount} for {symbol}"
                logging.error(colored(f"❌ PRE-FLIGHT FAILED: {error_msg}", "red"))
                return TradingResult(False, "", error_msg)
            
            # ✅ VALIDATION PASSED
            logging.info(colored(f"✅ Pre-flight OK: size {normalized_size:.6f} within [{min_amount}, {max_amount}]", "green"))
            logging.info(colored(f"📏 Position size: {levels.position_size:.6f} → {normalized_size:.6f}", "cyan"))
            
            # 6) Market order with normalized size
            market_result = await self.order_manager.place_market_order(exchange, symbol, side, normalized_size)
            if not market_result.success:
                return TradingResult(False, "", f"Market order failed: {market_result.error}")

            # 🔧 FIX #6: RACE CONDITION - Wait for Bybit to process the position before setting SL
            # Critical: Without this wait, position may not exist yet when we try to set SL
            logging.debug(f"⏳ {symbol}: Waiting 3s for Bybit to process market order...")
            await asyncio.sleep(3)

            # 7) Calculate and apply FIXED Stop Loss (-5%)
            stop_loss_price = self.risk_calculator.calculate_stop_loss_fixed(
                market_data.price, side
            )
            
            # Normalize SL price for Bybit precision
            normalized_sl = await _normalize_sl_price_new(
                exchange, symbol, side, market_data.price, stop_loss_price
            )
            
            # Apply SL on Bybit (NO take profit)
            # position_idx=0 automatically used (One-Way Mode)
            sl_result = await self.order_manager.set_trading_stop(
                exchange, symbol, 
                stop_loss=normalized_sl,
                take_profit=None  # NO TP as requested
            )
            
            if sl_result.success:
                # Calculate REAL margin loss percentage from ACTUAL normalized SL
                price_change_pct = abs((normalized_sl - market_data.price) / market_data.price) * 100
                margin_loss_pct = price_change_pct * config.LEVERAGE
                
                logging.info(colored(
                    f"✅ {symbol}: Stop Loss set at ${normalized_sl:.6f} ({'-' if side == 'buy' else '+'}{price_change_pct:.2f}%)",
                    "green"
                ))
                logging.info(colored(
                    f"   📊 Rischio REALE: {price_change_pct:.2f}% prezzo × {config.LEVERAGE}x leva = "
                    f"-{margin_loss_pct:.1f}% MARGIN", "yellow"
                ))
            else:
                logging.warning(colored(
                    f"⚠️ {symbol}: Stop Loss failed to set: {sl_result.error}", "yellow"
                ))
            
            # 8) Create position in tracker (SL già applicato su Bybit)
            position_usd_value = levels.margin * config.LEVERAGE  # USD notional value
            
            # Build DETAILED ML open reason with all prediction details
            symbol_short = symbol.replace('/USDT:USDT', '')
            side_name = "BUY" if side == 'buy' else "SELL"
            
            # Start with base prediction
            open_reason_parts = [f"ML {side_name} {confidence:.0%}"]
            
            # Add timeframe predictions if available
            tf_predictions = signal_data.get('tf_predictions', {})
            if tf_predictions:
                tf_summary = []
                for tf, pred_data in tf_predictions.items():
                    if isinstance(pred_data, dict):
                        pred = pred_data.get('prediction', -1)
                        pred_conf = pred_data.get('confidence', 0)
                        if pred == 1:  # BUY
                            tf_summary.append(f"{tf}:↑{pred_conf:.0%}")
                        elif pred == 0:  # SELL
                            tf_summary.append(f"{tf}:↓{pred_conf:.0%}")
                if tf_summary:
                    open_reason_parts.append("TF[" + " ".join(tf_summary) + "]")
            
            # Add RL approval if available
            if signal_data.get('rl_approved'):
                rl_conf = signal_data.get('rl_confidence', 0)
                open_reason_parts.append(f"RL✓{rl_conf:.0%}")
            
            # Add entry price and timestamp for reference
            open_reason_parts.append(f"@${market_data.price:.6f}")
            
            open_reason = " | ".join(open_reason_parts)
            
            # Extract ADX from signal_data if available
            adx_value = 0.0
            if 'adx' in signal_data:
                adx_value = float(signal_data.get('adx', 0.0))
            elif 'indicators' in signal_data and isinstance(signal_data['indicators'], dict):
                adx_value = float(signal_data['indicators'].get('adx', 0.0))
            elif hasattr(market_data, 'adx'):
                adx_value = float(market_data.adx) if market_data.adx else 0.0
            
            position_id = self.position_manager.thread_safe_create_position(
                symbol=symbol,
                side=side,
                entry_price=market_data.price,
                position_size=position_usd_value,  # USD value
                leverage=config.LEVERAGE,
                confidence=confidence,
                open_reason=open_reason,  # FIX: Pass ML prediction details
                atr=market_data.atr,  # Pass technical indicators for dashboard
                adx=adx_value,  # FIX: Extract ADX from signal_data
                volatility=market_data.volatility
                # Note: SL già applicato su Bybit, non serve passarlo al tracker
            )
            
            # 🎯 ADAPTIVE SIZING: Register opening in memory
            try:
                from config import ADAPTIVE_SIZING_ENABLED
                if ADAPTIVE_SIZING_ENABLED:
                    from core.adaptive_position_sizing import global_adaptive_sizing
                    if global_adaptive_sizing:
                        global_adaptive_sizing.register_opening(
                            symbol=symbol,
                            margin_used=levels.margin,
                            wallet_equity=balance
                        )
                        logging.debug(f"🎯 Adaptive sizing: Registered opening for {symbol}")
            except Exception as adaptive_error:
                logging.debug(f"⚠️ Failed to register opening in adaptive sizing: {adaptive_error}")
            
            
            #  SAVE REAL IM: Store actual margin used (will be updated by sync)
            try:
                with self.position_manager._lock:
                    if position_id in self.position_manager._open_positions:
                        self.position_manager._open_positions[position_id].real_initial_margin = levels.margin
                        logging.debug(f"💰 Real IM saved for {symbol}: ${levels.margin:.2f}")
            except Exception as im_error:
                logging.debug(f"⚠️ Failed to save real IM: {im_error}")
            
            logging.info(colored(
                f"✅ {symbol}: Position opened with fixed SL protection", "green"
            ))
            
            # 📝 LOG TRADE OPENED to history
            if TRADE_HISTORY_LOGGER_AVAILABLE:
                try:
                    # Get position object to log
                    with self.position_manager._lock:
                        if position_id in self.position_manager._open_positions:
                            position_obj = self.position_manager._open_positions[position_id]
                            log_trade_opened_from_position(position_obj)
                except Exception as log_err:
                    logging.warning(f"⚠️ Failed to log trade opened: {log_err}")

            return TradingResult(True, position_id, "", {
                'main': market_result.order_id,
                'stop_loss': 'set' if sl_result.success else 'failed',
                'sl_price': normalized_sl
            })

        except Exception as e:
            err = f"Trade execution failed: {str(e)}"
            logging.error(colored(f"❌ {err}", "red"))
            return TradingResult(False, "", err)

    # --------------------------------------------------------------------- #
    #                  EXISTING POSITIONS (sync + SL 6%)                    #
    # --------------------------------------------------------------------- #
    async def protect_existing_positions(self, exchange) -> Dict[str, TradingResult]:
        """
        Sincronizza posizioni reali da Bybit e applica Stop Loss -5% se mancante
        """
        results: Dict[str, TradingResult] = {}

        try:
            real_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_positions = [p for p in real_positions if float(p.get('contracts', 0) or 0) != 0]
            
            if not active_positions:
                logging.info(colored("🆕 No existing positions on Bybit - starting fresh", "green"))
                return {}

            # Sync with ThreadSafePositionManager
            newly_opened, _ = await self.position_manager.thread_safe_sync_with_bybit(exchange)
            
            if newly_opened:
                logging.info(colored(f"📥 Synced {len(newly_opened)} positions from Bybit", "cyan"))
                logging.info(colored(f"🛡️ Applying Stop Loss protection to synced positions...", "yellow"))

            # Apply SL protection to synced positions
            for position in newly_opened:
                try:
                    symbol = position.symbol
                    symbol_short = symbol.replace('/USDT:USDT', '')
                    
                    # Calculate SL -5% from entry price
                    stop_loss_price = self.risk_calculator.calculate_stop_loss_fixed(
                        position.entry_price, position.side
                    )
                    
                    # Normalize SL price
                    normalized_sl = await _normalize_sl_price_new(
                        exchange, symbol, position.side, 
                        position.entry_price, stop_loss_price
                    )
                    
                    # Apply SL on Bybit (position_idx=0 for One-Way Mode)
                    sl_result = await self.order_manager.set_trading_stop(
                        exchange, symbol,
                        stop_loss=normalized_sl,
                        take_profit=None
                    )
                    
                    if sl_result.success:
                        # Calculate REAL percentage from entry price
                        price_change_pct = abs((normalized_sl - position.entry_price) / position.entry_price) * 100
                        margin_loss_pct = price_change_pct * config.LEVERAGE
                        
                        logging.info(colored(
                            f"✅ {symbol_short}: Stop Loss set at ${normalized_sl:.6f} "
                            f"({'-' if position.side == 'buy' else '+'}{price_change_pct:.2f}% price, "
                            f"-{margin_loss_pct:.1f}% margin)",
                            "green"
                        ))
                        results[symbol] = TradingResult(
                            True, position.position_id, "",
                            {'tracking_type': 'bybit_sync', 'sl_applied': True, 'sl_price': normalized_sl}
                        )
                    else:
                        logging.warning(colored(
                            f"⚠️ {symbol_short}: Failed to set SL: {sl_result.error}",
                            "yellow"
                        ))
                        results[symbol] = TradingResult(
                            True, position.position_id, "",
                            {'tracking_type': 'bybit_sync', 'sl_applied': False, 'error': sl_result.error}
                        )
                    
                except Exception as pos_error:
                    symbol_short = position.symbol.replace('/USDT:USDT', '')
                    logging.error(colored(
                        f"❌ {symbol_short}: Error applying SL: {pos_error}",
                        "red"
                    ))
                    results[position.symbol] = TradingResult(
                        True, position.position_id, str(pos_error),
                        {'tracking_type': 'bybit_sync', 'sl_applied': False}
                    )
            
            return results

        except Exception as e:
            err = f"Error in position sync: {str(e)}"
            logging.error(colored(f"❌ {err}", "red"))
            return {'error': TradingResult(False, "", err)}

    # --------------------------------------------------------------------- #
    #                      TRAILING UPDATE / EXIT                           #
    # --------------------------------------------------------------------- #
    async def update_trailing_positions(self, exchange) -> List[Position]:
        """
        REMOVED: Trailing logic eliminated - positions managed manually
        
        This method is kept for compatibility but does nothing now.
        """
        return []

    # --------------------------------------------------------------------- #
    #                            SUMMARY / CHECKS                           #
    # --------------------------------------------------------------------- #
    def get_trading_summary(self) -> Dict:
        """Get comprehensive trading summary"""
        try:
            session = self.position_manager.get_session_summary()
            order_summary = self.order_manager.get_placed_orders_summary()
            return {
                'positions': {
                    'active_count': session['active_positions'],
                    'used_margin': session['used_margin'],
                    'total_pnl_usd': session['total_pnl_usd'],
                    'available_balance': session['available_balance']
                },
                'orders': {
                    'total_placed': order_summary['total_orders'],
                    'stop_losses': order_summary['stop_losses'],
                    'take_profits': order_summary['take_profits']
                },
                'session': {
                    'balance': session['balance'],
                    'pnl_pct': session['total_pnl_pct']
                }
            }
        except Exception as e:
            logging.error(f"Error getting trading summary: {e}")
            return {}

    def can_open_new_position(self, symbol: str, balance: float) -> Tuple[bool, str]:
        """Check if new position can be opened"""
        try:
            from config import MAX_CONCURRENT_POSITIONS
            if self.position_manager.has_position_for_symbol(symbol):
                return False, f"Position already exists for {symbol}"
            current = self.position_manager.get_position_count()
            if current >= MAX_CONCURRENT_POSITIONS:
                return False, f"Maximum {MAX_CONCURRENT_POSITIONS} positions reached (current: {current})"
            if self.position_manager.get_available_balance() < 60.0:
                return False, "Insufficient available balance"
            return True, f"Position can be opened ({current}/{MAX_CONCURRENT_POSITIONS} slots used)"
        except Exception as e:
            return False, f"Validation error: {e}"


# Global trading orchestrator instance
global_trading_orchestrator = TradingOrchestrator()
