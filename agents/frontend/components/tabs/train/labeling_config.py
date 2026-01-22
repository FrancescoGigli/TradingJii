"""
⚙️ Labeling Configuration Module

ATR-based configuration UI for label generation.
Provides sliders and settings for ATR multipliers.
"""

import streamlit as st
from ai.core.labels import ATRLabelConfig


def render_atr_config_section() -> ATRLabelConfig:
    """
    Render ATR-based configuration section.
    
    Returns ATRLabelConfig with user-selected parameters.
    Defaults are chosen for STABILITY, not max performance.
    """
    
    st.markdown("#### ⚙️ ATR Configuration")
    
    st.info("""
    💡 **ATR-Based Labeling**: Stop loss and trailing are calculated as multiples of ATR (Average True Range).
    This makes the system **adaptive to volatility** of each coin.
    
    **The k_* parameters are chosen for STABILITY, not to maximize win rate!**
    """)
    
    with st.expander("🔧 ATR Multipliers (global, stable)", expanded=True):
        col_15m, col_1h = st.columns(2)
        
        with col_15m:
            st.markdown("##### 📊 **15 Minutes**")
            k_fixed_sl_15m = st.slider(
                "k_fixed_sl (Fixed SL)",
                min_value=1.5, max_value=4.0, value=2.8, step=0.1,
                key="k_fixed_sl_15m",
                help="Fixed SL = ATR% × k_fixed_sl. Ex: ATR=1.2%, k=2.8 → SL=3.36%"
            )
            k_trailing_15m = st.slider(
                "k_trailing (Trailing)",
                min_value=0.8, max_value=3.0, value=1.8, step=0.1,
                key="k_trailing_15m",
                help="Trailing SL = ATR% × k_trailing. Ex: ATR=1.2%, k=1.8 → Trailing=2.16%"
            )
            max_bars_15m = st.slider(
                "Max Bars",
                min_value=12, max_value=96, value=64,
                key="max_bars_15m", help="64 bars = 16 hours"
            )
        
        with col_1h:
            st.markdown("##### 📊 **1 Hour**")
            k_fixed_sl_1h = st.slider(
                "k_fixed_sl (Fixed SL)",
                min_value=1.5, max_value=5.0, value=3.2, step=0.1,
                key="k_fixed_sl_1h",
                help="Fixed SL = ATR% × k_fixed_sl"
            )
            k_trailing_1h = st.slider(
                "k_trailing (Trailing)",
                min_value=0.8, max_value=3.5, value=2.0, step=0.1,
                key="k_trailing_1h",
                help="Trailing SL = ATR% × k_trailing"
            )
            max_bars_1h = st.slider(
                "Max Bars",
                min_value=12, max_value=72, value=36,
                key="max_bars_1h", help="36 bars = 36 hours"
            )
        
        st.markdown("---")
        st.markdown("##### 💰 **Scoring Parameters (same for all)**")
        
        common_col1, common_col2, common_col3 = st.columns(3)
        with common_col1:
            time_penalty = st.slider(
                "Time Penalty λ",
                min_value=0.0001, max_value=0.01, value=0.001, step=0.0001,
                format="%.4f", key="time_penalty"
            )
        with common_col2:
            trading_cost = st.slider(
                "Trading Cost",
                min_value=0.0, max_value=0.005, value=0.001, step=0.0001,
                format="%.4f", key="trading_cost"
            )
        with common_col3:
            atr_period = st.slider(
                "ATR Period",
                min_value=7, max_value=21, value=14,
                key="atr_period", help="Period for ATR calculation"
            )
    
    # Show formula
    with st.expander("📐 Formula and Logic", expanded=False):
        st.markdown("""
        **Stop Loss Logic:**
        ```
        LONG Entry:
          fixed_sl = entry × (1 - k_fixed_sl × ATR%)
          trailing_sl = max_seen × (1 - k_trailing × ATR%)
          effective_sl = max(fixed_sl, trailing_sl)  ← stop never worsens!
        
        SHORT Entry:
          fixed_sl = entry × (1 + k_fixed_sl × ATR%)
          trailing_sl = min_seen × (1 + k_trailing × ATR%)
          effective_sl = min(fixed_sl, trailing_sl)  ← stop never worsens!
        ```
        
        **Score Formula:**
        ```
        score = R - λ×log(1+D) - costs
        ```
        Where:
        - R = realized return
        - D = bars held
        - λ = time penalty coefficient
        - costs = trading fees
        
        **What each exit type means:**
        - `fixed_sl`: Hit the fixed stop loss (max loss protection)
        - `trailing`: Hit trailing stop after profit locked in (good!)
        - `time`: Reached max_bars without hitting any stop (neutral/timeout)
        """)
    
    # Create config
    config = ATRLabelConfig()
    config.k_fixed_sl_15m = k_fixed_sl_15m
    config.k_trailing_15m = k_trailing_15m
    config.max_bars_15m = max_bars_15m
    config.k_fixed_sl_1h = k_fixed_sl_1h
    config.k_trailing_1h = k_trailing_1h
    config.max_bars_1h = max_bars_1h
    config.time_penalty_lambda = time_penalty
    config.trading_cost = trading_cost
    config.atr_period = atr_period
    
    return config


__all__ = ['render_atr_config_section']
