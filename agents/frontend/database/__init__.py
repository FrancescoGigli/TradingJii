"""
Database module - Modularized database access functions

This module provides all database functions for the Crypto Dashboard.
All functions are re-exported for backwards compatibility.
"""

# Connection
from .connection import get_connection

# OHLCV functions
from .ohlcv import (
    get_top_symbols,
    get_symbols,
    get_timeframes,
    get_ohlcv,
    get_stats,
    get_update_status,
)

# Historical data functions
from .historical import (
    get_historical_stats,
    get_backfill_status_all,
    get_historical_ohlcv,
    get_historical_symbols,
    get_historical_date_range,
    get_backfill_summary,
    get_historical_inventory,
    get_historical_symbols_by_volume,
    get_symbol_data_quality,
    trigger_backfill,
    check_backfill_running,
    get_backfill_errors,
    clear_historical_data,
    retry_failed_downloads,
)

# ML Labels functions
from .ml_labels import (
    create_ml_labels_table,
    save_ml_labels_to_db,
    get_ml_labels_stats,
    get_ml_labels_by_symbol,
    get_ml_labels,
    clear_ml_labels,
    get_ml_labels_table_schema,
    get_available_symbols_for_labels,
    get_ml_labels_full,
    get_ml_labels_inventory,
    get_ml_training_dataset,
    get_dataset_availability,
)

# Explorer functions
from .explorer import (
    execute_custom_query,
    ML_LABELS_EXAMPLE_QUERIES,
)

# Export all
__all__ = [
    # Connection
    'get_connection',
    
    # OHLCV
    'get_top_symbols',
    'get_symbols',
    'get_timeframes',
    'get_ohlcv',
    'get_stats',
    'get_update_status',
    
    # Historical
    'get_historical_stats',
    'get_backfill_status_all',
    'get_historical_ohlcv',
    'get_historical_symbols',
    'get_historical_date_range',
    'get_backfill_summary',
    'get_historical_inventory',
    'get_historical_symbols_by_volume',
    'get_symbol_data_quality',
    'trigger_backfill',
    'check_backfill_running',
    'get_backfill_errors',
    'clear_historical_data',
    'retry_failed_downloads',
    
    # ML Labels
    'create_ml_labels_table',
    'save_ml_labels_to_db',
    'get_ml_labels_stats',
    'get_ml_labels_by_symbol',
    'get_ml_labels',
    'clear_ml_labels',
    'get_ml_labels_table_schema',
    'get_available_symbols_for_labels',
    'get_ml_labels_full',
    'get_ml_labels_inventory',
    'get_ml_training_dataset',
    'get_dataset_availability',
    
    # Explorer
    'execute_custom_query',
    'ML_LABELS_EXAMPLE_QUERIES',
]
