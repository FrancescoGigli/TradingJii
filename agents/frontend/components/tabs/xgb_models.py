"""
🤖 XGBoost Models Tab - ML Training Results Dashboard

Displays:
- Trained model versions
- Regression metrics (R², RMSE, MAE)
- Ranking Metrics (Spearman, Precision@K)
- Feature Importance
- Training metadata
"""

import streamlit as st
import json
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go


# ═══════════════════════════════════════════════════════════════════════════════
# PATH CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

def get_models_dir():
    """Get models directory path (works in Docker and locally)"""
    shared_path = os.environ.get('SHARED_DATA_PATH')
    if shared_path:
        return Path(shared_path) / "models"
    else:
        return Path(__file__).parent.parent.parent.parent.parent / "shared" / "models"


MODELS_DIR = get_models_dir()


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_metadata(model_version: str = "latest") -> dict:
    """Load model metadata from JSON file"""
    metadata_path = MODELS_DIR / f"metadata_{model_version}.json"
    
    if not metadata_path.exists():
        return None
    
    with open(metadata_path, 'r') as f:
        return json.load(f)


def get_available_models() -> list:
    """Get list of available model versions"""
    if not MODELS_DIR.exists():
        return []
    
    versions = []
    for f in MODELS_DIR.glob("metadata_*.json"):
        version = f.stem.replace("metadata_", "")
        versions.append(version)
    
    # Sort by date (most recent first), keep 'latest' at top
    versions = sorted([v for v in versions if v != 'latest'], reverse=True)
    if (MODELS_DIR / "metadata_latest.json").exists():
        versions.insert(0, "latest")
    
    return versions


def get_signal_quality(spearman: float) -> tuple:
    """Get signal quality label and color based on Spearman correlation"""
    if spearman > 0.10:
        return "🟢 EXCELLENT", "green"
    elif spearman > 0.05:
        return "🟡 GOOD", "yellow"
    elif spearman > 0.02:
        return "🟠 WEAK", "orange"
    else:
        return "🔴 NO SIGNAL", "red"


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def render_xgb_models_tab():
    """Main render function for XGBoost Models tab"""
    
    # Header
    st.markdown("## 🤖 XGBoost Models Dashboard")
    st.caption("ML models trained to predict score_long and score_short")
    
    # Check if models directory exists
    if not MODELS_DIR.exists():
        st.warning(f"⚠️ Models directory not found: {MODELS_DIR}")
        st.info("💡 Run training to create models: `python agents/ml-training/train.py`")
        return
    
    # Get available models
    versions = get_available_models()
    
    if not versions:
        st.warning("⚠️ No models found")
        st.info("💡 Run training to create models: `python agents/ml-training/train.py`")
        return
    
    # Model selector
    col1, col2 = st.columns([2, 4])
    
    with col1:
        selected_version = st.selectbox(
            "📦 Select Model Version",
            versions,
            format_func=lambda x: f"🕐 Latest" if x == "latest" else f"📅 {x[:8]}_{x[9:]}"
        )
    
    # Load metadata
    metadata = load_metadata(selected_version)
    
    if not metadata:
        st.error(f"❌ Failed to load metadata for version: {selected_version}")
        return
    
    st.divider()
    
    # ================================================================
    # TRAINING OVERVIEW
    # ================================================================
    
    st.markdown("### 📊 Training Overview")
    
    m1, m2, m3, m4 = st.columns(4)
    
    n_features = metadata.get('n_features', 0)
    m1.metric("Features Used", str(n_features))
    
    created = metadata.get('created_at', 'N/A')
    if created != 'N/A':
        try:
            dt = datetime.fromisoformat(created)
            created_display = dt.strftime("%Y-%m-%d")
        except:
            created_display = created[:10] if len(created) > 10 else created
    else:
        created_display = 'N/A'
    m2.metric("Training Date", created_display)
    
    train_ratio = metadata.get('train_ratio', 0.8)
    m3.metric("Train/Test Split", f"{int(train_ratio*100)}/{int((1-train_ratio)*100)}%")
    
    n_estimators = metadata.get('xgboost_params', {}).get('n_estimators', 'N/A')
    m4.metric("N° Trees", str(n_estimators))
    
    st.divider()
    
    # ================================================================
    # MODEL PERFORMANCE - REGRESSION METRICS
    # ================================================================
    
    st.markdown("### 🎯 Regression Metrics")
    st.caption("Train vs Test performance for LONG and SHORT models")
    
    metrics_long = metadata.get('metrics_long', {})
    metrics_short = metadata.get('metrics_short', {})
    
    # Create regression metrics table
    regression_data = []
    
    for metric, key, fmt in [
        ('R² Score', 'train_r2', '.4f'),
        ('R² Score', 'test_r2', '.4f'),
        ('RMSE', 'train_rmse', '.6f'),
        ('RMSE', 'test_rmse', '.6f'),
        ('MAE', 'train_mae', '.6f'),
        ('MAE', 'test_mae', '.6f'),
    ]:
        split = 'Train' if 'train' in key else 'Test'
        regression_data.append({
            'Metric': metric,
            'Split': split,
            '📈 LONG': f'{metrics_long.get(key, 0):{fmt}}',
            '📉 SHORT': f'{metrics_short.get(key, 0):{fmt}}'
        })
    
    df_regression = pd.DataFrame(regression_data)
    df_regression = df_regression.set_index(['Metric', 'Split'])
    st.table(df_regression)
    
    st.divider()
    
    # ================================================================
    # RANKING METRICS
    # ================================================================
    
    st.markdown("### 🎯 Ranking Metrics")
    st.caption("How well does the model rank trading opportunities? (Most important for trading!)")
    
    ranking_long = metrics_long.get('ranking', {})
    ranking_short = metrics_short.get('ranking', {})
    
    col_long, col_short = st.columns(2)
    
    # LONG Model Spearman
    with col_long:
        spearman_long = ranking_long.get('spearman_corr', 0)
        pval_long = ranking_long.get('spearman_pval', 1)
        quality_long, color_long = get_signal_quality(spearman_long)
        
        st.markdown("#### 📈 LONG Model")
        st.metric("Spearman Correlation", f"{spearman_long:.4f}")
        st.caption(f"p-value: {pval_long:.2e}")
        st.info(f"Signal Quality: **{quality_long}**")
    
    # SHORT Model Spearman
    with col_short:
        spearman_short = ranking_short.get('spearman_corr', 0)
        pval_short = ranking_short.get('spearman_pval', 1)
        quality_short, color_short = get_signal_quality(spearman_short)
        
        st.markdown("#### 📉 SHORT Model")
        st.metric("Spearman Correlation", f"{spearman_short:.4f}")
        st.caption(f"p-value: {pval_short:.2e}")
        st.info(f"Signal Quality: **{quality_short}**")
    
    # Signal Quality Guide
    with st.expander("📖 Signal Quality Guide"):
        st.markdown("""
        | Quality | Spearman Range | Meaning |
        |---------|----------------|---------|
        | 🟢 EXCELLENT | > 0.10 | Strong ranking signal |
        | 🟡 GOOD | 0.05 - 0.10 | Useful ranking signal |
        | 🟠 WEAK | 0.02 - 0.05 | Marginal signal |
        | 🔴 NO SIGNAL | < 0.02 | No predictive power |
        """)
    
    st.divider()
    
    # ================================================================
    # PRECISION@K ANALYSIS
    # ================================================================
    
    st.markdown("### 📊 Precision@K Analysis")
    st.caption("If I only trade the top K% of predictions, how good are they?")
    
    # Build Precision@K table
    precision_rows = []
    for k in [1, 5, 10, 20]:
        precision_rows.append({
            'Top K%': f'{k}%',
            'LONG Avg Score': f'{ranking_long.get(f"top{k}pct_avg_score", 0):.6f}',
            'LONG % Positive': f'{ranking_long.get(f"top{k}pct_positive", 0):.1f}%',
            'SHORT Avg Score': f'{ranking_short.get(f"top{k}pct_avg_score", 0):.6f}',
            'SHORT % Positive': f'{ranking_short.get(f"top{k}pct_positive", 0):.1f}%'
        })
    
    df_precision = pd.DataFrame(precision_rows)
    df_precision = df_precision.set_index('Top K%')
    st.table(df_precision)
    
    # Visualization
    st.markdown("#### 📈 Top K% Average Score Comparison")
    
    fig = go.Figure()
    
    scores_long = [ranking_long.get(f'top{k}pct_avg_score', 0) for k in [1, 5, 10, 20]]
    scores_short = [ranking_short.get(f'top{k}pct_avg_score', 0) for k in [1, 5, 10, 20]]
    
    fig.add_trace(go.Bar(
        name='LONG',
        x=['1%', '5%', '10%', '20%'],
        y=scores_long,
        marker_color='#10B981',
        text=[f'{s:.4f}' for s in scores_long],
        textposition='outside'
    ))
    
    fig.add_trace(go.Bar(
        name='SHORT',
        x=['1%', '5%', '10%', '20%'],
        y=scores_short,
        marker_color='#EF4444',
        text=[f'{s:.4f}' for s in scores_short],
        textposition='outside'
    ))
    
    fig.update_layout(
        barmode='group',
        template='plotly_dark',
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
        yaxis_title='Average True Score',
        xaxis_title='Top Prediction Percentile',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation='h', y=1.1, x=0.5, xanchor='center')
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # ================================================================
    # COMPLETE METRICS SUMMARY TABLE
    # ================================================================
    
    st.markdown("### 📋 Complete Metrics Summary")
    st.caption("All metrics in one table for easy comparison")
    
    # Build comprehensive summary table
    summary_rows = []
    
    # Regression metrics
    for name, key, fmt in [
        ('Train R²', 'train_r2', '.4f'),
        ('Test R²', 'test_r2', '.4f'),
        ('Train RMSE', 'train_rmse', '.6f'),
        ('Test RMSE', 'test_rmse', '.6f'),
        ('Train MAE', 'train_mae', '.6f'),
        ('Test MAE', 'test_mae', '.6f'),
    ]:
        summary_rows.append({
            'Category': 'Regression',
            'Metric': name,
            '📈 LONG': f'{metrics_long.get(key, 0):{fmt}}',
            '📉 SHORT': f'{metrics_short.get(key, 0):{fmt}}'
        })
    
    # Ranking metrics
    summary_rows.append({
        'Category': 'Ranking',
        'Metric': 'Spearman Corr',
        '📈 LONG': f'{ranking_long.get("spearman_corr", 0):.4f}',
        '📉 SHORT': f'{ranking_short.get("spearman_corr", 0):.4f}'
    })
    summary_rows.append({
        'Category': 'Ranking',
        'Metric': 'Spearman p-value',
        '📈 LONG': f'{ranking_long.get("spearman_pval", 1):.2e}',
        '📉 SHORT': f'{ranking_short.get("spearman_pval", 1):.2e}'
    })
    
    # Precision@K
    for k in [1, 5, 10, 20]:
        summary_rows.append({
            'Category': f'Precision@{k}%',
            'Metric': 'Avg Score',
            '📈 LONG': f'{ranking_long.get(f"top{k}pct_avg_score", 0):.6f}',
            '📉 SHORT': f'{ranking_short.get(f"top{k}pct_avg_score", 0):.6f}'
        })
        summary_rows.append({
            'Category': f'Precision@{k}%',
            'Metric': '% Positive',
            '📈 LONG': f'{ranking_long.get(f"top{k}pct_positive", 0):.1f}%',
            '📉 SHORT': f'{ranking_short.get(f"top{k}pct_positive", 0):.1f}%'
        })
    
    df_summary = pd.DataFrame(summary_rows)
    df_summary = df_summary.set_index(['Category', 'Metric'])
    st.table(df_summary)
    
    st.divider()
    
    # ================================================================
    # FEATURES LIST
    # ================================================================
    
    st.markdown("### 📋 Features Used in Training")
    
    feature_names = metadata.get('feature_names', [])
    
    if feature_names:
        # Categorize features
        categories = {
            '📊 OHLCV': ['open', 'high', 'low', 'close', 'volume'],
            '📈 Moving Averages': [f for f in feature_names if 'sma' in f.lower() or 'ema' in f.lower()],
            '📉 Bollinger Bands': [f for f in feature_names if 'bb_' in f.lower()],
            '⚡ Momentum': [f for f in feature_names if f in ['rsi', 'macd', 'macd_signal', 'macd_hist', 'stoch_k', 'stoch_d', 'rsi_14_norm', 'macd_hist_norm']],
            '🌊 Volatility': [f for f in feature_names if 'atr' in f.lower() or 'vol_' in f.lower()],
            '📦 Volume': [f for f in feature_names if 'obv' in f.lower() or 'volume' in f.lower() or 'vwap' in f.lower()],
            '📐 Returns': [f for f in feature_names if 'ret_' in f.lower()],
            '🎯 Trend': [f for f in feature_names if 'trend' in f.lower() or 'adx' in f.lower() or 'momentum' in f.lower()],
            '📍 Price Position': [f for f in feature_names if 'position' in f.lower() or 'dist_' in f.lower() or 'percentile' in f.lower()],
        }
        
        # Create feature summary table
        feature_rows = []
        for cat_name, cat_features in categories.items():
            actual_features = [f for f in cat_features if f in feature_names]
            if actual_features:
                feature_rows.append({
                    'Category': cat_name,
                    'Count': len(actual_features),
                    'Features': ', '.join(actual_features[:5]) + ('...' if len(actual_features) > 5 else '')
                })
        
        df_features = pd.DataFrame(feature_rows)
        df_features = df_features.set_index('Category')
        st.table(df_features)
        
        # Full feature list
        with st.expander("🔍 View All Features"):
            cols = st.columns(3)
            for idx, f in enumerate(sorted(feature_names)):
                col_idx = idx % 3
                cols[col_idx].markdown(f"• `{f}`")
    
    st.divider()
    
    # ================================================================
    # MODEL FILES
    # ================================================================
    
    st.markdown("### 💾 Model Files")
    
    model_files = []
    if MODELS_DIR.exists():
        patterns = [f"*_{selected_version}.*"]
        if selected_version == "latest":
            patterns.append("*_latest.*")
        
        for pattern in patterns:
            for f in sorted(MODELS_DIR.glob(pattern)):
                size_kb = f.stat().st_size / 1024
                model_files.append({
                    'File': f.name,
                    'Size': f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB",
                    'Type': f.suffix.upper()
                })
    
    if model_files:
        df_files = pd.DataFrame(model_files)
        df_files = df_files.set_index('File')
        st.table(df_files)
    else:
        st.info("No model files found for this version")
    
    st.caption(f"📁 Models Directory: `{MODELS_DIR}`")
    
    # ================================================================
    # XGBOOST PARAMETERS
    # ================================================================
    
    with st.expander("⚙️ XGBoost Hyperparameters"):
        params = metadata.get('xgboost_params', {})
        
        params_rows = []
        for key in ['max_depth', 'n_estimators', 'learning_rate', 'min_child_weight', 
                   'subsample', 'colsample_bytree', 'objective', 'eval_metric', 
                   'early_stopping_rounds', 'random_state']:
            params_rows.append({
                'Parameter': key,
                'Value': str(params.get(key, 'N/A'))
            })
        
        df_params = pd.DataFrame(params_rows)
        df_params = df_params.set_index('Parameter')
        st.table(df_params)
    
    # ================================================================
    # METRICS GUIDE
    # ================================================================
    
    with st.expander("📖 Metrics Guide - Understanding the Results"):
        st.markdown("""
        ### 🎯 Regression Metrics
        
        | Metric | Description | Interpretation |
        |--------|-------------|----------------|
        | **R²** | Coefficient of determination | % of variance explained. Low values (0.02-0.05) are normal in finance! |
        | **RMSE** | Root Mean Squared Error | Average prediction error. Lower = better |
        | **MAE** | Mean Absolute Error | Absolute average error |
        
        ### 📊 Ranking Metrics (Most Important!)
        
        | Metric | Description | Meaning |
        |--------|-------------|---------|
        | **Spearman Correlation** | Rank correlation | How well does the model RANK opportunities. 0.05+ = good! |
        | **Precision@K** | Top K% precision | If I take the top K% of predictions, how many are good? |
        
        ### 💡 Why is Low R² Okay?
        
        In financial markets, it's **impossible** to exactly predict future movements.
        An R² of 3% seems low, but it means the model has a **statistical edge**!
        
        **What matters is RANKING**: if the model says "A is better than B", 
        it should be correct more often than not → **Spearman Correlation**
        """)


# Export
__all__ = ['render_xgb_models_tab']
