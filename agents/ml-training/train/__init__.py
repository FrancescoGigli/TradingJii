"""
🚀 ML Training Package

Modular package for XGBoost model training.
Split from monolithic train.py for maintainability.

Submodules:
- config: Feature columns, XGBoost parameters, paths
- data_loader: Dataset loading and validation
- metrics: Ranking metrics calculation
- trainer: Model training and saving
- main: Entry point and CLI

Usage:
    python -m agents.ml_training.train
"""

from .config import (
    FEATURE_COLUMNS,
    EXCLUDE_COLUMNS,
    XGBOOST_PARAMS,
    TARGET_LONG,
    TARGET_SHORT,
    TRAIN_RATIO,
    DB_PATH,
    MODEL_OUTPUT_DIR
)

from .data_loader import (
    load_dataset,
    validate_data_quality,
    prepare_dataset
)

from .metrics import (
    temporal_split,
    calculate_ranking_metrics,
    print_ranking_metrics
)

from .trainer import (
    train_model,
    save_models
)

__all__ = [
    # Config
    'FEATURE_COLUMNS', 'EXCLUDE_COLUMNS', 'XGBOOST_PARAMS',
    'TARGET_LONG', 'TARGET_SHORT', 'TRAIN_RATIO',
    'DB_PATH', 'MODEL_OUTPUT_DIR',
    # Data
    'load_dataset', 'validate_data_quality', 'prepare_dataset',
    # Metrics
    'temporal_split', 'calculate_ranking_metrics', 'print_ranking_metrics',
    # Trainer
    'train_model', 'save_models'
]
