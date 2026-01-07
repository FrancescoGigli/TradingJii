"""
🤖 ML Model Trainer

Training pipeline for LightGBM/XGBoost binary classifiers.
Handles training, evaluation, and model persistence.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import json
import pickle
from pathlib import Path
from datetime import datetime
import logging

# ML Libraries
try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report
)

logger = logging.getLogger(__name__)


@dataclass
class TrainingResult:
    """Container for training results"""
    model: Any
    model_type: str
    target: str  # 'long' or 'short'
    
    # Metrics on test set
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    roc_auc: float = 0.0
    
    # Custom trading metrics
    profit_factor: float = 0.0
    avg_return: float = 0.0
    win_rate: float = 0.0
    
    # Feature importance
    feature_importance: Dict[str, float] = field(default_factory=dict)
    
    # Training metadata
    n_train_samples: int = 0
    n_test_samples: int = 0
    train_time_seconds: float = 0.0
    
    # Confusion matrix
    confusion_matrix: Optional[np.ndarray] = None


class ModelTrainer:
    """
    Trains LightGBM or XGBoost binary classifiers.
    
    Supports:
    - Early stopping with validation set
    - Custom sample weights
    - Feature importance extraction
    - Custom trading metrics
    """
    
    def __init__(
        self,
        model_type: str = 'lightgbm',
        params: Dict = None,
        min_probability: float = 0.55
    ):
        """
        Initialize trainer.
        
        Args:
            model_type: 'lightgbm' or 'xgboost'
            params: Model hyperparameters
            min_probability: Threshold for positive prediction
        """
        self.model_type = model_type
        self.params = params or {}
        self.min_probability = min_probability
        
        # Validate model availability
        if model_type == 'lightgbm' and not HAS_LIGHTGBM:
            raise ImportError("LightGBM not installed")
        if model_type == 'xgboost' and not HAS_XGBOOST:
            raise ImportError("XGBoost not installed")
    
    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        sample_weights: Optional[pd.Series] = None,
        target_name: str = 'long'
    ) -> TrainingResult:
        """
        Train a binary classifier.
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            sample_weights: Optional sample weights
            target_name: 'long' or 'short'
        
        Returns:
            TrainingResult with trained model and metrics
        """
        start_time = datetime.now()
        
        if self.model_type == 'lightgbm':
            model = self._train_lightgbm(
                X_train, y_train, X_val, y_val, sample_weights
            )
        else:
            model = self._train_xgboost(
                X_train, y_train, X_val, y_val, sample_weights
            )
        
        train_time = (datetime.now() - start_time).total_seconds()
        
        # Get feature importance
        importance = self._get_feature_importance(model, X_train.columns)
        
        result = TrainingResult(
            model=model,
            model_type=self.model_type,
            target=target_name,
            feature_importance=importance,
            n_train_samples=len(X_train),
            train_time_seconds=train_time
        )
        
        return result
    
    def _train_lightgbm(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        sample_weights: Optional[pd.Series] = None
    ) -> lgb.LGBMClassifier:
        """Train LightGBM classifier"""
        from config import LIGHTGBM_PARAMS
        
        params = {**LIGHTGBM_PARAMS, **self.params}
        
        # Handle early stopping
        early_stopping = params.pop('early_stopping_rounds', 50)
        
        model = lgb.LGBMClassifier(**params)
        
        # Prepare weights
        weights = sample_weights.values if sample_weights is not None else None
        
        # Train with early stopping
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            eval_metric='auc',
            callbacks=[lgb.early_stopping(early_stopping, verbose=False)],
            sample_weight=weights
        )
        
        logger.info(f"LightGBM trained: {model.best_iteration_} iterations")
        
        return model
    
    def _train_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        sample_weights: Optional[pd.Series] = None
    ) -> xgb.XGBClassifier:
        """Train XGBoost classifier"""
        from config import XGBOOST_PARAMS
        
        params = {**XGBOOST_PARAMS, **self.params}
        
        # Adjust scale_pos_weight for imbalance
        n_pos = y_train.sum()
        n_neg = len(y_train) - n_pos
        if n_pos > 0:
            params['scale_pos_weight'] = n_neg / n_pos
        
        # Handle early stopping
        early_stopping = params.pop('early_stopping_rounds', 50)
        
        model = xgb.XGBClassifier(**params)
        
        # Prepare weights
        weights = sample_weights.values if sample_weights is not None else None
        
        # Train with early stopping
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
            sample_weight=weights
        )
        
        logger.info(f"XGBoost trained: {model.best_iteration} iterations")
        
        return model
    
    def _get_feature_importance(
        self, 
        model: Any, 
        feature_names: List[str]
    ) -> Dict[str, float]:
        """Extract feature importance from trained model"""
        if self.model_type == 'lightgbm':
            importance = model.feature_importances_
        else:
            importance = model.feature_importances_
        
        # Create dict sorted by importance
        imp_dict = dict(zip(feature_names, importance))
        return dict(sorted(imp_dict.items(), key=lambda x: x[1], reverse=True))
    
    def evaluate(
        self,
        model: Any,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        returns: Optional[pd.Series] = None
    ) -> Dict[str, float]:
        """
        Evaluate model on test set.
        
        Args:
            model: Trained model
            X_test: Test features
            y_test: Test labels
            returns: Optional returns for trading metrics
        
        Returns:
            Dictionary of evaluation metrics
        """
        # Get predictions
        y_proba = model.predict_proba(X_test)[:, 1]
        y_pred = (y_proba >= self.min_probability).astype(int)
        
        # Classification metrics
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1': f1_score(y_test, y_pred, zero_division=0),
            'roc_auc': roc_auc_score(y_test, y_proba) if y_test.nunique() > 1 else 0.5,
        }
        
        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        metrics['true_negatives'] = cm[0, 0] if cm.shape[0] > 0 else 0
        metrics['false_positives'] = cm[0, 1] if cm.shape[1] > 1 else 0
        metrics['false_negatives'] = cm[1, 0] if cm.shape[0] > 1 else 0
        metrics['true_positives'] = cm[1, 1] if cm.shape == (2, 2) else 0
        
        # Trading metrics (if returns provided)
        if returns is not None:
            trading_metrics = self._compute_trading_metrics(
                y_pred, y_test, returns
            )
            metrics.update(trading_metrics)
        
        return metrics
    
    def _compute_trading_metrics(
        self,
        y_pred: np.ndarray,
        y_true: pd.Series,
        returns: pd.Series
    ) -> Dict[str, float]:
        """Compute custom trading metrics"""
        # Align arrays
        pred_mask = y_pred == 1
        
        if not pred_mask.any():
            return {
                'profit_factor': 0.0,
                'avg_return': 0.0,
                'win_rate': 0.0,
                'n_trades': 0
            }
        
        # Get returns when model predicts positive
        trade_returns = returns.iloc[pred_mask]
        
        # Win rate
        n_wins = (trade_returns > 0).sum()
        n_trades = len(trade_returns)
        win_rate = n_wins / n_trades if n_trades > 0 else 0
        
        # Profit factor
        gross_profit = trade_returns[trade_returns > 0].sum()
        gross_loss = abs(trade_returns[trade_returns < 0].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Average return
        avg_return = trade_returns.mean() * 100  # As percentage
        
        return {
            'profit_factor': profit_factor,
            'avg_return': avg_return,
            'win_rate': win_rate,
            'n_trades': n_trades
        }
    
    def predict(
        self, 
        model: Any, 
        X: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Make predictions with trained model.
        
        Args:
            model: Trained model
            X: Features
        
        Returns:
            Tuple of (predictions, probabilities)
        """
        y_proba = model.predict_proba(X)[:, 1]
        y_pred = (y_proba >= self.min_probability).astype(int)
        return y_pred, y_proba


class ModelStorage:
    """Handles model persistence and versioning"""
    
    def __init__(self, base_path: str = 'models'):
        """
        Initialize model storage.
        
        Args:
            base_path: Base directory for model storage
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def save_model(
        self,
        result: TrainingResult,
        version: str = None
    ) -> str:
        """
        Save trained model and metadata.
        
        Args:
            result: TrainingResult to save
            version: Optional version string
        
        Returns:
            Path to saved model
        """
        if version is None:
            version = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create version directory
        version_path = self.base_path / version
        version_path.mkdir(exist_ok=True)
        
        # Save model
        model_filename = f"entry_{result.target}_{result.model_type}.pkl"
        model_path = version_path / model_filename
        
        with open(model_path, 'wb') as f:
            pickle.dump(result.model, f)
        
        # Save metadata
        metadata = {
            'version': version,
            'model_type': result.model_type,
            'target': result.target,
            'metrics': {
                'accuracy': result.accuracy,
                'precision': result.precision,
                'recall': result.recall,
                'f1': result.f1,
                'roc_auc': result.roc_auc,
                'profit_factor': result.profit_factor,
                'avg_return': result.avg_return,
                'win_rate': result.win_rate,
            },
            'n_train_samples': result.n_train_samples,
            'n_test_samples': result.n_test_samples,
            'train_time_seconds': result.train_time_seconds,
            'top_features': dict(list(result.feature_importance.items())[:20]),
            'created_at': datetime.now().isoformat(),
        }
        
        metadata_path = version_path / f"metadata_{result.target}.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Model saved: {model_path}")
        
        return str(model_path)
    
    def load_model(
        self, 
        version: str, 
        target: str = 'long'
    ) -> Tuple[Any, Dict]:
        """
        Load model and metadata.
        
        Args:
            version: Model version
            target: 'long' or 'short'
        
        Returns:
            Tuple of (model, metadata)
        """
        version_path = self.base_path / version
        
        # Find model file
        model_files = list(version_path.glob(f"entry_{target}_*.pkl"))
        if not model_files:
            raise FileNotFoundError(f"No model found for {target} in {version}")
        
        model_path = model_files[0]
        
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        
        # Load metadata
        metadata_path = version_path / f"metadata_{target}.json"
        metadata = {}
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        
        return model, metadata
    
    def get_latest_version(self) -> Optional[str]:
        """Get the latest model version"""
        versions = sorted([
            d.name for d in self.base_path.iterdir() 
            if d.is_dir() and d.name[0].isdigit()
        ], reverse=True)
        
        return versions[0] if versions else None
    
    def list_versions(self) -> List[Dict]:
        """List all available model versions"""
        versions = []
        
        for version_dir in self.base_path.iterdir():
            if not version_dir.is_dir():
                continue
            
            metadata_files = list(version_dir.glob("metadata_*.json"))
            for meta_file in metadata_files:
                with open(meta_file, 'r') as f:
                    metadata = json.load(f)
                    versions.append(metadata)
        
        return sorted(versions, key=lambda x: x.get('created_at', ''), reverse=True)


def print_evaluation_report(metrics: Dict[str, float], target: str):
    """Print evaluation metrics in a nice format"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║          MODEL EVALUATION: {target.upper()} ENTRY                     
╠══════════════════════════════════════════════════════════════╣
║  Classification Metrics:                                     
║    Accuracy:      {metrics.get('accuracy', 0)*100:>6.2f}%                           
║    Precision:     {metrics.get('precision', 0)*100:>6.2f}%                           
║    Recall:        {metrics.get('recall', 0)*100:>6.2f}%                           
║    F1 Score:      {metrics.get('f1', 0)*100:>6.2f}%                           
║    ROC AUC:       {metrics.get('roc_auc', 0):>6.4f}                            
╠══════════════════════════════════════════════════════════════╣
║  Trading Metrics:                                            
║    Win Rate:      {metrics.get('win_rate', 0)*100:>6.2f}%                           
║    Avg Return:    {metrics.get('avg_return', 0):>6.2f}%                           
║    Profit Factor: {metrics.get('profit_factor', 0):>6.2f}                            
║    N Trades:      {metrics.get('n_trades', 0):>6}                              
╚══════════════════════════════════════════════════════════════╝
    """)
