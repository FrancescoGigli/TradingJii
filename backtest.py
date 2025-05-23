#!/usr/bin/env python3
"""
backtest.py

Module for backtesting trading strategies against historical data:
- Loads historical price data
- Applies trading signals and strategy rules
- Simulates trades with configurable parameters
- Calculates performance metrics
- Generates visualization and analysis
"""

import os
import sys
import pandas as pd
import numpy as np
import logging
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path

# Set non-interactive matplotlib backend
import matplotlib
matplotlib.use('Agg')

# Local imports
import config
from data_utils import prepare_data
from predictor import Predictor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class Backtest:
    """
    Backtest class for simulating trading strategies on historical data
    """
    def __init__(
        self,
        symbol,
        timeframes=None,
        initial_balance=1000.0,
        take_profit_pct=1.0,
        stop_loss_pct=1.0,
        position_size_pct=10.0,
        max_bars_in_trade=3,
        leverage=1.0,
        model_type="lstm"  # Options: lstm, rf, xgb
    ):
        """
        Initialize the backtest environment
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframes: List of timeframes to use (e.g., ['15m', '1h'])
            initial_balance: Starting account balance
            take_profit_pct: Take profit percentage
            stop_loss_pct: Stop loss percentage
            position_size_pct: Position size as percentage of balance
            max_bars_in_trade: Maximum number of bars to stay in a trade
            leverage: Leverage multiplier for positions
            model_type: Type of model to use for predictions
        """
        self.symbol = symbol
        self.timeframes = timeframes if timeframes else [config.TIMEFRAME_DEFAULT]
        self.initial_balance = initial_balance
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.position_size_pct = position_size_pct
        self.max_bars_in_trade = max_bars_in_trade
        self.leverage = leverage
        self.model_type = model_type
        
        # State variables
        self.balance = initial_balance
        self.equity = [initial_balance]
        self.trades = []
        self.dataframes = {}
        self.predictors = {}
        
        # Performance metrics
        self.metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0,
            'return_pct': 0.0,
        }

    async def load_data_from_async(self, exchange):
        """
        Load historical data using the exchange instance
        
        Args:
            exchange: ccxt exchange instance
            
        Returns:
            bool: True if data loaded successfully, False otherwise
        """
        from fetcher import fetch_and_save_data
        
        success = True
        for tf in self.timeframes:
            try:
                logging.info(f"Loading data for {self.symbol} ({tf})")
                
                # Fetch data from exchange
                df = await fetch_and_save_data(
                    exchange, 
                    self.symbol, 
                    tf, 
                    save_to_db=False
                )
                
                if df is None or len(df) < 100:  # Ensure enough data
                    logging.error(f"Insufficient data for {self.symbol} ({tf})")
                    success = False
                    continue
                
                # Apply indicators using prepare_data
                data = prepare_data(df)
                
                # Create predictor
                predictor = Predictor(self.model_type, tf)
                self.predictors[tf] = predictor
                
                # Add signals to dataframe
                df['signal'] = predictor.predict(data)
                
                # Convert to datetime index if it's not already
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                
                # Store dataframe
                self.dataframes[tf] = df
                logging.info(f"Loaded {len(df)} candles for {self.symbol} ({tf})")
                
            except Exception as e:
                logging.error(f"Error loading data for {self.symbol} ({tf}): {e}")
                success = False
        
        return success

    def run(self):
        """
        Run the backtest simulation
        """
        if not self.dataframes:
            logging.error("No data loaded for backtesting")
            return
        
        # Use the first timeframe as the primary one
        primary_tf = self.timeframes[0]
        df = self.dataframes[primary_tf]
        
        # Reset state variables
        self.balance = self.initial_balance
        self.equity = [self.initial_balance]
        self.trades = []
        
        # Backtest variables
        in_position = False
        entry_price = 0.0
        entry_time = None
        entry_idx = 0
        bars_in_trade = 0
        
        # Loop through each bar
        for i in range(1, len(df)):
            current_time = df.index[i]
            current_price = df['close'].iloc[i]
            current_signal = df['signal'].iloc[i]
            
            # Update equity
            if in_position:
                # Calculate unrealized PnL
                price_change_pct = (current_price - entry_price) / entry_price * 100
                if df['signal'].iloc[entry_idx] == 1:  # Long position
                    unrealized_pnl = self.balance * (self.position_size_pct / 100) * (price_change_pct / 100) * self.leverage
                else:  # Short position
                    unrealized_pnl = self.balance * (self.position_size_pct / 100) * (-price_change_pct / 100) * self.leverage
                
                current_equity = self.balance + unrealized_pnl
            else:
                current_equity = self.balance
            
            self.equity.append(current_equity)
            
            # Position management
            if in_position:
                bars_in_trade += 1
                price_change_pct = (current_price - entry_price) / entry_price * 100
                
                # Check exit conditions
                exit_signal = False
                exit_reason = None
                
                # Take profit
                if (df['signal'].iloc[entry_idx] == 1 and price_change_pct >= self.take_profit_pct) or \
                   (df['signal'].iloc[entry_idx] == 0 and price_change_pct <= -self.take_profit_pct):
                    exit_signal = True
                    exit_reason = "Take Profit"
                
                # Stop loss
                elif (df['signal'].iloc[entry_idx] == 1 and price_change_pct <= -self.stop_loss_pct) or \
                     (df['signal'].iloc[entry_idx] == 0 and price_change_pct >= self.stop_loss_pct):
                    exit_signal = True
                    exit_reason = "Stop Loss"
                
                # Max bars in trade
                elif bars_in_trade >= self.max_bars_in_trade:
                    exit_signal = True
                    exit_reason = "Max Bars"
                
                # Reverse signal
                elif (df['signal'].iloc[entry_idx] == 1 and current_signal == 0) or \
                     (df['signal'].iloc[entry_idx] == 0 and current_signal == 1):
                    exit_signal = True
                    exit_reason = "Reverse Signal"
                
                # Exit position if conditions met
                if exit_signal:
                    # Calculate P&L
                    if df['signal'].iloc[entry_idx] == 1:  # Long position
                        pnl = self.balance * (self.position_size_pct / 100) * (price_change_pct / 100) * self.leverage
                        pnl_pct = price_change_pct * self.leverage
                    else:  # Short position
                        pnl = self.balance * (self.position_size_pct / 100) * (-price_change_pct / 100) * self.leverage
                        pnl_pct = -price_change_pct * self.leverage
                    
                    # Update balance
                    self.balance += pnl
                    
                    # Record trade
                    trade = {
                        'symbol': self.symbol,
                        'timeframe': primary_tf,
                        'side': 'BUY' if df['signal'].iloc[entry_idx] == 1 else 'SELL',
                        'entry_time': entry_time,
                        'entry_price': entry_price,
                        'exit_time': current_time,
                        'exit_price': current_price,
                        'exit_reason': exit_reason,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'duration': bars_in_trade
                    }
                    self.trades.append(trade)
                    
                    # Reset position flags
                    in_position = False
                    bars_in_trade = 0
            
            # Entry logic - only enter if not already in a position
            elif current_signal in [0, 1]:  # 0=SELL, 1=BUY
                in_position = True
                entry_price = current_price
                entry_time = current_time
                entry_idx = i
                bars_in_trade = 0
        
        # Calculate and store metrics
        self.calculate_statistics()

    def calculate_statistics(self):
        """
        Calculate performance statistics
        
        Returns:
            dict: Dictionary of performance metrics
        """
        if not self.trades:
            logging.warning("No trades executed during backtest")
            stats = {
                'symbol': self.symbol,
                'timeframe': self.timeframes[0],
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'total_return': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'avg_trade_duration': 0
            }
            return stats
        
        # Basic counting metrics
        total_trades = len(self.trades)
        winning_trades = len([t for t in self.trades if t['pnl'] > 0])
        losing_trades = len([t for t in self.trades if t['pnl'] <= 0])
        
        # Win rate
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Profit metrics
        gross_profit = sum([t['pnl'] for t in self.trades if t['pnl'] > 0])
        gross_loss = sum([abs(t['pnl']) for t in self.trades if t['pnl'] <= 0])
        net_profit = sum([t['pnl'] for t in self.trades])
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Return metrics
        total_return = ((self.balance - self.initial_balance) / self.initial_balance) * 100
        
        # Risk metrics
        if len(self.equity) > 1:
            equity_series = pd.Series(self.equity)
            max_equity = equity_series.cummax()
            drawdowns = (max_equity - equity_series) / max_equity * 100
            max_drawdown = drawdowns.max()
        else:
            max_drawdown = 0
        
        # Time metrics
        avg_trade_duration = sum([t['duration'] for t in self.trades]) / total_trades if total_trades > 0 else 0
        
        # Sharpe ratio (simplified)
        if len(self.equity) > 1:
            equity_series = pd.Series(self.equity)
            daily_returns = equity_series.pct_change().dropna()
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5) if daily_returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Store and return metrics
        stats = {
            'symbol': self.symbol,
            'timeframe': self.timeframes[0],
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'avg_trade_duration': avg_trade_duration
        }
        
        self.metrics = stats
        return stats

    def plot_results(self, save_path=None):
        """
        Plot backtest results
        
        Args:
            save_path: Optional path to save the plot
        """
        if not self.trades or len(self.equity) <= 1:
            logging.warning("No trades to plot")
            return
        
        plt.figure(figsize=(12, 10))
        
        # Plot equity curve
        plt.subplot(2, 1, 1)
        plt.plot(self.equity, label='Equity')
        plt.title(f'Backtest Results - {self.symbol} ({self.timeframes[0]})')
        plt.ylabel('Portfolio Value')
        plt.grid(True)
        plt.legend()
        
        # Plot drawdown
        plt.subplot(2, 1, 2)
        equity_series = pd.Series(self.equity)
        running_max = equity_series.cummax()
        drawdown = (running_max - equity_series) / running_max * 100
        plt.fill_between(range(len(drawdown)), 0, drawdown, color='red', alpha=0.3)
        plt.title('Drawdown %')
        plt.xlabel('Bars')
        plt.ylabel('Drawdown %')
        plt.grid(True)
        
        plt.tight_layout()
        
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            plt.savefig(save_path)
            plt.close()
        else:
            plt.show()

# Function for running a simple backtest from command line
async def run_backtest_cli():
    """
    Command-line interface for running a backtest
    """
    import argparse
    import ccxt.async_support as ccxt
    
    parser = argparse.ArgumentParser(description='Run a backtest')
    parser.add_argument('--symbol', type=str, default='BTC/USDT:USDT', help='Trading pair')
    parser.add_argument('--timeframe', type=str, default='1h', help='Timeframe')
    parser.add_argument('--balance', type=float, default=1000.0, help='Initial balance')
    parser.add_argument('--tp', type=float, default=1.0, help='Take profit percentage')
    parser.add_argument('--sl', type=float, default=1.0, help='Stop loss percentage')
    parser.add_argument('--size', type=float, default=10.0, help='Position size percentage')
    parser.add_argument('--max-bars', type=int, default=3, help='Max bars in trade')
    parser.add_argument('--leverage', type=float, default=1.0, help='Leverage multiplier')
    parser.add_argument('--model', type=str, default='lstm', choices=['lstm', 'rf', 'xgb'], help='Model type')
    
    args = parser.parse_args()
    
    # Create and configure exchange
    exchange = ccxt.bybit(config.exchange_config)
    
    try:
        # Create backtest instance
        bt = Backtest(
            symbol=args.symbol,
            timeframes=[args.timeframe],
            initial_balance=args.balance,
            take_profit_pct=args.tp,
            stop_loss_pct=args.sl,
            position_size_pct=args.size,
            max_bars_in_trade=args.max_bars,
            leverage=args.leverage,
            model_type=args.model
        )
        
        # Load data
        await exchange.load_markets()
        data_loaded = await bt.load_data_from_async(exchange)
        
        if not data_loaded:
            logging.error(f"Failed to load data for {args.symbol}")
            return
        
        # Run backtest
        bt.run()
        
        # Display results
        stats = bt.calculate_statistics()
        
        print("\n" + "="*80)
        print(f"BACKTEST RESULTS - {args.symbol} ({args.timeframe})")
        print("="*80)
        print(f"Total trades: {stats['total_trades']}")
        print(f"Win rate: {stats['win_rate']:.2f}%")
        print(f"Profit factor: {stats['profit_factor']:.2f}")
        print(f"Total return: {stats['total_return']:.2f}%")
        print(f"Max drawdown: {stats['max_drawdown']:.2f}%")
        print(f"Sharpe ratio: {stats['sharpe_ratio']:.2f}")
        print("="*80)
        
        # Plot results
        output_dir = Path("logs/backtest")
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        safe_symbol = args.symbol.replace('/', '_').replace(':USDT', '')
        bt.plot_results(save_path=output_dir / f"backtest_{safe_symbol}_{args.timeframe}_{timestamp}.png")
        
    finally:
        await exchange.close()

if __name__ == "__main__":
    import asyncio
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(run_backtest_cli())
