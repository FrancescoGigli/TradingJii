"""
📊 Unified Analysis Tab for the Crypto Dashboard
Combines: Advanced Charts + Volume Analysis + Technical Analysis
Uses centralized colors and styled components
"""

import streamlit as st
import pandas as pd

from database import get_symbols, get_timeframes, get_ohlcv
from charts import create_advanced_chart, create_volume_analysis_chart
from indicators import (
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_atr,
    calculate_vwap
)
from utils import format_volume
from styles import (
    PALETTE, 
    SIGNAL_COLORS,
    styled_table, 
    styled_signal_box,
    get_signal_color
)

# Warmup period to skip for display (indicators need this many candles to calculate)
WARMUP_PERIOD = 50


def render_analysis_tab():
    """Render the unified Analysis tab with Chart, Volume Analysis, and Technical Analysis"""
    
    # Get symbols ordered by volume
    symbols = get_symbols()
    if not symbols:
        st.warning("No data available")
        st.stop()
    
    # Create symbol map (display name -> full symbol)
    symbol_map = {s.replace('/USDT:USDT', ''): s for s in symbols}
    
    # ═══════════════════════════════════════════════════════════════════
    # CONTROLS SECTION
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("### 📊 Coin Analysis")
    
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        selected_name = st.selectbox(
            "🪙 Select Coin (ordered by volume)", 
            list(symbol_map.keys()), 
            key="analysis_coin"
        )
        selected_symbol = symbol_map[selected_name]
    
    with col2:
        timeframes = get_timeframes(selected_symbol)
        tf_order = ['15m', '1h', '4h', '1d']
        timeframes_sorted = [tf for tf in tf_order if tf in timeframes]
        selected_tf = st.selectbox("⏱️ Timeframe", timeframes_sorted, key="analysis_tf")
    
    with col3:
        num_candles = st.selectbox("🕯️ Candles", [50, 100, 150, 200], index=3, key="analysis_candles")
    
    # Load data with extra warmup
    total_candles_needed = num_candles + WARMUP_PERIOD
    df_full = get_ohlcv(selected_symbol, selected_tf, total_candles_needed)
    
    if df_full.empty:
        st.error("No data for this selection")
        st.stop()
    
    # ═══════════════════════════════════════════════════════════════════
    # PRICE METRICS
    # ═══════════════════════════════════════════════════════════════════
    df_display = df_full.tail(num_candles).copy()
    
    price = df_display['close'].iloc[-1]
    change = ((df_display['close'].iloc[-1] - df_display['close'].iloc[0]) / df_display['close'].iloc[0]) * 100
    high = df_display['high'].max()
    low = df_display['low'].min()
    vol = df_display['volume'].sum()
    volatility = ((high - low) / low * 100)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("💰 Price", f"${price:,.2f}", f"{change:+.2f}%")
    col2.metric("📈 Period High", f"${high:,.2f}")
    col3.metric("📉 Period Low", f"${low:,.2f}")
    col4.metric("📊 Volume", format_volume(vol))
    col5.metric("⚡ Volatility", f"{volatility:.2f}%")
    
    st.markdown("---")
    
    # ═══════════════════════════════════════════════════════════════════
    # MAIN CHART SECTION
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("### 📈 Advanced Chart")
    
    fig = create_advanced_chart(df_full, selected_symbol, show_indicators=True, warmup_skip=WARMUP_PERIOD)
    st.plotly_chart(fig, use_container_width=True)
    
    # ═══════════════════════════════════════════════════════════════════
    # VOLUME ANALYSIS SECTION
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📉 Volume Analysis")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 Avg Volume", format_volume(df_display['volume'].mean()))
    col2.metric("📈 Max Volume", format_volume(df_display['volume'].max()))
    col3.metric("📉 Min Volume", format_volume(df_display['volume'].min()))
    col4.metric("📐 Std Dev", format_volume(df_display['volume'].std()))
    
    # VWAP Analysis
    vwap = calculate_vwap(df_full)
    current_price = df_display['close'].iloc[-1]
    vwap_current = vwap.iloc[-1]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("💵 Current Price", f"${current_price:,.2f}")
    col2.metric("📊 VWAP", f"${vwap_current:,.2f}")
    
    diff_vwap = ((current_price - vwap_current) / vwap_current) * 100
    status = "Above VWAP 📈" if diff_vwap > 0 else "Below VWAP 📉"
    col3.metric("📍 Status", status, f"{diff_vwap:+.2f}%")
    
    # Volume Chart
    fig_vol = create_volume_analysis_chart(df_display, selected_name)
    st.plotly_chart(fig_vol, use_container_width=True)
    
    # ═══════════════════════════════════════════════════════════════════
    # TECHNICAL ANALYSIS SECTION
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 🔬 Technical Analysis")
    
    # Calculate all indicators on full data
    rsi = calculate_rsi(df_full)
    macd_line, signal_line, histogram = calculate_macd(df_full)
    upper_bb, sma_bb, lower_bb = calculate_bollinger_bands(df_full)
    atr = calculate_atr(df_full)
    
    # Current values (last value)
    st.markdown("#### 📊 Current Indicator Values")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # RSI
    current_rsi = rsi.iloc[-1]
    rsi_status = "Overbought 🔴" if current_rsi > 70 else "Oversold 🟢" if current_rsi < 30 else "Neutral ⚪"
    col1.metric("RSI (14)", f"{current_rsi:.1f}", rsi_status)
    
    # MACD
    current_macd = macd_line.iloc[-1]
    current_signal = signal_line.iloc[-1]
    macd_status = "Bullish 🟢" if current_macd > current_signal else "Bearish 🔴"
    col2.metric("MACD", f"{current_macd:.4f}", macd_status)
    
    # ATR
    current_atr = atr.iloc[-1]
    col3.metric("ATR (14)", f"${current_atr:.2f}")
    
    # BB Position
    bb_position = (current_price - lower_bb.iloc[-1]) / (upper_bb.iloc[-1] - lower_bb.iloc[-1]) * 100
    bb_status = "Upper 🔴" if bb_position > 80 else "Lower 🟢" if bb_position < 20 else "Middle ⚪"
    col4.metric("BB Position", f"{bb_position:.0f}%", bb_status)
    
    st.markdown("---")
    
    # Signal Summary
    st.markdown("#### 🎯 Signal Summary")
    
    signals = []
    
    # RSI Signal
    if current_rsi > 70:
        signals.append(("RSI", "SELL", SIGNAL_COLORS['sell']))
    elif current_rsi < 30:
        signals.append(("RSI", "BUY", SIGNAL_COLORS['buy']))
    else:
        signals.append(("RSI", "NEUTRAL", SIGNAL_COLORS['neutral']))
    
    # MACD Signal
    if current_macd > current_signal and histogram.iloc[-1] > histogram.iloc[-2]:
        signals.append(("MACD", "BUY", SIGNAL_COLORS['buy']))
    elif current_macd < current_signal and histogram.iloc[-1] < histogram.iloc[-2]:
        signals.append(("MACD", "SELL", SIGNAL_COLORS['sell']))
    else:
        signals.append(("MACD", "NEUTRAL", SIGNAL_COLORS['neutral']))
    
    # BB Signal
    if bb_position > 95:
        signals.append(("Bollinger", "SELL", SIGNAL_COLORS['sell']))
    elif bb_position < 5:
        signals.append(("Bollinger", "BUY", SIGNAL_COLORS['buy']))
    else:
        signals.append(("Bollinger", "NEUTRAL", SIGNAL_COLORS['neutral']))
    
    # Display signals using styled components
    cols = st.columns(len(signals))
    for i, (indicator, signal, color) in enumerate(signals):
        with cols[i]:
            st.markdown(styled_signal_box(indicator, signal, color), unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════
    # RECENT DATA TABLE (Expandable)
    # ═══════════════════════════════════════════════════════════════════
    with st.expander("📋 Recent Data Table"):
        table = df_display.tail(20).iloc[::-1].copy()
        table.index = table.index.strftime('%Y-%m-%d %H:%M')
        table['change'] = table['close'].pct_change() * 100
        
        # Format for display
        display_table = table.round(4).reset_index()
        display_table.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Change %']
        st.markdown(styled_table(display_table), unsafe_allow_html=True)
