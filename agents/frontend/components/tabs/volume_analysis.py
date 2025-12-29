"""
Volume Analysis Tab for the Crypto Dashboard
"""

import streamlit as st

from database import get_symbols, get_ohlcv
from charts import create_volume_analysis_chart
from indicators import calculate_vwap
from utils import format_volume


def render_volume_analysis_tab():
    """Render the Volume Analysis tab"""
    st.markdown("### 📉 Volume Analysis")
    
    symbols = get_symbols()
    if not symbols:
        st.warning("No data available")
        st.stop()
    
    symbol_map = {s.replace('/USDT:USDT', ''): s for s in symbols}
    
    col1, col2 = st.columns([2, 1])
    with col1:
        vol_coin = st.selectbox("🪙 Select Coin", list(symbol_map.keys()), key="vol_coin")
    with col2:
        vol_tf = st.selectbox("⏱️ Timeframe", ['15m', '1h', '4h', '1d'], key="vol_tf")
    
    df_vol = get_ohlcv(symbol_map[vol_coin], vol_tf, 200)
    
    if not df_vol.empty:
        # Volume stats
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📊 Avg Volume", format_volume(df_vol['volume'].mean()))
        col2.metric("📈 Max Volume", format_volume(df_vol['volume'].max()))
        col3.metric("📉 Min Volume", format_volume(df_vol['volume'].min()))
        col4.metric("📐 Std Dev", format_volume(df_vol['volume'].std()))
        
        st.markdown("---")
        
        # Volume Analysis Chart
        fig_vol = create_volume_analysis_chart(df_vol, vol_coin)
        st.plotly_chart(fig_vol, use_container_width=True)
        
        # VWAP
        st.markdown("#### 📊 VWAP Analysis")
        vwap = calculate_vwap(df_vol)
        current_price = df_vol['close'].iloc[-1]
        vwap_current = vwap.iloc[-1]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Current Price", f"${current_price:,.2f}")
        col2.metric("VWAP", f"${vwap_current:,.2f}")
        
        diff_vwap = ((current_price - vwap_current) / vwap_current) * 100
        status = "Above VWAP 📈" if diff_vwap > 0 else "Below VWAP 📉"
        col3.metric("Status", status, f"{diff_vwap:+.2f}%")
    else:
        st.warning("No data available for this selection")
