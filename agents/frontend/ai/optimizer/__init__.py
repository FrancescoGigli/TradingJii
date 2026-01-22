"""
🔬 Optimizer Module - Grid Search and Optuna optimization

Includes:
- GridSearchOptimizer: General parameter optimization
- TrailingStopOptimizer: Specific trailing stop optimization for live trading
- LabelOptimizer: Optuna-based label parameter optimization
"""

from .grid_search import GridSearchOptimizer, OptimizationResult
from .trailing_optimizer import (
    TrailingStopOptimizer,
    TrailingConfig,
    TrailingOptimizationResult,
    OptimizationMetric,
    run_trailing_optimization
)
from .label_optimizer import (
    LabelOptimizer,
    OptimizationObjective,
    OptimizationResult as LabelOptimizationResult,
    optimize_labels_with_optuna,
    get_default_params,
    PARAM_SEARCH_SPACE
)

__all__ = [
    # Grid Search
    'GridSearchOptimizer', 
    'OptimizationResult',
    # Trailing Stop
    'TrailingStopOptimizer',
    'TrailingConfig',
    'TrailingOptimizationResult',
    'OptimizationMetric',
    'run_trailing_optimization',
    # Label Optimization (Optuna)
    'LabelOptimizer',
    'OptimizationObjective',
    'LabelOptimizationResult',
    'optimize_labels_with_optuna',
    'get_default_params',
    'PARAM_SEARCH_SPACE'
]
