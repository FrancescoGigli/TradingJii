"""
⚙️ Backtest Controls - Settings and configuration UI
"""

import streamlit as st
from ai.core.config import BACKTEST_CONFIG


def render_backtest_controls(symbols: list, symbol_map: dict) -> dict:
    """
    Render backtest control panel.
    
    Returns dict with selected values:
    - selected_symbol
    - selected_name
    - selected_tf
    - num_candles
    - entry_threshold
    - exit_threshold
    - min_holding
    - stop_loss_pct
    - take_profit_pct
    - use_sl_tp
    - max_holding
    """
    from database import get_timeframes
    
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
        # Signal settings
        st.markdown("##### 📊 Signal Settings")
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
        
        st.markdown("---")
        
        # Stop Loss / Take Profit settings
        st.markdown("##### 🛑 Stop Loss / Take Profit")
        
        use_sl_tp = st.checkbox(
            "Enable SL/TP exits",
            value=BACKTEST_CONFIG.get('use_sl_tp', True),
            help="Exit trades when Stop Loss or Take Profit levels are hit"
        )
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            stop_loss_pct = st.slider(
                "🛑 Stop Loss %",
                min_value=0.5,
                max_value=10.0,
                value=float(BACKTEST_CONFIG.get('stop_loss_pct', 2.0)),
                step=0.5,
                help="Exit if loss exceeds this percentage",
                disabled=not use_sl_tp
            )
        
        with col2:
            take_profit_pct = st.slider(
                "🎯 Take Profit %",
                min_value=1.0,
                max_value=20.0,
                value=float(BACKTEST_CONFIG.get('take_profit_pct', 4.0)),
                step=0.5,
                help="Exit if profit exceeds this percentage",
                disabled=not use_sl_tp
            )
        
        with col3:
            max_holding = st.slider(
                "⏰ Max Holding (candles)",
                min_value=0,
                max_value=200,
                value=BACKTEST_CONFIG.get('max_holding_candles', 0),
                step=10,
                help="Force exit after N candles (0 = disabled)"
            )
        
        # Store settings in session state for optimizer
        st.session_state['backtest_settings'] = {
            'entry_threshold': entry_threshold,
            'exit_threshold': exit_threshold,
            'min_holding': min_holding,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'use_sl_tp': use_sl_tp,
            'max_holding_candles': max_holding
        }
    
    return {
        'selected_symbol': selected_symbol,
        'selected_name': selected_name,
        'selected_tf': selected_tf,
        'num_candles': num_candles,
        'entry_threshold': entry_threshold,
        'exit_threshold': exit_threshold,
        'min_holding': min_holding,
        'stop_loss_pct': stop_loss_pct,
        'take_profit_pct': take_profit_pct,
        'use_sl_tp': use_sl_tp,
        'max_holding': max_holding
    }
