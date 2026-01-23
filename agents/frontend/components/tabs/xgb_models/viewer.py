"""
📊 XGBoost Models - Model Viewer

View and analyze trained models:
- Training overview
- Regression metrics
- Ranking metrics
- Precision@K analysis
- Feature list
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import shutil
from pathlib import Path

from styles.tables import render_html_table

from .utils import (
    MODELS_DIR, load_metadata, get_available_models, 
    get_signal_quality, format_date, format_version, is_optuna_model
)


def delete_model(version: str) -> bool:
    """
    Delete a specific model version and all its associated files.
    
    Args:
        version: The version string to delete (e.g., 'v1', 'latest')
    
    Returns:
        True if successful, False otherwise
    """
    try:
        deleted_count = 0
        
        # Find all files matching the version
        patterns = [
            f"*_{version}.*",      # Standard files like model_long_v1.json
            f"*_{version}_*",      # Files with suffix after version
        ]
        
        files_to_delete = []
        for pattern in patterns:
            files_to_delete.extend(MODELS_DIR.glob(pattern))
        
        # Also check for exact version match in filename
        for f in MODELS_DIR.iterdir():
            if f.is_file():
                # Extract version from filename
                stem = f.stem
                parts = stem.split('_')
                if version in parts:
                    if f not in files_to_delete:
                        files_to_delete.append(f)
        
        # Delete the files
        for f in files_to_delete:
            if f.exists():
                f.unlink()
                deleted_count += 1
        
        return deleted_count > 0
        
    except Exception as e:
        st.error(f"Error deleting model: {e}")
        return False


def render_models_view_section():
    """Section for viewing existing models"""
    
    # Check if models directory exists
    if not MODELS_DIR.exists():
        st.warning(f"⚠️ Models directory not found: {MODELS_DIR}")
        st.info("💡 Run training to create models")
        return
    
    # Get available models
    versions = get_available_models()
    
    if not versions:
        st.warning("⚠️ No models found")
        st.info("💡 Train a model in the 'Train New Model' tab")
        return
    
    # Model selector
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        selected_version = st.selectbox(
            "📦 Select Model Version",
            versions,
            format_func=format_version
        )
    
    # Load metadata
    metadata = load_metadata(selected_version)
    
    if not metadata:
        st.error(f"❌ Failed to load metadata for version: {selected_version}")
        return
    
    # Show if Optuna model
    with col2:
        if is_optuna_model(metadata):
            st.markdown("""
            <div style="background: #8B5CF6; padding: 8px 15px; border-radius: 8px; margin-top: 5px;">
                <span style="color: white;">🎯 Optuna Auto-Tuned Model</span>
            </div>
            """, unsafe_allow_html=True)
    
    # Delete model button
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Use session state for delete confirmation
        delete_key = f"delete_confirm_{selected_version}"
        
        if delete_key not in st.session_state:
            st.session_state[delete_key] = False
        
        if not st.session_state[delete_key]:
            if st.button("🗑️ Delete Model", key=f"delete_btn_{selected_version}", type="secondary"):
                st.session_state[delete_key] = True
                st.rerun()
        else:
            st.warning(f"⚠️ Confirm delete **{selected_version}**?")
            col_yes, col_no = st.columns(2)
            
            with col_yes:
                if st.button("✅ Yes, Delete", key=f"confirm_del_{selected_version}", type="primary"):
                    if delete_model(selected_version):
                        st.success(f"✅ Model {selected_version} deleted!")
                        st.session_state[delete_key] = False
                        # Clear the session state and refresh
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete model")
                        st.session_state[delete_key] = False
            
            with col_no:
                if st.button("❌ Cancel", key=f"cancel_del_{selected_version}"):
                    st.session_state[delete_key] = False
                    st.rerun()
    
    st.divider()
    
    # Render sections
    _render_training_overview(metadata)
    st.divider()
    
    _render_regression_metrics(metadata)
    st.divider()
    
    _render_ranking_metrics(metadata)
    st.divider()
    
    _render_precision_analysis(metadata)
    st.divider()
    
    _render_complete_summary(metadata)
    st.divider()
    
    _render_features_list(metadata)
    st.divider()
    
    _render_model_files(selected_version)
    
    _render_parameters(metadata)
    
    _render_metrics_guide()


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

def _render_training_overview(metadata: dict):
    """Render training overview section"""
    st.markdown("### 📊 Training Overview")
    
    m1, m2, m3, m4 = st.columns(4)
    
    n_features = metadata.get('n_features', 0)
    m1.metric("Features Used", str(n_features))
    
    created = metadata.get('created_at', 'N/A')
    m2.metric("Training Date", format_date(created))
    
    # Handle different metadata formats
    if 'train_ratio' in metadata:
        train_ratio = metadata['train_ratio']
        m3.metric("Train/Test Split", f"{int(train_ratio*100)}/{int((1-train_ratio)*100)}%")
    elif 'split_ratios' in metadata:
        ratios = metadata['split_ratios']
        m3.metric("Split", f"{int(ratios.get('train', 0.7)*100)}/{int(ratios.get('val', 0.15)*100)}/{int(ratios.get('test', 0.15)*100)}%")
    else:
        m3.metric("Train/Test Split", "N/A")
    
    # Get n_estimators from different locations
    n_estimators = metadata.get('xgboost_params', {}).get('n_estimators', 
                   metadata.get('best_params_long', {}).get('n_estimators', 'N/A'))
    m4.metric("N° Trees", str(n_estimators))
    
    # Show n_trials if Optuna
    if is_optuna_model(metadata):
        st.info(f"🎯 **Optuna Trials:** {metadata.get('n_trials', 'N/A')} per model")


# ═══════════════════════════════════════════════════════════════════════════════
# REGRESSION METRICS
# ═══════════════════════════════════════════════════════════════════════════════

def _render_regression_metrics(metadata: dict):
    """Render regression metrics table"""
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
        val_long = metrics_long.get(key, 0)
        val_short = metrics_short.get(key, 0)
        
        # Skip if both are 0 (not available)
        if val_long == 0 and val_short == 0 and 'train' in key:
            continue
            
        regression_data.append({
            'Metric': metric,
            'Split': split,
            '📈 LONG': f'{val_long:{fmt}}',
            '📉 SHORT': f'{val_short:{fmt}}'
        })
    
    if regression_data:
        df_regression = pd.DataFrame(regression_data)
        render_html_table(df_regression, height=250)


# ═══════════════════════════════════════════════════════════════════════════════
# RANKING METRICS
# ═══════════════════════════════════════════════════════════════════════════════

def _render_ranking_metrics(metadata: dict):
    """Render ranking metrics section"""
    st.markdown("### 🎯 Ranking Metrics")
    st.caption("How well does the model rank trading opportunities? (Most important for trading!)")
    
    metrics_long = metadata.get('metrics_long', {})
    metrics_short = metadata.get('metrics_short', {})
    
    # Support both old format (nested 'ranking') and new format (direct keys)
    ranking_long = metrics_long.get('ranking', metrics_long)
    ranking_short = metrics_short.get('ranking', metrics_short)
    
    col_long, col_short = st.columns(2)
    
    # LONG Model Spearman
    with col_long:
        spearman_long = ranking_long.get('test_spearman', ranking_long.get('spearman_corr', 0))
        pval_long = ranking_long.get('test_spearman_pval', ranking_long.get('spearman_pval', 1))
        quality_long, color_long = get_signal_quality(spearman_long)
        
        st.markdown("#### 📈 LONG Model")
        st.metric("Spearman Correlation", f"{spearman_long:.4f}")
        st.caption(f"p-value: {pval_long:.2e}")
        st.info(f"Signal Quality: **{quality_long}**")
    
    # SHORT Model Spearman
    with col_short:
        spearman_short = ranking_short.get('test_spearman', ranking_short.get('spearman_corr', 0))
        pval_short = ranking_short.get('test_spearman_pval', ranking_short.get('spearman_pval', 1))
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


# ═══════════════════════════════════════════════════════════════════════════════
# PRECISION@K ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def _render_precision_analysis(metadata: dict):
    """Render Precision@K analysis with chart"""
    st.markdown("### 📊 Precision@K Analysis")
    st.caption("If I only trade the top K% of predictions, how good are they?")
    
    metrics_long = metadata.get('metrics_long', {})
    metrics_short = metadata.get('metrics_short', {})
    
    ranking_long = metrics_long.get('ranking', metrics_long)
    ranking_short = metrics_short.get('ranking', metrics_short)
    
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
    render_html_table(df_precision, height=200)
    
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


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLETE SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

def _render_complete_summary(metadata: dict):
    """Render complete metrics summary table"""
    st.markdown("### 📋 Complete Metrics Summary")
    st.caption("All metrics in one table for easy comparison")
    
    metrics_long = metadata.get('metrics_long', {})
    metrics_short = metadata.get('metrics_short', {})
    
    ranking_long = metrics_long.get('ranking', metrics_long)
    ranking_short = metrics_short.get('ranking', metrics_short)
    
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
        val_l = metrics_long.get(key, 0)
        val_s = metrics_short.get(key, 0)
        if val_l != 0 or val_s != 0:
            summary_rows.append({
                'Category': 'Regression',
                'Metric': name,
                '📈 LONG': f'{val_l:{fmt}}',
                '📉 SHORT': f'{val_s:{fmt}}'
            })
    
    # Ranking metrics
    spearman_l = ranking_long.get('test_spearman', ranking_long.get('spearman_corr', 0))
    spearman_s = ranking_short.get('test_spearman', ranking_short.get('spearman_corr', 0))
    pval_l = ranking_long.get('test_spearman_pval', ranking_long.get('spearman_pval', 1))
    pval_s = ranking_short.get('test_spearman_pval', ranking_short.get('spearman_pval', 1))
    
    summary_rows.append({
        'Category': 'Ranking',
        'Metric': 'Spearman Corr',
        '📈 LONG': f'{spearman_l:.4f}',
        '📉 SHORT': f'{spearman_s:.4f}'
    })
    summary_rows.append({
        'Category': 'Ranking',
        'Metric': 'Spearman p-value',
        '📈 LONG': f'{pval_l:.2e}',
        '📉 SHORT': f'{pval_s:.2e}'
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
    render_html_table(df_summary, height=500)


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURES LIST
# ═══════════════════════════════════════════════════════════════════════════════

def _render_features_list(metadata: dict):
    """Render features used in training"""
    st.markdown("### 📋 Features Used in Training")
    
    feature_names = metadata.get('feature_names', [])
    
    if not feature_names:
        st.info("Feature names not available in metadata")
        return
    
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
    
    if feature_rows:
        df_features = pd.DataFrame(feature_rows)
        render_html_table(df_features, height=300)
    
    # Full feature list
    with st.expander("🔍 View All Features"):
        cols = st.columns(3)
        for idx, f in enumerate(sorted(feature_names)):
            col_idx = idx % 3
            cols[col_idx].markdown(f"• `{f}`")


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL FILES
# ═══════════════════════════════════════════════════════════════════════════════

def _render_model_files(selected_version: str):
    """Render model files section"""
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
        render_html_table(df_files, height=200)
    else:
        st.info("No model files found for this version")
    
    st.caption(f"📁 Models Directory: `{MODELS_DIR}`")


# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

def _render_parameters(metadata: dict):
    """Render XGBoost parameters section"""
    
    # Check if Optuna model with best_params
    if is_optuna_model(metadata):
        with st.expander("⚙️ Best Hyperparameters (Optuna-Tuned)"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**LONG Model:**")
                params_long = metadata.get('best_params_long', {})
                for key, value in params_long.items():
                    if isinstance(value, float):
                        st.markdown(f"- `{key}`: {value:.6f}")
                    else:
                        st.markdown(f"- `{key}`: {value}")
            
            with col2:
                st.markdown("**SHORT Model:**")
                params_short = metadata.get('best_params_short', {})
                for key, value in params_short.items():
                    if isinstance(value, float):
                        st.markdown(f"- `{key}`: {value:.6f}")
                    else:
                        st.markdown(f"- `{key}`: {value}")
    else:
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
            render_html_table(df_params, height=300)


# ═══════════════════════════════════════════════════════════════════════════════
# METRICS GUIDE
# ═══════════════════════════════════════════════════════════════════════════════

def _render_metrics_guide():
    """Render metrics guide expander"""
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


__all__ = ['render_models_view_section']
