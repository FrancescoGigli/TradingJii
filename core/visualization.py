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
        🚀 REALISTIC BACKTEST USING LIVE TRADING LOGIC (OPTION C)
        
        Uses SAME position management, TP/SL, and tracking as live trading
        for perfect consistency and RL calibration.
        
        Returns: backtest results dictionary
        """
        try:
            logging.info(f"🔄 Running enhanced backtest for {symbol} [{timeframe}]")
            
            # CRITICAL FIX: Ensure backtest uses only closed candles like live trading
            from fetcher import is_candle_closed
            
            # Filter only closed candles for consistency with live trading
            original_length = len(df)
            closed_candles_mask = df.index.to_series().apply(
                lambda ts: is_candle_closed(ts, timeframe)
            )
            df = df[closed_candles_mask]
            
            # Prepare data
            if start_date:
                df = df[df.index >= start_date]
            if end_date:
                df = df[df.index <= end_date]
            
            # Ensure we have predictions for the data
            min_len = min(len(df), len(predictions))
            df = df.iloc[-min_len:]
            predictions = predictions[-min_len:]
            
            # OPTION C: Use SAME position tracker as live trading!
            from core.smart_position_manager import SmartPositionManager as PositionTracker
            from config import BACKTEST_INITIAL_BALANCE, BACKTEST_LEVERAGE, BACKTEST_BASE_RISK_PCT
            
            # Create isolated position tracker for backtest
            backtest_tracker = PositionTracker(storage_file="backtest_positions.json")
            backtest_tracker.session_stats['initial_balance'] = BACKTEST_INITIAL_BALANCE
            backtest_tracker.session_stats['current_balance'] = BACKTEST_INITIAL_BALANCE
            
            logging.info(f"🔄 Backtest config: Balance=${BACKTEST_INITIAL_BALANCE}, Leverage={BACKTEST_LEVERAGE}x, Risk={BACKTEST_BASE_RISK_PCT}%")
            
            # Track each price update exactly like live trading
            all_trades = []
            equity_curve = [BACKTEST_INITIAL_BALANCE]
            
            for i in range(1, len(df)):
                current_candle = df.iloc[i]
                current_price = current_candle['close']
                signal = predictions[i]
                
                # Update existing positions with current price (like live trading)
                current_prices = {symbol: current_price}
                positions_to_close = backtest_tracker.update_positions(current_prices)
                
                # Close positions that hit TP/SL/Trailing (like live trading)
                for position in positions_to_close:
                    backtest_tracker.close_position(
                        position['position_id'],
                        position['exit_price'], 
                        position['exit_reason']
                    )
                    all_trades.append(position)
                
                # Open new position if signal and no existing position for symbol
                existing_position = any(pos['symbol'] == symbol for pos in backtest_tracker.active_positions.values())
                
                if not existing_position and signal in [0, 1]:  # BUY or SELL signal
                    try:
                        # Calculate realistic position size (5% of balance like live)
                        available_balance = backtest_tracker.get_available_balance()
                        position_size = available_balance * 0.05  # Same as live trading
                        
                        if position_size >= 10:  # Minimum position size
                            # Extract ATR for realistic TP/SL calculation
                            atr = current_candle.get('atr', current_price * 0.02)
                            confidence = 0.75  # Default confidence for backtest
                            
                            # Open position using SAME logic as live trading
                            side = "Buy" if signal == 1 else "Sell"
                            position_id = backtest_tracker.open_position(
                                symbol=symbol,
                                side=side,
                                entry_price=current_price,
                                position_size=position_size,
                                leverage=BACKTEST_LEVERAGE,
                                confidence=confidence,
                                atr=atr
                            )
                            
                    except Exception as position_error:
                        logging.warning(f"Error opening backtest position for {symbol}: {position_error}")
                
                # Track equity curve
                current_balance = backtest_tracker.session_stats['current_balance']
                equity_curve.append(current_balance)
            
            # Get final statistics from position tracker (SAME as live trading)
            final_summary = backtest_tracker.get_session_summary()
            
            # Convert to compatible stats format
            total_return_pct = ((final_summary['wallet_balance'] - BACKTEST_INITIAL_BALANCE) / BACKTEST_INITIAL_BALANCE) * 100
            
            stats = {
                'total_return_pct': total_return_pct,
                'total_trades': final_summary['total_trades'],
                'win_rate': final_summary['win_rate'],
                'signal_accuracy': final_summary['win_rate'],  # Approximation
                'avg_return': total_return_pct / max(final_summary['total_trades'], 1),
                'avg_win': 0.0,  # Calculated below
                'avg_loss': 0.0,  # Calculated below
                'max_return': 0.0,  # Calculated below
                'min_return': 0.0,  # Calculated below
                'sharpe_ratio': 0.0,  # Calculated below
                'sortino_ratio': 0.0,
                'max_drawdown': 0.0,  # Calculated below
                'avg_trade_duration': 0.0,
                'profit_factor': 0.0,
                'recovery_factor': 0.0
            }
            
            # Calculate detailed stats from individual trades
            if all_trades:
                returns = [self._get_trade_pnl_pct(t) for t in all_trades]
                returns = [r for r in returns if r is not None]  # Filter None values
                win_trades = [r for r in returns if r > 0]
                lose_trades = [r for r in returns if r <= 0]
                
                if returns:
                    stats['avg_win'] = np.mean(win_trades) if win_trades else 0.0
                    stats['avg_loss'] = np.mean(lose_trades) if lose_trades else 0.0
                    stats['max_return'] = max(returns)
                    stats['min_return'] = min(returns)
                    stats['sharpe_ratio'] = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0.0
                    
                    # Calculate max drawdown from equity curve
                    equity_array = np.array(equity_curve)
                    running_max = np.maximum.accumulate(equity_array)
                    drawdowns = (running_max - equity_array) / running_max * 100
                    stats['max_drawdown'] = np.max(drawdowns) if len(drawdowns) > 0 else 0.0
                    
                    # Profit factor
                    total_wins = sum(win_trades) if win_trades else 0
                    total_losses = abs(sum(lose_trades)) if lose_trades else 1
                    stats['profit_factor'] = total_wins / total_losses if total_losses > 0 else float('inf')
            
            # Use all_trades data for visualization and reports  
            # Create enhanced visualization chart
            self._plot_backtest_results(symbol, df, predictions, equity_curve, 
                                      all_trades, stats, timeframe)
            
            # Save enhanced backtest report
            self._save_backtest_report(symbol, timeframe, stats, all_trades)
            
            logging.info(f"✅ Enhanced backtest completed for {symbol}: {stats['total_return_pct']:.2f}% return, {stats['win_rate']:.1f}% win rate, {stats['signal_accuracy']:.1f}% accuracy")
            
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'stats': stats,
                'trades': all_trades,
                'equity_curve': equity_curve,
                'drawdowns': [0.0] if not all_trades else []  # Placeholder
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
                returns = [self._get_trade_pnl_pct(t) for t in trades]
                returns = [r for r in returns if r is not None]  # Filter None values
                if returns:
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
                    trade_pnl = self._get_trade_pnl_pct(trade)
                    if trade_pnl is not None:
                        cum_return += trade_pnl
                        cumulative_returns.append(cum_return)
                
                if cumulative_returns:
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
                    returns = [self._get_trade_pnl_pct(t) for t in trades]
                    returns = [r for r in returns if r is not None]  # Filter None values
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
                        entry_time = trade.get('entry_time', 'N/A')
                        exit_time = trade.get('exit_time', 'N/A')
                        side = trade.get('side', 'N/A')
                        entry_price = trade.get('entry_price', 0.0)
                        exit_price = trade.get('exit_price', 0.0)
                        pnl = self._get_trade_pnl_pct(trade)
                        balance = trade.get('balance', 0.0)
                        
                        # Format times if they are datetime objects
                        if hasattr(entry_time, 'strftime'):
                            entry_time = entry_time.strftime('%Y-%m-%d %H:%M')
                        if hasattr(exit_time, 'strftime'):
                            exit_time = exit_time.strftime('%Y-%m-%d %H:%M')
                        
                        pnl_str = f"{pnl:>+7.2f}%" if pnl is not None else "N/A"
                        f.write(f"{i:<4} {entry_time:<20} {exit_time:<20} {side:<6} {entry_price:<10.4f} {exit_price:<10.4f} {pnl_str:<8} ${balance:>8.0f}\n")
                    
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
    
    def _get_trade_pnl_pct(self, trade: Dict) -> Optional[float]:
        """
        Safely extract PnL percentage from trade object
        
        Args:
            trade: Trade dictionary from PositionTracker
            
        Returns:
            float or None: PnL percentage if available
        """
        # Try different possible field names
        pnl_fields = ['final_pnl_pct', 'pnl_pct', 'unrealized_pnl_pct']
        
        for field in pnl_fields:
            if field in trade and trade[field] is not None:
                return float(trade[field])
        
        # Calculate PnL from entry/exit prices if available
        entry_price = trade.get('entry_price')
        exit_price = trade.get('exit_price')
        side = trade.get('side', '').upper()
        
        if entry_price and exit_price and side:
            try:
                if side in ['BUY', 'LONG']:
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                elif side in ['SELL', 'SHORT']:
                    pnl_pct = ((entry_price - exit_price) / entry_price) * 100
                else:
                    return None
                    
                return float(pnl_pct)
            except (ValueError, ZeroDivisionError):
                pass
        
        return None
    
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
