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
    Gestione ordini Bybit semplificata
    """

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
        
        CRITICAL FIX: Auto-detect position_idx if not provided:
        - position_idx=1 for LONG (Buy)
        - position_idx=2 for SHORT (Sell)
        """
        try:
            # Converte il simbolo nel formato Bybit (BTC/USDT:USDT → BTCUSDT)
            bybit_symbol = symbol.replace('/USDT:USDT', 'USDT').replace('/', '')

            # FIX: Bybit One-Way Mode requires position_idx=0 always
            # In Hedge Mode would use: 1=LONG, 2=SHORT
            # Most accounts use One-Way Mode, so default to 0
            if position_idx is None:
                position_idx = 0  # One-Way Mode (default for most accounts)

            sl_text = f"${stop_loss:.6f}" if stop_loss else "None"
            tp_text = f"${take_profit:.6f}" if take_profit else "None"
            idx_text = {0: "Both", 1: "LONG", 2: "SHORT"}.get(position_idx, str(position_idx))

            logging.debug(colored(
                f"🛡️ SETTING TRADING STOP: {bybit_symbol} ({idx_text}) | SL: {sl_text} | TP: {tp_text}",
                "yellow", attrs=['bold']
            ))

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

            # Debug log parametri API (ridotto)
            logging.debug(f"🔧 API params: {params}")
            
            result = await exchange.private_post_v5_position_trading_stop(params)
            
            # Debug log risposta (ridotto)  
            logging.debug(f"🔧 Bybit response: {result}")

            ret_code = result.get('retCode', -1)
            ret_msg = result.get('retMsg', 'Unknown response')

            # FIXED: Proper handling of Bybit API responses
            # retCode 0 = SUCCESS, retCode 34040 = already set correctly
            if ret_code == 0 or (isinstance(ret_code, str) and ret_code == "0"):
                # SUCCESS: Stop loss was set successfully
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
                logging.debug(colored(f"📝 {bybit_symbol}: Stop loss already set correctly ({ret_msg})", "cyan"))
                return OrderExecutionResult(True, f"trading_stop_{bybit_symbol}_existing", None)
            else:
                # ACTUAL ERROR: Only log as critical if it's a real error
                if ret_code != 0:
                    error_msg = f"Stop loss setting failed - Bybit error {ret_code}: {ret_msg}"
                    logging.warning(colored(f"⚠️ {error_msg}", "yellow"))
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
