#!/usr/bin/env python3
"""
📊 DASHBOARD PACKAGE

Modular dashboard components:
- helpers: ColorHelper and utilities
- adaptive_tab: Adaptive Memory tab creator and populator
"""

from .helpers import ColorHelper
from .adaptive_tab import create_adaptive_memory_table, populate_adaptive_memory_table

__all__ = [
    'ColorHelper',
    'create_adaptive_memory_table',
    'populate_adaptive_memory_table',
]
