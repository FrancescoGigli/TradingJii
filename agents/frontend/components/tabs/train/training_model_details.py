"""
📊 Training Model Details Section

Displays the last trained model details:
- Summary card with quality badge
- Metrics table (LONG vs SHORT)
- Feature importance chart
- Precision@K chart
- Radar comparison chart
"""

import streamlit as st
import json
from pathlib import Path
from typing import Dict, Any, Optional
import os

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


# Color scheme (dark theme)
COLORS = {
    'primary': '#00ffff',
    'secondary': '#ff6b6b',
    'success': '#4ade80',
    'warning': '#fbbf24',
    'info': '#60a5fa',
    'background': '#0d1117',
    'card': '#1e2130',
    'text': '#e0e0ff',
    'muted': '#9ca3af',
    'border': '#2d3748',
    'long': '#00ffff',
    'short': '#ff6b6b'
}


def _get_models_dir() -> Path:
    """Get the models directory path."""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    return Path(shared_path) / "models"


def _load_metadata(timeframe: str) -> Optional[Dict[str, Any]]:
    """Load metadata for a specific timeframe."""
    models_dir = _get_models_dir()
    metadata_path = models_dir / f"metadata_{timeframe}_latest.json"
    
    if not metadata_path.exists():
        return None
    
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def render_model_details_section():
    """Render the model details section."""
    st.markdown("### 📦 Last Trained Model")
    
    # Check which models exist
    meta_15m = _load_metadata('15m')
    meta_1h = _load_metadata('1h')
    
    if not meta_15m and not meta_1h:
        st.warning("""
        ⚠️ **No trained models found.**
        
        Run the training command to create a model:
        ```bash
        python train_local.py --timeframe 15m --trials 30
        ```
        """)
        return
    
    # Timeframe selector
    available = []
    if meta_15m:
        available.append('15m')
    if meta_1h:
        available.append('1h')
    
    selected_tf = st.selectbox(
        "Select Model",
        available,
        format_func=lambda x: f"{'🔵' if x == '15m' else '🟢'} {x.upper()} Model"
    )
    
    meta = meta_15m if selected_tf == '15m' else meta_1h
    
    if not meta:
        st.error("Failed to load model metadata")
        return
    
    # Render all sub-sections
    _render_summary_card(meta)
    
    st.markdown("---")
    
    # Metrics and charts in columns
    col1, col2 = st.columns([1, 1])
    
    with col1:
        _render_metrics_table(meta)
    
    with col2:
        if PLOTLY_AVAILABLE:
            _render_precision_chart(meta)
    
    st.markdown("---")
    
    # Feature importance
    if PLOTLY_AVAILABLE:
        _render_feature_importance_chart(meta)
    
    # Expandable sections
    with st.expander("⚙️ Hyperparameters", expanded=False):
        _render_hyperparameters(meta)
    
    with st.expander("📅 Training Data Range", expanded=False):
        _render_data_range(meta)


def _render_summary_card(meta: Dict[str, Any]):
    """Render the model summary card."""
    metrics_long = meta.get('metrics_long', {})
    metrics_short = meta.get('metrics_short', {})
    
    spearman_long = metrics_long.get('ranking', {}).get('spearman_corr', 0)
    spearman_short = metrics_short.get('ranking', {}).get('spearman_corr', 0)
    avg_spearman = (spearman_long + spearman_short) / 2
    
    # Quality badge
    if avg_spearman >= 0.2:
        quality = ("🟢", "Excellent", "#4ade80")
    elif avg_spearman >= 0.15:
        quality = ("🟡", "Good", "#fbbf24")
    elif avg_spearman >= 0.1:
        quality = ("🟠", "Acceptable", "#f97316")
    else:
        quality = ("🔴", "Needs Improvement", "#ff6b6b")
    
    timeframe = meta.get('timeframe', 'N/A')
    version = meta.get('version', 'Unknown')
    created_at = meta.get('created_at', 'Unknown')[:19].replace('T', ' ')
    duration_min = meta.get('training_duration_seconds', 0) / 60
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {COLORS['card']}, #16213e);
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <span style="color: {COLORS['success']}; font-size: 1.3em; font-weight: bold;">
                📦 {timeframe.upper()} Model
            </span>
            <span style="
                background: {quality[2]}22;
                color: {quality[2]};
                padding: 6px 14px;
                border-radius: 20px;
                font-weight: bold;
            ">
                {quality[0]} {quality[1]}
            </span>
        </div>
        <div style="color: {COLORS['muted']}; font-size: 0.9em; margin-bottom: 15px;">
            Version: <code style="background: {COLORS['border']}; padding: 2px 6px; border-radius: 4px;">{version[:30]}...</code>
            | Trained: {created_at}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Features", meta.get('n_features', 0))
    with col2:
        st.metric("📚 Train Samples", f"{meta.get('n_train_samples', 0):,}")
    with col3:
        st.metric("🧪 Test Samples", f"{meta.get('n_test_samples', 0):,}")
    with col4:
        st.metric("⏱️ Duration", f"{duration_min:.1f} min")


def _render_metrics_table(meta: Dict[str, Any]):
    """Render the metrics comparison table."""
    metrics_long = meta.get('metrics_long', {})
    metrics_short = meta.get('metrics_short', {})
    ranking_long = metrics_long.get('ranking', {})
    ranking_short = metrics_short.get('ranking', {})
    
    st.markdown("#### 📊 Model Metrics")
    
    st.markdown(f"""
    <div style="background: {COLORS['background']}; border-radius: 8px; overflow: hidden;">
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; background: #161b26; 
                    border-bottom: 1px solid {COLORS['border']}; padding: 12px;">
            <div style="color: {COLORS['muted']}; font-weight: bold;">Metric</div>
            <div style="color: {COLORS['long']}; font-weight: bold; text-align: center;">📈 LONG</div>
            <div style="color: {COLORS['short']}; font-weight: bold; text-align: center;">📉 SHORT</div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 10px 12px; 
                    border-bottom: 1px solid {COLORS['border']};">
            <div style="color: {COLORS['text']};">Spearman Correlation</div>
            <div style="color: {COLORS['long']}; text-align: center; font-family: monospace;">
                {ranking_long.get('spearman_corr', 0):.4f}
            </div>
            <div style="color: {COLORS['short']}; text-align: center; font-family: monospace;">
                {ranking_short.get('spearman_corr', 0):.4f}
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 10px 12px; 
                    border-bottom: 1px solid {COLORS['border']};">
            <div style="color: {COLORS['text']};">R² Score</div>
            <div style="color: {COLORS['long']}; text-align: center; font-family: monospace;">
                {metrics_long.get('test_r2', 0):.4f}
            </div>
            <div style="color: {COLORS['short']}; text-align: center; font-family: monospace;">
                {metrics_short.get('test_r2', 0):.4f}
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 10px 12px; 
                    border-bottom: 1px solid {COLORS['border']};">
            <div style="color: {COLORS['text']};">RMSE</div>
            <div style="color: {COLORS['long']}; text-align: center; font-family: monospace;">
                {metrics_long.get('test_rmse', 0):.4f}
            </div>
            <div style="color: {COLORS['short']}; text-align: center; font-family: monospace;">
                {metrics_short.get('test_rmse', 0):.4f}
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 10px 12px; 
                    border-bottom: 1px solid {COLORS['border']};">
            <div style="color: {COLORS['text']};">Top 1% Positive</div>
            <div style="color: {COLORS['long']}; text-align: center; font-family: monospace;">
                {ranking_long.get('top1pct_positive', 0):.1f}%
            </div>
            <div style="color: {COLORS['short']}; text-align: center; font-family: monospace;">
                {ranking_short.get('top1pct_positive', 0):.1f}%
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 10px 12px; 
                    border-bottom: 1px solid {COLORS['border']};">
            <div style="color: {COLORS['text']};">Top 5% Positive</div>
            <div style="color: {COLORS['long']}; text-align: center; font-family: monospace;">
                {ranking_long.get('top5pct_positive', 0):.1f}%
            </div>
            <div style="color: {COLORS['short']}; text-align: center; font-family: monospace;">
                {ranking_short.get('top5pct_positive', 0):.1f}%
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 10px 12px;">
            <div style="color: {COLORS['text']};">Top 10% Positive</div>
            <div style="color: {COLORS['long']}; text-align: center; font-family: monospace;">
                {ranking_long.get('top10pct_positive', 0):.1f}%
            </div>
            <div style="color: {COLORS['short']}; text-align: center; font-family: monospace;">
                {ranking_short.get('top10pct_positive', 0):.1f}%
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_precision_chart(meta: Dict[str, Any]):
    """Render Precision@K bar chart."""
    metrics_long = meta.get('metrics_long', {})
    metrics_short = meta.get('metrics_short', {})
    ranking_long = metrics_long.get('ranking', {})
    ranking_short = metrics_short.get('ranking', {})
    
    k_values = ['Top 1%', 'Top 5%', 'Top 10%', 'Top 20%']
    
    long_precision = [
        ranking_long.get('top1pct_positive', 0),
        ranking_long.get('top5pct_positive', 0),
        ranking_long.get('top10pct_positive', 0),
        ranking_long.get('top20pct_positive', 0),
    ]
    
    short_precision = [
        ranking_short.get('top1pct_positive', 0),
        ranking_short.get('top5pct_positive', 0),
        ranking_short.get('top10pct_positive', 0),
        ranking_short.get('top20pct_positive', 0),
    ]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='LONG',
        x=k_values,
        y=long_precision,
        marker_color=COLORS['long'],
        text=[f'{v:.1f}%' for v in long_precision],
        textposition='outside'
    ))
    
    fig.add_trace(go.Bar(
        name='SHORT',
        x=k_values,
        y=short_precision,
        marker_color=COLORS['short'],
        text=[f'{v:.1f}%' for v in short_precision],
        textposition='outside'
    ))
    
    # 50% baseline
    fig.add_hline(y=50, line_dash="dash", line_color=COLORS['warning'],
                  annotation_text="Random (50%)")
    
    fig.update_layout(
        title=dict(text="🎯 Precision@K", font=dict(color=COLORS['text'])),
        barmode='group',
        plot_bgcolor=COLORS['card'],
        paper_bgcolor=COLORS['background'],
        font=dict(color=COLORS['text']),
        xaxis=dict(gridcolor=COLORS['border']),
        yaxis=dict(gridcolor=COLORS['border'], title="% Positive", range=[0, 100]),
        legend=dict(bgcolor='rgba(0,0,0,0.5)'),
        height=350,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    st.plotly_chart(fig, use_container_width=True)


def _render_feature_importance_chart(meta: Dict[str, Any]):
    """Render feature importance chart."""
    fi_long = meta.get('feature_importance_long', {})
    fi_short = meta.get('feature_importance_short', {})
    
    if not fi_long or not fi_short:
        st.info("No feature importance data available")
        return
    
    st.markdown("#### 🔬 Feature Importance (Top 10)")
    
    # Top 10 features
    top_long = list(fi_long.items())[:10]
    top_short = list(fi_short.items())[:10]
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("📈 LONG Model", "📉 SHORT Model"),
        horizontal_spacing=0.15
    )
    
    # LONG
    fig.add_trace(go.Bar(
        y=[f[0] for f in reversed(top_long)],
        x=[f[1] for f in reversed(top_long)],
        orientation='h',
        marker_color=COLORS['long'],
        text=[f'{f[1]:.3f}' for f in reversed(top_long)],
        textposition='outside',
        name='LONG'
    ), row=1, col=1)
    
    # SHORT
    fig.add_trace(go.Bar(
        y=[f[0] for f in reversed(top_short)],
        x=[f[1] for f in reversed(top_short)],
        orientation='h',
        marker_color=COLORS['short'],
        text=[f'{f[1]:.3f}' for f in reversed(top_short)],
        textposition='outside',
        name='SHORT'
    ), row=1, col=2)
    
    fig.update_layout(
        plot_bgcolor=COLORS['card'],
        paper_bgcolor=COLORS['background'],
        font=dict(color=COLORS['text']),
        showlegend=False,
        height=400,
        margin=dict(l=120, r=80, t=50, b=20)
    )
    
    fig.update_xaxes(gridcolor=COLORS['border'])
    fig.update_yaxes(gridcolor=COLORS['border'])
    
    st.plotly_chart(fig, use_container_width=True)


def _render_hyperparameters(meta: Dict[str, Any]):
    """Render hyperparameters section."""
    params_long = meta.get('best_params_long', {})
    params_short = meta.get('best_params_short', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**📈 LONG Model**")
        for key, value in params_long.items():
            if isinstance(value, float):
                st.text(f"  {key}: {value:.4f}")
            else:
                st.text(f"  {key}: {value}")
    
    with col2:
        st.markdown(f"**📉 SHORT Model**")
        for key, value in params_short.items():
            if isinstance(value, float):
                st.text(f"  {key}: {value:.4f}")
            else:
                st.text(f"  {key}: {value}")


def _render_data_range(meta: Dict[str, Any]):
    """Render training data range."""
    data_range = meta.get('data_range', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Train Set:**")
        st.markdown(f"- Start: `{data_range.get('train_start', 'N/A')[:19]}`")
        st.markdown(f"- End: `{data_range.get('train_end', 'N/A')[:19]}`")
    
    with col2:
        st.markdown("**Test Set:**")
        st.markdown(f"- Start: `{data_range.get('test_start', 'N/A')[:19]}`")
        st.markdown(f"- End: `{data_range.get('test_end', 'N/A')[:19]}`")


__all__ = ['render_model_details_section']
