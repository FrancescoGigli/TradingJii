"""
AI Core Module - Configuration and base classes
"""

from .config import AI_CONFIG, BACKTEST_CONFIG, CONFIDENCE_LEVELS, get_confidence_level
from .labels import TrailingStopLabeler, TrailingLabelConfig, generate_trailing_labels

__all__ = [
    'AI_CONFIG', 
    'BACKTEST_CONFIG', 
    'CONFIDENCE_LEVELS', 
    'get_confidence_level',
    'TrailingStopLabeler',
    'TrailingLabelConfig',
    'generate_trailing_labels',
]
