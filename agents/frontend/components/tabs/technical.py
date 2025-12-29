"""
Technical Analysis Tab for the Crypto Dashboard
"""

import streamlit as st
import pandas as pd

from database import get_symbols, get_ohlcv
from indicators import (
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_atr
)


def render_technical_tab():
    """Render the Technical Analysis tab"""
    st.markdown("### 🔬 Technical Analysis")
    
    symbols = get_symbols()
    if not symbols:
        st.warning("No data available")
        st.stop()
    
    symbol_map = {s.replace('/USDT:USDT', ''): s for s in symbols}
    
    col1, col2 = st.columns([2, 1])
    with col1:
        ta_coin = st.selectbox("🪙 Select Coin", list(symbol_map.keys()), key="ta_coin")
    with col2:
        ta_tf = st.selectbox("⏱️ Timeframe", ['15m', '1h', '4h', '1d'], key="ta_tf")
    
    df_ta = get_ohlcv(symbol_map[ta_coin], ta_tf, 200)
    
    if not df_ta.empty:
        # Calculate all indicators
        rsi = calculate_rsi(df_ta)
        macd_line, signal_line, histogram = calculate_macd(df_ta)
        upper_bb, sma_bb, lower_bb = calculate_bollinger_bands(df_ta)
        atr = calculate_atr(df_ta)
        
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
        current_price = df_ta['close'].iloc[-1]
        bb_position = (current_price - lower_bb.iloc[-1]) / (upper_bb.iloc[-1] - lower_bb.iloc[-1]) * 100
        bb_status = "Upper 🔴" if bb_position > 80 else "Lower 🟢" if bb_position < 20 else "Middle ⚪"
        col4.metric("BB Position", f"{bb_position:.0f}%", bb_status)
        
        st.markdown("---")
        
        # Signal Summary
        st.markdown("#### 🎯 Signal Summary")
        
        signals = []
        
        # RSI Signal
        if current_rsi > 70:
            signals.append(("RSI", "SELL", "#ff4757"))
        elif current_rsi < 30:
            signals.append(("RSI", "BUY", "#00ff88"))
        else:
            signals.append(("RSI", "NEUTRAL", "#ffc107"))
        
        # MACD Signal
        if current_macd > current_signal and histogram.iloc[-1] > histogram.iloc[-2]:
            signals.append(("MACD", "BUY", "#00ff88"))
        elif current_macd < current_signal and histogram.iloc[-1] < histogram.iloc[-2]:
            signals.append(("MACD", "SELL", "#ff4757"))
        else:
            signals.append(("MACD", "NEUTRAL", "#ffc107"))
        
        # BB Signal
        if bb_position > 95:
            signals.append(("Bollinger", "SELL", "#ff4757"))
        elif bb_position < 5:
            signals.append(("Bollinger", "BUY", "#00ff88"))
        else:
            signals.append(("Bollinger", "NEUTRAL", "#ffc107"))
        
        # Display signals
        cols = st.columns(len(signals))
        for i, (indicator, signal, color) in enumerate(signals):
            with cols[i]:
                st.markdown(f"""
                <div style="background-color: {color}; padding: 15px; border-radius: 10px; text-align: center;">
                    <h4 style="color: white; margin: 0;">{indicator}</h4>
                    <h2 style="color: white; margin: 5px 0;">{signal}</h2>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Moving Averages Table
        st.markdown("#### 📈 Moving Averages")
        
        ma_data = []
        for period in [10, 20, 50, 100, 200]:
            if len(df_ta) >= period:
                sma = df_ta['close'].rolling(window=period).mean().iloc[-1]
                ema = df_ta['close'].ewm(span=period).mean().iloc[-1]
                signal = "BUY 🟢" if current_price > sma else "SELL 🔴"
                ma_data.append({
                    'Period': period,
                    'SMA': f"${sma:.2f}",
                    'EMA': f"${ema:.2f}",
                    'Signal': signal
                })
        
        st.dataframe(pd.DataFrame(ma_data), use_container_width=True, hide_index=True)
    else:
        st.warning("No data available for this selection")
