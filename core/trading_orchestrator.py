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
    from core.unified_balance_manager import get_global_balance_manager
    from core.smart_api_manager import global_smart_api_manager
    UNIFIED_MANAGERS_AVAILABLE = True
    logging.debug("🔧 Unified managers integration enabled in TradingOrchestrator")
except ImportError as e:
    UNIFIED_MANAGERS_AVAILABLE = False
    logging.warning(f"⚠️ Unified managers not available: {e}")

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
            self.balance_manager = get_global_balance_manager()
            self.api_manager = global_smart_api_manager
            logging.debug("🔧 TradingOrchestrator: Unified managers initialized (no SL calculator)")

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

            # 7) Create position in tracker (NO stop loss/trailing)
            position_usd_value = levels.margin * config.LEVERAGE  # USD notional value
            
            position_id = self.position_manager.thread_safe_create_position(
                symbol=symbol,
                side=side,
                entry_price=market_data.price,
                position_size=position_usd_value,  # USD value
                leverage=config.LEVERAGE,
                confidence=confidence
            )
            
            logging.info(colored(f"✅ {symbol}: Position opened successfully (no stop loss)", "green"))

            return TradingResult(True, position_id, "", {
                'main': market_result.order_id,
                'note': 'Position opened without stop loss/trailing'
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
        Sincronizza posizioni reali da Bybit e importa nel tracker (NO stop loss/trailing)
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

            # Register synced positions
            for position in newly_opened:
                results[position.symbol] = TradingResult(
                    True,
                    position.position_id,
                    "",
                    {'tracking_type': 'bybit_sync', 'note': 'Position synced without protection'}
                )
                
                symbol_short = position.symbol.replace('/USDT:USDT', '')
                logging.info(colored(f"✅ {symbol_short}: Position synced (no stop loss)", "green"))
            
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
