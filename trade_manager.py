#!/usr/bin/env python3
"""
Trade Manager - Balance and Account Management

Provides utility functions for retrieving account information from Bybit.
"""

import logging
from typing import Optional
import ccxt

async def get_real_balance(exchange: ccxt.Exchange) -> Optional[float]:
    """
    Fetch real USDT balance from Bybit exchange
    
    Args:
        exchange: CCXT exchange instance
        
    Returns:
        float: Available USDT balance, or None if error
    """
    try:
        # Fetch balance from exchange
        balance_data = await exchange.fetch_balance()
        
        # Try multiple balance structures (Standard Account vs Unified Trading)
        usdt_balance = None
        
        # Try structure 1: balance['free']['USDT'] (Standard Account)
        if 'free' in balance_data and isinstance(balance_data['free'], dict):
            usdt_balance = balance_data['free'].get('USDT', 0.0)
        
        # Try structure 2: balance['USDT']['free'] (Alternative format)
        if (usdt_balance is None or usdt_balance == 0) and 'USDT' in balance_data:
            if isinstance(balance_data['USDT'], dict):
                usdt_balance = balance_data['USDT'].get('free', 0.0)
        
        # Try structure 3: balance['total']['USDT'] (Unified Trading Account)
        if (usdt_balance is None or usdt_balance == 0) and 'total' in balance_data:
            if isinstance(balance_data['total'], dict):
                usdt_balance = balance_data['total'].get('USDT', 0.0)
        
        # Return balance
        if usdt_balance is not None and usdt_balance > 0:
            logging.info(f"💰 USDT Balance: ${usdt_balance:.2f}")
            return float(usdt_balance)
        else:
            logging.warning(f"⚠️ USDT balance is 0 or not available")
            return 0.0
            
    except Exception as e:
        logging.error(f"❌ Error fetching balance from Bybit: {e}")
        return None
