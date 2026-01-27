"""
📈 Bitcoin Inference Section

Displays live inference on BTCUSDT with last 200 candles:
- Current signal card (STRONG BUY/BUY/HOLD/SELL/STRONG SELL)
- Candlestick chart with price
- ML scores overlay (LONG/SHORT)
"""

import streamlit as st
from typing import Any
import pandas as pd

try:
    # Plotly is only used indirectly here; figure building is in
    # `btc_inference_charts.py`.
    import plotly.graph_objects as go  # noqa: F401
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# Import local models service
try:
    from services.local_models import (
        model_exists,
        run_inference,
        get_latest_signals,
        InferenceDataNotFoundError,
        list_realtime_symbols,
    )
    MODELS_SERVICE_AVAILABLE = True
except ImportError:
    MODELS_SERVICE_AVAILABLE = False

# Import from shared modules (centralized, no duplication)
from .shared import COLORS
from .shared.colors import SIGNAL_COLORS
from .btc_inference_charts import build_btc_inference_figure
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
    try:
        signals = get_latest_signals(timeframe, "BTCUSDT")
    except InferenceDataNotFoundError as e:
        st.error(f"❌ {e}")
        with st.expander("🔎 Available symbols in realtime DB", expanded=False):
            symbols = list_realtime_symbols(timeframe)
            if symbols:
                st.code("\n".join(symbols[:200]))
            else:
                st.caption("No symbols found or realtime DB not available.")
        return
    
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
    
    net_score = signals.get('net_score_-100_100', 0)
    net_color = COLORS['success'] if net_score > 0 else COLORS['secondary']
    confidence = signals.get('confidence_0_100', 0)
    
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
                <div style="color: {COLORS['muted']}; font-size: 11px;">LONG (0-100)</div>
                <div style="color: {COLORS['long']}; font-size: 20px; font-weight: bold;">
                    {signals.get('score_long_0_100', 0):.1f}
                </div>
            </div>
            <div style="
                text-align: center;
                background: {COLORS['background']};
                padding: 12px;
                border-radius: 8px;
            ">
                <div style="color: {COLORS['muted']}; font-size: 11px;">SHORT (0-100)</div>
                <div style="color: {COLORS['short']}; font-size: 20px; font-weight: bold;">
                    {signals.get('score_short_0_100', 0):.1f}
                </div>
            </div>
            <div style="
                text-align: center;
                background: {COLORS['background']};
                padding: 12px;
                border-radius: 8px;
            ">
                <div style="color: {COLORS['muted']}; font-size: 11px;">Net (-100..100)</div>
                <div style="color: {net_color}; font-size: 20px; font-weight: bold;">
                    {net_score:+.1f}
                </div>
            </div>
        </div>
        <div style="
            color: {COLORS['muted']};
            font-size: 12px;
            margin-top: 10px;
        ">
            Confidence: <b style="color: {COLORS['text']};">{confidence:.1f}</b> &nbsp;|&nbsp;
            Short inverted: <b style="color: {COLORS['text']};">{signals.get('short_inverted', False)}</b>
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
    try:
        df = run_inference(timeframe, "BTCUSDT", 200)
    except InferenceDataNotFoundError as e:
        st.error(f"❌ {e}")
        with st.expander("🔎 Available symbols in realtime DB", expanded=False):
            symbols = list_realtime_symbols(timeframe)
            if symbols:
                st.code("\n".join(symbols[:200]))
            else:
                st.caption("No symbols found or realtime DB not available.")
        return
    
    if df is None or len(df) == 0:
        st.warning("⚠️ No inference data available. Check if historical data exists.")
        return
    
    st.markdown("#### 📊 Price Chart with ML Predictions")
    
    fig = build_btc_inference_figure(df=df, colors=COLORS, signal_colors=SIGNAL_COLORS)
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
                "Avg LONG (0-100)",
                f"{df['score_long_0_100'].mean():.1f}",
                f"{df['score_long_0_100'].std():.1f} std"
            )
        
        with col2:
            st.metric(
                "Avg SHORT (0-100)",
                f"{df['score_short_0_100'].mean():.1f}",
                f"{df['score_short_0_100'].std():.1f} std"
            )
        
        with col3:
            net_mean = df['net_score_-100_100'].mean()
            st.metric(
                "Avg Net (-100..100)",
                f"{net_mean:+.1f}",
                "Bullish Bias" if net_mean > 0 else "Bearish Bias"
            )


__all__ = ['render_btc_inference_section']
