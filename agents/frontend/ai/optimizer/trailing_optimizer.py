"""
🎯 Trailing Stop Optimizer
==========================

Systematically tests all combinations of trailing stop parameters
and finds optimal configurations for live trading.

Features:
- Grid search over SL, TP, Trailing Stop, Activation
- Parallel equity curve generation
- Ranking by multiple metrics (Sharpe, Return, Win Rate)
- Ready-to-use configurations for live trading
"""

import itertools
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime
from enum import Enum

from ..backtest.xgb_simulator import (
    run_xgb_simulation, 
    XGBSimulatorConfig, 
    XGBSimulatorResult
)


class OptimizationMetric(Enum):
    """Metrics to optimize for"""
    SHARPE_RATIO = "sharpe_ratio"
    TOTAL_RETURN = "total_return"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    RISK_ADJUSTED = "risk_adjusted"  # Return / Max Drawdown


@dataclass
class TrailingConfig:
    """Single trailing stop configuration"""
    stop_loss_pct: float
    take_profit_pct: float
    trailing_stop_pct: float
    trailing_activation_pct: float
    entry_threshold: float
    max_holding_candles: int = 50
    
    def to_dict(self) -> Dict:
        return {
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'trailing_stop_pct': self.trailing_stop_pct,
            'trailing_activation_pct': self.trailing_activation_pct,
            'entry_threshold': self.entry_threshold,
            'max_holding_candles': self.max_holding_candles
        }
    
    def to_simulator_config(self) -> XGBSimulatorConfig:
        return XGBSimulatorConfig(
            entry_threshold=self.entry_threshold,
            stop_loss_pct=self.stop_loss_pct,
            take_profit_pct=self.take_profit_pct,
            trailing_stop_pct=self.trailing_stop_pct,
            trailing_activation_pct=self.trailing_activation_pct,
            max_holding_candles=self.max_holding_candles,
            min_holding_candles=2
        )
    
    def get_label(self) -> str:
        """Get short label for charts"""
        return f"SL:{self.stop_loss_pct}% TP:{self.take_profit_pct}% TS:{self.trailing_stop_pct}%"


@dataclass
class OptimizationResult:
    """Result of a single configuration test"""
    config: TrailingConfig
    simulation_result: XGBSimulatorResult
    
    # Calculated metrics
    total_trades: int = 0
    win_rate: float = 0.0
    total_return: float = 0.0
    average_trade: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    risk_adjusted_return: float = 0.0
    
    # Equity curve
    equity_curve: List[float] = field(default_factory=list)
    equity_timestamps: List[pd.Timestamp] = field(default_factory=list)
    
    def __post_init__(self):
        if self.simulation_result:
            self._calculate_metrics()
    
    def _calculate_metrics(self):
        """Calculate all metrics from simulation result"""
        stats = self.simulation_result.get_statistics()
        
        self.total_trades = stats['total_trades']
        self.win_rate = stats['win_rate']
        self.total_return = stats['total_return']
        self.average_trade = stats['average_trade']
        self.best_trade = stats['best_trade']
        self.worst_trade = stats['worst_trade']
        self.profit_factor = stats['profit_factor']
        
        # Calculate Sharpe Ratio
        closed_trades = [t for t in self.simulation_result.trades if t.is_closed]
        if closed_trades:
            returns = [t.pnl_pct for t in closed_trades if t.pnl_pct is not None]
            if len(returns) > 1:
                mean_return = np.mean(returns)
                std_return = np.std(returns)
                self.sharpe_ratio = mean_return / std_return if std_return > 0 else 0.0
            else:
                self.sharpe_ratio = 0.0
        
        # Calculate equity curve and max drawdown
        self._calculate_equity_curve()
    
    def _calculate_equity_curve(self):
        """Build equity curve and calculate max drawdown"""
        if not self.simulation_result.trades:
            self.equity_curve = [100.0]
            self.equity_timestamps = []
            self.max_drawdown = 0.0
            return
        
        df = self.simulation_result.df
        equity = [100.0]
        timestamps = [df.index[0]]
        current_equity = 100.0
        
        for trade in self.simulation_result.trades:
            if trade.is_closed and trade.pnl_pct is not None:
                current_equity *= (1 + trade.pnl_pct / 100)
                equity.append(current_equity)
                timestamps.append(trade.exit_time)
        
        self.equity_curve = equity
        self.equity_timestamps = timestamps
        
        # Calculate max drawdown
        if len(equity) > 1:
            equity_arr = np.array(equity)
            running_max = np.maximum.accumulate(equity_arr)
            drawdowns = (running_max - equity_arr) / running_max * 100
            self.max_drawdown = np.max(drawdowns)
        else:
            self.max_drawdown = 0.0
        
        # Risk-adjusted return (Return / Max Drawdown)
        if self.max_drawdown > 0:
            self.risk_adjusted_return = self.total_return / self.max_drawdown
        else:
            self.risk_adjusted_return = self.total_return if self.total_return > 0 else 0.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for display"""
        return {
            'SL %': f"{self.config.stop_loss_pct:.1f}",
            'TP %': f"{self.config.take_profit_pct:.1f}",
            'TS %': f"{self.config.trailing_stop_pct:.1f}",
            'Act %': f"{self.config.trailing_activation_pct:.1f}",
            'Threshold': int(self.config.entry_threshold),
            'Trades': self.total_trades,
            'Win %': f"{self.win_rate:.1f}",
            'Return': f"{self.total_return:+.2f}%",
            'Sharpe': f"{self.sharpe_ratio:.2f}",
            'PF': f"{self.profit_factor:.2f}",
            'Max DD': f"{self.max_drawdown:.1f}%",
            'Risk Adj': f"{self.risk_adjusted_return:.2f}"
        }


@dataclass
class TrailingOptimizationResult:
    """Complete optimization results"""
    results: List[OptimizationResult]
    total_combinations: int
    execution_time_sec: float
    
    # Best results by different metrics
    best_by_sharpe: Optional[OptimizationResult] = None
    best_by_return: Optional[OptimizationResult] = None
    best_by_winrate: Optional[OptimizationResult] = None
    best_by_profit_factor: Optional[OptimizationResult] = None
    best_by_risk_adjusted: Optional[OptimizationResult] = None
    
    def __post_init__(self):
        if self.results:
            self._find_best_results()
    
    def _find_best_results(self):
        """Find best configurations by each metric"""
        valid_results = [r for r in self.results if r.total_trades >= 5]  # Min 5 trades
        
        if not valid_results:
            return
        
        self.best_by_sharpe = max(valid_results, key=lambda x: x.sharpe_ratio)
        self.best_by_return = max(valid_results, key=lambda x: x.total_return)
        self.best_by_winrate = max(valid_results, key=lambda x: x.win_rate)
        self.best_by_profit_factor = max(valid_results, key=lambda x: x.profit_factor if x.profit_factor < float('inf') else 0)
        self.best_by_risk_adjusted = max(valid_results, key=lambda x: x.risk_adjusted_return)
    
    def get_top_n(self, n: int = 10, metric: OptimizationMetric = OptimizationMetric.SHARPE_RATIO) -> List[OptimizationResult]:
        """Get top N results sorted by specified metric"""
        valid_results = [r for r in self.results if r.total_trades >= 5]
        
        if metric == OptimizationMetric.SHARPE_RATIO:
            return sorted(valid_results, key=lambda x: x.sharpe_ratio, reverse=True)[:n]
        elif metric == OptimizationMetric.TOTAL_RETURN:
            return sorted(valid_results, key=lambda x: x.total_return, reverse=True)[:n]
        elif metric == OptimizationMetric.WIN_RATE:
            return sorted(valid_results, key=lambda x: x.win_rate, reverse=True)[:n]
        elif metric == OptimizationMetric.PROFIT_FACTOR:
            return sorted(valid_results, key=lambda x: x.profit_factor if x.profit_factor < float('inf') else 0, reverse=True)[:n]
        elif metric == OptimizationMetric.RISK_ADJUSTED:
            return sorted(valid_results, key=lambda x: x.risk_adjusted_return, reverse=True)[:n]
        else:
            return valid_results[:n]
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert all results to DataFrame"""
        if not self.results:
            return pd.DataFrame()
        
        data = [r.to_dict() for r in self.results]
        return pd.DataFrame(data)


class TrailingStopOptimizer:
    """
    Optimizer for finding best trailing stop configurations.
    
    Tests all combinations of parameters and ranks them
    by performance metrics for live trading readiness.
    """
    
    DEFAULT_PARAM_GRID = {
        'stop_loss_pct': [1.0, 1.5, 2.0, 2.5, 3.0],
        'take_profit_pct': [2.0, 3.0, 4.0, 5.0, 6.0],
        'trailing_stop_pct': [0.5, 1.0, 1.5, 2.0],
        'trailing_activation_pct': [0.5, 1.0, 1.5, 2.0],
        'entry_threshold': [30, 40, 50]
    }
    
    QUICK_PARAM_GRID = {
        'stop_loss_pct': [1.5, 2.0, 2.5],
        'take_profit_pct': [3.0, 4.0, 5.0],
        'trailing_stop_pct': [1.0, 1.5, 2.0],
        'trailing_activation_pct': [1.0, 1.5],
        'entry_threshold': [40]
    }
    
    COMPREHENSIVE_PARAM_GRID = {
        'stop_loss_pct': [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
        'take_profit_pct': [1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0],
        'trailing_stop_pct': [0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5],
        'trailing_activation_pct': [0.3, 0.5, 1.0, 1.5, 2.0],
        'entry_threshold': [25, 30, 35, 40, 45, 50]
    }
    
    def __init__(self, max_holding_candles: int = 50):
        self.max_holding_candles = max_holding_candles
    
    def optimize(
        self,
        df: pd.DataFrame,
        xgb_scores: pd.Series,
        param_grid: Dict[str, List[float]] = None,
        progress_callback: Callable[[int, int], None] = None
    ) -> TrailingOptimizationResult:
        """
        Run optimization over all parameter combinations.
        
        Args:
            df: OHLCV DataFrame
            xgb_scores: XGB normalized scores (-100 to +100)
            param_grid: Parameter grid to test (uses default if None)
            progress_callback: Callback(current, total) for progress updates
            
        Returns:
            TrailingOptimizationResult with all tested configurations
        """
        if param_grid is None:
            param_grid = self.DEFAULT_PARAM_GRID
        
        start_time = datetime.now()
        
        # Generate all combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(itertools.product(*param_values))
        total_combinations = len(combinations)
        
        results = []
        
        for i, combo in enumerate(combinations):
            # Create config
            params = dict(zip(param_names, combo))
            config = TrailingConfig(
                stop_loss_pct=params['stop_loss_pct'],
                take_profit_pct=params['take_profit_pct'],
                trailing_stop_pct=params['trailing_stop_pct'],
                trailing_activation_pct=params['trailing_activation_pct'],
                entry_threshold=params['entry_threshold'],
                max_holding_candles=self.max_holding_candles
            )
            
            # Run simulation
            sim_config = config.to_simulator_config()
            sim_result = run_xgb_simulation(df, xgb_scores, sim_config)
            
            # Create optimization result
            opt_result = OptimizationResult(
                config=config,
                simulation_result=sim_result
            )
            results.append(opt_result)
            
            # Progress callback
            if progress_callback:
                progress_callback(i + 1, total_combinations)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return TrailingOptimizationResult(
            results=results,
            total_combinations=total_combinations,
            execution_time_sec=execution_time
        )
    
    @staticmethod
    def estimate_combinations(param_grid: Dict[str, List[float]]) -> int:
        """Estimate total number of combinations"""
        total = 1
        for values in param_grid.values():
            total *= len(values)
        return total
    
    @staticmethod
    def get_preset_grid(preset: str) -> Dict[str, List[float]]:
        """Get preset parameter grid"""
        if preset == 'quick':
            return TrailingStopOptimizer.QUICK_PARAM_GRID
        elif preset == 'comprehensive':
            return TrailingStopOptimizer.COMPREHENSIVE_PARAM_GRID
        else:
            return TrailingStopOptimizer.DEFAULT_PARAM_GRID


def run_trailing_optimization(
    df: pd.DataFrame,
    xgb_scores: pd.Series,
    preset: str = 'default',
    progress_callback: Callable[[int, int], None] = None
) -> TrailingOptimizationResult:
    """
    Convenience function to run trailing optimization.
    
    Args:
        df: OHLCV DataFrame
        xgb_scores: XGB normalized scores
        preset: 'quick', 'default', or 'comprehensive'
        progress_callback: Progress callback function
        
    Returns:
        TrailingOptimizationResult
    """
    optimizer = TrailingStopOptimizer()
    param_grid = optimizer.get_preset_grid(preset)
    
    return optimizer.optimize(
        df=df,
        xgb_scores=xgb_scores,
        param_grid=param_grid,
        progress_callback=progress_callback
    )
