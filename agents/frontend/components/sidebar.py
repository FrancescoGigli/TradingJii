"""
📋 Sidebar component for the Crypto Dashboard
Shows real-time status of data-fetcher and database update info
Uses centralized colors from styles/colors.py
"""

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta

from database import get_update_status
from styles.colors import PALETTE, STATUS_COLORS


def get_status_html(status_data):
    """Generate HTML for the control panel based on current status"""
    
    status = status_data.get('status', 'OFFLINE')
    last_update = status_data.get('last_update')
    duration = status_data.get('duration_sec', 0)
    symbols_updated = status_data.get('symbols_updated', 0)
    candles_updated = status_data.get('candles_updated', 0)
    
    # Determine status display using centralized colors
    if status == 'UPDATING':
        status_color = STATUS_COLORS['updating']
        status_text = 'UPDATING'
        status_animation = 'pulse-fast'
    elif status == 'OFFLINE':
        status_color = STATUS_COLORS['offline']
        status_text = 'OFFLINE'
        status_animation = 'pulse'
    else:  # IDLE = LIVE
        status_color = STATUS_COLORS['live']
        status_text = 'LIVE'
        status_animation = 'pulse'
    
    # Calculate time ago
    time_ago_str = "Never"
    warning_class = ""
    warning_html = ""
    
    if last_update:
        try:
            last_dt = datetime.strptime(last_update, '%Y-%m-%d %H:%M:%S')
            now_utc = datetime.utcnow()
            diff = now_utc - last_dt
            data_age_minutes = diff.total_seconds() / 60
            
            if diff.total_seconds() < 60:
                time_ago_str = f"{int(diff.total_seconds())}s ago"
            elif diff.total_seconds() < 3600:
                time_ago_str = f"{int(diff.total_seconds() / 60)}m ago"
            else:
                hours = int(diff.total_seconds() / 3600)
                time_ago_str = f"{hours}h ago"
            
            # Warning levels
            if data_age_minutes > 60:
                warning_class = "stale-danger"
                warning_html = '<div class="warning-box danger">⚠️ Database not updated for over 1 hour!</div>'
            elif data_age_minutes > 20:
                warning_class = "stale-warning"
                warning_html = '<div class="warning-box warning">⚠️ Data might be stale</div>'
                
        except Exception:
            time_ago_str = "Unknown"
    
    # Format last update time for display
    last_update_display = "--:--:--"
    if last_update:
        try:
            last_dt = datetime.strptime(last_update, '%Y-%m-%d %H:%M:%S')
            last_dt_rome = last_dt + timedelta(hours=1)
            last_update_display = last_dt_rome.strftime('%H:%M:%S')
        except Exception:
            pass
    
    duration_str = f"{duration:.1f}s" if duration else "--"
    
    # Use centralized palette colors
    bg_card = PALETTE['bg_card']
    bg_secondary = PALETTE['bg_secondary']
    cyan = PALETTE['accent_cyan']
    yellow = PALETTE['accent_yellow']
    text_muted = PALETTE['text_muted']
    text_primary = PALETTE['text_primary']
    green = PALETTE['accent_green']
    border = PALETTE['border_primary']
    
    html = f"""
<div id="sidebar-control-panel">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@500;600&display=swap');

    #sidebar-control-panel * {{ box-sizing: border-box; }}
    #sidebar-control-panel .control-panel {{
        background: {bg_card};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 10px;
        width: 100%;
        max-width: 100%;
    }}
    #sidebar-control-panel .live-row {{
        display: flex;
        align-items: center;
        margin-bottom: 8px;
    }}
    #sidebar-control-panel .status-dot {{
        width: 10px;
        height: 10px;
        background: {status_color};
        border-radius: 50%;
        margin-right: 10px;
        box-shadow: 0 0 12px {status_color};
        animation: {status_animation} 1.5s ease-in-out infinite;
    }}
    @keyframes pulse {{
        0%, 100% {{ opacity: 1; transform: scale(1); }}
        50% {{ opacity: 0.6; transform: scale(0.95); }}
    }}
    @keyframes pulse-fast {{
        0%, 100% {{ opacity: 1; transform: scale(1); }}
        50% {{ opacity: 0.4; transform: scale(0.9); }}
    }}
    #sidebar-control-panel .live-text {{
        color: {status_color};
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 2px;
    }}
    #sidebar-control-panel .clock {{
        color: {cyan};
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 1.4rem;
        text-shadow: 0 0 10px rgba(0, 255, 255, 0.4);
        line-height: 1.2;
    }}
    #sidebar-control-panel .date {{
        color: {text_muted};
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.8rem;
        margin-bottom: 10px;
    }}
    
    /* Database Status Section */
    #sidebar-control-panel .db-status {{
        background: rgba(0, 255, 255, 0.05);
        border: 1px solid rgba(0, 255, 255, 0.15);
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 10px;
    }}
    #sidebar-control-panel .db-status.stale-warning {{
        border-color: rgba(255, 193, 7, 0.5);
        background: rgba(255, 193, 7, 0.1);
    }}
    #sidebar-control-panel .db-status.stale-danger {{
        border-color: rgba(255, 68, 68, 0.5);
        background: rgba(255, 68, 68, 0.1);
    }}
    #sidebar-control-panel .db-title {{
        color: {cyan};
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    #sidebar-control-panel .db-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }}
    #sidebar-control-panel .db-label {{
        color: {text_muted};
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.8rem;
    }}
    #sidebar-control-panel .db-value {{
        color: {text_primary};
        font-family: 'Orbitron', sans-serif;
        font-weight: 600;
        font-size: 0.9rem;
    }}
    #sidebar-control-panel .time-ago {{
        color: {yellow};
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.85rem;
        font-weight: 600;
    }}
    
    /* Warning Box */
    #sidebar-control-panel .warning-box {{
        padding: 8px 12px;
        border-radius: 6px;
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.8rem;
        font-weight: 600;
        margin-top: 8px;
        text-align: center;
    }}
    #sidebar-control-panel .warning-box.warning {{
        background: rgba(255, 193, 7, 0.2);
        color: {yellow};
        border: 1px solid rgba(255, 193, 7, 0.4);
    }}
    #sidebar-control-panel .warning-box.danger {{
        background: rgba(255, 68, 68, 0.2);
        color: {STATUS_COLORS['danger']};
        border: 1px solid rgba(255, 68, 68, 0.4);
        animation: blink 1s ease-in-out infinite;
    }}
    @keyframes blink {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.5; }}
    }}
    
    /* Next Update Section */
    #sidebar-control-panel .update-box {{
        background: rgba(0, 255, 255, 0.08);
        border: 1px solid rgba(0, 255, 255, 0.2);
        border-radius: 8px;
        padding: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    #sidebar-control-panel .update-label {{
        color: {text_muted};
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    #sidebar-control-panel .update-time {{
        color: {cyan};
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 0.9rem;
    }}
    #sidebar-control-panel .countdown {{
        color: {yellow};
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 0.9rem;
    }}
    
    /* Stats row */
    #sidebar-control-panel .stats-row {{
        display: flex;
        justify-content: space-around;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid rgba(0, 255, 255, 0.1);
    }}
    #sidebar-control-panel .stat-item {{
        text-align: center;
        flex: 1;
    }}
    #sidebar-control-panel .stat-value {{
        color: {green};
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 0.85rem;
    }}
    #sidebar-control-panel .stat-label {{
        color: {text_muted};
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.6rem;
        text-transform: uppercase;
    }}
</style>
<div class="control-panel">
    <div class="live-row">
        <span class="status-dot"></span>
        <span class="live-text">{status_text}</span>
    </div>
    
    <div class="clock" id="clock">--:--:--</div>
    <div class="date" id="date">--/--/----</div>
    
    <div class="db-status {warning_class}">
        <div class="db-title">📊 Database Status</div>
        <div class="db-row">
            <span class="db-label">Last Update</span>
            <span class="db-value">{last_update_display}</span>
        </div>
        <div class="db-row">
            <span class="db-label">Age</span>
            <span class="time-ago">{time_ago_str}</span>
        </div>
        <div class="db-row">
            <span class="db-label">Duration</span>
            <span class="db-value">{duration_str}</span>
        </div>
        {warning_html}
    </div>
    
    <div class="stats-row">
        <div class="stat-item">
            <div class="stat-value">{symbols_updated}</div>
            <div class="stat-label">Symbols</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">{candles_updated:,}</div>
            <div class="stat-label">Candles</div>
        </div>
    </div>
    
    <div style="margin: 10px 0; border-top: 1px solid rgba(0, 255, 255, 0.15);"></div>
    
    <div class="update-box">
        <div class="update-left">
            <div class="update-label">Next Update</div>
            <div class="update-time" id="nextUpdate">--:--</div>
        </div>
        <div class="countdown-box">
            <div class="update-label">Remaining</div>
            <div class="countdown" id="countdown">--:--</div>
        </div>
    </div>
</div>
<script>
    function updateClock() {{
        const now = new Date();
        const options = {{ timeZone: 'Europe/Rome' }};
        const timeStr = now.toLocaleTimeString('en-GB', {{ ...options, hour: '2-digit', minute: '2-digit', second: '2-digit' }});
        const dateStr = now.toLocaleDateString('en-GB', {{ ...options, day: '2-digit', month: '2-digit', year: 'numeric' }});
        
        const root = document.getElementById('sidebar-control-panel');
        if (!root) return;
        root.querySelector('#clock').textContent = timeStr;
        root.querySelector('#date').textContent = dateStr;
        
        const romeTime = new Date(now.toLocaleString('en-US', {{ timeZone: 'Europe/Rome' }}));
        const minutes = romeTime.getMinutes();
        const seconds = romeTime.getSeconds();
        
        const nextUpdate = Math.ceil((minutes + 1) / 15) * 15;
        const nextHour = romeTime.getHours() + (nextUpdate >= 60 ? 1 : 0);
        const nextMin = nextUpdate >= 60 ? 0 : nextUpdate;
        
        root.querySelector('#nextUpdate').textContent = 
            String(nextHour % 24).padStart(2, '0') + ':' + String(nextMin).padStart(2, '0');
        
        let minutesLeft = (nextUpdate >= 60 ? 60 : nextUpdate) - minutes - 1;
        let secondsLeft = 60 - seconds;
        if (secondsLeft === 60) {{
            secondsLeft = 0;
            minutesLeft += 1;
        }}
        if (minutesLeft < 0) minutesLeft = 14;
        
        const countdownStr = '-' + String(minutesLeft).padStart(2, '0') + ':' + String(secondsLeft).padStart(2, '0');
        root.querySelector('#countdown').textContent = countdownStr;
    }}
    
    updateClock();
    setInterval(updateClock, 1000);
</script>
</div>
"""
    return html


def render_control_panel():
    """Render the live clock control panel with status"""
    st.markdown("## ⚡ Control Panel")
    status_data = get_update_status()
    html = get_status_html(status_data)
    components.html(html, height=380)


def render_refresh_button():
    """Render the manual refresh button (OHLCV data only)"""
    from config import REFRESH_SIGNAL_FILE
    from pathlib import Path
    
    status_data = get_update_status()
    is_updating = status_data.get('status') == 'UPDATING'
    
    st.markdown("---")
    st.markdown("##### 📊 Data Controls")
    
    # CSS is now in theme.py - no inline CSS needed here
    
    if is_updating:
        st.button("🔄 Refresh in progress...", disabled=True, use_container_width=True, key="btn_refresh_disabled")
    else:
        if st.button("🔄 Force Refresh Data", use_container_width=True, key="btn_refresh", 
                     help="Refresh OHLCV candles for coins in current Top 100 list"):
            try:
                Path(REFRESH_SIGNAL_FILE).parent.mkdir(parents=True, exist_ok=True)
                Path(REFRESH_SIGNAL_FILE).write_text("refresh requested from dashboard")
                st.success("✅ Refresh signal sent!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {e}")


def render_update_list_button():
    """Render the button to update Top 100 list"""
    from config import UPDATE_LIST_SIGNAL_FILE
    from pathlib import Path
    
    status_data = get_update_status()
    is_updating = status_data.get('status') == 'UPDATING'
    
    st.markdown("---")
    st.markdown("##### 📋 Top 100 List")
    st.caption("Update the ranking of top 100 coins by volume. This also refreshes all data.")
    
    if is_updating:
        st.button("📋 Update in progress...", disabled=True, use_container_width=True, key="btn_update_list_disabled")
    else:
        if st.button("📋 Update Top 100 List", use_container_width=True, key="btn_update_list",
                     help="Fetch new Top 100 coins by volume and refresh all data"):
            try:
                Path(UPDATE_LIST_SIGNAL_FILE).parent.mkdir(parents=True, exist_ok=True)
                Path(UPDATE_LIST_SIGNAL_FILE).write_text("update list requested from dashboard")
                st.success("✅ Update list signal sent!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {e}")


def render_sidebar():
    """Render the complete sidebar"""
    render_control_panel()
    render_refresh_button()
    render_update_list_button()
