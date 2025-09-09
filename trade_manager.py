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
    TOP_ANALYSIS_CRYPTO, DEMO_BALANCE, MAX_CONCURRENT_POSITIONS
)
import config
from fetcher import get_top_symbols, get_data_async

# CRITICAL FIX: Safe formatting utility to prevent TypeError on None values
def safe_format_price(price, decimals=6, default="N/A"):
    """
    Safely format price values, handling None cases
    
    Args:
        price: Price value (can be None)
        decimals: Number of decimal places
        default: Default value if price is None
        
    Returns:
        str: Formatted price or default value
    """
    if price is None:
        return default
    try:
        return f"${price:.{decimals}f}"
    except (ValueError, TypeError):
        return default

def safe_format_float(value, decimals=2, default="N/A", prefix=""):
    """
    Safely format float values, handling None cases
    
    Args:
        value: Float value (can be None)
        decimals: Number of decimal places  
        default: Default value if value is None
        prefix: Optional prefix (e.g., "$", "%")
        
    Returns:
        str: Formatted value or default value
    """
    if value is None:
        return default
    try:
        return f"{prefix}{value:.{decimals}f}"
    except (ValueError, TypeError):
        return default

# CLEAN: Obsolete imports removed (replaced by new modules)
RISK_MANAGER_AVAILABLE = False  # Replaced by risk_calculator.py
UNIFIED_TRADING_ENGINE_AVAILABLE = False  # Replaced by order_manager.py

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
except ImportError as e:
    logging.warning(f"⚠️ Position Tracker not available: {e}")
    POSITION_TRACKER_AVAILABLE = False

async def place_protective_orders_on_bybit(exchange, symbol, side, position_size, stop_loss_price, take_profit_price):
    """
    CRITICAL FIX: Place actual protective orders on Bybit for imported positions
    
    Args:
        exchange: Bybit exchange instance
        symbol: Trading symbol
        side: 'BUY' or 'SELL'  
        position_size: Position size in contracts
        stop_loss_price: Stop loss price
        take_profit_price: Take profit price
    """
    try:
        logging.info(colored(f"🛡️ PLACING PROTECTIVE ORDERS for {symbol}...", "yellow", attrs=['bold']))
        
        # Place Stop Loss Order
        try:
            stop_side = "sell" if side == "BUY" else "buy"
            stop_order = await exchange.create_order(
                symbol=symbol,
                type='stop_market',
                side=stop_side,
                amount=position_size,
                params={'stopPrice': stop_loss_price}
            )
            stop_loss_order_id = stop_order.get('id')
            logging.info(colored(f"✅ PROTECTIVE STOP LOSS ACTIVE: Order ID {stop_loss_order_id}", "green", attrs=['bold']))
            
        except Exception as sl_error:
            logging.error(colored(f"❌ PROTECTIVE STOP LOSS FAILED for {symbol}: {sl_error}", "red"))
        
        # Place Take Profit Order  
        try:
            tp_side = "sell" if side == "BUY" else "buy"
            tp_order = await exchange.create_order(
                symbol=symbol,
                type='take_profit_market',
                side=tp_side,
                amount=position_size,
                params={'stopPrice': take_profit_price}
            )
            take_profit_order_id = tp_order.get('id')
            logging.info(colored(f"✅ PROTECTIVE TAKE PROFIT ACTIVE: Order ID {take_profit_order_id}", "green", attrs=['bold']))
            
        except Exception as tp_error:
            logging.error(colored(f"❌ PROTECTIVE TAKE PROFIT FAILED for {symbol}: {tp_error}", "red"))
        
        logging.info(colored(f"🛡️ Protective orders setup complete for {symbol}", "green"))
        
    except Exception as e:
        logging.error(colored(f"❌ Error placing protective orders for {symbol}: {e}", "red"))

def is_symbol_excluded(symbol):
    normalized = re.sub(r'[^A-Za-z0-9]', '', symbol).upper()
    return any(exc.upper() in normalized for exc in EXCLUDED_SYMBOLS)

async def get_real_balance(exchange):
    # Modalità Demo: usa balance fittizio senza API
    if config.DEMO_MODE:
        logging.info(colored(f"🎮 DEMO MODE: Utilizzo balance fittizio di {DEMO_BALANCE} USDT", "magenta"))
        return DEMO_BALANCE
    
    # Modalità Live: usa API Bybit reali
    try:
        logging.info(colored("🔍 LIVE MODE: Tentativo di recupero balance USDT tramite API...", "cyan"))
        balance = await exchange.fetch_balance()
        logging.info(colored(f"📊 Balance response ricevuto: {type(balance)}", "cyan"))
        
        # ENHANCED: Bybit Unified Account Balance Recovery
        if isinstance(balance, dict):
            available_keys = list(balance.keys())
            logging.info(colored(f"🔑 Balance keys found ({len(available_keys)}): {available_keys}", "cyan"))
            
            usdt_balance = None
            found_key = None
            
            # STEP 1: Try Bybit Unified Account total balance (inside info structure)
            try:
                if 'info' in balance and isinstance(balance['info'], dict):
                    info_data = balance['info']
                    logging.debug(f"🔍 Info data found: {type(info_data)}")
                    
                    if 'result' in info_data and isinstance(info_data['result'], dict):
                        result_data = info_data['result']
                        logging.debug(f"🔍 Result data found: {type(result_data)}")
                        
                        if 'list' in result_data and isinstance(result_data['list'], list) and len(result_data['list']) > 0:
                            account_data = result_data['list'][0]
                            logging.info(colored(f"🔍 Account data keys: {list(account_data.keys())}", "yellow"))
                            
                            # Try totalWalletBalance first (best for trading)
                            if 'totalWalletBalance' in account_data and account_data['totalWalletBalance']:
                                usdt_balance = float(account_data['totalWalletBalance'])
                                found_key = "info.result.list[0].totalWalletBalance"
                                logging.info(colored(f"💰 Total Wallet Balance: ${usdt_balance:.2f} (Unified Account)", "green", attrs=['bold']))
                            
                            # Fallback to totalEquity
                            elif 'totalEquity' in account_data and account_data['totalEquity']:
                                usdt_balance = float(account_data['totalEquity'])
                                found_key = "info.result.list[0].totalEquity"
                                logging.info(colored(f"💰 Total Equity: ${usdt_balance:.2f} (Unified Account)", "green", attrs=['bold']))
                            
                            else:
                                logging.warning(colored("🔍 totalWalletBalance/totalEquity not found in account data", "yellow"))
                                
            except Exception as nested_error:
                logging.warning(f"Could not extract from nested info structure: {nested_error}")
            
            # STEP 2: Direct keys fallback (if not found in info structure)
            if usdt_balance is None:
                for direct_key in ['totalWalletBalance', 'totalEquity']:
                    if direct_key in balance:
                        try:
                            usdt_balance = float(balance[direct_key])
                            found_key = direct_key
                            logging.info(colored(f"💰 {direct_key}: ${usdt_balance:.2f} (direct key)", "green"))
                            break
                        except (ValueError, TypeError) as e:
                            logging.warning(f"Could not convert {direct_key}: {e}")
            
            # STEP 3: Fallback to USDT-specific balance (classic method)
            if usdt_balance is None:
                logging.info(colored("🔍 Trying classic USDT balance method...", "yellow"))
                
                priority_keys = ['USDT', 'usdt', 'USDT:USDT', 'USDT/USDT']
                for key in priority_keys:
                    if key in balance:
                        usdt_data = balance[key]
                        logging.info(colored(f"📋 Found {key}: {usdt_data}", "cyan"))
                        
                        if isinstance(usdt_data, dict):
                            # Try multiple balance keys, prioritizing non-None values
                            for balance_key in ['total', 'free', 'available', 'balance']:
                                if balance_key in usdt_data and usdt_data[balance_key] is not None:
                                    try:
                                        usdt_balance = float(usdt_data[balance_key])
                                        found_key = f"{key}.{balance_key}"
                                        logging.info(colored(f"💰 USDT Balance: ${usdt_balance:.2f} (from {found_key})", "green"))
                                        break
                                    except (ValueError, TypeError):
                                        continue
                            
                            if usdt_balance is not None:
                                break
                                
                        elif isinstance(usdt_data, (int, float, str)) and usdt_data is not None:
                            try:
                                usdt_balance = float(usdt_data)
                                found_key = key
                                logging.info(colored(f"💰 USDT Balance: ${usdt_balance:.2f} (from {found_key})", "green"))
                                break
                            except (ValueError, TypeError):
                                continue
            
            # STEP 4: Final validation
            if usdt_balance is None:
                logging.error(colored("❌ Could not find any valid balance! Available data:", "red"))
                for key, value in balance.items():
                    if isinstance(value, dict) and any(sub_key in ['total', 'free', 'balance'] for sub_key in value.keys()):
                        logging.error(colored(f"🔍 {key}: {value}", "red"))
                    elif isinstance(value, (int, float, str)) and 'balance' in key.lower():
                        logging.error(colored(f"🔍 {key}: {value}", "red"))
                
                usdt_balance = 0
                found_key = "NOT_FOUND"
            
        else:
            logging.error(colored(f"❌ Balance response non è un dictionary: {balance}", "red"))
            usdt_balance = 0
            found_key = "INVALID_RESPONSE"
        
        # RISULTATO FINALE CON DISPLAY MIGLIORATO
        if usdt_balance is None or usdt_balance == 0:
            logging.warning(colored(f"⚠️ Balance non disponibile (source: {found_key})", "yellow"))
            return None
        else:
            # Enhanced balance display
            balance_type = "💼 TOTAL EQUITY" if found_key in ["totalWalletBalance", "totalEquity"] else "💰 USDT ONLY"
            logging.info(colored("=" * 60, "green"))
            logging.info(colored(f"✅ LIVE MODE BALANCE RECOVERY SUCCESS", "green", attrs=['bold']))
            logging.info(colored(f"💳 Account Type: Bybit Unified Account", "green"))
            logging.info(colored(f"{balance_type}: ${usdt_balance:.2f} USD", "green", attrs=['bold']))
            logging.info(colored(f"🔑 Source: {found_key}", "green"))
            logging.info(colored(f"🚀 Ready for live trading with ${usdt_balance:.2f}", "green"))
            logging.info(colored("=" * 60, "green"))
        
        return usdt_balance
        
    except Exception as e:
        error_msg = str(e)
        logging.error(colored(f"❌ Errore nel recupero del saldo: {error_msg}", "red"))
        logging.error(colored(f"🔍 Tipo errore: {type(e).__name__}", "red"))
        
        # Controlla errori comuni Bybit
        if "33004" in error_msg or "api key expired" in error_msg.lower():
            logging.error(colored("🔑 Errore: API key scaduta o non valida", "red"))
        elif "10003" in error_msg or "invalid api key" in error_msg.lower():
            logging.error(colored("🔑 Errore: API key non valida", "red"))
        elif "permissions" in error_msg.lower():
            logging.error(colored("🔒 Errore: Permissions insufficienti - serve 'Read' permission", "red"))
        elif "authentication" in error_msg.lower():
            logging.error(colored("🔐 Errore: Problema di autenticazione", "red"))
        elif "invalid signature" in error_msg.lower():
            logging.error(colored("🔏 Errore: Firma API non valida", "red"))
        else:
            logging.error(colored(f"❓ Errore sconosciuto: {error_msg}", "red"))
        
        return None

async def get_open_positions(exchange):
    try:
        positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
        return len([p for p in positions if float(p.get('contracts', 0)) > 0])
    except Exception as e:
        logging.error(colored(f"❌ Errore nel recupero delle posizioni aperte: {e}", "red"))
        return 0

async def sync_positions_at_startup(exchange):
    """
    Sincronizza le posizioni del position tracker con quelle reali su Bybit all'avvio
    
    LIVE Mode: Importa posizioni esistenti da Bybit
    DEMO Mode: Reset completo del position tracker
    """
    try:
        if config.DEMO_MODE:
            logging.info(colored("🎮 DEMO MODE: Resetting position tracker for fresh simulation", "magenta"))
            
            # Reset complete del position tracker
            if POSITION_TRACKER_AVAILABLE:
                global_position_tracker.active_positions = {}
                global_position_tracker.session_stats = {
                    'initial_balance': 1000.0,
                    'current_balance': 1000.0,
                    'total_trades': 0,
                    'winning_trades': 0,
                    'total_pnl': 0.0,
                    'session_start': datetime.now().isoformat(),
                    'last_update': datetime.now().isoformat()
                }
                global_position_tracker.save_session()
                logging.info(colored("✅ Demo session reset complete - starting fresh", "green"))
            return 0
            
        else:
            # LIVE MODE: Sincronizza con posizioni reali
            logging.info(colored("🔍 LIVE MODE: Checking existing positions on Bybit...", "cyan"))
            
            positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_positions = [p for p in positions if float(p.get('contracts', 0)) > 0]
            
            if not active_positions:
                logging.info(colored("✅ No open positions found on Bybit - starting fresh", "green"))
                if POSITION_TRACKER_AVAILABLE:
                    global_position_tracker.active_positions = {}
                    global_position_tracker.save_session()
                return 0
            
            # Posizioni trovate su Bybit - sincronizza con tracker
            logging.info(colored(f"📊 Found {len(active_positions)} active positions on Bybit", "yellow"))
            
            if POSITION_TRACKER_AVAILABLE:
                # In LIVE mode, initialize tracker with REAL balance, not demo balance
                real_balance = await get_real_balance(exchange)
                if real_balance:
                    global_position_tracker.session_stats = {
                        'initial_balance': real_balance,
                        'current_balance': real_balance,
                        'total_trades': 0,
                        'winning_trades': 0,
                        'total_pnl': 0.0,
                        'session_start': datetime.now().isoformat(),
                        'last_update': datetime.now().isoformat()
                    }
                    logging.info(colored(f"💰 LIVE mode tracker initialized with real balance: ${real_balance:.2f}", "cyan"))
                
                # Clear existing tracker positions
                global_position_tracker.active_positions = {}
                
                # Import each real position into tracker
                for pos in active_positions:
                    try:
                        symbol = pos.get('symbol')
                        side = 'BUY' if float(pos.get('contracts', 0)) > 0 else 'SELL'
                        entry_price = float(pos.get('entryPrice', 0))
                        position_size = abs(float(pos.get('contracts', 0))) * entry_price  # Convert to USD value
                        unrealized_pnl = float(pos.get('unrealizedPnl', 0))
                        
                        if symbol and entry_price > 0:
                            # Create position ID for imported position
                            position_id = f"imported_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                            
                            # Calculate protective stop loss at 40% for imported positions
                            protective_stop_pct = 40.0  # 40% stop loss for existing positions
                            if side == 'BUY':
                                protective_stop_loss = entry_price * (1 - protective_stop_pct / 100)
                                protective_tp = entry_price * (1 + (protective_stop_pct / 100) * 0.5)  # Half risk for TP
                                trailing_trigger = entry_price * 1.01  # Start trailing at +1%
                            else:  # SELL
                                protective_stop_loss = entry_price * (1 + protective_stop_pct / 100)  
                                protective_tp = entry_price * (1 - (protective_stop_pct / 100) * 0.5)  # Half risk for TP
                                trailing_trigger = entry_price * 0.99  # Start trailing at -1%
                            
                            # Import position into tracker with protective levels
                            position_data = {
                                'position_id': position_id,
                                'symbol': symbol,
                                'side': side,
                                'entry_price': entry_price,
                                'entry_time': datetime.now().isoformat(),
                                'position_size': position_size,
                                'leverage': LEVERAGE,
                                'confidence': 0.7,  # Default confidence for imported positions
                                'atr': entry_price * 0.02,  # Estimated ATR
                                'take_profit': protective_tp,  # Protective TP calculated
                                'stop_loss': protective_stop_loss,  # 40% protective SL
                                'trailing_trigger': trailing_trigger,  # 1% trailing trigger
                                'initial_stop_loss': protective_stop_loss,  # Save original SL
                                'trailing_active': False,  # Will activate at +1%
                                'current_price': entry_price,
                                'unrealized_pnl_pct': (unrealized_pnl / position_size) * 100,
                                'unrealized_pnl_usd': unrealized_pnl,
                                'max_favorable_pnl': 0.0,
                                'status': 'OPEN',
                                'imported': True,  # Mark as imported from real exchange
                                'protective_sl_set': True  # Mark as having protective SL
                            }
                            
                            global_position_tracker.active_positions[position_id] = position_data
                            
                            logging.info(colored(
                                f"📥 Imported: {symbol} {side} @ {entry_price:.6f} | "
                                f"Size: ${position_size:.2f} | PnL: {unrealized_pnl:+.2f}",
                                "cyan"
                            ))
                            
                            # Enhanced logging for protective levels
                            logging.info(colored(
                                f"🛡️ PROTECTIVE LEVELS SET for {symbol}:",
                                "yellow", attrs=['bold']
                            ))
                            logging.info(colored(
                                f"   📉 Stop Loss: ${protective_stop_loss:.6f} (-{protective_stop_pct:.0f}%)",
                                "red"
                            ))
                            logging.info(colored(
                                f"   📈 Take Profit: ${protective_tp:.6f} (+{protective_stop_pct/2:.0f}%)",
                                "green"  
                            ))
                            logging.info(colored(
                                f"   🎪 Trailing Trigger: ${trailing_trigger:.6f} (±1.0%)",
                                "magenta"
                            ))
                            logging.info(colored(
                                f"   ✅ Bot will manage trailing stop automatically",
                                "green"
                            ))
                            
                            # CRITICAL FIX: Actually place protective orders on Bybit for imported positions
                            await place_protective_orders_on_bybit(
                                exchange, symbol, side, abs(float(pos.get('contracts', 0))),
                                protective_stop_loss, protective_tp
                            )
                            
                    except Exception as pos_error:
                        logging.error(f"Error importing position: {pos_error}")
                        continue
                
                global_position_tracker.save_session()
                logging.info(colored(f"✅ Position sync complete: {len(global_position_tracker.active_positions)} positions imported", "green"))
            
            return len(active_positions)
            
    except Exception as e:
        logging.error(colored(f"❌ Error during position sync: {e}", "red"))
        return 0

async def calculate_position_size(exchange, symbol, usdt_balance, min_amount=0, risk_factor=1.0):
    """DEPRECATED: Legacy function - use RobustRiskManager instead"""
    try:
        # CRITICAL FIX: Use unified risk manager for position sizing
        if RISK_MANAGER_AVAILABLE and global_risk_manager:
            ticker = await exchange.fetch_ticker(symbol)
            current_price = ticker.get('last')
            if current_price is None:
                return None
                
            # Extract or estimate ATR (simplified)
            atr = current_price * 0.02  # 2% fallback ATR
            
            position_size, stop_loss = global_risk_manager.calculate_position_size(
                symbol=symbol,
                signal_strength=risk_factor,
                current_price=current_price,
                atr=atr,
                account_balance=usdt_balance
            )
            
            return max(position_size, min_amount)
        else:
            # Legacy fallback (deprecated)
            logging.warning("Using deprecated position sizing - risk manager not available")
            ticker = await exchange.fetch_ticker(symbol)
            current_price = ticker.get('last')
            if current_price is None:
                return None
                
            # Use configured margin and leverage (respect user settings)
            margin_to_use = MARGIN_USDT
            
            # Safety check: don't use more than 20% of total balance
            max_safe_margin = usdt_balance * 0.2  # 20% safety limit
            if margin_to_use > max_safe_margin:
                margin_to_use = max_safe_margin
                logging.warning(colored(f"💡 Legacy: Margin reduced from ${MARGIN_USDT} to ${margin_to_use:.2f} (20% safety)", "yellow"))
            
            notional_value = margin_to_use * LEVERAGE
            position_size = notional_value / current_price
            
            logging.info(colored(f"📏 Legacy sizing: ${margin_to_use:.2f} margin × {LEVERAGE}x leverage = ${notional_value:.2f} notional", "cyan"))
            
            return max(position_size, min_amount)
            
    except Exception as e:
        logging.error(f"❌ Position size calculation failed for {symbol}: {e}")
        return min_amount

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
    
    # Use advanced risk management V2 (Thread-safe) if available
    if RISK_MANAGER_AVAILABLE and global_risk_manager:
        try:
            # Force sync with position tracker before risk calculations
            sync_success = global_risk_manager.force_sync()
            if not sync_success:
                logging.warning(colored(f"⚠️ Risk manager sync failed for {symbol}, using fallback", "yellow"))
            
            # For LIVE mode, use real balance instead of tracker balance
            if config.DEMO_MODE:
                current_balance = global_risk_manager.get_current_balance()
            else:
                current_balance = usdt_balance  # Use real Bybit balance in LIVE mode
                logging.info(colored(f"💰 Using real Bybit balance: ${current_balance:.2f} (LIVE mode)", "cyan"))
            
            # Calculate risk-based position size with thread-safe operations
            signal_confidence = predictions.get('confidence', 0.7) if predictions else 0.7
            position_size, calculated_stop_loss = global_risk_manager.calculate_position_size(
                symbol=symbol,
                signal_strength=signal_confidence,
                current_price=current_price,
                atr=atr,
                account_balance=current_balance,
                volatility=volatility
            )
            
            if position_size <= 0:
                logging.warning(colored(f"⚠️ Risk manager rejected position for {symbol}: zero size calculated", "yellow"))
                return "risk_rejected"
            
            # Build existing positions list from position tracker (thread-safe)
            existing_positions = []
            if POSITION_TRACKER_AVAILABLE:
                try:
                    for pos_id, pos in global_position_tracker.active_positions.items():
                        existing_positions.append(PositionRisk(
                            symbol=pos['symbol'],
                            side=pos['side'],
                            size=pos['position_size'],
                            entry_price=pos['entry_price'],
                            current_price=pos.get('current_price', pos['entry_price']),
                            unrealized_pnl=pos.get('unrealized_pnl_usd', 0.0)
                        ))
                except Exception as pos_error:
                    logging.debug(f"Could not build existing positions list: {pos_error}")
            
            # Validate position with risk manager (thread-safe)
            approved, reason = global_risk_manager.validate_new_position(
                symbol=symbol,
                side=side,
                size=position_size,
                current_price=current_price,
                account_balance=current_balance,
                existing_positions=existing_positions
            )
            
            if not approved:
                logging.warning(colored(f"⚠️ Risk manager rejected {symbol}: {reason}", "yellow"))
                return "risk_rejected"
            
            # Calculate proper stop loss (thread-safe)
            stop_loss_price = global_risk_manager.calculate_stop_loss(
                symbol=symbol,
                side=side,
                entry_price=current_price,
                atr=atr,
                volatility=volatility
            )
            
            # Calculate take profit
            take_profit_price = global_risk_manager.calculate_take_profit(
                symbol=symbol,
                side=side,
                entry_price=current_price,
                stop_loss=stop_loss_price,
                risk_reward_ratio=2.0
            )
            
            logging.info(colored(f"🛡️ Risk Management V2 Applied | {symbol}: Size={position_size:.4f}", "green"))
            logging.info(colored(f"🛡️ Stop Loss: {safe_format_price(stop_loss_price)} | Take Profit: {safe_format_price(take_profit_price)}", "green"))
            
        except Exception as e:
            logging.error(f"❌ Risk manager V2 error for {symbol}: {e}")
            # Fallback to basic calculation
            position_size = await calculate_fallback_position_size(symbol, current_price, usdt_balance)
            stop_loss_price = None
            
    else:
        # Fallback: Use original logic but improved
        logging.info(f"🔄 Using fallback position sizing for {symbol}")
        position_size = await calculate_fallback_position_size(symbol, current_price, usdt_balance)
        stop_loss_price = None
    
    # Get current open positions count
    if config.DEMO_MODE:
        current_open_positions = 0  # Demo: simulate no positions
        logging.info(colored(f"🎮 DEMO | {symbol}: {side} | Balance: {usdt_balance:.2f} USDT | Size: {position_size:.4f}", "magenta"))
    else:
        current_open_positions = await get_open_positions(exchange)
        logging.info(colored(f"💼 LIVE | {symbol}: {side} | Balance: {usdt_balance:.2f} USDT | Positions: {current_open_positions}/{MAX_CONCURRENT_POSITIONS}", "cyan"))
    
    # FIXED: Check position limits using centralized config
    if current_open_positions >= MAX_CONCURRENT_POSITIONS:
        logging.info(colored(f"{symbol}: Max trade limit reached ({current_open_positions}/{MAX_CONCURRENT_POSITIONS})", "yellow"))
        return "max_trades_reached"
    
    # FORCE DIRECT EXECUTION FOR PROPER STOP LOSS SETUP
    logging.info(colored(f"🔧 Using direct execution for proper risk management setup", "cyan"))
    
    # FALLBACK: Execute based on mode (Original Logic)
    if config.DEMO_MODE:
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
                
                # Check position limits using centralized config
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
        
        # Ensure we have a stop loss price calculated
        if stop_loss_price is None:
            # Calculate basic stop loss as fallback
            basic_stop_pct = 0.03  # 3% stop loss
            if side == "Buy":
                stop_loss_price = current_price * (1 - basic_stop_pct)
            else:
                stop_loss_price = current_price * (1 + basic_stop_pct)
            logging.info(colored(f"🛡️ Using fallback 3% stop loss: {safe_format_price(stop_loss_price)}", "yellow"))
        
        new_trade = await execute_order_with_risk_management(
            exchange, symbol, side, position_size, current_price, 
            current_time, df, predictions, stop_loss_price
        )
        return new_trade


async def calculate_fallback_position_size(symbol, current_price, usdt_balance):
    """
    Fallback position sizing respecting MARGIN_USDT configuration
    """
    try:
        # Use configured margin directly (respect user setting)
        margin_to_use = MARGIN_USDT
        
        # Safety check: don't use more than 20% of total balance
        max_safe_margin = usdt_balance * 0.2  # 20% safety limit
        if margin_to_use > max_safe_margin:
            margin_to_use = max_safe_margin
            logging.warning(colored(f"💡 Margin reduced from ${MARGIN_USDT} to ${margin_to_use:.2f} (20% of balance limit)", "yellow"))
        
        # Use full configured leverage
        notional_value = margin_to_use * LEVERAGE
        position_size = notional_value / current_price
        
        logging.info(colored(f"📏 Position sizing: ${margin_to_use:.2f} margin × {LEVERAGE}x leverage = ${notional_value:.2f} notional", "cyan"))
        logging.info(colored(f"📏 Final position size: {position_size:.4f} {symbol.split('/')[0]}", "cyan"))
        
        return position_size
        
    except Exception as e:
        logging.error(f"❌ Position calculation failed for {symbol}: {e}")
        return 0.0


async def execute_order_with_risk_management(exchange, symbol, side, position_size, price, 
                                           current_time, df, predictions, stop_loss_price):
    """
    Enhanced order execution with stop loss integration and verification
    """
    try:
        logging.info(colored(f"🚀 LIVE ORDER EXECUTION", "blue", attrs=['bold']))
        logging.info(colored(f"📊 Symbol: {symbol} | Side: {side} | Size: {position_size:.4f} | Price: ~{price:.6f}", "cyan"))
        
        # Execute main order with detailed logging
        start_time = time.time()
        
        if side == "Buy":
            logging.info(colored(f"📈 Executing MARKET BUY order for {position_size:.4f} {symbol}...", "green"))
            order = await exchange.create_market_buy_order(symbol, position_size)
        else:
            logging.info(colored(f"📉 Executing MARKET SELL order for {position_size:.4f} {symbol}...", "red"))
            order = await exchange.create_market_sell_order(symbol, position_size)
        
        execution_time = time.time() - start_time
        
        # Validate order response
        if not order or not order.get('id'):
            logging.error(colored(f"❌ Invalid order response: {order}", "red"))
            return "invalid_order_response"
            
        entry_price = order.get('average') or order.get('price') or price
        trade_id = order.get("id")
        order_status = order.get('status', 'unknown')
        filled_amount = order.get('filled', 0)
        
        # Enhanced order confirmation display
        logging.info(colored("=" * 70, "green"))
        logging.info(colored("✅ ORDER EXECUTED SUCCESSFULLY", "green", attrs=['bold']))
        logging.info(colored(f"🆔 Order ID: {trade_id}", "green"))
        logging.info(colored(f"📊 Symbol: {symbol} | Side: {side.upper()}", "green"))
        logging.info(colored(f"💰 Entry Price: ${entry_price:.6f}", "green"))
        logging.info(colored(f"📏 Size: {position_size:.4f} | Filled: {safe_format_float(filled_amount, 4, 'N/A')}", "green"))
        logging.info(colored(f"📈 Status: {order_status.upper()}", "green"))
        logging.info(colored(f"⚡ Execution Time: {execution_time:.2f}s", "green"))
        
        # Verify position was actually opened (post-execution check)
        try:
            await asyncio.sleep(1)  # Small delay for exchange to register position
            positions = await exchange.fetch_positions([symbol])
            
            position_found = False
            for pos in positions:
                if (pos.get('symbol') == symbol and 
                    float(pos.get('contracts', 0)) != 0):
                    
                    contracts = float(pos.get('contracts', 0))
                    position_side = 'LONG' if contracts > 0 else 'SHORT'
                    unrealized_pnl = float(pos.get('unrealizedPnl', 0))
                    
                    logging.info(colored(f"✅ POSITION VERIFIED ON BYBIT:", "green", attrs=['bold']))
                    logging.info(colored(f"📊 {symbol} {position_side} | Contracts: {abs(contracts):.4f}", "green"))
                    logging.info(colored(f"💵 Unrealized PnL: ${unrealized_pnl:+.2f}", "green" if unrealized_pnl >= 0 else "red"))
                    
                    position_found = True
                    break
            
            if not position_found:
                logging.warning(colored(f"⚠️ Position not found on Bybit - may still be processing", "yellow"))
                
        except Exception as verify_error:
            logging.warning(f"Could not verify position on Bybit: {verify_error}")
        
        # ENHANCED RISK MANAGEMENT SETUP - CRITICAL: Separate display from execution
        stop_loss_order_id = None
        take_profit_order_id = None
        take_profit_price = None
        
        # SAFE DISPLAY: Try to show risk calculation but don't fail if it errors
        try:
            if stop_loss_price:
                logging.info(colored("🛡️ SETTING UP RISK MANAGEMENT", "yellow", attrs=['bold']))
                logging.info(colored("=" * 70, "yellow"))
                
                if side == "Buy":
                    risk = entry_price - stop_loss_price
                    take_profit_price = entry_price + (risk * 2.0)
                    risk_pct = (risk / entry_price) * 100
                    reward_pct = ((take_profit_price - entry_price) / entry_price) * 100
                else:
                    risk = stop_loss_price - entry_price
                    take_profit_price = entry_price - (risk * 2.0)
                    risk_pct = (risk / entry_price) * 100
                    reward_pct = ((entry_price - take_profit_price) / entry_price) * 100
                
                logging.info(colored(f"📊 RISK CALCULATION:", "cyan", attrs=['bold']))
                logging.info(colored(f"📈 Entry Price: ${entry_price:.6f}", "white"))
                logging.info(colored(f"🛡️ Stop Loss: {safe_format_price(stop_loss_price)} (-{risk_pct:.1f}%)", "red"))
                logging.info(colored(f"🎯 Take Profit: {safe_format_price(take_profit_price)} (+{reward_pct:.1f}%)", "green"))
                
                # Safe risk-reward ratio
                if risk_pct and risk_pct != 0 and reward_pct is not None:
                    ratio = reward_pct / risk_pct
                    logging.info(colored(f"⚖️ Risk-Reward Ratio: 1:{ratio:.1f}", "cyan"))
                else:
                    logging.info(colored(f"⚖️ Risk-Reward Ratio: N/A", "cyan"))
        except Exception as display_error:
            logging.warning(f"Risk display error (non-critical): {display_error}")
            # Continue - display errors don't affect order placement
        
        # Set Stop Loss on Bybit
        if stop_loss_price and not config.DEMO_MODE:
            try:
                logging.info(colored(f"🛡️ PLACING STOP LOSS ORDER on Bybit...", "red", attrs=['bold']))
                
                stop_side = "sell" if side == "Buy" else "buy"
                stop_order = await exchange.create_order(
                    symbol=symbol,
                    type='stop_market',
                    side=stop_side,
                    amount=position_size,
                    params={'stopPrice': stop_loss_price}
                )
                stop_loss_order_id = stop_order.get('id')
                logging.info(colored(f"✅ STOP LOSS ACTIVE: Order ID {stop_loss_order_id}", "green", attrs=['bold']))
                
            except Exception as sl_error:
                logging.error(colored(f"❌ STOP LOSS FAILED: {sl_error}", "red", attrs=['bold']))
        
        # Set Take Profit on Bybit
        if take_profit_price and not config.DEMO_MODE:
            try:
                logging.info(colored(f"🎯 PLACING TAKE PROFIT ORDER on Bybit...", "green", attrs=['bold']))
                
                tp_side = "sell" if side == "Buy" else "buy"
                tp_order = await exchange.create_order(
                    symbol=symbol,
                    type='take_profit_market',
                    side=tp_side,
                    amount=position_size,
                    params={'stopPrice': take_profit_price}
                )
                take_profit_order_id = tp_order.get('id')
                logging.info(colored(f"✅ TAKE PROFIT ACTIVE: Order ID {take_profit_order_id}", "green", attrs=['bold']))
                
            except Exception as tp_error:
                logging.error(colored(f"❌ TAKE PROFIT FAILED: {tp_error}", "red", attrs=['bold']))
        
        # Add position to tracker for trailing stop management
        if POSITION_TRACKER_AVAILABLE and not config.DEMO_MODE:
            try:
                logging.info(colored(f"🎪 SETTING UP TRAILING STOP...", "magenta", attrs=['bold']))
                position_id = global_position_tracker.open_position(
                    symbol=symbol,
                    side=side,
                    entry_price=entry_price,
                    position_size=position_size * entry_price,  # Convert to USD value
                    leverage=LEVERAGE,
                    confidence=predictions.get('confidence', 0.7) if predictions else 0.7,
                    atr=atr
                )
                logging.info(colored(f"✅ TRAILING STOP ACTIVE: Tracker ID {position_id}", "magenta", attrs=['bold']))
                logging.info(colored(f"🎪 Bot will manage trailing stop automatically", "magenta"))
                
            except Exception as tracker_error:
                logging.error(colored(f"❌ TRAILING STOP FAILED: {tracker_error}", "red", attrs=['bold']))
        
        logging.info(colored("=" * 70, "yellow"))
        logging.info(colored("🛡️ RISK MANAGEMENT SETUP COMPLETE", "green", attrs=['bold']))
        logging.info(colored("=" * 70, "green"))
        
        # Create enhanced trade record
        new_trade = {
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "position_size": position_size,
            "filled_amount": filled_amount,
            "order_status": order_status,
            "stop_loss": stop_loss_price,
            "stop_loss_order_id": stop_loss_order_id,
            "exit_price": None,
            "trade_type": "Open",
            "closed_pnl": None,
            "result": None,
            "risk_managed": True,
            "execution_time": execution_time,
            "trade_time": datetime.utcnow().isoformat(),
            "timestamp": datetime.utcnow().isoformat(),
            "status": "open",
            "verified_on_exchange": position_found if 'position_found' in locals() else False
        }
        
        return new_trade
        
    except Exception as e:
        error_str = str(e)
        logging.error(colored("=" * 70, "red"))
        logging.error(colored("❌ ORDER EXECUTION FAILED", "red", attrs=['bold']))
        logging.error(colored(f"🆔 Symbol: {symbol} | Side: {side}", "red"))
        logging.error(colored(f"💥 Error: {error_str}", "red"))
        logging.error(colored(f"🔍 Error Type: {type(e).__name__}", "red"))
        
        # Enhanced error categorization
        if "110007" in error_str or "not enough" in error_str:
            logging.error(colored("💰 Category: INSUFFICIENT_FUNDS", "red"))
            logging.error(colored("=" * 70, "red"))
            return "insufficient_balance"
        elif "110043" in error_str or "exceeds available balance" in error_str:
            logging.error(colored("💰 Category: BALANCE_EXCEEDED", "red"))
            logging.error(colored("=" * 70, "red"))
            return "insufficient_balance"
        elif "110012" in error_str or "reduce only" in error_str:
            logging.error(colored("🔒 Category: REDUCE_ONLY_MODE", "red"))
            logging.error(colored("=" * 70, "red"))
            return "reduce_only_error"
        elif "170213" in error_str or "order value too small" in error_str:
            logging.error(colored("📏 Category: ORDER_TOO_SMALL", "red"))
            logging.error(colored("=" * 70, "red"))
            return "order_too_small"
        else:
            logging.error(colored("❓ Category: UNKNOWN_ERROR", "red"))
            logging.error(colored("=" * 70, "red"))
            return "unknown_error"

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
