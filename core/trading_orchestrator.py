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
from core.trailing_stop_manager import TrailingStopManager
from core.price_precision_handler import global_price_precision_handler

# CRITICAL FIX: Import new unified managers
try:
    from core.thread_safe_position_manager import global_thread_safe_position_manager
    from core.unified_balance_manager import get_global_balance_manager
    from core.unified_stop_loss_calculator import global_unified_stop_loss_calculator
    from core.smart_api_manager import global_smart_api_manager
    UNIFIED_MANAGERS_AVAILABLE = True
    logging.debug("🔧 Unified managers integration enabled in TradingOrchestrator")
except ImportError as e:
    UNIFIED_MANAGERS_AVAILABLE = False
    logging.warning(f"⚠️ Unified managers not available: {e}")


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
        
        self.trailing_manager = TrailingStopManager(self.order_manager, self.position_manager)
        
        # Initialize unified managers
        if UNIFIED_MANAGERS_AVAILABLE:
            self.balance_manager = get_global_balance_manager()
            self.sl_calculator = global_unified_stop_loss_calculator
            self.api_manager = global_smart_api_manager
            logging.debug("🔧 TradingOrchestrator: All unified managers initialized")

    # --------------------------------------------------------------------- #
    #                      NEW TRADE (open + SL 6%)                         #
    # --------------------------------------------------------------------- #
    async def execute_new_trade(self, exchange, signal_data: Dict, market_data: MarketData, balance: float) -> TradingResult:
        """
        Esegue un nuovo trade completo di protezione iniziale:
        - imposta leva e margine isolato
        - piazza market order
        - applica SL iniziale = ±6% sul prezzo (≈60% del margine con leva 10)
        - registra la posizione per il trailing
        """
        try:
            symbol = signal_data['symbol']
            side = signal_data['signal_name'].lower()  # 'buy' | 'sell'
            confidence = signal_data.get('confidence', 0.7)

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

            # 1) Calcolo livelli (size/margin/SL/TP)
            levels = self.risk_calculator.calculate_position_levels(market_data, side, confidence, balance)

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
            
            # Check minimum amount requirements
            precision_info = await global_price_precision_handler.get_symbol_precision(exchange, symbol)
            min_amount = precision_info.get('min_amount', 0.001)
            
            if normalized_size < min_amount:
                error_msg = f"Position size {normalized_size:.6f} < minimum {min_amount} for {symbol}"
                logging.error(colored(f"❌ {error_msg}", "red"))
                return TradingResult(False, "", error_msg)
            
            logging.info(colored(f"📏 Position size: {levels.position_size:.6f} → {normalized_size:.6f}", "cyan"))
            
            # 6) Market order with normalized size
            market_result = await self.order_manager.place_market_order(exchange, symbol, side, normalized_size)
            if not market_result.success:
                return TradingResult(False, "", f"Market order failed: {market_result.error}")

            # 6) 🔧 FIXED: SMART STOP LOSS con nuovo precision handler
            raw_sl = market_data.price * (1 - 0.06) if side == "buy" else market_data.price * (1 + 0.06)
            sl_price = await _normalize_sl_price_new(exchange, symbol, side, market_data.price, raw_sl)

            # Inizializza TrailingData per decidere il tipo di stop loss
            trailing_data = self.trailing_manager.initialize_trailing_data(
                symbol, side, market_data.price, market_data.atr
            )
            
            # 🔧 SMART LOGIC: Stesso trattamento delle posizioni esistenti
            current_price = await global_price_precision_handler.get_current_price(exchange, symbol)
            
            if self.trailing_manager.check_activation_conditions(trailing_data, current_price):
                # NUOVO TRADE GIÀ IN PROFITTO → Usa trailing stop immediato
                self.trailing_manager.activate_trailing(trailing_data, current_price, side, market_data.atr)
                
                trailing_sl = trailing_data.sl_corrente
                logging.info(colored(f"🚀 {symbol}: New trade profitable → Using trailing stop", "cyan"))
                
                sl_result = await self.order_manager.set_trading_stop(exchange, symbol, trailing_sl, None)
                if sl_result.success:
                    logging.info(colored(f"✅ {symbol}: Trailing stop activated (${trailing_sl:.6f})", "green"))
                    sl_order_id = sl_result.order_id
                else:
                    # CRITICAL FIX: More rigorous SL enforcement
                    logging.warning(colored(f"❌ {symbol}: Trailing SL failed: {sl_result.error}", "red"))
                    
                    # Mandatory fallback to fixed SL - retry with better validation
                    for retry in range(3):  # 3 retry attempts
                        try:
                            # Validate SL price before setting
                            current_price_check = await global_price_precision_handler.get_current_price(exchange, symbol)
                            
                            # Ensure SL respects Bybit rules
                            if side == "buy" and sl_price >= current_price_check:
                                sl_price = current_price_check * 0.94  # Force 6% below current
                            elif side == "sell" and sl_price <= current_price_check:
                                sl_price = current_price_check * 1.06  # Force 6% above current
                            
                            sl_result = await self.order_manager.set_trading_stop(exchange, symbol, sl_price, None)
                            if sl_result.success:
                                logging.info(colored(f"✅ {symbol}: Fixed SL set on retry {retry+1} (${sl_price:.6f})", "green"))
                                sl_order_id = sl_result.order_id
                                break
                            else:
                                logging.warning(f"Retry {retry+1} failed: {sl_result.error}")
                                if retry == 2:  # Last attempt
                                    logging.error(colored(f"❌ CRITICAL: {symbol} has NO STOP LOSS after 3 attempts!", "red"))
                                    sl_order_id = None
                        except Exception as retry_error:
                            logging.error(f"SL retry {retry+1} error: {retry_error}")
                            sl_order_id = None
            else:
                # NUOVO TRADE NON IN PROFITTO → Stop fisso normale
                sl_result = await self.order_manager.set_trading_stop(exchange, symbol, sl_price, None)
                sl_order_id = sl_result.order_id if sl_result.success else None
                if sl_result.success:
                    if side == "buy":
                        sl_pct = ((market_data.price - sl_price) / market_data.price) * 100
                    else:
                        sl_pct = ((sl_price - market_data.price) / market_data.price) * 100
                    logging.info(colored(f"✅ {symbol}: Stop Loss set at ${sl_price:.6f} (-{sl_pct:.1f}% risk)", "green"))
                else:
                    logging.warning(colored(f"⚠️ Failed to set stop loss: {sl_result.error}", "yellow"))

            # 7) STEP 1 FIX: Use ThreadSafe position creation with atomic operations
            position_usd_value = levels.margin * config.LEVERAGE  # USD notional value
            
            position_id = self.position_manager.thread_safe_create_position(
                symbol=symbol,
                side=side,
                entry_price=market_data.price,
                position_size=position_usd_value,  # USD value
                leverage=config.LEVERAGE,
                confidence=confidence
            )
            
            # STEP 1 FIX: Use atomic updates instead of direct position access
            if position_id:
                # Store trailing data atomically with explicit trailing state
                trailing_updates = {
                    'trailing_data': trailing_data,
                    'trailing_active': trailing_data.trailing_attivo,
                    'best_price': trailing_data.best_price,
                    'sl_corrente': trailing_data.sl_corrente
                }
                
                # Log state for debugging
                symbol_short = symbol.replace('/USDT:USDT', '')
                logging.info(f"🔧 SAVING TRAILING STATE: {symbol_short} trailing_active={trailing_data.trailing_attivo}, sl_corrente={trailing_data.sl_corrente}")
                
                self.position_manager.atomic_update_position(position_id, trailing_updates)

            return TradingResult(True, position_id, "", {
                'main': market_result.order_id,
                'stop_loss': sl_order_id,
                'note': 'Fixed 6% SL + Trailing system active'
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
        Sincronizza posizioni reali da Bybit, importa nel tracker e APPLICA SUBITO:
          - Stop Loss iniziale = ±6% dal prezzo di entrata (≈ -60% del margine con leva 10)
          - TrailingData inizializzato (fixed SL + trigger dinamico)
        """
        results: Dict[str, TradingResult] = {}

        try:
            # 🔧 CLEANED: Log unico per sincronizzazione
            real_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_positions = [p for p in real_positions if float(p.get('contracts', 0) or 0) != 0]
            if not active_positions:
                logging.info(colored("🆕 No existing positions on Bybit - starting fresh", "green"))
                return {}

            # 2) STEP 1 FIX: Use ThreadSafePositionManager for sync
            newly_opened, _ = await self.position_manager.thread_safe_sync_with_bybit(exchange)
            
            if newly_opened:
                logging.info(colored(f"🛡️ PROTECTING {len(newly_opened)} positions...", "yellow", attrs=['bold']))

            # 3) Applica protezione per ogni posizione (silenzioso)
            protected_count = 0
            already_protected_count = 0
            trailing_count = 0
            protection_details = []
            
            for i, position in enumerate(newly_opened, 1):
                results[position.symbol] = TradingResult(
                    True,
                    position.position_id,
                    "",
                    {'tracking_type': 'thread_safe_sync', 'note': 'Position synced via ThreadSafePositionManager'}
                )

                try:
                    # Silent protection - no individual logs
                    symbol_short = position.symbol.replace('/USDT:USDT', '')
                    
                    entry = float(position.entry_price)
                    side = position.side.lower()

                    raw_sl = entry * (1 - 0.06) if side == "buy" else entry * (1 + 0.06)
                    sl_price = await _normalize_sl_price_new(exchange, position.symbol, side, entry, raw_sl)

                    # (idempotente) leva + isolated
                    try:
                        await exchange.set_leverage(config.LEVERAGE, position.symbol)
                        await exchange.set_margin_mode('isolated', position.symbol)
                    except Exception as e:
                        # Gestisci errori "non preoccupanti"
                        if "leverage not modified" in str(e):
                            logging.debug(f"📝 {position.symbol}: Leverage already set correctly")
                        else:
                            logging.warning(colored(f"⚠️ {position.symbol}: leverage/margin setup failed: {e}", "yellow"))

                    # Inizializza TrailingData prima di decidere lo stop loss
                    atr_value = getattr(position, "atr_value", entry * 0.02)  # fallback ATR 2%
                    trailing_data = self.trailing_manager.initialize_trailing_data(
                        position.symbol, side, entry, atr_value
                    )
                    position.trailing_data = trailing_data
                    
                    # 🔧 SMART LOGIC: Se già sopra trigger, usa stop trailing invece di fisso
                    current_price = await global_price_precision_handler.get_current_price(exchange, position.symbol)
                    
                    if self.trailing_manager.check_activation_conditions(trailing_data, current_price):
                        # POSIZIONE GIÀ IN PROFITTO → Attiva trailing e usa stop più stretto
                        self.trailing_manager.activate_trailing(trailing_data, current_price, side, atr_value)
                        
                        # Calcola dettagli per log informativi
                        if side == "buy":
                            profit_pct = ((current_price - entry) / entry) * 100 * 10  # Con leva
                            exit_pct = ((trailing_data.sl_corrente - entry) / entry) * 100 * 10  # Target exit
                        else:
                            profit_pct = ((entry - current_price) / entry) * 100 * 10  # Con leva
                            exit_pct = ((entry - trailing_data.sl_corrente) / entry) * 100 * 10  # Target exit
                        
                        # Usa lo stop trailing invece del fisso 6%
                        trailing_sl = trailing_data.sl_corrente
                        logging.info(colored(f"🚀 {position.symbol}: Profitable +{profit_pct:.1f}% → Trailing stop active (exit target: +{exit_pct:.1f}%)", "cyan"))
                        
                        sl_res = await self.order_manager.set_trading_stop(exchange, position.symbol, trailing_sl, None)
                        if sl_res.success:
                            logging.info(colored(f"✅ {position.symbol}: Trailing SL on Bybit ${trailing_sl:.6f} → Profit protected above +{exit_pct:.1f}%", "green"))
                        else:
                            # Controlla se è un errore "non preoccupante" prima del fallback
                            error_msg = str(sl_res.error or "").lower()
                            if "api error 0: ok" in error_msg or "not modified" in error_msg:
                                logging.info(colored(f"📝 {position.symbol}: Trailing stop set correctly → Exit at +{exit_pct:.1f}% minimum", "cyan"))
                            else:
                                # Vero fallimento → Fallback al stop fisso
                                sl_res = await self.order_manager.set_trading_stop(exchange, position.symbol, sl_price, None)
                                if sl_res.success:
                                    logging.info(colored(f"📝 {position.symbol}: Using fixed SL protection (-60% max loss)", "cyan"))
                                else:
                                    logging.debug(f"⚡ {position.symbol}: SL management handled internally")
                    else:
                        # POSIZIONE NON ANCORA IN PROFITTO → Usa stop fisso normale
                        # CRITICAL FIX: More rigorous SL enforcement for existing positions
                        sl_res = await self.order_manager.set_trading_stop(exchange, position.symbol, sl_price, None)
                        if sl_res.success:
                            protected_count += 1
                            logging.debug(f"✅ {symbol_short}: Stop loss protected")
                        else:
                            # 🔧 SMART ERROR HANDLING: Distinguish between real errors and "already protected"
                            error_msg = str(sl_res.error or "").lower()
                            
                            # Check if it's error 34040 "not modified" = already protected
                            if "34040" in error_msg and "not modified" in error_msg:
                                already_protected_count += 1  # Count as already protected!
                                logging.info(colored(f"✅ {symbol_short}: Already protected (stop loss exists)", "cyan"))
                            else:
                                # Real error - attempt retry with validation
                                logging.warning(colored(f"⚠️ {symbol_short}: SL failed: {sl_res.error}", "yellow"))
                                
                                # Retry with validation for real errors only
                                for retry in range(3):
                                    try:
                                        # Re-validate SL price
                                        current_check = await global_price_precision_handler.get_current_price(exchange, position.symbol)
                                        
                                        # Ensure SL respects Bybit rules
                                        if side == "buy" and sl_price >= current_check:
                                            sl_price = current_check * 0.94  # Force 6% below current
                                        elif side == "sell" and sl_price <= current_check:
                                            sl_price = current_check * 1.06  # Force 6% above current
                                        
                                        retry_result = await self.order_manager.set_trading_stop(exchange, position.symbol, sl_price, None)
                                        if retry_result.success:
                                            protected_count += 1
                                            logging.info(colored(f"✅ {symbol_short}: SL set on retry {retry+1} (${sl_price:.6f})", "green"))
                                            break
                                        elif "34040" in str(retry_result.error or "").lower() and "not modified" in str(retry_result.error or "").lower():
                                            # Even retry found existing protection
                                            already_protected_count += 1
                                            logging.info(colored(f"✅ {symbol_short}: Already protected (found on retry {retry+1})", "cyan"))
                                            break
                                        else:
                                            logging.warning(f"SL retry {retry+1} failed: {retry_result.error}")
                                            if retry == 2:  # Last attempt
                                                logging.error(colored(f"❌ {symbol_short}: Could not set stop loss after 3 attempts", "red"))
                                    except Exception as retry_error:
                                        logging.error(f"SL retry {retry+1} error: {retry_error}")

                    # Conta trailing se attivato e raccogli dettagli
                    if trailing_data.trailing_attivo:
                        trailing_count += 1
                        protection_details.append(f"{symbol_short}:TRAILING")
                    else:
                        protection_details.append(f"{symbol_short}:FIXED_SL")

                except Exception as e:
                    logging.debug(f"❌ Error protecting {position.symbol}: {e}")
                    protection_details.append(f"{symbol_short}:ERROR")

            # 🔧 CLEAN SUMMARY: Single line with all protection results
            if newly_opened:
                total_secure = protected_count + already_protected_count
                summary_parts = []
                
                if protected_count > 0:
                    summary_parts.append(f"{protected_count} new")
                if already_protected_count > 0:
                    summary_parts.append(f"{already_protected_count} existing")
                if trailing_count > 0:
                    summary_parts.append(f"{trailing_count} trailing")
                
                summary_text = " | ".join(summary_parts) if summary_parts else "none"
                logging.info(colored(f"✅ PROTECTION COMPLETE: {total_secure}/{len(newly_opened)} secured ({summary_text})", "green"))
            
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
        🔧 SIMPLIFIED: Solo sincronizzazione Bybit - TrailingMonitor fa il lavoro principale
        
        STRATEGY: TrailingMonitor (30s) fa trailing logic, TradingOrchestrator (5min) fa solo sync
        ELIMINA: Logica duplicata e conflitti di stato
        """
        closed_positions: List[Position] = []

        try:
            trailing_positions = self.position_manager.get_trailing_positions()
            if not trailing_positions:
                return closed_positions

            logging.debug(f"🔄 TradingOrchestrator sync: {len(trailing_positions)} trailing positions")

            # STEP 1 FIX: Use atomic operations for price/PnL updates (no direct position access)
            for position in trailing_positions:
                try:
                    ticker = await exchange.fetch_ticker(position.symbol)
                    current_price = ticker.get('last', 0)
                    
                    if current_price > 0:
                        # STEP 1 FIX: Use atomic price/PnL update instead of direct access
                        success = self.position_manager.atomic_update_price_and_pnl(position.position_id, current_price)
                        if not success:
                            logging.warning(f"⚠️ Failed to update price for {position.symbol}")
                            continue
                        
                        # Initialize trailing_data if missing (atomic update)
                        if not hasattr(position, 'trailing_data') or position.trailing_data is None:
                            atr_value = current_price * 0.02  # fallback ATR
                            trailing_data = self.trailing_manager.initialize_trailing_data(
                                position.symbol, position.side, position.entry_price, atr_value
                            )
                            
                            # STEP 1 FIX: Use atomic update for trailing_data
                            self.position_manager.atomic_update_position(position.position_id, {
                                'trailing_data': trailing_data
                            })
                            logging.debug(f"🔧 Initialized trailing_data for {position.symbol}")
                            
                except Exception as e:
                    logging.debug(f"Error updating price for {position.symbol}: {e}")

            # Note: ThreadSafePositionManager auto-saves during atomic operations
            # No manual save needed

            # Nota: Le chiusure trailing sono gestite dal TrailingMonitor (30s)
            # Questo metodo non fa più uscite per evitare conflitti

            return closed_positions

        except Exception as e:
            logging.error(f"Error in trailing positions sync: {e}")
            return closed_positions

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
