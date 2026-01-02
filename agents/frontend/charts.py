"""
📊 Chart creation functions using Plotly for the Crypto Dashboard
Uses centralized colors from styles/colors.py
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from styles.colors import PALETTE, CHART_COLORS, PLOTLY_LAYOUT
from indicators import (
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands
)


def _apply_layout(fig, title: str, height: int, rows: int):
    """Apply consistent layout to a figure using centralized colors"""
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>", 
            font=dict(size=24, color=PALETTE['text_primary']), 
            x=0.5
        ),
        template=PLOTLY_LAYOUT['template'],
        paper_bgcolor=PLOTLY_LAYOUT['paper_bgcolor'],
        plot_bgcolor=PLOTLY_LAYOUT['plot_bgcolor'],
        height=height,
        margin=dict(l=60, r=60, t=80, b=40),
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(
            orientation="h", 
            y=1.02, 
            x=0.5, 
            xanchor="center",
            font=dict(color=PLOTLY_LAYOUT['legend_font_color'], size=10), 
            bgcolor=PLOTLY_LAYOUT['legend_bgcolor']
        ),
        hovermode='x unified'
    )
    
    # Apply axis styling to all rows
    for i in range(1, rows + 1):
        fig.update_xaxes(
            gridcolor=PLOTLY_LAYOUT['grid_color'], 
            linecolor=PLOTLY_LAYOUT['axis_line_color'],
            tickfont=dict(color=PLOTLY_LAYOUT['axis_text_color']), 
            row=i, col=1
        )
        fig.update_yaxes(
            gridcolor=PLOTLY_LAYOUT['grid_color'], 
            linecolor=PLOTLY_LAYOUT['axis_line_color'],
            tickfont=dict(color=PLOTLY_LAYOUT['axis_text_color']), 
            row=i, col=1
        )


def create_advanced_chart(df, symbol, show_indicators=True, warmup_skip=0):
    """
    Create advanced candlestick chart with indicators.
    
    Args:
        df: DataFrame with OHLCV data (includes warmup period)
        symbol: Symbol name
        show_indicators: Whether to show RSI, MACD
        warmup_skip: Number of candles to skip from beginning for display
    """
    
    rows = 4 if show_indicators else 2
    row_heights = [0.5, 0.15, 0.15, 0.2] if show_indicators else [0.7, 0.3]
    
    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=('', 'RSI', 'MACD', 'Volume') if show_indicators else ('', 'Volume')
    )
    
    # Calculate all indicators on FULL data (before slicing)
    upper_full, sma_full, lower_full = None, None, None
    ema20_full, ema50_full = None, None
    
    if len(df) >= 20:
        upper_full, sma_full, lower_full = calculate_bollinger_bands(df)
        ema20_full = df['close'].ewm(span=20).mean()
        ema50_full = df['close'].ewm(span=50).mean() if len(df) >= 50 else None
    
    rsi_full, macd_full, signal_full, hist_full = None, None, None, None
    if show_indicators:
        rsi_full = calculate_rsi(df)
        macd_full, signal_full, hist_full = calculate_macd(df)
    
    # Slice for display (skip warmup period)
    df_display = df.iloc[warmup_skip:].copy() if warmup_skip > 0 else df
    
    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df_display.index,
            open=df_display['open'],
            high=df_display['high'],
            low=df_display['low'],
            close=df_display['close'],
            name='OHLC',
            increasing=dict(
                line=dict(color=CHART_COLORS['candle_up_line']), 
                fillcolor=CHART_COLORS['candle_up_fill']
            ),
            decreasing=dict(
                line=dict(color=CHART_COLORS['candle_down_line']), 
                fillcolor=CHART_COLORS['candle_down_fill']
            ),
        ),
        row=1, col=1
    )
    
    # Bollinger Bands (sliced)
    if upper_full is not None:
        upper = upper_full.iloc[warmup_skip:] if warmup_skip > 0 else upper_full
        sma = sma_full.iloc[warmup_skip:] if warmup_skip > 0 else sma_full
        lower = lower_full.iloc[warmup_skip:] if warmup_skip > 0 else lower_full
        
        fig.add_trace(go.Scatter(
            x=df_display.index, y=upper, name='BB Upper',
            line=dict(color=CHART_COLORS['bb_upper'], width=1)
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=df_display.index, y=sma, name='BB SMA',
            line=dict(color=CHART_COLORS['bb_middle'], width=1)
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=df_display.index, y=lower, name='BB Lower',
            line=dict(color=CHART_COLORS['bb_lower'], width=1),
            fill='tonexty', fillcolor=CHART_COLORS['bb_fill']
        ), row=1, col=1)
    
    # EMA (sliced)
    if ema20_full is not None:
        ema20 = ema20_full.iloc[warmup_skip:] if warmup_skip > 0 else ema20_full
        fig.add_trace(go.Scatter(
            x=df_display.index, y=ema20, name='EMA 20',
            line=dict(color=CHART_COLORS['ema_20'], width=1.5)
        ), row=1, col=1)
        
        if ema50_full is not None:
            ema50 = ema50_full.iloc[warmup_skip:] if warmup_skip > 0 else ema50_full
            fig.add_trace(go.Scatter(
                x=df_display.index, y=ema50, name='EMA 50',
                line=dict(color=CHART_COLORS['ema_50'], width=1.5)
            ), row=1, col=1)
    
    if show_indicators:
        # RSI (sliced)
        rsi = rsi_full.iloc[warmup_skip:] if warmup_skip > 0 else rsi_full
        fig.add_trace(go.Scatter(
            x=df_display.index, y=rsi, name='RSI',
            line=dict(color=CHART_COLORS['rsi'], width=1.5)
        ), row=2, col=1)
        
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(255,71,87,0.5)", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="rgba(0,255,136,0.5)", row=2, col=1)
        fig.add_hrect(y0=30, y1=70, fillcolor="rgba(168,85,247,0.1)", line_width=0, row=2, col=1)
        
        # MACD (sliced)
        macd_line = macd_full.iloc[warmup_skip:] if warmup_skip > 0 else macd_full
        signal_line = signal_full.iloc[warmup_skip:] if warmup_skip > 0 else signal_full
        histogram = hist_full.iloc[warmup_skip:] if warmup_skip > 0 else hist_full
        
        colors = [CHART_COLORS['macd_hist_positive'] if val >= 0 
                  else CHART_COLORS['macd_hist_negative'] for val in histogram]
        
        fig.add_trace(go.Bar(
            x=df_display.index, y=histogram, name='MACD Hist',
            marker=dict(color=colors, opacity=0.6)
        ), row=3, col=1)
        
        fig.add_trace(go.Scatter(
            x=df_display.index, y=macd_line, name='MACD',
            line=dict(color=CHART_COLORS['macd_line'], width=1.5)
        ), row=3, col=1)
        
        fig.add_trace(go.Scatter(
            x=df_display.index, y=signal_line, name='Signal',
            line=dict(color=CHART_COLORS['macd_signal'], width=1.5)
        ), row=3, col=1)
        
        # Volume
        colors_vol = [CHART_COLORS['volume_up'] if c >= o 
                      else CHART_COLORS['volume_down'] 
                      for c, o in zip(df_display['close'], df_display['open'])]
        fig.add_trace(go.Bar(
            x=df_display.index, y=df_display['volume'], name='Volume',
            marker=dict(color=colors_vol, opacity=0.7)
        ), row=4, col=1)
    else:
        # Only Volume
        colors_vol = [CHART_COLORS['volume_up'] if c >= o 
                      else CHART_COLORS['volume_down'] 
                      for c, o in zip(df_display['close'], df_display['open'])]
        fig.add_trace(go.Bar(
            x=df_display.index, y=df_display['volume'], name='Volume',
            marker=dict(color=colors_vol, opacity=0.7)
        ), row=2, col=1)
    
    # Apply layout
    symbol_name = symbol.replace('/USDT:USDT', '')
    height = 800 if show_indicators else 550
    _apply_layout(fig, f"{symbol_name}/USDT", height, rows)
    
    return fig


def create_volume_analysis_chart(df, symbol):
    """Create volume analysis chart with 4 subplots"""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Volume Distribution', 'Price vs Volume Correlation', 
                       'Volume Profile', 'Cumulative Volume'),
        specs=[[{"type": "histogram"}, {"type": "scatter"}],
               [{"type": "bar"}, {"type": "scatter"}]]
    )
    
    # Volume Distribution
    fig.add_trace(go.Histogram(
        x=df['volume'], nbinsx=30, name='Volume Dist',
        marker_color=PALETTE['accent_blue'], opacity=0.7
    ), row=1, col=1)
    
    # Price vs Volume
    fig.add_trace(go.Scatter(
        x=df['volume'], y=df['close'], mode='markers',
        name='Price vs Vol', 
        marker=dict(color=PALETTE['accent_green'], size=5, opacity=0.6)
    ), row=1, col=2)
    
    # Volume Profile (by price level)
    price_bins = pd.cut(df['close'], bins=20)
    vol_profile = df.groupby(price_bins, observed=True)['volume'].sum()
    fig.add_trace(go.Bar(
        x=vol_profile.values, y=[str(x) for x in vol_profile.index],
        orientation='h', name='Vol Profile', 
        marker_color=PALETTE['accent_purple']
    ), row=2, col=1)
    
    # Cumulative Volume
    cum_vol = df['volume'].cumsum()
    fig.add_trace(go.Scatter(
        x=df.index, y=cum_vol, name='Cum Volume',
        line=dict(color=PALETTE['accent_yellow'], width=2)
    ), row=2, col=2)
    
    fig.update_layout(
        template=PLOTLY_LAYOUT['template'],
        paper_bgcolor=PLOTLY_LAYOUT['paper_bgcolor'],
        plot_bgcolor=PLOTLY_LAYOUT['plot_bgcolor'],
        height=500,
        showlegend=False,
        margin=dict(l=50, r=50, t=60, b=40)
    )
    
    return fig


def create_market_overview_chart(top_symbols):
    """Create market overview chart for top coins"""
    if not top_symbols:
        return None
    
    df = pd.DataFrame(top_symbols[:20])
    df['coin'] = df['symbol'].str.replace('/USDT:USDT', '')
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Top 20 by Volume', 'Volume Distribution'),
        specs=[[{"type": "bar"}, {"type": "pie"}]]
    )
    
    # Bar chart
    fig.add_trace(go.Bar(
        x=df['coin'], y=df['volume_24h'], name='Volume',
        marker=dict(color=df['volume_24h'], colorscale='Viridis')
    ), row=1, col=1)
    
    # Pie chart top 10
    df_pie = df.head(10)
    fig.add_trace(go.Pie(
        labels=df_pie['coin'], values=df_pie['volume_24h'],
        hole=0.4, name='Distribution'
    ), row=1, col=2)
    
    fig.update_layout(
        template=PLOTLY_LAYOUT['template'],
        paper_bgcolor=PLOTLY_LAYOUT['paper_bgcolor'],
        plot_bgcolor=PLOTLY_LAYOUT['plot_bgcolor'],
        height=400,
        showlegend=False,
        margin=dict(l=50, r=50, t=60, b=40)
    )
    
    return fig
