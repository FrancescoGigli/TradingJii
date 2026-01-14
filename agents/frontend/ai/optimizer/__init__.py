"""
🔬 Optimizer Module - Grid Search for backtest parameter optimization

Includes:
- GridSearchOptimizer: General parameter optimization
- TrailingStopOptimizer: Specific trailing stop optimization for live trading
"""

from .grid_search import GridSearchOptimizer, OptimizationResult
from .trailing_optimizer import (
    TrailingStopOptimizer,
    TrailingConfig,
    TrailingOptimizationResult,
    OptimizationMetric,
    run_trailing_optimization
)

__all__ = [
    'GridSearchOptimizer', 
    'OptimizationResult',
    'TrailingStopOptimizer',
    'TrailingConfig',
    'TrailingOptimizationResult',
    'OptimizationMetric',
    'run_trailing_optimization'
]
