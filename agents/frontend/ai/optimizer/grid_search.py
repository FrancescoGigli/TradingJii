"""
🔬 Grid Search Optimizer - Find optimal backtest parameters

Systematically tests all combinations of parameters and ranks them
by performance metrics (Sharpe Ratio, Total Return, Win Rate).
"""

import itertools
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from ..backtest.engine import BacktestEngine
from ..backtest.trades import TradeList
from ..core.config import BACKTEST_CONFIG


@dataclass
class OptimizationResult:
    """Result of a single parameter combination test"""
    params: Dict[str, float]
    total_trades: int
    win_rate: float
    total_return: float
    average_trade: float
    best_trade: float
    worst_trade: float
    sharpe_ratio: float
    max_drawdown: float
    profit_factor: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for display"""
        return {
            'SL %': f"{self.params.get('stop_loss_pct', 0):.1f}",
            'TP %': f"{self.params.get('take_profit_pct', 0):.1f}",
            'Entry': int(self.params.get('entry_threshold', 0)),
            'Trades': self.total_trades,
            'Win %': f"{self.win_rate:.1f}%",
            'Return': f"{self.total_return:+.2f}%",
            'Avg Trade': f"{self.average_trade:+.2f}%",
            'Sharpe': f"{self.sharpe_ratio:.2f}",
            'Max DD': f"{self.max_drawdown:.1f}%",
            'PF': f"{self.profit_factor:.2f}"
        }


@dataclass
class GridSearchResult:
    """Complete grid search results"""
    results: List[OptimizationResult]
    best_by_sharpe: Optional[OptimizationResult] = None
    best_by_return: Optional[OptimizationResult] = None
    best_by_winrate: Optional[OptimizationResult] = None
    total_combinations: int = 0
    execution_time_sec: float = 0.0
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert all results to DataFrame"""
        if not self.results:
            return pd.DataFrame()
        
        data = [r.to_dict() for r in self.results]
        return pd.DataFrame(data)
    
    def get_top_n(self, n: int = 10, sort_by: str = 'sharpe') -> List[OptimizationResult]:
        """Get top N results sorted by metric"""
        if sort_by == 'sharpe':
            return sorted(self.results, key=lambda x: x.sharpe_ratio, reverse=True)[:n]
        elif sort_by == 'return':
            return sorted(self.results, key=lambda x: x.total_return, reverse=True)[:n]
        elif sort_by == 'winrate':
            return sorted(self.results, key=lambda x: x.win_rate, reverse=True)[:n]
        else:
            return self.results[:n]


class GridSearchOptimizer:
    """
    Grid Search Optimizer for backtest parameters.
    
    Tests all combinations of given parameter ranges and finds
    the optimal configuration based on performance metrics.
    """
    
    def __init__(self, base_config: Dict = None):
        self.base_config = base_config or BACKTEST_CONFIG.copy()
    
    def optimize(
        self,
        df: pd.DataFrame,
        param_grid: Dict[str, List[float]],
        progress_callback=None
    ) -> GridSearchResult:
        """
        Run grid search optimization.
        
        Args:
            df: DataFrame with OHLCV data
            param_grid: Dictionary of parameter ranges to test
                Example:
                {
                    'stop_loss_pct': [1.0, 1.5, 2.0, 2.5, 3.0],
                    'take_profit_pct': [2.0, 3.0, 4.0, 5.0, 6.0],
                    'entry_threshold': [20, 25, 30, 35]
                }
            progress_callback: Optional callback(current, total) for progress
            
        Returns:
            GridSearchResult with all tested combinations
        """
        start_time = datetime.now()
        
        # Generate all combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(itertools.product(*param_values))
        total_combinations = len(combinations)
        
        results = []
        
        for i, combo in enumerate(combinations):
            # Create params dict
            params = dict(zip(param_names, combo))
            
            # Update config with these params
            test_config = self.base_config.copy()
            test_config.update(params)
            test_config['use_sl_tp'] = True  # Always enable SL/TP for optimization
            
            # Run backtest
            engine = BacktestEngine(test_config)
            backtest_result = engine.run(
                df,
                entry_threshold=int(params.get('entry_threshold', test_config['entry_threshold'])),
                exit_threshold=int(params.get('exit_threshold', test_config['exit_threshold'])),
                min_holding=int(params.get('min_holding_candles', test_config['min_holding_candles']))
            )
            
            # Calculate metrics
            trades = backtest_result.trades
            metrics = self._calculate_metrics(trades)
            
            # Create result
            opt_result = OptimizationResult(
                params=params,
                total_trades=trades.total_trades,
                win_rate=trades.win_rate,
                total_return=trades.total_return,
                average_trade=trades.average_trade,
                best_trade=trades.best_trade,
                worst_trade=trades.worst_trade,
                sharpe_ratio=metrics['sharpe_ratio'],
                max_drawdown=metrics['max_drawdown'],
                profit_factor=metrics['profit_factor']
            )
            results.append(opt_result)
            
            # Progress callback
            if progress_callback:
                progress_callback(i + 1, total_combinations)
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Find best results
        if results:
            best_sharpe = max(results, key=lambda x: x.sharpe_ratio)
            best_return = max(results, key=lambda x: x.total_return)
            best_winrate = max(results, key=lambda x: x.win_rate)
        else:
            best_sharpe = best_return = best_winrate = None
        
        return GridSearchResult(
            results=results,
            best_by_sharpe=best_sharpe,
            best_by_return=best_return,
            best_by_winrate=best_winrate,
            total_combinations=total_combinations,
            execution_time_sec=execution_time
        )
    
    def _calculate_metrics(self, trades: TradeList) -> Dict[str, float]:
        """Calculate advanced metrics for a trade list"""
        
        if trades.total_trades == 0:
            return {
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'profit_factor': 0.0
            }
        
        # Get trade returns
        returns = [t.pnl_pct for t in trades.closed_trades if t.pnl_pct is not None]
        
        if not returns:
            return {
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'profit_factor': 0.0
            }
        
        # Sharpe Ratio (simplified: mean / std)
        mean_return = np.mean(returns)
        std_return = np.std(returns) if len(returns) > 1 else 1.0
        sharpe_ratio = mean_return / std_return if std_return > 0 else 0.0
        
        # Max Drawdown
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0.0
        
        # Profit Factor (gross profit / gross loss)
        gross_profit = sum(r for r in returns if r > 0)
        gross_loss = abs(sum(r for r in returns if r < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0
        
        return {
            'sharpe_ratio': round(sharpe_ratio, 3),
            'max_drawdown': round(max_drawdown, 2),
            'profit_factor': round(min(profit_factor, 99.99), 2)  # Cap at 99.99
        }
    
    @staticmethod
    def get_default_param_grid() -> Dict[str, List[float]]:
        """Get default parameter grid for optimization"""
        return {
            'stop_loss_pct': [1.0, 1.5, 2.0, 2.5, 3.0],
            'take_profit_pct': [2.0, 3.0, 4.0, 5.0, 6.0, 8.0],
            'entry_threshold': [20, 25, 30, 35, 40]
        }
    
    @staticmethod
    def estimate_combinations(param_grid: Dict[str, List[float]]) -> int:
        """Estimate total number of combinations"""
        total = 1
        for values in param_grid.values():
            total *= len(values)
        return total
