"""
🎯 Trailing Optimization Section
================================

Frontend component for trailing stop optimization:
- Parameter grid selection
- Progress visualization
- Results with equity curves and metrics
- Best configuration for live trading
"""

import streamlit as st
import pandas as pd
from typing import Optional

from styles.tables import render_html_table

from ai.optimizer.trailing_optimizer import (
    TrailingStopOptimizer,
    TrailingOptimizationResult,
    OptimizationMetric,
    run_trailing_optimization
)
from ai.visualizations.optimization_charts import (
    create_equity_comparison_chart,
    create_metrics_comparison_chart,
    create_optimization_summary_chart,
    create_best_config_card,
    create_ranking_table_html
)
from ai.visualizations.xgb_charts import create_xgb_simulation_chart


def render_optimization_section(df_full: pd.DataFrame, xgb_data: pd.DataFrame, symbol_name: str):
    """
    Render the trailing stop optimization section.
    
    Args:
        df_full: OHLCV DataFrame
        xgb_data: DataFrame with XGB scores
        symbol_name: Symbol name for display
    """
    st.markdown("---")
    st.markdown("### 🎯 Trailing Stop Optimization")
    st.markdown("""
    <p style="color: #a0a0a0; font-size: 0.85rem;">
    Find the <b>optimal trailing stop configuration</b> for live trading.
    Tests multiple combinations of SL, TP, Trailing Stop and ranks them by performance.
    </p>
    """, unsafe_allow_html=True)
    
    # Check if XGB data is available
    if xgb_data is None or 'xgb_score_long_norm' not in xgb_data.columns:
        st.warning("⚠️ XGB scores required. Run XGB inference first.")
        return
    
    # Optimization settings
    settings = _render_optimization_settings()
    
    # Estimate combinations
    optimizer = TrailingStopOptimizer()
    param_grid = optimizer.get_preset_grid(settings['preset'])
    estimated = optimizer.estimate_combinations(param_grid)
    
    # Info card
    _render_info_card(settings['preset'], estimated)
    
    # Run button
    col1, col2 = st.columns([3, 1])
    with col1:
        run_button = st.button(
            f"🚀 Run Optimization ({estimated} combinations)",
            type="primary",
            use_container_width=True,
            key="run_trailing_opt"
        )
    with col2:
        clear_button = st.button(
            "🗑️ Clear",
            use_container_width=True,
            key="clear_trailing_opt"
        )
    
    if clear_button and 'trailing_opt_result' in st.session_state:
        del st.session_state['trailing_opt_result']
        st.rerun()
    
    # Run optimization
    if run_button:
        _run_optimization(df_full, xgb_data, settings, symbol_name)
    
    # Display results if available
    if 'trailing_opt_result' in st.session_state:
        _display_optimization_results(st.session_state['trailing_opt_result'], symbol_name)


def _render_optimization_settings() -> dict:
    """Render optimization settings UI"""
    with st.expander("⚙️ Optimization Settings", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            preset = st.selectbox(
                "📊 Preset",
                options=['quick', 'default', 'comprehensive'],
                index=1,
                help="Quick: ~54 combinations\nDefault: ~600 combinations\nComprehensive: ~7000+ combinations",
                key="opt_preset"
            )
        
        with col2:
            sort_metric = st.selectbox(
                "📈 Sort By",
                options=['Sharpe Ratio', 'Total Return', 'Win Rate', 'Profit Factor', 'Risk Adjusted'],
                index=0,
                help="Metric to rank configurations",
                key="opt_sort_metric"
            )
        
        with col3:
            top_n = st.slider(
                "🏆 Show Top N",
                min_value=3,
                max_value=20,
                value=10,
                step=1,
                help="Number of top configurations to display",
                key="opt_top_n"
            )
        
        # Map sort metric to enum
        metric_map = {
            'Sharpe Ratio': OptimizationMetric.SHARPE_RATIO,
            'Total Return': OptimizationMetric.TOTAL_RETURN,
            'Win Rate': OptimizationMetric.WIN_RATE,
            'Profit Factor': OptimizationMetric.PROFIT_FACTOR,
            'Risk Adjusted': OptimizationMetric.RISK_ADJUSTED
        }
        
        return {
            'preset': preset,
            'sort_metric': metric_map[sort_metric],
            'top_n': top_n
        }


def _render_info_card(preset: str, estimated: int):
    """Render info card about optimization"""
    preset_info = {
        'quick': ('⚡', '~30 seconds', 'Fast testing with core parameters'),
        'default': ('📊', '~2-3 minutes', 'Balanced coverage of parameters'),
        'comprehensive': ('🔬', '~10-15 minutes', 'Exhaustive search for best config')
    }
    
    icon, time_est, description = preset_info.get(preset, ('📊', 'Unknown', ''))
    
    st.markdown(f"""
    <div style="background: #252542; padding: 15px 20px; border-radius: 10px; margin: 10px 0;
                display: flex; justify-content: space-between; align-items: center;">
        <div>
            <span style="font-size: 1.2rem;">{icon}</span>
            <span style="color: white; margin-left: 10px;"><b>{preset.upper()}</b> preset</span>
            <span style="color: #888; margin-left: 10px;">- {description}</span>
        </div>
        <div style="text-align: right;">
            <span style="color: #00d4ff; font-weight: 600;">{estimated:,}</span>
            <span style="color: #888;"> combinations</span>
            <span style="color: #ffaa00; margin-left: 15px;">⏱️ {time_est}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _run_optimization(df_full: pd.DataFrame, xgb_data: pd.DataFrame, settings: dict, symbol_name: str):
    """Run the optimization with progress"""
    
    # Progress container
    progress_container = st.empty()
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def update_progress(current: int, total: int):
        progress = current / total
        progress_bar.progress(progress)
        status_text.markdown(f"""
        <div style="text-align: center; color: #888;">
            Testing configuration <b>{current}</b> / <b>{total}</b> 
            ({progress*100:.1f}%)
        </div>
        """, unsafe_allow_html=True)
    
    try:
        with st.spinner(f"🔄 Running optimization for {symbol_name}..."):
            # Run optimization
            result = run_trailing_optimization(
                df=df_full,
                xgb_scores=xgb_data['xgb_score_long_norm'],
                preset=settings['preset'],
                progress_callback=update_progress
            )
            
            # Store result
            st.session_state['trailing_opt_result'] = result
            st.session_state['trailing_opt_settings'] = settings
            
            # Clear progress
            progress_bar.empty()
            status_text.empty()
            progress_container.empty()
            
            st.success(f"""
            ✅ **Optimization Complete!**
            
            - Tested **{result.total_combinations}** configurations
            - Execution time: **{result.execution_time_sec:.1f}s**
            - Best Sharpe Ratio: **{result.best_by_sharpe.sharpe_ratio:.2f}** 
              (Return: {result.best_by_sharpe.total_return:+.1f}%)
            """)
            
            st.rerun()
            
    except Exception as e:
        st.error(f"❌ Optimization failed: {e}")
        import traceback
        st.code(traceback.format_exc())


def _render_best_config_native(best_result):
    """Render best configuration using native Streamlit components"""
    from ai.optimizer.trailing_optimizer import OptimizationResult
    
    config = best_result.config
    
    # Determine rating
    if best_result.sharpe_ratio >= 1 and best_result.win_rate >= 55:
        rating = "🏆 EXCELLENT"
        rating_type = "success"
    elif best_result.sharpe_ratio >= 0.5 and best_result.win_rate >= 50:
        rating = "✅ GOOD"
        rating_type = "info"
    elif best_result.profit_factor >= 1:
        rating = "⚠️ MODERATE"
        rating_type = "warning"
    else:
        rating = "❌ RISKY"
        rating_type = "error"
    
    # Header with rating
    st.markdown("#### 🎯 Best Configuration for Live Trading")
    
    if rating_type == "success":
        st.success(f"**Rating: {rating}**")
    elif rating_type == "info":
        st.info(f"**Rating: {rating}**")
    elif rating_type == "warning":
        st.warning(f"**Rating: {rating}**")
    else:
        st.error(f"**Rating: {rating}**")
    
    # Parameters section
    st.markdown("##### 📋 Parameters (Copy to Live)")
    col1, col2, col3 = st.columns(3)
    col1.metric("🛑 Stop Loss", f"{config.stop_loss_pct}%")
    col2.metric("🎯 Take Profit", f"{config.take_profit_pct}%")
    col3.metric("📊 Entry Threshold", f"{int(config.entry_threshold)}")
    
    col4, col5 = st.columns(2)
    col4.metric("📉 Trailing Stop", f"{config.trailing_stop_pct}%")
    col5.metric("🚀 Trailing Activation", f"{config.trailing_activation_pct}%")
    
    # Performance metrics
    st.markdown("##### 📊 Backtest Performance")
    perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
    
    return_delta = "positive" if best_result.total_return >= 0 else "negative"
    perf_col1.metric(
        "Total Return",
        f"{best_result.total_return:+.1f}%",
        delta=f"{best_result.total_return:+.1f}%",
        delta_color="normal" if best_result.total_return >= 0 else "inverse"
    )
    
    wr_delta = "positive" if best_result.win_rate >= 50 else "negative"
    perf_col2.metric(
        "Win Rate",
        f"{best_result.win_rate:.0f}%",
        delta=f"{best_result.win_rate - 50:.0f}% vs 50%",
        delta_color="normal" if best_result.win_rate >= 50 else "inverse"
    )
    
    perf_col3.metric("Sharpe Ratio", f"{best_result.sharpe_ratio:.2f}")
    perf_col4.metric("Profit Factor", f"{best_result.profit_factor:.2f}")
    
    # Risk metrics
    st.markdown("##### ⚠️ Risk Metrics")
    risk_col1, risk_col2, risk_col3, risk_col4 = st.columns(4)
    
    risk_col1.metric(
        "Max Drawdown",
        f"-{best_result.max_drawdown:.1f}%",
        delta=f"-{best_result.max_drawdown:.1f}%",
        delta_color="inverse"
    )
    risk_col2.metric(
        "Worst Trade",
        f"{best_result.worst_trade:+.1f}%"
    )
    risk_col3.metric(
        "Best Trade",
        f"{best_result.best_trade:+.1f}%"
    )
    risk_col4.metric(
        "Total Trades",
        f"{best_result.total_trades}"
    )


def _render_ranking_table_native(results, max_rows: int = 10):
    """Render ranking table using native Streamlit table"""
    # Build DataFrame from results
    data = []
    for i, r in enumerate(results[:max_rows]):
        rank = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"#{i+1}"
        data.append({
            "Rank": rank,
            "SL %": r.config.stop_loss_pct,
            "TP %": r.config.take_profit_pct,
            "TS %": r.config.trailing_stop_pct,
            "Act %": r.config.trailing_activation_pct,
            "Thr": int(r.config.entry_threshold),
            "Trades": r.total_trades,
            "Win %": f"{r.win_rate:.0f}%",
            "Return": f"{r.total_return:+.1f}%",
            "Sharpe": f"{r.sharpe_ratio:.2f}",
            "PF": f"{r.profit_factor:.2f}",
            "Max DD": f"{r.max_drawdown:.1f}%"
        })
    
    df = pd.DataFrame(data)
    
    # Display using styled HTML table (dark theme compatible)
    render_html_table(df, height=400)


def _display_optimization_results(result: TrailingOptimizationResult, symbol_name: str):
    """Display optimization results with charts and tables"""
    
    settings = st.session_state.get('trailing_opt_settings', {
        'sort_metric': OptimizationMetric.SHARPE_RATIO,
        'top_n': 10
    })
    
    # Get top results
    top_results = result.get_top_n(
        n=settings['top_n'],
        metric=settings['sort_metric']
    )
    
    if not top_results:
        st.warning("⚠️ No valid results found. Try with more data or different parameters.")
        return
    
    # Summary stats
    st.markdown("#### 📊 Optimization Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric(
        "Configurations Tested",
        f"{result.total_combinations:,}",
        f"⏱️ {result.execution_time_sec:.1f}s"
    )
    
    best = result.best_by_sharpe
    if best:
        col2.metric(
            "Best Return",
            f"{result.best_by_return.total_return:+.1f}%" if result.best_by_return else "N/A"
        )
        col3.metric(
            "Best Win Rate",
            f"{result.best_by_winrate.win_rate:.0f}%" if result.best_by_winrate else "N/A"
        )
        col4.metric(
            "Best Sharpe",
            f"{best.sharpe_ratio:.2f}"
        )
    
    # ═══════════════════════════════════════════════════════════════════
    # BEST CONFIGURATION CARD
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    if result.best_by_sharpe:
        _render_best_config_native(result.best_by_sharpe)
        
        # ═══════════════════════════════════════════════════════════════════
        # BEST CONFIG - CANDLESTICK WITH TRADES (Entry/Exit Points)
        # ═══════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.markdown("#### 📊 Best Config - Trade Visualization")
        st.caption("Candlestick chart with LONG/SHORT entry points and exit markers. Green lines = profit, Red lines = loss.")
        
        # The simulation_result is already an XGBSimulatorResult
        best_sim_result = result.best_by_sharpe.simulation_result
        best_config = result.best_by_sharpe.config
        
        if best_sim_result and len(best_sim_result.trades) > 0:
            try:
                # Build title with configuration parameters
                config_title = (
                    f"{symbol_name} | "
                    f"SL: {best_config.stop_loss_pct}% | "
                    f"TP: {best_config.take_profit_pct}% | "
                    f"TS: {best_config.trailing_stop_pct}% | "
                    f"Act: {best_config.trailing_activation_pct}% | "
                    f"Thr: {int(best_config.entry_threshold)}"
                )
                
                trades_fig = create_xgb_simulation_chart(
                    result=best_sim_result,
                    symbol=config_title,
                    show_trailing_stops=True
                )
                st.plotly_chart(trades_fig, use_container_width=True, key="best_config_trades_chart")
                
                # Trade summary
                stats = best_sim_result.get_statistics()
                st.info(f"""
                **Trade Summary:** {stats['total_trades']} trades 
                (LONG: {stats['long_trades']}, SHORT: {stats['short_trades']}) | 
                ✅ {stats['winning_trades']} wins | ❌ {stats['losing_trades']} losses | 
                📤 Exit Reasons: {', '.join([f"{k}: {v}" for k, v in stats.get('exit_reasons', {}).items()])}
                """)
            except Exception as e:
                st.warning(f"⚠️ Could not render trades chart: {e}")
        else:
            st.info("ℹ️ No trades executed with this configuration.")
    
    # ═══════════════════════════════════════════════════════════════════
    # EQUITY CURVES COMPARISON
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("#### 📈 Top Configurations - Equity Curves")
    
    equity_fig = create_equity_comparison_chart(
        top_results,
        title=f"Top {len(top_results)} Configurations - {symbol_name}"
    )
    st.plotly_chart(equity_fig, use_container_width=True, key="equity_comparison")
    
    # ═══════════════════════════════════════════════════════════════════
    # METRICS COMPARISON
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("#### 📊 Performance Metrics Comparison")
    
    metrics_fig = create_metrics_comparison_chart(
        top_results,
        title=f"Metrics Comparison - Top {len(top_results)}"
    )
    st.plotly_chart(metrics_fig, use_container_width=True, key="metrics_comparison")
    
    # ═══════════════════════════════════════════════════════════════════
    # RISK-RETURN SCATTER
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("#### 🎯 Risk-Return Analysis")
    
    summary_fig = create_optimization_summary_chart(result)
    st.plotly_chart(summary_fig, use_container_width=True, key="risk_return_scatter")
    
    # ═══════════════════════════════════════════════════════════════════
    # RANKING TABLE
    # ═══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("#### 🏆 Top Configurations Ranking")
    
    _render_ranking_table_native(top_results, max_rows=settings['top_n'])
    
    # ═══════════════════════════════════════════════════════════════════
    # DETAILED RESULTS (Expandable)
    # ═══════════════════════════════════════════════════════════════════
    with st.expander(f"📋 All Results ({len(result.results)} configurations)", expanded=False):
        # Show DataFrame
        df_results = result.to_dataframe()
        if not df_results.empty:
            render_html_table(df_results.head(50), height=500)  # Limit to 50 rows
            
            # Download button
            csv = df_results.to_csv(index=False)
            st.download_button(
                "📥 Download Results CSV",
                data=csv,
                file_name=f"trailing_optimization_{symbol_name}.csv",
                mime="text/csv"
            )
