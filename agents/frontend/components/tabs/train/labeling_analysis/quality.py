"""
🎯 Label Quality Analysis Module

Deep dive analysis of label quality with database queries and visualizations.
Provides comprehensive metrics for validating ML training readiness.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import logging
from typing import Dict, Optional

from styles.tables import render_html_table

logger = logging.getLogger(__name__)


def get_label_quality_from_db() -> Optional[Dict]:
    """
    Load label quality statistics from database.
    
    Returns:
        Dictionary with quality metrics or None if no data
    """
    try:
        import sqlite3
        conn = sqlite3.connect('/app/shared/data_cache/trading_data.db')
        
        # Check if training_labels table exists
        check = pd.read_sql_query(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='training_labels'", 
            conn
        )
        if len(check) == 0:
            conn.close()
            return None
        
        # General statistics
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
        
        # Positive vs negative comparison
        comparison = pd.read_sql_query("""
            SELECT 
                CASE WHEN score_long > 0 
                    THEN 'POSITIVE (entry)' 
                    ELSE 'NEGATIVE (skip)' 
                END as label_type,
                COUNT(*) as samples,
                ROUND(AVG(realized_return_long) * 100, 3) as avg_return_pct,
                ROUND(AVG(score_long), 5) as avg_score
            FROM training_labels
            GROUP BY CASE WHEN score_long > 0 
                THEN 'POSITIVE (entry)' 
                ELSE 'NEGATIVE (skip)' 
            END
        """, conn)
        
        # Return distribution of positive labels
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
        
        # Performance by score range
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
                ROUND(
                    SUM(CASE WHEN realized_return_long > 0 THEN 1 ELSE 0 END) 
                    * 100.0 / COUNT(*), 1
                ) as win_rate
            FROM training_labels
            GROUP BY score_range
            ORDER BY score_range
        """, conn)
        
        # Theoretical win rate
        theoretical = pd.read_sql_query("""
            SELECT 
                ROUND(
                    SUM(CASE WHEN realized_return_long > 0 THEN 1 ELSE 0 END) 
                    * 100.0 / COUNT(*), 1
                ) as win_rate,
                ROUND(
                    SUM(CASE WHEN realized_return_long > 0 
                        THEN realized_return_long ELSE 0 END) * 100, 2
                ) as gross_profit,
                ROUND(
                    SUM(CASE WHEN realized_return_long < 0 
                        THEN ABS(realized_return_long) ELSE 0 END) * 100, 2
                ) as gross_loss
            FROM training_labels
            WHERE score_long > 0
        """, conn).iloc[0]
        
        # Correlation
        df_corr = pd.read_sql_query(
            "SELECT score_long, realized_return_long FROM training_labels", 
            conn
        )
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
    Create scatter plot of score vs return with regression line.
    
    Returns:
        Plotly figure
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
        fig.add_vline(
            x=0, 
            line_dash="dash", 
            line_color="yellow", 
            annotation_text="Score = 0 (threshold)"
        )
        
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
    Create bar chart of performance by score range.
    
    Args:
        score_ranges: DataFrame with score range data
    
    Returns:
        Plotly figure
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
        title="🎯 Average Return by Score Range",
        xaxis_title="Score Range",
        yaxis_title="Avg Return (%)",
        template="plotly_dark",
        height=400
    )
    
    return fig


def create_positive_distribution_pie(positive_dist: pd.DataFrame) -> go.Figure:
    """
    Create pie chart of return distribution for positive labels.
    
    Args:
        positive_dist: DataFrame with return distribution
    
    Returns:
        Plotly figure
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
        title="📊 Return Distribution of Positive Labels",
        template="plotly_dark",
        height=400
    )
    
    return fig


def _render_quality_header(stats: Dict, quality: Dict) -> tuple:
    """Render header metrics section."""
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
        delta_text = "✓ Good ratio" if 15 < pct_positive < 40 else "⚠️ Check ratio"
        st.metric(
            "✅ Positive Labels",
            f"{pct_positive:.1f}%",
            delta_text,
            help="Percentage of profitable entries (score > 0)"
        )
    
    with col3:
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
    
    return pct_positive, corr, win_rate


def _render_quality_interpretation(corr: float, pct_positive: float, win_rate: float):
    """Render interpretation box based on quality metrics."""
    st.markdown("---")
    
    if corr > 0.95:
        quality_text = "EXCELLENT"
        quality_description = f"""
        **Labels are of exceptional quality!**
        
        With correlation of **{corr:.4f}**, this means:
        - Score accurately predicts profit/loss
        - Positive labels (score > 0) have **{pct_positive:.1f}%** of total samples
        - Theoretical win rate is **{win_rate:.1f}%**
        
        **You can proceed with ML training with confidence!**
        """
        st.success(f"### 🟢 Label Quality: {quality_text}\n\n{quality_description}")
    elif corr > 0.8:
        st.info(
            f"### 🟡 Label Quality: GOOD\n\n"
            f"Score has good predictive power (corr={corr:.4f}). Ready for training."
        )
    elif corr > 0.5:
        st.warning(
            f"### 🟠 Label Quality: MODERATE\n\n"
            f"Score has moderate predictive power (corr={corr:.4f}). "
            "Consider optimizing parameters."
        )
    else:
        st.error(
            f"### 🔴 Label Quality: WEAK\n\n"
            f"Score has weak predictive power (corr={corr:.4f}). "
            "Labeling parameters need adjustment."
        )


def render_label_quality_analysis():
    """
    Render complete label quality analysis dashboard.
    Fully reactive to actual data found in database.
    """
    st.subheader("🎯 Label Quality Analysis - Deep Dive")
    
    # Load data
    quality = get_label_quality_from_db()
    
    if quality is None:
        st.warning("⚠️ No data available. Generate labels first.")
        return
    
    stats = quality['stats']
    total_samples = stats['total_samples']
    
    # Header metrics
    pct_positive, corr, win_rate = _render_quality_header(stats, quality)
    
    # Interpretation box
    _render_quality_interpretation(corr, pct_positive, win_rate)
    
    # Comparison table
    st.markdown("### 🎯 Positive vs Negative Labels Comparison")
    
    comparison = quality['comparison']
    col1, col2 = st.columns(2)
    
    with col1:
        positive_rows = comparison[comparison['label_type'] == 'POSITIVE (entry)']
        if len(positive_rows) > 0:
            row = positive_rows.iloc[0]
            st.success(f"""
            **✅ POSITIVE (Entry)**
            - Samples: **{row['samples']:,}** ({row['samples']/total_samples*100:.1f}%)
            - Avg Return: **+{row['avg_return_pct']:.2f}%**
            - Avg Score: {row['avg_score']:.5f}
            
            → When model predicts "ENTRY", expect profit!
            """)
    
    with col2:
        negative_rows = comparison[comparison['label_type'] == 'NEGATIVE (skip)']
        if len(negative_rows) > 0:
            row = negative_rows.iloc[0]
            st.error(f"""
            **❌ NEGATIVE (Skip)**
            - Samples: **{row['samples']:,}** ({row['samples']/total_samples*100:.1f}%)
            - Avg Return: **{row['avg_return_pct']:.2f}%**
            - Avg Score: {row['avg_score']:.5f}
            
            → Model learns when NOT to enter!
            """)
    
    # Charts
    st.markdown("---")
    st.markdown("### 📊 Visualizations")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_scatter = create_score_vs_return_scatter()
        st.plotly_chart(fig_scatter, width='stretch')
        st.caption(f"""
        **How to read:** Each point is a candle (sample: 10,000 of {total_samples:,}).
        - Right of yellow line (score > 0) = profitable entries
        - Left = avoid
        - Strong diagonal correlation ({corr:.4f}) confirms label quality
        """)
    
    with col2:
        fig_bar = create_score_range_bar_chart(quality['score_ranges'])
        st.plotly_chart(fig_bar, width='stretch')
        
        score_ranges = quality['score_ranges']
        if len(score_ranges) > 0:
            best = score_ranges.iloc[0]
            worst = score_ranges.iloc[-1]
            st.caption(f"""
            **How to read:** Higher score = higher avg return.
            - Best: {best['score_range']} → {best['avg_return_pct']:.2f}% avg return
            - Worst: {worst['score_range']} → {worst['avg_return_pct']:.2f}% avg return
            """)
    
    # Distribution pie
    st.markdown("### 📈 Return Distribution of Positive Labels")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        fig_pie = create_positive_distribution_pie(quality['positive_dist'])
        st.plotly_chart(fig_pie, width='stretch')
    
    with col2:
        st.markdown("**Interpretation:**\n\nDistribution of positive labels (score > 0):")
        
        positive_dist = quality['positive_dist']
        total_positive = positive_dist['count'].sum()
        
        for _, row in positive_dist.iterrows():
            bucket = row['return_bucket']
            count = row['count']
            avg_ret = row['avg_return_pct']
            pct = count / total_positive * 100 if total_positive > 0 else 0
            
            if '> +5%' in bucket or avg_ret > 5:
                st.success(f"🚀 **{bucket}**: {count:,} ({pct:.1f}%) | avg: +{avg_ret:.2f}%")
            elif '+2%' in bucket or avg_ret > 2:
                st.info(f"📈 **{bucket}**: {count:,} ({pct:.1f}%) | avg: +{avg_ret:.2f}%")
            elif '+1%' in bucket or avg_ret > 1:
                st.warning(f"📊 **{bucket}**: {count:,} ({pct:.1f}%) | avg: +{avg_ret:.2f}%")
            else:
                st.write(f"📋 **{bucket}**: {count:,} ({pct:.1f}%) | avg: +{avg_ret:.2f}%")
    
    # Score ranges table
    st.markdown("---")
    st.markdown("### 🎯 Detailed Performance by Score Range")
    
    score_ranges_display = quality['score_ranges'].copy()
    score_ranges_display['samples'] = score_ranges_display['samples'].apply(
        lambda x: f"{x:,}"
    )
    score_ranges_display['avg_return_pct'] = score_ranges_display['avg_return_pct'].apply(
        lambda x: f"{x:+.2f}%"
    )
    score_ranges_display['win_rate'] = score_ranges_display['win_rate'].apply(
        lambda x: f"{x:.0f}%"
    )
    
    score_ranges_display = score_ranges_display.rename(columns={
        'score_range': 'Score Range',
        'samples': '# Samples',
        'avg_return_pct': 'Avg Return',
        'win_rate': 'Win Rate'
    })
    render_html_table(score_ranges_display, height=300)
    
    # Educational expander
    with st.expander("ℹ️ How the Labeling System Works", expanded=False):
        reliability = (
            "very reliable" if corr > 0.9 
            else "reliable" if corr > 0.7 
            else "moderately reliable"
        )
        st.markdown(f"""
        ### ATR-Based Trailing Stop System
        
        **Based on your current data: {total_samples:,} samples across 
        {stats['n_symbols']:.0f} symbols**
        
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
        
        Your correlation of **{corr:.4f}** indicates the score is a 
        {reliability} predictor.
        """)
