"""
📊 ML Labels Visualization - Single Coin View

This module provides visualization tools for exploring
ML training labels for a single selected coin.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from io import BytesIO

from database import (
    get_ml_labels,
    get_available_symbols_for_labels,
    get_ml_labels_stats
)

# Import visualization functions
try:
    from ai.visualizations.label_charts import (
        create_score_overlay_chart,
        create_score_distribution,
        create_score_heatmap,
        create_mfe_mae_scatter,
        create_label_summary_table,
        create_entry_exit_chart,
        create_combined_entry_exit_chart
    )
    CHARTS_AVAILABLE = True
except ImportError as e:
    print(f"Charts import error: {e}")
    CHARTS_AVAILABLE = False


def render_single_coin_visualization():
    """Render visualization for a single selected coin"""
    
    st.markdown("### 📊 Single Coin Visualization")
    st.caption("Explore labels for a specific coin from the database")
    
    # Check if we have data
    db_stats = get_ml_labels_stats()
    
    if not db_stats.get('exists') or db_stats.get('empty'):
        st.warning("📭 No labels in database. Generate labels first using the 'Generate' tab.")
        return
    
    if not CHARTS_AVAILABLE:
        st.error("❌ Visualization charts not available")
        return
    
    # === SYMBOL SELECTION ===
    available_symbols = get_available_symbols_for_labels()
    
    if not available_symbols:
        st.warning("No symbols with labels found")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        symbol = st.selectbox(
            "📈 Symbol",
            available_symbols,
            format_func=lambda x: x.replace('/USDT:USDT', ''),
            key="viz_symbol"
        )
    
    with col2:
        timeframe = st.selectbox(
            "⏱️ Timeframe",
            ["15m", "1h"],
            key="viz_timeframe"
        )
    
    with col3:
        limit = st.selectbox(
            "📊 Candles",
            [500, 1000, 2000, 5000],
            index=1,
            key="viz_limit"
        )
    
    # Load data from database
    df_labels = get_ml_labels(symbol, timeframe, limit)
    
    if df_labels is None or len(df_labels) == 0:
        st.warning(f"No labels found for {symbol} [{timeframe}]")
        return
    
    # Get symbol short name
    sym_short = symbol.replace('/USDT:USDT', '')
    
    st.success(f"✅ Loaded **{len(df_labels):,}** labels for {sym_short} [{timeframe}]")
    
    # === METRICS OVERVIEW ===
    st.markdown("#### 📊 Score Statistics")
    
    m1, m2, m3, m4 = st.columns(4)
    
    avg_score_long = df_labels['score_long'].mean()
    avg_score_short = df_labels['score_short'].mean()
    positive_pct = (df_labels['score_long'] > 0).mean() * 100
    avg_bars = df_labels['bars_held_long'].mean()
    
    with m1:
        st.metric(
            "📈 Avg LONG Score",
            f"{avg_score_long:.5f}",
            f"{avg_score_long * 100:.3f}%"
        )
    
    with m2:
        st.metric(
            "📉 Avg SHORT Score",
            f"{avg_score_short:.5f}",
            f"{avg_score_short * 100:.3f}%"
        )
    
    with m3:
        st.metric(
            "✅ Positive Scores (LONG)",
            f"{positive_pct:.1f}%"
        )
    
    with m4:
        st.metric(
            "⏱️ Avg Bars Held",
            f"{avg_bars:.1f}"
        )
    
    st.divider()
    
    # === VISUALIZATION TABS ===
    tab_entry, tab_dist, tab_mfe, tab_stats = st.tabs([
        "🎯 Entry/Exit",
        "📊 Distribution",
        "🎯 MFE vs MAE",
        "📋 Statistics"
    ])
    
    # Prepare data for visualization (add timeframe suffix to columns)
    viz_df = df_labels.copy()
    
    # Rename columns to match expected format with timeframe suffix
    rename_map = {
        'score_long': f'score_long_{timeframe}',
        'score_short': f'score_short_{timeframe}',
        'realized_return_long': f'realized_return_long_{timeframe}',
        'realized_return_short': f'realized_return_short_{timeframe}',
        'mfe_long': f'mfe_long_{timeframe}',
        'mfe_short': f'mfe_short_{timeframe}',
        'mae_long': f'mae_long_{timeframe}',
        'mae_short': f'mae_short_{timeframe}',
        'bars_held_long': f'bars_held_long_{timeframe}',
        'bars_held_short': f'bars_held_short_{timeframe}',
        'exit_type_long': f'exit_type_long_{timeframe}',
        'exit_type_short': f'exit_type_short_{timeframe}'
    }
    
    for old_col, new_col in rename_map.items():
        if old_col in viz_df.columns:
            viz_df[new_col] = viz_df[old_col]
    
    with tab_entry:
        st.markdown("### 🎯 Entry/Exit Points Visualization")
        
        entry_direction = st.radio(
            "Direction",
            ["BOTH", "LONG", "SHORT"],
            horizontal=True,
            key="viz_entry_direction"
        )
        
        col_ee1, col_ee2 = st.columns(2)
        
        with col_ee1:
            score_threshold = st.slider(
                "Min Score Threshold",
                min_value=-0.01,
                max_value=0.02,
                value=0.0,
                step=0.001,
                format="%.3f",
                key="viz_threshold"
            )
        
        with col_ee2:
            max_trades = st.slider(
                "Max Trades per Direction",
                min_value=5,
                max_value=50,
                value=10,
                step=5,
                key="viz_max_trades"
            )
        
        entry_bars = st.slider(
            "Number of Candles",
            min_value=50,
            max_value=500,
            value=150,
            step=50,
            key="viz_entry_bars"
        )
        
        try:
            if entry_direction == "BOTH":
                fig_entry = create_combined_entry_exit_chart(
                    df=viz_df,
                    labels_df=viz_df,
                    timeframe=timeframe,
                    symbol=sym_short,
                    show_last_n=entry_bars,
                    score_threshold=score_threshold,
                    max_trades_per_direction=max_trades
                )
            else:
                fig_entry = create_entry_exit_chart(
                    df=viz_df,
                    labels_df=viz_df,
                    direction=entry_direction.lower(),
                    timeframe=timeframe,
                    symbol=sym_short,
                    show_last_n=entry_bars,
                    score_threshold=score_threshold,
                    max_trades_show=max_trades
                )
            
            st.plotly_chart(fig_entry, use_container_width=True)
        except Exception as e:
            st.error(f"Error creating chart: {e}")
    
    with tab_dist:
        st.markdown("### 📊 Score Distribution")
        
        try:
            score_col = f'score_long_{timeframe}'
            short_score_col = f'score_short_{timeframe}'
            
            fig_dist = create_score_distribution(
                labels_df=viz_df,
                score_columns=[score_col, short_score_col]
            )
            
            st.plotly_chart(fig_dist, use_container_width=True)
            
            # Heatmap
            st.markdown("### 🗓️ Time Heatmap")
            
            fig_heat = create_score_heatmap(
                labels_df=viz_df,
                score_column=score_col,
                resample_period='D'
            )
            
            st.plotly_chart(fig_heat, use_container_width=True)
        except Exception as e:
            st.error(f"Error creating distribution: {e}")
    
    with tab_mfe:
        st.markdown("### 🎯 MFE vs MAE Analysis")
        
        mfe_direction = st.radio(
            "Direction",
            ["LONG", "SHORT"],
            horizontal=True,
            key="viz_mfe_direction"
        )
        
        try:
            fig_mfe = create_mfe_mae_scatter(
                labels_df=viz_df,
                direction=mfe_direction.lower(),
                timeframe=timeframe
            )
            
            st.plotly_chart(fig_mfe, use_container_width=True)
            
            st.info("""
            **Interpretation:**
            - Points **above** the diagonal = MAE > MFE (unfavorable trade)
            - Points **below** the diagonal = MFE > MAE (favorable trade)
            - Color: 🟢 Green = positive score, 🔴 Red = negative score
            """)
        except Exception as e:
            st.error(f"Error creating MFE/MAE chart: {e}")
    
    with tab_stats:
        st.markdown("### 📋 Detailed Statistics")
        
        # Exit type analysis
        st.markdown("#### 🚪 Exit Types Analysis")
        
        exit_col = 'exit_type_long'
        return_col = 'realized_return_long'
        
        if exit_col in df_labels.columns:
            trailing_exits = df_labels[df_labels[exit_col] == 'trailing']
            time_exits = df_labels[df_labels[exit_col] == 'time']
            
            c1, c2 = st.columns(2)
            
            trailing_pct = (len(trailing_exits) / len(df_labels)) * 100
            time_pct = (len(time_exits) / len(df_labels)) * 100
            
            c1.metric("🎯 Trailing Stop Exit", f"{len(trailing_exits):,}", f"{trailing_pct:.1f}%")
            c2.metric("⏰ Time Exit", f"{len(time_exits):,}", f"{time_pct:.1f}%")
            
            # Profit breakdown
            st.markdown("#### 📈 Profit vs Loss Breakdown")
            
            if return_col in df_labels.columns:
                trailing_profit = trailing_exits[trailing_exits[return_col] > 0]
                trailing_loss = trailing_exits[trailing_exits[return_col] <= 0]
                time_profit = time_exits[time_exits[return_col] > 0]
                time_loss = time_exits[time_exits[return_col] <= 0]
                
                b1, b2, b3, b4 = st.columns(4)
                
                b1.metric("🎯✅ Trailing Profit", f"{len(trailing_profit):,}")
                b2.metric("🎯❌ Trailing Loss", f"{len(trailing_loss):,}")
                b3.metric("⏰✅ Time Profit", f"{len(time_profit):,}")
                b4.metric("⏰❌ Time Loss", f"{len(time_loss):,}")
                
                # Pie chart
                fig_pie = go.Figure(data=[go.Pie(
                    labels=['Trailing Profit', 'Trailing Loss', 'Time Profit', 'Time Loss'],
                    values=[len(trailing_profit), len(trailing_loss), len(time_profit), len(time_loss)],
                    hole=0.4,
                    marker_colors=['#00C853', '#FF5252', '#00BCD4', '#FF9800']
                )])
                
                fig_pie.update_layout(
                    title='Exit Types Distribution',
                    height=400,
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                
                st.plotly_chart(fig_pie, use_container_width=True)
        
        # Raw data
        st.markdown("#### 📄 Raw Data Sample")
        
        sample_cols = ['close', 'score_long', 'score_short', 'realized_return_long', 
                       'mfe_long', 'mae_long', 'bars_held_long', 'exit_type_long']
        
        available_cols = [c for c in sample_cols if c in df_labels.columns]
        sample_df = df_labels[available_cols].tail(20).round(5)
        st.dataframe(sample_df, use_container_width=True)
    
    # === EXPORT ===
    st.divider()
    st.markdown("### 📥 Export Data")
    
    csv_buffer = BytesIO()
    df_labels.to_csv(csv_buffer, index=True)
    csv_data = csv_buffer.getvalue()
    
    st.download_button(
        label=f"📥 Download {sym_short} [{timeframe}] Labels (CSV)",
        data=csv_data,
        file_name=f"labels_{sym_short}_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
