"""
📊 Training I/O Tables Section

Displays Input and Output data tables with status indicators.
Shows v_xgb_training view and model files status.
"""

import streamlit as st
from pathlib import Path
import os
from typing import Dict, Any

from .data_model_display import get_table_info


# Color scheme (dark theme)
COLORS = {
    'primary': '#00ffff',
    'success': '#4ade80',
    'error': '#ef4444',
    'background': '#0d1117',
    'card': '#1e2130',
    'text': '#e0e0ff',
    'muted': '#9ca3af',
    'border': '#2d3748'
}


def _get_models_dir() -> Path:
    """Get the models directory path."""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    return Path(shared_path) / "models"


def _check_model_files(timeframe: str) -> Dict[str, bool]:
    """Check if model files exist for a timeframe."""
    models_dir = _get_models_dir()
    return {
        'model_long': (models_dir / f"model_long_{timeframe}_latest.pkl").exists(),
        'model_short': (models_dir / f"model_short_{timeframe}_latest.pkl").exists(),
        'scaler': (models_dir / f"scaler_{timeframe}_latest.pkl").exists(),
        'metadata': (models_dir / f"metadata_{timeframe}_latest.json").exists(),
    }


def render_io_tables_section():
    """Render the Input/Output tables section."""
    st.markdown("### 📋 Data Tables Status")
    
    col1, col2 = st.columns(2)
    
    # === INPUT TABLE ===
    with col1:
        _render_input_table_card()
    
    # === OUTPUT TABLE ===
    with col2:
        _render_output_table_card()


def _render_input_table_card():
    """Render the input table status card."""
    # Get info about v_xgb_training view
    info = get_table_info('v_xgb_training')
    
    exists = info.get('exists', False)
    status = "✅" if exists else "❌"
    status_color = COLORS['success'] if exists else COLORS['error']
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {COLORS['card']}, {COLORS['background']});
        border: 1px solid {COLORS['border']};
        border-left: 4px solid #60a5fa;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 8px;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="color: #60a5fa; font-weight: bold; font-size: 1.1em;">
                    📥 INPUT TABLE
                </span>
            </div>
            <span style="color: {status_color}; font-size: 1.5em;">{status}</span>
        </div>
        <div style="color: {COLORS['muted']}; margin-top: 8px; font-family: monospace;">
            v_xgb_training (view)
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if exists:
        # Metrics row
        mcol1, mcol2, mcol3 = st.columns(3)
        with mcol1:
            st.metric("Rows", f"{info.get('row_count', 0):,}")
        with mcol2:
            st.metric("Features", info.get('feature_count', 0))
        with mcol3:
            tfs = info.get('timeframes', [])
            st.metric("Timeframes", ", ".join(tfs) if tfs else "N/A")
        
        # Date range
        date_range = info.get('date_range', {})
        if date_range.get('min'):
            st.caption(f"📅 {date_range['min'][:19]} → {date_range['max'][:19]}")
        
        # Features list (expandable)
        with st.expander(f"📋 Features ({info.get('feature_count', 0)})", expanded=False):
            features = info.get('feature_columns', [])
            if features:
                _render_feature_badges(features)
            else:
                st.info("No features found")
        
        # Label columns
        label_cols = info.get('label_columns', [])
        if label_cols:
            with st.expander(f"🏷️ Labels ({len(label_cols)})", expanded=False):
                _render_feature_badges(label_cols, color='#ff6b6b')
    else:
        st.error("⚠️ View not found. Run labeling first.")
        st.code("# Create labels first\npython train_local.py --help", language="bash")


def _render_output_table_card():
    """Render the output models status card."""
    # Check model files for both timeframes
    files_15m = _check_model_files('15m')
    files_1h = _check_model_files('1h')
    
    has_15m = all(files_15m.values())
    has_1h = all(files_1h.values())
    has_any = has_15m or has_1h
    
    status = "✅" if has_any else "❌"
    status_color = COLORS['success'] if has_any else COLORS['error']
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {COLORS['card']}, {COLORS['background']});
        border: 1px solid {COLORS['border']};
        border-left: 4px solid #34d399;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 8px;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="color: #34d399; font-weight: bold; font-size: 1.1em;">
                    📤 OUTPUT MODELS
                </span>
            </div>
            <span style="color: {status_color}; font-size: 1.5em;">{status}</span>
        </div>
        <div style="color: {COLORS['muted']}; margin-top: 8px; font-family: monospace;">
            shared/models/*.pkl
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Model files status
    _render_timeframe_files_status("15m", files_15m)
    _render_timeframe_files_status("1h", files_1h)
    
    if not has_any:
        st.warning("⚠️ No trained models found. Run training to create models.")


def _render_timeframe_files_status(timeframe: str, files: Dict[str, bool]):
    """Render file status for a specific timeframe."""
    all_exist = all(files.values())
    tf_color = '#60a5fa' if timeframe == '15m' else '#4ade80'
    
    with st.expander(
        f"{'🔵' if timeframe == '15m' else '🟢'} {timeframe} Model Files",
        expanded=False
    ):
        for file_name, exists in files.items():
            icon = "✅" if exists else "❌"
            color = COLORS['success'] if exists else COLORS['error']
            st.markdown(f"""
            <div style="
                display: flex;
                justify-content: space-between;
                padding: 6px 10px;
                background: {COLORS['background']};
                border-radius: 4px;
                margin: 4px 0;
            ">
                <span style="color: {COLORS['text']}; font-family: monospace;">
                    {file_name}_{timeframe}_latest.pkl
                </span>
                <span style="color: {color};">{icon}</span>
            </div>
            """, unsafe_allow_html=True)


def _render_feature_badges(features: list, color: str = '#00ffff'):
    """Render feature names as styled badges."""
    badges_html = ""
    for feat in sorted(features):
        badges_html += f"""
        <span style="
            display: inline-block;
            background: {COLORS['border']};
            color: {color};
            padding: 4px 10px;
            border-radius: 6px;
            margin: 4px;
            font-family: monospace;
            font-size: 0.85em;
        ">• {feat}</span>
        """
    
    st.markdown(f"""
    <div style="
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        padding: 10px;
        background: {COLORS['background']};
        border-radius: 8px;
    ">
        {badges_html}
    </div>
    """, unsafe_allow_html=True)


__all__ = ['render_io_tables_section']
