"""
🧩 Styled Components for the Crypto Dashboard
Reusable HTML components with consistent styling
"""

import pandas as pd
from typing import List, Dict, Optional, Any
from .colors import PALETTE, SIGNAL_COLORS, get_gradient, get_glow


def styled_table(df: pd.DataFrame, title: Optional[str] = None) -> str:
    """
    Generate a dark-themed HTML table from a DataFrame.
    
    Args:
        df: DataFrame to render
        title: Optional title above the table
    
    Returns:
        HTML string for the styled table
    """
    # Build header row
    headers = ''.join(f'<th>{col}</th>' for col in df.columns)
    
    # Build data rows
    rows = ''
    for idx, row in df.iterrows():
        cells = ''.join(f'<td>{val}</td>' for val in row.values)
        rows += f'<tr>{cells}</tr>'
    
    title_html = f'<div class="table-title">{title}</div>' if title else ''
    
    html = f"""
    <div class="styled-table-container">
        <style>
            .styled-table-container {{
                width: 100%;
                overflow-x: auto;
                margin: 10px 0;
            }}
            .styled-table-container .table-title {{
                color: {PALETTE['accent_cyan']};
                font-size: 1rem;
                font-weight: 600;
                margin-bottom: 10px;
                padding: 5px 0;
            }}
            .styled-table {{
                width: 100%;
                border-collapse: collapse;
                background: {PALETTE['bg_secondary']};
                border: 1px solid {PALETTE['border_primary']};
                border-radius: 8px;
                overflow: hidden;
            }}
            .styled-table th {{
                background: {PALETTE['bg_tertiary']};
                color: {PALETTE['accent_cyan']};
                padding: 12px 15px;
                text-align: left;
                font-weight: 600;
                font-size: 0.85rem;
                text-transform: uppercase;
                letter-spacing: 1px;
                border-bottom: 2px solid {PALETTE['border_primary']};
            }}
            .styled-table td {{
                padding: 10px 15px;
                color: {PALETTE['text_secondary']};
                border-bottom: 1px solid rgba(0, 255, 255, 0.1);
                font-size: 0.9rem;
            }}
            .styled-table tr:hover td {{
                background: rgba(0, 255, 255, 0.08);
            }}
            .styled-table tr:nth-child(even) td {{
                background: {PALETTE['bg_primary']};
            }}
            .styled-table tr:nth-child(even):hover td {{
                background: rgba(0, 255, 255, 0.08);
            }}
        </style>
        {title_html}
        <table class="styled-table">
            <thead><tr>{headers}</tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    """
    return html


def styled_signal_box(indicator: str, signal: str, color: str) -> str:
    """
    Generate a styled signal box (BUY/SELL/NEUTRAL).
    
    Args:
        indicator: Name of the indicator (e.g., "RSI", "MACD")
        signal: Signal text (e.g., "BUY", "SELL", "NEUTRAL")
        color: Background color for the box
    
    Returns:
        HTML string for the signal box
    """
    return f"""
    <div style="
        background-color: {color}; 
        padding: 15px; 
        border-radius: 10px; 
        text-align: center;
        box-shadow: {get_glow(color, 15)};
        transition: transform 0.2s ease;
    ">
        <h4 style="color: white; margin: 0; font-size: 0.9rem; opacity: 0.9;">{indicator}</h4>
        <h2 style="color: white; margin: 5px 0; font-size: 1.5rem; font-weight: 700;">{signal}</h2>
    </div>
    """


def styled_metric_card(label: str, value: str, delta: Optional[str] = None, 
                       delta_color: Optional[str] = None) -> str:
    """
    Generate a styled metric card.
    
    Args:
        label: Metric label
        value: Metric value
        delta: Optional delta/change value
        delta_color: Optional color for delta (green/red)
    
    Returns:
        HTML string for the metric card
    """
    delta_html = ''
    if delta:
        d_color = delta_color or PALETTE['text_muted']
        delta_html = f'<div class="metric-delta" style="color: {d_color};">{delta}</div>'
    
    return f"""
    <div style="
        background: {PALETTE['bg_card']};
        border: 1px solid {PALETTE['border_primary']};
        border-radius: 12px;
        padding: 15px 20px;
        text-align: center;
        transition: all 0.3s ease;
    ">
        <div style="color: {PALETTE['text_muted']}; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">{label}</div>
        <div style="color: {PALETTE['accent_cyan']}; font-size: 1.8rem; font-weight: 700; margin: 5px 0;">{value}</div>
        {delta_html}
    </div>
    """


def styled_info_box(content: str, box_type: str = 'info') -> str:
    """
    Generate a styled info/warning/success box.
    
    Args:
        content: Text content
        box_type: One of 'info', 'warning', 'success', 'danger'
    
    Returns:
        HTML string for the info box
    """
    colors = {
        'info': (PALETTE['accent_blue'], 'rgba(0, 212, 255, 0.15)'),
        'warning': (PALETTE['accent_yellow'], 'rgba(255, 193, 7, 0.15)'),
        'success': (PALETTE['accent_green'], 'rgba(0, 255, 136, 0.15)'),
        'danger': (PALETTE['accent_red'], 'rgba(255, 71, 87, 0.15)'),
    }
    text_color, bg_color = colors.get(box_type, colors['info'])
    
    return f"""
    <div style="
        background: {bg_color};
        border: 1px solid {text_color};
        border-radius: 10px;
        padding: 15px 20px;
        color: {text_color};
        margin: 10px 0;
    ">
        {content}
    </div>
    """


def styled_section_header(title: str, icon: str = '') -> str:
    """
    Generate a styled section header.
    
    Args:
        title: Section title
        icon: Optional emoji icon
    
    Returns:
        HTML string for the section header
    """
    icon_html = f'{icon} ' if icon else ''
    return f"""
    <h3 style="
        color: {PALETTE['text_primary']};
        font-size: 1.3rem;
        font-weight: 600;
        margin: 20px 0 15px 0;
        padding-bottom: 10px;
        border-bottom: 1px solid {PALETTE['border_primary']};
    ">
        {icon_html}{title}
    </h3>
    """


def styled_status_indicator(status: str, label: str) -> str:
    """
    Generate a styled status indicator with pulsing dot.
    
    Args:
        status: One of 'live', 'updating', 'offline'
        label: Status label text
    
    Returns:
        HTML string for the status indicator
    """
    from .colors import STATUS_COLORS
    
    color = STATUS_COLORS.get(status.lower(), STATUS_COLORS['offline'])
    
    return f"""
    <div style="display: flex; align-items: center; gap: 10px;">
        <span style="
            width: 10px;
            height: 10px;
            background: {color};
            border-radius: 50%;
            box-shadow: 0 0 10px {color};
            animation: pulse 1.5s ease-in-out infinite;
        "></span>
        <span style="color: {color}; font-weight: 600; letter-spacing: 1px;">{label}</span>
    </div>
    <style>
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.6; transform: scale(0.95); }}
        }}
    </style>
    """


def get_signal_color(signal: str) -> str:
    """
    Get color for a trading signal.
    
    Args:
        signal: Signal type (buy, sell, neutral, etc.)
    
    Returns:
        Hex color string
    """
    signal_lower = signal.lower()
    if 'buy' in signal_lower or 'bullish' in signal_lower or 'oversold' in signal_lower:
        return SIGNAL_COLORS['buy']
    elif 'sell' in signal_lower or 'bearish' in signal_lower or 'overbought' in signal_lower:
        return SIGNAL_COLORS['sell']
    else:
        return SIGNAL_COLORS['neutral']
