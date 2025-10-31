#!/usr/bin/env python3
"""
📊 DASHBOARD PACKAGE

Modular dashboard components organized for maintainability:

Core Utilities:
- helpers: ColorHelper and formatting utilities
- stats_calculator: Statistics and metrics calculation
- update_manager: Cache management and async updates

UI Components:
- table_factory: Table creation and configuration
- adaptive_tab: Adaptive Memory tab creator and populator

Renderers:
- position_renderer: Position table cell rendering and population
- closed_renderer: Closed trades table rendering and population
"""

# Core utilities
from .helpers import ColorHelper
from .stats_calculator import StatsCalculator
from .update_manager import UpdateManager

# UI components
from .table_factory import TableFactory
from .adaptive_tab import create_adaptive_memory_table, populate_adaptive_memory_table

# Renderers
from .position_renderer import PositionCellRenderer, PositionTablePopulator
from .closed_renderer import ClosedCellRenderer, ClosedTablePopulator

__all__ = [
    # Core utilities
    'ColorHelper',
    'StatsCalculator',
    'UpdateManager',
    
    # UI components
    'TableFactory',
    'create_adaptive_memory_table',
    'populate_adaptive_memory_table',
    
    # Renderers
    'PositionCellRenderer',
    'PositionTablePopulator',
    'ClosedCellRenderer',
    'ClosedTablePopulator',
]
