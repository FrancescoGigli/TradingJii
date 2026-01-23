"""
📊 ML Labels Database Module

Modular package for ML training labels database operations.
Split from monolithic ml_labels.py for maintainability.

Submodules:
- crud: CRUD operations (get, clear)
- save: Save labels to database
- stats: Statistics and inventory functions
- schema: Table creation and dataset export

Usage:
    from agents.frontend.database.ml_labels import (
        get_training_labels,
        save_ml_labels_to_db,
        get_ml_labels_stats,
        get_ml_training_dataset
    )
"""

# Re-export all public functions for backward compatibility
from .crud import (
    get_training_labels,
    get_ml_labels,
    get_ml_labels_full,
    clear_ml_labels
)

from .save import (
    save_ml_labels_to_db,
    _safe_float,
    _safe_int
)

from .stats import (
    get_ml_labels_stats,
    get_ml_labels_by_symbol,
    get_ml_labels_inventory,
    get_available_symbols_for_labels
)

from .schema import (
    create_ml_labels_table,
    get_ml_labels_table_schema,
    get_ml_training_dataset,
    get_dataset_availability
)

__all__ = [
    # CRUD
    'get_training_labels',
    'get_ml_labels',
    'get_ml_labels_full',
    'clear_ml_labels',
    # Save
    'save_ml_labels_to_db',
    '_safe_float',
    '_safe_int',
    # Stats
    'get_ml_labels_stats',
    'get_ml_labels_by_symbol',
    'get_ml_labels_inventory',
    'get_available_symbols_for_labels',
    # Schema
    'create_ml_labels_table',
    'get_ml_labels_table_schema',
    'get_ml_training_dataset',
    'get_dataset_availability'
]
