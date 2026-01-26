"""
Top 100 Coins Tab - Main Entry Point.

Orchestrates:
- Coins table (Top 100 list with volume chart)
- Coin analysis (charts, volume, technical indicators)
"""

import streamlit as st

from .coins_table import render_coins_section
from .analysis import render_analysis_section


def render_top_coins_tab():
    """Main render function for Top 100 Coins tab."""
    
    # Render Top 100 coins list
    has_data = render_coins_section()
    
    if not has_data:
        return
    
    # Divider between sections
    st.markdown("---")
    
    # Render coin analysis section (formerly Charts tab)
    render_analysis_section()


__all__ = ['render_top_coins_tab']
