"""
🏷️ Train Tab - Step 2: Labeling (ATR-Based)

Main orchestrator for ATR-based label generation.
Uses modular components for clean separation of concerns.

Structure:
┌────────────────────────────────────────────────────────────────┐
│ Step 2: Labeling                                                │
├────────────────────────────────────────────────────────────────┤
│ ⚙️ ATR Configuration (sliders)                                  │
│ [🏷️ Generate Labels] ← single action button                    │
├────────────────────────────────────────────────────────────────┤
│ 📤 Status (auto - shows existing labels count)                 │
├────────────────────────────────────────────────────────────────┤
│ 🔍 Symbol/Timeframe Selector                                    │
├────────────────────────────────────────────────────────────────┤
│ 📊 Statistics (auto)                                           │
├────────────────────────────────────────────────────────────────┤
│ 📋 Labels Table Preview (First 50 + ... + Last 50)             │
├────────────────────────────────────────────────────────────────┤
│ 📈 Analysis Dashboard (auto)                                    │
├────────────────────────────────────────────────────────────────┤
│ 🔍 Stability Report (auto)                                      │
├────────────────────────────────────────────────────────────────┤
│ 👁️ Visualizer (candlestick + markers - auto)                   │
└────────────────────────────────────────────────────────────────┘

Modules used:
- labeling_config: ATR configuration UI
- labeling_db: Database operations
- labeling_pipeline: Label generation
- labeling_table: Labels table preview
- labeling_analysis: Charts and diagnostics
- labeling_visualizer: Candlestick visualization
"""

import streamlit as st

# Import configuration module
from .labeling_config import render_atr_config_section

# Import database operations
from .labeling_db import (
    get_training_features_symbols,
    get_training_labels_stats,
    get_label_statistics
)

# Import pipeline
from .labeling_pipeline import run_labeling_pipeline_both

# Import table preview
from .labeling_table import render_labels_table_preview

# Import visualizer
from .labeling_visualizer import get_available_symbols_with_labels


def render_status_section() -> bool:
    """
    Render existing labels status.
    
    Returns:
        True if labels exist, False otherwise
    """
    st.markdown("#### 📤 Labels Status")
    
    labels_stats = get_training_labels_stats()
    
    if labels_stats:
        for tf, data in labels_stats.items():
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Timeframe", tf)
            col2.metric("Symbols", data['symbols'])
            col3.metric("Rows", f"{data['total_rows']:,}")
            col4.metric("Avg Score (Long)", f"{data['avg_score_long']:.4f}" if data['avg_score_long'] else "N/A")
        st.success("✅ Training labels exist")
        return True
    else:
        st.warning("⚠️ No training labels generated yet")
        return False


def render_symbol_timeframe_selector() -> tuple:
    """
    Render symbol and timeframe selector.
    
    Returns:
        Tuple of (selected_symbol, selected_timeframe)
    """
    st.markdown("#### 🔍 Symbol Selector")
    
    # Default to 15m - can be changed if needed
    selected_tf = '15m'
    
    # Get available symbols for timeframe
    symbols = get_available_symbols_with_labels(selected_tf)
    
    if not symbols:
        st.warning(f"No labels available for {selected_tf}")
        return None, selected_tf
    
    # Default to BTC if available
    btc_symbols = [s for s in symbols if 'BTC' in s]
    default_idx = symbols.index(btc_symbols[0]) if btc_symbols else 0
    
    selected_symbol = st.selectbox(
        "Symbol",
        symbols,
        index=default_idx,
        format_func=lambda x: x.replace('/USDT:USDT', ''),
        key="labeling_symbol_selector"
    )
    
    return selected_symbol, selected_tf


def render_statistics_section(timeframe: str):
    """Render label statistics for selected timeframe."""
    st.markdown("#### 📊 Statistics")
    
    stats = get_label_statistics(timeframe)
    if stats:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Samples", f"{stats['total_samples']:,}")
        c2.metric("Avg Score (Long)", f"{stats['avg_score_long']:.5f}")
        c3.metric("Avg Score (Short)", f"{stats['avg_score_short']:.5f}")
        c4.metric("% Positive (Long)", f"{stats['pct_positive_long']:.1f}%")
    else:
        st.info(f"No statistics available for {timeframe}")


def render_analysis_dashboard(symbol: str, timeframe: str):
    """Render analysis dashboard with charts."""
    st.markdown("#### 📈 Analysis Dashboard")
    
    try:
        from .labeling_analysis import (
            create_score_distribution,
            create_atr_analysis,
            create_exit_type_pie,
            create_mae_histogram,
            create_mae_vs_score_scatter,
            create_bars_held_histogram
        )
        from database.ml_labels import get_training_labels
        
        labels_df = get_training_labels(timeframe, symbol)
        
        if labels_df is None or len(labels_df) == 0:
            st.warning("No labels available for analysis")
            return
        
        # Row 1: Score distribution and ATR
        col1, col2 = st.columns(2)
        with col1:
            fig = create_score_distribution(labels_df, timeframe)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = create_atr_analysis(labels_df, timeframe)
            st.plotly_chart(fig, use_container_width=True)
        
        # Row 2: Exit type pie charts
        st.markdown("##### Exit Type Analysis")
        col1, col2 = st.columns(2)
        with col1:
            fig = create_exit_type_pie(labels_df, timeframe, 'long')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = create_exit_type_pie(labels_df, timeframe, 'short')
            st.plotly_chart(fig, use_container_width=True)
        
        # Row 3: MAE analysis
        st.markdown("##### MAE Histograms (LONG / SHORT)")
        col1, col2 = st.columns(2)
        with col1:
            fig = create_mae_histogram(labels_df, timeframe, 'long')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = create_mae_histogram(labels_df, timeframe, 'short')
            st.plotly_chart(fig, use_container_width=True)
        
        # Row 4: MAE vs Score scatter
        st.markdown("##### MAE vs Score Scatter")
        col1, col2 = st.columns(2)
        with col1:
            fig = create_mae_vs_score_scatter(labels_df, timeframe, 'long')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = create_mae_vs_score_scatter(labels_df, timeframe, 'short')
            st.plotly_chart(fig, use_container_width=True)
        
        # Row 5: Bars held
        st.markdown("##### Bars Held Analysis")
        col1, col2 = st.columns(2)
        with col1:
            fig = create_bars_held_histogram(labels_df, timeframe, 'long')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = create_bars_held_histogram(labels_df, timeframe, 'short')
            st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error loading analysis: {e}")
        import traceback
        st.code(traceback.format_exc())


def render_stability_report(symbol: str, timeframe: str):
    """Render stability report."""
    st.markdown("#### 🔍 Stability Report")
    
    try:
        from .labeling_analysis import get_stability_report
        from database.ml_labels import get_training_labels
        
        labels_df = get_training_labels(timeframe, symbol)
        
        if labels_df is None or len(labels_df) == 0:
            st.warning("No labels available for stability report")
            return
        
        report = get_stability_report(labels_df, timeframe)
        
        if not report.get('valid', False):
            st.error(f"Cannot generate report: {report.get('reason', 'Unknown error')}")
            return
        
        # Overall status
        if report.get('is_stable', False):
            st.success("✅ Parameters appear STABLE - good for ML training")
        else:
            st.warning("⚠️ Parameters may need adjustment")
            for warning in report.get('warnings', []):
                st.warning(warning)
        
        # Metrics
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**LONG Labels:**")
            st.write(f"- Score Mean: {report.get('long_score_mean', 0):.5f}")
            st.write(f"- Score Std: {report.get('long_score_std', 0):.5f}")
            st.write(f"- Positive: {report.get('long_positive_pct', 0):.1f}%")
            st.write(f"- Avg MAE: {report.get('long_mae_mean', 0):.2f}%")
            st.write(f"- Exit: fixed_sl {report.get('long_fixed_sl_pct', 0):.1f}% | trailing {report.get('long_trailing_pct', 0):.1f}% | time {report.get('long_time_pct', 0):.1f}%")
        
        with col2:
            st.markdown("**SHORT Labels:**")
            st.write(f"- Score Mean: {report.get('short_score_mean', 0):.5f}")
            st.write(f"- Score Std: {report.get('short_score_std', 0):.5f}")
            st.write(f"- Positive: {report.get('short_positive_pct', 0):.1f}%")
            st.write(f"- Avg MAE: {report.get('short_mae_mean', 0):.2f}%")
            st.write(f"- Exit: fixed_sl {report.get('short_fixed_sl_pct', 0):.1f}% | trailing {report.get('short_trailing_pct', 0):.1f}% | time {report.get('short_time_pct', 0):.1f}%")
        
    except Exception as e:
        st.error(f"Error loading stability report: {e}")


def render_visualizer(selected_symbol: str, timeframe: str):
    """Render candlestick visualizer for the SELECTED symbol/timeframe."""
    st.markdown("#### 👁️ Visualizer")
    
    try:
        from .labeling_visualizer import get_labels_with_prices, create_labels_chart
        
        # Get last 200 candles
        df = get_labels_with_prices(selected_symbol, timeframe, 200)
        
        if df is None or len(df) == 0:
            st.warning(f"No OHLCV data available for visualizer")
            return
        
        # Main chart
        symbol_short = selected_symbol.replace('/USDT:USDT', '')
        fig = create_labels_chart(df, timeframe)
        fig.update_layout(title=f"📊 {symbol_short} ({timeframe}) - Last {len(df)} candles")
        st.plotly_chart(fig, use_container_width=True)
        
        # Legend
        st.markdown("""
        **📖 How to read:**
        🟢 Triangle Up = LONG+ | 🔴 Triangle Down = SHORT+ | Score Bars: Green = profit, Red = loss
        """)
        
    except Exception as e:
        st.error(f"Error loading visualizer: {e}")


def run_labeling_process(config, symbols_15m: list, symbols_1h: list):
    """Run ATR-based labeling with progress display."""
    st.markdown("#### 🔄 Generating ATR-Based Labels")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    current_tf_text = st.empty()
    
    total_symbols = len(symbols_15m) + len(symbols_1h)
    
    def update_progress(current, total, symbol, timeframe):
        if timeframe == '15m':
            overall = current
        else:
            overall = len(symbols_15m) + current
        progress_bar.progress(overall / total_symbols if total_symbols > 0 else 0)
        current_tf_text.markdown(f"**Processing: {timeframe}**")
        status_text.text(f"Symbol {overall}/{total_symbols}: {symbol.replace('/USDT:USDT', '')}")
    
    success, message = run_labeling_pipeline_both(config, update_progress)
    
    if success:
        st.success(f"✅ {message}")
        st.cache_data.clear()
    else:
        st.error(f"❌ {message}")


def render_labeling_step():
    """
    Main entry point: Render Step 2 Labeling.
    
    Flow:
    1. Check prerequisites (training features available)
    2. Show ATR configuration
    3. Single Generate Labels button
    4. Auto-display all sections when labels exist
    """
    st.markdown("### 🏷️ Step 2: Labeling (ATR-Based)")
    st.caption("Generate training labels using ATR-based Trailing Stop simulation")
    
    # === CHECK PREREQUISITES ===
    symbols_15m = get_training_features_symbols('15m')
    symbols_1h = get_training_features_symbols('1h')
    
    if not symbols_15m and not symbols_1h:
        st.error("❌ **No training features available!**")
        st.info("Complete **Step 1 (Data)** first to prepare training features.")
        return
    
    # Show available data
    st.markdown("#### 📥 Available Data (COMPLETE downloads only)")
    c1, c2 = st.columns(2)
    c1.metric("15m Symbols (COMPLETE)", len(symbols_15m))
    c2.metric("1h Symbols (COMPLETE)", len(symbols_1h))
    
    st.info(f"ℹ️ **ATR-based labels will be generated for BOTH timeframes:** {len(symbols_15m)} symbols for 15m and {len(symbols_1h)} symbols for 1h")
    
    # === ATR CONFIGURATION ===
    st.divider()
    config = render_atr_config_section()
    
    # === SINGLE ACTION BUTTON ===
    st.divider()
    
    if st.button("🏷️ Generate Labels", use_container_width=True, type="primary"):
        st.session_state['start_labeling'] = True
    
    # === RUN LABELING ===
    if st.session_state.get('start_labeling'):
        st.divider()
        run_labeling_process(config, symbols_15m, symbols_1h)
        st.session_state['start_labeling'] = False
    
    # === AUTO SECTIONS (only if labels exist) ===
    st.divider()
    labels_exist = render_status_section()
    
    if labels_exist:
        # GLOBAL LABEL QUALITY ANALYSIS
        st.divider()
        st.markdown("#### 🎯 Global Label Quality Analysis")
        st.caption("Aggregated analysis across ALL symbols and timeframes - reactive to your data")
        
        with st.expander("📊 View Deep Dive Quality Analysis", expanded=False):
            try:
                from .labeling_analysis import render_label_quality_analysis
                render_label_quality_analysis()
            except Exception as e:
                st.error(f"Error loading quality analysis: {e}")
                import traceback
                st.code(traceback.format_exc())
        
        # Symbol/Timeframe Selector
        st.divider()
        selected_symbol, selected_tf = render_symbol_timeframe_selector()
        
        if selected_symbol:
            # Statistics
            st.divider()
            render_statistics_section(selected_tf)
            
            # Labels Table Preview
            st.divider()
            render_labels_table_preview(selected_symbol, selected_tf)
            
            # Analysis Dashboard
            st.divider()
            render_analysis_dashboard(selected_symbol, selected_tf)
            
            # Stability Report
            st.divider()
            render_stability_report(selected_symbol, selected_tf)
            
            # Visualizer
            st.divider()
            render_visualizer(selected_symbol, selected_tf)


__all__ = ['render_labeling_step']
