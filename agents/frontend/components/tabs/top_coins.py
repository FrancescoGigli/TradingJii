"""
Top 100 Coins Tab for the Crypto Dashboard
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from database import get_top_symbols, get_stats
from charts import create_market_overview_chart
from utils import format_volume


def render_top_coins_tab():
    """Render the Top 100 Coins tab"""
    st.markdown("### 🏆 Top 100 Cryptocurrencies by 24h Volume")
    
    top_symbols = get_top_symbols()
    stats = get_stats()
    
    if top_symbols:
        # Summary metrics
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
        
        # Search filter
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
        
        # Formatted table
        df_display['Volume 24h'] = df_display['volume_24h'].apply(format_volume)
        df_display['% of Total'] = (df_display['volume_24h'] / total_vol * 100).round(2).astype(str) + '%'
        
        # Custom HTML table with neon style
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
        
        # Use components.html to render correctly
        components.html(table_html, height=550, scrolling=True)
        
        # Update info
        if stats.get('top_fetched_at'):
            st.caption(f"📅 List updated: {stats['top_fetched_at'][:16]}")
    else:
        st.warning("⚠️ No data available. Wait for data-fetcher to load data.")
