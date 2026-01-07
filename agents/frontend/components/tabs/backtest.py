"""
🔄 Backtest Tab - Visual backtesting interface

Shows:
- Candlestick chart with entry/exit markers
- Confidence score bar for each candle
- Component breakdown (RSI, MACD, BB contributions)
- Trade statistics
- Detailed signals list with mini analysis
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from database import get_symbols, get_timeframes, get_ohlcv
from ai.backtest.engine import run_backtest
from ai.core.config import BACKTEST_CONFIG, get_confidence_level
from ai.visualizations.backtest_charts import (
    create_backtest_chart,
    create_confidence_gauge,
    create_component_breakdown_chart
)

# Warmup period for indicators
WARMUP_PERIOD = 50


def render_backtest_tab():
    """Render the Backtest tab with visual backtesting"""
    
    # Get available symbols
    symbols = get_symbols()
    if not symbols:
        st.warning("⚠️ No data available. Wait for data-fetcher to load data.")
        st.stop()
    
    # Create symbol map (display name -> full symbol)
    symbol_map = {s.replace('/USDT:USDT', ''): s for s in symbols}
    
    # ═══════════════════════════════════════════════════════════════════
    # HEADER
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("### 🔄 Visual Backtesting")
    st.markdown("""
    <p style="color: #a0a0a0; font-size: 0.9rem;">
    Test trading strategies based on technical indicators. 
    The system calculates a <b>confidence score</b> from RSI, MACD, and Bollinger Bands, 
    then simulates entries when confidence exceeds thresholds.
    </p>
    """, unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════
    # CONTROLS
    # ═══════════════════════════════════════════════════════════════════
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        selected_name = st.selectbox(
            "🪙 Select Coin (ordered by volume)",
            list(symbol_map.keys()),
            key="backtest_coin"
        )
        selected_symbol = symbol_map[selected_name]
    
    with col2:
        timeframes = get_timeframes(selected_symbol)
        tf_order = ['15m', '1h', '4h', '1d']
        timeframes_sorted = [tf for tf in tf_order if tf in timeframes]
        selected_tf = st.selectbox("⏱️ Timeframe", timeframes_sorted, key="backtest_tf")
    
    with col3:
        num_candles = st.selectbox("🕯️ Candles", [100, 150, 200, 300, 500], index=2, key="backtest_candles")
    
    # Advanced settings expander
    with st.expander("⚙️ Backtest Settings"):
        # Signal settings
        st.markdown("##### 📊 Signal Settings")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            entry_threshold = st.slider(
                "Entry Threshold",
                min_value=5,
                max_value=80,
                value=BACKTEST_CONFIG['entry_threshold'],
                step=5,
                help="Minimum |confidence| to open a position (±)"
            )
        
        with col2:
            exit_threshold = st.slider(
                "Exit Threshold",
                min_value=5,
                max_value=50,
                value=BACKTEST_CONFIG['exit_threshold'],
                step=5,
                help="Opposite confidence to close position"
            )
        
        with col3:
            min_holding = st.slider(
                "Min Holding (candles)",
                min_value=1,
                max_value=10,
                value=BACKTEST_CONFIG['min_holding_candles'],
                step=1,
                help="Minimum candles before exit allowed"
            )
        
        st.markdown("---")
        
        # Stop Loss / Take Profit settings
        st.markdown("##### 🛑 Stop Loss / Take Profit")
        
        use_sl_tp = st.checkbox(
            "Enable SL/TP exits",
            value=BACKTEST_CONFIG.get('use_sl_tp', True),
            help="Exit trades when Stop Loss or Take Profit levels are hit"
        )
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            stop_loss_pct = st.slider(
                "🛑 Stop Loss %",
                min_value=0.5,
                max_value=10.0,
                value=float(BACKTEST_CONFIG.get('stop_loss_pct', 2.0)),
                step=0.5,
                help="Exit if loss exceeds this percentage",
                disabled=not use_sl_tp
            )
        
        with col2:
            take_profit_pct = st.slider(
                "🎯 Take Profit %",
                min_value=1.0,
                max_value=20.0,
                value=float(BACKTEST_CONFIG.get('take_profit_pct', 4.0)),
                step=0.5,
                help="Exit if profit exceeds this percentage",
                disabled=not use_sl_tp
            )
        
        with col3:
            max_holding = st.slider(
                "⏰ Max Holding (candles)",
                min_value=0,
                max_value=200,
                value=BACKTEST_CONFIG.get('max_holding_candles', 0),
                step=10,
                help="Force exit after N candles (0 = disabled)"
            )
        
        # Store settings in session state for optimizer
        st.session_state['backtest_settings'] = {
            'entry_threshold': entry_threshold,
            'exit_threshold': exit_threshold,
            'min_holding': min_holding,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'use_sl_tp': use_sl_tp,
            'max_holding_candles': max_holding
        }
    
    # Run backtest button
    run_button = st.button("🚀 Run Backtest", type="primary", use_container_width=True)
    
    # ═══════════════════════════════════════════════════════════════════
    # LOAD DATA & RUN BACKTEST
    # ═══════════════════════════════════════════════════════════════════
    
    # Load data with warmup
    total_candles_needed = num_candles + WARMUP_PERIOD
    df_full = get_ohlcv(selected_symbol, selected_tf, total_candles_needed)
    
    if df_full.empty:
        st.error("❌ No data available for this selection")
        st.stop()
    
    # Run backtest
    result = run_backtest(
        df_full,
        entry_threshold=entry_threshold,
        exit_threshold=exit_threshold,
        min_holding=min_holding
    )
    
    # Get statistics
    stats = result.trades.get_statistics()
    
    # ═══════════════════════════════════════════════════════════════════
    # CURRENT CONFIDENCE DISPLAY
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 🎯 Current Signal")
    
    current_confidence = result.confidence_scores.iloc[-1]
    level_info = get_confidence_level(current_confidence)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        st.metric(
            "Confidence Score",
            f"{current_confidence:+.1f}",
            delta=level_info['label']
        )
    
    with col2:
        # Confidence gauge
        gauge_fig = create_confidence_gauge(current_confidence)
        st.plotly_chart(gauge_fig, use_container_width=True)
    
    with col3:
        # Component breakdown
        components_data = result.signal_components
        breakdown_fig = create_component_breakdown_chart(components_data)
        st.plotly_chart(breakdown_fig, use_container_width=True)
    
    # ═══════════════════════════════════════════════════════════════════
    # BACKTEST STATISTICS
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📊 Backtest Statistics")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    col1.metric(
        "Total Trades",
        stats['total_trades'],
        f"🟢 {stats['long_trades']} L / 🔴 {stats['short_trades']} S"
    )
    
    col2.metric(
        "Win Rate",
        f"{stats['win_rate']:.1f}%",
        f"✅ {stats['winning_trades']} / ❌ {stats['losing_trades']}"
    )
    
    col3.metric(
        "Total Return",
        f"{stats['total_return']:+.2f}%",
        "Compounded"
    )
    
    col4.metric(
        "Avg Trade",
        f"{stats['average_trade']:+.2f}%"
    )
    
    col5.metric(
        "Best / Worst",
        f"{stats['best_trade']:+.1f}%",
        f"{stats['worst_trade']:+.1f}%"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # MAIN BACKTEST CHART
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📈 Backtest Chart")
    st.markdown("""
    <p style="color: #a0a0a0; font-size: 0.85rem;">
    <b>▲</b> = LONG entry | <b>▼</b> = SHORT entry | <b>✗</b> = Exit | 
    <span style="color: #00ff88;">Green line</span> = Profit | 
    <span style="color: #ff4757;">Red line</span> = Loss
    </p>
    """, unsafe_allow_html=True)
    
    # Create and display backtest chart
    backtest_fig = create_backtest_chart(result, selected_name)
    st.plotly_chart(backtest_fig, use_container_width=True)
    
    # Show warning if no trades were generated
    trades_list = result.trades.trades
    if not trades_list:
        conf_min = result.confidence_scores.min()
        conf_max = result.confidence_scores.max()
        
        st.warning(f"""
        ⚠️ **No Trades Generated**
        
        Confidence score ranges between **{conf_min:.1f}** and **{conf_max:.1f}**, 
        but entry threshold is set to **±{entry_threshold}**.
        
        **Solutions:**
        - Lower Entry Threshold to **{max(5, int(abs(conf_max) - 5))}** or less
        - Try more volatile timeframes (1h, 4h)
        - Try more volatile coins (altcoins vs BTC)
        """)
    
    # ═══════════════════════════════════════════════════════════════════
    # SIGNALS DETAIL LIST
    # ═══════════════════════════════════════════════════════════════════
    if trades_list:
        st.markdown("---")
        st.markdown("### 📋 Signal Details")
        st.markdown("""
        <p style="color: #c0c0c0; font-size: 0.9rem;">
        Select a trade from the list to see complete indicator details and analysis.
        </p>
        """, unsafe_allow_html=True)
        
        # Create trade selector
        trade_options = []
        for trade in trades_list:
            emoji = "🟢" if trade.trade_type.value == "LONG" else "🔴"
            result_emoji = ""
            if trade.is_closed:
                result_emoji = "✅" if trade.is_winner else "❌"
            else:
                result_emoji = "⏳"
            
            # Format entry time
            entry_time_str = trade.entry_time.strftime('%m/%d %H:%M') if hasattr(trade.entry_time, 'strftime') else str(trade.entry_time)[:16]
            
            pnl_str = f" ({trade.pnl_pct:+.2f}%)" if trade.pnl_pct is not None else ""
            trade_options.append(f"{result_emoji} #{trade.trade_id} {emoji} {trade.trade_type.value} @ {entry_time_str}{pnl_str}")
        
        # Selector for trade
        selected_trade_idx = st.selectbox(
            "🔍 Select Trade",
            range(len(trade_options)),
            format_func=lambda x: trade_options[x],
            key="selected_trade"
        )
        
        # Show selected trade details
        if selected_trade_idx is not None:
            selected_trade = trades_list[selected_trade_idx]
            
            # Get indicator values at entry time
            entry_idx = df_full.index.get_loc(selected_trade.entry_time)
            
            # Get component scores at entry
            rsi_score_entry = result.signal_components.rsi_score.iloc[entry_idx]
            macd_score_entry = result.signal_components.macd_score.iloc[entry_idx]
            bb_score_entry = result.signal_components.bb_score.iloc[entry_idx]
            total_score_entry = result.signal_components.total_score.iloc[entry_idx]
            
            # Trade details in styled container
            st.markdown("#### 📊 Entry Details")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown(f"""
                <div style="background: #1e1e2e; padding: 12px; border-radius: 8px; border: 1px solid #3a3a5a;">
                    <p style="color: #888; margin: 0 0 4px 0; font-size: 0.8rem;">⏱️ Entry Time</p>
                    <p style="color: #fff; margin: 0; font-size: 0.95rem; font-weight: 500;">{selected_trade.entry_time.strftime('%Y-%m-%d %H:%M') if hasattr(selected_trade.entry_time, 'strftime') else str(selected_trade.entry_time)[:16]}</p>
                    <p style="color: #888; margin: 10px 0 4px 0; font-size: 0.8rem;">💰 Entry Price</p>
                    <p style="color: #fff; margin: 0; font-size: 0.95rem; font-weight: 500;">${selected_trade.entry_price:,.2f}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                trade_color = "#00ff88" if selected_trade.trade_type.value == "LONG" else "#ff4757"
                trade_emoji = "🟢" if selected_trade.trade_type.value == "LONG" else "🔴"
                st.markdown(f"""
                <div style="background: #1e1e2e; padding: 12px; border-radius: 8px; border: 1px solid #3a3a5a;">
                    <p style="color: #888; margin: 0 0 4px 0; font-size: 0.8rem;">{trade_emoji} Type</p>
                    <p style="color: {trade_color}; margin: 0; font-size: 0.95rem; font-weight: 600;">{selected_trade.trade_type.value}</p>
                    <p style="color: #888; margin: 10px 0 4px 0; font-size: 0.8rem;">🎯 Confidence</p>
                    <p style="color: {trade_color}; margin: 0; font-size: 0.95rem; font-weight: 600;">{selected_trade.entry_confidence:+.1f}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                if selected_trade.is_closed:
                    st.markdown(f"""
                    <div style="background: #1e1e2e; padding: 12px; border-radius: 8px; border: 1px solid #3a3a5a;">
                        <p style="color: #888; margin: 0 0 4px 0; font-size: 0.8rem;">⏱️ Exit Time</p>
                        <p style="color: #fff; margin: 0; font-size: 0.95rem; font-weight: 500;">{selected_trade.exit_time.strftime('%Y-%m-%d %H:%M') if hasattr(selected_trade.exit_time, 'strftime') else str(selected_trade.exit_time)[:16]}</p>
                        <p style="color: #888; margin: 10px 0 4px 0; font-size: 0.8rem;">💰 Exit Price</p>
                        <p style="color: #fff; margin: 0; font-size: 0.95rem; font-weight: 500;">${selected_trade.exit_price:,.2f}</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background: #1e1e2e; padding: 12px; border-radius: 8px; border: 1px solid #3a3a5a;">
                        <p style="color: #888; margin: 0 0 4px 0; font-size: 0.8rem;">⏱️ Exit Time</p>
                        <p style="color: #ffaa00; margin: 0; font-size: 0.95rem; font-weight: 500;">⏳ OPEN</p>
                        <p style="color: #888; margin: 10px 0 4px 0; font-size: 0.8rem;">💰 Exit Price</p>
                        <p style="color: #ffaa00; margin: 0; font-size: 0.95rem; font-weight: 500;">--</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            with col4:
                if selected_trade.is_closed:
                    pnl_color = "#00ff88" if selected_trade.is_winner else "#ff4757"
                    result_text = "✅ WIN" if selected_trade.is_winner else "❌ LOSS"
                    st.markdown(f"""
                    <div style="background: #1e1e2e; padding: 12px; border-radius: 8px; border: 1px solid #3a3a5a;">
                        <p style="color: #888; margin: 0 0 4px 0; font-size: 0.8rem;">📈 P&L</p>
                        <p style="color: {pnl_color}; margin: 0; font-size: 1.1rem; font-weight: 700;">{selected_trade.pnl_pct:+.2f}%</p>
                        <p style="color: #888; margin: 10px 0 4px 0; font-size: 0.8rem;">Result</p>
                        <p style="color: {pnl_color}; margin: 0; font-size: 0.95rem; font-weight: 600;">{result_text}</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background: #1e1e2e; padding: 12px; border-radius: 8px; border: 1px solid #3a3a5a;">
                        <p style="color: #888; margin: 0 0 4px 0; font-size: 0.8rem;">📈 P&L</p>
                        <p style="color: #ffaa00; margin: 0; font-size: 1.1rem; font-weight: 700;">⏳ Pending</p>
                        <p style="color: #888; margin: 10px 0 4px 0; font-size: 0.8rem;">Result</p>
                        <p style="color: #ffaa00; margin: 0; font-size: 0.95rem; font-weight: 600;">⏳ OPEN</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Indicator breakdown
            st.markdown("#### 🔬 Indicator Breakdown (at Entry)")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                rsi_color = "#00ff88" if rsi_score_entry > 10 else "#ff4757" if rsi_score_entry < -10 else "#ffaa00"
                rsi_desc = "Oversold (LONG)" if rsi_score_entry > 15 else "Overbought (SHORT)" if rsi_score_entry < -15 else "Neutral"
                st.markdown(f"""
                <div style="background: #1e1e2e; padding: 15px; border-radius: 8px; border-left: 4px solid {rsi_color};">
                    <p style="color: #fff; margin: 0 0 8px 0; font-weight: 600;">📊 RSI</p>
                    <p style="font-size: 1.4rem; margin: 0 0 8px 0; color: {rsi_color}; font-weight: 700;">{rsi_score_entry:+.1f}</p>
                    <p style="color: #aaa; font-size: 0.85rem; margin: 0;">{rsi_desc}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                macd_color = "#00ff88" if macd_score_entry > 10 else "#ff4757" if macd_score_entry < -10 else "#ffaa00"
                macd_desc = "Bullish Cross" if macd_score_entry > 15 else "Bearish Cross" if macd_score_entry < -15 else "Neutral"
                st.markdown(f"""
                <div style="background: #1e1e2e; padding: 15px; border-radius: 8px; border-left: 4px solid {macd_color};">
                    <p style="color: #fff; margin: 0 0 8px 0; font-weight: 600;">📈 MACD</p>
                    <p style="font-size: 1.4rem; margin: 0 0 8px 0; color: {macd_color}; font-weight: 700;">{macd_score_entry:+.1f}</p>
                    <p style="color: #aaa; font-size: 0.85rem; margin: 0;">{macd_desc}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                bb_color = "#00ff88" if bb_score_entry > 10 else "#ff4757" if bb_score_entry < -10 else "#ffaa00"
                bb_desc = "Near Lower Band" if bb_score_entry > 15 else "Near Upper Band" if bb_score_entry < -15 else "Mid Band"
                st.markdown(f"""
                <div style="background: #1e1e2e; padding: 15px; border-radius: 8px; border-left: 4px solid {bb_color};">
                    <p style="color: #fff; margin: 0 0 8px 0; font-weight: 600;">📉 Bollinger</p>
                    <p style="font-size: 1.4rem; margin: 0 0 8px 0; color: {bb_color}; font-weight: 700;">{bb_score_entry:+.1f}</p>
                    <p style="color: #aaa; font-size: 0.85rem; margin: 0;">{bb_desc}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                total_color = "#00ff88" if total_score_entry > 0 else "#ff4757"
                total_desc = "LONG Signal" if total_score_entry > entry_threshold else "SHORT Signal" if total_score_entry < -entry_threshold else "Below threshold"
                st.markdown(f"""
                <div style="background: #2a2a3e; padding: 15px; border-radius: 8px; border-left: 4px solid {total_color};">
                    <p style="color: #fff; margin: 0 0 8px 0; font-weight: 600;">🎯 TOTAL</p>
                    <p style="font-size: 1.4rem; margin: 0 0 8px 0; color: {total_color}; font-weight: 700;">{total_score_entry:+.1f}</p>
                    <p style="color: #aaa; font-size: 0.85rem; margin: 0;">{total_desc}</p>
                </div>
                """, unsafe_allow_html=True)
            
            # ═══════════════════════════════════════════════════════════════════
            # AI ANALYSIS BUTTON
            # ═══════════════════════════════════════════════════════════════════
            st.markdown("---")
            st.markdown("#### 🤖 AI Analysis")
            st.caption("Get GPT-4o analysis for this trade signal (requires OpenAI API key)")
            
            # AI Analysis button and result
            ai_button_key = f"ai_analyze_{selected_trade.trade_id}"
            
            if st.button("🤖 Analyze with AI", key=ai_button_key, type="secondary", use_container_width=True):
                with st.spinner("🤖 AI is analyzing this trade..."):
                    try:
                        from services import get_openai_service, get_market_intelligence
                        
                        openai_service = get_openai_service()
                        market_intel = get_market_intelligence()
                        
                        if not openai_service.is_available:
                            st.warning("⚠️ OpenAI API key not configured. Add OPENAI_API_KEY to your .env file.")
                        else:
                            # Get market context
                            sentiment_dict = market_intel.get_sentiment_dict()
                            news_text = market_intel.get_news_text(max_items=3)
                            
                            # Prepare indicators dict
                            indicators_dict = {
                                'rsi_score': rsi_score_entry,
                                'macd_score': macd_score_entry,
                                'bb_score': bb_score_entry,
                                'total_score': total_score_entry
                            }
                            
                            # Call AI
                            ai_result = openai_service.analyze_trade(
                                symbol=selected_name,
                                trade_type=selected_trade.trade_type.value,
                                entry_price=selected_trade.entry_price,
                                indicators=indicators_dict,
                                sentiment=sentiment_dict,
                                news=news_text
                            )
                            
                            if ai_result:
                                # Store in session state for display
                                st.session_state[f'ai_result_{selected_trade.trade_id}'] = ai_result
                            else:
                                st.error("❌ AI analysis failed. Check logs for details.")
                                
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
            
            # Display AI result if exists
            ai_result_key = f'ai_result_{selected_trade.trade_id}'
            if ai_result_key in st.session_state:
                ai_result = st.session_state[ai_result_key]
                
                # AI Result Card
                action_color = "#00ff88" if ai_result.is_approved else "#ff4757" if ai_result.action == "reject" else "#ffaa00"
                action_emoji = "✅" if ai_result.is_approved else "❌" if ai_result.action == "reject" else "⏸️"
                risk_color = "#00ff88" if ai_result.risk_assessment == "low" else "#ffaa00" if ai_result.risk_assessment == "medium" else "#ff4757"
                
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                            border: 1px solid {action_color}; border-radius: 12px; padding: 20px; margin: 15px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                        <div>
                            <span style="font-size: 1.3rem; font-weight: bold; color: {action_color};">
                                {action_emoji} {ai_result.action.upper()}
                            </span>
                            <span style="color: #888; margin-left: 10px;">
                                Confidence: {ai_result.confidence:.0f}%
                            </span>
                        </div>
                        <div style="text-align: right;">
                            <span style="background: {risk_color}22; color: {risk_color}; 
                                         padding: 4px 12px; border-radius: 20px; font-size: 0.8rem;">
                                Risk: {ai_result.risk_assessment.upper()}
                            </span>
                        </div>
                    </div>
                    
                    <div style="background: rgba(0,0,0,0.2); border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                        <p style="color: #e0e0e0; margin: 0; font-size: 0.95rem; line-height: 1.6;">
                            {ai_result.reasoning}
                        </p>
                    </div>
                    
                    <div style="margin-bottom: 10px;">
                        <span style="color: #888; font-size: 0.8rem;">KEY FACTORS:</span>
                        <ul style="margin: 5px 0 0 0; padding-left: 20px;">
                            {"".join([f'<li style="color: #c0c0c0; font-size: 0.85rem; margin: 3px 0;">{factor}</li>' for factor in ai_result.key_factors[:4]])}
                        </ul>
                    </div>
                    
                    <div style="display: flex; justify-content: space-between; align-items: center; 
                                border-top: 1px solid rgba(255,255,255,0.1); padding-top: 10px; margin-top: 10px;">
                        <span style="color: #888; font-size: 0.75rem;">
                            Confidence Boost: <span style="color: {'#00ff88' if ai_result.confidence_boost > 0 else '#ff4757'};">
                                {ai_result.confidence_boost:+.0f}
                            </span>
                        </span>
                        <span style="color: #666; font-size: 0.7rem;">
                            Cost: ${ai_result.cost_usd:.4f} | {ai_result.timestamp.strftime('%H:%M:%S')}
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Mini Analysis
            st.markdown("#### 🧠 Signal Analysis")
            
            # Determine which indicators contributed most
            contributions = [
                ("RSI", rsi_score_entry),
                ("MACD", macd_score_entry),
                ("Bollinger", bb_score_entry)
            ]
            contributions.sort(key=lambda x: abs(x[1]), reverse=True)
            
            main_contributor = contributions[0]
            second_contributor = contributions[1]
            
            trade_type = selected_trade.trade_type.value
            
            # Build analysis text using native Streamlit
            direction = "buying" if trade_type == "LONG" else "selling"
            threshold_text = f"+{entry_threshold}" if trade_type == "LONG" else f"-{entry_threshold}"
            
            st.markdown(f"""
            **📊 {trade_type} Signal Analysis:**
            
            The system identified a {direction} opportunity with confidence score of **{total_score_entry:+.1f}** 
            ({"above" if trade_type == "LONG" else "below"} the threshold of {threshold_text}).
            
            **Main Contributing Factors:**
            - **{main_contributor[0]}** contributed most with score **{main_contributor[1]:+.1f}**
            - **{second_contributor[0]}** supported with score **{second_contributor[1]:+.1f}**
            """)
            
            # Indicator details
            st.markdown("**Indicator Details:**")
            
            if trade_type == "LONG":
                if rsi_score_entry > 15:
                    st.markdown("- 📈 RSI indicates **oversold** conditions, suggesting potential bounce")
                if macd_score_entry > 15:
                    st.markdown("- 📈 MACD shows **bullish momentum** with line above signal")
                if bb_score_entry > 15:
                    st.markdown("- 📈 Price near **lower Bollinger Band**, indicating potential undervaluation")
            else:
                if rsi_score_entry < -15:
                    st.markdown("- 📉 RSI indicates **overbought** conditions, suggesting potential pullback")
                if macd_score_entry < -15:
                    st.markdown("- 📉 MACD shows **bearish momentum** with line below signal")
                if bb_score_entry < -15:
                    st.markdown("- 📉 Price near **upper Bollinger Band**, indicating potential overvaluation")
            
            # Check if no strong signals
            if trade_type == "LONG" and not any([rsi_score_entry > 15, macd_score_entry > 15, bb_score_entry > 15]):
                st.markdown("- No strong indicator signals detected")
            elif trade_type == "SHORT" and not any([rsi_score_entry < -15, macd_score_entry < -15, bb_score_entry < -15]):
                st.markdown("- No strong indicator signals detected")
            
            # Outcome section using native Streamlit
            if selected_trade.is_closed:
                if selected_trade.is_winner:
                    st.success(f"✅ **Outcome: PROFIT +{selected_trade.pnl_pct:.2f}%** - Trade closed in profit. Indicator analysis was correct and price moved in the predicted direction.")
                else:
                    st.error(f"❌ **Outcome: LOSS {selected_trade.pnl_pct:.2f}%** - Trade closed at a loss. Market moved against the position. Possible causes: false signal, sudden volatility, or trend reversal.")
    
    # ═══════════════════════════════════════════════════════════════════
    # PARAMETER OPTIMIZER
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("🔬 Parameter Optimizer (Grid Search)", expanded=False):
        st.markdown("""
        <p style="color: #a0a0a0; font-size: 0.9rem;">
        Find optimal SL/TP and entry threshold values using grid search. 
        The optimizer tests all parameter combinations and ranks them by Sharpe Ratio.
        </p>
        """, unsafe_allow_html=True)
        
        # Parameter ranges
        st.markdown("##### 📐 Parameter Ranges")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**🛑 Stop Loss %**")
            sl_min = st.number_input("Min", value=1.0, step=0.5, key="sl_min")
            sl_max = st.number_input("Max", value=5.0, step=0.5, key="sl_max")
            sl_step = st.number_input("Step", value=0.5, step=0.5, key="sl_step")
        
        with col2:
            st.markdown("**🎯 Take Profit %**")
            tp_min = st.number_input("Min", value=2.0, step=0.5, key="tp_min")
            tp_max = st.number_input("Max", value=10.0, step=0.5, key="tp_max")
            tp_step = st.number_input("Step", value=1.0, step=0.5, key="tp_step")
        
        with col3:
            st.markdown("**📊 Entry Threshold**")
            entry_min = st.number_input("Min", value=15, step=5, key="entry_min")
            entry_max = st.number_input("Max", value=40, step=5, key="entry_max")
            entry_step = st.number_input("Step", value=5, step=5, key="entry_step")
        
        # Build param grid
        import numpy as np
        sl_values = list(np.arange(sl_min, sl_max + sl_step, sl_step))
        tp_values = list(np.arange(tp_min, tp_max + tp_step, tp_step))
        entry_values = list(range(int(entry_min), int(entry_max) + int(entry_step), int(entry_step)))
        
        total_combinations = len(sl_values) * len(tp_values) * len(entry_values)
        
        st.markdown(f"""
        <div style="background: #1e1e2e; padding: 10px 15px; border-radius: 8px; margin: 10px 0;">
            <span style="color: #888;">Total combinations to test: </span>
            <span style="color: #00ff88; font-weight: bold;">{total_combinations}</span>
            <span style="color: #666;"> (~{total_combinations * 0.05:.1f}s estimated)</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Run optimization button
        if st.button("🚀 Run Optimization", type="primary", use_container_width=True, key="run_optimizer"):
            from ai.optimizer.grid_search import GridSearchOptimizer
            
            param_grid = {
                'stop_loss_pct': sl_values,
                'take_profit_pct': tp_values,
                'entry_threshold': entry_values
            }
            
            optimizer = GridSearchOptimizer()
            
            progress_bar = st.progress(0, text="Starting optimization...")
            
            def update_progress(current, total):
                progress_bar.progress(current / total, text=f"Testing {current}/{total} combinations...")
            
            result = optimizer.optimize(df_full, param_grid, progress_callback=update_progress)
            
            progress_bar.empty()
            
            # Store result in session state
            st.session_state['optimization_result'] = result
            st.rerun()
        
        # Display results if available
        if 'optimization_result' in st.session_state:
            result = st.session_state['optimization_result']
            
            st.markdown("---")
            st.markdown("##### 🏆 Optimization Results")
            
            # Show period information
            start_date = df_full.index[0].strftime('%Y-%m-%d %H:%M') if hasattr(df_full.index[0], 'strftime') else str(df_full.index[0])[:16]
            end_date = df_full.index[-1].strftime('%Y-%m-%d %H:%M') if hasattr(df_full.index[-1], 'strftime') else str(df_full.index[-1])[:16]
            
            st.markdown(f"""
            <div style="background: #1a1a2e; padding: 12px 18px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #2d2d4a;">
                <div style="display: flex; flex-wrap: wrap; gap: 20px; align-items: center;">
                    <div>
                        <span style="color: #888; font-size: 0.8rem;">⏱️ Execution:</span>
                        <span style="color: #00ff88; font-weight: 600; margin-left: 5px;">{result.execution_time_sec:.1f}s</span>
                    </div>
                    <div>
                        <span style="color: #888; font-size: 0.8rem;">🔢 Combinations:</span>
                        <span style="color: #ffffff; font-weight: 600; margin-left: 5px;">{result.total_combinations}</span>
                    </div>
                    <div>
                        <span style="color: #888; font-size: 0.8rem;">📅 Period:</span>
                        <span style="color: #00d4ff; font-weight: 600; margin-left: 5px;">{start_date}</span>
                        <span style="color: #888; margin: 0 5px;">→</span>
                        <span style="color: #00d4ff; font-weight: 600;">{end_date}</span>
                    </div>
                    <div>
                        <span style="color: #888; font-size: 0.8rem;">🕯️ Candles:</span>
                        <span style="color: #ffffff; font-weight: 600; margin-left: 5px;">{len(df_full)}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Best result card using native Streamlit
            if result.best_by_sharpe:
                best = result.best_by_sharpe
                
                st.success("🏆 **BEST CONFIGURATION FOUND**")
                
                # Main parameters row
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "🛑 Stop Loss",
                        f"{best.params.get('stop_loss_pct', 0):.1f}%"
                    )
                
                with col2:
                    st.metric(
                        "🎯 Take Profit",
                        f"{best.params.get('take_profit_pct', 0):.1f}%"
                    )
                
                with col3:
                    st.metric(
                        "📊 Entry Threshold",
                        f"{int(best.params.get('entry_threshold', 0))}"
                    )
                
                with col4:
                    st.metric(
                        "📈 Sharpe Ratio",
                        f"{best.sharpe_ratio:.2f}"
                    )
                
                # Performance metrics row
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    delta_color = "normal" if best.total_return >= 0 else "inverse"
                    st.metric(
                        "💰 Return",
                        f"{best.total_return:+.2f}%",
                        delta_color=delta_color
                    )
                
                with col2:
                    st.metric(
                        "🎯 Win Rate",
                        f"{best.win_rate:.1f}%"
                    )
                
                with col3:
                    st.metric(
                        "📊 Trades",
                        f"{best.total_trades}"
                    )
                
                with col4:
                    st.metric(
                        "⚖️ Profit Factor",
                        f"{best.profit_factor:.2f}"
                    )
                
                st.markdown("")
                
                # Apply best values button
                if st.button("📌 Apply Best Values", type="secondary", use_container_width=True, key="apply_best"):
                    st.session_state['apply_best_params'] = best.params
                    st.info(f"✅ Best parameters: SL={best.params.get('stop_loss_pct', 0):.1f}%, TP={best.params.get('take_profit_pct', 0):.1f}%, Entry={int(best.params.get('entry_threshold', 0))}")
            
            st.markdown("---")
            
            # ═══════════════════════════════════════════════════════════════════
            # TOP 10 RESULTS - Premium Styled Table
            # ═══════════════════════════════════════════════════════════════════
            st.markdown("##### 📊 Top 10 Results (sorted by Sharpe Ratio)")
            top_results = result.get_top_n(10, sort_by='sharpe')
            
            if top_results:
                # CSS styles for the premium table - High contrast version
                st.markdown("""
                <style>
                .opt-results-container {
                    background: #1a1a2e;
                    border-radius: 12px;
                    padding: 20px;
                    margin: 15px 0;
                    border: 1px solid #2d2d4a;
                }
                .opt-result-row {
                    background: #252542;
                    border-radius: 10px;
                    padding: 15px 18px;
                    margin: 10px 0;
                    border-left: 5px solid #4a4a6a;
                    transition: all 0.3s ease;
                }
                .opt-result-row:hover {
                    transform: translateX(5px);
                    box-shadow: 0 4px 20px rgba(0, 255, 136, 0.15);
                    background: #2d2d52;
                }
                .opt-result-row.opt-gold {
                    border-left: 5px solid #ffd700;
                    background: linear-gradient(135deg, #3d3520 0%, #4a4025 100%);
                }
                .opt-result-row.opt-silver {
                    border-left: 5px solid #e0e0e0;
                    background: linear-gradient(135deg, #353545 0%, #404055 100%);
                }
                .opt-result-row.opt-bronze {
                    border-left: 5px solid #e8a050;
                    background: linear-gradient(135deg, #3d3025 0%, #4a3a2d 100%);
                }
                .opt-rank-badge {
                    font-size: 1.5rem;
                    font-weight: bold;
                    min-width: 50px;
                    display: inline-block;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                }
                .opt-rank-badge.opt-gold { color: #ffd700; }
                .opt-rank-badge.opt-silver { color: #e0e0e0; }
                .opt-rank-badge.opt-bronze { color: #e8a050; }
                .opt-rank-badge.opt-normal { color: #9999aa; font-size: 1.2rem; }
                .opt-params-section {
                    display: flex;
                    gap: 25px;
                    flex-wrap: wrap;
                    margin-bottom: 12px;
                }
                .opt-param-item {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .opt-param-label {
                    color: #b0b0c0;
                    font-size: 0.85rem;
                    font-weight: 500;
                }
                .opt-param-value {
                    color: #ffffff;
                    font-weight: 700;
                    font-size: 1rem;
                }
                .opt-metrics-section {
                    display: flex;
                    gap: 30px;
                    flex-wrap: wrap;
                    padding-top: 12px;
                    border-top: 1px solid rgba(255,255,255,0.15);
                }
                .opt-metric-item {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .opt-metric-label {
                    color: #9999aa;
                    font-size: 0.8rem;
                    font-weight: 500;
                }
                .opt-metric-value {
                    font-weight: 700;
                    font-size: 0.95rem;
                }
                .opt-metric-value.opt-positive { color: #00ff88; text-shadow: 0 0 10px rgba(0,255,136,0.3); }
                .opt-metric-value.opt-negative { color: #ff6b7a; text-shadow: 0 0 10px rgba(255,107,122,0.3); }
                .opt-metric-value.opt-neutral { color: #ffffff; }
                .opt-sharpe-bar-container {
                    width: 70px;
                    height: 8px;
                    background: #3a3a5a;
                    border-radius: 4px;
                    overflow: hidden;
                    margin-left: 10px;
                }
                .opt-sharpe-bar {
                    height: 100%;
                    background: linear-gradient(90deg, #00ff88 0%, #00d4ff 100%);
                    border-radius: 4px;
                    box-shadow: 0 0 8px rgba(0,255,136,0.5);
                }
                </style>
                """, unsafe_allow_html=True)
                
                # Start results container
                st.markdown('<div class="opt-results-container">', unsafe_allow_html=True)
                
                for idx, res in enumerate(top_results):
                    # Determine rank styling
                    rank = idx + 1
                    if rank == 1:
                        rank_class = "opt-gold"
                        rank_emoji = "🥇"
                        row_class = "opt-gold"
                    elif rank == 2:
                        rank_class = "opt-silver"
                        rank_emoji = "🥈"
                        row_class = "opt-silver"
                    elif rank == 3:
                        rank_class = "opt-bronze"
                        rank_emoji = "🥉"
                        row_class = "opt-bronze"
                    else:
                        rank_class = "opt-normal"
                        rank_emoji = f"#{rank}"
                        row_class = ""
                    
                    # Extract values
                    sl_pct = res.params.get('stop_loss_pct', 0)
                    tp_pct = res.params.get('take_profit_pct', 0)
                    entry_th = int(res.params.get('entry_threshold', 0))
                    
                    # Return color
                    return_color = "opt-positive" if res.total_return >= 0 else "opt-negative"
                    win_color = "opt-positive" if res.win_rate >= 50 else "opt-negative" if res.win_rate < 40 else "opt-neutral"
                    sharpe_color = "opt-positive" if res.sharpe_ratio >= 1.0 else "opt-neutral" if res.sharpe_ratio >= 0.5 else "opt-negative"
                    
                    # Sharpe bar width (max 2.0 = 100%)
                    sharpe_width = min(res.sharpe_ratio / 2.0 * 100, 100)
                    
                    # Build the row HTML
                    row_html = f'''
                    <div class="opt-result-row {row_class}">
                        <div style="display: flex; align-items: flex-start; gap: 15px;">
                            <span class="opt-rank-badge {rank_class}">{rank_emoji}</span>
                            <div style="flex: 1;">
                                <div class="opt-params-section">
                                    <div class="opt-param-item">
                                        <span class="opt-param-label">🛑 SL:</span>
                                        <span class="opt-param-value">{sl_pct:.1f}%</span>
                                    </div>
                                    <div class="opt-param-item">
                                        <span class="opt-param-label">🎯 TP:</span>
                                        <span class="opt-param-value">{tp_pct:.1f}%</span>
                                    </div>
                                    <div class="opt-param-item">
                                        <span class="opt-param-label">📊 Entry:</span>
                                        <span class="opt-param-value">{entry_th}</span>
                                    </div>
                                    <div class="opt-param-item">
                                        <span class="opt-param-label">📈 Trades:</span>
                                        <span class="opt-param-value">{res.total_trades}</span>
                                    </div>
                                </div>
                                <div class="opt-metrics-section">
                                    <div class="opt-metric-item">
                                        <span class="opt-metric-label">Return:</span>
                                        <span class="opt-metric-value {return_color}">{res.total_return:+.2f}%</span>
                                    </div>
                                    <div class="opt-metric-item">
                                        <span class="opt-metric-label">Win Rate:</span>
                                        <span class="opt-metric-value {win_color}">{res.win_rate:.1f}%</span>
                                    </div>
                                    <div class="opt-metric-item">
                                        <span class="opt-metric-label">Sharpe:</span>
                                        <span class="opt-metric-value {sharpe_color}">{res.sharpe_ratio:.2f}</span>
                                        <div class="opt-sharpe-bar-container">
                                            <div class="opt-sharpe-bar" style="width: {sharpe_width}%;"></div>
                                        </div>
                                    </div>
                                    <div class="opt-metric-item">
                                        <span class="opt-metric-label">Max DD:</span>
                                        <span class="opt-metric-value opt-negative">-{res.max_drawdown:.1f}%</span>
                                    </div>
                                    <div class="opt-metric-item">
                                        <span class="opt-metric-label">PF:</span>
                                        <span class="opt-metric-value opt-neutral">{res.profit_factor:.2f}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    '''
                    st.markdown(row_html, unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Summary note
                st.markdown("""
                <p style="color: #6c757d; font-size: 0.75rem; margin-top: 10px; text-align: center;">
                    💡 Use "Apply Best Values" button above to apply the #1 configuration to your backtest settings
                </p>
                """, unsafe_allow_html=True)
            else:
                st.warning("No results to display. Run the optimization first.")
    
    # ═══════════════════════════════════════════════════════════════════
    # EXPLANATION
    # ═══════════════════════════════════════════════════════════════════
    with st.expander("ℹ️ How It Works", expanded=False):
        st.markdown("""
        ### Confidence Score Calculation
        
        The system calculates a **confidence score** from -100 (strong SHORT) to +100 (strong LONG) 
        based on three technical indicators:
        
        | Indicator | Contribution | Logic |
        |-----------|-------------|-------|
        | **RSI** | ±33.33 | RSI < 30 = LONG, RSI > 70 = SHORT |
        | **MACD** | ±33.33 | MACD > Signal = LONG, MACD < Signal = SHORT |
        | **Bollinger** | ±33.33 | Price near lower = LONG, near upper = SHORT |
        
        ### Entry Rules
        - **LONG Entry**: Confidence > +Entry Threshold
        - **SHORT Entry**: Confidence < -Entry Threshold
        
        ### Exit Rules
        - **Stop Loss**: Exit if loss exceeds SL % (if enabled)
        - **Take Profit**: Exit if profit exceeds TP % (if enabled)
        - **Max Holding**: Exit after N candles (if enabled)
        - **Signal Reversal**: Exit on opposite signal (after min holding)
        
        ### Chart Legend
        - **▲ Green Triangle**: LONG entry point
        - **▼ Red Triangle**: SHORT entry point  
        - **✗ Green X**: Exit with profit
        - **✗ Red X**: Exit with loss
        - **Dotted Lines**: Trade duration (green = profit, red = loss)
        """)
