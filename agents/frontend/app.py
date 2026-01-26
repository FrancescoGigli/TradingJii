"""
📊 Crypto Dashboard - Advanced Dark Theme

Dashboard for visualizing crypto data with:
- Top 100 Coins with analysis
- Backtest strategies
- ML Training pipeline

Entry point for the application.
"""

import streamlit as st

from config import PAGE_TITLE, PAGE_ICON
from styles import inject_theme
from components.sidebar import render_sidebar
from components.tabs import (
    render_top_coins_tab,
    render_backtest_tab,
    render_train_tab
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

# Inject dark theme CSS
inject_theme()


# ============================================================
# MAIN APP
# ============================================================
def main():
    """Main application entry point"""

    # Sidebar
    with st.sidebar:
        render_sidebar()

    # Persistent header bar with Balance/Sentiment/Services
    try:
        from components.header import render_header_bar
        render_header_bar()
    except Exception:
        # Fallback: continue if header fails
        pass

    # Main content - 3 TABS
    tab1, tab2, tab3 = st.tabs([
        "📊 Top 100 Coins",
        "🔄 Test",
        "🎓 ML"
    ])

    with tab1:
        render_top_coins_tab()

    with tab2:
        render_backtest_tab()

    with tab3:
        render_train_tab()


if __name__ == "__main__":
    main()
