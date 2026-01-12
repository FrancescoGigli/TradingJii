"""
Core modules for ML Feature Engineering

Components:
- FeatureCalculator: Computes ML features from OHLCV data
- MarketFeatureCalculator: Computes cross-asset market features
- MultiTimeframeFeatures: Multi-timeframe feature aggregation
- TrailingStopLabeler: Generates training labels using trailing stop simulation
- TrailingLabelConfig: Configuration for label generation
"""

from .features import FeatureCalculator
from .market_features import MarketFeatureCalculator, MultiTimeframeFeatures
from .labels import (
    # New classes (primary)
    TrailingStopLabeler,
    TrailingLabelConfig,
    generate_trailing_labels,
    
    # Backward compatibility aliases (deprecated)
    TripleBarrierLabeler,  # -> TrailingStopLabeler
    BarrierConfig,         # -> TrailingLabelConfig
    generate_training_labels,  # -> generate_trailing_labels
)

__all__ = [
    # Feature calculators
    'FeatureCalculator',
    'MarketFeatureCalculator', 
    'MultiTimeframeFeatures',
    
    # Label generators (new)
    'TrailingStopLabeler',
    'TrailingLabelConfig',
    'generate_trailing_labels',
    
    # Backward compatibility (deprecated)
    'TripleBarrierLabeler',
    'BarrierConfig',
    'generate_training_labels',
]
