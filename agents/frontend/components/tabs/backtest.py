"""
🔄 Backtest Tab - Visual backtesting interface

Shows:
- Candlestick chart with entry/exit markers
- Confidence score bar for each candle
- Component breakdown (RSI, MACD, BB contributions)
- Trade statistics
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from database import get_symbols, get_timeframes, get_ohlcv
from ai.backtest.engine import run_backtest
from ai.core.config import BACKTEST_CONFIG, get_confidence_level
from ai.visualizations.backtest_charts import (
    create_backtest_chart,
    create_confidence_gauge,
    create_component_breakdown_chart
)

# Warmup period for indicators
WARMUP_PERIOD = 50


def render_backtest_tab():
    """Render the Backtest tab with visual backtesting"""
    
    # Get available symbols
    symbols = get_symbols()
    if not symbols:
        st.warning("⚠️ No data available. Wait for data-fetcher to load data.")
        st.stop()
    
    # Create symbol map (display name -> full symbol)
    symbol_map = {s.replace('/USDT:USDT', ''): s for s in symbols}
    
    # ═══════════════════════════════════════════════════════════════════
    # HEADER
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("### 🔄 Visual Backtesting")
    st.markdown("""
    <p style="color: #a0a0a0; font-size: 0.9rem;">
    Test trading strategies based on technical indicators. 
    The system calculates a <b>confidence score</b> from RSI, MACD, and Bollinger Bands, 
    then simulates entries when confidence exceeds thresholds.
    </p>
    """, unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════
    # CONTROLS
    # ═══════════════════════════════════════════════════════════════════
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        selected_name = st.selectbox(
            "🪙 Select Coin (ordered by volume)",
            list(symbol_map.keys()),
            key="backtest_coin"
        )
        selected_symbol = symbol_map[selected_name]
    
    with col2:
        timeframes = get_timeframes(selected_symbol)
        tf_order = ['15m', '1h', '4h', '1d']
        timeframes_sorted = [tf for tf in tf_order if tf in timeframes]
        selected_tf = st.selectbox("⏱️ Timeframe", timeframes_sorted, key="backtest_tf")
    
    with col3:
        num_candles = st.selectbox("🕯️ Candles", [100, 150, 200, 300, 500], index=2, key="backtest_candles")
    
    # Advanced settings expander
    with st.expander("⚙️ Backtest Settings"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            entry_threshold = st.slider(
                "Entry Threshold",
                min_value=5,
                max_value=80,
                value=BACKTEST_CONFIG['entry_threshold'],
                step=5,
                help="Minimum |confidence| to open a position (±)"
            )
        
        with col2:
            exit_threshold = st.slider(
                "Exit Threshold",
                min_value=5,
                max_value=50,
                value=BACKTEST_CONFIG['exit_threshold'],
                step=5,
                help="Opposite confidence to close position"
            )
        
        with col3:
            min_holding = st.slider(
                "Min Holding (candles)",
                min_value=1,
                max_value=10,
                value=BACKTEST_CONFIG['min_holding_candles'],
                step=1,
                help="Minimum candles before exit allowed"
            )
    
    # Run backtest button
    run_button = st.button("🚀 Run Backtest", type="primary", use_container_width=True)
    
    # ═══════════════════════════════════════════════════════════════════
    # LOAD DATA & RUN BACKTEST
    # ═══════════════════════════════════════════════════════════════════
    
    # Load data with warmup
    total_candles_needed = num_candles + WARMUP_PERIOD
    df_full = get_ohlcv(selected_symbol, selected_tf, total_candles_needed)
    
    if df_full.empty:
        st.error("❌ No data available for this selection")
        st.stop()
    
    # Run backtest
    result = run_backtest(
        df_full,
        entry_threshold=entry_threshold,
        exit_threshold=exit_threshold,
        min_holding=min_holding
    )
    
    # Get statistics
    stats = result.trades.get_statistics()
    
    # ═══════════════════════════════════════════════════════════════════
    # CURRENT CONFIDENCE DISPLAY
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 🎯 Current Signal")
    
    current_confidence = result.confidence_scores.iloc[-1]
    level_info = get_confidence_level(current_confidence)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        st.metric(
            "Confidence Score",
            f"{current_confidence:+.1f}",
            delta=level_info['label']
        )
    
    with col2:
        # Confidence gauge
        gauge_fig = create_confidence_gauge(current_confidence)
        st.plotly_chart(gauge_fig, use_container_width=True)
    
    with col3:
        # Component breakdown
        components_data = result.signal_components
        breakdown_fig = create_component_breakdown_chart(components_data)
        st.plotly_chart(breakdown_fig, use_container_width=True)
    
    # ═══════════════════════════════════════════════════════════════════
    # BACKTEST STATISTICS
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📊 Backtest Statistics")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    col1.metric(
        "Total Trades",
        stats['total_trades'],
        f"🟢 {stats['long_trades']} L / 🔴 {stats['short_trades']} S"
    )
    
    col2.metric(
        "Win Rate",
        f"{stats['win_rate']:.1f}%",
        f"✅ {stats['winning_trades']} / ❌ {stats['losing_trades']}"
    )
    
    col3.metric(
        "Total Return",
        f"{stats['total_return']:+.2f}%",
        "Compounded"
    )
    
    col4.metric(
        "Avg Trade",
        f"{stats['average_trade']:+.2f}%"
    )
    
    col5.metric(
        "Best / Worst",
        f"{stats['best_trade']:+.1f}%",
        f"{stats['worst_trade']:+.1f}%"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # MAIN BACKTEST CHART
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📈 Backtest Chart")
    st.markdown("""
    <p style="color: #a0a0a0; font-size: 0.85rem;">
    <b>▲</b> = LONG entry | <b>▼</b> = SHORT entry | <b>✗</b> = Exit | 
    <span style="color: #00ff88;">Green line</span> = Profit | 
    <span style="color: #ff4757;">Red line</span> = Loss
    </p>
    """, unsafe_allow_html=True)
    
    # Create and display backtest chart
    backtest_fig = create_backtest_chart(result, selected_name)
    st.plotly_chart(backtest_fig, use_container_width=True)
    
    # Show warning if no trades were generated
    trades_df = result.trades.to_dataframe()
    if trades_df.empty:
        conf_min = result.confidence_scores.min()
        conf_max = result.confidence_scores.max()
        
        st.warning(f"""
        ⚠️ **No Trades Generated**
        
        Confidence score ranges between **{conf_min:.1f}** and **{conf_max:.1f}**, 
        but entry threshold is set to **±{entry_threshold}**.
        
        **Solutions:**
        - Lower Entry Threshold to **{max(5, int(abs(conf_max) - 5))}** or less
        - Try more volatile timeframes (1h, 4h)
        - Try more volatile coins (altcoins vs BTC)
        """)
    
    # ═══════════════════════════════════════════════════════════════════
    # EXPLANATION
    # ═══════════════════════════════════════════════════════════════════
    with st.expander("ℹ️ How It Works", expanded=False):
        st.markdown("""
        ### Confidence Score Calculation
        
        The system calculates a **confidence score** from -100 (strong SHORT) to +100 (strong LONG) 
        based on three technical indicators:
        
        | Indicator | Contribution | Logic |
        |-----------|-------------|-------|
        | **RSI** | ±33.33 | RSI < 30 = LONG, RSI > 70 = SHORT |
        | **MACD** | ±33.33 | MACD > Signal = LONG, MACD < Signal = SHORT |
        | **Bollinger** | ±33.33 | Price near lower = LONG, near upper = SHORT |
        
        ### Entry Rules
        - **LONG Entry**: Confidence > +Entry Threshold
        - **SHORT Entry**: Confidence < -Entry Threshold
        
        ### Exit Rules
        - **Exit LONG**: Confidence drops below -Exit Threshold
        - **Exit SHORT**: Confidence rises above +Exit Threshold
        - Minimum holding period must pass before exit
        
        ### Chart Legend
        - **▲ Green Triangle**: LONG entry point
        - **▼ Red Triangle**: SHORT entry point  
        - **✗ Green X**: Exit with profit
        - **✗ Red X**: Exit with loss
        - **Dotted Lines**: Trade duration (green = profit, red = loss)
        """)
