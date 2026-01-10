"""
📊 Historical Data Tab - ML Training Data Monitor

Fast loading with optimized caching and clear 15m/1h visualization.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

from database import (
    get_historical_stats,
    get_backfill_status_all,
    get_historical_ohlcv,
    get_historical_inventory,
    get_historical_symbols_by_volume,
    get_symbol_data_quality,
    trigger_backfill,
    check_backfill_running,
    clear_historical_data,
    retry_failed_downloads
)


# === CACHED FUNCTIONS (longer TTL to avoid frequent refresh) ===
@st.cache_data(ttl=120)
def cached_get_stats():
    return get_historical_stats()


@st.cache_data(ttl=60)
def cached_get_backfill_status():
    return get_backfill_status_all()


@st.cache_data(ttl=300)
def cached_get_inventory():
    return get_historical_inventory()


@st.cache_data(ttl=300)
def cached_get_symbols():
    return get_historical_symbols_by_volume()


@st.cache_data(ttl=300)
def cached_get_ohlcv(symbol, timeframe, limit):
    return get_historical_ohlcv(symbol, timeframe, limit)


def render_historical_data_tab():
    """Render the Historical Data monitoring tab"""
    
    # Header with actions
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("## 📊 Historical Data")
        st.caption("ML Training Data • 12 months OHLCV • 100 coins")
    
    with col2:
        b1, b2, b3 = st.columns(3)
        is_running = check_backfill_running()
        
        with b1:
            if is_running:
                st.button("⏳ Running...", disabled=True, use_container_width=True)
            else:
                if st.button("🚀 Start", type="primary", use_container_width=True):
                    if trigger_backfill():
                        st.toast("✅ Backfill started!")
                        st.cache_data.clear()
                        st.rerun()
        with b2:
            if st.button("🔄 Refresh", type="secondary", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        with b3:
            if st.button("🗑️ Clear", type="secondary", use_container_width=True):
                st.session_state['confirm_clear'] = True
    
    # Clear confirmation
    if st.session_state.get('confirm_clear'):
        st.error("⚠️ DELETE ALL HISTORICAL DATA?")
        c1, c2 = st.columns(2)
        if c1.button("✅ Yes, Delete", type="primary"):
            clear_historical_data()
            st.session_state['confirm_clear'] = False
            st.cache_data.clear()
            st.rerun()
        if c2.button("❌ Cancel"):
            st.session_state['confirm_clear'] = False
            st.rerun()
        return
    
    # Get stats
    stats = cached_get_stats()
    
    if not stats.get('exists'):
        st.warning("⚠️ No historical data available")
        st.info("Click **🚀 Start** to download 12 months of data for 100 coins")
        return
    
    # === OVERVIEW METRICS ===
    st.divider()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("📈 Symbols", stats.get('symbols', 0))
    m2.metric("🕯️ Total Candles", f"{stats.get('total_candles', 0):,}")
    m3.metric("💾 Database Size", f"{stats.get('db_size_mb', 0):.1f} MB")
    
    # Date range
    min_d = stats.get('min_date', '')[:10] if stats.get('min_date') else '—'
    max_d = stats.get('max_date', '')[:10] if stats.get('max_date') else '—'
    st.caption(f"📅 Data range: **{min_d}** → **{max_d}**")
    
    # === DOWNLOAD PROGRESS (15m & 1h separate) ===
    st.divider()
    st.markdown("### 📥 Download Progress")
    
    render_download_progress()
    
    # === COIN INVENTORY ===
    st.divider()
    st.markdown("### 📋 Data Inventory by Coin")
    
    render_coin_inventory()
    
    # === CHART PREVIEW ===
    st.divider()
    st.markdown("### 📊 Data Preview")
    
    render_chart_preview()


@st.fragment(run_every="15s")
def render_download_progress():
    """Show download progress with clear 15m/1h separation - auto-refreshes every 15s"""
    
    status_list = get_backfill_status_all()  # Direct call, fragment handles refresh
    
    if not status_list:
        st.info("⏳ No backfill status. Click Start to begin downloading.")
        return
    
    df = pd.DataFrame(status_list)
    
    # Separate by timeframe
    df_15m = df[df['timeframe'] == '15m']
    df_1h = df[df['timeframe'] == '1h']
    
    # Count statuses
    def count_status(df_tf):
        return {
            'complete': len(df_tf[df_tf['status'] == 'COMPLETE']),
            'in_progress': len(df_tf[df_tf['status'] == 'IN_PROGRESS']),
            'pending': len(df_tf[df_tf['status'] == 'PENDING']),
            'error': len(df_tf[df_tf['status'] == 'ERROR']),
            'total': len(df_tf)
        }
    
    stats_15m = count_status(df_15m)
    stats_1h = count_status(df_1h)
    
    # Total candles
    total_candles_15m = df_15m['total_candles'].sum() if 'total_candles' in df_15m.columns else 0
    total_candles_1h = df_1h['total_candles'].sum() if 'total_candles' in df_1h.columns else 0
    
    # Two columns for 15m and 1h
    col_15m, col_1h = st.columns(2)
    
    with col_15m:
        st.markdown("#### ⏱️ 15 Minutes")
        
        pct_15m = stats_15m['complete'] / stats_15m['total'] if stats_15m['total'] > 0 else 0
        st.progress(pct_15m)
        
        # Stats row
        c1, c2, c3 = st.columns(3)
        c1.metric("Complete", f"{stats_15m['complete']}/{stats_15m['total']}")
        c2.metric("Candles", f"{total_candles_15m:,}")
        if stats_15m['error'] > 0:
            c3.metric("Errors", stats_15m['error'], delta=None)
        elif stats_15m['in_progress'] > 0:
            c3.metric("Status", "🔄 Downloading")
        else:
            c3.metric("Status", "✅ Done" if pct_15m == 1 else "⏳ Pending")
    
    with col_1h:
        st.markdown("#### ⏱️ 1 Hour")
        
        pct_1h = stats_1h['complete'] / stats_1h['total'] if stats_1h['total'] > 0 else 0
        st.progress(pct_1h)
        
        # Stats row
        c1, c2, c3 = st.columns(3)
        c1.metric("Complete", f"{stats_1h['complete']}/{stats_1h['total']}")
        c2.metric("Candles", f"{total_candles_1h:,}")
        if stats_1h['error'] > 0:
            c3.metric("Errors", stats_1h['error'])
        elif stats_1h['in_progress'] > 0:
            c3.metric("Status", "🔄 Downloading")
        else:
            c3.metric("Status", "✅ Done" if pct_1h == 1 else "⏳ Pending")
    
    # Current download info
    in_progress = df[df['status'] == 'IN_PROGRESS']
    if not in_progress.empty:
        row = in_progress.iloc[0]
        sym = row['symbol'].replace('/USDT:USDT', '')
        tf = row['timeframe']
        candles = row.get('total_candles', 0)
        st.info(f"🔄 **Currently downloading:** {sym} [{tf}] — {candles:,} candles")
    
    # Error list with retry button
    errors = df[df['status'] == 'ERROR']
    if len(errors) > 0:
        with st.expander(f"❌ {len(errors)} Errors - Click to view", expanded=True):
            # Retry button
            if st.button("🔄 Retry Failed Downloads", type="primary", use_container_width=True):
                count = retry_failed_downloads()
                if count > 0:
                    st.toast(f"✅ Reset {count} failed downloads to PENDING")
                    # Trigger backfill to reprocess
                    trigger_backfill()
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("No errors to retry")
            
            st.divider()
            
            # Error details
            for _, row in errors.iterrows():
                sym = row['symbol'].replace('/USDT:USDT', '')
                msg = row.get('error_message', 'Unknown error')
                st.error(f"**{sym}** [{row['timeframe']}]: {msg}")


@st.fragment(run_every="30s")
def render_coin_inventory():
    """Show table with 15m and 1h data per coin - auto-refreshes every 30s"""
    
    # Direct call, fragment handles refresh
    inventory = get_historical_inventory()
    
    if not inventory:
        st.warning("⚠️ No data inventory available - database may be empty")
        return
    
    # Process data
    rows = []
    complete_count = 0
    partial_count = 0
    
    for item in inventory:
        sym = item['symbol'].replace('/USDT:USDT', '')
        candles_15m = item.get('candles_15m', 0) or 0
        candles_1h = item.get('candles_1h', 0) or 0
        
        # Date ranges (format: YYYY-MM-DD)
        from_date = item.get('from_date_15m', '') or item.get('from_date_1h', '')
        to_date = item.get('to_date_15m', '') or item.get('to_date_1h', '')
        
        # Format dates (short)
        if from_date:
            from_date = from_date[:10]  # YYYY-MM-DD
        if to_date:
            to_date = to_date[:10]
        
        # Expected candles (approx 12 months)
        expected_15m = 35000
        expected_1h = 8760
        
        pct_15m = min(100, (candles_15m / expected_15m) * 100)
        pct_1h = min(100, (candles_1h / expected_1h) * 100)
        
        # Status
        if pct_15m >= 95 and pct_1h >= 95:
            status = "✅"
            complete_count += 1
        elif candles_15m > 0 or candles_1h > 0:
            status = "🔄"
            partial_count += 1
        else:
            status = "⏳"
        
        rows.append({
            'Rank': item.get('rank', 999),
            'Symbol': sym,
            'From': from_date or '-',
            'To': to_date or '-',
            '15m': candles_15m,
            '15m%': pct_15m,
            '1h': candles_1h,
            '1h%': pct_1h,
            'Status': status
        })
    
    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Coins", len(rows))
    c2.metric("Complete", complete_count)
    c3.metric("Partial", partial_count)
    c4.metric("Pending", len(rows) - complete_count - partial_count)
    
    # Show coin list - simple st.table (this worked before)
    if rows:
        # Create dataframe
        df = pd.DataFrame(rows)
        
        # Sort by rank and use Rank as index to hide row numbers
        df = df.sort_values('Rank')
        df = df.set_index('Rank')  # This hides the row number column
        
        # Format for display
        df['15m%'] = df['15m%'].apply(lambda x: f"{x:.0f}%")
        df['1h%'] = df['1h%'].apply(lambda x: f"{x:.0f}%")
        df['15m'] = df['15m'].apply(lambda x: f"{x:,}")
        df['1h'] = df['1h'].apply(lambda x: f"{x:,}")
        
        # Simple table display
        st.markdown(f"**📋 All {len(rows)} Coins:**")
        st.table(df)
        
    else:
        st.warning("⚠️ No coins found in inventory")


def check_indicators_in_db(df):
    """Check if DataFrame has pre-computed indicators from database"""
    required_indicators = ['SMA_20', 'RSI', 'MACD', 'ATR']
    has_indicators = all(col in df.columns for col in required_indicators)
    
    # Also check if values are not all null
    if has_indicators:
        for col in required_indicators:
            if df[col].notna().sum() > 0:
                return True
    return False


def render_chart_preview():
    """Show preview charts with ALL technical indicators (pre-computed from database)"""
    
    symbols = cached_get_symbols()
    
    if not symbols:
        st.info("No data available for preview")
        return
    
    # Selectors in row
    c1, c2, c3 = st.columns([2, 1, 1])
    
    with c1:
        symbol = st.selectbox(
            "Select Coin",
            symbols,
            format_func=lambda x: x.replace('/USDT:USDT', ''),
            key="hist_preview_symbol"
        )
    with c2:
        timeframe = st.selectbox("Timeframe", ["15m", "1h"], key="hist_preview_tf")
    with c3:
        limit = st.selectbox("Last N candles", [500, 1000, 2000], key="hist_preview_limit")
    
    if not symbol:
        return
    
    # Get data directly from DB (includes pre-computed indicators)
    df = cached_get_ohlcv(symbol, timeframe, limit)
    
    if df is None or len(df) == 0:
        st.warning(f"No data available for {symbol}")
        return
    
    # Check if indicators are available in database
    has_db_indicators = check_indicators_in_db(df)
    
    if has_db_indicators:
        st.success("📊 Using **pre-computed indicators** from database (faster)")
    else:
        st.warning("⚠️ Indicators not yet saved in database. Re-run backfill with --force to compute.")
    
    # Info row
    sym_short = symbol.replace('/USDT:USDT', '')
    
    # Data stats
    st.markdown(f"### 📊 {sym_short} [{timeframe}] — {len(df):,} candles")
    
    # Date range and stats
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📅 From", str(df.index.min())[:10])
    c2.metric("📅 To", str(df.index.max())[:10])
    c3.metric("💰 Last Price", f"${df['close'].iloc[-1]:,.2f}")
    c4.metric("📊 Avg Volume", f"{df['volume'].mean():,.0f}")
    c5.metric("📈 ATR", f"{df['ATR'].iloc[-1]:.2f}" if not pd.isna(df['ATR'].iloc[-1]) else "N/A")
    
    # === CHART 1: Candlestick with Bollinger Bands and MAs ===
    st.markdown("#### 🕯️ Price + Bollinger Bands + Moving Averages")
    
    fig1 = go.Figure()
    
    # Candlestick
    fig1.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='OHLC',
        increasing_line_color='#26a69a',
        decreasing_line_color='#ef5350'
    ))
    
    # Bollinger Bands
    fig1.add_trace(go.Scatter(x=df.index, y=df['BB_upper'], name='BB Upper', line=dict(color='rgba(173,216,230,0.5)', width=1)))
    fig1.add_trace(go.Scatter(x=df.index, y=df['BB_lower'], name='BB Lower', line=dict(color='rgba(173,216,230,0.5)', width=1), fill='tonexty', fillcolor='rgba(173,216,230,0.1)'))
    
    # Moving Averages
    fig1.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', line=dict(color='orange', width=1)))
    fig1.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], name='SMA 50', line=dict(color='purple', width=1)))
    
    fig1.update_layout(
        height=400,
        xaxis_rangeslider_visible=False,
        margin=dict(t=10, b=30, l=50, r=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(gridcolor='rgba(128,128,128,0.2)'),
        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', title='Price'),
        legend=dict(orientation='h', y=1.02, x=0.5, xanchor='center')
    )
    
    st.plotly_chart(fig1, use_container_width=True)
    
    # === CHART 2: Volume ===
    st.markdown("#### 📊 Volume")
    
    colors = ['#26a69a' if c >= o else '#ef5350' for c, o in zip(df['close'], df['open'])]
    
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=df.index, y=df['volume'], name='Volume', marker_color=colors))
    fig2.add_trace(go.Scatter(x=df.index, y=df['Volume_SMA'], name='Vol SMA 20', line=dict(color='yellow', width=1)))
    
    fig2.update_layout(
        height=200,
        margin=dict(t=10, b=30, l=50, r=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(gridcolor='rgba(128,128,128,0.2)'),
        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', title='Volume'),
        showlegend=False
    )
    
    st.plotly_chart(fig2, use_container_width=True)
    
    # === CHART 3: RSI ===
    st.markdown("#### 📈 RSI (Relative Strength Index)")
    
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='cyan', width=1)))
    fig3.add_hline(y=70, line_dash='dash', line_color='red', annotation_text='Overbought')
    fig3.add_hline(y=30, line_dash='dash', line_color='green', annotation_text='Oversold')
    fig3.add_hrect(y0=30, y1=70, fillcolor='rgba(128,128,128,0.1)', line_width=0)
    
    fig3.update_layout(
        height=200,
        margin=dict(t=10, b=30, l=50, r=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(gridcolor='rgba(128,128,128,0.2)'),
        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', title='RSI', range=[0, 100]),
        showlegend=False
    )
    
    st.plotly_chart(fig3, use_container_width=True)
    
    # === CHART 4: MACD ===
    st.markdown("#### 📉 MACD")
    
    macd_colors = ['#26a69a' if v >= 0 else '#ef5350' for v in df['MACD_hist']]
    
    fig4 = go.Figure()
    fig4.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], name='MACD Histogram', marker_color=macd_colors))
    fig4.add_trace(go.Scatter(x=df.index, y=df['MACD'], name='MACD', line=dict(color='blue', width=1)))
    fig4.add_trace(go.Scatter(x=df.index, y=df['MACD_signal'], name='Signal', line=dict(color='orange', width=1)))
    
    fig4.update_layout(
        height=200,
        margin=dict(t=10, b=30, l=50, r=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(gridcolor='rgba(128,128,128,0.2)'),
        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', title='MACD'),
        legend=dict(orientation='h', y=1.02, x=0.5, xanchor='center')
    )
    
    st.plotly_chart(fig4, use_container_width=True)
    
    # === CHART 5: Stochastic ===
    st.markdown("#### 🔄 Stochastic Oscillator")
    
    fig5 = go.Figure()
    fig5.add_trace(go.Scatter(x=df.index, y=df['Stoch_K'], name='%K', line=dict(color='cyan', width=1)))
    fig5.add_trace(go.Scatter(x=df.index, y=df['Stoch_D'], name='%D', line=dict(color='orange', width=1)))
    fig5.add_hline(y=80, line_dash='dash', line_color='red')
    fig5.add_hline(y=20, line_dash='dash', line_color='green')
    
    fig5.update_layout(
        height=200,
        margin=dict(t=10, b=30, l=50, r=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(gridcolor='rgba(128,128,128,0.2)'),
        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', title='Stochastic', range=[0, 100]),
        legend=dict(orientation='h', y=1.02, x=0.5, xanchor='center')
    )
    
    st.plotly_chart(fig5, use_container_width=True)
    
    # === CHART 6: ATR ===
    st.markdown("#### 📐 ATR (Average True Range - Volatility)")
    
    fig6 = go.Figure()
    fig6.add_trace(go.Scatter(x=df.index, y=df['ATR'], name='ATR', line=dict(color='magenta', width=1), fill='tozeroy', fillcolor='rgba(255,0,255,0.1)'))
    
    fig6.update_layout(
        height=200,
        margin=dict(t=10, b=30, l=50, r=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(gridcolor='rgba(128,128,128,0.2)'),
        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', title='ATR'),
        showlegend=False
    )
    
    st.plotly_chart(fig6, use_container_width=True)
    
    # === DATA TABLE (raw sample) ===
    st.markdown("#### 📋 Raw Data Sample - ALL Indicators")
    
    # Get ALL columns dynamically from dataframe (excluding index)
    all_available_cols = list(df.columns)
    
    # Count indicators (exclude OHLCV base columns)
    base_cols = {'open', 'high', 'low', 'close', 'volume'}
    indicator_count = len([c for c in all_available_cols if c.lower() not in base_cols])
    
    # Summary stats first
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Total Candles", f"{len(df):,}")
    sc2.metric("Date Range", f"{(df.index.max() - df.index.min()).days} days")
    sc3.metric("Price Range", f"${df['low'].min():,.2f} - ${df['high'].max():,.2f}")
    sc4.metric("Total Indicators", f"{indicator_count}")
    
    st.divider()
    
    # First 10 candles - HTML table with scroll (ALL columns)
    st.markdown("**🔼 First 10 Candles (oldest data) - ALL COLUMNS**")
    first_df = df.head(10).copy()
    first_df = first_df.reset_index()
    first_df['timestamp'] = first_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
    
    # Use all columns
    display_cols = ['timestamp'] + [c for c in all_available_cols if c in first_df.columns]
    first_df = first_df[display_cols].round(4)
    
    # Convert to HTML with horizontal scroll
    html_first = first_df.to_html(index=False, classes='dataframe')
    st.markdown(f"""
    <div style="overflow-x: auto; max-width: 100%;">
        <style>
            .dataframe {{ font-size: 11px; border-collapse: collapse; width: 100%; }}
            .dataframe th {{ background-color: #1e1e1e; color: #00ff88; padding: 6px; text-align: left; border: 1px solid #333; white-space: nowrap; }}
            .dataframe td {{ padding: 4px; border: 1px solid #333; color: #ffffff; background-color: #0e1117; white-space: nowrap; }}
        </style>
        {html_first}
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # Last 10 candles - HTML table with scroll
    st.markdown("**🔽 Last 10 Candles (newest data) - ALL COLUMNS**")
    last_df = df.tail(10).copy()
    last_df = last_df.reset_index()
    last_df['timestamp'] = last_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
    last_df = last_df[display_cols].round(4)
    
    html_last = last_df.to_html(index=False, classes='dataframe')
    st.markdown(f"""
    <div style="overflow-x: auto; max-width: 100%;">
        {html_last}
    </div>
    """, unsafe_allow_html=True)
    
    # Show total column count
    st.success(f"📊 **{len(display_cols)} total columns** ({indicator_count} indicators + OHLCV)")


# Export
__all__ = ['render_historical_data_tab']
