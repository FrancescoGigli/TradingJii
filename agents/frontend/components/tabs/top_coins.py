"""
Top 100 Coins Tab for the Crypto Dashboard

Now includes:
- Market Overview (volume chart)
- XGB Market Scanner (signals table)
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
        
        # ═══════════════════════════════════════════════════════════════════
        # MARKET SCANNER SECTION
        # ═══════════════════════════════════════════════════════════════════
        st.markdown("---")
        render_market_scanner_section()
        
    else:
        st.warning("⚠️ No data available. Wait for data-fetcher to load data.")


def render_market_scanner_section():
    """Render the XGB Market Scanner section"""
    from datetime import datetime
    import pytz
    
    # Roma timezone
    rome_tz = pytz.timezone('Europe/Rome')
    
    st.markdown("### 📡 XGB Market Scanner")
    
    # Import scanner service
    try:
        from services.market_scanner import get_market_scanner_service
        scanner = get_market_scanner_service()
    except ImportError as e:
        st.error(f"Scanner service not available: {e}")
        return
    
    # Settings row
    col1, col2 = st.columns([1, 1])
    
    with col1:
        timeframe = st.selectbox("Timeframe", ["15m", "1h", "4h"], index=0, key="scanner_tf", label_visibility="collapsed")
    
    with col2:
        filter_signal = st.selectbox(
            "Filter",
            ["All", "📈 BUY", "📉 SELL", "➡️ NEUTRAL"],
            key="scanner_filter",
            label_visibility="collapsed"
        )
    
    # Run scan automatically (cached for 60 seconds)
    signals = scanner.scan_market(timeframe=timeframe)
    
    if not signals:
        st.warning("⚠️ No signals available. Make sure historical data is loaded.")
        return
    
    # Apply filter
    if filter_signal == "📈 BUY":
        signals = [s for s in signals if s.signal == "BUY"]
    elif filter_signal == "📉 SELL":
        signals = [s for s in signals if s.signal == "SELL"]
    elif filter_signal == "➡️ NEUTRAL":
        signals = [s for s in signals if s.signal == "NEUTRAL"]
    
    # Summary
    buy_count = sum(1 for s in signals if s.signal == "BUY")
    sell_count = sum(1 for s in signals if s.signal == "SELL")
    neutral_count = sum(1 for s in signals if s.signal == "NEUTRAL")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📊 Total Scanned", len(signals))
    m2.metric("📈 BUY", buy_count, delta=None)
    m3.metric("📉 SELL", sell_count, delta=None)
    m4.metric("➡️ NEUTRAL", neutral_count, delta=None)
    
    st.divider()
    
    # Build signals table
    table_html = """
    <style>
        .scanner-table {
            width: 100%;
            border-collapse: collapse;
            background: rgba(13, 17, 23, 0.95);
            border-radius: 12px;
            overflow: hidden;
            font-family: 'Rajdhani', sans-serif;
        }
        .scanner-table th {
            background: linear-gradient(135deg, #1a1f2e 0%, #252d3d 100%);
            color: #00d4ff !important;
            padding: 12px 10px;
            text-align: center;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid rgba(0, 212, 255, 0.3);
            font-size: 0.75rem;
        }
        .scanner-table td {
            color: #e0e0e0 !important;
            padding: 10px 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            font-size: 0.9rem;
            text-align: center;
        }
        .scanner-table tr:hover td {
            background: rgba(0, 212, 255, 0.08);
        }
        .rank-col { color: #00d4ff !important; font-weight: 700; }
        .coin-col { color: #ffffff !important; font-weight: 600; text-align: left !important; }
        .price-col { color: #e0e0e0 !important; }
        .change-up { color: #10B981 !important; }
        .change-down { color: #EF4444 !important; }
        .rsi-oversold { color: #10B981 !important; font-weight: 600; }
        .rsi-overbought { color: #EF4444 !important; font-weight: 600; }
        .rsi-neutral { color: #888 !important; }
        .macd-bullish { color: #10B981 !important; }
        .macd-bearish { color: #EF4444 !important; }
        .macd-neutral { color: #888 !important; }
        .xgb-positive { color: #10B981 !important; font-weight: 600; }
        .xgb-negative { color: #EF4444 !important; font-weight: 600; }
        .xgb-neutral { color: #888 !important; }
        .tech-positive { color: #10B981 !important; }
        .tech-negative { color: #EF4444 !important; }
        .tech-neutral { color: #888 !important; }
        .signal-buy {
            background: linear-gradient(135deg, #10B981 0%, #059669 100%);
            color: white !important;
            padding: 4px 12px;
            border-radius: 15px;
            font-weight: 700;
        }
        .signal-sell {
            background: linear-gradient(135deg, #EF4444 0%, #DC2626 100%);
            color: white !important;
            padding: 4px 12px;
            border-radius: 15px;
            font-weight: 700;
        }
        .signal-neutral {
            background: rgba(100, 100, 100, 0.5);
            color: #ccc !important;
            padding: 4px 12px;
            border-radius: 15px;
        }
        .scanner-container {
            max-height: 600px;
            overflow-y: auto;
            border-radius: 12px;
            border: 1px solid rgba(0, 212, 255, 0.2);
            box-shadow: 0 0 30px rgba(0, 212, 255, 0.1);
        }
    </style>
    <div class="scanner-container">
    <table class="scanner-table">
        <thead>
            <tr>
                <th>#</th>
                <th>Coin</th>
                <th>Price</th>
                <th>24h %</th>
                <th>RSI</th>
                <th>RSI Sc</th>
                <th>MACD Sc</th>
                <th>BB Sc</th>
                <th>Tech</th>
                <th>XGB L</th>
                <th>XGB S</th>
                <th>Signal</th>
                <th>Last TS</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for s in signals[:50]:  # Limit to 50 for performance
        # Format values
        change_class = "change-up" if s.change_24h >= 0 else "change-down"
        change_str = f"+{s.change_24h:.1f}%" if s.change_24h >= 0 else f"{s.change_24h:.1f}%"
        
        # RSI class
        if s.rsi < 30:
            rsi_class = "rsi-oversold"
            rsi_icon = "🟢"
        elif s.rsi > 70:
            rsi_class = "rsi-overbought"
            rsi_icon = "🔴"
        else:
            rsi_class = "rsi-neutral"
            rsi_icon = ""
        
        # MACD class
        macd_class = f"macd-{s.macd_signal.lower()}"
        macd_icon = "🟢" if s.macd_signal == "BULLISH" else ("🔴" if s.macd_signal == "BEARISH" else "")
        
        # XGB classes
        xgb_long_class = "xgb-positive" if s.xgb_long > 20 else ("xgb-negative" if s.xgb_long < -20 else "xgb-neutral")
        xgb_short_class = "xgb-positive" if s.xgb_short > 20 else ("xgb-negative" if s.xgb_short < -20 else "xgb-neutral")
        
        # Signal class
        signal_class = f"signal-{s.signal.lower()}"
        signal_icon = "📈" if s.signal == "BUY" else ("📉" if s.signal == "SELL" else "➡️")
        
        # Format price
        if s.price >= 1000:
            price_str = f"${s.price:,.0f}"
        elif s.price >= 1:
            price_str = f"${s.price:.2f}"
        else:
            price_str = f"${s.price:.4f}"
        
        # Tech scores classes
        rsi_sc_class = "tech-positive" if s.rsi_score > 5 else ("tech-negative" if s.rsi_score < -5 else "tech-neutral")
        macd_sc_class = "tech-positive" if s.macd_score > 5 else ("tech-negative" if s.macd_score < -5 else "tech-neutral")
        bb_sc_class = "tech-positive" if s.bb_score > 5 else ("tech-negative" if s.bb_score < -5 else "tech-neutral")
        tech_class = "tech-positive" if s.tech_signal > 20 else ("tech-negative" if s.tech_signal < -20 else "tech-neutral")
        
        # Format last timestamp (show DD HH:MM)
        try:
            ts_str = str(s.last_update)[:16].replace('T', ' ')  # "2026-01-15 00:15"
            # Extract day and time: "15 00:15"
            if len(ts_str) >= 16:
                last_ts_display = ts_str[8:10] + " " + ts_str[11:16]  # "15 00:15"
            else:
                last_ts_display = ts_str
        except:
            last_ts_display = "-"
        
        table_html += f"""
            <tr>
                <td class="rank-col">{s.rank}</td>
                <td class="coin-col">{s.coin}</td>
                <td class="price-col">{price_str}</td>
                <td class="{change_class}">{change_str}</td>
                <td class="{rsi_class}">{s.rsi:.0f}</td>
                <td class="{rsi_sc_class}">{s.rsi_score:+.0f}</td>
                <td class="{macd_sc_class}">{s.macd_score:+.0f}</td>
                <td class="{bb_sc_class}">{s.bb_score:+.0f}</td>
                <td class="{tech_class}">{s.tech_signal:+.0f}</td>
                <td class="{xgb_long_class}">{s.xgb_long:+.0f}</td>
                <td class="{xgb_short_class}">{s.xgb_short:+.0f}</td>
                <td><span class="{signal_class}">{signal_icon} {s.signal}</span></td>
                <td style="color: #888; font-size: 0.8rem;">{last_ts_display}</td>
            </tr>
        """
    
    table_html += """
        </tbody>
    </table>
    </div>
    """
    
    components.html(table_html, height=650, scrolling=True)
    
    # Legend
    with st.expander("📖 Legend"):
        st.markdown("""
        | Column | Description |
        |--------|-------------|
        | **RSI** | Relative Strength Index (🟢 <30 oversold, 🔴 >70 overbought) |
        | **MACD** | MACD histogram direction (🟢 bullish crossover, 🔴 bearish) |
        | **XGB Long** | XGBoost LONG score (-100 to +100, higher = more bullish) |
        | **XGB Short** | XGBoost SHORT score (-100 to +100, higher = more bearish) |
        | **Signal** | Combined signal: 📈 BUY, 📉 SELL, ➡️ NEUTRAL |
        
        **Signal Calculation:**
        - XGB scores contribute 80% (40% LONG, 40% SHORT inverted)
        - RSI contributes 10% (oversold = bullish)
        - MACD contributes 10%
        """)
