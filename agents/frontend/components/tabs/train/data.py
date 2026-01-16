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
    check_backfill_running,
    clear_historical_data,
    retry_failed_downloads
)


# === CACHED FUNCTIONS ===
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


def render_data_step():
    """Render Step 1: Historical Data (full integrated version)"""
    
    # Header with actions
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("### 📊 Step 1: Historical Data")
        st.caption("ML Training Data • 12 months OHLCV • 100 coins")
    
    with col2:
        b1, b2, b3 = st.columns(3)
        is_running = check_backfill_running()
        
        with b1:
            if is_running:
                st.button("⏳ Running...", disabled=True, use_container_width=True, key="data_run_btn")
            else:
                if st.button("🚀 Start", type="primary", use_container_width=True, key="data_start_btn"):
                    if trigger_backfill():
                        st.toast("✅ Backfill started!")
                        st.cache_data.clear()
                        st.rerun()
        with b2:
            if st.button("🔄 Refresh", type="secondary", use_container_width=True, key="data_refresh_btn"):
                st.cache_data.clear()
                st.rerun()
        with b3:
            if st.button("🗑️ Clear", type="secondary", use_container_width=True, key="data_clear_btn"):
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


@st.fragment(run_every="15s")
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
        return {
            'complete': len(df_tf[df_tf['status'] == 'COMPLETE']),
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
        pct_15m = stats_15m['complete'] / stats_15m['total'] if stats_15m['total'] > 0 else 0
        st.progress(pct_15m)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Complete", f"{stats_15m['complete']}/{stats_15m['total']}")
        c2.metric("Candles", f"{total_candles_15m:,}")
        if stats_15m['error'] > 0:
            c3.metric("Errors", stats_15m['error'])
        elif stats_15m['in_progress'] > 0:
            c3.metric("Status", "🔄 Downloading")
        else:
            c3.metric("Status", "✅ Done" if pct_15m == 1 else "⏳ Pending")
    
    with col_1h:
        st.markdown("#### ⏱️ 1 Hour")
        pct_1h = stats_1h['complete'] / stats_1h['total'] if stats_1h['total'] > 0 else 0
        st.progress(pct_1h)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Complete", f"{stats_1h['complete']}/{stats_1h['total']}")
        c2.metric("Candles", f"{total_candles_1h:,}")
        if stats_1h['error'] > 0:
            c3.metric("Errors", stats_1h['error'])
        elif stats_1h['in_progress'] > 0:
            c3.metric("Status", "🔄 Downloading")
        else:
            c3.metric("Status", "✅ Done" if pct_1h == 1 else "⏳ Pending")
    
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
            if st.button("🔄 Retry Failed Downloads", type="primary", use_container_width=True, key="retry_failed"):
                count = retry_failed_downloads()
                if count > 0:
                    st.toast(f"✅ Reset {count} failed downloads")
                    trigger_backfill()
                    st.cache_data.clear()
                    st.rerun()
            
            st.divider()
            for _, row in errors.iterrows():
                sym = row['symbol'].replace('/USDT:USDT', '')
                msg = row.get('error_message', 'Unknown')
                st.error(f"**{sym}** [{row['timeframe']}]: {msg}")


@st.fragment(run_every="30s")
def render_coin_inventory():
    """Show table with 15m and 1h data per coin"""
    
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
        df = df.set_index('Rank')
        
        df['15m%'] = df['15m%'].apply(lambda x: f"{x:.0f}%")
        df['1h%'] = df['1h%'].apply(lambda x: f"{x:.0f}%")
        df['15m'] = df['15m'].apply(lambda x: f"{x:,}")
        df['1h'] = df['1h'].apply(lambda x: f"{x:,}")
        
        st.markdown(f"**📋 All {len(rows)} Coins:**")
        st.table(df)


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
    
    st.plotly_chart(fig, use_container_width=True)
    
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
        st.plotly_chart(fig_rsi, use_container_width=True)
    
    # Data sample
    st.markdown("#### 📋 Data Sample")
    
    all_cols = list(df.columns)
    base_cols = {'open', 'high', 'low', 'close', 'volume'}
    indicator_count = len([c for c in all_cols if c.lower() not in base_cols])
    
    c1, c2 = st.columns(2)
    c1.metric("Total Columns", len(all_cols))
    c2.metric("Indicators", indicator_count)
    
    # Show last 5 rows
    st.dataframe(df.tail(5), use_container_width=True)


__all__ = ['render_data_step']
