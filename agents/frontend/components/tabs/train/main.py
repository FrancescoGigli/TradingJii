"""
🎓 Train Tab - Main Entry Point

Unified ML training pipeline with 4 steps:
1. Data - Fetch and clean historical data
2. Labeling - Generate trailing stop labels  
3. Training - Train XGBoost models
4. Models - View and manage trained models
"""

import streamlit as st

from .data import render_data_step
from .labeling import render_labeling_step
from .training import render_training_step
from .models import render_models_step


def render_train_tab():
    """Main render function for Train tab"""

    # Header
    st.markdown("## 🎓 ML Training Pipeline")
    st.caption("Data → Labeling → Training → Models")
    
    # Info box
    with st.expander("ℹ️ How the Training Pipeline Works", expanded=False):
        st.markdown("""
        ### Training Pipeline Overview
        
        This tab guides you through the complete ML training process:
        
        **1️⃣ Data**
        - Fetch OHLCV data from Bybit (12 months: 2025-01-01 → 2026-01-01)
        - Calculate 64 technical indicators
        - Clean data (remove warm-up period with NULLs)
        - Align timestamps between 15m and 1h
        
        **2️⃣ Labeling**
        - Generate training labels using Trailing Stop simulation
        - Formula: `score = R - λ*log(1+D) - costs`
        - Labels use FUTURE data (lookahead) - only for training!
        - Remove last N rows without valid labels
        
        **3️⃣ Training**
        - Train XGBoost models (LONG + SHORT)
        - Manual mode: Set hyperparameters yourself
        - Optuna mode: Automatic hyperparameter optimization
        
        **4️⃣ Models**
        - View trained models and metrics
        - Compare Spearman correlation, Precision@K
        - Delete old models
        """)
    
    st.divider()
    
    # === SUB-TABS ===
    tab_data, tab_labeling, tab_training, tab_models = st.tabs([
        "📊 1. Data",
        "🏷️ 2. Labeling",
        "🚀 3. Training",
        "📈 4. Models"
    ])
    
    with tab_data:
        render_data_step()
    
    with tab_labeling:
        render_labeling_step()
    
    with tab_training:
        render_training_step()
    
    with tab_models:
        render_models_step()


__all__ = ['render_train_tab']
