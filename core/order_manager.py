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
                               position_idx: int = 0) -> OrderExecutionResult:
        """
        Imposta SL/TP su Bybit (endpoint: /v5/position/trading-stop)
        """
        try:
            # Converte il simbolo nel formato Bybit (BTC/USDT:USDT → BTCUSDT)
            bybit_symbol = symbol.replace('/USDT:USDT', 'USDT').replace('/', '')

            sl_text = f"${stop_loss:.6f}" if stop_loss else "None"
            tp_text = f"${take_profit:.6f}" if take_profit else "None"

            logging.debug(colored(
                f"🛡️ SETTING TRADING STOP: {bybit_symbol} | SL: {sl_text} | TP: {tp_text}",
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

            result = await exchange.private_post_v5_position_trading_stop(params)

            ret_code = result.get('retCode', -1)
            ret_msg = result.get('retMsg', 'Unknown response')

            # 🔧 PRIMO: Controlla errori "non preoccupanti" prima di tutto
            if (ret_code == 34040 and "not modified" in ret_msg.lower()) or "api error 0: ok" in ret_msg.lower():
                logging.debug(colored(f"📝 {bybit_symbol}: Stop loss already set correctly", "cyan"))
                return OrderExecutionResult(True, f"trading_stop_{bybit_symbol}_existing", None)
            elif ret_code == 0:
                logging.info(colored(
                    f"✅ TRADING STOP SUCCESS: {bybit_symbol} | Response: {ret_msg}",
                    "green", attrs=['bold']
                ))
                return OrderExecutionResult(True, f"trading_stop_{bybit_symbol}", None)
            else:
                error_msg = f"Bybit API error {ret_code}: {ret_msg}"
                logging.error(colored(f"❌ {error_msg}", "red"))
                return OrderExecutionResult(False, None, error_msg)

        except Exception as e:
            # 🔧 PRIMO: Controlla errori "non preoccupanti" PRIMA di loggare
            error_str = str(e).lower()
            # Matching più ampio per catturare tutte le varianti
            non_critical_patterns = [
                "34040", "not modified", "api error 0", "retcode\":0", 
                "bybit api error 0", "ok", "\"retcode\": 0"
            ]
            
            is_non_critical = any(pattern in error_str for pattern in non_critical_patterns)
            
            if is_non_critical:
                # SILENCED: Non loggare nemmeno come debug per pulire output
                return OrderExecutionResult(True, f"trading_stop_{bybit_symbol}_existing", None)
            else:
                # Solo errori veri vengono loggati come ERROR
                error_msg = f"Trading stop API call failed: {str(e)}"
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
