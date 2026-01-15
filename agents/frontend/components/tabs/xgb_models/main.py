"""
🤖 XGBoost Models Tab - Main Entry Point

Main render function that combines training and viewing tabs.
"""

import streamlit as st

from .training import render_training_section
from .viewer import render_models_view_section


def render_xgb_models_tab():
    """Main render function for XGBoost Models tab"""
    
    # Header
    st.markdown("## 🤖 XGBoost Models Dashboard")
    st.caption("Train and evaluate ML models to predict score_long and score_short")
    
    # Create tabs for Training vs Viewing models
    tab_train, tab_view = st.tabs(["🚀 Train New Model", "📊 View Models"])
    
    with tab_train:
        render_training_section()
    
    with tab_view:
        render_models_view_section()


__all__ = ['render_xgb_models_tab']
