"""
📈 Bitcoin Inference Section

Displays live inference on BTCUSDT with last 200 candles:
- Current signal card (STRONG BUY/BUY/HOLD/SELL/STRONG SELL)
- Candlestick chart with price
- ML scores overlay (LONG/SHORT)
"""

import streamlit as st
from typing import Dict, Any
import pandas as pd

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# Import local models service
try:
    from services.local_models import (
        model_exists,
        run_inference,
        get_latest_signals
    )
    MODELS_SERVICE_AVAILABLE = True
except ImportError:
    MODELS_SERVICE_AVAILABLE = False

# Import from shared modules (centralized, no duplication)
from .shared import COLORS
from .shared.colors import SIGNAL_COLORS
from .shared.model_loader import model_exists as shared_model_exists


def _check_model_exists(timeframe: str) -> bool:
    """Check if model exists for a timeframe."""
    if MODELS_SERVICE_AVAILABLE:
        return model_exists(timeframe)
    return shared_model_exists(timeframe)


def render_btc_inference_section():
    """Render the Bitcoin inference section."""
    st.markdown("### 📈 Bitcoin Live Inference (Last 200 Candles)")
    st.caption("Real-time ML predictions on BTCUSDT using trained model")
    
    if not MODELS_SERVICE_AVAILABLE:
        st.error("❌ Models service not available. Check imports.")
        return
    
    if not PLOTLY_AVAILABLE:
        st.error("❌ Plotly not available for charts.")
        return
    
    # Check which models exist
    has_15m = _check_model_exists('15m')
    has_1h = _check_model_exists('1h')
    
    if not has_15m and not has_1h:
        st.warning("""
        ⚠️ **No trained models found.**
        
        Train a model first to see Bitcoin inference:
        ```bash
        python train_local.py --timeframe 15m --trials 30
        ```
        """)
        return
    
    # Timeframe selector
    available = []
    if has_15m:
        available.append('15m')
    if has_1h:
        available.append('1h')
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_tf = st.selectbox(
            "Select Model for Inference",
            available,
            format_func=lambda x: f"{'🔵' if x == '15m' else '🟢'} {x.upper()} Model",
            key="btc_inference_tf_selector"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        refresh_clicked = st.button(
            "🔄 Refresh Data",
            use_container_width=True
        )
    
    # Get latest signals
    _render_signal_card(selected_tf)
    
    st.markdown("---")
    
    # Inference chart
    _render_inference_chart(selected_tf)


def _render_signal_card(timeframe: str):
    """Render the current signal card."""
    signals = get_latest_signals(timeframe, "BTCUSDT")
    
    if signals is None:
        st.warning("⚠️ Unable to get signals. Check if OHLCV data is available.")
        return
    
    signal = signals.get('signal', 'HOLD')
    
    # Signal colors
    signal_colors = {
        'STRONG BUY': '#4ade80',
        'BUY': '#34d399',
        'HOLD': '#9ca3af',
        'SELL': '#f97316',
        'STRONG SELL': '#ff6b6b'
    }
    
    signal_color = signal_colors.get(signal, '#9ca3af')
    
    # Net score color
    net_score = signals.get('net_score', 0)
    net_color = COLORS['success'] if net_score > 0 else COLORS['secondary']
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {COLORS['card']}, {COLORS['background']});
        border: 2px solid {signal_color};
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="color: {COLORS['muted']}; font-size: 12px; margin-bottom: 4px;">
                    Current Signal
                </div>
                <div style="color: {signal_color}; font-size: 28px; font-weight: bold;">
                    {signal}
                </div>
            </div>
            <div style="text-align: right;">
                <div style="color: {COLORS['muted']}; font-size: 12px; margin-bottom: 4px;">
                    BTC Price
                </div>
                <div style="color: {COLORS['text']}; font-size: 24px; font-weight: bold;">
                    ${signals.get('close', 0):,.2f}
                </div>
            </div>
        </div>
        <div style="
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-top: 20px;
        ">
            <div style="
                text-align: center;
                background: {COLORS['background']};
                padding: 12px;
                border-radius: 8px;
            ">
                <div style="color: {COLORS['muted']}; font-size: 11px;">LONG Score</div>
                <div style="color: {COLORS['long']}; font-size: 20px; font-weight: bold;">
                    {signals.get('score_long', 0):.3f}
                </div>
            </div>
            <div style="
                text-align: center;
                background: {COLORS['background']};
                padding: 12px;
                border-radius: 8px;
            ">
                <div style="color: {COLORS['muted']}; font-size: 11px;">SHORT Score</div>
                <div style="color: {COLORS['short']}; font-size: 20px; font-weight: bold;">
                    {signals.get('score_short', 0):.3f}
                </div>
            </div>
            <div style="
                text-align: center;
                background: {COLORS['background']};
                padding: 12px;
                border-radius: 8px;
            ">
                <div style="color: {COLORS['muted']}; font-size: 11px;">Net Score</div>
                <div style="color: {net_color}; font-size: 20px; font-weight: bold;">
                    {net_score:+.3f}
                </div>
            </div>
        </div>
        <div style="
            color: {COLORS['muted']};
            font-size: 11px;
            margin-top: 12px;
            text-align: right;
        ">
            Last update: {signals.get('timestamp', 'N/A')[:19]}
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_inference_chart(timeframe: str):
    """Render the candlestick chart with ML scores."""
    # Get inference data
    df = run_inference(timeframe, "BTCUSDT", 200)
    
    if df is None or len(df) == 0:
        st.warning("⚠️ No inference data available. Check if historical data exists.")
        return
    
    st.markdown("#### 📊 Price Chart with ML Predictions")
    
    # Create figure with subplots
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
        subplot_titles=("BTCUSDT Price", "ML Scores (LONG / SHORT)")
    )
    
    # Candlestick chart
    fig.add_trace(go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='BTCUSDT',
        increasing_line_color=COLORS['bullish'],
        decreasing_line_color=COLORS['bearish']
    ), row=1, col=1)
    
    # ML Scores
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
    fig.add_hline(
        y=0.7, line_dash="dash", line_color=COLORS['success'],
        row=2, col=1, annotation_text="Strong Signal (0.7)"
    )
    fig.add_hline(
        y=0.5, line_dash="dot", line_color=COLORS['warning'],
        row=2, col=1, annotation_text="Signal (0.5)"
    )
    fig.add_hline(
        y=0.3, line_dash="dot", line_color=COLORS['muted'],
        row=2, col=1
    )
    
    # Layout
    fig.update_layout(
        plot_bgcolor=COLORS['card'],
        paper_bgcolor=COLORS['background'],
        font=dict(color=COLORS['text']),
        xaxis_rangeslider_visible=False,
        height=600,
        legend=dict(
            bgcolor='rgba(0,0,0,0.5)',
            orientation='h',
            y=1.02,
            x=0.5,
            xanchor='center'
        ),
        margin=dict(l=20, r=20, t=60, b=20)
    )
    
    fig.update_xaxes(gridcolor=COLORS['border'], showgrid=True)
    fig.update_yaxes(gridcolor=COLORS['border'], showgrid=True)
    
    # Y-axis for scores
    fig.update_yaxes(range=[0, 1], row=2, col=1)
    
    st.plotly_chart(fig, width='stretch')
    
    # Signal distribution summary
    _render_signal_summary(df)


def _render_signal_summary(df: pd.DataFrame):
    """Render signal distribution summary."""
    if 'signal' not in df.columns:
        return
    
    with st.expander("📊 Signal Distribution (Last 200 Candles)", expanded=False):
        signal_counts = df['signal'].value_counts()
        
        total = len(df)
        
        st.markdown(f"""
        <div style="
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 10px;
            padding: 10px;
            background: {COLORS['background']};
            border-radius: 8px;
        ">
        """, unsafe_allow_html=True)
        
        signals = ['STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL']
        signal_colors = {
            'STRONG BUY': '#4ade80',
            'BUY': '#34d399',
            'HOLD': '#9ca3af',
            'SELL': '#f97316',
            'STRONG SELL': '#ff6b6b'
        }
        
        cols = st.columns(5)
        for i, sig in enumerate(signals):
            count = signal_counts.get(sig, 0)
            pct = (count / total * 100) if total > 0 else 0
            color = signal_colors[sig]
            
            with cols[i]:
                st.markdown(f"""
                <div style="
                    text-align: center;
                    padding: 12px;
                    background: {COLORS['card']};
                    border-radius: 8px;
                    border: 1px solid {color}33;
                ">
                    <div style="color: {color}; font-size: 0.85em; font-weight: bold;">
                        {sig}
                    </div>
                    <div style="color: {COLORS['text']}; font-size: 1.5em; font-weight: bold;">
                        {count}
                    </div>
                    <div style="color: {COLORS['muted']}; font-size: 0.8em;">
                        {pct:.1f}%
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # Score statistics
        st.markdown("---")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Avg LONG Score",
                f"{df['score_long'].mean():.3f}",
                f"{df['score_long'].std():.3f} std"
            )
        
        with col2:
            st.metric(
                "Avg SHORT Score",
                f"{df['score_short'].mean():.3f}",
                f"{df['score_short'].std():.3f} std"
            )
        
        with col3:
            net_mean = df['net_score'].mean()
            st.metric(
                "Avg Net Score",
                f"{net_mean:+.3f}",
                "Bullish Bias" if net_mean > 0 else "Bearish Bias"
            )


__all__ = ['render_btc_inference_section']
