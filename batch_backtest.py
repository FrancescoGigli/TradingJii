#!/usr/bin/env python3
"""
batch_backtest.py

Utility to perform batch backtesting across multiple symbols and timeframes:
- Gets top symbols by volume from the exchange
- Downloads data for each symbol and timeframe
- Runs backtest on each combination
- Saves graphs, logs, and statistics
- Generates a summary report
"""

import os
import sys
import pandas as pd
import asyncio
import logging
import ccxt.async_support as ccxt
from datetime import datetime
import csv
from pathlib import Path
import json
import argparse
import numpy as np # Import numpy

# Set non-interactive matplotlib backend before importing pyplot
# This prevents tkinter threading issues with asyncio
import matplotlib
matplotlib.use('Agg')  # Use the Agg backend which doesn't require a GUI
import matplotlib.pyplot as plt # Import matplotlib for plotting

# Important: Set the TIMEFRAME_DEFAULT before importing any local modules
# This ensures all modules use this value when they import config
import config as global_config
# Set a default timeframe from the enabled timeframes
if global_config.ENABLED_TIMEFRAMES:
    global_config.TIMEFRAME_DEFAULT = global_config.ENABLED_TIMEFRAMES[0]
else:
    global_config.TIMEFRAME_DEFAULT = "15m"  # Fallback if no enabled timeframes

# Local imports - these need to come after setting TIMEFRAME_DEFAULT
from config import exchange_config, ENABLED_TIMEFRAMES
from fetcher import get_top_symbols, fetch_and_save_data
# Import the async function directly from backtest module
from backtest import Backtest  # Import the Backtest class instead

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Default configuration
TOP_SYMBOLS_LIMIT = 5
DEFAULT_INITIAL_BALANCE = 1000.0
DEFAULT_TAKE_PROFIT_PCT = 1.0 
DEFAULT_STOP_LOSS_PCT = 1.0
DEFAULT_POSITION_SIZE_PCT = 10.0
DEFAULT_MAX_BARS_IN_TRADE = 3
DEFAULT_LEVERAGE = 1.0 # Nuovo parametro per la leva
OUTPUT_DIR = os.path.join('logs', 'backtest', 'batch')
SUMMARY_FILE = os.path.join(OUTPUT_DIR, 'summary.csv')

async def get_top_symbols_by_volume(exchange, limit=TOP_SYMBOLS_LIMIT):
    """
    Get top symbols by volume from the exchange
    
    Args:
        exchange: Exchange instance
        limit: Number of symbols to retrieve
        
    Returns:
        list: Top symbols by volume
    """
    # Get all USDT markets that are active and of type 'swap'
    markets = await exchange.load_markets()
    symbols = [m['symbol'] for m in markets.values() 
               if m.get('quote') == 'USDT' 
               and m.get('active') 
               and m.get('type') == 'swap']
    
    # Get top symbols by volume
    top_symbols = await get_top_symbols(exchange, symbols, top_n=limit)
    return top_symbols

async def download_data(exchange, symbol, timeframe):
    """
    Download data for a symbol and timeframe
    
    Args:
        exchange: Exchange instance
        symbol: Trading pair symbol
        timeframe: Timeframe (e.g., '1h', '4h')
    
    Returns:
        DataFrame or None: DataFrame with OHLCV and indicators or None if failed
    """
    try:
        logging.info(f"Downloading data for {symbol} ({timeframe})")
        # Pass save_to_db=False to prevent saving to database during batch backtest
        df = await fetch_and_save_data(exchange, symbol, timeframe, save_to_db=False)
        
        if df is None:
            logging.error(f"Failed to download data for {symbol} ({timeframe})")
            return None
        logging.info(f"Downloaded {len(df)} candles for {symbol} ({timeframe})")
        return df
    except Exception as e:
        logging.error(f"Error downloading data for {symbol} ({timeframe}): {e}")
        return None

async def process_symbol_timeframe(exchange, symbol, timeframe, config):
    """
    Process a single symbol and timeframe combination
    
    Args:
        exchange: Exchange instance
        symbol: Trading pair symbol
        timeframe: Timeframe (e.g., '1h', '4h')
        config: Dictionary containing backtest configuration
        
    Returns:
        dict: Statistics from the backtest or None if failed
    """
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    safe_symbol = symbol.replace('/', '_').replace(':USDT', '')
    
    try:
        # Run backtest
        logging.info(f"Running backtest for {symbol} ({timeframe})")
        
        # Create backtest instance
        bt = Backtest(
            symbol=symbol,
            timeframes=[timeframe],  # Pass as list as required
            initial_balance=config['initial_balance'],
            take_profit_pct=config['take_profit_pct'],
            stop_loss_pct=config['stop_loss_pct'],
            position_size_pct=config['position_size_pct'],
            max_bars_in_trade=config['max_bars_in_trade'],
            leverage=config['leverage']
        )
        
        # Load data from exchange
        data_loaded = await bt.load_data_from_async(exchange)
        
        if not data_loaded:
            logging.error(f"Failed to load data for {symbol} ({timeframe})")
            return None
            
        # Run the backtest
        bt.run()
        
        # Save trades log
        trades_file = os.path.join(OUTPUT_DIR, f"trades_{safe_symbol}_{timeframe}_{timestamp}.csv")
        trades_df = pd.DataFrame(bt.trades)
        if not trades_df.empty:
            # Convert timestamps to string for CSV export
            if 'entry_time' in trades_df.columns:
                trades_df['entry_time'] = trades_df['entry_time'].astype(str)
            if 'exit_time' in trades_df.columns:
                trades_df['exit_time'] = trades_df['exit_time'].astype(str)
            
            trades_df.to_csv(trades_file, index=False)
            logging.info(f"Saved trades log to {trades_file}")
        
        # Save equity chart - implement our own plotting since bt.plot_results may not exist
        chart_file = os.path.join(OUTPUT_DIR, f"equity_{safe_symbol}_{timeframe}.png")
        
        try:
            # Try to use the object's plot_results method if it exists
            if hasattr(bt, 'plot_results') and callable(getattr(bt, 'plot_results')):
                bt.plot_results(save_path=chart_file)
                logging.info(f"Saved equity chart to {chart_file} using object's plot_results")
            else:
                # Otherwise implement our own plotting
                plt.figure(figsize=(12, 10))
                
                # Plot equity curve
                plt.subplot(2, 1, 1)
                plt.plot(bt.equity, label='Equity')
                plt.title(f'Backtest Results - {symbol} ({timeframe})')
                plt.ylabel('Portfolio Value')
                plt.grid(True)
                plt.legend()
                
                # Plot drawdown
                plt.subplot(2, 1, 2)
                equity_series = pd.Series(bt.equity)
                running_max = equity_series.cummax()
                drawdown = (running_max - equity_series) / running_max * 100
                plt.fill_between(range(len(drawdown)), 0, drawdown, color='red', alpha=0.3)
                plt.title('Drawdown %')
                plt.xlabel('Bars')
                plt.ylabel('Drawdown %')
                plt.grid(True)
                
                plt.tight_layout()
                plt.savefig(chart_file)
                plt.close()
                logging.info(f"Saved equity chart to {chart_file} using custom plotting")
        except Exception as e:
            logging.error(f"Error creating equity chart: {e}")
        
        # Also save a detailed price chart with trade entries/exits
        trade_chart_file = os.path.join(OUTPUT_DIR, f"backtest_{safe_symbol}_{timeframe}.png")
        os.makedirs(os.path.dirname(trade_chart_file), exist_ok=True)
        
        # Plot price and trades on a separate chart
        if hasattr(bt, 'dataframes') and bt.trades:
            try:
                # Create a figure with price and trade markers
                plt.figure(figsize=(14, 8))
                
                # Get the main dataframe
                tf = bt.timeframes[0]  # Use the first timeframe
                df = bt.dataframes[tf]
                
                # Plot price
                plt.plot(df.index, df['close'], label='Price', color='blue')
                plt.title(f'Price and Trades - {symbol} ({timeframe})')
                plt.ylabel('Price')
                plt.grid(True)
                
                # Add markers for trades
                for trade in bt.trades:
                    entry_color = 'green' if trade['pnl'] > 0 else 'red'
                    entry_marker = '^' if trade['side'] == 'BUY' else 'v'
                    
                    # Entry point
                    plt.scatter(trade['entry_time'], trade['entry_price'], 
                              color=entry_color, marker=entry_marker, s=100)
                    
                    # Add entry price annotation
                    plt.annotate(f"{trade['entry_price']:.2f}", 
                               xy=(trade['entry_time'], trade['entry_price']),
                               xytext=(5, 10 if trade['side'] == 'BUY' else -25),
                               textcoords='offset points',
                               fontsize=9,
                               bbox=dict(boxstyle="round,pad=0.3", fc=entry_color, alpha=0.3))
                    
                    # Exit point
                    plt.scatter(trade['exit_time'], trade['exit_price'], 
                              color=entry_color, marker='o', s=100)
                    
                    # Add exit price annotation
                    plt.annotate(f"{trade['exit_price']:.2f}", 
                               xy=(trade['exit_time'], trade['exit_price']),
                               xytext=(5, 10),
                               textcoords='offset points',
                               fontsize=9,
                               bbox=dict(boxstyle="round,pad=0.3", fc=entry_color, alpha=0.3))
                    
                    # Connect entry and exit with a line
                    plt.plot([trade['entry_time'], trade['exit_time']], 
                           [trade['entry_price'], trade['exit_price']], 
                           color=entry_color, linestyle='-', alpha=0.5)
                
                plt.legend()
                plt.tight_layout()
                plt.savefig(trade_chart_file)
                plt.close()
                logging.info(f"Saved detailed trade chart to {trade_chart_file}")
            except Exception as e:
                logging.error(f"Error creating detailed trade chart: {e}")
        
        # Return statistics (with a fallback if calculate_statistics doesn't exist)
        try:
            if hasattr(bt, 'calculate_statistics') and callable(getattr(bt, 'calculate_statistics')):
                stats = bt.calculate_statistics()
            else:
                # Implement a basic statistics calculation if the method doesn't exist
                stats = {}
                
                # Basic stats
                stats['total_trades'] = len(bt.trades) if hasattr(bt, 'trades') else 0
                
                # Win rate
                if hasattr(bt, 'trades') and bt.trades:
                    winning_trades = [t for t in bt.trades if t['pnl'] > 0]
                    stats['win_rate'] = (len(winning_trades) / len(bt.trades) * 100) if bt.trades else 0
                else:
                    stats['win_rate'] = 0
                
                # Total return
                if hasattr(bt, 'equity') and len(bt.equity) > 1:
                    stats['total_return'] = ((bt.equity[-1] - bt.equity[0]) / bt.equity[0]) * 100
                else:
                    stats['total_return'] = 0
                
                # Sharpe ratio (simplified)
                if hasattr(bt, 'equity') and len(bt.equity) > 1:
                    equity_series = pd.Series(bt.equity)
                    daily_returns = equity_series.pct_change().dropna()
                    stats['sharpe_ratio'] = (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5) if len(daily_returns) > 0 and daily_returns.std() > 0 else 0
                else:
                    stats['sharpe_ratio'] = 0
                
                # Max drawdown
                if hasattr(bt, 'equity') and len(bt.equity) > 1:
                    equity_series = pd.Series(bt.equity)
                    running_max = equity_series.cummax()
                    drawdown = (running_max - equity_series) / running_max * 100
                    stats['max_drawdown'] = drawdown.max() if not drawdown.empty else 0
                else:
                    stats['max_drawdown'] = 0
                
                # Average trade duration
                if hasattr(bt, 'trades') and bt.trades:
                    durations = []
                    for trade in bt.trades:
                        if 'duration' in trade:
                            durations.append(trade['duration'])
                        elif 'entry_time' in trade and 'exit_time' in trade:
                            # Calculate duration in minutes if not available
                            duration = (trade['exit_time'] - trade['entry_time']).total_seconds() / 60
                            durations.append(duration)
                    stats['avg_trade_duration'] = sum(durations) / len(durations) if durations else 0
                else:
                    stats['avg_trade_duration'] = 0
                
                # Profit factor
                if hasattr(bt, 'trades') and bt.trades:
                    gross_profit = sum(t['pnl'] for t in bt.trades if t['pnl'] > 0)
                    gross_loss = sum(abs(t['pnl']) for t in bt.trades if t['pnl'] < 0)
                    stats['profit_factor'] = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                else:
                    stats['profit_factor'] = 0
            
            # Add common stats regardless of calculation method
            stats['symbol'] = symbol
            stats['timeframe'] = timeframe
            stats['timestamp'] = timestamp
            
            return stats
        except Exception as e:
            logging.error(f"Error calculating statistics: {e}")
            # Return basic stats in case of error
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'timestamp': timestamp,
                'total_trades': len(bt.trades) if hasattr(bt, 'trades') else 0,
                'win_rate': 0,
                'total_return': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'avg_trade_duration': 0,
                'profit_factor': 0
            }
    except Exception as e:
        logging.error(f"Error processing {symbol} ({timeframe}): {e}")
        return None

async def batch_backtest(config):
    """
    Run batch backtesting for multiple symbols and timeframes,
    including grid search for TP, SL, and Leverage.
    
    Args:
        config: Dictionary containing configuration parameters
    """
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Initialize exchange
    exchange = ccxt.bybit(exchange_config)
    await exchange.load_markets()
    
    try:
        # Get top symbols by volume
        logging.info(f"Getting top {config['top_symbols_limit']} symbols by volume")
        symbols = await get_top_symbols_by_volume(exchange, config['top_symbols_limit'])
        logging.info(f"Top symbols: {', '.join(symbols)}")
        
        # Initialize results list and counters
        results = []
        successful_tests = 0
        failed_tests = 0
        
        # Grid search loops
        for tp_val in config['tp_values']:
            for sl_val in config['sl_values']:
                for leverage_val in config['leverage_values']:
                    logging.info(f"Running grid search for TP: {tp_val}%, SL: {sl_val}%, Leverage: {leverage_val}x")
                    
                    # Process each symbol and timeframe
                    for symbol in symbols:
                        logging.info(f"Processing symbol: {symbol}")
                        for timeframe in config['timeframes']:
                            logging.info(f"Processing timeframe: {timeframe}")
                            
                            # Create a temporary config for the current iteration
                            current_iteration_config = {
                                'initial_balance': config['initial_balance'],
                                'take_profit_pct': tp_val,
                                'stop_loss_pct': sl_val,
                                'position_size_pct': config['position_size_pct'],
                                'max_bars_in_trade': config['max_bars_in_trade'],
                                'leverage': leverage_val
                            }
                            
                            stats = await process_symbol_timeframe(exchange, symbol, timeframe, current_iteration_config)
                            
                            if stats is not None:
                                # Add grid search parameters to stats
                                stats['take_profit_pct'] = tp_val
                                stats['stop_loss_pct'] = sl_val
                                stats['leverage'] = leverage_val
                                results.append(stats)
                                successful_tests += 1
                            else:
                                failed_tests += 1
        
        # Save summary CSV
        if results:
            df = pd.DataFrame(results)
            df.to_csv(SUMMARY_FILE, index=False)
            logging.info(f"Saved summary to {SUMMARY_FILE}")
            
            # Print summary report
            print("\n" + "="*80)
            print(f"BATCH BACKTEST SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*80)
            print(f"Symbols tested: {len(symbols)}")
            print(f"Timeframes tested: {', '.join(config['timeframes'])}")
            print(f"Total combinations (symbols*timeframes*TP*SL*Leverage): {successful_tests + failed_tests}")
            print(f"Successful tests: {successful_tests}")
            print(f"Failed tests: {failed_tests}")
            print("-"*80)
            print("Top 3 performing combinations (by total return):")
            
            # Sort by total_return and print top 3
            top_performers = sorted(results, key=lambda x: x['total_return'], reverse=True)[:3]
            for i, stats in enumerate(top_performers, 1):
                print(f"{i}. {stats['symbol']} ({stats['timeframe']}) - TP: {stats['take_profit_pct']}%, SL: {stats['stop_loss_pct']}%, Leva: {stats['leverage']}x: {stats['total_return']:.2f}% return, {stats['win_rate']:.2f}% win rate")
            
            print("\nWorst 3 performing combinations (by total return):")
            worst_performers = sorted(results, key=lambda x: x['total_return'])[:3]
            for i, stats in enumerate(worst_performers, 1):
                print(f"{i}. {stats['symbol']} ({stats['timeframe']}) - TP: {stats['take_profit_pct']}%, SL: {stats['stop_loss_pct']}%, Leva: {stats['leverage']}x: {stats['total_return']:.2f}% return, {stats['win_rate']:.2f}% win rate")
            
            print("-"*80)
            print(f"Full results saved to: {SUMMARY_FILE}")
            print("="*80)
    except Exception as e:
        logging.error(f"Error during batch backtest: {e}")
    finally:
        # Close the exchange
        await exchange.close()
        logging.info("Batch backtest completed")

def parse_arguments():
    """
    Parse command line arguments
    
    Returns:
        dict: Dictionary containing parsed arguments
    """
    parser = argparse.ArgumentParser(description='Run batch backtests on multiple symbols and timeframes')
    
    parser.add_argument('--limit', type=int, default=TOP_SYMBOLS_LIMIT,
                        help=f'Number of top symbols to test (default: {TOP_SYMBOLS_LIMIT})')
    
    parser.add_argument('--timeframes', type=str, default=','.join(ENABLED_TIMEFRAMES) if ENABLED_TIMEFRAMES else '1h',
                        help=f'Comma-separated list of timeframes to test (default: {",".join(ENABLED_TIMEFRAMES) if ENABLED_TIMEFRAMES else "1h"})')
    
    parser.add_argument('--balance', type=float, default=DEFAULT_INITIAL_BALANCE,
                        help=f'Initial balance for backtesting (default: {DEFAULT_INITIAL_BALANCE})')
    
    parser.add_argument('--tp', type=float, default=DEFAULT_TAKE_PROFIT_PCT,
                        help=f'Take profit percentage (default: {DEFAULT_TAKE_PROFIT_PCT}). Use with --tp-range for grid search.')
    
    parser.add_argument('--sl', type=float, default=DEFAULT_STOP_LOSS_PCT,
                        help=f'Stop loss percentage (default: {DEFAULT_STOP_LOSS_PCT}). Use with --sl-range for grid search.')
    
    parser.add_argument('--size', type=float, default=DEFAULT_POSITION_SIZE_PCT,
                        help=f'Position size percentage (default: {DEFAULT_POSITION_SIZE_PCT})')
    
    parser.add_argument('--max-bars', type=int, default=DEFAULT_MAX_BARS_IN_TRADE,
                        help=f'Maximum number of bars to stay in a trade (default: {DEFAULT_MAX_BARS_IN_TRADE})')
    
    parser.add_argument('--leverage', type=float, default=DEFAULT_LEVERAGE,
                        help=f'Leverage factor (default: {DEFAULT_LEVERAGE}). Use with --leverage-range for grid search.')

    # Grid search arguments
    parser.add_argument('--tp-range', type=str, 
                        help='TP range for grid search (e.g., "0.5:2.0:0.1" for start:end:step)')
    parser.add_argument('--sl-range', type=str,
                        help='SL range for grid search (e.g., "0.5:2.0:0.1" for start:end:step)')
    parser.add_argument('--leverage-range', type=str,
                        help='Leverage range for grid search (e.g., "1:10:1" for start:end:step)')
    
    args = parser.parse_args()
    
    # Process timeframes
    timeframes = [tf.strip() for tf in args.timeframes.split(',') if tf.strip()]

    # Process ranges for grid search
    def parse_range(range_str, default_value):
        if range_str:
            parts = [float(p) for p in range_str.split(':')]
            if len(parts) == 3:
                return np.arange(parts[0], parts[1] + parts[2]/2, parts[2]).tolist()
            else:
                raise ValueError(f"Invalid range format: {range_str}. Expected 'start:end:step'")
        return [default_value]

    tp_values = parse_range(args.tp_range, args.tp)
    sl_values = parse_range(args.sl_range, args.sl)
    leverage_values = parse_range(args.leverage_range, args.leverage)
    
    config = {
        'top_symbols_limit': args.limit,
        'timeframes': timeframes,
        'initial_balance': args.balance,
        'position_size_pct': args.size,
        'max_bars_in_trade': args.max_bars,
        'tp_values': tp_values,
        'sl_values': sl_values,
        'leverage_values': leverage_values
    }
    
    return config

async def main():
    """
    Main entry point
    """
    # Parse command line arguments
    config = parse_arguments()
    
    # Print configuration
    print("\n" + "="*80)
    print("BATCH BACKTEST CONFIGURATION")
    print("="*80)
    print(f"Top symbols limit: {config['top_symbols_limit']}")
    print(f"Timeframes: {', '.join(config['timeframes'])}")
    print(f"Initial balance: {config['initial_balance']}")
    print(f"Take profit values: {config['tp_values']}")
    print(f"Stop loss values: {config['sl_values']}")
    print(f"Position size: {config['position_size_pct']}%")
    print(f"Max bars in trade: {config['max_bars_in_trade']}")
    print(f"Leverage values: {config['leverage_values']}")
    print("="*80 + "\n")
    
    # Run batch backtest
    await batch_backtest(config)

if __name__ == "__main__":
    # Add immediate console output
    print("\n" + "="*80)
    print("STARTING BATCH BACKTEST")
    print("="*80)
    
    import asyncio

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    config = {
        "top_symbols_limit": 5,
        "initial_balance": 1000.0,
        "tp_values": [0.5, 1.0, 1.5],
        "sl_values": [0.5, 1.0, 1.5],
        "leverage_values": [10.0],
        "position_size_pct": 10.0,
        "max_bars_in_trade": 3,
        "timeframes": ["15m", "30m", "1h"]
    }
    
    # Print configuration immediately for visibility
    print(f"Configuration: {config}")
    print("Loading...\n")
    
    # Update TIMEFRAME_DEFAULT based on the selected timeframes in config, if needed
    if config["timeframes"]:
        global_config.TIMEFRAME_DEFAULT = config["timeframes"][0]

    try:
        # Actually run the main function
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBatch backtest interrotto dall'utente.")
        sys.exit(0)
    except Exception as e:
        print(f"\nErrore durante il backtest: {e}")
        sys.exit(1)
