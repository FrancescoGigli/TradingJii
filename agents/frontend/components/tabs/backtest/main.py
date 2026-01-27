"""
🔄 Backtest Tab - Main render function

Orchestrates all backtest sub-modules:
- controls: Settings and configuration
- signals: Dual signal comparison (Tech vs XGB)
- xgb_section: XGBoost ML backtest and simulation
"""

import streamlit as st
import pandas as pd

from database import get_symbols, get_ohlcv
from ai.backtest.engine import run_backtest
from ai.visualizations.backtest_charts import create_backtest_chart
from services.ml_inference import get_ml_inference_service, compute_ml_features, build_normalized_xgb_frame
from services.xgb_model_bundles import list_available_timeframes, load_bundle, predict_batch

from .controls import render_backtest_controls
from .signals import render_signal_comparison
from .xgb_section import render_xgb_section

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
    # CONTROLS
    # ═══════════════════════════════════════════════════════════════════
    settings = render_backtest_controls(symbols, symbol_map)
    
    # Run backtest button
    run_button = st.button("🚀 Run Backtest", type="primary", use_container_width=True)
    
    # ═══════════════════════════════════════════════════════════════════
    # LOAD DATA & RUN BACKTEST
    # ═══════════════════════════════════════════════════════════════════
    
    # Load data with warmup
    total_candles_needed = settings['num_candles'] + WARMUP_PERIOD
    df_full = get_ohlcv(settings['selected_symbol'], settings['selected_tf'], total_candles_needed)
    
    if df_full.empty:
        st.error("❌ No data available for this selection")
        st.stop()
    
    # Run backtest
    result = run_backtest(
        df_full,
        entry_threshold=settings['entry_threshold'],
        exit_threshold=settings['exit_threshold'],
        min_holding=settings['min_holding']
    )
    
    # Get statistics
    stats = result.trades.get_statistics()
    
    # ML service (legacy "latest" models, still used elsewhere)
    ml_service = get_ml_inference_service()

    # Pre-compute XGB normalized scores:
    # - One canonical frame used by chart + simulation (prefers model matching selected_tf)
    # - Optional additional frames for UI comparison (e.g. 15m + 1h)
    xgb_data = None
    xgb_frames: dict[str, pd.DataFrame] = {}
    try:
        df_features = compute_ml_features(df_full)

        # Compute per-timeframe frames if those model bundles exist.
        for tf in list_available_timeframes():
            bundle = load_bundle(tf)
            if bundle is None:
                continue
            df_pred = predict_batch(bundle, df_features)
            xgb_frames[tf] = build_normalized_xgb_frame(df_pred)

        # Choose the primary frame for chart/simulation.
        if settings['selected_tf'] in xgb_frames:
            xgb_data = xgb_frames[settings['selected_tf']]
        elif xgb_frames:
            # Fallback: just pick the first available timeframe.
            xgb_data = next(iter(xgb_frames.values()))
        else:
            # Legacy fallback: use latest models if available.
            if ml_service.is_available:
                df_pred = ml_service.predict_batch(df_features)
                xgb_data = build_normalized_xgb_frame(df_pred)
    except Exception:
        # Keep the rest of the backtest working even if XGB normalization fails.
        xgb_data = None
        xgb_frames = {}
    
    # ═══════════════════════════════════════════════════════════════════
    # SIGNAL COMPARISON
    # ═══════════════════════════════════════════════════════════════════
    render_signal_comparison(
        result,
        ml_service,
        df_full,
        settings['entry_threshold'],
        xgb_data=xgb_data,
        xgb_frames=xgb_frames,
    )
    
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
    # TECHNICAL BACKTEST CHART
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📊 Technical Backtest Chart")
    st.markdown("""
    <p style="color: #a0a0a0; font-size: 0.85rem;">
    Signal Calculator based on <b>RSI + MACD + Bollinger Bands</b>. 
    <b>▲</b> = LONG entry | <b>▼</b> = SHORT entry | <b>✗</b> = Exit |
    <span style="color: #00ff88;">Green line</span> = Profit | 
    <span style="color: #ff4757;">Red line</span> = Loss
    </p>
    """, unsafe_allow_html=True)
    
    # Create and display technical backtest chart
    tech_backtest_fig = create_backtest_chart(result, settings['selected_name'], xgb_data=None, xgb_threshold=0)
    st.plotly_chart(tech_backtest_fig, width='stretch', key="tech_chart")
    
    # ═══════════════════════════════════════════════════════════════════
    # XGB SECTION
    # ═══════════════════════════════════════════════════════════════════
    render_xgb_section(df_full, ml_service, settings['selected_name'], xgb_data=xgb_data)
    
    # Show warning if no trades were generated
    trades_list = result.trades.trades
    if not trades_list:
        conf_min = result.confidence_scores.min()
        conf_max = result.confidence_scores.max()
        
        st.warning(f"""
        ⚠️ **No Trades Generated**
        
        Confidence score ranges between **{conf_min:.1f}** and **{conf_max:.1f}**, 
        but entry threshold is set to **±{settings['entry_threshold']}**.
        
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
        - **Stop Loss**: Exit if loss exceeds SL % (if enabled)
        - **Take Profit**: Exit if profit exceeds TP % (if enabled)
        - **Max Holding**: Exit after N candles (if enabled)
        - **Signal Reversal**: Exit on opposite signal (after min holding)
        
        ### Chart Legend
        - **▲ Green Triangle**: LONG entry point
        - **▼ Red Triangle**: SHORT entry point  
        - **✗ Green X**: Exit with profit
        - **✗ Red X**: Exit with loss
        - **Dotted Lines**: Trade duration (green = profit, red = loss)
        """)
