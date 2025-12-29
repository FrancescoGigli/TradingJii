"""
Advanced Charts Tab for the Crypto Dashboard
"""

import streamlit as st

from database import get_symbols, get_timeframes, get_ohlcv
from charts import create_advanced_chart
from utils import format_volume


def render_advanced_charts_tab():
    """Render the Advanced Charts tab"""
    st.markdown("### 📈 Advanced Candlestick Charts")
    
    symbols = get_symbols()
    if not symbols:
        st.warning("No data available")
        st.stop()
    
    symbol_map = {s.replace('/USDT:USDT', ''): s for s in symbols}
    
    # Controls
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        selected_name = st.selectbox("🪙 Select Coin", list(symbol_map.keys()), key="chart_coin")
        selected_symbol = symbol_map[selected_name]
    
    with col2:
        timeframes = get_timeframes(selected_symbol)
        tf_order = ['15m', '1h', '4h', '1d']
        timeframes_sorted = [tf for tf in tf_order if tf in timeframes]
        selected_tf = st.selectbox("⏱️ Timeframe", timeframes_sorted, key="chart_tf")
    
    with col3:
        num_candles = st.selectbox("🕯️ Candles", [50, 100, 150, 200], index=3, key="chart_candles")
    
    with col4:
        show_indicators = st.checkbox("📊 Indicators", value=True)
    
    # Load data
    df = get_ohlcv(selected_symbol, selected_tf, num_candles)
    
    if df.empty:
        st.error("No data for this selection")
        st.stop()
    
    # Metrics
    price = df['close'].iloc[-1]
    change = ((df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]) * 100
    high = df['high'].max()
    low = df['low'].min()
    vol = df['volume'].sum()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("💰 Price", f"${price:,.2f}", f"{change:+.2f}%")
    col2.metric("📈 24h High", f"${high:,.2f}")
    col3.metric("📉 24h Low", f"${low:,.2f}")
    col4.metric("📊 Volume", format_volume(vol))
    
    # Volatility
    volatility = ((high - low) / low * 100)
    col5.metric("⚡ Volatility", f"{volatility:.2f}%")
    
    st.markdown("---")
    
    # Chart
    fig = create_advanced_chart(df, selected_symbol, show_indicators)
    st.plotly_chart(fig, use_container_width=True)
    
    # Recent data
    with st.expander("📋 Recent Data Table"):
        table = df.tail(20).iloc[::-1].copy()
        table.index = table.index.strftime('%Y-%m-%d %H:%M')
        table['change'] = table['close'].pct_change() * 100
        st.dataframe(table.round(4), use_container_width=True)
