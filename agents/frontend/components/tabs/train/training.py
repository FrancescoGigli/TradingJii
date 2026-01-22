"""
🚀 Train Tab - Step 3: Training

Train XGBoost models:
- Load data from training_labels
- Manual mode: Custom hyperparameters
- Optuna mode: Automatic optimization
- Train LONG + SHORT models
- Calculate metrics (R², Spearman, Precision@K)
- Save models to shared/models/
"""

import streamlit as st
import pandas as pd
import numpy as np
import pickle
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, Callable

from database import get_connection

# Try imports - show helpful error if missing
try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    from scipy.stats import spearmanr
    from xgboost import XGBRegressor
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


# Feature columns from v_xgb_training VIEW (NO LOOK-AHEAD BIAS!)
# Only indicators available at entry time: rsi, atr, macd
FEATURE_COLUMNS_OHLCV = ['open', 'high', 'low', 'close', 'volume']

# Technical indicators from VIEW (limited to avoid look-ahead)
FEATURE_COLUMNS_INDICATORS = ['rsi', 'atr', 'macd']

# All features (OHLCV + Available Indicators)
FEATURE_COLUMNS = FEATURE_COLUMNS_OHLCV + FEATURE_COLUMNS_INDICATORS

# Optional: Extended features if using training_data directly
EXTENDED_FEATURE_COLUMNS = [
    'sma_20', 'sma_50', 'ema_12', 'ema_26',
    'bb_upper', 'bb_mid', 'bb_lower',
    'macd', 'macd_signal', 'macd_hist',
    'rsi', 'stoch_k', 'stoch_d',
    'atr', 'volume_sma', 'obv'
]


def get_model_dir() -> Path:
    """Get models directory path"""
    import os
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    
    if Path(shared_path).exists():
        model_dir = Path(shared_path) / "models"
    else:
        # Local development
        base = Path(__file__).parent.parent.parent.parent.parent
        model_dir = base / "shared" / "models"
    
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def get_training_labels_count(timeframe: str) -> int:
    """Get count of training labels"""
    conn = get_connection()
    if not conn:
        return 0
    try:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM training_labels WHERE timeframe=?', (timeframe,))
        return cur.fetchone()[0]
    except:
        return 0
    finally:
        conn.close()


def load_training_data(timeframe: str, progress_callback: Callable = None) -> pd.DataFrame:
    """
    Load training data from v_xgb_training VIEW.
    
    This VIEW contains:
    - OHLCV: open, high, low, close, volume
    - Indicators: rsi, atr, macd (NO LOOK-AHEAD!)
    - Labels: score_long, score_short, mfe, mae, bars_held, exit_type
    """
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        if progress_callback:
            progress_callback(0.1, "Loading data from v_xgb_training VIEW (no look-ahead)...")
        
        # Use the pre-defined VIEW for training - NO LOOK-AHEAD BIAS!
        df = pd.read_sql_query('''
            SELECT 
                timestamp, symbol, timeframe,
                open, high, low, close, volume,
                rsi, atr, macd,
                score_long, score_short,
                realized_return_long, realized_return_short,
                mfe_long, mfe_short,
                mae_long, mae_short,
                bars_held_long, bars_held_short,
                exit_type_long, exit_type_short,
                atr_pct
            FROM v_xgb_training
            WHERE timeframe = ?
            ORDER BY symbol, timestamp
        ''', conn, params=(timeframe,))
        
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        if progress_callback:
            progress_callback(0.2, f"Loaded {len(df):,} samples from VIEW (8 features, no look-ahead)")
        
        return df
    except Exception as e:
        if progress_callback:
            progress_callback(0.2, f"Error: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()


def prepare_features(df: pd.DataFrame, progress_callback: Callable = None) -> Tuple:
    """Prepare features and targets for training"""
    
    if progress_callback:
        progress_callback(0.3, "Preparing features...")
    
    # Get available features
    available_features = [c for c in FEATURE_COLUMNS if c in df.columns]
    
    X = df[available_features].copy()
    y_long = df['score_long'].copy()
    y_short = df['score_short'].copy()
    timestamps = df['timestamp'].copy()
    
    # Remove any remaining NaN
    valid_mask = ~(X.isna().any(axis=1) | y_long.isna() | y_short.isna())
    X = X[valid_mask]
    y_long = y_long[valid_mask]
    y_short = y_short[valid_mask]
    timestamps = timestamps[valid_mask]
    
    if progress_callback:
        progress_callback(0.4, f"Prepared {len(X):,} samples with {len(available_features)} features")
    
    return X, y_long, y_short, timestamps, available_features


def calculate_ranking_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Calculate ranking metrics including Spearman and Precision@K"""
    spearman_corr, spearman_pval = spearmanr(y_pred, y_true)
    
    metrics = {
        'spearman_corr': spearman_corr,
        'spearman_pval': spearman_pval,
    }
    
    # Calculate Precision@K for various K values
    for k_pct in [1, 5, 10, 20]:
        k = max(1, int(len(y_pred) * k_pct / 100))
        top_k_idx = np.argsort(y_pred)[-k:]
        
        if hasattr(y_true, 'iloc'):
            top_k_true = y_true.iloc[top_k_idx]
        else:
            top_k_true = y_true[top_k_idx]
        
        metrics[f'top{k_pct}pct_avg_score'] = float(np.mean(top_k_true))
        metrics[f'top{k_pct}pct_positive'] = float((top_k_true > 0).mean() * 100)
    
    return metrics


def train_xgb_models(
    timeframe: str,
    params: dict,
    train_ratio: float = 0.8,
    progress_callback: Callable = None
) -> Dict[str, Any]:
    """Train XGBoost models for LONG and SHORT"""
    
    if not SKLEARN_AVAILABLE:
        return {'error': 'sklearn/xgboost not installed'}
    
    # Load data
    df = load_training_data(timeframe, progress_callback)
    
    if len(df) == 0:
        return {'error': 'No training data found'}
    
    # Prepare features
    X, y_long, y_short, timestamps, feature_names = prepare_features(df, progress_callback)
    
    if len(X) < 100:
        return {'error': f'Not enough samples ({len(X)}). Need at least 100.'}
    
    # Temporal split
    split_idx = int(len(X) * train_ratio)
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_long_train, y_long_test = y_long.iloc[:split_idx], y_long.iloc[split_idx:]
    y_short_train, y_short_test = y_short.iloc[:split_idx], y_short.iloc[split_idx:]
    ts_train, ts_test = timestamps.iloc[:split_idx], timestamps.iloc[split_idx:]
    
    if progress_callback:
        progress_callback(0.45, f"Split: {len(X_train):,} train / {len(X_test):,} test")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # XGBoost parameters
    xgb_params = {
        'objective': 'reg:squarederror',
        'eval_metric': 'rmse',
        'tree_method': 'hist',
        'verbosity': 0,
        'random_state': 42,
        **params
    }
    
    # Train LONG model
    if progress_callback:
        progress_callback(0.5, "Training LONG model...")
    
    model_long = XGBRegressor(**xgb_params)
    model_long.fit(X_train_scaled, y_long_train, 
                   eval_set=[(X_test_scaled, y_long_test)], verbose=False)
    
    y_pred_long = model_long.predict(X_test_scaled)
    
    metrics_long = {
        'test_r2': r2_score(y_long_test, y_pred_long),
        'test_rmse': np.sqrt(mean_squared_error(y_long_test, y_pred_long)),
        'test_mae': mean_absolute_error(y_long_test, y_pred_long),
        'ranking': calculate_ranking_metrics(y_long_test, y_pred_long)
    }
    
    # Train SHORT model
    if progress_callback:
        progress_callback(0.75, "Training SHORT model...")
    
    model_short = XGBRegressor(**xgb_params)
    model_short.fit(X_train_scaled, y_short_train,
                    eval_set=[(X_test_scaled, y_short_test)], verbose=False)
    
    y_pred_short = model_short.predict(X_test_scaled)
    
    metrics_short = {
        'test_r2': r2_score(y_short_test, y_pred_short),
        'test_rmse': np.sqrt(mean_squared_error(y_short_test, y_pred_short)),
        'test_mae': mean_absolute_error(y_short_test, y_pred_short),
        'ranking': calculate_ranking_metrics(y_short_test, y_pred_short)
    }
    
    # Save models
    if progress_callback:
        progress_callback(0.9, "Saving models...")
    
    model_dir = get_model_dir()
    version = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    with open(model_dir / f"model_long_{version}.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(model_dir / f"model_short_{version}.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(model_dir / f"scaler_{version}.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save as latest
    with open(model_dir / "model_long_latest.pkl", 'wb') as f:
        pickle.dump(model_long, f)
    with open(model_dir / "model_short_latest.pkl", 'wb') as f:
        pickle.dump(model_short, f)
    with open(model_dir / "scaler_latest.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save metadata
    metadata = {
        'version': version,
        'created_at': datetime.now().isoformat(),
        'timeframe': timeframe,
        'feature_names': feature_names,
        'n_features': len(feature_names),
        'xgboost_params': xgb_params,
        'train_ratio': train_ratio,
        'metrics_long': metrics_long,
        'metrics_short': metrics_short,
        'data_range': {
            'train_start': str(ts_train.iloc[0]),
            'train_end': str(ts_train.iloc[-1]),
            'test_start': str(ts_test.iloc[0]),
            'test_end': str(ts_test.iloc[-1]),
        },
        'n_train_samples': len(X_train),
        'n_test_samples': len(X_test),
    }
    
    with open(model_dir / f"metadata_{version}.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    with open(model_dir / "metadata_latest.json", 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    
    if progress_callback:
        progress_callback(1.0, "Training complete!")
    
    return {
        'success': True,
        'version': version,
        'metrics_long': metrics_long,
        'metrics_short': metrics_short,
        'n_features': len(feature_names),
        'n_train': len(X_train),
        'n_test': len(X_test)
    }


def render_training_step():
    """Render Step 3: XGBoost training"""
    
    st.markdown("### 🚀 Step 3: Training")
    st.caption("Train XGBoost models for score prediction")
    
    # Check dependencies
    if not SKLEARN_AVAILABLE:
        st.error("❌ **Missing Dependencies!**")
        st.code("pip install scikit-learn xgboost scipy", language="bash")
        return
    
    # Check prerequisite
    labels_15m = get_training_labels_count('15m')
    labels_1h = get_training_labels_count('1h')
    
    if labels_15m == 0 and labels_1h == 0:
        st.error("❌ **No training labels available!**")
        st.info("Complete **Step 2 (Labeling)** first to generate training labels.")
        return
    
    # Show available data
    st.markdown("#### 📥 Available Training Labels")
    c1, c2 = st.columns(2)
    c1.metric("15m Samples", f"{labels_15m:,}")
    c2.metric("1h Samples", f"{labels_1h:,}")
    
    # === CONFIGURATION ===
    st.divider()
    st.markdown("#### ⚙️ Training Configuration")
    
    # Timeframe selection
    selected_tf = st.selectbox("Select Timeframe", ["15m", "1h"], key="train_tf_select")
    
    # Mode selection
    training_mode = st.radio(
        "Training Mode",
        ["Manual", "Optuna (Auto)"],
        horizontal=True,
        key="training_mode"
    )
    
    # Parameters expander
    with st.expander("🔧 XGBoost Parameters", expanded=True):
        
        if training_mode == "Manual":
            col1, col2 = st.columns(2)
            
            with col1:
                n_estimators = st.slider("n_estimators", 100, 1500, 500, 100, key="n_estimators")
                max_depth = st.slider("max_depth", 3, 12, 6, 1, key="max_depth")
                learning_rate = st.slider("learning_rate", 0.01, 0.3, 0.05, 0.01, key="learning_rate")
            
            with col2:
                min_child_weight = st.slider("min_child_weight", 1, 30, 10, 1, key="min_child_weight")
                subsample = st.slider("subsample", 0.5, 1.0, 0.8, 0.05, key="subsample")
                colsample_bytree = st.slider("colsample_bytree", 0.5, 1.0, 0.8, 0.05, key="colsample")
            
            params = {
                'n_estimators': n_estimators,
                'max_depth': max_depth,
                'learning_rate': learning_rate,
                'min_child_weight': min_child_weight,
                'subsample': subsample,
                'colsample_bytree': colsample_bytree
            }
        else:
            st.info("🔮 **Optuna Mode**: Automatically finds the best hyperparameters using TPE sampler.")
            n_trials = st.slider("Number of Trials", 10, 100, 30, 10, key="n_trials")
            st.caption("More trials = better results but takes longer")
    
    # Train ratio
    train_ratio = st.slider("Train/Test Split", 0.6, 0.9, 0.8, 0.05, key="train_ratio")
    st.caption(f"Train: {int(train_ratio*100)}% | Test: {int((1-train_ratio)*100)}%")
    
    # === TRAINING BUTTON ===
    st.divider()
    
    if training_mode == "Manual":
        if st.button("🚀 Start Training", use_container_width=True, type="primary"):
            st.session_state['start_training'] = True
    else:
        if st.button("🔮 Start Optuna Optimization", use_container_width=True, type="primary"):
            st.warning("⚠️ Optuna optimization coming soon. Using Manual mode for now.")
            st.session_state['start_training'] = True
    
    # === TRAINING PROCESS ===
    if st.session_state.get('start_training'):
        st.divider()
        st.markdown(f"#### 🔄 Training ({selected_tf})")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(pct, message):
            progress_bar.progress(pct)
            status_text.text(message)
        
        result = train_xgb_models(
            timeframe=selected_tf,
            params=params if training_mode == "Manual" else {},
            train_ratio=train_ratio,
            progress_callback=update_progress
        )
        
        if result.get('success'):
            st.success(f"✅ Training complete! Version: `{result['version']}`")
            
            # Show metrics
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**LONG Model:**")
                st.metric("R²", f"{result['metrics_long']['test_r2']:.4f}")
                st.metric("RMSE", f"{result['metrics_long']['test_rmse']:.6f}")
                st.metric("Spearman", f"{result['metrics_long']['ranking']['spearman_corr']:.4f}")
            
            with col2:
                st.markdown("**SHORT Model:**")
                st.metric("R²", f"{result['metrics_short']['test_r2']:.4f}")
                st.metric("RMSE", f"{result['metrics_short']['test_rmse']:.6f}")
                st.metric("Spearman", f"{result['metrics_short']['ranking']['spearman_corr']:.4f}")
            
            # Precision@K
            st.markdown("---")
            st.markdown("**Precision@K (LONG):**")
            
            prec_data = []
            for k in [1, 5, 10, 20]:
                prec_data.append({
                    'Top K%': f"{k}%",
                    'Avg Score': f"{result['metrics_long']['ranking'][f'top{k}pct_avg_score']:.5f}",
                    '% Positive': f"{result['metrics_long']['ranking'][f'top{k}pct_positive']:.1f}%"
                })
            
            st.dataframe(pd.DataFrame(prec_data), use_container_width=True, hide_index=True)
        else:
            st.error(f"❌ {result.get('error', 'Unknown error')}")
        
        st.session_state['start_training'] = False


__all__ = ['render_training_step']
