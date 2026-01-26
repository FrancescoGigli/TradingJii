"""
Top 100 Coins Table Component.

Displays:
- Summary metrics
- Market overview chart
- Searchable/sortable coins table
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from database import get_top_symbols, get_stats
from charts import create_market_overview_chart
from utils import format_volume

from .styles import render_crypto_table_html


def render_coins_section():
    """Render the Top 100 coins list section."""
    st.markdown("### 🏆 Top 100 Cryptocurrencies by 24h Volume")
    
    top_symbols = get_top_symbols()
    stats = get_stats()
    
    if not top_symbols:
        st.warning("⚠️ No data available. Wait for data-fetcher to load data.")
        return False
    
    # Build dataframe
    df_top = pd.DataFrame(top_symbols)
    df_top['coin'] = df_top['symbol'].str.replace('/USDT:USDT', '')
    
    total_vol = df_top['volume_24h'].sum()
    avg_vol = df_top['volume_24h'].mean()
    
    # Summary metrics
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
    
    # Search and sort controls
    col1, col2 = st.columns([3, 1])
    with col1:
        search = st.text_input("🔍 Search coin", placeholder="BTC, ETH, SOL...")
    with col2:
        sort_by = st.selectbox("Sort by", ["Rank", "Volume (High)", "Volume (Low)"])
    
    # Filter and sort
    df_display = df_top.copy()
    if search:
        df_display = df_display[df_display['coin'].str.contains(search.upper())]
    
    if sort_by == "Volume (High)":
        df_display = df_display.sort_values('volume_24h', ascending=False)
    elif sort_by == "Volume (Low)":
        df_display = df_display.sort_values('volume_24h', ascending=True)
    
    # Format display columns
    df_display['Volume 24h'] = df_display['volume_24h'].apply(format_volume)
    df_display['% of Total'] = (
        (df_display['volume_24h'] / total_vol * 100).round(2).astype(str) + '%'
    )
    
    # Render HTML table
    table_html = render_crypto_table_html(df_display, total_vol)
    components.html(table_html, height=550, scrolling=True)
    
    # Update info
    if stats.get('top_fetched_at'):
        st.caption(f"📅 List updated: {stats['top_fetched_at'][:16]}")
    
    return True


__all__ = ['render_coins_section']
