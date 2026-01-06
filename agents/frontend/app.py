"""
📊 Crypto Dashboard Pro - Advanced Dark Theme

Dashboard avanzata per visualizzare dati crypto
Con Tab per Top 100 Coins, Charts, Volume Analysis, Technical Indicators e Backtest

Entry point principale dell'applicazione.
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from config import PAGE_TITLE, PAGE_ICON
from styles import inject_theme
from components.sidebar import render_sidebar
from components.tabs import (
    render_top_coins_tab,
    render_analysis_tab,
    render_backtest_tab
)


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Auto-refresh every 30 seconds to check for database updates
# The counter increments on each refresh - we can use it to track refreshes
refresh_count = st_autorefresh(interval=30000, limit=None, key="data_refresh")

# Inject dark theme CSS
inject_theme()


# ============================================================
# HEADER HTML
# ============================================================
HEADER_HTML = """
<div class="header-card">
    <h1>📈 Crypto Dashboard Pro</h1>
    <p>Top 100 Cryptocurrencies • Real-time Analysis • Technical Indicators</p>
</div>
"""

FOOTER_HTML = """
<p class="footer-text">
    🚀 Crypto Dashboard Pro | Built with Streamlit & Plotly | Data from Bybit | Updates every 15 minutes<br>
    <small>© 2024 - Real-time cryptocurrency analysis</small>
</p>
"""


# ============================================================
# MAIN APP
# ============================================================
def main():
    """Main application entry point"""
    
    # Header
    st.markdown(HEADER_HTML, unsafe_allow_html=True)
    
    # Persistent header bar with Balance/Sentiment/Services
    try:
        from components.header import render_header_bar
        render_header_bar()
    except Exception as e:
        # Fallback: show simple metrics if header fails
        pass
    
    # Sidebar
    with st.sidebar:
        render_sidebar()
    
    # Main content - TABS
    tab1, tab2, tab3 = st.tabs([
        "📊 Top 100 Coins", 
        "📈 Coin Analysis",
        "🔄 Backtest"
    ])
    
    with tab1:
        render_top_coins_tab()
    
    with tab2:
        render_analysis_tab()
    
    with tab3:
        render_backtest_tab()
    
    # Footer
    st.markdown(FOOTER_HTML, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
