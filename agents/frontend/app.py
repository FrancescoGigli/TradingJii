"""
📊 Crypto Dashboard Pro - Advanced Dark Theme

Dashboard avanzata per visualizzare dati crypto
Con Tab per Top 100 Coins, Charts, Volume Analysis e Technical Indicators
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import sqlite3
from pathlib import Path
import os
from datetime import datetime, timedelta
import pytz

# Timezone Roma
ROME_TZ = pytz.timezone('Europe/Rome')
UPDATE_INTERVAL_MINUTES = 15

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Crypto Dashboard Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# DARK THEME CSS - Neon Cyberpunk Style with Effects
# ============================================================
st.markdown("""
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
        background: rgba(15, 20, 40, 0.9);
        border: 1px solid rgba(0, 255, 255, 0.3);
        border-radius: 10px;
        color: #ffffff;
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
    
    /* Hide streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
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
""", unsafe_allow_html=True)

# ============================================================
# DATABASE PATH
# ============================================================
SHARED_PATH = os.getenv("SHARED_DATA_PATH", "/app/shared")
DB_PATH = f"{SHARED_PATH}/data_cache/trading_data.db"
REFRESH_SIGNAL_FILE = f"{SHARED_PATH}/refresh_signal.txt"


# ============================================================
# DATABASE FUNCTIONS
# ============================================================
def get_connection():
    """Connessione database"""
    if not Path(DB_PATH).exists():
        return None
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def get_top_symbols():
    """Lista top symbols con volume"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT symbol, rank, volume_24h, fetched_at 
            FROM top_symbols 
            ORDER BY rank ASC
        ''')
        results = []
        for row in cur.fetchall():
            results.append({
                'symbol': row[0],
                'rank': row[1],
                'volume_24h': row[2],
                'fetched_at': row[3]
            })
        return results
    except:
        return []


def get_symbols():
    """Lista simboli"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute('SELECT DISTINCT symbol FROM ohlcv_data ORDER BY symbol')
        return [r[0] for r in cur.fetchall()]
    except:
        return []


def get_timeframes(symbol):
    """Timeframes per simbolo"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute('SELECT DISTINCT timeframe FROM ohlcv_data WHERE symbol=? ORDER BY timeframe', (symbol,))
        return [r[0] for r in cur.fetchall()]
    except:
        return []


def get_ohlcv(symbol, timeframe, limit=200):
    """Dati OHLCV"""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    try:
        query = '''
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv_data WHERE symbol=? AND timeframe=?
            ORDER BY timestamp DESC LIMIT ?
        '''
        df = pd.read_sql_query(query, conn, params=(symbol, timeframe, limit))
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            df.set_index('timestamp', inplace=True)
        return df
    except:
        return pd.DataFrame()


def get_stats():
    """Statistiche database"""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT timeframe), 
                   COUNT(*), MAX(timestamp)
            FROM ohlcv_data
        ''')
        r = cur.fetchone()
        
        # Top symbols info
        cur.execute('SELECT COUNT(*), MIN(fetched_at) FROM top_symbols')
        top_info = cur.fetchone()
        
        return {
            'symbols': r[0] or 0,
            'timeframes': r[1] or 0,
            'candles': r[2] or 0,
            'updated': r[3],
            'top_count': top_info[0] or 0,
            'top_fetched_at': top_info[1]
        }
    except:
        return {}


def trigger_refresh():
    """Crea file di segnale per triggerare refresh"""
    try:
        Path(REFRESH_SIGNAL_FILE).write_text(datetime.now().isoformat())
        return True
    except Exception as e:
        st.error(f"Errore: {e}")
        return False


def get_rome_time():
    """Restituisce l'orario corrente di Roma"""
    return datetime.now(ROME_TZ)


def format_datetime_rome(dt_str):
    """Converte stringa datetime UTC in orario Roma formattato"""
    if not dt_str:
        return "N/A"
    try:
        # Parse datetime string (formato: 2025-12-23 16:30:00)
        dt = datetime.fromisoformat(dt_str.replace(' ', 'T'))
        # Se non ha timezone, assumiamo UTC
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        # Converti in Roma
        dt_rome = dt.astimezone(ROME_TZ)
        return dt_rome.strftime('%d/%m/%Y %H:%M')
    except:
        return dt_str[:16] if dt_str else "N/A"


def get_next_update_info():
    """Calcola quando sarà il prossimo update e quanto manca"""
    now_rome = get_rome_time()
    
    # Calcola il prossimo intervallo di 15 minuti
    minutes = now_rome.minute
    next_15 = ((minutes // UPDATE_INTERVAL_MINUTES) + 1) * UPDATE_INTERVAL_MINUTES
    
    if next_15 >= 60:
        next_update = now_rome.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        next_update = now_rome.replace(minute=next_15, second=0, microsecond=0)
    
    # Calcola tempo rimanente
    time_remaining = next_update - now_rome
    total_seconds = int(time_remaining.total_seconds())
    
    if total_seconds < 0:
        total_seconds = 0
    
    minutes_left = total_seconds // 60
    seconds_left = total_seconds % 60
    
    return {
        'next_update': next_update.strftime('%H:%M'),
        'minutes_left': minutes_left,
        'seconds_left': seconds_left,
        'countdown': f"{minutes_left:02d}:{seconds_left:02d}"
    }


# ============================================================
# TECHNICAL INDICATORS
# ============================================================
def calculate_rsi(df, period=14):
    """Calcola RSI"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_macd(df, fast=12, slow=26, signal=9):
    """Calcola MACD"""
    ema_fast = df['close'].ewm(span=fast).mean()
    ema_slow = df['close'].ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(df, period=20, std_dev=2):
    """Calcola Bollinger Bands"""
    sma = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


def calculate_atr(df, period=14):
    """Calcola ATR"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_vwap(df):
    """Calcola VWAP"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    return (typical_price * df['volume']).cumsum() / df['volume'].cumsum()


# ============================================================
# CHARTS
# ============================================================
def create_advanced_chart(df, symbol, show_indicators=True):
    """Grafico candlestick avanzato con indicatori"""
    
    rows = 4 if show_indicators else 2
    row_heights = [0.5, 0.15, 0.15, 0.2] if show_indicators else [0.7, 0.3]
    
    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=('', 'RSI', 'MACD', 'Volume') if show_indicators else ('', 'Volume')
    )
    
    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='OHLC',
            increasing=dict(line=dict(color='#00ff88'), fillcolor='#00875a'),
            decreasing=dict(line=dict(color='#ff4757'), fillcolor='#c92a2a'),
        ),
        row=1, col=1
    )
    
    # Bollinger Bands
    if len(df) >= 20:
        upper, sma, lower = calculate_bollinger_bands(df)
        fig.add_trace(go.Scatter(x=df.index, y=upper, name='BB Upper', 
                                  line=dict(color='rgba(0, 212, 255, 0.3)', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=sma, name='BB SMA', 
                                  line=dict(color='#00d4ff', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=lower, name='BB Lower', 
                                  line=dict(color='rgba(0, 212, 255, 0.3)', width=1),
                                  fill='tonexty', fillcolor='rgba(0, 212, 255, 0.05)'), row=1, col=1)
    
    # EMA
    if len(df) >= 20:
        ema20 = df['close'].ewm(span=20).mean()
        ema50 = df['close'].ewm(span=50).mean() if len(df) >= 50 else None
        fig.add_trace(go.Scatter(x=df.index, y=ema20, name='EMA 20',
                                  line=dict(color='#ffc107', width=1.5)), row=1, col=1)
        if ema50 is not None:
            fig.add_trace(go.Scatter(x=df.index, y=ema50, name='EMA 50',
                                      line=dict(color='#ff6b35', width=1.5)), row=1, col=1)
    
    if show_indicators:
        # RSI
        rsi = calculate_rsi(df)
        fig.add_trace(go.Scatter(x=df.index, y=rsi, name='RSI',
                                  line=dict(color='#a855f7', width=1.5)), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(255,71,87,0.5)", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="rgba(0,255,136,0.5)", row=2, col=1)
        fig.add_hrect(y0=30, y1=70, fillcolor="rgba(168,85,247,0.1)", line_width=0, row=2, col=1)
        
        # MACD
        macd_line, signal_line, histogram = calculate_macd(df)
        colors = ['#00ff88' if val >= 0 else '#ff4757' for val in histogram]
        fig.add_trace(go.Bar(x=df.index, y=histogram, name='MACD Hist',
                              marker=dict(color=colors, opacity=0.6)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=macd_line, name='MACD',
                                  line=dict(color='#00d4ff', width=1.5)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=signal_line, name='Signal',
                                  line=dict(color='#ff6b35', width=1.5)), row=3, col=1)
        
        # Volume
        colors_vol = ['#00875a' if c >= o else '#c92a2a' for c, o in zip(df['close'], df['open'])]
        fig.add_trace(go.Bar(x=df.index, y=df['volume'], name='Volume',
                              marker=dict(color=colors_vol, opacity=0.7)), row=4, col=1)
    else:
        # Solo Volume
        colors_vol = ['#00875a' if c >= o else '#c92a2a' for c, o in zip(df['close'], df['open'])]
        fig.add_trace(go.Bar(x=df.index, y=df['volume'], name='Volume',
                              marker=dict(color=colors_vol, opacity=0.7)), row=2, col=1)
    
    # Layout
    symbol_name = symbol.replace('/USDT:USDT', '')
    height = 800 if show_indicators else 550
    
    fig.update_layout(
        title=dict(text=f"<b>{symbol_name}/USDT</b>", font=dict(size=24, color='#f0f6fc'), x=0.5),
        template='plotly_dark',
        paper_bgcolor='#0a0e14',
        plot_bgcolor='#111820',
        height=height,
        margin=dict(l=60, r=60, t=80, b=40),
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center", 
                    font=dict(color='#8b949e', size=10), bgcolor='rgba(0,0,0,0)'),
        hovermode='x unified'
    )
    
    # Axes styling
    for i in range(1, rows + 1):
        fig.update_xaxes(gridcolor='#1e2a38', linecolor='#30363d', 
                         tickfont=dict(color='#8b949e'), row=i, col=1)
        fig.update_yaxes(gridcolor='#1e2a38', linecolor='#30363d', 
                         tickfont=dict(color='#8b949e'), row=i, col=1)
    
    return fig


def create_volume_analysis_chart(df, symbol):
    """Grafico analisi volume"""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Volume Distribution', 'Price vs Volume Correlation', 
                       'Volume Profile', 'Cumulative Volume'),
        specs=[[{"type": "histogram"}, {"type": "scatter"}],
               [{"type": "bar"}, {"type": "scatter"}]]
    )
    
    # Volume Distribution
    fig.add_trace(go.Histogram(x=df['volume'], nbinsx=30, name='Volume Dist',
                                marker_color='#00d4ff', opacity=0.7), row=1, col=1)
    
    # Price vs Volume
    fig.add_trace(go.Scatter(x=df['volume'], y=df['close'], mode='markers',
                              name='Price vs Vol', marker=dict(color='#00ff88', size=5, opacity=0.6)), 
                  row=1, col=2)
    
    # Volume Profile (by price level)
    price_bins = pd.cut(df['close'], bins=20)
    vol_profile = df.groupby(price_bins)['volume'].sum()
    fig.add_trace(go.Bar(x=vol_profile.values, y=[str(x) for x in vol_profile.index],
                          orientation='h', name='Vol Profile', marker_color='#a855f7'), row=2, col=1)
    
    # Cumulative Volume
    cum_vol = df['volume'].cumsum()
    fig.add_trace(go.Scatter(x=df.index, y=cum_vol, name='Cum Volume',
                              line=dict(color='#ffc107', width=2)), row=2, col=2)
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0a0e14',
        plot_bgcolor='#111820',
        height=500,
        showlegend=False,
        margin=dict(l=50, r=50, t=60, b=40)
    )
    
    return fig


def create_market_overview_chart(top_symbols):
    """Grafico overview mercato"""
    if not top_symbols:
        return None
    
    df = pd.DataFrame(top_symbols[:20])
    df['coin'] = df['symbol'].str.replace('/USDT:USDT', '')
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Top 20 by Volume', 'Volume Distribution'),
        specs=[[{"type": "bar"}, {"type": "pie"}]]
    )
    
    # Bar chart
    colors = px.colors.sequential.Viridis[:20]
    fig.add_trace(go.Bar(x=df['coin'], y=df['volume_24h'], name='Volume',
                          marker=dict(color=df['volume_24h'], colorscale='Viridis')), row=1, col=1)
    
    # Pie chart top 10
    df_pie = df.head(10)
    fig.add_trace(go.Pie(labels=df_pie['coin'], values=df_pie['volume_24h'],
                          hole=0.4, name='Distribution'), row=1, col=2)
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0a0e14',
        plot_bgcolor='#111820',
        height=400,
        showlegend=False,
        margin=dict(l=50, r=50, t=60, b=40)
    )
    
    return fig


def format_volume(vol):
    """Formatta volume in modo leggibile"""
    if vol >= 1e9:
        return f"${vol/1e9:.2f}B"
    elif vol >= 1e6:
        return f"${vol/1e6:.1f}M"
    elif vol >= 1e3:
        return f"${vol/1e3:.1f}K"
    else:
        return f"${vol:.0f}"


def get_price_change_color(change):
    """Ritorna colore in base al cambio"""
    if change > 0:
        return "#00ff88"
    elif change < 0:
        return "#ff4757"
    return "#8b949e"


# ============================================================
# MAIN APP
# ============================================================
def main():
    # Header
    st.markdown("""
    <div class="header-card">
        <h1>📈 Crypto Dashboard Pro</h1>
        <p>Top 100 Cryptocurrencies • Real-time Analysis • Technical Indicators</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚡ Control Panel")
        
        # Live clock con JavaScript
        next_info = get_next_update_info()
        components.html(f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&display=swap');
            .live-clock-container {{
                background: rgba(10, 15, 30, 0.8);
                border: 1px solid rgba(0, 255, 255, 0.3);
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 10px;
            }}
            .status-dot {{
                display: inline-block;
                width: 10px;
                height: 10px;
                background: #00ff88;
                border-radius: 50%;
                margin-right: 8px;
                box-shadow: 0 0 10px #00ff88;
                animation: pulse 1.5s ease-in-out infinite;
            }}
            @keyframes pulse {{
                0%, 100% {{ opacity: 1; transform: scale(1); }}
                50% {{ opacity: 0.7; transform: scale(1.1); }}
            }}
            .live-text {{
                color: #00ff88;
                font-family: 'Orbitron', sans-serif;
                font-weight: 700;
                font-size: 0.9rem;
            }}
            .clock {{
                color: #00ffff;
                font-family: 'Orbitron', sans-serif;
                font-weight: 700;
                font-size: 1.5rem;
                text-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
                margin: 10px 0;
            }}
            .date {{
                color: #8899aa;
                font-size: 0.85rem;
            }}
            .countdown-container {{
                background: rgba(0, 255, 255, 0.1);
                border: 1px solid rgba(0, 255, 255, 0.3);
                border-radius: 8px;
                padding: 10px;
                margin-top: 10px;
                text-align: center;
            }}
            .countdown-label {{
                color: #8899aa;
                font-size: 0.7rem;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .countdown-time {{
                color: #ffc107;
                font-family: 'Orbitron', sans-serif;
                font-weight: 700;
                font-size: 1.2rem;
            }}
            .next-update {{
                color: #00ffff;
                font-size: 0.9rem;
                margin-top: 5px;
            }}
        </style>
        <div class="live-clock-container">
            <div>
                <span class="status-dot"></span>
                <span class="live-text">LIVE</span>
            </div>
            <div class="clock" id="clock">--:--:--</div>
            <div class="date" id="date">--/--/----</div>
            <div class="countdown-container">
                <div class="countdown-label">Prossimo Update</div>
                <div class="next-update">⏰ {next_info['next_update']}</div>
                <div class="countdown-time" id="countdown">--:--</div>
            </div>
        </div>
        <script>
            function updateClock() {{
                const now = new Date();
                // Converti in orario Roma
                const options = {{ timeZone: 'Europe/Rome' }};
                const timeStr = now.toLocaleTimeString('it-IT', {{ ...options, hour: '2-digit', minute: '2-digit', second: '2-digit' }});
                const dateStr = now.toLocaleDateString('it-IT', {{ ...options, day: '2-digit', month: '2-digit', year: 'numeric' }});
                
                document.getElementById('clock').textContent = timeStr;
                document.getElementById('date').textContent = dateStr;
                
                // Calcola countdown al prossimo 15 minuti
                const minutes = now.getMinutes();
                const seconds = now.getSeconds();
                const nextUpdate = Math.ceil(minutes / 15) * 15;
                let minutesLeft = (nextUpdate >= 60 ? 60 : nextUpdate) - minutes - 1;
                let secondsLeft = 60 - seconds;
                if (secondsLeft === 60) {{
                    secondsLeft = 0;
                    minutesLeft += 1;
                }}
                if (minutesLeft < 0) minutesLeft = 14;
                
                const countdownStr = String(minutesLeft).padStart(2, '0') + ':' + String(secondsLeft).padStart(2, '0');
                document.getElementById('countdown').textContent = '⏱️ -' + countdownStr;
            }}
            
            updateClock();
            setInterval(updateClock, 1000);
        </script>
        """, height=200)
        
        # Stats
        stats = get_stats()
        if stats:
            st.markdown("### 📊 Database Stats")
            
            col1, col2 = st.columns(2)
            col1.metric("Coins", stats['top_count'])
            col2.metric("TFs", stats['timeframes'])
            
            st.metric("Total Candles", f"{stats['candles']:,}")
            
            # Last Update con timezone Roma
            if stats.get('updated'):
                last_update_rome = format_datetime_rome(stats['updated'])
                st.caption(f"🕐 Last Update: {last_update_rome}")
            
            st.markdown("---")
            
            # Timer prossimo aggiornamento
            st.markdown("### ⏰ Next Update")
            next_info = get_next_update_info()
            
            # Mostra countdown con stile
            st.markdown(f"""
            <div style="background: rgba(0, 255, 255, 0.1); border: 1px solid #00ffff; border-radius: 10px; padding: 15px; text-align: center;">
                <p style="color: #aabbcc; margin: 0; font-size: 0.8rem;">PROSSIMO UPDATE ALLE</p>
                <h2 style="color: #00ffff; margin: 5px 0; font-family: 'Orbitron', sans-serif;">{next_info['next_update']}</h2>
                <p style="color: #ffc107; margin: 0; font-size: 1.2rem; font-family: 'Orbitron', sans-serif;">⏱️ -{next_info['countdown']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("---")
        else:
            st.error("⚠️ Database not found")
            st.code("docker compose up -d")
            st.stop()
        
        # Quick Actions
        st.markdown("### 🚀 Quick Actions")
        
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()
        
        if st.button("📥 Force Update List", use_container_width=True):
            if trigger_refresh():
                st.success("✅ Update signal sent!")
        
        st.markdown("---")
        
        # Info
        st.markdown("### ℹ️ Info")
        st.caption(f"📍 Timezone: Europe/Rome")
        st.caption("🔄 Updates every 15 minutes")
        st.caption("📡 Data from Bybit Exchange")
    
    # Main content - TABS
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Top 100 Coins", 
        "📈 Advanced Charts", 
        "📉 Volume Analysis",
        "🔬 Technical Analysis"
    ])
    
    # ============================================================
    # TAB 1: TOP 100 COINS
    # ============================================================
    with tab1:
        st.markdown("### 🏆 Top 100 Cryptocurrencies by 24h Volume")
        
        top_symbols = get_top_symbols()
        
        if top_symbols:
            # Metriche riassuntive
            df_top = pd.DataFrame(top_symbols)
            df_top['coin'] = df_top['symbol'].str.replace('/USDT:USDT', '')
            
            total_vol = df_top['volume_24h'].sum()
            avg_vol = df_top['volume_24h'].mean()
            
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("🪙 Total Coins", len(df_top))
            col2.metric("💰 Total Volume", format_volume(total_vol))
            col3.metric("📊 Avg Volume", format_volume(avg_vol))
            col4.metric("🥇 #1", df_top.iloc[0]['coin'])
            col5.metric("🥇 Vol", format_volume(df_top.iloc[0]['volume_24h']))
            
            st.markdown("---")
            
            # Market Overview Chart
            fig_overview = create_market_overview_chart(top_symbols)
            if fig_overview:
                st.plotly_chart(fig_overview, use_container_width=True)
            
            st.markdown("---")
            
            # Filtro di ricerca
            col1, col2 = st.columns([3, 1])
            with col1:
                search = st.text_input("🔍 Search coin", placeholder="BTC, ETH, SOL...")
            with col2:
                sort_by = st.selectbox("Sort by", ["Rank", "Volume (High)", "Volume (Low)"])
            
            # Filtra e ordina
            df_display = df_top.copy()
            if search:
                df_display = df_display[df_display['coin'].str.contains(search.upper())]
            
            if sort_by == "Volume (High)":
                df_display = df_display.sort_values('volume_24h', ascending=False)
            elif sort_by == "Volume (Low)":
                df_display = df_display.sort_values('volume_24h', ascending=True)
            
            # Tabella formattata HTML custom
            df_display['Volume 24h'] = df_display['volume_24h'].apply(format_volume)
            df_display['% of Total'] = (df_display['volume_24h'] / total_vol * 100).round(2).astype(str) + '%'
            
            # Crea tabella HTML con stile neon
            table_html = """
            <style>
                .crypto-table {
                    width: 100%;
                    border-collapse: collapse;
                    background: rgba(13, 17, 23, 0.9);
                    border-radius: 12px;
                    overflow: hidden;
                    font-family: 'Rajdhani', sans-serif;
                }
                .crypto-table th {
                    background: linear-gradient(135deg, #161b26 0%, #1e2a38 100%);
                    color: #00ffff !important;
                    padding: 15px 20px;
                    text-align: left;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    border-bottom: 2px solid rgba(0, 255, 255, 0.3);
                    font-size: 0.9rem;
                }
                .crypto-table td {
                    color: #ffffff !important;
                    padding: 12px 20px;
                    border-bottom: 1px solid rgba(0, 255, 255, 0.1);
                    font-size: 1rem;
                }
                .crypto-table tr:hover td {
                    background: rgba(0, 255, 255, 0.1);
                }
                .crypto-table tr:nth-child(even) td {
                    background: rgba(0, 0, 0, 0.2);
                }
                .rank-col {
                    color: #00ffff !important;
                    font-weight: 700;
                    font-family: 'Orbitron', sans-serif;
                }
                .coin-col {
                    color: #ffffff !important;
                    font-weight: 600;
                }
                .vol-col {
                    color: #00ff88 !important;
                    font-weight: 600;
                }
                .pct-col {
                    color: #ffc107 !important;
                }
                .table-container {
                    max-height: 500px;
                    overflow-y: auto;
                    border-radius: 12px;
                    border: 1px solid rgba(0, 255, 255, 0.3);
                    box-shadow: 0 0 20px rgba(0, 255, 255, 0.1);
                }
            </style>
            <div class="table-container">
            <table class="crypto-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Coin</th>
                        <th>Volume 24h</th>
                        <th>% of Total</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for _, row in df_display.iterrows():
                table_html += f"""
                    <tr>
                        <td class="rank-col">{row['rank']}</td>
                        <td class="coin-col">{row['coin']}</td>
                        <td class="vol-col">{row['Volume 24h']}</td>
                        <td class="pct-col">{row['% of Total']}</td>
                    </tr>
                """
            
            table_html += """
                </tbody>
            </table>
            </div>
            """
            
            # Usa components.html per renderizzare correttamente
            components.html(table_html, height=550, scrolling=True)
            
            # Info aggiornamento
            if stats.get('top_fetched_at'):
                st.caption(f"📅 List updated: {stats['top_fetched_at'][:16]}")
        else:
            st.warning("⚠️ No data available. Wait for data-fetcher to load data.")
    
    # ============================================================
    # TAB 2: ADVANCED CHARTS
    # ============================================================
    with tab2:
        st.markdown("### 📈 Advanced Candlestick Charts")
        
        symbols = get_symbols()
        if not symbols:
            st.warning("No data available")
            st.stop()
        
        symbol_map = {s.replace('/USDT:USDT', ''): s for s in symbols}
        
        # Controlli
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        
        with col1:
            selected_name = st.selectbox("🪙 Select Coin", list(symbol_map.keys()), key="chart_coin")
            selected_symbol = symbol_map[selected_name]
        
        with col2:
            timeframes = get_timeframes(selected_symbol)
            tf_order = ['15m', '1h', '4h', '1d']
            timeframes_sorted = [tf for tf in tf_order if tf in timeframes]
            selected_tf = st.selectbox("⏱️ Timeframe", timeframes_sorted, key="chart_tf")
        
        with col3:
            num_candles = st.selectbox("🕯️ Candles", [50, 100, 150, 200], index=3, key="chart_candles")
        
        with col4:
            show_indicators = st.checkbox("📊 Indicators", value=True)
        
        # Carica dati
        df = get_ohlcv(selected_symbol, selected_tf, num_candles)
        
        if df.empty:
            st.error("No data for this selection")
            st.stop()
        
        # Metriche
        price = df['close'].iloc[-1]
        change = ((df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]) * 100
        high = df['high'].max()
        low = df['low'].min()
        vol = df['volume'].sum()
        
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("💰 Price", f"${price:,.2f}", f"{change:+.2f}%")
        col2.metric("📈 24h High", f"${high:,.2f}")
        col3.metric("📉 24h Low", f"${low:,.2f}")
        col4.metric("📊 Volume", format_volume(vol))
        
        # Volatility
        volatility = ((high - low) / low * 100)
        col5.metric("⚡ Volatility", f"{volatility:.2f}%")
        
        st.markdown("---")
        
        # Chart
        fig = create_advanced_chart(df, selected_symbol, show_indicators)
        st.plotly_chart(fig, use_container_width=True)
        
        # Recent data
        with st.expander("📋 Recent Data Table"):
            table = df.tail(20).iloc[::-1].copy()
            table.index = table.index.strftime('%Y-%m-%d %H:%M')
            table['change'] = table['close'].pct_change() * 100
            st.dataframe(table.round(4), use_container_width=True)
    
    # ============================================================
    # TAB 3: VOLUME ANALYSIS
    # ============================================================
    with tab3:
        st.markdown("### 📉 Volume Analysis")
        
        symbols = get_symbols()
        if not symbols:
            st.warning("No data available")
            st.stop()
        
        symbol_map = {s.replace('/USDT:USDT', ''): s for s in symbols}
        
        col1, col2 = st.columns([2, 1])
        with col1:
            vol_coin = st.selectbox("🪙 Select Coin", list(symbol_map.keys()), key="vol_coin")
        with col2:
            vol_tf = st.selectbox("⏱️ Timeframe", ['15m', '1h', '4h', '1d'], key="vol_tf")
        
        df_vol = get_ohlcv(symbol_map[vol_coin], vol_tf, 200)
        
        if not df_vol.empty:
            # Volume stats
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📊 Avg Volume", format_volume(df_vol['volume'].mean()))
            col2.metric("📈 Max Volume", format_volume(df_vol['volume'].max()))
            col3.metric("📉 Min Volume", format_volume(df_vol['volume'].min()))
            col4.metric("📐 Std Dev", format_volume(df_vol['volume'].std()))
            
            st.markdown("---")
            
            # Volume Analysis Chart
            fig_vol = create_volume_analysis_chart(df_vol, vol_coin)
            st.plotly_chart(fig_vol, use_container_width=True)
            
            # VWAP
            st.markdown("#### 📊 VWAP Analysis")
            vwap = calculate_vwap(df_vol)
            current_price = df_vol['close'].iloc[-1]
            vwap_current = vwap.iloc[-1]
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Current Price", f"${current_price:,.2f}")
            col2.metric("VWAP", f"${vwap_current:,.2f}")
            
            diff_vwap = ((current_price - vwap_current) / vwap_current) * 100
            status = "Above VWAP 📈" if diff_vwap > 0 else "Below VWAP 📉"
            col3.metric("Status", status, f"{diff_vwap:+.2f}%")
    
    # ============================================================
    # TAB 4: TECHNICAL ANALYSIS
    # ============================================================
    with tab4:
        st.markdown("### 🔬 Technical Analysis")
        
        symbols = get_symbols()
        if not symbols:
            st.warning("No data available")
            st.stop()
        
        symbol_map = {s.replace('/USDT:USDT', ''): s for s in symbols}
        
        col1, col2 = st.columns([2, 1])
        with col1:
            ta_coin = st.selectbox("🪙 Select Coin", list(symbol_map.keys()), key="ta_coin")
        with col2:
            ta_tf = st.selectbox("⏱️ Timeframe", ['15m', '1h', '4h', '1d'], key="ta_tf")
        
        df_ta = get_ohlcv(symbol_map[ta_coin], ta_tf, 200)
        
        if not df_ta.empty:
            # Calculate all indicators
            rsi = calculate_rsi(df_ta)
            macd_line, signal_line, histogram = calculate_macd(df_ta)
            upper_bb, sma_bb, lower_bb = calculate_bollinger_bands(df_ta)
            atr = calculate_atr(df_ta)
            
            st.markdown("#### 📊 Current Indicator Values")
            
            col1, col2, col3, col4 = st.columns(4)
            
            # RSI
            current_rsi = rsi.iloc[-1]
            rsi_status = "Overbought 🔴" if current_rsi > 70 else "Oversold 🟢" if current_rsi < 30 else "Neutral ⚪"
            col1.metric("RSI (14)", f"{current_rsi:.1f}", rsi_status)
            
            # MACD
            current_macd = macd_line.iloc[-1]
            current_signal = signal_line.iloc[-1]
            macd_status = "Bullish 🟢" if current_macd > current_signal else "Bearish 🔴"
            col2.metric("MACD", f"{current_macd:.4f}", macd_status)
            
            # ATR
            current_atr = atr.iloc[-1]
            col3.metric("ATR (14)", f"${current_atr:.2f}")
            
            # BB Position
            current_price = df_ta['close'].iloc[-1]
            bb_position = (current_price - lower_bb.iloc[-1]) / (upper_bb.iloc[-1] - lower_bb.iloc[-1]) * 100
            bb_status = "Upper 🔴" if bb_position > 80 else "Lower 🟢" if bb_position < 20 else "Middle ⚪"
            col4.metric("BB Position", f"{bb_position:.0f}%", bb_status)
            
            st.markdown("---")
            
            # Signal Summary
            st.markdown("#### 🎯 Signal Summary")
            
            signals = []
            
            # RSI Signal
            if current_rsi > 70:
                signals.append(("RSI", "SELL", "#ff4757"))
            elif current_rsi < 30:
                signals.append(("RSI", "BUY", "#00ff88"))
            else:
                signals.append(("RSI", "NEUTRAL", "#ffc107"))
            
            # MACD Signal
            if current_macd > current_signal and histogram.iloc[-1] > histogram.iloc[-2]:
                signals.append(("MACD", "BUY", "#00ff88"))
            elif current_macd < current_signal and histogram.iloc[-1] < histogram.iloc[-2]:
                signals.append(("MACD", "SELL", "#ff4757"))
            else:
                signals.append(("MACD", "NEUTRAL", "#ffc107"))
            
            # BB Signal
            if bb_position > 95:
                signals.append(("Bollinger", "SELL", "#ff4757"))
            elif bb_position < 5:
                signals.append(("Bollinger", "BUY", "#00ff88"))
            else:
                signals.append(("Bollinger", "NEUTRAL", "#ffc107"))
            
            # Display signals
            cols = st.columns(len(signals))
            for i, (indicator, signal, color) in enumerate(signals):
                with cols[i]:
                    st.markdown(f"""
                    <div style="background-color: {color}; padding: 15px; border-radius: 10px; text-align: center;">
                        <h4 style="color: white; margin: 0;">{indicator}</h4>
                        <h2 style="color: white; margin: 5px 0;">{signal}</h2>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Moving Averages Table
            st.markdown("#### 📈 Moving Averages")
            
            ma_data = []
            for period in [10, 20, 50, 100, 200]:
                if len(df_ta) >= period:
                    sma = df_ta['close'].rolling(window=period).mean().iloc[-1]
                    ema = df_ta['close'].ewm(span=period).mean().iloc[-1]
                    signal = "BUY 🟢" if current_price > sma else "SELL 🔴"
                    ma_data.append({
                        'Period': period,
                        'SMA': f"${sma:.2f}",
                        'EMA': f"${ema:.2f}",
                        'Signal': signal
                    })
            
            st.dataframe(pd.DataFrame(ma_data), use_container_width=True, hide_index=True)
    
    # Footer
    st.markdown("""
    <p class="footer-text">
        🚀 Crypto Dashboard Pro | Built with Streamlit & Plotly | Data from Bybit | Updates every 15 minutes<br>
        <small>© 2024 - Real-time cryptocurrency analysis</small>
    </p>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
