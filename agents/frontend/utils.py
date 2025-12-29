"""
Utility functions for the Crypto Dashboard
"""

from datetime import datetime, timedelta
from pathlib import Path
import pytz
import streamlit as st

from config import ROME_TZ, UPDATE_INTERVAL_MINUTES, REFRESH_SIGNAL_FILE


def format_volume(vol):
    """Format volume in readable format"""
    if vol >= 1e9:
        return f"${vol/1e9:.2f}B"
    elif vol >= 1e6:
        return f"${vol/1e6:.1f}M"
    elif vol >= 1e3:
        return f"${vol/1e3:.1f}K"
    else:
        return f"${vol:.0f}"


def get_price_change_color(change):
    """Return color based on price change"""
    if change > 0:
        return "#00ff88"
    elif change < 0:
        return "#ff4757"
    return "#8b949e"


def get_rome_time():
    """Get current Rome time"""
    return datetime.now(ROME_TZ)


def format_datetime_rome(dt_str):
    """Convert UTC datetime string to Rome timezone formatted string"""
    if not dt_str:
        return "N/A"
    try:
        # Parse datetime string (format: 2025-12-23 16:30:00)
        dt = datetime.fromisoformat(dt_str.replace(' ', 'T'))
        # If no timezone, assume UTC
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        # Convert to Rome
        dt_rome = dt.astimezone(ROME_TZ)
        return dt_rome.strftime('%d/%m/%Y %H:%M')
    except Exception:
        return dt_str[:16] if dt_str else "N/A"


def get_next_update_info():
    """Calculate next update time and countdown"""
    now_rome = get_rome_time()
    
    # Calculate next 15-minute interval
    minutes = now_rome.minute
    next_15 = ((minutes // UPDATE_INTERVAL_MINUTES) + 1) * UPDATE_INTERVAL_MINUTES
    
    if next_15 >= 60:
        next_update = now_rome.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        next_update = now_rome.replace(minute=next_15, second=0, microsecond=0)
    
    # Calculate remaining time
    time_remaining = next_update - now_rome
    total_seconds = int(time_remaining.total_seconds())
    
    if total_seconds < 0:
        total_seconds = 0
    
    minutes_left = total_seconds // 60
    seconds_left = total_seconds % 60
    
    return {
        'next_update': next_update.strftime('%H:%M'),
        'minutes_left': minutes_left,
        'seconds_left': seconds_left,
        'countdown': f"{minutes_left:02d}:{seconds_left:02d}"
    }


def trigger_refresh():
    """Create signal file to trigger data refresh"""
    try:
        Path(REFRESH_SIGNAL_FILE).write_text(datetime.now().isoformat())
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False
