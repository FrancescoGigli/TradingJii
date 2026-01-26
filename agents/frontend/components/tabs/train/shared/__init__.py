"""
Shared modules for the Train tab.

Contains centralized utilities to avoid code duplication:
- model_loader: Load model metadata and paths
- ai_analysis: GPT-4o analysis functions
- colors: Dark theme color scheme
"""

from .model_loader import get_model_dir, load_metadata
from .colors import COLORS

__all__ = [
    'get_model_dir',
    'load_metadata',
    'COLORS'
]
