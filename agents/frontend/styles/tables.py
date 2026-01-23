"""
📊 Styled HTML Tables Module

Reusable HTML table rendering for dark theme compatibility.
Replaces st.table() and st.dataframe() which have visibility issues.
"""

import streamlit as st
import pandas as pd
from typing import Optional, List, Dict


def render_html_table(
    df: pd.DataFrame,
    height: int = 400,
    show_index: bool = False,
    highlight_columns: Optional[List[str]] = None
):
    """
    Render DataFrame as styled HTML table with dark theme.
    
    Replaces st.table() and st.dataframe() for better dark theme visibility.
    
    Args:
        df: DataFrame to display
        height: Height of the scrollable container in pixels
        show_index: Whether to show the DataFrame index
        highlight_columns: List of column names to apply value-based coloring
    
    Example:
        render_html_table(df, height=300, highlight_columns=['Return', 'Score'])
    """
    if df is None or len(df) == 0:
        st.warning("No data to display")
        return
    
    # Reset index if needed
    if show_index and df.index.name:
        df = df.reset_index()
    elif show_index:
        df = df.reset_index(drop=False)
    
    # Default highlight columns
    if highlight_columns is None:
        highlight_columns = []
    
    # CSS styles
    table_css = f"""
    <style>
        .styled-table-container {{
            max-height: {height}px;
            overflow-y: auto;
            overflow-x: auto;
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 10px;
            background: #0d1117;
            margin: 10px 0;
        }}
        .styled-table {{
            width: 100%;
            border-collapse: collapse;
            font-family: 'Rajdhani', monospace;
            font-size: 13px;
            white-space: nowrap;
        }}
        .styled-table thead {{
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        .styled-table th {{
            background: linear-gradient(135deg, #1a1f2e 0%, #2d3548 100%);
            color: #00ffff !important;
            padding: 12px 10px;
            text-align: left;
            border-bottom: 2px solid rgba(0, 255, 255, 0.5);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .styled-table td {{
            background: #0d1117;
            color: #e0e0ff !important;
            padding: 10px;
            border-bottom: 1px solid rgba(0, 255, 255, 0.1);
        }}
        .styled-table tr:hover td {{
            background: rgba(0, 255, 255, 0.1);
        }}
        .styled-table tr:nth-child(even) td {{
            background: rgba(15, 20, 40, 0.5);
        }}
        .styled-table tr:nth-child(even):hover td {{
            background: rgba(0, 255, 255, 0.15);
        }}
        /* Semantic colors */
        .cell-positive {{ color: #00ff88 !important; font-weight: 600; }}
        .cell-negative {{ color: #ff4757 !important; font-weight: 600; }}
        .cell-neutral {{ color: #ffc107 !important; }}
        .cell-muted {{ color: #8899aa !important; font-family: monospace; }}
    </style>
    """
    
    # Build HTML table
    html_rows = []
    
    # Header
    header_cells = "".join([f"<th>{col}</th>" for col in df.columns])
    html_rows.append(f"<thead><tr>{header_cells}</tr></thead>")
    
    # Body
    html_rows.append("<tbody>")
    for _, row in df.iterrows():
        cells = []
        for col, val in zip(df.columns, row.values):
            cell_class = _get_cell_class(col, val, highlight_columns)
            cells.append(f'<td class="{cell_class}">{val}</td>')
        html_rows.append(f"<tr>{''.join(cells)}</tr>")
    html_rows.append("</tbody>")
    
    # Combine
    table_html = f"""
    {table_css}
    <div class="styled-table-container">
        <table class="styled-table">
            {''.join(html_rows)}
        </table>
    </div>
    """
    
    st.markdown(table_html, unsafe_allow_html=True)


def _get_cell_class(col: str, val, highlight_columns: List[str]) -> str:
    """
    Determine CSS class for cell based on column name and value.
    
    Args:
        col: Column name
        val: Cell value
        highlight_columns: List of columns to apply value-based coloring
    
    Returns:
        CSS class name
    """
    col_lower = str(col).lower()
    
    # Check if column should be highlighted
    should_highlight = any(h.lower() in col_lower for h in highlight_columns)
    
    # Auto-detect columns to highlight
    auto_highlight = any(kw in col_lower for kw in [
        'return', 'score', 'sharpe', 'pf', 'profit', 'r²', 'r2',
        'mfe', 'mae', 'positive', 'win', 'drawdown', 'dd'
    ])
    
    if should_highlight or auto_highlight:
        try:
            # Clean value for comparison
            val_str = str(val).replace('%', '').replace(',', '').strip()
            val_float = float(val_str)
            
            if val_float > 0:
                return "cell-positive"
            elif val_float < 0:
                return "cell-negative"
        except (ValueError, TypeError):
            pass
    
    # Special formatting for certain column types
    if col_lower in ['timestamp', 'time', 'date', 'from', 'to']:
        return "cell-muted"
    
    if 'exit' in col_lower or 'type' in col_lower:
        val_str = str(val).lower()
        if val_str == 'trailing':
            return "cell-positive"
        elif val_str == 'stop':
            return "cell-negative"
        elif val_str in ['time', 'timeout']:
            return "cell-neutral"
    
    return ""


def render_metrics_table(
    data: List[Dict],
    height: int = 300
):
    """
    Render a metrics comparison table (e.g., LONG vs SHORT).
    
    Args:
        data: List of dicts with keys like 'Metric', 'LONG', 'SHORT'
        height: Table height
    
    Example:
        data = [
            {'Metric': 'R²', 'LONG': '0.032', 'SHORT': '0.028'},
            {'Metric': 'RMSE', 'LONG': '0.0045', 'SHORT': '0.0051'},
        ]
        render_metrics_table(data)
    """
    df = pd.DataFrame(data)
    render_html_table(df, height=height)


def render_ranking_table(
    data: List[Dict],
    height: int = 400,
    rank_column: str = "Rank"
):
    """
    Render a ranking table with medal emojis for top 3.
    
    Args:
        data: List of dicts with ranking data
        height: Table height
        rank_column: Name of the rank column
    
    Example:
        data = [
            {'Rank': 1, 'Config': 'A', 'Return': '+12.5%'},
            {'Rank': 2, 'Config': 'B', 'Return': '+10.2%'},
        ]
        render_ranking_table(data)
    """
    df = pd.DataFrame(data)
    
    # Add medal emojis to rank column
    if rank_column in df.columns:
        df[rank_column] = df[rank_column].apply(_format_rank)
    
    render_html_table(df, height=height)


def _format_rank(rank) -> str:
    """Format rank with medal emojis."""
    try:
        rank_int = int(rank)
        if rank_int == 1:
            return "🥇"
        elif rank_int == 2:
            return "🥈"
        elif rank_int == 3:
            return "🥉"
        else:
            return f"#{rank_int}"
    except (ValueError, TypeError):
        return str(rank)


__all__ = [
    'render_html_table',
    'render_metrics_table',
    'render_ranking_table'
]
