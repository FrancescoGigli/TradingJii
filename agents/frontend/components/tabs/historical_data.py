"""
📊 Historical Data Tab - ML Training Data Monitor

Displays status and quality of historical OHLCV data for ML training:
- Backfill progress for all symbols
- Data quality heatmap
- Price chart verification
- Gap detection
- Statistics overview

Beautiful dark theme with modern UI components.
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

from database import (
    get_historical_stats,
    get_backfill_status_all,
    get_historical_ohlcv,
    get_historical_symbols,
    get_backfill_summary
)
from styles.colors import PALETTE, SIGNAL_COLORS

# Simple color map for the UI
COLORS = {
    'success': PALETTE['accent_green'],
    'warning': PALETTE['accent_yellow'],
    'danger': PALETTE['accent_red'],
    'info': PALETTE['accent_blue'],
    'cyan': PALETTE['accent_cyan'],
    'purple': PALETTE['accent_purple'],
}


def render_progress_ring(percentage: float, label: str, size: int = 120, color: str = "#00ff88") -> str:
    """Create an animated circular progress ring"""
    # Clamp percentage between 0 and 100
    pct = max(0, min(100, percentage))
    
    # Calculate stroke dasharray for the progress
    circumference = 2 * 3.14159 * 45  # radius = 45
    stroke_dasharray = f"{(pct / 100) * circumference} {circumference}"
    
    return f"""
    <div style="display: flex; flex-direction: column; align-items: center; padding: 10px;">
        <svg width="{size}" height="{size}" viewBox="0 0 100 100">
            <!-- Background circle -->
            <circle
                cx="50" cy="50" r="45"
                fill="none"
                stroke="rgba(255,255,255,0.1)"
                stroke-width="8"
            />
            <!-- Progress circle -->
            <circle
                cx="50" cy="50" r="45"
                fill="none"
                stroke="{color}"
                stroke-width="8"
                stroke-linecap="round"
                stroke-dasharray="{stroke_dasharray}"
                transform="rotate(-90 50 50)"
                style="filter: drop-shadow(0 0 6px {color}80); transition: stroke-dasharray 0.5s ease;"
            />
            <!-- Percentage text -->
            <text x="50" y="50" text-anchor="middle" dy="0.3em"
                  style="font-size: 20px; font-weight: bold; fill: {color}; font-family: 'Orbitron', sans-serif;">
                {pct:.1f}%
            </text>
        </svg>
        <span style="color: #888; font-size: 12px; margin-top: 5px; text-transform: uppercase; letter-spacing: 1px;">
            {label}
        </span>
    </div>
    """


def render_stat_card(icon: str, value: str, label: str, color: str = "#00ffff") -> str:
    """Create a beautiful stat card"""
    return f"""
    <div style="
        background: linear-gradient(135deg, rgba(26, 26, 46, 0.9) 0%, rgba(22, 33, 62, 0.9) 100%);
        border: 1px solid {color}30;
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    ">
        <div style="font-size: 32px; margin-bottom: 8px;">{icon}</div>
        <div style="font-size: 28px; font-weight: bold; color: {color}; font-family: 'Orbitron', sans-serif; text-shadow: 0 0 10px {color}50;">
            {value}
        </div>
        <div style="font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-top: 5px;">
            {label}
        </div>
    </div>
    """


def render_animated_progress_bar(percentage: float, label: str, color: str = "#00ff88") -> str:
    """Create a beautiful animated progress bar"""
    pct = max(0, min(100, percentage))
    
    return f"""
    <div style="margin: 15px 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="color: #fff; font-size: 14px; font-weight: 500;">{label}</span>
            <span style="color: {color}; font-size: 14px; font-weight: bold; font-family: 'Orbitron', sans-serif;">{pct:.1f}%</span>
        </div>
        <div style="
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            height: 12px;
            overflow: hidden;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
        ">
            <div style="
                width: {pct}%;
                height: 100%;
                background: linear-gradient(90deg, {color}80, {color});
                border-radius: 10px;
                box-shadow: 0 0 10px {color}60, 0 0 20px {color}40;
                transition: width 0.5s ease;
                position: relative;
                overflow: hidden;
            ">
                <div style="
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
                    animation: shimmer 2s infinite;
                "></div>
            </div>
        </div>
    </div>
    <style>
        @keyframes shimmer {{
            0% {{ transform: translateX(-100%); }}
            100% {{ transform: translateX(100%); }}
        }}
    </style>
    """


def render_historical_data_tab():
    """Render the Historical Data monitoring tab"""
    
    # Custom CSS for the page
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&display=swap');
    
    .historical-header {
        text-align: center;
        padding: 20px 0;
        margin-bottom: 20px;
    }
    
    .historical-header h1 {
        font-family: 'Orbitron', sans-serif;
        font-size: 2.5rem;
        background: linear-gradient(135deg, #00ffff, #00ff88);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 10px;
    }
    
    .historical-header p {
        color: #888;
        font-size: 14px;
    }
    
    .section-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: #fff;
        margin: 20px 0 15px 0;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .glass-card {
        background: linear-gradient(135deg, rgba(26, 26, 46, 0.8) 0%, rgba(22, 33, 62, 0.8) 100%);
        border: 1px solid rgba(0, 255, 255, 0.15);
        border-radius: 16px;
        padding: 20px;
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .status-complete {
        background: rgba(0, 255, 136, 0.2);
        color: #00ff88;
        border: 1px solid #00ff8840;
    }
    
    .status-progress {
        background: rgba(0, 255, 255, 0.2);
        color: #00ffff;
        border: 1px solid #00ffff40;
    }
    
    .status-pending {
        background: rgba(255, 255, 255, 0.1);
        color: #888;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="historical-header">
        <h1>📊 Historical Data</h1>
        <p>ML Training Data Monitor • Real-time Backfill Progress</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get overall stats
    stats = get_historical_stats()
    
    if not stats.get('exists', False):
        st.markdown("""
        <div class="glass-card" style="text-align: center; padding: 40px;">
            <div style="font-size: 64px; margin-bottom: 20px;">⏳</div>
            <h2 style="color: #fff; margin-bottom: 15px;">Historical Data Not Available</h2>
            <p style="color: #888; max-width: 500px; margin: 0 auto 20px;">
                The historical-data agent needs to run first to download training data.
            </p>
            <div style="background: rgba(0, 0, 0, 0.3); border-radius: 8px; padding: 15px; display: inline-block; text-align: left;">
                <code style="color: #00ff88;">docker-compose up -d historical-data</code>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # === TOP METRICS CARDS ===
    cards_html = f"""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px;">
        {render_stat_card("📈", str(stats.get('symbols', 0)), "Symbols", "#00ffff")}
        {render_stat_card("🕯️", f"{stats.get('total_candles', 0):,}", "Total Candles", "#00ff88")}
        {render_stat_card("💾", f"{stats.get('db_size_mb', 0):.1f} MB", "Database Size", "#a855f7")}
        {render_stat_card("🔄", f"{stats.get('interpolated_count', 0):,}", "Interpolated", "#ffa502")}
    </div>
    """
    components.html(cards_html, height=180)
    
    # Date range info
    if stats.get('min_date') and stats.get('max_date'):
        st.markdown(f"""
        <div style="
            background: rgba(0, 255, 255, 0.05);
            border: 1px solid rgba(0, 255, 255, 0.2);
            border-radius: 10px;
            padding: 12px 20px;
            text-align: center;
            margin-bottom: 20px;
        ">
            <span style="color: #888;">📅 Data Range:</span>
            <span style="color: #00ffff; font-weight: 600; margin-left: 10px;">
                {stats['min_date'][:10]}
            </span>
            <span style="color: #888; margin: 0 10px;">→</span>
            <span style="color: #00ff88; font-weight: 600;">
                {stats['max_date'][:10]}
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Backfill Status",
        "📊 Data Quality",
        "📈 Price Verify",
        "⚠️ Gap Detector"
    ])
    
    with tab1:
        render_backfill_status()
    
    with tab2:
        render_data_quality()
    
    with tab3:
        render_price_verification()
    
    with tab4:
        render_gap_detector()


def render_backfill_status():
    """Render backfill progress for all symbols"""
    
    # Get all status data
    all_status = get_backfill_status_all()
    
    if not all_status:
        st.info("⏳ Waiting for backfill to start...")
        return
    
    df_all = pd.DataFrame(all_status)
    
    # Separate by timeframe
    tf_15m = df_all[df_all['timeframe'] == '15m']
    tf_1h = df_all[df_all['timeframe'] == '1h']
    
    # Calculate stats
    complete_15m = len(tf_15m[tf_15m['status'] == 'COMPLETE'])
    complete_1h = len(tf_1h[tf_1h['status'] == 'COMPLETE'])
    total_15m = len(tf_15m) if len(tf_15m) > 0 else 100
    total_1h = len(tf_1h) if len(tf_1h) > 0 else 100
    
    # Find current symbol in progress
    in_progress = df_all[df_all['status'] == 'IN_PROGRESS']
    current_symbol = ""
    if not in_progress.empty:
        row = in_progress.iloc[0]
        current_symbol = row['symbol'].replace('/USDT:USDT', '')
    
    # Calculate overall progress
    total_complete = complete_15m + complete_1h
    total_all = total_15m + total_1h
    overall_pct = (total_complete / total_all * 100) if total_all > 0 else 0
    pct_15m = (complete_15m / total_15m * 100) if total_15m > 0 else 0
    pct_1h = (complete_1h / total_1h * 100) if total_1h > 0 else 0
    
    # === PROGRESS RINGS ===
    progress_html = f"""
    <div class="glass-card" style="margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-around; align-items: center; flex-wrap: wrap;">
            {render_progress_ring(overall_pct, "Overall Progress", 150, "#00ffff")}
            {render_progress_ring(pct_15m, f"15min ({complete_15m}/{total_15m})", 120, "#00ff88")}
            {render_progress_ring(pct_1h, f"1hour ({complete_1h}/{total_1h})", 120, "#a855f7")}
        </div>
    </div>
    """
    components.html(progress_html, height=200)
    
    # Current activity badge
    if current_symbol:
        st.markdown(f"""
        <div style="
            background: linear-gradient(90deg, rgba(0, 255, 255, 0.1), rgba(0, 255, 136, 0.1));
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 10px;
            padding: 15px 20px;
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        ">
            <div style="
                width: 12px;
                height: 12px;
                background: #00ffff;
                border-radius: 50%;
                margin-right: 12px;
                animation: pulse 1.5s infinite;
                box-shadow: 0 0 10px #00ffff;
            "></div>
            <span style="color: #fff; font-weight: 500;">Currently downloading:</span>
            <span style="color: #00ffff; font-weight: 700; margin-left: 10px; font-family: 'Orbitron', sans-serif;">
                {current_symbol}
            </span>
        </div>
        <style>
            @keyframes pulse {{
                0%, 100% {{ opacity: 1; transform: scale(1); }}
                50% {{ opacity: 0.5; transform: scale(1.2); }}
            }}
        </style>
        """, unsafe_allow_html=True)
    elif overall_pct >= 100:
        st.markdown("""
        <div style="
            background: linear-gradient(90deg, rgba(0, 255, 136, 0.1), rgba(0, 255, 136, 0.2));
            border: 1px solid rgba(0, 255, 136, 0.3);
            border-radius: 10px;
            padding: 15px 20px;
            text-align: center;
            margin-bottom: 20px;
        ">
            <span style="font-size: 24px; margin-right: 10px;">✅</span>
            <span style="color: #00ff88; font-weight: 700; font-size: 18px;">Backfill Complete!</span>
        </div>
        """, unsafe_allow_html=True)
    
    # === PENDING QUEUE ===
    pending = df_all[df_all['status'] == 'PENDING'].head(5)
    if not pending.empty:
        st.markdown('<div class="section-title">⏳ Coming Up Next</div>', unsafe_allow_html=True)
        
        queue_items = []
        for _, row in pending.iterrows():
            symbol = row['symbol'].replace('/USDT:USDT', '')
            tf = row['timeframe']
            queue_items.append(f'<span style="background: rgba(255,255,255,0.1); padding: 4px 12px; border-radius: 15px; margin-right: 8px; color: #888;">{symbol} [{tf}]</span>')
        
        st.markdown(f"""
        <div style="padding: 10px 0;">
            {"".join(queue_items)}
        </div>
        """, unsafe_allow_html=True)


def render_data_quality():
    """Render data quality heatmap"""
    st.markdown('<div class="section-title">📊 Data Quality Overview</div>', unsafe_allow_html=True)
    
    all_status = get_backfill_status_all()
    
    if not all_status:
        st.info("No data available yet")
        return
    
    # Create heatmap data
    df = pd.DataFrame(all_status)
    
    if df.empty:
        st.info("No data available")
        return
    
    # Pivot for heatmap (symbols x timeframes)
    df['symbol_short'] = df['symbol'].str.replace('/USDT:USDT', '')
    
    # Select timeframe for detailed view
    timeframe = st.selectbox(
        "Select Timeframe",
        df['timeframe'].unique(),
        key="quality_timeframe"
    )
    
    tf_data = df[df['timeframe'] == timeframe].copy()
    
    if not tf_data.empty:
        # Sort by completeness
        tf_data = tf_data.sort_values('completeness_pct', ascending=False)
        
        # Create bar chart with gradient colors
        fig = go.Figure()
        
        # Color based on completeness
        colors = tf_data['completeness_pct'].apply(
            lambda x: '#00ff88' if x >= 99 else 
                     '#ffa502' if x >= 95 else '#ff4757'
        )
        
        fig.add_trace(go.Bar(
            x=tf_data['symbol_short'],
            y=tf_data['completeness_pct'],
            marker=dict(
                color=colors,
                line=dict(width=0)
            ),
            text=tf_data['completeness_pct'].apply(lambda x: f"{x:.1f}%"),
            textposition='outside',
            textfont=dict(color='#888', size=10)
        ))
        
        fig.update_layout(
            title=dict(
                text=f"Data Completeness by Symbol [{timeframe}]",
                font=dict(color='#fff', size=16)
            ),
            xaxis=dict(
                title="Symbol",
                tickfont=dict(color='#888'),
                gridcolor='rgba(255,255,255,0.05)'
            ),
            yaxis=dict(
                title="Completeness %",
                range=[0, 105],
                tickfont=dict(color='#888'),
                gridcolor='rgba(255,255,255,0.05)'
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400,
            showlegend=False,
            margin=dict(t=50, b=50)
        )
        
        fig.add_hline(y=99, line_dash="dash", line_color="#00ff88",
                     annotation_text="99% threshold",
                     annotation_font_color="#00ff88")
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Summary stats in cards
        above_99 = len(tf_data[tf_data['completeness_pct'] >= 99])
        avg_comp = tf_data['completeness_pct'].mean()
        total_gaps = tf_data['gap_count'].sum()
        
        summary_html = f"""
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 20px;">
            {render_stat_card("🟢", f"{above_99}/{len(tf_data)}", "≥99% Complete", "#00ff88")}
            {render_stat_card("📊", f"{avg_comp:.2f}%", "Average", "#00ffff")}
            {render_stat_card("⚠️", str(int(total_gaps)), "Total Gaps", "#ffa502")}
        </div>
        """
        components.html(summary_html, height=160)


def render_price_verification():
    """Render price chart for visual verification"""
    st.markdown('<div class="section-title">📈 Price Chart Verification</div>', unsafe_allow_html=True)
    
    symbols = get_historical_symbols()
    
    if not symbols:
        st.info("No historical data available yet")
        return
    
    # Symbol selector
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        symbol = st.selectbox(
            "Select Symbol",
            symbols,
            format_func=lambda x: x.replace('/USDT:USDT', ''),
            key="verify_symbol"
        )
    with col2:
        timeframe = st.selectbox(
            "Timeframe",
            ["15m", "1h"],
            key="verify_tf"
        )
    with col3:
        limit = st.selectbox(
            "Candles",
            [500, 1000, 2500, 5000],
            index=1,
            key="verify_limit"
        )
    
    if symbol:
        df = get_historical_ohlcv(symbol, timeframe, limit)
        
        if df is not None and len(df) > 0:
            # Create candlestick chart
            fig = go.Figure()
            
            # Candlestick with custom colors
            fig.add_trace(go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name="OHLC",
                increasing_line_color='#00ff88',
                decreasing_line_color='#ff4757',
                increasing_fillcolor='#00ff88',
                decreasing_fillcolor='#ff4757'
            ))
            
            # Highlight interpolated candles if any
            if 'interpolated' in df.columns:
                interp_df = df[df['interpolated'] == 1]
                if len(interp_df) > 0:
                    fig.add_trace(go.Scatter(
                        x=interp_df.index,
                        y=interp_df['high'],
                        mode='markers',
                        marker=dict(
                            symbol='triangle-down',
                            size=10,
                            color='#ffa502'
                        ),
                        name="Interpolated"
                    ))
            
            symbol_short = symbol.replace('/USDT:USDT', '')
            fig.update_layout(
                title=dict(
                    text=f"{symbol_short} Historical Data [{timeframe}]",
                    font=dict(color='#fff', size=16)
                ),
                xaxis=dict(
                    title="Date",
                    tickfont=dict(color='#888'),
                    gridcolor='rgba(255,255,255,0.05)',
                    rangeslider=dict(visible=False)
                ),
                yaxis=dict(
                    title="Price (USDT)",
                    tickfont=dict(color='#888'),
                    gridcolor='rgba(255,255,255,0.05)'
                ),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=500,
                margin=dict(t=50, b=50)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Stats cards
            interp_count = df['interpolated'].sum() if 'interpolated' in df.columns else 0
            
            stats_html = f"""
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 20px;">
                {render_stat_card("🕯️", f"{len(df):,}", "Candles", "#00ffff")}
                {render_stat_card("📅", df.index.min().strftime('%Y-%m-%d'), "From", "#00ff88")}
                {render_stat_card("📅", df.index.max().strftime('%Y-%m-%d'), "To", "#a855f7")}
                {render_stat_card("🔄", str(int(interp_count)), "Interpolated", "#ffa502")}
            </div>
            """
            components.html(stats_html, height=160)
        else:
            st.warning(f"No data available for {symbol} [{timeframe}]")


def render_gap_detector():
    """Render gap detection view"""
    st.markdown('<div class="section-title">⚠️ Gap Detector</div>', unsafe_allow_html=True)
    
    all_status = get_backfill_status_all()
    
    if not all_status:
        st.info("No data available yet")
        return
    
    # Filter to only show items with gaps
    gaps_data = [s for s in all_status if s['gap_count'] > 0]
    
    if not gaps_data:
        st.markdown("""
        <div style="
            background: linear-gradient(90deg, rgba(0, 255, 136, 0.1), rgba(0, 255, 136, 0.2));
            border: 1px solid rgba(0, 255, 136, 0.3);
            border-radius: 16px;
            padding: 40px;
            text-align: center;
        ">
            <div style="font-size: 48px; margin-bottom: 15px;">✅</div>
            <h3 style="color: #00ff88; margin-bottom: 10px;">No Gaps Detected!</h3>
            <p style="color: #888;">All historical data is complete and continuous.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    st.markdown(f"""
    <div style="
        background: rgba(255, 165, 2, 0.1);
        border: 1px solid rgba(255, 165, 2, 0.3);
        border-radius: 10px;
        padding: 15px 20px;
        margin-bottom: 20px;
    ">
        <span style="font-size: 20px; margin-right: 10px;">⚠️</span>
        <span style="color: #ffa502; font-weight: 600;">{len(gaps_data)} symbol/timeframe pairs have gaps</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Create table
    df = pd.DataFrame(gaps_data)
    df['symbol_short'] = df['symbol'].str.replace('/USDT:USDT', '')
    
    # Sort by gap count
    df = df.sort_values('gap_count', ascending=False)
    
    # Display
    st.dataframe(
        df[['symbol_short', 'timeframe', 'gap_count', 'completeness_pct', 
            'total_candles', 'error_message']].rename(columns={
            'symbol_short': 'Symbol',
            'timeframe': 'TF',
            'gap_count': 'Gaps',
            'completeness_pct': 'Complete %',
            'total_candles': 'Candles',
            'error_message': 'Error'
        }),
        hide_index=True,
        use_container_width=True
    )
    
    # Summary chart
    if len(df) > 0:
        fig = px.bar(
            df.head(20),
            x='symbol_short',
            y='gap_count',
            color='timeframe',
            title="Top 20 Symbols with Most Gaps",
            color_discrete_map={'15m': '#00ffff', '1h': '#a855f7'}
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400,
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.05)')
        )
        st.plotly_chart(fig, use_container_width=True)


# Export
__all__ = ['render_historical_data_tab']
