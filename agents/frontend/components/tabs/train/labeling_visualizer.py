"""
👁️ Labeling Visualizer Module - V3

Visualizzazione candele + labels usando v_xgb_training VIEW.
La VIEW ha già tutto: OHLCV + indicatori + labels.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional
import logging
from database import get_connection
from styles.tables import render_html_table

logger = logging.getLogger(__name__)


def get_labels_with_prices(symbol: str, timeframe: str, last_n: int = 200) -> pd.DataFrame:
    """
    Get labels with OHLCV prices from v_xgb_training VIEW.
    The VIEW already has everything joined!
    """
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        # Use v_xgb_training VIEW - has OHLCV + indicators + labels
        query = '''
            SELECT 
                timestamp,
                open,
                high,
                low,
                close,
                volume,
                rsi,
                atr,
                score_long,
                score_short,
                realized_return_long,
                realized_return_short,
                exit_type_long,
                exit_type_short,
                bars_held_long,
                bars_held_short,
                mfe_long,
                mfe_short,
                mae_long,
                mae_short,
                atr_pct
            FROM v_xgb_training
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
        '''
        
        df = pd.read_sql_query(query, conn, params=(symbol, timeframe, last_n))
        
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')  # Chronological order
            df = df.set_index('timestamp')
        
        return df
        
    except Exception as e:
        logger.error(f"Error fetching from v_xgb_training VIEW: {e}")
        # Fallback: try training_data directly (has OHLCV)
        try:
            query = '''
                SELECT 
                    d.timestamp,
                    d.open, d.high, d.low, d.close, d.volume,
                    d.rsi, d.atr,
                    l.score_long, l.score_short,
                    l.realized_return_long, l.realized_return_short,
                    l.exit_type_long, l.exit_type_short,
                    l.bars_held_long, l.bars_held_short
                FROM training_data d
                INNER JOIN training_labels l
                    ON d.symbol = l.symbol AND d.timeframe = l.timeframe AND d.timestamp = l.timestamp
                WHERE d.symbol = ? AND d.timeframe = ?
                ORDER BY d.timestamp DESC
                LIMIT ?
            '''
            df = pd.read_sql_query(query, conn, params=(symbol, timeframe, last_n))
            
            if len(df) > 0:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp')
                df = df.set_index('timestamp')
            
            return df
        except Exception as e2:
            logger.error(f"Fallback also failed: {e2}")
            return pd.DataFrame()
    finally:
        conn.close()


def get_available_symbols_with_labels(timeframe: str) -> list:
    """Get symbols that have labels generated."""
    conn = get_connection()
    if not conn:
        return []
    
    try:
        query = '''
            SELECT DISTINCT symbol, COUNT(*) as cnt
            FROM training_labels
            WHERE timeframe = ?
            GROUP BY symbol
            ORDER BY cnt DESC
        '''
        df = pd.read_sql_query(query, conn, params=(timeframe,))
        return df['symbol'].tolist()
    except Exception as e:
        logger.error(f"Error: {e}")
        return []
    finally:
        conn.close()


def create_labels_chart(df: pd.DataFrame, timeframe: str) -> go.Figure:
    """
    Create candlestick chart with score overlay.
    Shows every candle with its classification.
    """
    if df is None or len(df) == 0:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5)
        return fig
    
    # Check if we have OHLCV data
    has_ohlcv = 'open' in df.columns and df['open'].notna().any() and df['open'].max() > 0
    
    if not has_ohlcv:
        # Create score-only chart if no OHLCV
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.5, 0.5],
            subplot_titles=('📈 Score LONG', '📉 Score SHORT')
        )
        
        # Score LONG
        colors_long = ['#22c55e' if s > 0 else '#ef4444' for s in df['score_long']]
        fig.add_trace(
            go.Bar(x=df.index, y=df['score_long'], marker_color=colors_long, name='Score LONG'),
            row=1, col=1
        )
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=1, col=1)
        
        # Score SHORT
        colors_short = ['#ef4444' if s > 0 else '#22c55e' for s in df['score_short']]
        fig.add_trace(
            go.Bar(x=df.index, y=df['score_short'], marker_color=colors_short, name='Score SHORT'),
            row=2, col=1
        )
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=2, col=1)
        
        fig.update_layout(
            title=f"📊 Score Visualization ({timeframe}) - No OHLCV data available",
            template="plotly_dark",
            height=500,
            showlegend=True
        )
        return fig
    
    # Create subplots: Price + Score Long + Score Short
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.25, 0.25],
        subplot_titles=('📊 Price (Candlestick)', '📈 Score LONG', '📉 Score SHORT')
    )
    
    # 1. Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='OHLC',
            increasing_line_color='#22c55e',
            decreasing_line_color='#ef4444'
        ),
        row=1, col=1
    )
    
    # Add markers for positive/negative scores on price chart
    positive_long = df[df['score_long'] > 0]
    
    if len(positive_long) > 0:
        fig.add_trace(
            go.Scatter(
                x=positive_long.index,
                y=positive_long['low'] * 0.998,
                mode='markers',
                marker=dict(symbol='triangle-up', size=8, color='#22c55e'),
                name='LONG+ signals',
                hovertemplate='%{x}<br>Score: %{customdata:.5f}<extra></extra>',
                customdata=positive_long['score_long']
            ),
            row=1, col=1
        )
    
    positive_short = df[df['score_short'] > 0]
    if len(positive_short) > 0:
        fig.add_trace(
            go.Scatter(
                x=positive_short.index,
                y=positive_short['high'] * 1.002,
                mode='markers',
                marker=dict(symbol='triangle-down', size=8, color='#ef4444'),
                name='SHORT+ signals',
                hovertemplate='%{x}<br>Score: %{customdata:.5f}<extra></extra>',
                customdata=positive_short['score_short']
            ),
            row=1, col=1
        )
    
    # 2. Score LONG bar chart (colored by sign)
    colors_long = ['#22c55e' if s > 0 else '#ef4444' for s in df['score_long']]
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['score_long'],
            name='Score LONG',
            marker_color=colors_long,
            opacity=0.7,
            hovertemplate='%{x}<br>Score: %{y:.5f}<extra>LONG</extra>'
        ),
        row=2, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=2, col=1)
    
    # 3. Score SHORT bar chart (colored by sign)
    colors_short = ['#ef4444' if s > 0 else '#22c55e' for s in df['score_short']]
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['score_short'],
            name='Score SHORT',
            marker_color=colors_short,
            opacity=0.7,
            hovertemplate='%{x}<br>Score: %{y:.5f}<extra>SHORT</extra>'
        ),
        row=3, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=3, col=1)
    
    # Layout
    fig.update_layout(
        title=f"📊 Labels Visualization ({timeframe}) - Last {len(df)} candles",
        template="plotly_dark",
        height=800,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_rangeslider_visible=False,
        hovermode='x unified'
    )
    
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Score", row=2, col=1)
    fig.update_yaxes(title_text="Score", row=3, col=1)
    
    return fig


def render_visualizer_ui(ohlcv_df: pd.DataFrame = None, labels_df: pd.DataFrame = None, timeframe: str = '15m'):
    """
    Main visualizer UI - gets data directly from v_xgb_training VIEW.
    """
    st.subheader("👁️ Labels Visualizer")
    
    # Get available symbols
    symbols = get_available_symbols_with_labels(timeframe)
    
    if not symbols:
        st.warning(f"No labels available for {timeframe}. Generate labels first!")
        return
    
    # Controls
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        selected_symbol = st.selectbox(
            "Select Symbol",
            symbols,
            format_func=lambda x: x.replace('/USDT:USDT', ''),
            key=f"viz_sym_{timeframe}"
        )
    
    with col2:
        n_candles = st.selectbox(
            "Candles to show",
            [50, 100, 200, 500, 1000],
            index=2,
            key=f"viz_n_{timeframe}"
        )
    
    with col3:
        st.write("")  # Spacer
        refresh = st.button("🔄 Refresh", key=f"viz_refresh_{timeframe}")
    
    # Get data from VIEW
    df = get_labels_with_prices(selected_symbol, timeframe, n_candles)
    
    if df is None or len(df) == 0:
        st.error(f"No data found for {selected_symbol} ({timeframe})")
        st.info("Make sure v_xgb_training VIEW exists. Re-generate labels to create it.")
        return
    
    # Display stats
    st.markdown("---")
    st.markdown("### 📊 Quick Stats")
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Candles", len(df))
    c2.metric("LONG+ Signals", f"{(df['score_long'] > 0).sum()} ({(df['score_long'] > 0).mean()*100:.1f}%)")
    c3.metric("SHORT+ Signals", f"{(df['score_short'] > 0).sum()} ({(df['score_short'] > 0).mean()*100:.1f}%)")
    c4.metric("Avg Score LONG", f"{df['score_long'].mean():.5f}")
    c5.metric("Avg Score SHORT", f"{df['score_short'].mean():.5f}")
    
    # Main chart
    st.markdown("---")
    fig = create_labels_chart(df, timeframe)
    st.plotly_chart(fig, width='stretch')
    
    # Legend
    st.markdown("""
    **📖 Come leggere il grafico:**
    - **🟢 Triangle Up**: Score LONG positivo (buon segnale per entrare LONG)
    - **🔴 Triangle Down**: Score SHORT positivo (buon segnale per entrare SHORT)
    - **Score Bars**: Verdi = positivi (profittevoli), Rossi = negativi (perdita)
    """)
    
    # Data table
    with st.expander("📋 View Raw Data (last 20)", expanded=False):
        cols_to_show = ['open', 'high', 'low', 'close', 'score_long', 'score_short', 
                        'exit_type_long', 'exit_type_short', 'bars_held_long', 'bars_held_short']
        available = [c for c in cols_to_show if c in df.columns]
        display_df = df.tail(20)[available]
        display_df = display_df.round(5)
        render_html_table(display_df.reset_index(), height=400)


def render_quick_preview(ohlcv_df: pd.DataFrame = None, labels_df: pd.DataFrame = None, timeframe: str = '15m'):
    """Quick preview for labeling page."""
    # Get BTC data by default
    symbols = get_available_symbols_with_labels(timeframe)
    if not symbols:
        st.info("No labels available for preview")
        return
    
    # Prefer BTC
    btc_symbols = [s for s in symbols if 'BTC' in s]
    symbol = btc_symbols[0] if btc_symbols else symbols[0]
    
    df = get_labels_with_prices(symbol, timeframe, 100)
    
    if df is None or len(df) == 0:
        st.info("No data for preview")
        return
    
    fig = create_labels_chart(df, timeframe)
    fig.update_layout(height=500, title=f"Preview: {symbol.replace('/USDT:USDT', '')} ({timeframe}) - Last 100 candles")
    st.plotly_chart(fig, width='stretch')


__all__ = [
    'get_labels_with_prices',
    'get_available_symbols_with_labels',
    'create_labels_chart',
    'render_visualizer_ui',
    'render_quick_preview'
]
