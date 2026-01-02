"""
Dark Theme CSS for the Crypto Dashboard - Neon Cyberpunk Style
Uses centralized colors from colors.py
"""

import streamlit as st
from .colors import PALETTE, CHART_COLORS, rgba


def _generate_css() -> str:
    """Generate CSS using centralized color palette"""
    
    # Shortcuts for commonly used colors
    bg_p = PALETTE['bg_primary']
    bg_s = PALETTE['bg_secondary']
    bg_t = PALETTE['bg_tertiary']
    bg_card = PALETTE['bg_card']
    bg_input = PALETTE['bg_input']
    
    text_p = PALETTE['text_primary']
    text_s = PALETTE['text_secondary']
    text_m = PALETTE['text_muted']
    
    cyan = PALETTE['accent_cyan']
    green = PALETTE['accent_green']
    red = PALETTE['accent_red']
    yellow = PALETTE['accent_yellow']
    blue = PALETTE['accent_blue']
    
    border = PALETTE['border_primary']
    border_h = PALETTE['border_hover']
    
    return f"""
<style>
    /* Import fonts */
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');
    
    /* Animated background */
    .stApp {{
        background: linear-gradient(135deg, {bg_p} 0%, {bg_s} 50%, {bg_p} 100%);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
        color: {text_p};
        font-family: 'Rajdhani', sans-serif;
    }}
    
    @keyframes gradientShift {{
        0% {{ background-position: 0% 50%; }}
        50% {{ background-position: 100% 50%; }}
        100% {{ background-position: 0% 50%; }}
    }}
    
    /* Sidebar with glass effect */
    section[data-testid="stSidebar"] {{
        background: rgba(15, 15, 35, 0.95);
        backdrop-filter: blur(10px);
        border-right: 1px solid {border};
        box-shadow: 5px 0 30px {rgba(cyan, 0.1)};
    }}
    
    section[data-testid="stSidebar"] * {{
        color: {text_s} !important;
    }}
    
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {{
        color: {cyan} !important;
        font-family: 'Orbitron', sans-serif;
        text-shadow: 0 0 10px {rgba(cyan, 0.5)};
        font-weight: 700;
    }}
    
    /* Sidebar buttons */
    section[data-testid="stSidebar"] button {{
        background: linear-gradient(135deg, #1a1f2e 0%, #2d3548 100%) !important;
        color: {cyan} !important;
        border: 1px solid {cyan} !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }}
    section[data-testid="stSidebar"] button:hover {{
        background: linear-gradient(135deg, #2d3548 0%, #3d4558 100%) !important;
        box-shadow: 0 0 15px {rgba(cyan, 0.3)} !important;
        transform: translateY(-1px) !important;
    }}
    section[data-testid="stSidebar"] button:disabled {{
        background: linear-gradient(135deg, #333 0%, #444 100%) !important;
        color: #666 !important;
        border: 1px solid #555 !important;
    }}
    
    /* Glowing Header Card */
    .header-card {{
        background: linear-gradient(135deg, {rgba(blue, 0.3)} 0%, {rgba(cyan, 0.2)} 50%, {rgba(green, 0.3)} 100%);
        border: 2px solid transparent;
        border-image: linear-gradient(135deg, {cyan}, {green}, #ff00ff) 1;
        padding: 35px;
        border-radius: 20px;
        margin-bottom: 30px;
        text-align: center;
        position: relative;
        overflow: hidden;
        box-shadow: 
            0 0 30px {rgba(cyan, 0.3)},
            0 0 60px {rgba(cyan, 0.1)},
            inset 0 0 30px {rgba(cyan, 0.1)};
    }}
    
    .header-card h1 {{
        color: {text_p} !important;
        font-size: 3rem;
        font-weight: 900;
        font-family: 'Orbitron', sans-serif;
        margin: 0;
        text-shadow: 0 0 10px {cyan}, 0 0 20px {cyan}, 0 0 40px {cyan};
        letter-spacing: 3px;
    }}
    
    .header-card p {{
        color: {cyan};
        font-size: 1.2rem;
        margin-top: 15px;
        font-weight: 500;
        text-shadow: 0 0 10px {rgba(cyan, 0.5)};
    }}
    
    /* Neon Metric Cards */
    [data-testid="metric-container"] {{
        background: {bg_card};
        border: 1px solid {border};
        border-radius: 15px;
        padding: 20px 25px;
        box-shadow: 0 0 20px {rgba(cyan, 0.15)}, inset 0 0 20px {rgba(cyan, 0.05)};
        transition: all 0.3s ease;
        backdrop-filter: blur(5px);
    }}
    
    [data-testid="metric-container"]:hover {{
        border-color: {border_h};
        box-shadow: 0 0 30px {rgba(cyan, 0.3)}, inset 0 0 30px {rgba(cyan, 0.1)};
        transform: translateY(-3px);
    }}
    
    [data-testid="metric-container"] label {{
        color: {text_m} !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 1.5px;
    }}
    
    [data-testid="metric-container"] [data-testid="stMetricValue"] {{
        color: {cyan} !important;
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        font-family: 'Orbitron', sans-serif;
        text-shadow: 0 0 15px {rgba(cyan, 0.5)};
    }}
    
    /* Text styling */
    .stMarkdown, .stText, p, span, label, div {{
        color: {text_p} !important;
        font-family: 'Rajdhani', sans-serif;
    }}
    
    h1, h2, h3, h4, h5, h6 {{
        color: {text_p} !important;
        font-family: 'Orbitron', sans-serif;
        text-shadow: 0 0 10px {rgba(cyan, 0.3)};
    }}
    
    * {{ color: {text_p}; }}
    
    .stCaption, small, .caption {{
        color: #aabbcc !important;
    }}
    
    /* Neon Selectbox */
    .stSelectbox > div > div {{
        background: {bg_input} !important;
        border: 1px solid {border};
        border-radius: 10px;
        color: {text_p} !important;
        transition: all 0.3s ease;
    }}
    
    .stSelectbox > div > div:hover {{
        border-color: {border_h};
        box-shadow: 0 0 15px {rgba(cyan, 0.2)};
    }}
    
    .stSelectbox label {{
        color: {text_m} !important;
        font-family: 'Rajdhani', sans-serif;
        font-weight: 600;
    }}
    
    /* BaseWeb select dropdown - DARK */
    [data-baseweb="popover"],
    [data-baseweb="popover"] > div,
    [data-baseweb="popover"] > div > div {{
        background: {bg_s} !important;
        background-color: {bg_s} !important;
        border: 1px solid {border} !important;
    }}
    
    [data-baseweb="menu"],
    [data-baseweb="menu"] > div {{
        background: {bg_s} !important;
        background-color: {bg_s} !important;
    }}
    
    [data-baseweb="menu"] li,
    [data-baseweb="menu"] ul li,
    [data-baseweb="listbox"] li,
    [role="listbox"] li,
    [role="option"],
    [data-baseweb="menu"] [role="option"] {{
        background: {bg_s} !important;
        background-color: {bg_s} !important;
        color: {text_p} !important;
    }}
    
    [data-baseweb="menu"] li:hover,
    [role="option"]:hover {{
        background: {rgba(cyan, 0.3)} !important;
        color: {bg_s} !important;
    }}
    
    [role="option"][aria-selected="true"] {{
        background: {rgba(cyan, 0.4)} !important;
        color: {bg_s} !important;
    }}
    
    [data-baseweb="listbox"],
    [role="listbox"] {{
        background: {bg_s} !important;
        border: 1px solid {border} !important;
    }}
    
    /* Text Input */
    .stTextInput input {{
        background: {bg_input} !important;
        color: {text_p} !important;
        border: 1px solid {border} !important;
    }}
    
    /* Glowing Buttons */
    .stButton > button {{
        background: linear-gradient(135deg, {rgba(blue, 0.8)} 0%, {rgba(cyan, 0.8)} 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 14px 28px;
        font-weight: 700;
        font-family: 'Orbitron', sans-serif;
        letter-spacing: 1px;
        transition: all 0.3s ease;
        box-shadow: 0 0 20px {rgba(blue, 0.4)}, inset 0 0 20px {rgba(text_p, 0.1)};
    }}
    
    .stButton > button:hover {{
        transform: translateY(-3px) scale(1.02);
        box-shadow: 0 0 40px {rgba(cyan, 0.6)}, inset 0 0 30px {rgba(text_p, 0.2)};
    }}
    
    /* Cyberpunk Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 10px;
        background: {bg_card};
        padding: 12px;
        border-radius: 15px;
        border: 1px solid {border};
    }}
    
    .stTabs [data-baseweb="tab"] {{
        background: rgba(20, 30, 60, 0.6);
        border-radius: 10px;
        padding: 14px 28px;
        color: {text_m};
        font-weight: 600;
        font-family: 'Rajdhani', sans-serif;
        transition: all 0.3s ease;
        border: 1px solid transparent;
    }}
    
    .stTabs [data-baseweb="tab"]:hover {{
        background: {rgba(cyan, 0.1)};
        border-color: {border};
    }}
    
    .stTabs [aria-selected="true"] {{
        background: linear-gradient(135deg, {rgba(blue, 0.8)} 0%, {rgba(cyan, 0.8)} 100%) !important;
        color: white !important;
        box-shadow: 0 0 20px {rgba(cyan, 0.5)};
    }}
    
    /* DataFrame / Table styling - FORCE DARK */
    .stDataFrame,
    [data-testid="stDataFrame"],
    [data-testid="stDataFrame"] > div,
    [data-testid="stDataFrame"] > div > div,
    [data-testid="stDataFrame"] > div > div > div,
    [data-testid="glideDataEditor"],
    [data-testid="glideDataEditor"] > div {{
        background-color: {bg_s} !important;
        background: {bg_s} !important;
    }}
    
    .stDataFrame table {{
        background-color: {bg_s} !important;
        color: {text_s} !important;
    }}
    
    .stDataFrame thead tr th {{
        background-color: {bg_t} !important;
        color: {cyan} !important;
        border-bottom: 2px solid {border} !important;
    }}
    
    .stDataFrame tbody tr td {{
        background-color: {bg_s} !important;
        color: {text_s} !important;
        border-bottom: 1px solid {rgba(cyan, 0.1)} !important;
    }}
    
    .stDataFrame tbody tr:hover td {{
        background-color: {rgba(cyan, 0.1)} !important;
    }}
    
    /* Glide data grid canvas background */
    .dvn-scroller, .dvn-stack, .dvn-underlay, .dvn-scroll-inner {{
        background-color: {bg_s} !important;
        background: {bg_s} !important;
    }}
    
    [data-testid="stDataFrame"] canvas {{
        background-color: {bg_s} !important;
    }}
    
    [data-testid="stDataFrame"] span,
    [data-testid="stDataFrame"] div {{
        color: {text_s} !important;
    }}
    
    /* Dividers */
    hr {{
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, {cyan}, transparent);
        box-shadow: 0 0 10px {rgba(cyan, 0.3)};
    }}
    
    /* Footer */
    .footer-text {{
        text-align: center;
        color: {text_m};
        padding: 30px;
        font-size: 0.95rem;
    }}
    
    /* Live indicator animation */
    @keyframes neonPulse {{
        0%, 100% {{ 
            box-shadow: 0 0 5px {green}, 0 0 10px {green}, 0 0 20px {green};
            transform: scale(1);
        }}
        50% {{ 
            box-shadow: 0 0 10px {green}, 0 0 25px {green}, 0 0 40px {green};
            transform: scale(1.1);
        }}
    }}
    
    /* Hide Streamlit branding */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    
    /* Header styling */
    header[data-testid="stHeader"] {{
        background: {bg_p} !important;
        border-bottom: 1px solid {border} !important;
        height: 50px !important;
        min-height: 50px !important;
    }}
    
    /* Sidebar toggle */
    [data-testid="collapsedControl"] {{
        background: {rgba(cyan, 0.2)} !important;
        border: 2px solid {border_h} !important;
        border-radius: 10px !important;
    }}
    
    [data-testid="collapsedControl"] svg {{
        fill: {cyan} !important;
        color: {cyan} !important;
    }}
    
    /* Main content padding */
    .main .block-container {{
        padding-top: 1rem !important;
    }}
    
    /* Neon scrollbar */
    ::-webkit-scrollbar {{
        width: 10px;
        height: 10px;
    }}
    ::-webkit-scrollbar-track {{
        background: {bg_card};
    }}
    ::-webkit-scrollbar-thumb {{
        background: linear-gradient(180deg, {cyan}, {blue});
        border-radius: 5px;
        box-shadow: 0 0 10px {rgba(cyan, 0.3)};
    }}
    
    /* Expander */
    .streamlit-expanderHeader {{
        background: {bg_input};
        border: 1px solid {border};
        border-radius: 10px;
        color: {cyan} !important;
    }}
    
    .streamlit-expanderHeader:hover {{
        border-color: {border_h};
        box-shadow: 0 0 15px {rgba(cyan, 0.2)};
    }}
    
    /* Checkbox */
    .stCheckbox label {{
        color: {text_s} !important;
    }}
</style>
"""


DARK_THEME_CSS = _generate_css()


def inject_theme():
    """Inject the dark theme CSS into the Streamlit app"""
    st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)
