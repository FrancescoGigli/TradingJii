"""
Labeling Module - Triple Barrier and SL-Aware Methods

Contains two labeling strategies:
1. Triple Barrier: Mathematically rigorous SL/TP barrier method
2. SL-Aware: Percentile-based method with SL awareness
"""

from __future__ import annotations

import logging
import numpy as np

import config

_LOG = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# TRIPLE BARRIER LABELING (New - Global Model Compatible)
# ----------------------------------------------------------------------
def label_with_triple_barrier(df, lookforward=8, tp_pct=0.09, sl_pct=0.06):
    """
    🎯 TRIPLE BARRIER METHOD - Mathematically Rigorous Labeling
    
    Simula trade execution con barriere SL/TP allineate al trading reale.
    Per ogni candela, testa LONG e SHORT e verifica chi tocca TP/SL per primo.
    
    VANTAGGI vs SL-Aware percentile:
    - Matematicamente rigoroso (no percentili relativi)
    - Allineato con trading reale (SL=6%, TP=9%)
    - Asimmetrico TP/SL per migliore risk/reward
    - Supporta SHORT trading (classe 2)
    - Più semplice da interpretare
    
    Args:
        df: DataFrame con OHLCV
        lookforward: Candele future (default 8 = 2h su 15m, 40min su 5m)
        tp_pct: Take profit % (default 0.09 = 9%)
        sl_pct: Stop loss % (default 0.06 = 6%)
    
    Returns:
        labels: Array [0=NEUTRAL, 1=BUY, 2=SELL]
    
    Labels logic:
    - BUY (1): Se TP long raggiunto PRIMA di SL long
    - SELL (2): Se TP short raggiunto PRIMA di SL short  
    - NEUTRAL (0): Se SL hit per primo, o nulla toccato, o timeout
    """
    labels = np.zeros(len(df), dtype=int)  # Default NEUTRAL
    
    close_prices = df['close'].values
    high_prices = df['high'].values
    low_prices = df['low'].values
    
    # Statistics
    stats = {
        'buy_tp_hit': 0,
        'buy_sl_hit': 0,
        'sell_tp_hit': 0,
        'sell_sl_hit': 0,
        'both_valid': 0,
        'timeout': 0
    }
    
    for i in range(len(df) - lookforward):
        entry_price = close_prices[i]
        
        # Future path
        future_highs = high_prices[i+1:i+1+lookforward]
        future_lows = low_prices[i+1:i+1+lookforward]
        
        # === LONG SCENARIO ===
        long_tp = entry_price * (1 + tp_pct)
        long_sl = entry_price * (1 - sl_pct)
        
        # Chi viene toccato prima?
        long_tp_hits = np.where(future_highs >= long_tp)[0]
        long_sl_hits = np.where(future_lows <= long_sl)[0]
        
        long_tp_time = long_tp_hits[0] if len(long_tp_hits) > 0 else float('inf')
        long_sl_time = long_sl_hits[0] if len(long_sl_hits) > 0 else float('inf')
        
        # === SHORT SCENARIO ===
        short_tp = entry_price * (1 - tp_pct)  # Profit per short
        short_sl = entry_price * (1 + sl_pct)  # Loss per short
        
        short_tp_hits = np.where(future_lows <= short_tp)[0]
        short_sl_hits = np.where(future_highs >= short_sl)[0]
        
        short_tp_time = short_tp_hits[0] if len(short_tp_hits) > 0 else float('inf')
        short_sl_time = short_sl_hits[0] if len(short_sl_hits) > 0 else float('inf')
        
        # === LABELING LOGIC ===
        long_wins = long_tp_time < long_sl_time
        short_wins = short_tp_time < short_sl_time
        
        if long_wins and short_wins:
            # Entrambi validi - chi tocca TP per primo vince
            stats['both_valid'] += 1
            if long_tp_time < short_tp_time:
                labels[i] = 1  # BUY
                stats['buy_tp_hit'] += 1
            else:
                labels[i] = 2  # SELL
                stats['sell_tp_hit'] += 1
        elif long_wins:
            labels[i] = 1  # BUY
            stats['buy_tp_hit'] += 1
            if long_sl_time < float('inf'):
                stats['buy_sl_hit'] += 1  # SL hit ma dopo TP
        elif short_wins:
            labels[i] = 2  # SELL
            stats['sell_tp_hit'] += 1
            if short_sl_time < float('inf'):
                stats['sell_sl_hit'] += 1  # SL hit ma dopo TP
        else:
            # NEUTRAL: SL hit per primo o timeout
            labels[i] = 0  # NEUTRAL
            if long_sl_time < float('inf') or short_sl_time < float('inf'):
                if long_sl_time <= short_sl_time:
                    stats['buy_sl_hit'] += 1
                else:
                    stats['sell_sl_hit'] += 1
            else:
                stats['timeout'] += 1
    
    # Log statistics
    buy_count = np.sum(labels == 1)
    sell_count = np.sum(labels == 2)
    neutral_count = np.sum(labels == 0)
    total = len(labels)
    
    _LOG.info(f"📊 Triple Barrier Labeling (lookforward={lookforward}, TP={tp_pct:.1%}, SL={sl_pct:.1%}):")
    _LOG.info(f"   BUY:     {buy_count:5d} ({buy_count/total*100:.1f}%) - TP hits: {stats['buy_tp_hit']}")
    _LOG.info(f"   SELL:    {sell_count:5d} ({sell_count/total*100:.1f}%) - TP hits: {stats['sell_tp_hit']}")
    _LOG.info(f"   NEUTRAL: {neutral_count:5d} ({neutral_count/total*100:.1f}%) - SL/Timeout")
    _LOG.info(f"   Both valid: {stats['both_valid']}, Timeouts: {stats['timeout']}")
    
    return labels


# ----------------------------------------------------------------------
# SL-AWARE LABELING (Legacy - kept for compatibility)
# ----------------------------------------------------------------------
def label_with_sl_awareness_v2(df, lookforward_steps=3, sl_percentage=0.05,
                                percentile_buy=80, percentile_sell=80):
    """
    🎯 PRODUCTION: Stop Loss Aware Labeling con Feature Engineering
    
    Invece di eliminare sample con SL hit, li mantiene e aggiunge features
    che insegnano al modello a riconoscere situazioni a rischio SL.
    
    FEATURES AVANZATE:
    - NO survivorship bias (mantiene tutti i sample)
    - Feature engineering (5 nuove features per ogni sample)
    - Borderline asimmetrici (pump vs dump)
    - Risoluzione ambiguità BUY/SELL
    - Percentili configurabili
    - Vectorizzato NumPy per performance
    
    Args:
        df: DataFrame con OHLCV columns
        lookforward_steps: Candele future per label
        sl_percentage: Stop loss % (default 0.05 = 5%)
        percentile_buy: Percentile per BUY (default 80 = top 20%)
        percentile_sell: Percentile per SELL (default 80 = top 20%)
    
    Returns:
        tuple: (labels, sl_features_dict)
    """
    labels = np.full(len(df), 2)  # Default NEUTRAL
    
    # Feature engineering (manteniamo tutti i sample!)
    sl_features = {
        'sl_hit_buy': np.zeros(len(df)),
        'sl_hit_sell': np.zeros(len(df)),
        'max_drawdown_pct': np.zeros(len(df)),
        'max_drawup_pct': np.zeros(len(df)),
        'volatility_path': np.zeros(len(df))
    }
    
    buy_returns_data = []
    sell_returns_data = []
    
    # Vectorized arrays
    close_prices = df['close'].values
    low_prices = df['low'].values
    high_prices = df['high'].values
    
    # Statistics
    sl_hit_count = {'buy': 0, 'sell': 0, 'both': 0}
    borderline_count = {'buy': 0, 'sell': 0}
    
    for i in range(len(df) - lookforward_steps):
        entry_price = close_prices[i]
        
        # Path slices
        path_lows = low_prices[i:i+lookforward_steps]
        path_highs = high_prices[i:i+lookforward_steps]
        path_closes = close_prices[i:i+lookforward_steps]
        
        # BUY SCENARIO
        buy_sl_price = entry_price * (1 - sl_percentage)
        buy_sl_hit = np.any(path_lows <= buy_sl_price)
        max_drawdown = np.min(path_lows)
        max_drawdown_pct = (max_drawdown - entry_price) / entry_price
        buy_borderline = (max_drawdown_pct < -config.SL_AWARENESS_BORDERLINE_BUY and 
                         max_drawdown_pct > -sl_percentage)
        
        # SELL SCENARIO
        sell_sl_price = entry_price * (1 + sl_percentage)
        sell_sl_hit = np.any(path_highs >= sell_sl_price)
        max_drawup = np.max(path_highs)
        max_drawup_pct = (max_drawup - entry_price) / entry_price
        sell_borderline = (max_drawup_pct > config.SL_AWARENESS_BORDERLINE_SELL and 
                          max_drawup_pct < sl_percentage)
        
        # VOLATILITY
        volatility = np.std(path_closes) / (np.mean(path_closes) + 1e-8)
        
        # Store features
        sl_features['sl_hit_buy'][i] = 1.0 if buy_sl_hit else 0.0
        sl_features['sl_hit_sell'][i] = 1.0 if sell_sl_hit else 0.0
        sl_features['max_drawdown_pct'][i] = max_drawdown_pct
        sl_features['max_drawup_pct'][i] = max_drawup_pct
        sl_features['volatility_path'][i] = volatility
        
        # Statistics
        if buy_sl_hit and sell_sl_hit:
            sl_hit_count['both'] += 1
        elif buy_sl_hit:
            sl_hit_count['buy'] += 1
        elif sell_sl_hit:
            sl_hit_count['sell'] += 1
        
        if buy_borderline:
            borderline_count['buy'] += 1
        if sell_borderline:
            borderline_count['sell'] += 1
        
        # Calculate returns
        future_price = close_prices[i + lookforward_steps]
        buy_return = (future_price - entry_price) / entry_price
        sell_return = (entry_price - future_price) / entry_price
        
        # FIX: Add to BOTH lists, let percentile decide (no ambiguity resolution)
        # This fixes the bug where abs_buy > abs_sell is almost always FALSE
        if not buy_borderline:
            buy_returns_data.append((i, buy_return, buy_sl_hit))
        
        if not sell_borderline:
            sell_returns_data.append((i, sell_return, sell_sl_hit))
    
    # PERCENTILE LABELING - FIXED: Include anche sample con SL hit
    # DEBUG: Log size dei dataset
    _LOG.debug(f"buy_returns_data size: {len(buy_returns_data)}, sell_returns_data size: {len(sell_returns_data)}")
    
    if buy_returns_data:
        # Usa TUTTI i returns (safe + risky) per percentile
        all_returns = np.array([r for _, r, _ in buy_returns_data])
        buy_threshold = np.percentile(all_returns, percentile_buy)
        
        _LOG.debug(f"BUY threshold (percentile {percentile_buy}): {buy_threshold:.6f}")
        
        # Label sia safe che risky, ma con threshold uguale
        labeled_count = 0
        for idx, return_val, sl_hit in buy_returns_data:
            if return_val >= buy_threshold:
                labels[idx] = 1  # BUY (anche se ha SL hit nel path)
                labeled_count += 1
        
        _LOG.debug(f"BUY labeled: {labeled_count}/{len(buy_returns_data)}")
    else:
        _LOG.warning(f"⚠️ buy_returns_data is EMPTY! All samples filtered or went to SELL")
    
    if sell_returns_data:
        # Usa TUTTI i returns (safe + risky) per percentile
        all_returns = np.array([r for _, r, _ in sell_returns_data])
        sell_threshold = np.percentile(all_returns, percentile_sell)
        
        _LOG.debug(f"SELL threshold (percentile {percentile_sell}): {sell_threshold:.6f}")
        
        # Label sia safe che risky
        labeled_count = 0
        for idx, return_val, sl_hit in sell_returns_data:
            if return_val >= sell_threshold:
                labels[idx] = 0  # SELL  
                labeled_count += 1
        
        _LOG.debug(f"SELL labeled: {labeled_count}/{len(sell_returns_data)}")
    
    # Log statistics
    buy_count = np.sum(labels == 1)
    sell_count = np.sum(labels == 0)
    neutral_count = np.sum(labels == 2)
    total = len(labels)
    
    _LOG.info(f"🎯 SL-Aware Labeling:")
    _LOG.info(f"   SL hits: BUY={sl_hit_count['buy']}, SELL={sl_hit_count['sell']}, BOTH={sl_hit_count['both']}")
    _LOG.info(f"   Borderline: BUY={borderline_count['buy']}, SELL={borderline_count['sell']}")
    _LOG.info(f"   Labels: BUY={buy_count}({buy_count/total*100:.1f}%), SELL={sell_count}({sell_count/total*100:.1f}%), NEUTRAL={neutral_count}({neutral_count/total*100:.1f}%)")
    
    return labels, sl_features
