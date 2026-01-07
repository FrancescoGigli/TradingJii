"""
⚙️ ML Training Pipeline Configuration

Configuration for model training, validation, and versioning.
"""

import os
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════
SHARED_DATA_PATH = os.environ.get('SHARED_DATA_PATH', '/app/shared')
DB_PATH = os.path.join(SHARED_DATA_PATH, 'data_cache', 'trading_data.db')
MODEL_PATH = os.path.join(SHARED_DATA_PATH, 'models')

# ═══════════════════════════════════════════════════════════════════════════════
# DATASET CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
DATASET_CONFIG = {
    # Timeframe for training
    'primary_timeframe': '15m',
    
    # Minimum samples per asset
    'min_samples_per_asset': 5000,
    
    # Maximum NaN ratio per feature
    'max_nan_ratio': 0.1,
    
    # Drop features with high correlation
    'drop_correlated_features': True,
    'correlation_threshold': 0.95,
}

# ═══════════════════════════════════════════════════════════════════════════════
# TEMPORAL SPLIT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
SPLIT_CONFIG = {
    # Walk-forward validation
    'n_splits': 5,  # Number of train/test splits
    
    # Split ratios
    'train_ratio': 0.7,  # 70% train
    'val_ratio': 0.15,   # 15% validation (for hyperparameter tuning)
    'test_ratio': 0.15,  # 15% test
    
    # Embargo period (bars between train and test to avoid leakage)
    'embargo_bars': 48,  # 48 bars = 12 hours on 15m
    
    # Purging (remove labels that depend on test period)
    'purge_bars': 24,  # Equal to max_holding_bars in Triple Barrier
}

# ═══════════════════════════════════════════════════════════════════════════════
# MODEL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
MODEL_TYPE = 'lightgbm'  # 'lightgbm' or 'xgboost'

LIGHTGBM_PARAMS = {
    'objective': 'binary',
    'metric': 'auc',
    'boosting_type': 'gbdt',
    'num_leaves': 31,
    'learning_rate': 0.05,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'min_child_samples': 20,
    'n_estimators': 500,
    'early_stopping_rounds': 50,
    'verbose': -1,
    'random_state': 42,
    'class_weight': 'balanced',  # Handle imbalanced labels
}

XGBOOST_PARAMS = {
    'objective': 'binary:logistic',
    'eval_metric': 'auc',
    'tree_method': 'hist',
    'max_depth': 6,
    'learning_rate': 0.05,
    'colsample_bytree': 0.8,
    'subsample': 0.8,
    'min_child_weight': 10,
    'n_estimators': 500,
    'early_stopping_rounds': 50,
    'verbosity': 0,
    'random_state': 42,
    'scale_pos_weight': 1,  # Will be adjusted for imbalance
}

# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
TRAINING_CONFIG = {
    # Train separate models for long and short
    'train_long_model': True,
    'train_short_model': True,
    
    # Minimum probability threshold for predictions
    'min_probability': 0.55,  # Only predict 1 if P >= 0.55
    
    # Feature importance threshold (drop features with 0 importance)
    'drop_zero_importance': True,
    
    # Cross-validation for hyperparameter tuning
    'cv_folds': 3,
    
    # Sample weights based on volatility regime
    'use_sample_weights': True,
}

# ═══════════════════════════════════════════════════════════════════════════════
# EVALUATION METRICS
# ═══════════════════════════════════════════════════════════════════════════════
EVALUATION_METRICS = [
    'accuracy',
    'precision',
    'recall', 
    'f1',
    'roc_auc',
    'profit_factor',  # Custom metric
    'avg_return',     # Average return when model predicts 1
]

# ═══════════════════════════════════════════════════════════════════════════════
# MODEL VERSIONING
# ═══════════════════════════════════════════════════════════════════════════════
def get_model_version():
    """Generate model version string"""
    return datetime.now().strftime('%Y%m%d_%H%M%S')

MODEL_NAMING = {
    'long_model': 'entry_long_{version}.pkl',
    'short_model': 'entry_short_{version}.pkl',
    'metadata': 'model_metadata_{version}.json',
}

# ═══════════════════════════════════════════════════════════════════════════════
# RETRAINING SCHEDULE
# ═══════════════════════════════════════════════════════════════════════════════
RETRAIN_CONFIG = {
    # Retrain frequency
    'retrain_interval_hours': 168,  # Weekly
    
    # Minimum new samples before retraining
    'min_new_samples': 10000,
    
    # Performance degradation threshold (trigger retraining)
    'max_accuracy_drop': 0.05,  # 5% drop
}

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

def print_config():
    """Print training configuration"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║               ML TRAINING CONFIGURATION                      ║
╠══════════════════════════════════════════════════════════════╣
║  Model Type:         {MODEL_TYPE:<15}                        ║
║  Walk-Forward Splits: {SPLIT_CONFIG['n_splits']}                                     ║
║  Train/Val/Test:     {int(SPLIT_CONFIG['train_ratio']*100)}/{int(SPLIT_CONFIG['val_ratio']*100)}/{int(SPLIT_CONFIG['test_ratio']*100)}%                              ║
║  Embargo Bars:       {SPLIT_CONFIG['embargo_bars']} (12h on 15m)                       ║
╠══════════════════════════════════════════════════════════════╣
║  Long Model:         {'✓' if TRAINING_CONFIG['train_long_model'] else '✗'}                                      ║
║  Short Model:        {'✓' if TRAINING_CONFIG['train_short_model'] else '✗'}                                      ║
║  Min Probability:    {TRAINING_CONFIG['min_probability']}                                ║
╚══════════════════════════════════════════════════════════════╝
    """)

if __name__ == '__main__':
    print_config()
