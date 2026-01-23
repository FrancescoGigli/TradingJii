"""
🏋️ Model Training and Saving

XGBoost model training and persistence.
"""

import pickle
import json
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from xgboost import XGBRegressor
from .config import XGBOOST_PARAMS


def train_model(X_train, y_train, X_test, y_test, model_name: str):
    """Train XGBoost Regressor model."""
    print(f"\n{'📈' if 'long' in model_name.lower() else '📉'} Training {model_name}...")
    print(f"   Train: {len(X_train):,} samples | Test: {len(X_test):,} samples")
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    model = XGBRegressor(**XGBOOST_PARAMS)
    model.fit(X_train_scaled, y_train, eval_set=[(X_test_scaled, y_test)], verbose=False)
    
    y_pred_train = model.predict(X_train_scaled)
    y_pred_test = model.predict(X_test_scaled)
    
    metrics = {
        'train_rmse': np.sqrt(mean_squared_error(y_train, y_pred_train)),
        'test_rmse': np.sqrt(mean_squared_error(y_test, y_pred_test)),
        'train_mae': mean_absolute_error(y_train, y_pred_train),
        'test_mae': mean_absolute_error(y_test, y_pred_test),
        'train_r2': r2_score(y_train, y_pred_train),
        'test_r2': r2_score(y_test, y_pred_test),
    }
    
    print(f"   📊 RMSE: train={metrics['train_rmse']:.6f}, test={metrics['test_rmse']:.6f}")
    print(f"   📊 R²: train={metrics['train_r2']:.4f}, test={metrics['test_r2']:.4f}")
    
    feature_importance = pd.DataFrame({
        'feature': X_train.columns, 'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print(f"\n   🏆 Top 5 Features:")
    for _, row in feature_importance.head(5).iterrows():
        print(f"      {row['feature']:25s} {row['importance']:.4f}")
    
    return model, scaler, metrics, feature_importance


def save_models(model_long, model_short, scaler, feature_names, metrics_long, metrics_short, 
                output_dir: Path, train_start=None, train_end=None, test_start=None, test_end=None,
                symbols=None, timeframes=None):
    """Save trained models, scaler, and metadata."""
    print(f"\n💾 Saving models to: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    version = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save versioned files
    for name, obj in [('model_long', model_long), ('model_short', model_short), ('scaler', scaler)]:
        with open(output_dir / f"{name}_{version}.pkl", 'wb') as f:
            pickle.dump(obj, f)
        with open(output_dir / f"{name}_latest.pkl", 'wb') as f:
            pickle.dump(obj, f)
    
    metadata = {
        'version': version, 'created_at': datetime.now().isoformat(),
        'feature_names': feature_names, 'n_features': len(feature_names),
        'xgboost_params': XGBOOST_PARAMS,
        'metrics_long': metrics_long, 'metrics_short': metrics_short,
        'data_range': {
            'train_start': str(train_start), 'train_end': str(train_end),
            'test_start': str(test_start), 'test_end': str(test_end),
        },
        'symbols': symbols or [], 'timeframes': timeframes or [],
    }
    
    for suffix in [f'_{version}', '_latest']:
        with open(output_dir / f"metadata{suffix}.json", 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
    
    print(f"   ✅ Models saved (version: {version})")
    return version
