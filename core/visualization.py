"""
Visualization and Backtesting Module for Trading Bot

FEATURES:
- Training metrics visualization (confusion matrix, feature importance, etc.)
- Backtesting with signal analysis
- Performance plots and statistics
- Automatic saving of charts as images
- Text reports for backtesting results
"""

import os
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Set matplotlib backend for headless operation
import matplotlib
matplotlib.use('Agg')

class TradingVisualizer:
    """
    Comprehensive visualization system for trading bot analysis
    """
    
    def __init__(self):
        self.output_dir = "visualizations"
        self._ensure_output_dir()
        
        # Set style
        plt.style.use('dark_background')
        sns.set_palette("husl")
        
        logging.info("📊 Trading Visualizer initialized")
    
    def _ensure_output_dir(self):
        """Create output directory for visualizations"""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(f"{self.output_dir}/training", exist_ok=True)
        os.makedirs(f"{self.output_dir}/backtests", exist_ok=True)
        os.makedirs(f"{self.output_dir}/reports", exist_ok=True)
    
    def plot_training_metrics(self, 
                            y_true: np.ndarray, 
                            y_pred: np.ndarray, 
                            y_prob: np.ndarray,
                            feature_importance: np.ndarray,
                            feature_names: List[str],
                            timeframe: str,
                            metrics: Dict) -> str:
        """
        Create comprehensive training visualization
        
        Returns: path to saved image
        """
        try:
            fig, axes = plt.subplots(2, 3, figsize=(20, 12))
            fig.suptitle(f'XGBoost Training Results - {timeframe}', fontsize=16, color='white')
            
            # 1. Confusion Matrix
            from sklearn.metrics import confusion_matrix
            cm = confusion_matrix(y_true, y_pred)
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                       xticklabels=['SELL', 'BUY', 'NEUTRAL'],
                       yticklabels=['SELL', 'BUY', 'NEUTRAL'],
                       ax=axes[0,0])
            axes[0,0].set_title('Confusion Matrix', color='white')
            axes[0,0].set_xlabel('Predicted', color='white')
            axes[0,0].set_ylabel('Actual', color='white')
            
            # 2. Class Distribution
            unique, counts = np.unique(y_true, return_counts=True)
            class_names = ['SELL', 'BUY', 'NEUTRAL']
            colors = ['#ff4444', '#44ff44', '#4444ff']
            bars = axes[0,1].bar([class_names[i] for i in unique], counts, color=colors)
            axes[0,1].set_title('Class Distribution', color='white')
            axes[0,1].set_ylabel('Count', color='white')
            
            # Add count labels on bars
            for bar, count in zip(bars, counts):
                axes[0,1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50,
                              str(count), ha='center', va='bottom', color='white')
            
            # 3. Feature Importance (Top 15)
            if len(feature_importance) > 0 and len(feature_names) > 0:
                top_n = min(15, len(feature_importance))
                top_idx = np.argsort(feature_importance)[-top_n:]
                top_features = [feature_names[i] if i < len(feature_names) else f'Feature_{i}' 
                              for i in top_idx]
                top_importance = feature_importance[top_idx]
                
                y_pos = np.arange(len(top_features))
                axes[0,2].barh(y_pos, top_importance, color='skyblue')
                axes[0,2].set_yticks(y_pos)
                axes[0,2].set_yticklabels(top_features, fontsize=8, color='white')
                axes[0,2].set_title('Top Feature Importance', color='white')
                axes[0,2].set_xlabel('Importance', color='white')
            
            # 4. Prediction Probabilities Distribution
            if y_prob is not None and len(y_prob.shape) > 1:
                for class_idx in range(y_prob.shape[1]):
                    class_probs = y_prob[:, class_idx]
                    axes[1,0].hist(class_probs, alpha=0.7, bins=30, 
                                  label=class_names[class_idx], color=colors[class_idx])
                axes[1,0].set_title('Prediction Confidence Distribution', color='white')
                axes[1,0].set_xlabel('Probability', color='white')
                axes[1,0].set_ylabel('Count', color='white')
                axes[1,0].legend()
            
            # 5. Performance Metrics
            metrics_text = []
            metrics_text.append(f"Accuracy: {metrics.get('val_accuracy', 0):.3f}")
            metrics_text.append(f"Precision: {metrics.get('val_precision', 0):.3f}")
            metrics_text.append(f"Recall: {metrics.get('val_recall', 0):.3f}")
            metrics_text.append(f"F1-Score: {metrics.get('val_f1', 0):.3f}")
            metrics_text.append(f"CV Mean: {metrics.get('cv_mean_accuracy', 0):.3f}")
            metrics_text.append(f"CV Std: {metrics.get('cv_std_accuracy', 0):.3f}")
            
            axes[1,1].text(0.1, 0.9, '\n'.join(metrics_text), 
                          transform=axes[1,1].transAxes, fontsize=12,
                          verticalalignment='top', color='white',
                          bbox=dict(boxstyle='round', facecolor='navy', alpha=0.8))
            axes[1,1].set_title('Performance Metrics', color='white')
            axes[1,1].axis('off')
            
            # 6. Classification Report Heatmap
            from sklearn.metrics import classification_report
            report = classification_report(y_true, y_pred, 
                                         target_names=class_names,
                                         output_dict=True, zero_division=0)
            
            # Extract metrics for heatmap
            metrics_matrix = []
            metric_names = ['precision', 'recall', 'f1-score']
            for metric in metric_names:
                row = [report[class_name][metric] for class_name in class_names]
                metrics_matrix.append(row)
            
            sns.heatmap(metrics_matrix, annot=True, fmt='.3f', cmap='RdYlGn',
                       xticklabels=class_names, yticklabels=metric_names,
                       ax=axes[1,2], vmin=0, vmax=1)
            axes[1,2].set_title('Classification Report Heatmap', color='white')
            
            plt.tight_layout()
            
            # Save image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"training_metrics_{timeframe}_{timestamp}.png"
            filepath = os.path.join(self.output_dir, "training", filename)
            
            plt.savefig(filepath, dpi=300, bbox_inches='tight', 
                       facecolor='black', edgecolor='none')
            plt.close()
            
            logging.info(f"📊 Training metrics saved: {filepath}")
            return filepath
            
        except Exception as e:
            logging.error(f"Error creating training visualization: {e}")
            return None
    
    def run_backtest(self, 
                    symbol: str,
                    df: pd.DataFrame, 
                    predictions: np.ndarray,
                    timeframe: str,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> Dict:
        """
        Run comprehensive backtest and create visualization with text reports
        
        Returns: backtest results dictionary
        """
        try:
            logging.info(f"🔄 Running enhanced backtest for {symbol} [{timeframe}]")
            
            # Prepare data
            if start_date:
                df = df[df.index >= start_date]
            if end_date:
                df = df[df.index <= end_date]
            
            # Ensure we have predictions for the data
            min_len = min(len(df), len(predictions))
            df = df.iloc[-min_len:]
            predictions = predictions[-min_len:]
            
            # Initialize backtest variables with enhanced tracking
            initial_balance = 10000  # $10k starting capital
            balance = initial_balance
            position = 0  # 0=no position, 1=long, -1=short
            entry_price = 0
            trades = []
            equity_curve = [initial_balance]
            drawdowns = []
            daily_returns = []
            
            # Enhanced signal accuracy tracking
            signal_accuracy = {'correct': 0, 'total': 0}
            
            # Run enhanced simulation
            for i in range(1, len(df)):
                current_price = df.iloc[i]['close']
                signal = predictions[i]
                prev_balance = balance
                
                # Calculate daily return if 24h passed
                if i % 96 == 0:  # Roughly daily for 15m timeframe
                    daily_return = (balance - prev_balance) / prev_balance * 100
                    daily_returns.append(daily_return)
                
                # Close existing position if signal changes or take profit/stop loss
                if position != 0:
                    should_close = False
                    exit_reason = ""
                    
                    if (position == 1 and signal == 0) or (position == -1 and signal == 1):
                        should_close = True
                        exit_reason = "Signal Change"
                    
                    # Take profit at 5% or stop loss at 3%
                    if position == 1:  # Long position
                        pnl_current = (current_price - entry_price) / entry_price * 100
                        if pnl_current >= 5.0:
                            should_close = True
                            exit_reason = "Take Profit"
                        elif pnl_current <= -3.0:
                            should_close = True
                            exit_reason = "Stop Loss"
                    else:  # Short position
                        pnl_current = (entry_price - current_price) / entry_price * 100
                        if pnl_current >= 5.0:
                            should_close = True
                            exit_reason = "Take Profit"
                        elif pnl_current <= -3.0:
                            should_close = True
                            exit_reason = "Stop Loss"
                    
                    if should_close:
                        # Close position
                        if position == 1:  # Close long
                            pnl = (current_price - entry_price) / entry_price
                        else:  # Close short
                            pnl = (entry_price - current_price) / entry_price
                        
                        balance *= (1 + pnl * 0.95)  # 5% slippage/fees
                        
                        # Check signal accuracy
                        if (position == 1 and pnl > 0) or (position == -1 and pnl > 0):
                            signal_accuracy['correct'] += 1
                        signal_accuracy['total'] += 1
                        
                        trades.append({
                            'entry_time': df.index[entry_idx],
                            'exit_time': df.index[i],
                            'side': 'LONG' if position == 1 else 'SHORT',
                            'entry_price': entry_price,
                            'exit_price': current_price,
                            'pnl_pct': pnl * 100,
                            'balance': balance,
                            'exit_reason': exit_reason,
                            'duration_hours': (df.index[i] - df.index[entry_idx]).total_seconds() / 3600
                        })
                        
                        position = 0
                
                # Open new position
                if position == 0:
                    if signal == 1:  # BUY signal
                        position = 1
                        entry_price = current_price
                        entry_idx = i
                    elif signal == 0:  # SELL signal
                        position = -1
                        entry_price = current_price
                        entry_idx = i
                
                equity_curve.append(balance)
                
                # Track drawdown
                peak = max(equity_curve)
                if peak > 0:
                    drawdown = (peak - balance) / peak * 100
                    drawdowns.append(drawdown)
            
            # Calculate enhanced statistics
            if trades:
                returns = [t['pnl_pct'] for t in trades]
                win_trades = [r for r in returns if r > 0]
                lose_trades = [r for r in returns if r <= 0]
                durations = [t['duration_hours'] for t in trades]
                
                # Calculate Sortino ratio
                downside_returns = [r for r in returns if r < 0]
                sortino_ratio = np.mean(returns) / np.std(downside_returns) if downside_returns and np.std(downside_returns) > 0 else 0
                
                total_return_pct = ((balance - initial_balance) / initial_balance) * 100
                max_dd = max(drawdowns) if drawdowns else 0
                
                stats = {
                    'total_return_pct': total_return_pct,
                    'total_trades': len(trades),
                    'win_rate': len(win_trades) / len(trades) * 100 if trades else 0,
                    'signal_accuracy': signal_accuracy['correct'] / signal_accuracy['total'] * 100 if signal_accuracy['total'] > 0 else 0,
                    'avg_return': np.mean(returns) if returns else 0,
                    'avg_win': np.mean(win_trades) if win_trades else 0,
                    'avg_loss': np.mean(lose_trades) if lose_trades else 0,
                    'max_return': max(returns) if returns else 0,
                    'min_return': min(returns) if returns else 0,
                    'sharpe_ratio': np.mean(returns) / np.std(returns) if returns and np.std(returns) > 0 else 0,
                    'sortino_ratio': sortino_ratio,
                    'max_drawdown': max_dd,
                    'avg_trade_duration': np.mean(durations) if durations else 0,
                    'profit_factor': abs(sum(win_trades) / sum(lose_trades)) if lose_trades and sum(lose_trades) != 0 else float('inf') if win_trades else 0,
                    'recovery_factor': abs(total_return_pct / max_dd) if max_dd > 0 else float('inf')
                }
            else:
                stats = {
                    'total_return_pct': 0, 'total_trades': 0, 'win_rate': 0, 'signal_accuracy': 0,
                    'avg_return': 0, 'avg_win': 0, 'avg_loss': 0, 'max_return': 0, 'min_return': 0,
                    'sharpe_ratio': 0, 'sortino_ratio': 0, 'max_drawdown': 0, 'avg_trade_duration': 0,
                    'profit_factor': 0, 'recovery_factor': 0
                }
            
            # Create enhanced visualization chart
            self._plot_backtest_results(symbol, df, predictions, equity_curve, 
                                      trades, stats, timeframe)
            
            # Save enhanced backtest report
            self._save_backtest_report(symbol, timeframe, stats, trades)
            
            logging.info(f"✅ Enhanced backtest completed for {symbol}: {stats['total_return_pct']:.2f}% return, {stats['win_rate']:.1f}% win rate, {stats['signal_accuracy']:.1f}% accuracy")
            
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'stats': stats,
                'trades': trades,
                'equity_curve': equity_curve,
                'drawdowns': drawdowns
            }
            
        except Exception as e:
            logging.error(f"Error in backtest for {symbol}: {e}")
            return {}
    
    def _plot_backtest_results(self, symbol: str, df: pd.DataFrame, predictions: np.ndarray,
                             equity_curve: List[float], trades: List[Dict], 
                             stats: Dict, timeframe: str):
        """Create backtest visualization"""
        try:
            fig, axes = plt.subplots(3, 2, figsize=(20, 15))
            fig.suptitle(f'Backtest Results: {symbol} [{timeframe}]', fontsize=16, color='white')
            
            # 1. Price chart with signals
            price_data = df['close'].values
            dates = df.index
            
            axes[0,0].plot(dates, price_data, color='white', linewidth=1, label='Price')
            
            # Plot signals
            buy_signals = predictions == 1
            sell_signals = predictions == 0
            
            if np.any(buy_signals):
                axes[0,0].scatter(dates[buy_signals], price_data[buy_signals], 
                                color='lime', marker='^', s=50, label='BUY Signal', alpha=0.7)
            if np.any(sell_signals):
                axes[0,0].scatter(dates[sell_signals], price_data[sell_signals], 
                                color='red', marker='v', s=50, label='SELL Signal', alpha=0.7)
            
            axes[0,0].set_title('Price Chart with Signals', color='white')
            axes[0,0].set_ylabel('Price', color='white')
            axes[0,0].legend()
            axes[0,0].grid(True, alpha=0.3)
            
            # 2. Equity Curve
            axes[0,1].plot(range(len(equity_curve)), equity_curve, color='gold', linewidth=2)
            axes[0,1].set_title('Equity Curve', color='white')
            axes[0,1].set_ylabel('Balance ($)', color='white')
            axes[0,1].set_xlabel('Time', color='white')
            axes[0,1].grid(True, alpha=0.3)
            
            # 3. Returns Distribution
            if trades:
                returns = [t['pnl_pct'] for t in trades]
                axes[1,0].hist(returns, bins=20, alpha=0.7, color='skyblue', edgecolor='white')
                axes[1,0].axvline(0, color='red', linestyle='--', alpha=0.7, label='Break Even')
                axes[1,0].set_title('Returns Distribution', color='white')
                axes[1,0].set_xlabel('Return %', color='white')
                axes[1,0].set_ylabel('Frequency', color='white')
                axes[1,0].legend()
                axes[1,0].grid(True, alpha=0.3)
            
            # 4. Performance Statistics
            stats_text = []
            stats_text.append(f"Total Return: {stats['total_return_pct']:.2f}%")
            stats_text.append(f"Total Trades: {stats['total_trades']}")
            stats_text.append(f"Win Rate: {stats['win_rate']:.1f}%")
            stats_text.append(f"Avg Return: {stats['avg_return']:.2f}%")
            stats_text.append(f"Avg Win: {stats['avg_win']:.2f}%")
            stats_text.append(f"Avg Loss: {stats['avg_loss']:.2f}%")
            stats_text.append(f"Best Trade: {stats['max_return']:.2f}%")
            stats_text.append(f"Worst Trade: {stats['min_return']:.2f}%")
            stats_text.append(f"Sharpe Ratio: {stats['sharpe_ratio']:.3f}")
            
            axes[1,1].text(0.1, 0.9, '\n'.join(stats_text), 
                          transform=axes[1,1].transAxes, fontsize=11,
                          verticalalignment='top', color='white',
                          bbox=dict(boxstyle='round', facecolor='navy', alpha=0.8))
            axes[1,1].set_title('Performance Statistics', color='white')
            axes[1,1].axis('off')
            
            # 5. Signal Distribution
            signal_counts = np.bincount(predictions)
            signal_names = ['SELL', 'BUY', 'NEUTRAL']
            colors = ['red', 'lime', 'gray']
            
            valid_signals = [(signal_names[i], signal_counts[i], colors[i]) 
                           for i in range(len(signal_counts)) if i < len(signal_names)]
            
            if valid_signals:
                names, counts, cols = zip(*valid_signals)
                bars = axes[2,0].bar(names, counts, color=cols, alpha=0.7)
                axes[2,0].set_title('Signal Distribution', color='white')
                axes[2,0].set_ylabel('Count', color='white')
                
                for bar, count in zip(bars, counts):
                    axes[2,0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                                  str(count), ha='center', va='bottom', color='white')
            
            # 6. Cumulative Returns
            if trades:
                cumulative_returns = []
                cum_return = 0
                for trade in trades:
                    cum_return += trade['pnl_pct']
                    cumulative_returns.append(cum_return)
                
                axes[2,1].plot(range(len(cumulative_returns)), cumulative_returns, 
                              color='gold', linewidth=2, marker='o', markersize=4)
                axes[2,1].axhline(0, color='red', linestyle='--', alpha=0.7)
                axes[2,1].set_title('Cumulative Returns by Trade', color='white')
                axes[2,1].set_xlabel('Trade Number', color='white')
                axes[2,1].set_ylabel('Cumulative Return %', color='white')
                axes[2,1].grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Save image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Replace problematic characters for Windows
            safe_symbol = symbol.replace('/', '_').replace(':', '_')
            filename = f"backtest_{safe_symbol}_{timeframe}_{timestamp}.png"
            filepath = os.path.join(self.output_dir, "backtests", filename)
            
            plt.savefig(filepath, dpi=300, bbox_inches='tight',
                       facecolor='black', edgecolor='none')
            plt.close()
            
            logging.info(f"📊 Backtest visualization saved: {filepath}")
            
        except Exception as e:
            logging.error(f"Error creating backtest visualization: {e}")

    def _save_backtest_report(self, symbol: str, timeframe: str, stats: Dict, trades: List[Dict]):
        """Save detailed backtest report in text format"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_symbol = symbol.replace('/', '_').replace(':', '_')
            report_filename = f"backtest_report_{safe_symbol}_{timeframe}_{timestamp}.txt"
            report_filepath = os.path.join(self.output_dir, "reports", report_filename)
            
            with open(report_filepath, 'w', encoding='utf-8') as f:
                # Header
                f.write("=" * 100 + "\n")
                f.write(f"📊 BACKTEST REPORT - {symbol} [{timeframe.upper()}]\n")
                f.write("=" * 100 + "\n")
                f.write(f"⏰ Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"🎯 Strategy: Future Returns Labeling with XGBoost ML\n")
                f.write(f"📈 Period: Last 30 days\n")
                f.write("-" * 100 + "\n\n")
                
                # Performance Summary
                f.write("🏆 PERFORMANCE SUMMARY\n")
                f.write("-" * 50 + "\n")
                f.write(f"💰 Total Return:     {stats['total_return_pct']:>10.2f}%\n")
                f.write(f"🎯 Total Trades:     {stats['total_trades']:>10d}\n")
                f.write(f"✅ Win Rate:         {stats['win_rate']:>10.1f}%\n")
                f.write(f"📊 Avg Return:       {stats['avg_return']:>10.2f}%\n")
                f.write(f"📈 Avg Win:          {stats['avg_win']:>10.2f}%\n")
                f.write(f"📉 Avg Loss:         {stats['avg_loss']:>10.2f}%\n")
                f.write(f"🚀 Best Trade:       {stats['max_return']:>10.2f}%\n")
                f.write(f"💥 Worst Trade:      {stats['min_return']:>10.2f}%\n")
                f.write(f"📈 Sharpe Ratio:     {stats['sharpe_ratio']:>10.3f}\n")
                f.write("-" * 50 + "\n\n")
                
                # Risk Analysis
                if trades:
                    returns = [t['pnl_pct'] for t in trades]
                    win_trades = [r for r in returns if r > 0]
                    lose_trades = [r for r in returns if r <= 0]
                    
                    f.write("🛡️ RISK ANALYSIS\n")
                    f.write("-" * 50 + "\n")
                    f.write(f"📊 Max Drawdown:     {min(returns):>10.2f}%\n")
                    f.write(f"📈 Max Gain:         {max(returns):>10.2f}%\n")
                    f.write(f"🎯 Win/Loss Ratio:   {len(win_trades)}/{len(lose_trades)}\n")
                    if lose_trades:
                        profit_factor = abs(sum(win_trades) / sum(lose_trades))
                        f.write(f"💎 Profit Factor:    {profit_factor:>10.2f}\n")
                    else:
                        f.write(f"💎 Profit Factor:    {'N/A':>10}\n")
                    f.write(f"📉 Max Consecutive:  {self._max_consecutive_losses(returns):>10d} losses\n")
                    f.write("-" * 50 + "\n\n")
                
                # Trading Activity
                if trades:
                    f.write("📋 DETAILED TRADE LOG\n")
                    f.write("-" * 100 + "\n")
                    f.write(f"{'#':<4} {'ENTRY TIME':<20} {'EXIT TIME':<20} {'SIDE':<6} {'ENTRY':<10} {'EXIT':<10} {'PnL%':<8} {'BALANCE':<10}\n")
                    f.write("-" * 100 + "\n")
                    
                    for i, trade in enumerate(trades[:20], 1):  # Show first 20 trades
                        entry_time = trade['entry_time'].strftime('%Y-%m-%d %H:%M')
                        exit_time = trade['exit_time'].strftime('%Y-%m-%d %H:%M')
                        side = trade['side']
                        entry_price = trade['entry_price']
                        exit_price = trade['exit_price']
                        pnl = trade['pnl_pct']
                        balance = trade['balance']
                        
                        f.write(f"{i:<4} {entry_time:<20} {exit_time:<20} {side:<6} {entry_price:<10.4f} {exit_price:<10.4f} {pnl:>+7.2f}% ${balance:>8.0f}\n")
                    
                    if len(trades) > 20:
                        f.write(f"\n... and {len(trades) - 20} more trades\n")
                    
                    f.write("-" * 100 + "\n\n")
                
                # Summary and Recommendations
                f.write("💡 ANALYSIS & RECOMMENDATIONS\n")
                f.write("-" * 50 + "\n")
                
                if stats['total_return_pct'] > 0:
                    f.write("✅ PROFITABLE STRATEGY - Strategy shows positive returns\n")
                else:
                    f.write("❌ LOSS-MAKING STRATEGY - Strategy shows negative returns\n")
                
                if stats['win_rate'] > 60:
                    f.write("🎯 HIGH WIN RATE - Good signal accuracy\n")
                elif stats['win_rate'] > 40:
                    f.write("⚠️ MODERATE WIN RATE - Average signal accuracy\n")
                else:
                    f.write("💥 LOW WIN RATE - Poor signal accuracy\n")
                
                if stats['sharpe_ratio'] > 1.0:
                    f.write("📈 EXCELLENT RISK/REWARD - High Sharpe ratio\n")
                elif stats['sharpe_ratio'] > 0.5:
                    f.write("📊 GOOD RISK/REWARD - Decent Sharpe ratio\n")
                else:
                    f.write("📉 POOR RISK/REWARD - Low Sharpe ratio\n")
                
                f.write("-" * 50 + "\n")
                f.write(f"📂 Charts saved: visualizations/backtests/\n")
                f.write(f"📄 Report saved: {report_filepath}\n")
                f.write("=" * 100 + "\n")
            
            logging.info(f"📄 Backtest report saved: {report_filepath}")
            
        except Exception as e:
            logging.error(f"Error saving backtest report: {e}")
    
    def _max_consecutive_losses(self, returns: List[float]) -> int:
        """Calculate maximum consecutive losses"""
        max_consecutive = 0
        current_consecutive = 0
        
        for ret in returns:
            if ret < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive


# Global instance for easy access
visualizer = TradingVisualizer()

def save_training_metrics(y_true, y_pred, y_prob, feature_importance, feature_names, timeframe, metrics):
    """Convenient function to save training metrics"""
    return visualizer.plot_training_metrics(y_true, y_pred, y_prob, feature_importance, 
                                          feature_names, timeframe, metrics)

def run_symbol_backtest(symbol, df, predictions, timeframe, start_date=None, end_date=None):
    """Convenient function to run backtest"""
    return visualizer.run_backtest(symbol, df, predictions, timeframe, start_date, end_date)
