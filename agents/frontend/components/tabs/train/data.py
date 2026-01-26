"""
📊 Train Tab - Step 1: Historical Data

Integrated Historical Data Monitor with full functionality:
- Download progress (15m/1h) with auto-refresh
- Coin inventory
- Chart preview with ALL indicators
- Backfill controls
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from database import (
    get_historical_stats,
    get_backfill_status_all,
    get_historical_ohlcv,
    get_historical_inventory,
    get_historical_symbols_by_volume,
    trigger_backfill,
    trigger_backfill_with_dates,
    check_backfill_running,
    clear_historical_data,
    retry_failed_downloads,
    cleanup_no_data_errors,
    get_training_data_stats,
    EXPECTED_FEATURE_COUNT
)

# Data model display component
from .data_model_display import render_step_data_model


# === CACHED FUNCTIONS ===
# Note: No cache for stats when downloading - use fragment auto-refresh instead
def cached_get_stats():
    """Get stats without cache during active download for real-time updates"""
    return get_historical_stats()


def cached_get_backfill_status():
    """Get backfill status without cache for real-time updates"""
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


def render_data_step():
    """Render Step 1: Historical Data (full integrated version)"""
    
    # Header with cyan style
    st.markdown("""
    <div style="padding: 10px 0;">
        <h3 style="color: #00d4aa; margin: 0;">📊 Step 1: Historical Data</h3>
        <p style="color: #888; font-size: 14px; margin-top: 5px;">
            Download OHLCV data for ML training • 100 top coins by volume
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # === DATA MODEL DISPLAY ===
    render_step_data_model('step1_data')
    
    # === DATE RANGE SELECTION ===
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                padding: 20px; border-radius: 10px; margin: 10px 0;
                border: 1px solid #00d4aa33;">
        <h4 style="color: #00d4aa; margin: 0 0 15px 0;">📅 Select Date Range</h4>
    </div>
    """, unsafe_allow_html=True)
    
    # Default: 12 months of data
    from datetime import date
    default_end = date.today()
    default_start = date(default_end.year - 1, default_end.month, default_end.day)
    
    col_dates = st.columns([1, 1, 1])
    
    with col_dates[0]:
        start_date = st.date_input(
            "📆 Start Date",
            value=default_start,
            min_value=date(2020, 1, 1),
            max_value=default_end,
            key="data_start_date"
        )
    
    with col_dates[1]:
        end_date = st.date_input(
            "📆 End Date", 
            value=default_end,
            min_value=start_date,
            max_value=default_end,
            key="data_end_date"
        )
    
    with col_dates[2]:
        # Calculate duration
        days_diff = (end_date - start_date).days
        months_diff = days_diff / 30
        st.markdown(f"""
        <div style="background: #00d4aa22; padding: 15px; border-radius: 8px; 
                    border-left: 4px solid #00d4aa; margin-top: 28px;">
            <div style="color: #00d4aa; font-weight: bold; font-size: 16px;">
                ⏱️ {days_diff} days
            </div>
            <div style="color: #888; font-size: 12px;">
                ~{months_diff:.1f} months of data
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # === ACTION BUTTONS ===
    b1, b2, b3 = st.columns(3)
    is_running = check_backfill_running()
    
    with b1:
        if is_running:
            st.button("⏳ Downloading...", disabled=True, use_container_width=True, key="data_run_btn")
        else:
            if st.button("🚀 Start Download", type="primary", use_container_width=True, key="data_start_btn"):
                # Save date range to trigger file
                if trigger_backfill_with_dates(start_date, end_date):
                    st.toast("✅ Download started!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ Failed to start download")
    with b2:
        if st.button("🔄 Refresh", use_container_width=True, key="data_refresh_btn"):
            st.cache_data.clear()
            st.rerun()
    with b3:
        if st.button("🗑️ Clear All Data", use_container_width=True, key="data_clear_btn"):
            st.session_state['train_confirm_clear'] = True
    
    # Clear confirmation
    if st.session_state.get('train_confirm_clear'):
        st.error("⚠️ DELETE ALL HISTORICAL DATA?")
        c1, c2 = st.columns(2)
        if c1.button("✅ Yes, Delete", type="primary", key="train_confirm_yes"):
            clear_historical_data()
            st.session_state['train_confirm_clear'] = False
            st.cache_data.clear()
            st.rerun()
        if c2.button("❌ Cancel", key="train_confirm_no"):
            st.session_state['train_confirm_clear'] = False
            st.rerun()
        return
    
    # === OVERVIEW METRICS (Auto-refresh) ===
    st.divider()
    render_overview_metrics()
    
    # === SECTIONS ===
    tab_progress, tab_inventory, tab_preview = st.tabs([
        "📥 Download Progress",
        "📋 Coin Inventory", 
        "📊 Data Preview"
    ])
    
    with tab_progress:
        render_download_progress()
    
    with tab_inventory:
        render_coin_inventory()
    
    with tab_preview:
        render_chart_preview()


@st.fragment(run_every="10s")
def render_overview_metrics():
    """Auto-refresh overview metrics every 10 seconds during download"""
    stats = get_historical_stats()
    
    if not stats.get('exists'):
        st.warning("⚠️ No historical data available")
        st.info("Click **🚀 Start** to download 12 months of data for 100 coins")
        return
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📈 Symbols", stats.get('symbols', 0))
    m2.metric("🕯️ Total Candles", f"{stats.get('total_candles', 0):,}")
    m3.metric("💾 Database Size", f"{stats.get('db_size_mb', 0):.1f} MB")
    
    # Check if download is running and show target dates
    is_running = check_backfill_running()
    if is_running:
        m4.metric("⏳ Status", "Downloading")
    else:
        m4.metric("✅ Status", "Ready")
    
    # Date range - show actual data in DB
    min_d = stats.get('min_date', '')[:10] if stats.get('min_date') else '—'
    max_d = stats.get('max_date', '')[:10] if stats.get('max_date') else '—'
    
    # Get download target dates from session state if available
    start_date = st.session_state.get('data_start_date')
    end_date = st.session_state.get('data_end_date')
    
    if start_date and end_date and is_running:
        st.caption(f"🎯 **Download Target:** {start_date} → {end_date} | 📊 **DB Actual:** {min_d} → {max_d} | 🔄 Auto-refresh 10s")
    else:
        st.caption(f"📅 **Data in DB:** {min_d} → {max_d} | 🔄 Auto-refresh every 10s")
    
    # === FEATURE REMINDER BOX ===
    feature_stats = get_training_data_stats()
    if feature_stats.get('exists'):
        feat_count = feature_stats.get('feature_count', 0)
        expected = EXPECTED_FEATURE_COUNT
        is_ok = feat_count >= expected - 5
        
        status_icon = "✅" if is_ok else "⚠️"
        color = "#00d4aa" if is_ok else "#ffaa00"
        
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                    padding: 12px 16px; border-radius: 8px; margin: 10px 0;
                    border-left: 4px solid {color};">
            <span style="font-size: 14px; color: {color}; font-weight: bold;">
                {status_icon} Phase 1 Output: <code style="background: #333; padding: 2px 6px; border-radius: 4px;">training_data</code>
            </span>
            <span style="color: #888; margin-left: 15px;">
                📊 <b>{feat_count}</b> features (expected: {expected}) | 
                📁 {feature_stats.get('row_count', 0):,} rows | 
                🪙 {feature_stats.get('symbol_count', 0)} symbols
            </span>
        </div>
        """, unsafe_allow_html=True)


@st.fragment(run_every="10s")
def render_download_progress():
    """Show download progress with clear 15m/1h separation"""
    
    status_list = get_backfill_status_all()
    
    if not status_list:
        st.info("⏳ No backfill status. Click Start to begin downloading.")
        return
    
    df = pd.DataFrame(status_list)
    
    # Separate by timeframe
    df_15m = df[df['timeframe'] == '15m']
    df_1h = df[df['timeframe'] == '1h']
    
    def count_status(df_tf):
        complete = len(df_tf[df_tf['status'] == 'COMPLETE'])
        skipped = len(df_tf[df_tf['status'] == 'SKIPPED'])
        return {
            'complete': complete,
            'skipped': skipped,
            'done': complete + skipped,  # Both count as "done"
            'in_progress': len(df_tf[df_tf['status'] == 'IN_PROGRESS']),
            'pending': len(df_tf[df_tf['status'] == 'PENDING']),
            'error': len(df_tf[df_tf['status'] == 'ERROR']),
            'total': len(df_tf)
        }
    
    stats_15m = count_status(df_15m)
    stats_1h = count_status(df_1h)
    
    total_candles_15m = df_15m['total_candles'].sum() if 'total_candles' in df_15m.columns else 0
    total_candles_1h = df_1h['total_candles'].sum() if 'total_candles' in df_1h.columns else 0
    
    col_15m, col_1h = st.columns(2)
    
    with col_15m:
        st.markdown("#### ⏱️ 15 Minutes")
        # Progress uses 'done' = complete + skipped
        pct_15m = stats_15m['done'] / stats_15m['total'] if stats_15m['total'] > 0 else 0
        st.progress(pct_15m)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Complete", f"{stats_15m['complete']}/{stats_15m['total']}")
        c2.metric("Candles", f"{total_candles_15m:,}")
        if stats_15m['error'] > 0:
            c3.metric("Errors", stats_15m['error'])
        elif stats_15m['in_progress'] > 0:
            c3.metric("Status", "🔄 Downloading")
        elif stats_15m['pending'] > 0:
            c3.metric("Status", "⏳ Pending")
        else:
            c3.metric("Status", "✅ Done")
    
    with col_1h:
        st.markdown("#### ⏱️ 1 Hour")
        # Progress uses 'done' = complete + skipped
        pct_1h = stats_1h['done'] / stats_1h['total'] if stats_1h['total'] > 0 else 0
        st.progress(pct_1h)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Complete", f"{stats_1h['complete']}/{stats_1h['total']}")
        c2.metric("Candles", f"{total_candles_1h:,}")
        if stats_1h['error'] > 0:
            c3.metric("Errors", stats_1h['error'])
        elif stats_1h['in_progress'] > 0:
            c3.metric("Status", "🔄 Downloading")
        elif stats_1h['pending'] > 0:
            c3.metric("Status", "⏳ Pending")
        else:
            c3.metric("Status", "✅ Done")
    
    # Current download
    in_progress = df[df['status'] == 'IN_PROGRESS']
    if not in_progress.empty:
        row = in_progress.iloc[0]
        sym = row['symbol'].replace('/USDT:USDT', '')
        tf = row['timeframe']
        candles = row.get('total_candles', 0)
        st.info(f"🔄 **Currently downloading:** {sym} [{tf}] — {candles:,} candles")
    
    # Errors
    errors = df[df['status'] == 'ERROR']
    if len(errors) > 0:
        with st.expander(f"❌ {len(errors)} Errors", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔄 Retry Failed Downloads", type="primary", use_container_width=True, key="retry_failed"):
                    count = retry_failed_downloads()
                    if count > 0:
                        st.toast(f"✅ Reset {count} failed downloads")
                        trigger_backfill()
                        st.cache_data.clear()
                        st.rerun()
            with c2:
                if st.button("🗑️ Remove 'No Data' Coins", use_container_width=True, key="cleanup_no_data"):
                    converted, removed = cleanup_no_data_errors()
                    if converted > 0 or removed > 0:
                        st.toast(f"✅ Fixed {converted} errors, removed {removed} coins from list")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.toast("ℹ️ No 'no data' errors found to clean up")
            
            st.divider()
            for _, row in errors.iterrows():
                sym = row['symbol'].replace('/USDT:USDT', '')
                msg = row.get('error_message', 'Unknown')
                st.error(f"**{sym}** [{row['timeframe']}]: {msg}")


@st.fragment(run_every="60s")
def render_coin_inventory():
    """Show table with 15m and 1h data per coin (optimized with dataframe)"""
    
    inventory = get_historical_inventory()
    
    if not inventory:
        st.warning("⚠️ No data inventory available")
        return
    
    rows = []
    complete_count = 0
    partial_count = 0
    
    for item in inventory:
        sym = item['symbol'].replace('/USDT:USDT', '')
        candles_15m = item.get('candles_15m', 0) or 0
        candles_1h = item.get('candles_1h', 0) or 0
        
        from_date = item.get('from_date_15m', '') or item.get('from_date_1h', '')
        to_date = item.get('to_date_15m', '') or item.get('to_date_1h', '')
        
        if from_date:
            from_date = from_date[:10]
        if to_date:
            to_date = to_date[:10]
        
        expected_15m = 35000
        expected_1h = 8760
        
        pct_15m = min(100, (candles_15m / expected_15m) * 100)
        pct_1h = min(100, (candles_1h / expected_1h) * 100)
        
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
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Coins", len(rows))
    c2.metric("Complete", complete_count)
    c3.metric("Partial", partial_count)
    c4.metric("Pending", len(rows) - complete_count - partial_count)
    
    if rows:
        df = pd.DataFrame(rows)
        df = df.sort_values('Rank')
        
        # Format columns
        df['15m%'] = df['15m%'].apply(lambda x: f"{x:.0f}%")
        df['1h%'] = df['1h%'].apply(lambda x: f"{x:.0f}%")
        df['15m'] = df['15m'].apply(lambda x: f"{x:,}")
        df['1h'] = df['1h'].apply(lambda x: f"{x:,}")
        
        st.markdown(f"**📋 All {len(rows)} Coins (Full Details):**")
        
        # Build full Markdown table
        md_table = "| # | Symbol | From | To | 15m Candles | 15m % | 1h Candles | 1h % | Status |\n"
        md_table += "|:--:|:-----:|:----:|:--:|:----------:|:-----:|:---------:|:----:|:------:|\n"
        
        for _, row in df.iterrows():
            md_table += f"| {row['Rank']} | **{row['Symbol']}** | {row['From']} | {row['To']} | {row['15m']} | {row['15m%']} | {row['1h']} | {row['1h%']} | {row['Status']} |\n"
        
        # Display in scrollable container
        st.markdown(md_table)


def render_chart_preview():
    """Show preview charts with indicators"""
    
    symbols = cached_get_symbols()
    
    if not symbols:
        st.info("No data available")
        return
    
    c1, c2, c3 = st.columns([2, 1, 1])
    
    with c1:
        symbol = st.selectbox(
            "Select Coin",
            symbols,
            format_func=lambda x: x.replace('/USDT:USDT', ''),
            key="train_preview_symbol"
        )
    with c2:
        timeframe = st.selectbox("Timeframe", ["15m", "1h"], key="train_preview_tf")
    with c3:
        limit = st.selectbox("Candles", [500, 1000, 2000], key="train_preview_limit")
    
    if not symbol:
        return
    
    df = cached_get_ohlcv(symbol, timeframe, limit)
    
    if df is None or len(df) == 0:
        st.warning(f"No data for {symbol}")
        return
    
    sym_short = symbol.replace('/USDT:USDT', '')
    st.markdown(f"### 📊 {sym_short} [{timeframe}] — {len(df):,} candles")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📅 From", str(df.index.min())[:10])
    c2.metric("📅 To", str(df.index.max())[:10])
    c3.metric("💰 Last", f"${df['close'].iloc[-1]:,.2f}")
    c4.metric("📊 Avg Vol", f"{df['volume'].mean():,.0f}")
    
    # Candlestick chart
    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='OHLC',
        increasing_line_color='#26a69a',
        decreasing_line_color='#ef5350'
    ))
    
    # Add MAs if available
    if 'SMA_20' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', line=dict(color='orange', width=1)))
    if 'SMA_50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], name='SMA 50', line=dict(color='purple', width=1)))
    
    # Add BBands if available
    if 'BB_upper' in df.columns and 'BB_lower' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_upper'], name='BB Upper', line=dict(color='rgba(173,216,230,0.5)', width=1)))
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_lower'], name='BB Lower', line=dict(color='rgba(173,216,230,0.5)', width=1), fill='tonexty', fillcolor='rgba(173,216,230,0.1)'))
    
    fig.update_layout(
        height=400,
        xaxis_rangeslider_visible=False,
        margin=dict(t=10, b=30, l=50, r=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(gridcolor='rgba(128,128,128,0.2)'),
        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', title='Price'),
        legend=dict(orientation='h', y=1.02, x=0.5, xanchor='center')
    )
    
    st.plotly_chart(fig, width='stretch')
    
    # RSI if available
    if 'RSI' in df.columns:
        st.markdown("#### 📈 RSI")
        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='cyan', width=1)))
        fig_rsi.add_hline(y=70, line_dash='dash', line_color='red')
        fig_rsi.add_hline(y=30, line_dash='dash', line_color='green')
        
        fig_rsi.update_layout(
            height=200,
            margin=dict(t=10, b=30, l=50, r=30),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(range=[0, 100], title='RSI'),
            showlegend=False
        )
        st.plotly_chart(fig_rsi, width='stretch')
    
    # Data sample
    st.markdown("#### 📋 Data Sample")
    
    all_cols = list(df.columns)
    base_cols = {'open', 'high', 'low', 'close', 'volume'}
    indicator_cols = [c for c in all_cols if c.lower() not in base_cols]
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Columns", len(all_cols))
    c2.metric("Indicators", len(indicator_cols))
    c3.metric("Rows Shown", "20 (10+10)")
    
    # Show available columns
    with st.expander("📊 Available Columns", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**OHLCV (Base):**")
            st.code("open, high, low, close, volume")
        with col_b:
            st.markdown("**Indicators:**")
            st.code(", ".join(indicator_cols) if indicator_cols else "None")
    
    # Get display columns
    display_cols = ['timestamp'] + [c for c in all_cols]
    
    # === FIRST 10 CANDLES (Oldest) ===
    st.markdown("**🔼 First 10 Candles (oldest data) - ALL COLUMNS**")
    first_df = df.head(10).copy()
    first_df = first_df.reset_index()
    first_df.rename(columns={'index': 'timestamp'}, inplace=True)
    first_df['timestamp'] = first_df['timestamp'].astype(str).str[:19]
    first_df = first_df.round(4)
    
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
    
    # === LAST 10 CANDLES (Newest) ===
    st.markdown("**🔽 Last 10 Candles (newest data) - ALL COLUMNS**")
    last_df = df.tail(10).copy()
    last_df = last_df.reset_index()
    last_df.rename(columns={'index': 'timestamp'}, inplace=True)
    last_df['timestamp'] = last_df['timestamp'].astype(str).str[:19]
    last_df = last_df.round(4)
    
    html_last = last_df.to_html(index=False, classes='dataframe')
    st.markdown(f"""
    <div style="overflow-x: auto; max-width: 100%;">
        {html_last}
    </div>
    """, unsafe_allow_html=True)
    
    # Show total column count
    st.success(f"📊 **{len(all_cols)} total columns** ({len(indicator_cols)} indicators + OHLCV)")


__all__ = ['render_data_step']
