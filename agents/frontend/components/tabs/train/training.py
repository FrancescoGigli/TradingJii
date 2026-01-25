"""
🚀 Train Tab - Step 3: Training Dashboard

Redesigned training interface with 5 sections:
1. Input/Output Data Tables with status
2. Training Commands (single, multi-frame, optuna)
3. Last Trained Model Details & Metrics
4. AI Evaluation (OpenAI GPT-4o)
5. Bitcoin Inference Chart (200 candles)
"""

import streamlit as st

# Import sub-components
from .training_io_tables import render_io_tables_section
from .training_commands import render_training_commands_section
from .training_model_details import render_model_details_section
from .training_ai_eval import render_ai_evaluation_section
from .training_btc_inference import render_btc_inference_section


def render_training_step():
    """Render Step 3: Training Dashboard with all sections."""
    st.markdown("### 🚀 Step 3: Training Dashboard")
    st.caption("Train models locally - View results, metrics, and AI analysis")
    
    # === SECTION 1: Input/Output Tables ===
    render_io_tables_section()
    
    st.divider()
    
    # === SECTION 2: Training Commands ===
    render_training_commands_section()
    
    st.divider()
    
    # === SECTION 3: Model Details & Metrics ===
    render_model_details_section()
    
    st.divider()
    
    # === SECTION 4: AI Evaluation ===
    render_ai_evaluation_section()
    
    st.divider()
    
    # === SECTION 5: Bitcoin Inference ===
    render_btc_inference_section()


__all__ = ['render_training_step']
