"""
Sidebar component for the Crypto Dashboard
"""

import streamlit as st
import streamlit.components.v1 as components


CONTROL_PANEL_HTML = """
<div id="sidebar-control-panel">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@500;600&display=swap');

    #sidebar-control-panel * { box-sizing: border-box; }
    #sidebar-control-panel .control-panel {
        background: rgba(10, 15, 30, 0.9);
        border: 1px solid rgba(0, 255, 255, 0.3);
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 14px;
    }
    #sidebar-control-panel .live-row {
        display: flex;
        align-items: center;
        margin-bottom: 8px;
    }
    #sidebar-control-panel .status-dot {
        width: 8px;
        height: 8px;
        background: #00ff88;
        border-radius: 50%;
        margin-right: 8px;
        box-shadow: 0 0 8px #00ff88;
        animation: pulse 1.5s ease-in-out infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    #sidebar-control-panel .live-text {
        color: #00ff88;
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 0.75rem;
        letter-spacing: 1px;
    }
    #sidebar-control-panel .clock {
        color: #00ffff;
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 1.6rem;
        text-shadow: 0 0 10px rgba(0, 255, 255, 0.4);
    }
    #sidebar-control-panel .date {
        color: #7a8899;
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.85rem;
        margin-bottom: 12px;
    }
    #sidebar-control-panel .update-box {
        background: rgba(0, 255, 255, 0.08);
        border: 1px solid rgba(0, 255, 255, 0.2);
        border-radius: 8px;
        padding: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    #sidebar-control-panel .update-left {
        text-align: left;
    }
    #sidebar-control-panel .update-label {
        color: #7a8899;
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    #sidebar-control-panel .update-time {
        color: #00ffff;
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 1rem;
    }
    #sidebar-control-panel .countdown-box {
        text-align: right;
    }
    #sidebar-control-panel .countdown-label {
        color: #7a8899;
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    #sidebar-control-panel .countdown {
        color: #ffc107;
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 1rem;
    }
</style>
<div class="control-panel">
    <div class="live-row">
        <span class="status-dot"></span>
        <span class="live-text">LIVE</span>
    </div>
    <div class="clock" id="clock">--:--:--</div>
    <div class="date" id="date">--/--/----</div>
    <div class="update-box">
        <div class="update-left">
            <div class="update-label">Next Update</div>
            <div class="update-time" id="nextUpdate">--:--</div>
        </div>
        <div class="countdown-box">
            <div class="countdown-label">Remaining</div>
            <div class="countdown" id="countdown">--:--</div>
        </div>
    </div>
</div>
<script>
    function updateClock() {
        const now = new Date();
        const options = { timeZone: 'Europe/Rome' };
        const timeStr = now.toLocaleTimeString('en-GB', { ...options, hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const dateStr = now.toLocaleDateString('en-GB', { ...options, day: '2-digit', month: '2-digit', year: 'numeric' });
        
        // Scope queries to this component to avoid collisions with other IDs
        const root = document.getElementById('sidebar-control-panel');
        if (!root) return;
        root.querySelector('#clock').textContent = timeStr;
        root.querySelector('#date').textContent = dateStr;
        
        // Calculate next 15-minute interval
        const romeTime = new Date(now.toLocaleString('en-US', { timeZone: 'Europe/Rome' }));
        const minutes = romeTime.getMinutes();
        const seconds = romeTime.getSeconds();
        
        const nextUpdate = Math.ceil((minutes + 1) / 15) * 15;
        const nextHour = romeTime.getHours() + (nextUpdate >= 60 ? 1 : 0);
        const nextMin = nextUpdate >= 60 ? 0 : nextUpdate;
        
        root.querySelector('#nextUpdate').textContent = 
            String(nextHour % 24).padStart(2, '0') + ':' + String(nextMin).padStart(2, '0');
        
        // Calculate countdown
        let minutesLeft = (nextUpdate >= 60 ? 60 : nextUpdate) - minutes - 1;
        let secondsLeft = 60 - seconds;
        if (secondsLeft === 60) {
            secondsLeft = 0;
            minutesLeft += 1;
        }
        if (minutesLeft < 0) minutesLeft = 14;
        
        const countdownStr = '-' + String(minutesLeft).padStart(2, '0') + ':' + String(secondsLeft).padStart(2, '0');
        root.querySelector('#countdown').textContent = countdownStr;
    }
    
    updateClock();
    setInterval(updateClock, 1000);
</script>
</div>
"""


def render_control_panel():
    """Render the live clock control panel"""
    st.markdown("## ⚡ Control Panel")
    components.html(CONTROL_PANEL_HTML, height=210)


def render_sidebar():
    """Render the complete sidebar"""
    render_control_panel()
