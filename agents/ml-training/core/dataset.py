"""
📊 Dataset Builder for ML Training

Builds training datasets with proper temporal splits, embargo periods,
and data validation. Prevents lookahead bias.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Generator
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class DataSplit:
    """Container for a train/val/test split"""
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    val_start: pd.Timestamp
    val_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    split_idx: int


class TemporalSplitter:
    """
    Creates temporal train/validation/test splits with embargo.
    
    Implements proper temporal cross-validation for time series
    to prevent lookahead bias.
    """
    
    def __init__(
        self,
        n_splits: int = 5,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        embargo_bars: int = 48,
        purge_bars: int = 24
    ):
        """
        Initialize temporal splitter.
        
        Args:
            n_splits: Number of walk-forward splits
            train_ratio: Ratio of data for training
            val_ratio: Ratio of data for validation
            test_ratio: Ratio of data for testing
            embargo_bars: Bars between train and test
            purge_bars: Bars to remove at end of train (label dependency)
        """
        self.n_splits = n_splits
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.embargo_bars = embargo_bars
        self.purge_bars = purge_bars
    
    def get_splits(
        self, 
        df: pd.DataFrame
    ) -> Generator[DataSplit, None, None]:
        """
        Generate temporal splits for walk-forward validation.
        
        Args:
            df: DataFrame with DatetimeIndex
        
        Yields:
            DataSplit objects with train/val/test boundaries
        """
        n = len(df)
        
        # For walk-forward: each split uses expanding window
        # or sliding window of fixed size
        
        # Calculate base split size
        split_size = n // (self.n_splits + 1)  # +1 for initial train
        
        for i in range(self.n_splits):
            # Training: from start to split point
            train_end_idx = split_size * (i + 1)
            
            # Purge: remove last purge_bars from train
            train_end_idx -= self.purge_bars
            
            # Test start: after embargo
            test_start_idx = train_end_idx + self.embargo_bars
            
            # Test end: next split or end of data
            test_end_idx = min(split_size * (i + 2), n - 1)
            
            # Validation: last portion of training data
            val_size = int((train_end_idx - 0) * self.val_ratio / (1 - self.test_ratio))
            val_start_idx = train_end_idx - val_size
            
            # Ensure valid indices
            if test_start_idx >= n or test_end_idx <= test_start_idx:
                continue
            
            yield DataSplit(
                train_start=df.index[0],
                train_end=df.index[train_end_idx],
                val_start=df.index[val_start_idx],
                val_end=df.index[train_end_idx],
                test_start=df.index[test_start_idx],
                test_end=df.index[test_end_idx],
                split_idx=i
            )
    
    def split(
        self, 
        X: pd.DataFrame, 
        y: pd.Series
    ) -> Generator[Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame, pd.Series], None, None]:
        """
        Split features and labels into train/val/test sets.
        
        Args:
            X: Features DataFrame
            y: Labels Series
        
        Yields:
            Tuple of (X_train, y_train, X_val, y_val, X_test, y_test)
        """
        for split in self.get_splits(X):
            # Training data (excluding validation)
            train_mask = (X.index >= split.train_start) & (X.index < split.val_start)
            X_train = X.loc[train_mask]
            y_train = y.loc[train_mask]
            
            # Validation data
            val_mask = (X.index >= split.val_start) & (X.index <= split.val_end)
            X_val = X.loc[val_mask]
            y_val = y.loc[val_mask]
            
            # Test data
            test_mask = (X.index >= split.test_start) & (X.index <= split.test_end)
            X_test = X.loc[test_mask]
            y_test = y.loc[test_mask]
            
            yield X_train, y_train, X_val, y_val, X_test, y_test


class DatasetBuilder:
    """
    Builds ML-ready datasets from features and labels.
    
    Handles:
    - Feature validation and cleaning
    - Label alignment
    - Sample weighting
    - Multi-asset pooling
    """
    
    def __init__(
        self,
        max_nan_ratio: float = 0.1,
        drop_correlated: bool = True,
        correlation_threshold: float = 0.95
    ):
        """
        Initialize dataset builder.
        
        Args:
            max_nan_ratio: Maximum allowed NaN ratio per feature
            drop_correlated: Whether to drop highly correlated features
            correlation_threshold: Threshold for correlation filtering
        """
        self.max_nan_ratio = max_nan_ratio
        self.drop_correlated = drop_correlated
        self.correlation_threshold = correlation_threshold
        self.feature_names: List[str] = []
        self.dropped_features: List[str] = []
    
    def validate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate and clean features.
        
        Args:
            df: Features DataFrame
        
        Returns:
            Cleaned DataFrame
        """
        initial_cols = df.columns.tolist()
        
        # Drop features with too many NaNs
        nan_ratio = df.isna().mean()
        valid_features = nan_ratio[nan_ratio <= self.max_nan_ratio].index
        df = df[valid_features]
        
        dropped_nan = set(initial_cols) - set(df.columns)
        if dropped_nan:
            logger.info(f"Dropped {len(dropped_nan)} features due to NaN ratio")
        
        # Drop constant features
        constant_cols = df.columns[df.nunique() <= 1]
        df = df.drop(columns=constant_cols)
        
        if len(constant_cols) > 0:
            logger.info(f"Dropped {len(constant_cols)} constant features")
        
        # Drop highly correlated features
        if self.drop_correlated and len(df.columns) > 1:
            df = self._drop_correlated_features(df)
        
        self.dropped_features = list(set(initial_cols) - set(df.columns))
        self.feature_names = df.columns.tolist()
        
        return df
    
    def _drop_correlated_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Drop highly correlated features"""
        # Compute correlation matrix
        corr_matrix = df.corr().abs()
        
        # Get upper triangle
        upper = corr_matrix.where(
            np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
        )
        
        # Find columns to drop
        to_drop = [
            column for column in upper.columns 
            if any(upper[column] > self.correlation_threshold)
        ]
        
        if to_drop:
            logger.info(f"Dropped {len(to_drop)} correlated features")
            df = df.drop(columns=to_drop)
        
        return df
    
    def build_dataset(
        self,
        features: pd.DataFrame,
        labels: pd.DataFrame,
        target_col: str = 'y_long',
        sample_weight_col: Optional[str] = None
    ) -> Tuple[pd.DataFrame, pd.Series, Optional[pd.Series]]:
        """
        Build training dataset from features and labels.
        
        Args:
            features: Features DataFrame
            labels: Labels DataFrame
            target_col: Target column name in labels
            sample_weight_col: Optional column for sample weights
        
        Returns:
            Tuple of (X, y, sample_weights)
        """
        # Align indices
        common_idx = features.index.intersection(labels.index)
        features = features.loc[common_idx]
        labels = labels.loc[common_idx]
        
        # Validate features
        X = self.validate_features(features)
        
        # Get target
        y = labels[target_col]
        
        # Remove rows with invalid labels
        valid_mask = ~y.isna()
        X = X.loc[valid_mask]
        y = y.loc[valid_mask]
        
        # Fill remaining NaNs with 0 (after validation)
        X = X.fillna(0)
        
        # Sample weights
        sample_weights = None
        if sample_weight_col and sample_weight_col in labels.columns:
            sample_weights = labels.loc[valid_mask, sample_weight_col]
        
        logger.info(f"Dataset built: {len(X)} samples, {len(X.columns)} features")
        logger.info(f"Label distribution: {y.value_counts().to_dict()}")
        
        return X, y, sample_weights
    
    def pool_multi_asset(
        self,
        asset_datasets: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Pool datasets from multiple assets.
        
        Args:
            asset_datasets: Dict of {symbol: (features, labels)}
        
        Returns:
            Tuple of (pooled_features, pooled_labels)
        """
        all_features = []
        all_labels = []
        
        for symbol, (features, labels) in asset_datasets.items():
            # Add symbol identifier
            features = features.copy()
            features['_symbol'] = symbol
            
            labels = labels.copy()
            labels['_symbol'] = symbol
            
            all_features.append(features)
            all_labels.append(labels)
        
        pooled_features = pd.concat(all_features, axis=0)
        pooled_labels = pd.concat(all_labels, axis=0)
        
        # Sort by timestamp
        pooled_features = pooled_features.sort_index()
        pooled_labels = pooled_labels.sort_index()
        
        logger.info(f"Pooled {len(asset_datasets)} assets: {len(pooled_features)} total samples")
        
        return pooled_features, pooled_labels


def compute_sample_weights(
    labels: pd.DataFrame,
    volatility_col: str = 'tp_pct'
) -> pd.Series:
    """
    Compute sample weights based on volatility regime.
    
    Higher weights for:
    - Samples in different volatility regimes (diversity)
    - More recent samples (temporal relevance)
    
    Args:
        labels: Labels DataFrame with volatility info
        volatility_col: Column to use for volatility weighting
    
    Returns:
        Series of sample weights
    """
    weights = pd.Series(1.0, index=labels.index)
    
    if volatility_col in labels.columns:
        # Normalize volatility to [0.5, 1.5] range
        vol = labels[volatility_col]
        vol_norm = (vol - vol.min()) / (vol.max() - vol.min() + 1e-8)
        vol_weight = 0.5 + vol_norm  # Range [0.5, 1.5]
        weights *= vol_weight
    
    # Time-based weighting (more recent = higher weight)
    n = len(weights)
    time_weight = np.linspace(0.8, 1.2, n)
    weights *= time_weight
    
    # Normalize to mean=1
    weights = weights / weights.mean()
    
    return weights
