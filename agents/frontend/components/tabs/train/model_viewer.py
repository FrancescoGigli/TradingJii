"""
📊 Model Viewer Component
=========================

Displays trained model details, metrics, feature importance,
and live inference on BTCUSDT.

Dark themed, Streamlit-compatible.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Dict, Any, Optional, List
import pandas as pd

# Import local models service
try:
    from services.local_models import (
        ModelInfo,
        load_model_metadata,
        model_exists,
        run_inference,
        get_latest_signals,
        list_available_models
    )
    MODELS_SERVICE_AVAILABLE = True
except ImportError as e:
    MODELS_SERVICE_AVAILABLE = False
    IMPORT_ERROR = str(e)


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
    'grid': '#2d3748',
    'long': '#00ffff',
    'short': '#ff6b6b'
}


def render_training_command():
    """Render the training command section."""
    st.markdown("### 🚀 Local Training")
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e2130, #0d1117); 
                border: 1px solid #2d3748; border-radius: 12px; padding: 16px; margin: 8px 0;">
        <div style="color: #9ca3af; margin-bottom: 8px;">
            Run training locally (no Docker needed):
        </div>
        <div style="background: #0d1117; border: 1px solid #00ffff; border-radius: 8px; 
                    padding: 12px; font-family: 'Courier New', monospace; color: #00ffff;">
            python train_local.py --timeframe 15m --trials 30
        </div>
        <div style="color: #666; font-size: 12px; margin-top: 8px;">
            💡 Options: --timeframe (15m/1h), --trials (10-50), --verbose
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_model_summary(model: ModelInfo):
    """Render model summary card."""
    # Quality assessment
    avg_spearman = (
        model.metrics_long.get('ranking', {}).get('spearman_corr', 0) +
        model.metrics_short.get('ranking', {}).get('spearman_corr', 0)
    ) / 2
    
    if avg_spearman >= 0.2:
        quality = ("🟢", "Excellent", "#4ade80")
    elif avg_spearman >= 0.15:
        quality = ("🟡", "Good", "#fbbf24")
    elif avg_spearman >= 0.1:
        quality = ("🟠", "Acceptable", "#f97316")
    else:
        quality = ("🔴", "Poor", "#ff6b6b")
    
    # Format created_at
    created_at = model.created_at[:19].replace('T', ' ') if len(model.created_at) > 10 else model.created_at
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1e2130, #16213e); 
                border: 1px solid #2d3748; border-radius: 12px; padding: 16px; margin: 8px 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <span style="color: #4ade80; font-size: 18px; font-weight: bold;">
                📦 {model.timeframe} Model
            </span>
            <span style="background: {quality[2]}22; color: {quality[2]}; 
                        padding: 4px 12px; border-radius: 16px; font-size: 13px;">
                {quality[0]} {quality[1]}
            </span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 12px;">
            <div style="text-align: center;">
                <div style="color: #888; font-size: 12px;">Version</div>
                <div style="color: #e0e0ff; font-size: 14px;">{model.version[:20]}</div>
            </div>
            <div style="text-align: center;">
                <div style="color: #888; font-size: 12px;">Features</div>
                <div style="color: #00ffff; font-size: 18px; font-weight: bold;">{model.n_features}</div>
            </div>
            <div style="text-align: center;">
                <div style="color: #888; font-size: 12px;">Train Samples</div>
                <div style="color: #e0e0ff; font-size: 14px;">{model.n_train_samples:,}</div>
            </div>
            <div style="text-align: center;">
                <div style="color: #888; font-size: 12px;">Test Samples</div>
                <div style="color: #e0e0ff; font-size: 14px;">{model.n_test_samples:,}</div>
            </div>
        </div>
        <div style="color: #666; font-size: 12px; margin-top: 12px; text-align: right;">
            📅 Trained: {created_at} | ⏱️ Duration: {model.training_duration_seconds/60:.1f} min
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_metrics_table(model: ModelInfo):
    """Render detailed metrics table."""
    metrics_long = model.metrics_long
    metrics_short = model.metrics_short
    ranking_long = metrics_long.get('ranking', {})
    ranking_short = metrics_short.get('ranking', {})
    
    st.markdown("#### 📊 Model Metrics")
    
    st.markdown(f"""
    <div style="background: #0d1117; border-radius: 8px; overflow: hidden; margin: 8px 0;">
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; background: #161b26; 
                    border-bottom: 1px solid #2d3748; padding: 12px;">
            <div style="color: #888; font-weight: bold;">Metric</div>
            <div style="color: #00ffff; font-weight: bold; text-align: center;">📈 LONG</div>
            <div style="color: #ff6b6b; font-weight: bold; text-align: center;">📉 SHORT</div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 10px 12px; 
                    border-bottom: 1px solid #1a1a2a;">
            <div style="color: #e0e0ff;">Spearman Correlation</div>
            <div style="color: #00ffff; text-align: center; font-family: monospace;">
                {ranking_long.get('spearman_corr', 0):.4f}
            </div>
            <div style="color: #ff6b6b; text-align: center; font-family: monospace;">
                {ranking_short.get('spearman_corr', 0):.4f}
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 10px 12px; 
                    border-bottom: 1px solid #1a1a2a;">
            <div style="color: #e0e0ff;">R² Score</div>
            <div style="color: #00ffff; text-align: center; font-family: monospace;">
                {metrics_long.get('test_r2', 0):.4f}
            </div>
            <div style="color: #ff6b6b; text-align: center; font-family: monospace;">
                {metrics_short.get('test_r2', 0):.4f}
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 10px 12px; 
                    border-bottom: 1px solid #1a1a2a;">
            <div style="color: #e0e0ff;">RMSE</div>
            <div style="color: #00ffff; text-align: center; font-family: monospace;">
                {metrics_long.get('test_rmse', 0):.4f}
            </div>
            <div style="color: #ff6b6b; text-align: center; font-family: monospace;">
                {metrics_short.get('test_rmse', 0):.4f}
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 10px 12px; 
                    border-bottom: 1px solid #1a1a2a;">
            <div style="color: #e0e0ff;">Top 1% Positive</div>
            <div style="color: #00ffff; text-align: center; font-family: monospace;">
                {ranking_long.get('top1pct_positive', 0):.1f}%
            </div>
            <div style="color: #ff6b6b; text-align: center; font-family: monospace;">
                {ranking_short.get('top1pct_positive', 0):.1f}%
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 10px 12px; 
                    border-bottom: 1px solid #1a1a2a;">
            <div style="color: #e0e0ff;">Top 5% Positive</div>
            <div style="color: #00ffff; text-align: center; font-family: monospace;">
                {ranking_long.get('top5pct_positive', 0):.1f}%
            </div>
            <div style="color: #ff6b6b; text-align: center; font-family: monospace;">
                {ranking_short.get('top5pct_positive', 0):.1f}%
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 10px 12px;">
            <div style="color: #e0e0ff;">Top 10% Positive</div>
            <div style="color: #00ffff; text-align: center; font-family: monospace;">
                {ranking_long.get('top10pct_positive', 0):.1f}%
            </div>
            <div style="color: #ff6b6b; text-align: center; font-family: monospace;">
                {ranking_short.get('top10pct_positive', 0):.1f}%
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def create_feature_importance_chart(model: ModelInfo) -> go.Figure:
    """Create feature importance horizontal bar chart."""
    # Get top 10 features for each model
    fi_long = dict(list(model.feature_importance_long.items())[:10])
    fi_short = dict(list(model.feature_importance_short.items())[:10])
    
    # Combine and get unique features
    all_features = list(set(list(fi_long.keys()) + list(fi_short.keys())))[:10]
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("📈 LONG Model", "📉 SHORT Model"),
        horizontal_spacing=0.15
    )
    
    # LONG
    features_long = list(fi_long.keys())
    values_long = list(fi_long.values())
    fig.add_trace(go.Bar(
        y=features_long,
        x=values_long,
        orientation='h',
        marker_color=COLORS['long'],
        name='LONG',
        text=[f'{v:.3f}' for v in values_long],
        textposition='outside'
    ), row=1, col=1)
    
    # SHORT
    features_short = list(fi_short.keys())
    values_short = list(fi_short.values())
    fig.add_trace(go.Bar(
        y=features_short,
        x=values_short,
        orientation='h',
        marker_color=COLORS['short'],
        name='SHORT',
        text=[f'{v:.3f}' for v in values_short],
        textposition='outside'
    ), row=1, col=2)
    
    fig.update_layout(
        title=dict(text="🔝 Feature Importance (Top 10)", font=dict(color=COLORS['text'])),
        plot_bgcolor=COLORS['card'],
        paper_bgcolor=COLORS['background'],
        font=dict(color=COLORS['text']),
        showlegend=False,
        height=400,
        margin=dict(l=20, r=20, t=60, b=20)
    )
    
    fig.update_xaxes(gridcolor=COLORS['grid'], showgrid=True)
    fig.update_yaxes(gridcolor=COLORS['grid'], showgrid=False)
    
    return fig


def create_precision_at_k_chart(model: ModelInfo) -> go.Figure:
    """Create Precision@K line chart."""
    k_values = ['Top 1%', 'Top 5%', 'Top 10%', 'Top 20%']
    ranking_long = model.metrics_long.get('ranking', {})
    ranking_short = model.metrics_short.get('ranking', {})
    
    precision_long = [
        ranking_long.get('top1pct_positive', 50),
        ranking_long.get('top5pct_positive', 50),
        ranking_long.get('top10pct_positive', 50),
        ranking_long.get('top20pct_positive', 50),
    ]
    
    precision_short = [
        ranking_short.get('top1pct_positive', 50),
        ranking_short.get('top5pct_positive', 50),
        ranking_short.get('top10pct_positive', 50),
        ranking_short.get('top20pct_positive', 50),
    ]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=k_values, y=precision_long,
        mode='lines+markers',
        name='LONG',
        line=dict(color=COLORS['long'], width=3),
        marker=dict(size=10)
    ))
    
    fig.add_trace(go.Scatter(
        x=k_values, y=precision_short,
        mode='lines+markers',
        name='SHORT',
        line=dict(color=COLORS['short'], width=3),
        marker=dict(size=10)
    ))
    
    # Baseline
    fig.add_hline(y=50, line_dash="dash", line_color=COLORS['warning'],
                  annotation_text="Random (50%)")
    
    fig.update_layout(
        title=dict(text="🎯 Precision@K (% Profitable)", font=dict(color=COLORS['text'])),
        plot_bgcolor=COLORS['card'],
        paper_bgcolor=COLORS['background'],
        font=dict(color=COLORS['text']),
        xaxis=dict(gridcolor=COLORS['grid']),
        yaxis=dict(gridcolor=COLORS['grid'], title="% Positive", range=[0, 100]),
        legend=dict(bgcolor='rgba(0,0,0,0.5)'),
        height=350
    )
    
    return fig


def render_hyperparameters(model: ModelInfo):
    """Render best hyperparameters."""
    st.markdown("#### ⚙️ Best Hyperparameters")
    
    params_long = model.best_params_long
    params_short = model.best_params_short
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📈 LONG Model**")
        for key, value in params_long.items():
            if isinstance(value, float):
                st.text(f"  {key}: {value:.4f}")
            else:
                st.text(f"  {key}: {value}")
    
    with col2:
        st.markdown("**📉 SHORT Model**")
        for key, value in params_short.items():
            if isinstance(value, float):
                st.text(f"  {key}: {value:.4f}")
            else:
                st.text(f"  {key}: {value}")


def render_data_range(model: ModelInfo):
    """Render training data range."""
    data_range = model.data_range
    
    st.markdown("#### 📅 Training Data Range")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        **Train Set:**
        - Start: `{data_range.get('train_start', 'N/A')[:19]}`
        - End: `{data_range.get('train_end', 'N/A')[:19]}`
        """)
    with col2:
        st.markdown(f"""
        **Test Set:**
        - Start: `{data_range.get('test_start', 'N/A')[:19]}`
        - End: `{data_range.get('test_end', 'N/A')[:19]}`
        """)


def create_inference_chart(df: pd.DataFrame) -> go.Figure:
    """Create candlestick chart with scores overlay."""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3],
        subplot_titles=("BTCUSDT Price", "ML Scores")
    )
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='BTCUSDT',
        increasing_line_color=COLORS['success'],
        decreasing_line_color=COLORS['secondary']
    ), row=1, col=1)
    
    # Scores
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['score_long'],
        mode='lines',
        name='Score LONG',
        line=dict(color=COLORS['long'], width=2)
    ), row=2, col=1)
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['score_short'],
        mode='lines',
        name='Score SHORT',
        line=dict(color=COLORS['short'], width=2)
    ), row=2, col=1)
    
    # Threshold lines
    fig.add_hline(y=0.7, line_dash="dash", line_color=COLORS['success'], 
                  row=2, col=1, annotation_text="Strong Signal")
    fig.add_hline(y=0.5, line_dash="dot", line_color=COLORS['warning'], 
                  row=2, col=1)
    
    fig.update_layout(
        plot_bgcolor=COLORS['card'],
        paper_bgcolor=COLORS['background'],
        font=dict(color=COLORS['text']),
        xaxis_rangeslider_visible=False,
        height=500,
        legend=dict(bgcolor='rgba(0,0,0,0.5)', orientation='h', y=1.02),
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    fig.update_xaxes(gridcolor=COLORS['grid'])
    fig.update_yaxes(gridcolor=COLORS['grid'])
    
    return fig


def render_live_inference(timeframe: str):
    """Render live inference section for BTCUSDT."""
    st.markdown("#### 🔮 Live Inference: BTCUSDT")
    
    # Get latest signals
    signals = get_latest_signals(timeframe, "BTCUSDT")
    
    if signals is None:
        st.warning("⚠️ Unable to run inference. Check if OHLCV data is available.")
        return
    
    # Signal card
    signal = signals['signal']
    signal_color = {
        'STRONG BUY': '#4ade80',
        'BUY': '#34d399',
        'HOLD': '#9ca3af',
        'SELL': '#f97316',
        'STRONG SELL': '#ff6b6b'
    }.get(signal, '#9ca3af')
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1e2130, #0d1117); 
                border: 2px solid {signal_color}; border-radius: 12px; padding: 16px; margin: 8px 0;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="color: #888; font-size: 12px;">Current Signal</div>
                <div style="color: {signal_color}; font-size: 24px; font-weight: bold;">
                    {signal}
                </div>
            </div>
            <div style="text-align: right;">
                <div style="color: #888; font-size: 12px;">BTC Price</div>
                <div style="color: #e0e0ff; font-size: 20px;">
                    ${signals['close']:,.2f}
                </div>
            </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 16px;">
            <div style="text-align: center; background: #0d1117; padding: 12px; border-radius: 8px;">
                <div style="color: #888; font-size: 11px;">LONG Score</div>
                <div style="color: #00ffff; font-size: 18px; font-weight: bold;">
                    {signals['score_long']:.3f}
                </div>
            </div>
            <div style="text-align: center; background: #0d1117; padding: 12px; border-radius: 8px;">
                <div style="color: #888; font-size: 11px;">SHORT Score</div>
                <div style="color: #ff6b6b; font-size: 18px; font-weight: bold;">
                    {signals['score_short']:.3f}
                </div>
            </div>
            <div style="text-align: center; background: #0d1117; padding: 12px; border-radius: 8px;">
                <div style="color: #888; font-size: 11px;">Net Score</div>
                <div style="color: {'#4ade80' if signals['net_score'] > 0 else '#ff6b6b'}; 
                            font-size: 18px; font-weight: bold;">
                    {signals['net_score']:+.3f}
                </div>
            </div>
        </div>
        <div style="color: #666; font-size: 11px; margin-top: 12px; text-align: right;">
            Last update: {signals['timestamp'][:19]}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Full inference chart
    with st.expander("📈 Inference Chart (Last 200 Candles)", expanded=False):
        df = run_inference(timeframe, "BTCUSDT", 200)
        if df is not None and len(df) > 0:
            fig = create_inference_chart(df)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No inference data available")


def render_model_viewer(timeframe: str):
    """
    Main function to render the complete model viewer.
    
    Args:
        timeframe: '15m' or '1h'
    """
    if not MODELS_SERVICE_AVAILABLE:
        st.error(f"❌ Models service not available: {IMPORT_ERROR}")
        return
    
    # Check if model exists
    if not model_exists(timeframe):
        st.warning(f"⚠️ No trained model found for {timeframe}")
        render_training_command()
        return
    
    # Load model metadata
    model = load_model_metadata(timeframe)
    if model is None:
        st.error("❌ Failed to load model metadata")
        return
    
    # Render all sections
    render_model_summary(model)
    
    st.divider()
    
    # Metrics and charts
    col1, col2 = st.columns([1, 1])
    
    with col1:
        render_metrics_table(model)
    
    with col2:
        fig = create_precision_at_k_chart(model)
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # Feature importance
    fig = create_feature_importance_chart(model)
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # Live inference
    render_live_inference(timeframe)
    
    st.divider()
    
    # Expandable sections
    with st.expander("⚙️ Hyperparameters", expanded=False):
        render_hyperparameters(model)
    
    with st.expander("📅 Data Range", expanded=False):
        render_data_range(model)
    
    with st.expander("📝 Feature List", expanded=False):
        st.write(", ".join(model.feature_names))


__all__ = ['render_model_viewer', 'render_training_command']
