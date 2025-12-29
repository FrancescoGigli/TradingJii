"""
Chart creation functions using Plotly for the Crypto Dashboard
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from indicators import (
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands
)


def create_advanced_chart(df, symbol, show_indicators=True):
    """Create advanced candlestick chart with indicators"""
    
    rows = 4 if show_indicators else 2
    row_heights = [0.5, 0.15, 0.15, 0.2] if show_indicators else [0.7, 0.3]
    
    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=('', 'RSI', 'MACD', 'Volume') if show_indicators else ('', 'Volume')
    )
    
    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='OHLC',
            increasing=dict(line=dict(color='#00ff88'), fillcolor='#00875a'),
            decreasing=dict(line=dict(color='#ff4757'), fillcolor='#c92a2a'),
        ),
        row=1, col=1
    )
    
    # Bollinger Bands
    if len(df) >= 20:
        upper, sma, lower = calculate_bollinger_bands(df)
        fig.add_trace(go.Scatter(x=df.index, y=upper, name='BB Upper', 
                                  line=dict(color='rgba(0, 212, 255, 0.3)', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=sma, name='BB SMA', 
                                  line=dict(color='#00d4ff', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=lower, name='BB Lower', 
                                  line=dict(color='rgba(0, 212, 255, 0.3)', width=1),
                                  fill='tonexty', fillcolor='rgba(0, 212, 255, 0.05)'), row=1, col=1)
    
    # EMA
    if len(df) >= 20:
        ema20 = df['close'].ewm(span=20).mean()
        ema50 = df['close'].ewm(span=50).mean() if len(df) >= 50 else None
        fig.add_trace(go.Scatter(x=df.index, y=ema20, name='EMA 20',
                                  line=dict(color='#ffc107', width=1.5)), row=1, col=1)
        if ema50 is not None:
            fig.add_trace(go.Scatter(x=df.index, y=ema50, name='EMA 50',
                                      line=dict(color='#ff6b35', width=1.5)), row=1, col=1)
    
    if show_indicators:
        # RSI
        rsi = calculate_rsi(df)
        fig.add_trace(go.Scatter(x=df.index, y=rsi, name='RSI',
                                  line=dict(color='#a855f7', width=1.5)), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(255,71,87,0.5)", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="rgba(0,255,136,0.5)", row=2, col=1)
        fig.add_hrect(y0=30, y1=70, fillcolor="rgba(168,85,247,0.1)", line_width=0, row=2, col=1)
        
        # MACD
        macd_line, signal_line, histogram = calculate_macd(df)
        colors = ['#00ff88' if val >= 0 else '#ff4757' for val in histogram]
        fig.add_trace(go.Bar(x=df.index, y=histogram, name='MACD Hist',
                              marker=dict(color=colors, opacity=0.6)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=macd_line, name='MACD',
                                  line=dict(color='#00d4ff', width=1.5)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=signal_line, name='Signal',
                                  line=dict(color='#ff6b35', width=1.5)), row=3, col=1)
        
        # Volume
        colors_vol = ['#00875a' if c >= o else '#c92a2a' for c, o in zip(df['close'], df['open'])]
        fig.add_trace(go.Bar(x=df.index, y=df['volume'], name='Volume',
                              marker=dict(color=colors_vol, opacity=0.7)), row=4, col=1)
    else:
        # Only Volume
        colors_vol = ['#00875a' if c >= o else '#c92a2a' for c, o in zip(df['close'], df['open'])]
        fig.add_trace(go.Bar(x=df.index, y=df['volume'], name='Volume',
                              marker=dict(color=colors_vol, opacity=0.7)), row=2, col=1)
    
    # Layout
    symbol_name = symbol.replace('/USDT:USDT', '')
    height = 800 if show_indicators else 550
    
    fig.update_layout(
        title=dict(text=f"<b>{symbol_name}/USDT</b>", font=dict(size=24, color='#f0f6fc'), x=0.5),
        template='plotly_dark',
        paper_bgcolor='#0a0e14',
        plot_bgcolor='#111820',
        height=height,
        margin=dict(l=60, r=60, t=80, b=40),
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center", 
                    font=dict(color='#8b949e', size=10), bgcolor='rgba(0,0,0,0)'),
        hovermode='x unified'
    )
    
    # Axes styling
    for i in range(1, rows + 1):
        fig.update_xaxes(gridcolor='#1e2a38', linecolor='#30363d', 
                         tickfont=dict(color='#8b949e'), row=i, col=1)
        fig.update_yaxes(gridcolor='#1e2a38', linecolor='#30363d', 
                         tickfont=dict(color='#8b949e'), row=i, col=1)
    
    return fig


def create_volume_analysis_chart(df, symbol):
    """Create volume analysis chart"""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Volume Distribution', 'Price vs Volume Correlation', 
                       'Volume Profile', 'Cumulative Volume'),
        specs=[[{"type": "histogram"}, {"type": "scatter"}],
               [{"type": "bar"}, {"type": "scatter"}]]
    )
    
    # Volume Distribution
    fig.add_trace(go.Histogram(x=df['volume'], nbinsx=30, name='Volume Dist',
                                marker_color='#00d4ff', opacity=0.7), row=1, col=1)
    
    # Price vs Volume
    fig.add_trace(go.Scatter(x=df['volume'], y=df['close'], mode='markers',
                              name='Price vs Vol', marker=dict(color='#00ff88', size=5, opacity=0.6)), 
                  row=1, col=2)
    
    # Volume Profile (by price level)
    price_bins = pd.cut(df['close'], bins=20)
    vol_profile = df.groupby(price_bins, observed=True)['volume'].sum()
    fig.add_trace(go.Bar(x=vol_profile.values, y=[str(x) for x in vol_profile.index],
                          orientation='h', name='Vol Profile', marker_color='#a855f7'), row=2, col=1)
    
    # Cumulative Volume
    cum_vol = df['volume'].cumsum()
    fig.add_trace(go.Scatter(x=df.index, y=cum_vol, name='Cum Volume',
                              line=dict(color='#ffc107', width=2)), row=2, col=2)
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0a0e14',
        plot_bgcolor='#111820',
        height=500,
        showlegend=False,
        margin=dict(l=50, r=50, t=60, b=40)
    )
    
    return fig


def create_market_overview_chart(top_symbols):
    """Create market overview chart"""
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
    fig.add_trace(go.Bar(x=df['coin'], y=df['volume_24h'], name='Volume',
                          marker=dict(color=df['volume_24h'], colorscale='Viridis')), row=1, col=1)
    
    # Pie chart top 10
    df_pie = df.head(10)
    fig.add_trace(go.Pie(labels=df_pie['coin'], values=df_pie['volume_24h'],
                          hole=0.4, name='Distribution'), row=1, col=2)
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0a0e14',
        plot_bgcolor='#111820',
        height=400,
        showlegend=False,
        margin=dict(l=50, r=50, t=60, b=40)
    )
    
    return fig
