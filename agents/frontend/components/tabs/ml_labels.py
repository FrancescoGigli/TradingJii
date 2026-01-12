"""
🎯 ML Labels Tab - Main Entry Point

This tab is organized into sub-modules for better maintainability:
- generator.py: Generate labels for ALL coins (batch processing)
- explorer.py: Database Explorer with SQL queries
- visualization.py: Single coin visualization

IMPORTANT: Labels use FUTURE data - for TRAINING only!
"""

import streamlit as st

# Import sub-modules
from .ml.generator import render_generate_all_labels
from .ml.explorer import render_database_explorer
from .ml.visualization import render_single_coin_visualization
from .ml.export import render_export_dataset


def render_ml_labels_tab():
    """Render the ML Labels tab with sub-tabs"""
    
    # Header
    st.markdown("## 🎯 ML Training Labels")
    st.caption("Generate • Explore • Visualize ML Training Labels")
    
    # Info box
    with st.expander("ℹ️ About ML Labels", expanded=False):
        st.markdown("""
        ### How Training Labels Work
        
        **Formula:** `score = R - λ*log(1+D) - costs`
        
        Where:
        - **R** = Return realized from trailing stop (not MFE!)
        - **D** = Bars held until exit
        - **λ** = Time penalty coefficient
        - **costs** = Trading fees
        
        **⚠️ IMPORTANT:**
        - Labels use **FUTURE** data (lookahead)
        - They are **ONLY** for ML model training
        - **NEVER** use them as model input!
        
        ### Tab Organization
        
        1. **🚀 Generate**: Generate labels for ALL coins with auto-save
        2. **🗄️ Explorer**: Query and browse labels with SQL
        3. **📊 Visualize**: Explore labels for a single coin
        """)
    
    st.divider()
    
    # === SUB-TABS ===
    tab_generate, tab_explorer, tab_export, tab_visualize = st.tabs([
        "🚀 Generate",
        "🗄️ Explorer", 
        "📦 Export",
        "📊 Visualize"
    ])
    
    with tab_generate:
        render_generate_all_labels()
    
    with tab_explorer:
        render_database_explorer()
    
    with tab_export:
        render_export_dataset()
    
    with tab_visualize:
        render_single_coin_visualization()


# Export
__all__ = ['render_ml_labels_tab']
