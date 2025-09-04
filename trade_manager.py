#!/usr/bin/env python3
import re
import time
from datetime import datetime, timedelta
import logging
from termcolor import colored
import os
import asyncio
import uuid
import json

from config import (
    MARGIN_USDT, LEVERAGE, EXCLUDED_SYMBOLS,
    TOP_ANALYSIS_CRYPTO, DEMO_MODE, DEMO_BALANCE, MAX_CONCURRENT_POSITIONS
)
from fetcher import get_top_symbols, get_data_async

# Import the robust risk management system
try:
    from core.risk_manager import RobustRiskManager, PositionRisk, calculate_safe_position_size, calculate_dynamic_stop_loss
    RISK_MANAGER_AVAILABLE = True
    logging.info("✅ Advanced Risk Manager loaded successfully")
    
    # Initialize global risk manager instance
    global_risk_manager = RobustRiskManager()
    
except ImportError as e:
    logging.warning(f"⚠️ Advanced Risk Manager not available: {e}")
    RISK_MANAGER_AVAILABLE = False
    global_risk_manager = None

# Import enhanced terminal display
try:
    from core.terminal_display import display_enhanced_signal, display_portfolio_status
    ENHANCED_DISPLAY_AVAILABLE = True
except ImportError as e:
    logging.warning(f"⚠️ Enhanced Terminal Display not available: {e}")
    ENHANCED_DISPLAY_AVAILABLE = False

# Import position tracking system
try:
    from core.position_tracker import global_position_tracker
    POSITION_TRACKER_AVAILABLE = True
    logging.info("✅ Position Tracker integrated in trade_manager")
except ImportError as e:
    logging.warning(f"⚠️ Position Tracker not available: {e}")
    POSITION_TRACKER_AVAILABLE = False

def is_symbol_excluded(symbol):
    normalized = re.sub(r'[^A-Za-z0-9]', '', symbol).upper()
    return any(exc.upper() in normalized for exc in EXCLUDED_SYMBOLS)

async def get_real_balance(exchange):
    # Modalità Demo: usa balance fittizio senza API
    if DEMO_MODE:
        logging.info(colored(f"🎮 DEMO MODE: Utilizzo balance fittizio di {DEMO_BALANCE} USDT", "magenta"))
        return DEMO_BALANCE
    
    # Modalità Live: usa API Bybit reali
    try:
        logging.info(colored("🔍 Tentativo di recupero balance USDT...", "cyan"))
        balance = await exchange.fetch_balance()
        logging.info(colored(f"📊 Balance response ricevuto: {type(balance)}", "cyan"))
        
        # Debug: mostra le chiavi disponibili nel balance
        if isinstance(balance, dict):
            available_keys = list(balance.keys())
            logging.info(colored(f"🔑 Chiavi disponibili nel balance: {available_keys[:10]}...", "cyan"))
            
            # Cerca USDT in diversi formati
            usdt_balance = None
            for key in ['USDT', 'usdt', 'USDT:USDT', 'USDT/USDT']:
                if key in balance:
                    usdt_data = balance[key]
                    logging.info(colored(f"💰 Trovato {key}: {usdt_data}", "cyan"))
                    if isinstance(usdt_data, dict):
                        usdt_balance = usdt_data.get('free', usdt_data.get('total', 0))
                    else:
                        usdt_balance = usdt_data
                    break
            
            if usdt_balance is None:
                # Fallback: cerca qualsiasi chiave che contenga USDT
                for key, value in balance.items():
                    if 'USDT' in str(key):
                        logging.info(colored(f"🔍 Possibile USDT trovato: {key} = {value}", "cyan"))
                        if isinstance(value, dict):
                            usdt_balance = value.get('free', value.get('total', 0))
                            break
                        
            if usdt_balance is None:
                usdt_balance = 0
                
        else:
            usdt_balance = 0
            
        if usdt_balance == 0:
            logging.warning(colored("⚠️ Il saldo USDT è zero o non trovato.", "yellow"))
        else:
            logging.info(colored(f"✅ USDT Balance trovato: {usdt_balance}", "green"))
            
        return usdt_balance
    except Exception as e:
        error_msg = str(e)
        logging.error(colored(f"❌ Errore nel recupero del saldo: {error_msg}", "red"))
        logging.error(colored(f"🔍 Tipo errore: {type(e).__name__}", "red"))
        
        # Controlla errori comuni
        if "33004" in error_msg or "api key expired" in error_msg.lower():
            logging.error(colored("🔑 Errore: API key scaduta o non valida", "red"))
        elif "10003" in error_msg or "invalid api key" in error_msg.lower():
            logging.error(colored("🔑 Errore: API key non valida", "red"))
        elif "permissions" in error_msg.lower():
            logging.error(colored("🔒 Errore: Permissions insufficienti - serve 'Read' permission", "red"))
            
        return None

async def get_open_positions(exchange):
    try:
        positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
        return len([p for p in positions if float(p.get('contracts', 0)) > 0])
    except Exception as e:
        logging.error(colored(f"❌ Errore nel recupero delle posizioni aperte: {e}", "red"))
        return 0

async def calculate_position_size(exchange, symbol, usdt_balance, min_amount=0, risk_factor=1.0):
    try:
        ticker = await exchange.fetch_ticker(symbol)
        current_price = ticker.get('last')
        if current_price is None or not isinstance(current_price, (int, float)):
            logging.error(colored(f"❌ Prezzo corrente per {symbol} non disponibile", "red"))
            return None
        margin = MARGIN_USDT
        leverage = LEVERAGE
        notional_value = margin * leverage
        position_size = notional_value / current_price
        position_size = float(exchange.amount_to_precision(symbol, position_size))
        logging.info(colored(f"📏 Dimensione posizione per {symbol}: {position_size} contratti (Margine = {margin})", "cyan"))
        if position_size < min_amount:
            logging.warning(colored(f"⚠️ Dimensione posizione {position_size} inferiore al minimo {min_amount} per {symbol}.", "yellow"))
            position_size = min_amount
        return position_size
    except Exception as e:
        logging.error(colored(f"❌ Errore nel calcolo della dimensione per {symbol}: {e}", "red"))
        return None

async def manage_position(exchange, symbol, signal, usdt_balance, min_amounts,
                          lstm_model, lstm_scaler, rf_model, rf_scaler, df, predictions=None):
    """
    Enhanced position management with advanced risk management
    
    MAJOR IMPROVEMENTS:
    - Risk-based position sizing
    - Dynamic stop loss calculation
    - Portfolio risk validation
    - ATR-based risk management
    """
    current_time = time.time()
    side = "Buy" if signal == 1 else "Sell"
    
    # Get current price and market data
    try:
        ticker = await exchange.fetch_ticker(symbol)
        current_price = ticker.get('last')
        if current_price is None:
            logging.error(colored(f"❌ Prezzo corrente per {symbol} non disponibile", "red"))
            return "price_unavailable"
            
    except Exception as e:
        logging.error(colored(f"❌ Errore nel recupero prezzo per {symbol}: {e}", "red"))
        return "price_error"
    
    # Extract market indicators from dataframe for risk calculations
    try:
        if df is not None and len(df) > 0:
            latest_candle = df.iloc[-1]
            atr = latest_candle.get('atr', current_price * 0.02)  # Fallback: 2% of price
            volatility = latest_candle.get('volatility', 0.0)
        else:
            atr = current_price * 0.02  # 2% fallback ATR
            volatility = 0.0
            
    except Exception as e:
        logging.warning(f"⚠️ Could not extract indicators for {symbol}: {e}")
        atr = current_price * 0.02
        volatility = 0.0
    
    # Check basic balance requirements
    if usdt_balance < 50.0:  # Increased minimum balance
        logging.warning(colored(f"{symbol}: Saldo USDT insufficiente ({usdt_balance:.2f} < 50.0).", "yellow"))
        return "insufficient_balance"
    
    # Use advanced risk management if available
    if RISK_MANAGER_AVAILABLE and global_risk_manager:
        try:
            # Calculate risk-based position size
            signal_confidence = predictions.get('confidence', 0.7) if predictions else 0.7
            position_size, calculated_stop_loss = global_risk_manager.calculate_position_size(
                symbol=symbol,
                signal_strength=signal_confidence,
                current_price=current_price,
                atr=atr,
                account_balance=usdt_balance,
                volatility=volatility
            )
            
            if position_size <= 0:
                logging.warning(colored(f"⚠️ Risk manager rejected position for {symbol}: zero size calculated", "yellow"))
                return "risk_rejected"
            
            # Validate position with risk manager
            # TODO: Get existing positions for validation
            existing_positions = []  # Simplified for now
            
            approved, reason = global_risk_manager.validate_new_position(
                symbol=symbol,
                side=side,
                size=position_size,
                current_price=current_price,
                account_balance=usdt_balance,
                existing_positions=existing_positions
            )
            
            if not approved:
                logging.warning(colored(f"⚠️ Risk manager rejected {symbol}: {reason}", "yellow"))
                return "risk_rejected"
            
            # Calculate proper stop loss
            stop_loss_price = global_risk_manager.calculate_stop_loss(
                symbol=symbol,
                side=side,
                entry_price=current_price,
                atr=atr,
                volatility=volatility
            )
            
            logging.info(colored(f"🛡️ Risk Management Applied | {symbol}: Size={position_size:.4f}, Stop Loss={stop_loss_price:.6f}", "green"))
            
        except Exception as e:
            logging.error(f"❌ Risk manager error for {symbol}: {e}")
            # Fallback to basic calculation
            position_size = await calculate_fallback_position_size(symbol, current_price, usdt_balance)
            stop_loss_price = None
            
    else:
        # Fallback: Use original logic but improved
        logging.info(f"🔄 Using fallback position sizing for {symbol}")
        position_size = await calculate_fallback_position_size(symbol, current_price, usdt_balance)
        stop_loss_price = None
    
    # Get current open positions count
    if DEMO_MODE:
        current_open_positions = 0  # Demo: simulate no positions
        logging.info(colored(f"🎮 DEMO | {symbol}: {side} | Balance: {usdt_balance:.2f} USDT | Size: {position_size:.4f}", "magenta"))
    else:
        current_open_positions = await get_open_positions(exchange)
        logging.info(colored(f"💼 LIVE | {symbol}: {side} | Balance: {usdt_balance:.2f} USDT | Positions: {current_open_positions}/{MAX_CONCURRENT_POSITIONS}", "cyan"))
    
    # FIXED: Check position limits using centralized config
    if current_open_positions >= MAX_CONCURRENT_POSITIONS:
        logging.info(colored(f"{symbol}: Max trade limit reached ({current_open_positions}/{MAX_CONCURRENT_POSITIONS})", "yellow"))
        return "max_trades_reached"
    
    # Execute based on mode
    if DEMO_MODE:
        # DEMO MODE: Use position tracker for realistic simulation
        if POSITION_TRACKER_AVAILABLE:
            try:
                # Get current wallet balance from position tracker
                current_wallet = global_position_tracker.session_stats['current_balance']
                
                # Calculate position size as 5% of current wallet
                calculated_position_size = current_wallet * 0.05
                
                # Check if we have enough available balance
                available_balance = global_position_tracker.get_available_balance()
                
                if available_balance < calculated_position_size:
                    logging.warning(colored(f"❌ {symbol}: Insufficient available balance ({available_balance:.2f} < {calculated_position_size:.2f})", "yellow"))
                    return "insufficient_balance"
                
                # FIXED: Check position limits using centralized config
                active_positions = global_position_tracker.get_active_positions_count()
                if active_positions >= MAX_CONCURRENT_POSITIONS:
                    logging.warning(colored(f"❌ {symbol}: Max positions reached ({active_positions}/{MAX_CONCURRENT_POSITIONS})", "yellow"))
                    return "max_trades_reached"
                
                # Extract confidence
                confidence = predictions.get('confidence', 0.7) if predictions else 0.7
                
                # Open position in tracker with TP/SL/Trailing
                position_id = global_position_tracker.open_position(
                    symbol=symbol,
                    side=side,
                    entry_price=current_price,
                    position_size=calculated_position_size,
                    leverage=LEVERAGE,
                    confidence=confidence,
                    atr=atr
                )
                
                # Enhanced display
                risk_pct = (3.0 / LEVERAGE) if LEVERAGE > 0 else 3.0  # Base risk divided by leverage
                
                if ENHANCED_DISPLAY_AVAILABLE:
                    display_enhanced_signal(
                        symbol=symbol,
                        signal=side.upper(),
                        confidence=confidence,
                        price=current_price,
                        stop_loss=stop_loss_price,
                        position_size=calculated_position_size,
                        risk_pct=risk_pct,
                        atr=atr
                    )
                
                logging.info(colored(f"🎮 DEMO POSITION OPENED | {symbol}: {side} | Balance: {current_wallet:.2f} USDT | Size: {calculated_position_size:.2f} USDT", "magenta"))
                
                return position_id
                
            except Exception as tracker_error:
                logging.error(f"Position tracker error: {tracker_error}")
                return f"demo_signal_{side.lower()}"
        else:
            # Fallback to original demo behavior
            risk_pct = (atr / current_price) * 100 if atr > 0 else 2.0
            logging.info(colored(
                f"🎮 DEMO SIGNAL | {symbol}: {side} | Price: {current_price:.6f} | "
                f"Size: {position_size:.4f} | Risk: {risk_pct:.2f}% | ATR: {atr:.6f}",
                "magenta"
            ))
            return f"demo_signal_{side.lower()}"
    
    else:
        # LIVE MODE: Execute with risk management
        try:
            await exchange.set_leverage(LEVERAGE, symbol)
        except Exception as lev_err:
            logging.warning(colored(f"{symbol}: Could not set leverage: {lev_err}", "yellow"))
        
        logging.info(colored(f"🚀 Executing {side} order for {symbol} with advanced risk management", "blue"))
        new_trade = await execute_order_with_risk_management(
            exchange, symbol, side, position_size, current_price, 
            current_time, df, predictions, stop_loss_price
        )
        return new_trade


async def calculate_fallback_position_size(symbol, current_price, usdt_balance):
    """
    Fallback position sizing when risk manager is not available
    More conservative than original
    """
    try:
        # More conservative margin allocation
        conservative_margin = min(MARGIN_USDT, usdt_balance * 0.1)  # Max 10% of balance
        conservative_leverage = min(LEVERAGE, 5)  # Max 5x leverage as fallback
        
        notional_value = conservative_margin * conservative_leverage
        position_size = notional_value / current_price
        
        logging.info(colored(f"📏 Fallback position size for {symbol}: {position_size:.4f} (conservative)", "yellow"))
        return position_size
        
    except Exception as e:
        logging.error(f"❌ Fallback position calculation failed for {symbol}: {e}")
        return 0.0


async def execute_order_with_risk_management(exchange, symbol, side, position_size, price, 
                                           current_time, df, predictions, stop_loss_price):
    """
    Enhanced order execution with stop loss integration
    """
    try:
        # Execute main order
        if side == "Buy":
            order = await exchange.create_market_buy_order(symbol, position_size)
        else:
            order = await exchange.create_market_sell_order(symbol, position_size)
            
        entry_price = order.get('average') or price
        trade_id = order.get("id") or f"{symbol}-{datetime.utcnow().timestamp()}"
        
        # Try to set stop loss if calculated
        stop_loss_order_id = None
        if stop_loss_price and not DEMO_MODE:
            try:
                # Create stop loss order
                stop_side = "sell" if side == "Buy" else "buy"
                stop_order = await exchange.create_order(
                    symbol=symbol,
                    type='stop_market',
                    side=stop_side,
                    amount=position_size,
                    params={'stopPrice': stop_loss_price}
                )
                stop_loss_order_id = stop_order.get('id')
                logging.info(colored(f"🛡️ Stop loss set for {symbol}: {stop_loss_price:.6f}", "green"))
                
            except Exception as sl_error:
                logging.warning(colored(f"⚠️ Could not set stop loss for {symbol}: {sl_error}", "yellow"))
        
        # Create enhanced trade record
        new_trade = {
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "stop_loss": stop_loss_price,
            "stop_loss_order_id": stop_loss_order_id,
            "exit_price": None,
            "trade_type": "Open",
            "closed_pnl": None,
            "result": None,
            "risk_managed": True,
            "trade_time": datetime.utcnow().isoformat(),
            "timestamp": datetime.utcnow().isoformat(),
            "status": "open"
        }
        
        logging.info(colored(f"🎯 Enhanced trade opened: {new_trade}", "green"))
        return new_trade
        
    except Exception as e:
        error_str = str(e)
        if "110007" in error_str or "not enough" in error_str:
            logging.warning(colored(f"⚠️ Insufficient funds for {symbol}: {error_str}", "yellow"))
            return "insufficient_balance"
        else:
            logging.error(colored(f"❌ Order execution failed for {symbol}: {error_str}", "red"))
            return None

async def execute_order(exchange, symbol, side, position_size, price, current_time, df, predictions=None):
    try:
        if side == "Buy":
            order = await exchange.create_market_buy_order(symbol, position_size)
        else:
            order = await exchange.create_market_sell_order(symbol, position_size)
    except Exception as e:
        error_str = str(e)
        if "110007" in error_str or "not enough" in error_str:
            logging.warning(colored(f"⚠️ Errore ordine per {symbol}: {error_str}", "yellow"))
            return "insufficient_balance"
        else:
            logging.error(colored(f"❌ Errore eseguendo ordine {side} per {symbol}: {error_str}", "red"))
            return None
    entry_price = order.get('average') or price
    trade_id = order.get("id") or f"{symbol}-{datetime.utcnow().timestamp()}"
    
    new_trade = {
        "trade_id": trade_id,
        "symbol": symbol,
        "side": side,
        "entry_price": entry_price,
        "exit_price": None,
        "trade_type": "Open",
        "closed_pnl": None,
        "result": None,
        "open_trade_volume": None,
        "closed_trade_volume": None,
        "opening_fee": None,
        "closing_fee": None,
        "funding_fee": None,
        "trade_time": datetime.utcnow().isoformat(),
        "timestamp": datetime.utcnow().isoformat(),
        "status": "open"
    }
    logging.info(colored(f"🔔 Trade aperto: {new_trade}", "green"))
    return new_trade

async def get_total_initial_margin(exchange, symbol):
    try:
        positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
        total_im = 0.0
        for pos in positions:
            if pos.get('symbol') == symbol and float(pos.get('contracts', 0)) > 0:
                im = pos.get('initialMargin') or 30.0
                total_im += float(im)
        return total_im
    except Exception as e:
        logging.error(colored(f"❌ Errore nel recupero del margine iniziale per {symbol}: {e}", "red"))
        return 0.0

async def update_orders_status(exchange):
    await save_orders_tracker()

async def save_orders_tracker():
    logging.info(colored("Salvataggio stato ordini (senza database).", "cyan"))
    try:
        import aiofiles
        async with aiofiles.open("orders_status.json", 'w') as f:
            await f.write(json.dumps([], indent=2))
    except Exception as e:
        logging.error(colored(f"❌ Errore nel salvataggio dello stato degli ordini: {e}", "red"))
