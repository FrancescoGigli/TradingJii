"""
Training Package - Modular Training System

Organized structure:
- labeling.py: Triple Barrier and SL-Aware labeling methods
- features.py: Temporal feature engineering
- xgb_trainer.py: XGBoost model training
- walk_forward.py: Walk-Forward testing implementation
"""

from training.labeling import label_with_triple_barrier, label_with_sl_awareness_v2
from training.features import create_temporal_features
from training.xgb_trainer import train_xgb_model
from training.walk_forward import walk_forward_training

__all__ = [
    'label_with_triple_barrier',
    'label_with_sl_awareness_v2',
    'create_temporal_features',
    'train_xgb_model',
    'walk_forward_training',
]
