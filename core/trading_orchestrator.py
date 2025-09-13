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
from typing import Dict, List, Tuple
from termcolor import colored

import config

# Import clean modules
from core.order_manager import global_order_manager
from core.risk_calculator import global_risk_calculator, MarketData
from core.smart_position_manager import global_smart_position_manager, Position
from core.trailing_stop_manager import TrailingStopManager
from core.price_precision_handler import global_price_precision_handler


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
        self.position_manager = global_smart_position_manager
        self.smart_position_manager = global_smart_position_manager  # alias
        self.trailing_manager = TrailingStopManager(self.order_manager, self.position_manager)

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

            # 5) Market order
            market_result = await self.order_manager.place_market_order(exchange, symbol, side, levels.position_size)
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
                    # Controlla se è un errore "non preoccupante" prima del fallback
                    error_msg = str(sl_result.error or "").lower()
                    if "api error 0: ok" in error_msg or "not modified" in error_msg:
                        logging.info(colored(f"📝 {symbol}: Trailing stop set correctly", "cyan"))
                        sl_order_id = sl_result.order_id
                    else:
                        # Vero fallimento → Fallback al stop fisso
                        sl_result = await self.order_manager.set_trading_stop(exchange, symbol, sl_price, None)
                        sl_order_id = sl_result.order_id if sl_result.success else None
                        logging.info(colored(f"📝 {symbol}: Using fixed SL protection", "cyan"))
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

            # 7) Registra posizione con trailing (già inizializzato)
            position_id = self.position_manager.create_trailing_position(
                symbol=symbol,
                side=side,
                entry_price=market_data.price,
                position_size=levels.position_size * market_data.price,  # USD
                atr=market_data.atr,
                catastrophic_sl_id=sl_order_id,
                leverage=config.LEVERAGE,
                confidence=confidence
            )
            
            # Salva trailing_data nella posizione creata
            if position_id:
                position = next((p for p in self.position_manager.get_active_positions() 
                               if p.position_id == position_id), None)
                if position:
                    position.trailing_data = trailing_data
                    if trailing_data.trailing_attivo:
                        position.trailing_attivo = True
                        position.best_price = current_price
                        position.sl_corrente = trailing_data.sl_corrente

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
            active_positions = [p for p in real_positions if float(p.get('contracts', 0) or 0) > 0]
            if not active_positions:
                logging.info(colored("🆕 No existing positions on Bybit - starting fresh", "green"))
                return {}

            # 2) Importa nello SmartPositionManager
            newly_opened, _ = await self.smart_position_manager.sync_with_bybit(exchange)
            
            if newly_opened:
                logging.info(colored(f"🛡️ PROTECTING {len(newly_opened)} positions...", "yellow", attrs=['bold']))

            # 3) Applica protezione per ogni posizione con log ridotto
            protected_count = 0
            trailing_count = 0
            
            for i, position in enumerate(newly_opened, 1):
                results[position.symbol] = TradingResult(
                    True,
                    position.position_id,
                    "",
                    {'tracking_type': 'smart_sync', 'note': 'Position synced via SmartPositionManager'}
                )

                try:
                    # 🔧 CLEANED: Log più conciso per protezione posizioni
                    symbol_short = position.symbol.replace('/USDT:USDT', '')
                    logging.debug(f"🛡️ Protecting {symbol_short} ({i}/{len(newly_opened)})")
                    
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
                        sl_res = await self.order_manager.set_trading_stop(exchange, position.symbol, sl_price, None)
                        if sl_res.success:
                            protected_count += 1
                            logging.debug(f"✅ {symbol_short}: Stop loss protected")
                        else:
                            # Gestisci errori "non preoccupanti" in modo silenzioso
                            error_msg = str(sl_res.error).lower()
                            if "not modified" in error_msg or "api error 0: ok" in error_msg:
                                protected_count += 1  # Conta come protetto
                                logging.debug(f"📝 {symbol_short}: Stop loss already set correctly")
                            else:
                                logging.warning(colored(f"⚠️ SL not applied to {symbol_short}: {sl_res.error}", "yellow"))

                    # Conta trailing se attivato
                    if trailing_data.trailing_attivo:
                        trailing_count += 1

                except Exception as e:
                    logging.error(f"❌ Error protecting {position.symbol}: {e}")

            # 🔧 CLEANED: Summary finale pulito
            logging.info(colored(f"✅ PROTECTION COMPLETE: {protected_count}/{len(newly_opened)} positions protected", "green"))
            if trailing_count > 0:
                logging.info(colored(f"🚀 TRAILING ACTIVE: {trailing_count} positions with trailing stops", "cyan"))
            
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

            # Solo aggiornamento prezzi e PnL per display (non trailing logic)
            for position in trailing_positions:
                try:
                    ticker = await exchange.fetch_ticker(position.symbol)
                    current_price = ticker.get('last', 0)
                    
                    if current_price > 0:
                        position.current_price = current_price
                        
                        # Solo PnL update (no trailing logic - delegato al TrailingMonitor)
                        if position.side == 'buy':
                            pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                        else:
                            pnl_pct = ((position.entry_price - current_price) / position.entry_price) * 100
                        
                        position.unrealized_pnl_pct = pnl_pct
                        position.unrealized_pnl_usd = (pnl_pct / 100) * position.position_size
                        
                        # Inizializza trailing_data se mancante (solo init, no logic)
                        if not hasattr(position, 'trailing_data') or position.trailing_data is None:
                            atr_value = getattr(position, "atr_value", current_price * 0.02)
                            position.trailing_data = self.trailing_manager.initialize_trailing_data(
                                position.symbol, position.side, position.entry_price, atr_value
                            )
                            logging.debug(f"🔧 Initialized trailing_data for {position.symbol}")
                            
                except Exception as e:
                    logging.debug(f"Error updating price for {position.symbol}: {e}")

            # Salva posizioni aggiornate
            self.position_manager.save_positions()

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
            if self.position_manager.get_available_balance() < 20.0:
                return False, "Insufficient available balance"
            return True, f"Position can be opened ({current}/{MAX_CONCURRENT_POSITIONS} slots used)"
        except Exception as e:
            return False, f"Validation error: {e}"


# Global trading orchestrator instance
global_trading_orchestrator = TradingOrchestrator()
