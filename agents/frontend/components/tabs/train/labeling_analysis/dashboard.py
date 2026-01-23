"""
📊 Analysis Dashboard Renderer

Streamlit dashboard for rendering the complete label analysis view.
"""

import streamlit as st
import pandas as pd

from .charts import (
    create_mae_histogram,
    create_mae_vs_score_scatter,
    create_exit_type_pie,
    create_score_distribution,
    create_atr_analysis,
    create_bars_held_histogram
)


def render_analysis_dashboard(labels_df: pd.DataFrame, timeframe: str = '15m'):
    """
    Render complete analysis dashboard in Streamlit.
    
    Args:
        labels_df: DataFrame with labels
        timeframe: '15m' or '1h'
    """
    st.subheader("📊 Label Analysis Dashboard")
    
    # Stats summary
    exit_col = f'exit_type_long_{timeframe}'
    valid_mask = labels_df[exit_col].notna() & (labels_df[exit_col] != 'invalid')
    n_valid = valid_mask.sum()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Samples", f"{n_valid:,}")
    
    with col2:
        score_long_col = f'score_long_{timeframe}'
        if score_long_col in labels_df.columns:
            pct_positive = (labels_df[valid_mask][score_long_col] > 0).mean() * 100
            st.metric("LONG Positive %", f"{pct_positive:.1f}%")
    
    with col3:
        score_short_col = f'score_short_{timeframe}'
        if score_short_col in labels_df.columns:
            pct_positive = (labels_df[valid_mask][score_short_col] > 0).mean() * 100
            st.metric("SHORT Positive %", f"{pct_positive:.1f}%")
    
    with col4:
        atr_col = f'atr_pct_{timeframe}'
        if atr_col in labels_df.columns:
            avg_atr = labels_df[valid_mask][atr_col].mean() * 100
            st.metric("Avg ATR %", f"{avg_atr:.2f}%")
    
    st.markdown("---")
    
    # Row 1: Score distribution and ATR
    col1, col2 = st.columns(2)
    
    with col1:
        fig = create_score_distribution(labels_df, timeframe)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = create_atr_analysis(labels_df, timeframe)
        st.plotly_chart(fig, use_container_width=True)
    
    # Row 2: Exit type pie charts
    st.markdown("### Exit Type Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        fig = create_exit_type_pie(labels_df, timeframe, 'long')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = create_exit_type_pie(labels_df, timeframe, 'short')
        st.plotly_chart(fig, use_container_width=True)
    
    # Row 3: MAE analysis
    st.markdown("### MAE Analysis (Max Adverse Excursion)")
    col1, col2 = st.columns(2)
    
    with col1:
        fig = create_mae_histogram(labels_df, timeframe, 'long')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = create_mae_histogram(labels_df, timeframe, 'short')
        st.plotly_chart(fig, use_container_width=True)
    
    # Row 4: MAE vs Score scatter
    st.markdown("### MAE vs Score (identifying problematic trades)")
    col1, col2 = st.columns(2)
    
    with col1:
        fig = create_mae_vs_score_scatter(labels_df, timeframe, 'long')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = create_mae_vs_score_scatter(labels_df, timeframe, 'short')
        st.plotly_chart(fig, use_container_width=True)
    
    # Row 5: Bars held
    st.markdown("### Holding Period Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        fig = create_bars_held_histogram(labels_df, timeframe, 'long')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = create_bars_held_histogram(labels_df, timeframe, 'short')
        st.plotly_chart(fig, use_container_width=True)
