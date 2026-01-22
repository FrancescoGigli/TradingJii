"""
📊 Labeling Analysis Module

Grafici diagnostici post-labeling per validare la stabilità dei parametri k_*.
NON modifica il labeling, serve solo per analisi ex-post.

Analisi disponibili:
- Istogramma MAE
- MAE vs Score
- Distribution per exit_type
- Confronto per symbol
- Confronto 15m vs 1h
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def create_mae_histogram(labels_df: pd.DataFrame, timeframe: str = '15m', direction: str = 'long') -> go.Figure:
    """
    Crea istogramma della MAE.
    
    Args:
        labels_df: DataFrame con labels
        timeframe: '15m' o '1h'
        direction: 'long' o 'short'
    
    Returns:
        Plotly figure
    """
    col = f'mae_{direction}_{timeframe}'
    exit_col = f'exit_type_{direction}_{timeframe}'
    
    if col not in labels_df.columns:
        return go.Figure().update_layout(title="MAE column not found")
    
    # Filter valid data
    valid_mask = labels_df[exit_col].notna() & (labels_df[exit_col] != 'invalid')
    data = labels_df[valid_mask][col].dropna() * 100  # Convert to percentage
    
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=data,
        nbinsx=50,
        marker_color='#ef4444',
        opacity=0.7,
        name='MAE Distribution'
    ))
    
    # Add mean line
    mean_mae = data.mean()
    fig.add_vline(x=mean_mae, line_dash="dash", line_color="yellow",
                  annotation_text=f"Mean: {mean_mae:.2f}%")
    
    fig.update_layout(
        title=f"📊 MAE Distribution ({direction.upper()} {timeframe})",
        xaxis_title="MAE (%)",
        yaxis_title="Count",
        template="plotly_dark",
        height=400
    )
    
    return fig


def create_mae_vs_score_scatter(labels_df: pd.DataFrame, timeframe: str = '15m', direction: str = 'long') -> go.Figure:
    """
    Crea scatter plot MAE vs Score.
    
    Args:
        labels_df: DataFrame con labels
        timeframe: '15m' o '1h'
        direction: 'long' o 'short'
    
    Returns:
        Plotly figure
    """
    mae_col = f'mae_{direction}_{timeframe}'
    score_col = f'score_{direction}_{timeframe}'
    exit_col = f'exit_type_{direction}_{timeframe}'
    
    if mae_col not in labels_df.columns or score_col not in labels_df.columns:
        return go.Figure().update_layout(title="Columns not found")
    
    # Filter valid data
    valid_mask = labels_df[exit_col].notna() & (labels_df[exit_col] != 'invalid')
    df = labels_df[valid_mask][[mae_col, score_col, exit_col]].dropna()
    
    # Sample for performance if too many points
    if len(df) > 5000:
        df = df.sample(5000)
    
    fig = px.scatter(
        df,
        x=df[mae_col] * 100,
        y=df[score_col],
        color=df[exit_col],
        color_discrete_map={
            'fixed_sl': '#ef4444',
            'trailing': '#22c55e',
            'time': '#3b82f6'
        },
        opacity=0.5,
        title=f"📉 MAE vs Score ({direction.upper()} {timeframe})"
    )
    
    fig.update_layout(
        xaxis_title="MAE (%)",
        yaxis_title="Score",
        template="plotly_dark",
        height=400
    )
    
    return fig


def create_exit_type_pie(labels_df: pd.DataFrame, timeframe: str = '15m', direction: str = 'long') -> go.Figure:
    """
    Crea pie chart per exit types.
    
    Args:
        labels_df: DataFrame con labels
        timeframe: '15m' o '1h'
        direction: 'long' o 'short'
    
    Returns:
        Plotly figure
    """
    exit_col = f'exit_type_{direction}_{timeframe}'
    
    if exit_col not in labels_df.columns:
        return go.Figure().update_layout(title="Exit type column not found")
    
    # Filter valid data
    valid_mask = labels_df[exit_col].notna() & (labels_df[exit_col] != 'invalid')
    counts = labels_df[valid_mask][exit_col].value_counts()
    
    colors = {
        'fixed_sl': '#ef4444',
        'trailing': '#22c55e',
        'time': '#3b82f6'
    }
    
    fig = go.Figure(data=[go.Pie(
        labels=counts.index,
        values=counts.values,
        hole=0.4,
        marker_colors=[colors.get(x, '#888') for x in counts.index]
    )])
    
    fig.update_layout(
        title=f"🎯 Exit Types ({direction.upper()} {timeframe})",
        template="plotly_dark",
        height=350
    )
    
    return fig


def create_score_distribution(labels_df: pd.DataFrame, timeframe: str = '15m') -> go.Figure:
    """
    Crea distribuzione score LONG vs SHORT.
    
    Args:
        labels_df: DataFrame con labels
        timeframe: '15m' o '1h'
    
    Returns:
        Plotly figure
    """
    score_long_col = f'score_long_{timeframe}'
    score_short_col = f'score_short_{timeframe}'
    exit_col = f'exit_type_long_{timeframe}'
    
    if score_long_col not in labels_df.columns:
        return go.Figure().update_layout(title="Score columns not found")
    
    # Filter valid data
    valid_mask = labels_df[exit_col].notna() & (labels_df[exit_col] != 'invalid')
    df = labels_df[valid_mask]
    
    fig = go.Figure()
    
    # LONG scores
    fig.add_trace(go.Histogram(
        x=df[score_long_col].dropna(),
        nbinsx=50,
        marker_color='#22c55e',
        opacity=0.6,
        name='LONG'
    ))
    
    # SHORT scores
    fig.add_trace(go.Histogram(
        x=df[score_short_col].dropna(),
        nbinsx=50,
        marker_color='#ef4444',
        opacity=0.6,
        name='SHORT'
    ))
    
    # Add zero line
    fig.add_vline(x=0, line_dash="dash", line_color="white", opacity=0.5)
    
    fig.update_layout(
        title=f"📊 Score Distribution ({timeframe})",
        xaxis_title="Score",
        yaxis_title="Count",
        barmode='overlay',
        template="plotly_dark",
        height=400
    )
    
    return fig


def create_atr_analysis(labels_df: pd.DataFrame, timeframe: str = '15m') -> go.Figure:
    """
    Analisi ATR% per vedere la volatilità del dataset.
    
    Args:
        labels_df: DataFrame con labels
        timeframe: '15m' o '1h'
    
    Returns:
        Plotly figure
    """
    atr_col = f'atr_pct_{timeframe}'
    
    if atr_col not in labels_df.columns:
        return go.Figure().update_layout(title="ATR column not found")
    
    data = labels_df[atr_col].dropna() * 100  # Convert to percentage
    
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=data,
        nbinsx=50,
        marker_color='#8b5cf6',
        opacity=0.7,
        name='ATR %'
    ))
    
    # Add mean and percentiles
    mean_atr = data.mean()
    p25 = data.quantile(0.25)
    p75 = data.quantile(0.75)
    
    fig.add_vline(x=mean_atr, line_dash="dash", line_color="yellow",
                  annotation_text=f"Mean: {mean_atr:.2f}%")
    fig.add_vline(x=p25, line_dash="dot", line_color="gray",
                  annotation_text=f"P25: {p25:.2f}%")
    fig.add_vline(x=p75, line_dash="dot", line_color="gray",
                  annotation_text=f"P75: {p75:.2f}%")
    
    fig.update_layout(
        title=f"📈 ATR% Distribution ({timeframe})",
        xaxis_title="ATR (%)",
        yaxis_title="Count",
        template="plotly_dark",
        height=400
    )
    
    return fig


def create_bars_held_histogram(labels_df: pd.DataFrame, timeframe: str = '15m', direction: str = 'long') -> go.Figure:
    """
    Crea istogramma delle candele tenute.
    
    Args:
        labels_df: DataFrame con labels
        timeframe: '15m' o '1h'
        direction: 'long' o 'short'
    
    Returns:
        Plotly figure
    """
    bars_col = f'bars_held_{direction}_{timeframe}'
    exit_col = f'exit_type_{direction}_{timeframe}'
    
    if bars_col not in labels_df.columns:
        return go.Figure().update_layout(title="Bars held column not found")
    
    # Filter valid data
    valid_mask = labels_df[exit_col].notna() & (labels_df[exit_col] != 'invalid')
    df = labels_df[valid_mask]
    
    fig = go.Figure()
    
    for exit_type, color in [('fixed_sl', '#ef4444'), ('trailing', '#22c55e'), ('time', '#3b82f6')]:
        mask = df[exit_col] == exit_type
        if mask.sum() > 0:
            fig.add_trace(go.Histogram(
                x=df[mask][bars_col],
                name=exit_type,
                marker_color=color,
                opacity=0.6
            ))
    
    fig.update_layout(
        title=f"⏱️ Bars Held by Exit Type ({direction.upper()} {timeframe})",
        xaxis_title="Bars Held",
        yaxis_title="Count",
        barmode='overlay',
        template="plotly_dark",
        height=400
    )
    
    return fig


def render_analysis_dashboard(labels_df: pd.DataFrame, timeframe: str = '15m'):
    """
    Render complete analysis dashboard in Streamlit.
    
    Args:
        labels_df: DataFrame con labels
        timeframe: '15m' o '1h'
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
        st.plotly_chart(create_score_distribution(labels_df, timeframe), use_container_width=True)
    
    with col2:
        st.plotly_chart(create_atr_analysis(labels_df, timeframe), use_container_width=True)
    
    # Row 2: Exit type pie charts
    st.markdown("### Exit Type Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(create_exit_type_pie(labels_df, timeframe, 'long'), use_container_width=True)
    
    with col2:
        st.plotly_chart(create_exit_type_pie(labels_df, timeframe, 'short'), use_container_width=True)
    
    # Row 3: MAE analysis
    st.markdown("### MAE Analysis (Max Adverse Excursion)")
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(create_mae_histogram(labels_df, timeframe, 'long'), use_container_width=True)
    
    with col2:
        st.plotly_chart(create_mae_histogram(labels_df, timeframe, 'short'), use_container_width=True)
    
    # Row 4: MAE vs Score scatter
    st.markdown("### MAE vs Score (identifying problematic trades)")
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(create_mae_vs_score_scatter(labels_df, timeframe, 'long'), use_container_width=True)
    
    with col2:
        st.plotly_chart(create_mae_vs_score_scatter(labels_df, timeframe, 'short'), use_container_width=True)
    
    # Row 5: Bars held
    st.markdown("### Holding Period Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(create_bars_held_histogram(labels_df, timeframe, 'long'), use_container_width=True)
    
    with col2:
        st.plotly_chart(create_bars_held_histogram(labels_df, timeframe, 'short'), use_container_width=True)


def get_stability_report(labels_df: pd.DataFrame, timeframe: str = '15m') -> Dict:
    """
    Genera un report sulla stabilità dei parametri.
    
    Args:
        labels_df: DataFrame con labels
        timeframe: '15m' o '1h'
    
    Returns:
        Dict con metriche di stabilità
    """
    exit_col = f'exit_type_long_{timeframe}'
    valid_mask = labels_df[exit_col].notna() & (labels_df[exit_col] != 'invalid')
    df = labels_df[valid_mask]
    
    n_valid = len(df)
    if n_valid == 0:
        return {'valid': False, 'reason': 'No valid samples'}
    
    # Calculate stability metrics
    score_long = df[f'score_long_{timeframe}']
    score_short = df[f'score_short_{timeframe}']
    mae_long = df[f'mae_long_{timeframe}']
    mae_short = df[f'mae_short_{timeframe}']
    
    # Exit type distribution
    exit_counts_long = df[f'exit_type_long_{timeframe}'].value_counts(normalize=True)
    exit_counts_short = df[f'exit_type_short_{timeframe}'].value_counts(normalize=True)
    
    report = {
        'valid': True,
        'n_samples': n_valid,
        
        # Score stability
        'long_score_mean': score_long.mean(),
        'long_score_std': score_long.std(),
        'long_positive_pct': (score_long > 0).mean() * 100,
        'short_score_mean': score_short.mean(),
        'short_score_std': score_short.std(),
        'short_positive_pct': (score_short > 0).mean() * 100,
        
        # MAE analysis
        'long_mae_mean': mae_long.mean() * 100,
        'short_mae_mean': mae_short.mean() * 100,
        
        # Exit type balance
        'long_fixed_sl_pct': exit_counts_long.get('fixed_sl', 0) * 100,
        'long_trailing_pct': exit_counts_long.get('trailing', 0) * 100,
        'long_time_pct': exit_counts_long.get('time', 0) * 100,
        'short_fixed_sl_pct': exit_counts_short.get('fixed_sl', 0) * 100,
        'short_trailing_pct': exit_counts_short.get('trailing', 0) * 100,
        'short_time_pct': exit_counts_short.get('time', 0) * 100,
    }
    
    # Stability warnings
    warnings = []
    
    # Check if score distribution is too skewed
    if report['long_positive_pct'] > 70 or report['long_positive_pct'] < 30:
        warnings.append(f"⚠️ LONG score distribution skewed ({report['long_positive_pct']:.1f}% positive)")
    
    if report['short_positive_pct'] > 70 or report['short_positive_pct'] < 30:
        warnings.append(f"⚠️ SHORT score distribution skewed ({report['short_positive_pct']:.1f}% positive)")
    
    # Check if fixed_sl is being hit too often
    if report['long_fixed_sl_pct'] > 50:
        warnings.append(f"⚠️ LONG fixed_sl hit {report['long_fixed_sl_pct']:.1f}% - consider wider k_fixed_sl")
    
    if report['short_fixed_sl_pct'] > 50:
        warnings.append(f"⚠️ SHORT fixed_sl hit {report['short_fixed_sl_pct']:.1f}% - consider wider k_fixed_sl")
    
    # Check if time exit is too common
    if report['long_time_pct'] > 40:
        warnings.append(f"⚠️ LONG time exit {report['long_time_pct']:.1f}% - consider increasing max_bars")
    
    if report['short_time_pct'] > 40:
        warnings.append(f"⚠️ SHORT time exit {report['short_time_pct']:.1f}% - consider increasing max_bars")
    
    report['warnings'] = warnings
    report['is_stable'] = len(warnings) == 0
    
    return report


def render_stability_report(labels_df: pd.DataFrame, timeframe: str = '15m'):
    """
    Render stability report in Streamlit.
    
    Args:
        labels_df: DataFrame con labels
        timeframe: '15m' o '1h'
    """
    report = get_stability_report(labels_df, timeframe)
    
    if not report['valid']:
        st.error(f"Cannot generate report: {report['reason']}")
        return
    
    st.subheader("🔍 Stability Report")
    
    # Overall status
    if report['is_stable']:
        st.success("✅ Parameters appear STABLE - good for ML training")
    else:
        st.warning("⚠️ Parameters may need adjustment")
        for warning in report['warnings']:
            st.warning(warning)
    
    # Metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**LONG Labels:**")
        st.write(f"- Score Mean: {report['long_score_mean']:.5f}")
        st.write(f"- Score Std: {report['long_score_std']:.5f}")
        st.write(f"- Positive: {report['long_positive_pct']:.1f}%")
        st.write(f"- Avg MAE: {report['long_mae_mean']:.2f}%")
        st.write(f"- Exit: fixed_sl {report['long_fixed_sl_pct']:.1f}% | trailing {report['long_trailing_pct']:.1f}% | time {report['long_time_pct']:.1f}%")
    
    with col2:
        st.markdown("**SHORT Labels:**")
        st.write(f"- Score Mean: {report['short_score_mean']:.5f}")
        st.write(f"- Score Std: {report['short_score_std']:.5f}")
        st.write(f"- Positive: {report['short_positive_pct']:.1f}%")
        st.write(f"- Avg MAE: {report['short_mae_mean']:.2f}%")
        st.write(f"- Exit: fixed_sl {report['short_fixed_sl_pct']:.1f}% | trailing {report['short_trailing_pct']:.1f}% | time {report['short_time_pct']:.1f}%")


# ═══════════════════════════════════════════════════════════════════════════════
# LABEL QUALITY ANALYSIS - Deep Dive
# ═══════════════════════════════════════════════════════════════════════════════

def get_label_quality_from_db() -> Optional[Dict]:
    """
    Carica statistiche sulla qualità delle label dal database.
    
    Returns:
        Dictionary con metriche di qualità
    """
    try:
        import sqlite3
        conn = sqlite3.connect('/app/shared/data_cache/trading_data.db')
        
        # Check if training_labels table exists
        check = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='training_labels'", 
            conn
        )
        if len(check) == 0:
            conn.close()
            return None
        
        # Statistiche generali
        stats = pd.read_sql_query("""
            SELECT 
                COUNT(*) as total_samples,
                COUNT(DISTINCT symbol) as n_symbols,
                ROUND(AVG(score_long), 6) as avg_score_long,
                ROUND(AVG(score_short), 6) as avg_score_short,
                ROUND(AVG(realized_return_long) * 100, 4) as avg_return_long_pct,
                ROUND(AVG(realized_return_short) * 100, 4) as avg_return_short_pct,
                SUM(CASE WHEN score_long > 0 THEN 1 ELSE 0 END) as n_positive_long,
                SUM(CASE WHEN score_short > 0 THEN 1 ELSE 0 END) as n_positive_short
            FROM training_labels
        """, conn).iloc[0]
        
        # Confronto positive vs negative
        comparison = pd.read_sql_query("""
            SELECT 
                CASE WHEN score_long > 0 THEN 'POSITIVE (entry)' ELSE 'NEGATIVE (skip)' END as label_type,
                COUNT(*) as samples,
                ROUND(AVG(realized_return_long) * 100, 3) as avg_return_pct,
                ROUND(AVG(score_long), 5) as avg_score
            FROM training_labels
            GROUP BY CASE WHEN score_long > 0 THEN 'POSITIVE (entry)' ELSE 'NEGATIVE (skip)' END
        """, conn)
        
        # Distribuzione return delle positive
        positive_dist = pd.read_sql_query("""
            SELECT 
                CASE 
                    WHEN realized_return_long > 0.05 THEN '> +5%'
                    WHEN realized_return_long > 0.02 THEN '+2% to +5%'
                    WHEN realized_return_long > 0.01 THEN '+1% to +2%'
                    WHEN realized_return_long > 0 THEN '0% to +1%'
                    ELSE 'Negative'
                END as return_bucket,
                COUNT(*) as count,
                ROUND(AVG(realized_return_long) * 100, 3) as avg_return_pct
            FROM training_labels
            WHERE score_long > 0
            GROUP BY return_bucket
        """, conn)
        
        # Performance per range di score
        score_ranges = pd.read_sql_query("""
            SELECT 
                CASE 
                    WHEN score_long > 0.1 THEN 'A. > 0.10 (excellent)'
                    WHEN score_long > 0.05 THEN 'B. 0.05-0.10 (very good)'
                    WHEN score_long > 0.02 THEN 'C. 0.02-0.05 (good)'
                    WHEN score_long > 0 THEN 'D. 0-0.02 (marginal)'
                    WHEN score_long > -0.02 THEN 'E. -0.02-0 (avoid)'
                    ELSE 'F. < -0.02 (bad)'
                END as score_range,
                COUNT(*) as samples,
                ROUND(AVG(realized_return_long) * 100, 3) as avg_return_pct,
                ROUND(SUM(CASE WHEN realized_return_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate
            FROM training_labels
            GROUP BY score_range
            ORDER BY score_range
        """, conn)
        
        # Win rate teorico
        theoretical = pd.read_sql_query("""
            SELECT 
                ROUND(SUM(CASE WHEN realized_return_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate,
                ROUND(SUM(CASE WHEN realized_return_long > 0 THEN realized_return_long ELSE 0 END) * 100, 2) as gross_profit,
                ROUND(SUM(CASE WHEN realized_return_long < 0 THEN ABS(realized_return_long) ELSE 0 END) * 100, 2) as gross_loss
            FROM training_labels
            WHERE score_long > 0
        """, conn).iloc[0]
        
        # Correlazione
        df_corr = pd.read_sql_query("SELECT score_long, realized_return_long FROM training_labels", conn)
        correlation = df_corr['score_long'].corr(df_corr['realized_return_long'])
        
        conn.close()
        
        return {
            'stats': stats.to_dict(),
            'comparison': comparison,
            'positive_dist': positive_dist,
            'score_ranges': score_ranges,
            'theoretical': theoretical.to_dict(),
            'correlation': correlation
        }
        
    except Exception as e:
        logger.error(f"Error loading label quality: {e}")
        return None


def create_score_vs_return_scatter() -> go.Figure:
    """
    Crea scatter plot score vs return con linea di regressione.
    """
    try:
        import sqlite3
        conn = sqlite3.connect('/app/shared/data_cache/trading_data.db')
        
        # Sample for performance
        df = pd.read_sql_query("""
            SELECT score_long, realized_return_long * 100 as return_pct
            FROM training_labels
            ORDER BY RANDOM()
            LIMIT 10000
        """, conn)
        conn.close()
        
        fig = go.Figure()
        
        # Scatter points
        fig.add_trace(go.Scattergl(
            x=df['score_long'],
            y=df['return_pct'],
            mode='markers',
            marker=dict(
                size=4,
                color=df['return_pct'],
                colorscale='RdYlGn',
                cmin=-5,
                cmax=5,
                opacity=0.5
            ),
            name='Samples'
        ))
        
        # Zero lines
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=0, line_dash="dash", line_color="yellow", 
                      annotation_text="Score = 0 (threshold)")
        
        fig.update_layout(
            title="📈 Score vs Return Correlation",
            xaxis_title="Score",
            yaxis_title="Return (%)",
            template="plotly_dark",
            height=450,
            showlegend=False
        )
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating scatter: {e}")
        return go.Figure().update_layout(title="Error loading data")


def create_score_range_bar_chart(score_ranges: pd.DataFrame) -> go.Figure:
    """
    Crea bar chart delle performance per range di score.
    """
    fig = go.Figure()
    
    # Colors based on score range
    colors = ['#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444', '#dc2626']
    
    fig.add_trace(go.Bar(
        x=score_ranges['score_range'],
        y=score_ranges['avg_return_pct'],
        marker_color=colors[:len(score_ranges)],
        text=[f"{x:.2f}%" for x in score_ranges['avg_return_pct']],
        textposition='outside'
    ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)
    
    fig.update_layout(
        title="🎯 Return Medio per Range di Score",
        xaxis_title="Score Range",
        yaxis_title="Return Medio (%)",
        template="plotly_dark",
        height=400
    )
    
    return fig


def create_positive_distribution_pie(positive_dist: pd.DataFrame) -> go.Figure:
    """
    Crea pie chart della distribuzione return delle label positive.
    """
    colors = ['#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444']
    
    fig = go.Figure(data=[go.Pie(
        labels=positive_dist['return_bucket'],
        values=positive_dist['count'],
        hole=0.4,
        marker_colors=colors[:len(positive_dist)],
        textinfo='label+percent'
    )])
    
    fig.update_layout(
        title="📊 Distribuzione Return Label Positive",
        template="plotly_dark",
        height=400
    )
    
    return fig


def render_label_quality_analysis():
    """
    Render complete label quality analysis dashboard.
    Fully reactive to actual data found in database.
    All text in English.
    """
    st.subheader("🎯 Label Quality Analysis - Deep Dive")
    
    # Load data
    quality = get_label_quality_from_db()
    
    if quality is None:
        st.warning("⚠️ No data available. Generate labels first.")
        return
    
    stats = quality['stats']
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HEADER METRICS - Reactive to actual data
    # ═══════════════════════════════════════════════════════════════════════════
    
    st.markdown("### 📈 Key Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_samples = stats['total_samples']
    n_positive = stats['n_positive_long']
    pct_positive = n_positive / total_samples * 100 if total_samples > 0 else 0
    corr = quality['correlation']
    theoretical = quality['theoretical']
    
    with col1:
        st.metric(
            "🔢 Total Samples",
            f"{total_samples:,.0f}",
            f"{stats['n_symbols']:.0f} symbols",
            help="Total number of labeled candles"
        )
    
    with col2:
        # Reactive delta based on quality
        delta_text = "✓ Good ratio" if 15 < pct_positive < 40 else "⚠️ Check ratio"
        st.metric(
            "✅ Positive Labels",
            f"{pct_positive:.1f}%",
            delta_text,
            help="Percentage of profitable entries (score > 0)"
        )
    
    with col3:
        # Reactive correlation quality indicator
        if corr > 0.95:
            corr_status = "🟢 EXCELLENT"
        elif corr > 0.8:
            corr_status = "🟡 GOOD"
        elif corr > 0.5:
            corr_status = "🟠 MODERATE"
        else:
            corr_status = "🔴 WEAK"
        
        st.metric(
            "📊 Correlation",
            f"{corr:.4f}",
            corr_status,
            help="Correlation between score and realized return"
        )
    
    with col4:
        win_rate = theoretical.get('win_rate', 0)
        st.metric(
            "🏆 Theoretical Win Rate",
            f"{win_rate:.1f}%",
            help="Win rate if model was perfect"
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # REACTIVE INTERPRETATION BOX
    # ═══════════════════════════════════════════════════════════════════════════
    
    st.markdown("---")
    
    # Build reactive message based on actual data
    if corr > 0.95:
        quality_emoji = "🟢"
        quality_text = "EXCELLENT"
        quality_description = f"""
        **Labels are of exceptional quality!**
        
        With correlation of **{corr:.4f}**, this means:
        - Score accurately predicts profit/loss
        - Positive labels (score > 0) have **{pct_positive:.1f}%** of total samples
        - Theoretical win rate is **{win_rate:.1f}%**
        
        **You can proceed with ML training with confidence!**
        """
        box_type = st.success
    elif corr > 0.8:
        quality_emoji = "🟡"
        quality_text = "GOOD"
        quality_description = f"Score has good predictive power (corr={corr:.4f}). Ready for training."
        box_type = st.info
    elif corr > 0.5:
        quality_emoji = "🟠"
        quality_text = "MODERATE"
        quality_description = f"Score has moderate predictive power (corr={corr:.4f}). Consider optimizing parameters."
        box_type = st.warning
    else:
        quality_emoji = "🔴"
        quality_text = "WEAK"
        quality_description = f"Score has weak predictive power (corr={corr:.4f}). Labeling parameters need adjustment."
        box_type = st.error
    
    box_type(f"""
    ### {quality_emoji} Label Quality: {quality_text}
    
    {quality_description}
    """)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMPARISON TABLE - Reactive
    # ═══════════════════════════════════════════════════════════════════════════
    
    st.markdown("### 🎯 Positive vs Negative Labels Comparison")
    
    comparison = quality['comparison']
    
    col1, col2 = st.columns(2)
    
    with col1:
        positive_rows = comparison[comparison['label_type'] == 'POSITIVE (entry)']
        if len(positive_rows) > 0:
            positive_row = positive_rows.iloc[0]
            pos_samples = positive_row['samples']
            pos_return = positive_row['avg_return_pct']
            pos_score = positive_row['avg_score']
            
            st.success(f"""
            **✅ POSITIVE (Entry)**
            - Samples: **{pos_samples:,}** ({pos_samples/total_samples*100:.1f}%)
            - Avg Return: **+{pos_return:.2f}%**
            - Avg Score: {pos_score:.5f}
            
            → When model predicts "ENTRY", expect profit!
            """)
    
    with col2:
        negative_rows = comparison[comparison['label_type'] == 'NEGATIVE (skip)']
        if len(negative_rows) > 0:
            negative_row = negative_rows.iloc[0]
            neg_samples = negative_row['samples']
            neg_return = negative_row['avg_return_pct']
            neg_score = negative_row['avg_score']
            
            st.error(f"""
            **❌ NEGATIVE (Skip)**
            - Samples: **{neg_samples:,}** ({neg_samples/total_samples*100:.1f}%)
            - Avg Return: **{neg_return:.2f}%**
            - Avg Score: {neg_score:.5f}
            
            → Model learns when NOT to enter!
            """)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CHARTS - Reactive
    # ═══════════════════════════════════════════════════════════════════════════
    
    st.markdown("---")
    st.markdown("### 📊 Visualizations")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_scatter = create_score_vs_return_scatter()
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        st.caption(f"""
        **How to read:** Each point is a candle (sample: 10,000 of {total_samples:,}).
        - Right of yellow line (score > 0) = profitable entries
        - Left = avoid
        - Strong diagonal correlation ({corr:.4f}) confirms label quality
        """)
    
    with col2:
        fig_bar = create_score_range_bar_chart(quality['score_ranges'])
        st.plotly_chart(fig_bar, use_container_width=True)
        
        # Get best and worst ranges from actual data
        score_ranges = quality['score_ranges']
        best_range = score_ranges.iloc[0] if len(score_ranges) > 0 else None
        worst_range = score_ranges.iloc[-1] if len(score_ranges) > 0 else None
        
        if best_range is not None and worst_range is not None:
            st.caption(f"""
            **How to read:** Higher score = higher avg return.
            - Best: {best_range['score_range']} → {best_range['avg_return_pct']:.2f}% avg return
            - Worst: {worst_range['score_range']} → {worst_range['avg_return_pct']:.2f}% avg return
            """)
    
    # Distribution pie - Reactive
    st.markdown("### 📈 Return Distribution of Positive Labels")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        fig_pie = create_positive_distribution_pie(quality['positive_dist'])
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        st.markdown("""
        **Interpretation:**
        
        Distribution of positive labels (score > 0):
        """)
        
        positive_dist = quality['positive_dist']
        total_positive = positive_dist['count'].sum()
        
        for _, row in positive_dist.iterrows():
            bucket = row['return_bucket']
            count = row['count']
            avg_ret = row['avg_return_pct']
            pct_of_total = count / total_positive * 100 if total_positive > 0 else 0
            
            if '> +5%' in bucket or avg_ret > 5:
                st.success(f"🚀 **{bucket}**: {count:,} trades ({pct_of_total:.1f}%) | avg: +{avg_ret:.2f}%")
            elif '+2%' in bucket or avg_ret > 2:
                st.info(f"📈 **{bucket}**: {count:,} trades ({pct_of_total:.1f}%) | avg: +{avg_ret:.2f}%")
            elif '+1%' in bucket or avg_ret > 1:
                st.warning(f"📊 **{bucket}**: {count:,} trades ({pct_of_total:.1f}%) | avg: +{avg_ret:.2f}%")
            else:
                st.write(f"📋 **{bucket}**: {count:,} trades ({pct_of_total:.1f}%) | avg: +{avg_ret:.2f}%")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SCORE RANGES TABLE - Reactive
    # ═══════════════════════════════════════════════════════════════════════════
    
    st.markdown("---")
    st.markdown("### 🎯 Detailed Performance by Score Range")
    
    score_ranges_display = quality['score_ranges'].copy()
    score_ranges_display['samples'] = score_ranges_display['samples'].apply(lambda x: f"{x:,}")
    score_ranges_display['avg_return_pct'] = score_ranges_display['avg_return_pct'].apply(lambda x: f"{x:+.2f}%")
    score_ranges_display['win_rate'] = score_ranges_display['win_rate'].apply(lambda x: f"{x:.0f}%")
    
    st.dataframe(
        score_ranges_display.rename(columns={
            'score_range': 'Score Range',
            'samples': '# Samples',
            'avg_return_pct': 'Avg Return',
            'win_rate': 'Win Rate'
        }),
        use_container_width=True,
        hide_index=True
    )
    
    # Reactive note based on actual win rates
    positive_ranges = quality['score_ranges'][quality['score_ranges']['win_rate'] == 100]
    n_perfect_ranges = len(positive_ranges)
    
    st.caption(f"""
    **Notes:** 
    - **{n_perfect_ranges}** score ranges have 100% win rate (perfect labeling)
    - Model should predict scores in top ranges for best results
    - Negative score ranges should be avoided by the model
    """)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HOW IT WORKS - Educational
    # ═══════════════════════════════════════════════════════════════════════════
    
    st.markdown("---")
    
    with st.expander("ℹ️ How the Labeling System Works", expanded=False):
        st.markdown(f"""
        ### ATR-Based Trailing Stop System
        
        **Based on your current data: {total_samples:,} samples across {stats['n_symbols']:.0f} symbols**
        
        **1. For each candle we compute:**
        - Entry price = close
        - ATR% = current volatility
        - Fixed Stop Loss = entry × (1 - k_fixed × ATR%)
        - Trailing Stop = max_price × (1 - k_trailing × ATR%)
        
        **2. We simulate the trade until:**
        - Stop hit (fixed or trailing)
        - Timeout (max_bars)
        
        **3. We compute the score:**
        ```
        score = realized_return - λ × log(1 + bars_held) - costs
        ```
        
        **4. Final label:**
        - score > 0 → ENTRY (label = 1) — **{pct_positive:.1f}%** of your data
        - score ≤ 0 → SKIP (label = 0) — **{100-pct_positive:.1f}%** of your data
        
        ### What the ML Model Learns
        
        The model does NOT try to make all trades profitable.
        
        It learns to **distinguish**:
        - ✅ When to enter ({pct_positive:.1f}% of time) → score > 0
        - ❌ When NOT to enter ({100-pct_positive:.1f}% of time) → score ≤ 0
        
        This is **by design** - most of the time is NOT a good time to enter!
        
        Your correlation of **{corr:.4f}** indicates the score is a {"very reliable" if corr > 0.9 else "reliable" if corr > 0.7 else "moderately reliable"} predictor.
        """)
