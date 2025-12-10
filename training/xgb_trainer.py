"""
XGBoost Training Module

Handles XGBoost model training with:
- Temporal train/validation split
- Class weight balancing
- Early stopping
- Comprehensive metrics
"""

from __future__ import annotations

import logging
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
from sklearn.utils import class_weight
import xgboost as xgb

import config

_LOG = logging.getLogger(__name__)


def train_xgb_model(X_train, y_train, X_val, y_val):
    """
    Train XGBoost model with validation and early stopping.
    
    Args:
        X_train: Training features
        y_train: Training labels
        X_val: Validation features
        y_val: Validation labels
        
    Returns:
        tuple: (model, scaler, metrics)
    """
    _LOG.info("🔧 Training XGBoost model...")
    _LOG.info(f"   Train samples: {len(X_train)}")
    _LOG.info(f"   Validation samples: {len(X_val)}")
    
    # Preprocessing
    scaler = StandardScaler().fit(X_train)
    X_train_scaled = scaler.transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    
    # Log class distribution
    unique_tr, counts_tr = np.unique(y_train, return_counts=True)
    unique_val, counts_val = np.unique(y_val, return_counts=True)
    
    _LOG.info("📊 Training class distribution:")
    for cls, count in zip(unique_tr, counts_tr):
        cls_name = {0: 'NEUTRAL', 1: 'BUY', 2: 'SELL'}[cls]
        _LOG.info(f"   {cls_name}: {count} ({count/len(y_train)*100:.1f}%)")
    
    # Calculate class weights
    sample_weight = None
    if config.USE_CLASS_WEIGHTS:
        try:
            class_weights = class_weight.compute_class_weight(
                'balanced', classes=np.unique(y_train), y=y_train
            )
            class_weight_dict = {i: class_weights[i] for i in range(len(class_weights))}
            sample_weight = np.array([class_weight_dict[cls] for cls in y_train])
            _LOG.info(f"🎯 Class weights computed")
        except Exception as e:
            _LOG.warning(f"⚠️ Class weights failed: {e}")
    
    # Create XGBoost model
    model = xgb.XGBClassifier(
        n_estimators=config.XGB_N_ESTIMATORS,
        max_depth=config.XGB_MAX_DEPTH,
        learning_rate=config.XGB_LEARNING_RATE,
        subsample=config.XGB_SUBSAMPLE,
        colsample_bytree=config.XGB_COLSAMPLE_BYTREE,
        reg_alpha=config.XGB_REG_ALPHA,
        reg_lambda=config.XGB_REG_LAMBDA,
        num_class=3,
        objective='multi:softprob',
        eval_metric='mlogloss',
        verbosity=0,
        random_state=42,
        early_stopping_rounds=20
    )
    
    _LOG.info("🚀 Training with early stopping...")
    
    # Train with early stopping
    model.fit(
        X_train_scaled, y_train,
        eval_set=[(X_val_scaled, y_val)],
        sample_weight=sample_weight,
        verbose=False
    )
    
    _LOG.info("✅ Training completed!")
    
    # Evaluate on validation
    y_pred = model.predict(X_val_scaled)
    y_proba = model.predict_proba(X_val_scaled)
    
    # Calculate metrics
    metrics = {
        "val_accuracy":  accuracy_score(y_val, y_pred),
        "val_precision": precision_score(y_val, y_pred, average="weighted", zero_division=0),
        "val_recall":    recall_score(y_val, y_pred, average="weighted", zero_division=0),
        "val_f1":        f1_score(y_val, y_pred, average="weighted", zero_division=0),
    }
    
    _LOG.info("📊 Validation Results:")
    _LOG.info(f"   Accuracy:  {metrics['val_accuracy']:.4f}")
    _LOG.info(f"   Precision: {metrics['val_precision']:.4f}")
    _LOG.info(f"   Recall:    {metrics['val_recall']:.4f}")
    _LOG.info(f"   F1-Score:  {metrics['val_f1']:.4f}")
    
    # Classification report
    _LOG.info("📋 Classification Report:")
    class_names = ['NEUTRAL', 'BUY', 'SELL']
    report = classification_report(y_val, y_pred, target_names=class_names, zero_division=0)
    for line in report.split('\n'):
        if line.strip():
            _LOG.info(f"   {line}")
    
    # Confusion Matrix
    _LOG.info("🔍 Confusion Matrix:")
    cm = confusion_matrix(y_val, y_pred)
    for i, true_class in enumerate(class_names):
        for j, pred_class in enumerate(class_names):
            if cm[i,j] > 0:
                _LOG.info(f"   True {true_class} → Pred {pred_class}: {cm[i,j]}")
    
    # Feature importance
    try:
        importance = model.feature_importances_
        top_features_idx = np.argsort(importance)[-10:][::-1]
        _LOG.info("🏆 Top 10 Feature Importance:")
        for i, idx in enumerate(top_features_idx):
            feature_name = config.EXPECTED_COLUMNS[idx] if idx < len(config.EXPECTED_COLUMNS) else f"Feature_{idx}"
            _LOG.info(f"   {i+1}. {feature_name}: {importance[idx]:.4f}")
    except Exception as e:
        _LOG.warning(f"Could not calculate feature importance: {e}")
    
    return model, scaler, metrics


def create_temporal_split(X, y, train_pct=0.90):
    """
    Create temporal train/validation split.
    
    Respects time order: training data comes before validation data.
    
    Args:
        X: All features
        y: All labels
        train_pct: Percentage for training (default 0.90 = 90% train, 10% val)
        
    Returns:
        tuple: (X_train, y_train, X_val, y_val)
    """
    n = len(X)
    split_idx = int(n * train_pct)
    
    X_train = X[:split_idx]
    y_train = y[:split_idx]
    X_val = X[split_idx:]
    y_val = y[split_idx:]
    
    _LOG.info(f"📊 Temporal split ({train_pct*100:.0f}/{(1-train_pct)*100:.0f}):")
    _LOG.info(f"   Training:   {len(X_train)} samples")
    _LOG.info(f"   Validation: {len(X_val)} samples")
    
    return X_train, y_train, X_val, y_val
