"""
Dark Theme CSS for the Crypto Dashboard - Neon Cyberpunk Style
"""

import streamlit as st

DARK_THEME_CSS = """
<style>
    /* Import fonts */
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');
    
    /* Animated background */
    .stApp {
        background: linear-gradient(135deg, #0a0a1a 0%, #0d1117 50%, #0a0a1a 100%);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
        color: #ffffff;
        font-family: 'Rajdhani', sans-serif;
    }
    
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Sidebar with glass effect */
    section[data-testid="stSidebar"] {
        background: rgba(15, 15, 35, 0.95);
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(0, 255, 255, 0.2);
        box-shadow: 5px 0 30px rgba(0, 255, 255, 0.1);
    }
    
    section[data-testid="stSidebar"] * {
        color: #e0e0ff !important;
    }
    
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #00ffff !important;
        font-family: 'Orbitron', sans-serif;
        text-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
        font-weight: 700;
    }
    
    /* Glowing Header Card */
    .header-card {
        background: linear-gradient(135deg, rgba(0, 100, 255, 0.3) 0%, rgba(0, 255, 255, 0.2) 50%, rgba(0, 255, 100, 0.3) 100%);
        border: 2px solid transparent;
        border-image: linear-gradient(135deg, #00f0ff, #00ff88, #ff00ff) 1;
        padding: 35px;
        border-radius: 20px;
        margin-bottom: 30px;
        text-align: center;
        position: relative;
        overflow: hidden;
        box-shadow: 
            0 0 30px rgba(0, 255, 255, 0.3),
            0 0 60px rgba(0, 255, 255, 0.1),
            inset 0 0 30px rgba(0, 255, 255, 0.1);
    }
    
    .header-card::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(
            45deg,
            transparent,
            transparent 40%,
            rgba(0, 255, 255, 0.1) 50%,
            transparent 60%,
            transparent
        );
        animation: shine 3s infinite;
    }
    
    @keyframes shine {
        0% { transform: translateX(-100%) rotate(45deg); }
        100% { transform: translateX(100%) rotate(45deg); }
    }
    
    .header-card h1 {
        color: #ffffff !important;
        font-size: 3rem;
        font-weight: 900;
        font-family: 'Orbitron', sans-serif;
        margin: 0;
        text-shadow: 
            0 0 10px #00ffff,
            0 0 20px #00ffff,
            0 0 40px #00ffff;
        letter-spacing: 3px;
    }
    
    .header-card p {
        color: #00ffff;
        font-size: 1.2rem;
        margin-top: 15px;
        font-weight: 500;
        text-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
    }
    
    /* Neon Metric Cards */
    [data-testid="metric-container"] {
        background: rgba(10, 15, 30, 0.8);
        border: 1px solid rgba(0, 255, 255, 0.3);
        border-radius: 15px;
        padding: 20px 25px;
        box-shadow: 
            0 0 20px rgba(0, 255, 255, 0.15),
            inset 0 0 20px rgba(0, 255, 255, 0.05);
        transition: all 0.3s ease;
        backdrop-filter: blur(5px);
    }
    
    [data-testid="metric-container"]:hover {
        border-color: rgba(0, 255, 255, 0.6);
        box-shadow: 
            0 0 30px rgba(0, 255, 255, 0.3),
            inset 0 0 30px rgba(0, 255, 255, 0.1);
        transform: translateY(-3px);
    }
    
    [data-testid="metric-container"] label {
        color: #8899aa !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-family: 'Rajdhani', sans-serif;
    }
    
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #00ffff !important;
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        font-family: 'Orbitron', sans-serif;
        text-shadow: 0 0 15px rgba(0, 255, 255, 0.5);
    }
    
    [data-testid="metric-container"] [data-testid="stMetricDelta"] {
        font-size: 1.1rem !important;
        text-shadow: 0 0 10px currentColor;
    }
    
    /* Text styling - FORZA BIANCO */
    .stMarkdown, .stText, p, span, label, div {
        color: #ffffff !important;
        font-family: 'Rajdhani', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
        font-family: 'Orbitron', sans-serif;
        text-shadow: 0 0 10px rgba(0, 255, 255, 0.3);
    }
    
    /* Forza bianco su tutto il testo */
    * {
        color: #ffffff;
    }
    
    /* Caption e small text */
    .stCaption, small, .caption {
        color: #aabbcc !important;
    }
    
    /* Neon Selectbox */
    .stSelectbox > div > div {
        background: rgba(15, 20, 40, 0.95) !important;
        border: 1px solid rgba(0, 255, 255, 0.3);
        border-radius: 10px;
        color: #ffffff !important;
        transition: all 0.3s ease;
    }
    
    .stSelectbox > div > div:hover {
        border-color: rgba(0, 255, 255, 0.6);
        box-shadow: 0 0 15px rgba(0, 255, 255, 0.2);
    }
    
    .stSelectbox label {
        color: #8899aa !important;
        font-family: 'Rajdhani', sans-serif;
        font-weight: 600;
    }
    
    /* Dropdown menu styling */
    .stSelectbox [data-baseweb="select"] > div {
        background: rgba(15, 20, 40, 0.98) !important;
        color: #ffffff !important;
    }
    
    .stSelectbox [data-baseweb="popover"] {
        background: rgba(15, 20, 40, 0.98) !important;
    }
    
    .stSelectbox [data-baseweb="menu"] {
        background: rgba(15, 20, 40, 0.98) !important;
    }
    
    .stSelectbox li {
        background: rgba(15, 20, 40, 0.98) !important;
        color: #ffffff !important;
    }
    
    .stSelectbox li:hover {
        background: rgba(0, 255, 255, 0.2) !important;
    }
    
    /* BaseWeb select dropdown */
    [data-baseweb="popover"] {
        background: #0d1117 !important;
    }
    
    [data-baseweb="menu"] {
        background: #0d1117 !important;
    }
    
    [data-baseweb="menu"] li {
        background: #0d1117 !important;
        color: #ffffff !important;
    }
    
    [data-baseweb="menu"] li:hover {
        background: rgba(0, 255, 255, 0.15) !important;
    }
    
    /* Text Input styling */
    .stTextInput input {
        background: rgba(15, 20, 40, 0.95) !important;
        color: #ffffff !important;
        border: 1px solid rgba(0, 255, 255, 0.3) !important;
    }
    
    .stTextInput input::placeholder {
        color: #6688aa !important;
    }
    
    /* Glowing Buttons */
    .stButton > button {
        background: linear-gradient(135deg, rgba(0, 100, 255, 0.8) 0%, rgba(0, 200, 255, 0.8) 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 14px 28px;
        font-weight: 700;
        font-family: 'Orbitron', sans-serif;
        letter-spacing: 1px;
        transition: all 0.3s ease;
        box-shadow: 
            0 0 20px rgba(0, 150, 255, 0.4),
            inset 0 0 20px rgba(255, 255, 255, 0.1);
        text-shadow: 0 0 10px rgba(255, 255, 255, 0.5);
    }
    
    .stButton > button:hover {
        transform: translateY(-3px) scale(1.02);
        box-shadow: 
            0 0 40px rgba(0, 200, 255, 0.6),
            inset 0 0 30px rgba(255, 255, 255, 0.2);
    }
    
    /* Cyberpunk Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background: rgba(10, 15, 30, 0.8);
        padding: 12px;
        border-radius: 15px;
        border: 1px solid rgba(0, 255, 255, 0.2);
    }
    
    .stTabs [data-baseweb="tab"] {
        background: rgba(20, 30, 60, 0.6);
        border-radius: 10px;
        padding: 14px 28px;
        color: #8899aa;
        font-weight: 600;
        font-family: 'Rajdhani', sans-serif;
        transition: all 0.3s ease;
        border: 1px solid transparent;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(0, 255, 255, 0.1);
        border-color: rgba(0, 255, 255, 0.3);
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(0, 100, 255, 0.8) 0%, rgba(0, 200, 255, 0.8) 100%) !important;
        color: white !important;
        box-shadow: 0 0 20px rgba(0, 200, 255, 0.5);
        text-shadow: 0 0 10px rgba(255, 255, 255, 0.5);
    }
    
    /* Neon Signal Boxes */
    .success-box {
        background: linear-gradient(135deg, rgba(0, 200, 100, 0.3) 0%, rgba(0, 255, 150, 0.2) 100%);
        border: 1px solid #00ff88;
        color: #00ff88;
        padding: 18px 25px;
        border-radius: 12px;
        margin: 15px 0;
        font-weight: 600;
        box-shadow: 0 0 20px rgba(0, 255, 136, 0.2);
        text-shadow: 0 0 10px rgba(0, 255, 136, 0.5);
    }
    
    .warning-box {
        background: linear-gradient(135deg, rgba(255, 180, 0, 0.3) 0%, rgba(255, 200, 50, 0.2) 100%);
        border: 1px solid #ffc107;
        color: #ffc107;
        padding: 18px 25px;
        border-radius: 12px;
        margin: 15px 0;
        box-shadow: 0 0 20px rgba(255, 193, 7, 0.2);
    }
    
    .info-box {
        background: linear-gradient(135deg, rgba(0, 100, 255, 0.3) 0%, rgba(0, 200, 255, 0.2) 100%);
        border: 1px solid #00d4ff;
        color: #00d4ff;
        padding: 18px 25px;
        border-radius: 12px;
        margin: 15px 0;
        box-shadow: 0 0 20px rgba(0, 212, 255, 0.2);
    }
    
    /* DataFrame with dark theme */
    .stDataFrame {
        border: 1px solid rgba(0, 255, 255, 0.3);
        border-radius: 12px;
        box-shadow: 0 0 20px rgba(0, 255, 255, 0.1);
    }
    
    .stDataFrame > div {
        background-color: #0a0a1a !important;
    }
    
    /* DataFrame table styling */
    .stDataFrame table {
        background-color: #0d1117 !important;
        color: #e0e0ff !important;
    }
    
    .stDataFrame thead tr th {
        background-color: #161b26 !important;
        color: #00ffff !important;
        border-bottom: 2px solid rgba(0, 255, 255, 0.3) !important;
        font-family: 'Rajdhani', sans-serif !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
    }
    
    .stDataFrame tbody tr td {
        background-color: #0d1117 !important;
        color: #d0d0e0 !important;
        border-bottom: 1px solid rgba(0, 255, 255, 0.1) !important;
    }
    
    .stDataFrame tbody tr:hover td {
        background-color: rgba(0, 255, 255, 0.1) !important;
    }
    
    .stDataFrame tbody tr:nth-child(even) td {
        background-color: #0a0e14 !important;
    }
    
    /* DataEditor / Data Table styling */
    [data-testid="stDataFrame"] > div > div {
        background-color: #0d1117 !important;
    }
    
    [data-testid="stDataFrame"] [data-testid="glideDataEditor"] {
        background-color: #0d1117 !important;
    }
    
    /* Glide Data Grid cells */
    .dvn-scroller {
        background-color: #0d1117 !important;
    }
    
    /* Header cells */
    .gdg-header {
        background-color: #161b26 !important;
        color: #00ffff !important;
    }
    
    /* Data cells */
    .gdg-cell {
        background-color: #0d1117 !important;
        color: #d0d0e0 !important;
    }
    
    /* Glowing dividers */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #00ffff, transparent);
        box-shadow: 0 0 10px rgba(0, 255, 255, 0.3);
    }
    
    /* Footer with glow */
    .footer-text {
        text-align: center;
        color: #6688aa;
        padding: 30px;
        font-size: 0.95rem;
        font-family: 'Rajdhani', sans-serif;
    }
    
    /* Pulsing live indicator */
    .status-live {
        display: inline-block;
        width: 12px;
        height: 12px;
        background: #00ff88;
        border-radius: 50%;
        margin-right: 10px;
        box-shadow: 0 0 10px #00ff88, 0 0 20px #00ff88;
        animation: neonPulse 1.5s ease-in-out infinite;
    }
    
    @keyframes neonPulse {
        0%, 100% { 
            box-shadow: 0 0 5px #00ff88, 0 0 10px #00ff88, 0 0 20px #00ff88;
            transform: scale(1);
        }
        50% { 
            box-shadow: 0 0 10px #00ff88, 0 0 25px #00ff88, 0 0 40px #00ff88;
            transform: scale(1.1);
        }
    }
    
    /* Floating particles effect on inputs */
    .stTextInput > div > div {
        background: rgba(15, 20, 40, 0.9);
        border: 1px solid rgba(0, 255, 255, 0.3);
        border-radius: 10px;
        transition: all 0.3s ease;
    }
    
    .stTextInput > div > div:focus-within {
        border-color: #00ffff;
        box-shadow: 0 0 20px rgba(0, 255, 255, 0.3);
    }
    
    /* Checkbox neon style */
    .stCheckbox label {
        color: #d0d0e0 !important;
        font-family: 'Rajdhani', sans-serif;
    }
    
    /* Hide Streamlit branding only */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Keep header but make it minimal and dark */
    header[data-testid="stHeader"] {
        background: #0a0a1a !important;
        border-bottom: 1px solid rgba(0, 255, 255, 0.2) !important;
        height: 50px !important;
        min-height: 50px !important;
    }
    
    /* Style the sidebar toggle button */
    [data-testid="collapsedControl"] {
        background: rgba(0, 255, 255, 0.2) !important;
        border: 2px solid rgba(0, 255, 255, 0.5) !important;
        border-radius: 10px !important;
        margin: 8px !important;
    }
    
    [data-testid="collapsedControl"] svg {
        fill: #00ffff !important;
        color: #00ffff !important;
    }
    
    [data-testid="collapsedControl"]:hover {
        background: rgba(0, 255, 255, 0.4) !important;
        box-shadow: 0 0 15px rgba(0, 255, 255, 0.3) !important;
    }
    
    /* Ensure sidebar is visible */
    section[data-testid="stSidebar"] {
        display: block !important;
        visibility: visible !important;
    }
    
    /* Remove extra top padding from main content */
    .main .block-container {
        padding-top: 1rem !important;
    }
    
    /* Neon scrollbar */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    ::-webkit-scrollbar-track {
        background: rgba(10, 15, 30, 0.8);
    }
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #00ffff, #0088ff);
        border-radius: 5px;
        box-shadow: 0 0 10px rgba(0, 255, 255, 0.3);
    }
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(180deg, #00ffff, #00ff88);
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background: rgba(15, 20, 40, 0.8);
        border: 1px solid rgba(0, 255, 255, 0.2);
        border-radius: 10px;
        color: #00ffff !important;
        font-family: 'Rajdhani', sans-serif;
    }
    
    .streamlit-expanderHeader:hover {
        border-color: rgba(0, 255, 255, 0.5);
        box-shadow: 0 0 15px rgba(0, 255, 255, 0.2);
    }
</style>
"""


def inject_theme():
    """Inject the dark theme CSS into the Streamlit app"""
    st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)
