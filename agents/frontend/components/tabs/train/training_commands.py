"""
🚀 Training Commands Section

Displays the training commands for different scenarios:
- Single timeframe training
- Multi-frame training
- Optuna intensive training
"""

import streamlit as st


# Color scheme (dark theme)
COLORS = {
    'primary': '#00ffff',
    'secondary': '#ff6b6b',
    'success': '#4ade80',
    'warning': '#fbbf24',
    'background': '#0d1117',
    'card': '#1e2130',
    'text': '#e0e0ff',
    'muted': '#9ca3af',
    'border': '#2d3748'
}


def render_training_commands_section():
    """Render the training commands section."""
    st.markdown("### 🚀 Training Commands")
    st.caption("Run these commands in terminal to train models locally")
    
    # Main container with styled background
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {COLORS['card']}, {COLORS['background']});
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
    ">
        <div style="color: {COLORS['muted']}; margin-bottom: 12px; font-size: 0.9em;">
            ⚡ No Docker required - Trains directly on your machine for faster performance
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Three columns for three command types
    col1, col2, col3 = st.columns(3)
    
    # === SINGLE TRAINING ===
    with col1:
        _render_command_card(
            title="🔵 Single Training (15m)",
            description="Train one model for 15-minute timeframe",
            command="python train_local.py --timeframe 15m --trials 30",
            color="#60a5fa",
            badge="Basic"
        )
    
    # === MULTI-FRAME TRAINING ===
    with col2:
        _render_command_card(
            title="🟢 Multi-Frame Training",
            description="Train models for both 15m and 1h timeframes",
            command="python train_local.py --timeframe 15m --trials 30\npython train_local.py --timeframe 1h --trials 30",
            color="#4ade80",
            badge="Recommended"
        )
    
    # === OPTUNA INTENSIVE ===
    with col3:
        _render_command_card(
            title="🟡 Optuna Intensive",
            description="More trials for better hyperparameter optimization",
            command="python train_local.py --timeframe 15m --trials 50 --verbose",
            color="#fbbf24",
            badge="Advanced"
        )
    
    # Options explanation
    with st.expander("⚙️ Command Options Explained", expanded=False):
        _render_options_table()


def _render_command_card(
    title: str,
    description: str,
    command: str,
    color: str,
    badge: str
):
    """Render a styled command card."""
    st.markdown(f"""
    <div style="
        background: {COLORS['background']};
        border: 1px solid {color};
        border-radius: 10px;
        padding: 16px;
        height: 100%;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <span style="color: {color}; font-weight: bold; font-size: 1em;">
                {title}
            </span>
            <span style="
                background: {color}22;
                color: {color};
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 0.75em;
            ">{badge}</span>
        </div>
        <div style="color: {COLORS['muted']}; font-size: 0.85em; margin-bottom: 12px;">
            {description}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Code block (Streamlit native for copy functionality)
    st.code(command, language="bash")


def _render_options_table():
    """Render the options explanation table."""
    st.markdown(f"""
    <div style="background: {COLORS['background']}; border-radius: 8px; padding: 15px;">
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="border-bottom: 1px solid {COLORS['border']};">
                    <th style="text-align: left; padding: 10px; color: {COLORS['primary']};">Option</th>
                    <th style="text-align: left; padding: 10px; color: {COLORS['primary']};">Values</th>
                    <th style="text-align: left; padding: 10px; color: {COLORS['primary']};">Description</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid {COLORS['border']};">
                    <td style="padding: 10px; color: {COLORS['text']}; font-family: monospace;">--timeframe</td>
                    <td style="padding: 10px; color: {COLORS['muted']};">15m, 1h</td>
                    <td style="padding: 10px; color: {COLORS['text']};">Candle timeframe to train on</td>
                </tr>
                <tr style="border-bottom: 1px solid {COLORS['border']};">
                    <td style="padding: 10px; color: {COLORS['text']}; font-family: monospace;">--trials</td>
                    <td style="padding: 10px; color: {COLORS['muted']};">10-100 (default: 20)</td>
                    <td style="padding: 10px; color: {COLORS['text']};">Number of Optuna optimization trials</td>
                </tr>
                <tr style="border-bottom: 1px solid {COLORS['border']};">
                    <td style="padding: 10px; color: {COLORS['text']}; font-family: monospace;">--train-ratio</td>
                    <td style="padding: 10px; color: {COLORS['muted']};">0.7-0.9 (default: 0.8)</td>
                    <td style="padding: 10px; color: {COLORS['text']};">Train/test split ratio</td>
                </tr>
                <tr style="border-bottom: 1px solid {COLORS['border']};">
                    <td style="padding: 10px; color: {COLORS['text']}; font-family: monospace;">--verbose</td>
                    <td style="padding: 10px; color: {COLORS['muted']};">flag</td>
                    <td style="padding: 10px; color: {COLORS['text']};">Show detailed output for each trial</td>
                </tr>
                <tr>
                    <td style="padding: 10px; color: {COLORS['text']}; font-family: monospace;">--output-dir</td>
                    <td style="padding: 10px; color: {COLORS['muted']};">path</td>
                    <td style="padding: 10px; color: {COLORS['text']};">Custom output directory (default: shared/models)</td>
                </tr>
            </tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)
    
    # Tips
    st.markdown(f"""
    <div style="
        background: {COLORS['card']};
        border-left: 4px solid {COLORS['warning']};
        padding: 12px 16px;
        margin-top: 15px;
        border-radius: 4px;
    ">
        <span style="color: {COLORS['warning']}; font-weight: bold;">💡 Tips:</span>
        <ul style="color: {COLORS['text']}; margin: 8px 0 0 0; padding-left: 20px;">
            <li>Start with <code style="background: {COLORS['border']}; padding: 2px 6px; border-radius: 4px;">--trials 20</code> for quick tests</li>
            <li>Use <code style="background: {COLORS['border']}; padding: 2px 6px; border-radius: 4px;">--trials 50+</code> for production models</li>
            <li>Training typically takes 2-10 minutes depending on trials</li>
            <li>Models are saved with timestamps for version tracking</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)


__all__ = ['render_training_commands_section']
