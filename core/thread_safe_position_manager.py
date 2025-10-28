#!/usr/bin/env python3
"""
🔒 THREAD-SAFE POSITION MANAGER

Legacy entry point for backward compatibility.
All functionality has been refactored into modular components.

New modular structure:
- core/position_management/position_data.py      - Data structures
- core/position_management/position_io.py        - File I/O operations
- core/position_management/position_core.py      - Core CRUD + thread-safe ops
- core/position_management/position_sync.py      - Bybit synchronization
- core/position_management/position_trailing.py  - Trailing stop system
- core/position_management/position_safety.py    - Safety checks
- core/position_management/__init__.py           - FACADE for backward compatibility

This file now simply re-exports everything from the new modular system.
All existing imports will continue to work without any changes.
"""

# Re-export everything from new modular system
from core.position_management import (
    ThreadSafePositionManager,
    ThreadSafePosition,
    TrailingStopData,
    global_thread_safe_position_manager
)

# Backward compatibility: make sure global instance is available
__all__ = [
    'ThreadSafePositionManager',
    'ThreadSafePosition', 
    'TrailingStopData',
    'global_thread_safe_position_manager'
]

# For any code that imports directly from this file, everything will work exactly as before
# Example: from core.thread_safe_position_manager import global_thread_safe_position_manager
