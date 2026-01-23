"""
📊 Chart Creation Functions

Plotly chart generators for label analysis visualization.
Contains: MAE histogram, score scatter, exit type pie, ATR analysis, etc.
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


def create_mae_histogram(
    labels_df: pd.DataFrame, 
    timeframe: str = '15m', 
    direction: str = 'long'
) -> go.Figure:
    """
    Create MAE (Max Adverse Excursion) histogram.
    
    Args:
        labels_df: DataFrame with labels
        timeframe: '15m' or '1h'
        direction: 'long' or 'short'
    
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
    fig.add_vline(
        x=mean_mae, 
        line_dash="dash", 
        line_color="yellow",
        annotation_text=f"Mean: {mean_mae:.2f}%"
    )
    
    fig.update_layout(
        title=f"📊 MAE Distribution ({direction.upper()} {timeframe})",
        xaxis_title="MAE (%)",
        yaxis_title="Count",
        template="plotly_dark",
        height=400
    )
    
    return fig


def create_mae_vs_score_scatter(
    labels_df: pd.DataFrame, 
    timeframe: str = '15m', 
    direction: str = 'long'
) -> go.Figure:
    """
    Create MAE vs Score scatter plot.
    
    Args:
        labels_df: DataFrame with labels
        timeframe: '15m' or '1h'
        direction: 'long' or 'short'
    
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


def create_exit_type_pie(
    labels_df: pd.DataFrame, 
    timeframe: str = '15m', 
    direction: str = 'long'
) -> go.Figure:
    """
    Create pie chart for exit types distribution.
    
    Args:
        labels_df: DataFrame with labels
        timeframe: '15m' or '1h'
        direction: 'long' or 'short'
    
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


def create_score_distribution(
    labels_df: pd.DataFrame, 
    timeframe: str = '15m'
) -> go.Figure:
    """
    Create LONG vs SHORT score distribution histogram.
    
    Args:
        labels_df: DataFrame with labels
        timeframe: '15m' or '1h'
    
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


def create_atr_analysis(
    labels_df: pd.DataFrame, 
    timeframe: str = '15m'
) -> go.Figure:
    """
    Create ATR% distribution histogram for volatility analysis.
    
    Args:
        labels_df: DataFrame with labels
        timeframe: '15m' or '1h'
    
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
    
    fig.add_vline(
        x=mean_atr, 
        line_dash="dash", 
        line_color="yellow",
        annotation_text=f"Mean: {mean_atr:.2f}%"
    )
    fig.add_vline(
        x=p25, 
        line_dash="dot", 
        line_color="gray",
        annotation_text=f"P25: {p25:.2f}%"
    )
    fig.add_vline(
        x=p75, 
        line_dash="dot", 
        line_color="gray",
        annotation_text=f"P75: {p75:.2f}%"
    )
    
    fig.update_layout(
        title=f"📈 ATR% Distribution ({timeframe})",
        xaxis_title="ATR (%)",
        yaxis_title="Count",
        template="plotly_dark",
        height=400
    )
    
    return fig


def create_bars_held_histogram(
    labels_df: pd.DataFrame, 
    timeframe: str = '15m', 
    direction: str = 'long'
) -> go.Figure:
    """
    Create histogram of bars held by exit type.
    
    Args:
        labels_df: DataFrame with labels
        timeframe: '15m' or '1h'
        direction: 'long' or 'short'
    
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
    
    exit_types = [
        ('fixed_sl', '#ef4444'),
        ('trailing', '#22c55e'),
        ('time', '#3b82f6')
    ]
    
    for exit_type, color in exit_types:
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
