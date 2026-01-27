"""Crypto Dashboard - Streamlit frontend entry point.

This module configures logging and warning filters early to keep container logs clean,
then starts the Streamlit UI.
"""

import logging
import os
import warnings


def _configure_runtime_noise_filters() -> None:
    """Reduce noisy logs/warnings in container output.

    This is intentionally done at import time (before the rest of the app runs)
    to ensure it applies to modules imported later.
    """

    # 1) Logging
    # Default to ERROR to hide verbose INFO logs in containers.
    log_level_name = os.environ.get("LOG_LEVEL", "ERROR").upper().strip()
    log_level = getattr(logging, log_level_name, logging.ERROR)
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s:%(name)s:%(message)s",
        force=True,
    )

    # 2) Warnings
    # Sklearn pickle version mismatch warnings (typical in containers).
    try:
        from sklearn.exceptions import InconsistentVersionWarning

        warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
    except Exception:
        pass

    # XGBoost warning triggered when unpickling models created with a different version.
    warnings.filterwarnings(
        "ignore",
        message=r".*If you are loading a serialized model.*older version of XGBoost.*",
        category=UserWarning,
    )


_configure_runtime_noise_filters()


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
