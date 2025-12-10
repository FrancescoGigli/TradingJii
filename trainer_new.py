"""
NEW Modular Trainer - Main Training Entry Point

This is the new simplified trainer that uses the modular training package.
After testing, this will replace the old trainer.py

Features:
- Walk-Forward Testing with 3 rounds
- Trading simulation on test sets
- Comprehensive reporting
- Clean modular architecture
"""

from __future__ import annotations

import logging
import asyncio
import numpy as np
from pathlib import Path
from termcolor import colored

import config
from data_utils import prepare_data
from training.labeling import label_with_triple_barrier, label_with_sl_awareness_v2
from training.features import create_temporal_features
from training.walk_forward import walk_forward_training

_LOG = logging.getLogger(__name__)


def ensure_trained_models_dir() -> str:
    """
    Create trained_models directory and return its path.
    
    This function maintains compatibility with main.py.
    
    Returns:
        str: Path to trained_models directory
    """
    trained_dir = Path(config.get_xgb_model_file("tmp")).parent
    trained_dir.mkdir(parents=True, exist_ok=True)
    return str(trained_dir)


async def train_xgboost_model_wrapper(top_symbols, exchange, timestep, timeframe, use_future_returns=False):
    """
    Main training wrapper with Walk-Forward Testing.
    
    This replaces the old train_xgboost_model_wrapper with a cleaner implementation.
    
    Args:
        top_symbols: List of symbols to train on
        exchange: CCXT exchange instance
        timestep: Timesteps for temporal features
        timeframe: Timeframe string (e.g., '15m')
        use_future_returns: Legacy parameter (not used)
        
    Returns:
        tuple: (model, scaler, metrics)
    """
    from fetcher import fetch_and_save_data
    
    X_all, y_all = [], []
    df_all = []  # Keep DataFrames for simulation
    
    labeling_method = "Triple Barrier" if config.TRIPLE_BARRIER_ENABLED else "SL-Aware"
    _LOG.info(f"🎯 Training XGBoost with {labeling_method} labeling for {timeframe}")
    
    # 📊 DATA COLLECTION
    print(colored(f"\n🧠 WALK-FORWARD TRAINING - Data Collection for {timeframe}", "magenta", attrs=['bold']))
    print(colored("=" * 100, "magenta"))
    print(colored(f"{'#':<4} {'SYMBOL':<20} {'SAMPLES':<10} {'STATUS':<15} {'BUY%':<8} {'SELL%':<8} {'NEUTRAL%':<8}", "white", attrs=['bold']))
    print(colored("-" * 100, "magenta"))
    
    successful_symbols = 0
    for idx, sym in enumerate(top_symbols, 1):
        try:
            # Fetch data with indicators
            df_with_indicators = await fetch_and_save_data(exchange, sym, timeframe)
            if df_with_indicators is None:
                _LOG.warning(f"No data returned for {sym} {timeframe}")
                continue
            
            # Prepare data for ML
            data = prepare_data(df_with_indicators)
            if not np.isfinite(data).all() or len(data) < timestep + config.FUTURE_RETURN_STEPS:
                _LOG.warning(f"Invalid or insufficient data for {sym}")
                continue
                
            successful_symbols += 1
            
            # Z-Score normalization if enabled
            if config.Z_SCORE_NORMALIZATION:
                from data_utils import add_z_score_normalization
                df_with_indicators = add_z_score_normalization(
                    df_with_indicators,
                    window=config.Z_SCORE_WINDOW
                )
            
            # LABELING
            if config.TRIPLE_BARRIER_ENABLED:
                labels = label_with_triple_barrier(
                    df_with_indicators,
                    lookforward=config.TRIPLE_BARRIER_LOOKFORWARD,
                    tp_pct=config.TRIPLE_BARRIER_TP_PCT,
                    sl_pct=config.TRIPLE_BARRIER_SL_PCT
                )
            else:
                labels, sl_features = label_with_sl_awareness_v2(
                    df_with_indicators,
                    lookforward_steps=config.FUTURE_RETURN_STEPS,
                    sl_percentage=config.SL_AWARENESS_PERCENTAGE,
                    percentile_buy=config.SL_AWARENESS_PERCENTILE_BUY,
                    percentile_sell=config.SL_AWARENESS_PERCENTILE_SELL
                )
            
            # Calculate label distribution
            if config.TRIPLE_BARRIER_ENABLED:
                buy_count = np.sum(labels == 1)
                sell_count = np.sum(labels == 2)
                neutral_count = np.sum(labels == 0)
            else:
                buy_count = np.sum(labels == 1)
                sell_count = np.sum(labels == 0)
                neutral_count = np.sum(labels == 2)
            
            total = len(labels)
            buy_pct = (buy_count / total * 100) if total > 0 else 0
            sell_pct = (sell_count / total * 100) if total > 0 else 0
            neutral_pct = (neutral_count / total * 100) if total > 0 else 0
            
            # Display progress
            symbol_short = sym.replace('/USDT:USDT', '')
            status = colored("✅ OK", "green")
            print(f"{idx:<4} {symbol_short:<20} {len(data):<10} {status:<15} {buy_pct:.1f}%    {sell_pct:.1f}%    {neutral_pct:.1f}%")
            
            # Progress separator every 10 symbols
            if idx % 10 == 0 and idx < len(top_symbols):
                print(colored("─" * 100, "blue"))
                print(colored(f"Progress: {idx}/{len(top_symbols)} ({idx/len(top_symbols)*100:.1f}%) | Success: {successful_symbols}/{idx}", "blue", attrs=['bold']))
                print(colored("─" * 100, "blue"))
            
            # Create temporal features
            timesteps_for_tf = config.get_timesteps_for_timeframe(timeframe)
            for i in range(timesteps_for_tf, len(data) - config.FUTURE_RETURN_STEPS):
                if i < len(labels):
                    # ✅ FIXED: Include current candle (i) in sequence
                    # Python slicing [start:end] excludes 'end', so we use i+1 to include candle i
                    # Example: if i=10, timesteps=8 → data[3:11] gives 8 candles [3,4,5,6,7,8,9,10]
                    sequence = data[i - timesteps_for_tf + 1 : i + 1]
                    temporal_features = create_temporal_features(sequence)
                    X_all.append(temporal_features)
                    y_all.append(labels[i])
                    
            # Store DataFrame for simulation with symbol tracking
            df_essential = df_with_indicators[['open', 'high', 'low', 'close', 'volume']].copy()
            df_essential['symbol'] = symbol_short  # ✅ Track symbol for per-symbol analysis
            df_all.append(df_essential)
                    
        except Exception as e:
            _LOG.error(f"Error processing {sym}: {e}")
            continue

    _LOG.info(f"💾 Total samples collected: {len(X_all)} from {successful_symbols} symbols")

    if not X_all:
        _LOG.error(f"❌ No valid training data for {timeframe}")
        return None, None, None

    # Convert to numpy arrays
    X_all = np.array(X_all)
    y_all = np.array(y_all)
    
    # Concatenate all DataFrames
    import pandas as pd
    df_combined = pd.concat(df_all, ignore_index=True)
    
    # Log class distribution
    unique, counts = np.unique(y_all, return_counts=True)
    class_distribution = {int(cls): int(count) for cls, count in zip(unique, counts)}
    total_samples = len(y_all)
    _LOG.info(f"📊 Final class distribution for {timeframe}: {class_distribution}")
    for cls, count in class_distribution.items():
        cls_name = {0: 'NEUTRAL', 1: 'BUY', 2: 'SELL'}[cls]
        _LOG.info(f"   {cls_name}: {count} ({count/total_samples*100:.1f}%)")
    
    # WALK-FORWARD TESTING
    model, scaler, report = walk_forward_training(
        all_data_X=X_all,
        all_data_y=y_all,
        all_data_df=df_combined,
        timeframe=timeframe
    )
    
    if model is None:
        _LOG.error(f"❌ Walk-Forward training failed for {timeframe}")
        return None, None, None
    
    _LOG.info(f"🎉 Training completed successfully for {timeframe}!")
    
    # Return model, scaler, and report
    metrics = report['aggregate'] if report else {}
    return model, scaler, metrics


# Entry point for standalone training
if __name__ == "__main__":
    import ccxt
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print(colored("\n" + "="*80, "cyan", attrs=['bold']))
    print(colored("🚀 WALK-FORWARD TRAINING SYSTEM", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan", attrs=['bold']))
    
    # Initialize exchange
    exchange = ccxt.bybit(config.exchange_config)
    
    # Get top symbols directly from exchange
    print(colored("📊 Fetching symbols from exchange...", "yellow"))
    markets = exchange.load_markets()
    
    # Filter for USDT perpetual futures
    usdt_symbols = [
        symbol for symbol in markets.keys()
        if '/USDT:USDT' in symbol and markets[symbol].get('active', False)
    ]
    
    # Sort by volume and take top N
    print(colored(f"Found {len(usdt_symbols)} USDT perpetual pairs", "yellow"))
    top_symbols = usdt_symbols[:config.TOP_SYMBOLS_COUNT]
    print(colored(f"✅ Using top {len(top_symbols)} symbols for training\n", "green"))
    
    # Train for each timeframe
    for timeframe in config.ENABLED_TIMEFRAMES:
        print(colored(f"\n{'='*80}", "magenta", attrs=['bold']))
        print(colored(f"🎯 TRAINING FOR TIMEFRAME: {timeframe}", "magenta", attrs=['bold']))
        print(colored(f"{'='*80}\n", "magenta", attrs=['bold']))
        
        timesteps = config.get_timesteps_for_timeframe(timeframe)
        
        try:
            model, scaler, metrics = asyncio.run(
                train_xgboost_model_wrapper(
                    top_symbols=top_symbols,
                    exchange=exchange,
                    timestep=timesteps,
                    timeframe=timeframe
                )
            )
            
            if model is not None:
                print(colored(f"\n✅ {timeframe} training completed successfully!", "green", attrs=['bold']))
            else:
                print(colored(f"\n❌ {timeframe} training failed!", "red", attrs=['bold']))
                
        except Exception as e:
            print(colored(f"\n❌ Error training {timeframe}: {e}", "red", attrs=['bold']))
            _LOG.exception(f"Training error for {timeframe}")
    
    print(colored("\n" + "="*80, "cyan", attrs=['bold']))
    print(colored("🎉 ALL TRAINING COMPLETED!", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan", attrs=['bold']))
