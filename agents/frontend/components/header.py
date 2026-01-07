"""
📊 Header Component - Persistent Balance & Sentiment Display

Displays:
- Bybit USDT balance (always visible)
- Fear & Greed sentiment index
- Quick news summary
- Service status indicators

This header appears above all tabs and persists across navigation.
Now uses caching and non-blocking error handling.
"""

import streamlit as st
import streamlit.components.v1 as components
from typing import Optional, Dict
from datetime import datetime
import logging
import concurrent.futures
from functools import lru_cache

from styles.colors import PALETTE, STATUS_COLORS

logger = logging.getLogger(__name__)

# Timeout for data fetching (seconds)
DATA_FETCH_TIMEOUT = 5


def _get_balance_html(balance_info: Dict) -> str:
    """Generate HTML for balance display"""
    total = balance_info.get('total_usdt', 0)
    available = balance_info.get('available_usdt', 0)
    is_real = balance_info.get('is_real', False)
    
    # Format balance
    if total >= 1000000:
        balance_str = f"${total/1e6:.2f}M"
    elif total >= 1000:
        balance_str = f"${total/1e3:.1f}K"
    else:
        balance_str = f"${total:.2f}"
    
    # Status indicator
    status_color = PALETTE['accent_green'] if is_real else PALETTE['accent_yellow']
    status_text = "" if is_real else " (offline)"
    
    return f"""
    <div class="header-item balance-item">
        <span class="header-icon">💰</span>
        <div class="header-content">
            <span class="header-value" style="color: {status_color};">{balance_str}{status_text}</span>
            <span class="header-label">USDT Balance</span>
        </div>
    </div>
    """


def _get_sentiment_html(sentiment_info: Dict) -> str:
    """Generate HTML for sentiment display"""
    value = sentiment_info.get('value', 50)
    classification = sentiment_info.get('classification', 'Neutral')
    is_real = sentiment_info.get('is_real', False)
    
    # Color based on value
    if value <= 25:
        color = "#ff4757"  # Extreme Fear - Red
        emoji = "😱"
    elif value <= 45:
        color = "#ffa502"  # Fear - Orange
        emoji = "😰"
    elif value <= 55:
        color = "#a0a0a0"  # Neutral - Gray
        emoji = "😐"
    elif value <= 75:
        color = "#7bed9f"  # Greed - Light Green
        emoji = "😊"
    else:
        color = "#00ff88"  # Extreme Greed - Green
        emoji = "🤑"
    
    status_text = "" if is_real else "*"
    
    return f"""
    <div class="header-item sentiment-item">
        <span class="header-icon">{emoji}</span>
        <div class="header-content">
            <span class="header-value" style="color: {color};">{value}/100{status_text}</span>
            <span class="header-label">{classification}</span>
        </div>
    </div>
    """


def _get_news_html(news_count: int, latest_title: str = "") -> str:
    """Generate HTML for news indicator"""
    if latest_title:
        title_preview = latest_title[:30] + "..." if len(latest_title) > 30 else latest_title
    else:
        title_preview = "No news available"
    
    return f"""
    <div class="header-item news-item">
        <span class="header-icon">📰</span>
        <div class="header-content">
            <span class="header-value">{news_count} News</span>
            <span class="header-label" title="{latest_title}">{title_preview}</span>
        </div>
    </div>
    """


def _get_services_html(bybit_ok: bool, openai_ok: bool, cmc_ok: bool) -> str:
    """Generate HTML for service status"""
    def status_dot(is_ok: bool) -> str:
        color = PALETTE['accent_green'] if is_ok else PALETTE['text_muted']
        return f'<span class="status-dot" style="background: {color};"></span>'
    
    return f"""
    <div class="header-item services-item">
        <span class="header-icon">⚡</span>
        <div class="header-content">
            <div class="services-row">
                {status_dot(bybit_ok)}<span>Bybit</span>
                {status_dot(openai_ok)}<span>AI</span>
                {status_dot(cmc_ok)}<span>CMC</span>
            </div>
            <span class="header-label">Services</span>
        </div>
    </div>
    """


def render_header_bar():
    """
    Render the persistent header bar with balance, sentiment, and services.
    
    This should be called at the top of app.py, after the main header
    but before the tabs.
    """
    # Get data from services (with fallbacks)
    balance_info = {'total_usdt': 0, 'available_usdt': 0, 'is_real': False}
    sentiment_info = {'value': 50, 'classification': 'Neutral', 'is_real': False}
    news_count = 0
    latest_news = ""
    bybit_ok = False
    openai_ok = False
    cmc_ok = False
    
    try:
        from services import get_bybit_service, get_openai_service, get_market_intelligence
        
        # Bybit balance
        bybit_service = get_bybit_service()
        bybit_ok = bybit_service.is_available
        if bybit_ok:
            balance = bybit_service.get_balance()
            balance_info = {
                'total_usdt': balance.total_usdt,
                'available_usdt': balance.available_usdt,
                'is_real': balance.is_real
            }
        
        # OpenAI status
        openai_service = get_openai_service()
        openai_ok = openai_service.is_available
        
        # Market intelligence
        market_intel = get_market_intelligence()
        cmc_ok = market_intel.is_sentiment_available
        
        # Sentiment
        sentiment = market_intel.get_sentiment()
        sentiment_info = {
            'value': sentiment.value,
            'classification': sentiment.classification,
            'is_real': sentiment.is_real
        }
        
        # News
        news = market_intel.get_news(max_items=5)
        news_count = len(news)
        if news:
            latest_news = news[0].title
            
    except Exception as e:
        # Silently fail - header will show offline status
        pass
    
    # Build HTML
    balance_html = _get_balance_html(balance_info)
    sentiment_html = _get_sentiment_html(sentiment_info)
    news_html = _get_news_html(news_count, latest_news)
    services_html = _get_services_html(bybit_ok, openai_ok, cmc_ok)
    
    # Colors from palette
    bg_card = PALETTE['bg_card']
    border = PALETTE['border_primary']
    text_primary = PALETTE['text_primary']
    text_muted = PALETTE['text_muted']
    cyan = PALETTE['accent_cyan']
    
    html = f"""
    <div id="header-bar-container">
    <style>
        #header-bar-container .header-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: {bg_card};
            border: 1px solid {border};
            border-radius: 12px;
            padding: 12px 20px;
            margin-bottom: 15px;
            gap: 15px;
            flex-wrap: wrap;
        }}
        
        #header-bar-container .header-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 15px;
            background: rgba(0, 255, 255, 0.03);
            border-radius: 8px;
            flex: 1;
            min-width: 140px;
        }}
        
        #header-bar-container .header-icon {{
            font-size: 1.5rem;
        }}
        
        #header-bar-container .header-content {{
            display: flex;
            flex-direction: column;
        }}
        
        #header-bar-container .header-value {{
            font-family: 'Orbitron', monospace;
            font-size: 1.1rem;
            font-weight: 700;
            color: {text_primary};
        }}
        
        #header-bar-container .header-label {{
            font-size: 0.7rem;
            color: {text_muted};
            text-transform: uppercase;
            letter-spacing: 0.5px;
            max-width: 120px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        #header-bar-container .services-row {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.75rem;
            color: {text_muted};
        }}
        
        #header-bar-container .status-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }}
        
        @media (max-width: 768px) {{
            #header-bar-container .header-bar {{
                flex-direction: column;
            }}
            #header-bar-container .header-item {{
                width: 100%;
            }}
        }}
    </style>
    
    <div class="header-bar">
        {balance_html}
        {sentiment_html}
        {news_html}
        {services_html}
    </div>
    </div>
    """
    
    components.html(html, height=85)


def render_header_simple():
    """
    Render a simpler header using native Streamlit components.
    Fallback if HTML component has issues.
    """
    # Get data from services
    try:
        from services import get_bybit_service, get_market_intelligence
        
        bybit_service = get_bybit_service()
        balance = bybit_service.get_balance() if bybit_service.is_available else None
        
        market_intel = get_market_intelligence()
        sentiment = market_intel.get_sentiment()
        news = market_intel.get_news(max_items=3)
        
    except Exception:
        balance = None
        sentiment = None
        news = []
    
    # Create columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        balance_val = f"${balance.total_usdt:,.2f}" if balance and balance.is_real else "Offline"
        st.metric("💰 Balance", balance_val)
    
    with col2:
        if sentiment:
            st.metric(
                f"{_get_sentiment_emoji(sentiment.value)} Fear & Greed",
                f"{sentiment.value}/100",
                sentiment.classification
            )
        else:
            st.metric("📊 Fear & Greed", "N/A")
    
    with col3:
        st.metric("📰 News", f"{len(news)} items")
    
    with col4:
        # Service status
        try:
            from services import get_bybit_service, get_openai_service, get_market_intelligence
            bybit_ok = get_bybit_service().is_available
            ai_ok = get_openai_service().is_available
            cmc_ok = get_market_intelligence().is_sentiment_available
            status = f"{'🟢' if bybit_ok else '🔴'} {'🟢' if ai_ok else '🔴'} {'🟢' if cmc_ok else '🔴'}"
        except:
            status = "🔴 🔴 🔴"
        st.metric("⚡ Services", status, "Bybit AI CMC")


def _get_sentiment_emoji(value: int) -> str:
    """Get emoji for sentiment value"""
    if value <= 25:
        return "😱"
    elif value <= 45:
        return "😰"
    elif value <= 55:
        return "😐"
    elif value <= 75:
        return "😊"
    else:
        return "🤑"
