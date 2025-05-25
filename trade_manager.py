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
    TOP_ANALYSIS_CRYPTO
)
from fetcher import get_top_symbols, get_data_async

def is_symbol_excluded(symbol):
    normalized = re.sub(r'[^A-Za-z0-9]', '', symbol).upper()
    return any(exc.upper() in normalized for exc in EXCLUDED_SYMBOLS)

async def get_real_balance(exchange):
    try:
        balance = await exchange.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        if usdt_balance == 0:
            logging.warning(colored("⚠️ Il saldo USDT è zero o non trovato.", "yellow"))
        return usdt_balance
    except Exception as e:
        logging.error(colored(f"❌ Errore nel recupero del saldo: {e}", "red"))
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
    current_time = time.time()
    
    # Limite fisso di 3 posizioni massime
    max_trades = 3
    current_open_positions = await get_open_positions(exchange)
    
    logging.info(colored(f"Balance: {usdt_balance:.2f} USDT | Max trade: {max_trades} | Posizioni aperte: {current_open_positions}", "cyan"))
    
    # Verifica se abbiamo già raggiunto il limite massimo di trade
    if current_open_positions >= max_trades:
        logging.info(colored(f"{symbol}: Apertura non consentita. Limite trade raggiunto ({current_open_positions}/{max_trades}).", "yellow"))
        return "max_trades_reached"
    
    
    margin = MARGIN_USDT
    logging.info(colored(f"{symbol} - Utilizzo margine USDT: {margin:.2f}", "magenta"))
    position_size = await calculate_position_size(exchange, symbol, usdt_balance, min_amount=min_amounts.get(symbol, 0.1))
    if not position_size or position_size < min_amounts.get(symbol, 0.1):
        return
    ticker = await exchange.fetch_ticker(symbol)
    price = ticker.get('last')
    if price is None:
        logging.error(colored(f"❌ Prezzo corrente non disponibile per {symbol}", "red"))
        return
    if usdt_balance < 30.0:
        logging.warning(colored(f"{symbol}: Saldo USDT insufficiente.", "yellow"))
        return "insufficient_balance"
    try:
        await exchange.set_leverage(LEVERAGE, symbol)
    except Exception as lev_err:
        logging.warning(colored(f"{symbol}: Leva non modificata: {lev_err}", "yellow"))
    side = "Buy" if signal == 1 else "Sell"
    logging.info(colored(f"{symbol}: Ordine eseguito: {side}", "blue"))
    new_trade = await execute_order(exchange, symbol, side, position_size, price, current_time, df, predictions)
    return new_trade

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
