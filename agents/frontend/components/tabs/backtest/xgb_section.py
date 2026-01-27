"""
🤖 XGB Section - XGBoost ML backtest chart and simulation

Includes:
- XGB signal visualization
- Trade simulation with trailing stop
- Trailing stop optimization for live trading
"""

import streamlit as st
import pandas as pd
from datetime import datetime


def _render_date_range_info(df_full, ml_service):
    """
    Render backtest date range info and check for overlap with training data.
    
    Shows:
    - Current backtest date range
    - Model training date range (if available)
    - Warning if backtest overlaps with training data (in-sample)
    """
    # Get backtest date range
    if 'timestamp' in df_full.columns:
        backtest_start = pd.to_datetime(df_full['timestamp'].min())
        backtest_end = pd.to_datetime(df_full['timestamp'].max())
    else:
        backtest_start = df_full.index.min()
        backtest_end = df_full.index.max()
    
    # Try to get model metadata
    model_metadata = ml_service.get_metadata() if hasattr(ml_service, 'get_metadata') else None
    
    # Build info card
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        <div style="background: #252542; padding: 12px 15px; border-radius: 8px; border-left: 4px solid #00d4ff;">
            <p style="color: #888; margin: 0; font-size: 0.75rem;">📊 BACKTEST DATA RANGE</p>
            <p style="color: white; margin: 5px 0; font-weight: 600;">
                {backtest_start.strftime('%Y-%m-%d %H:%M')} → {backtest_end.strftime('%Y-%m-%d %H:%M')}
            </p>
            <p style="color: #00d4ff; margin: 0; font-size: 0.8rem;">
                {len(df_full):,} candles
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if model_metadata and 'data_range' in model_metadata:
            data_range = model_metadata['data_range']
            train_end = data_range.get('train_end')
            
            if train_end:
                train_end_dt = pd.to_datetime(train_end)
                train_start_dt = pd.to_datetime(data_range.get('train_start', train_end))
                
                st.markdown(f"""
                <div style="background: #252542; padding: 12px 15px; border-radius: 8px; border-left: 4px solid #ffaa00;">
                    <p style="color: #888; margin: 0; font-size: 0.75rem;">🤖 MODEL TRAINING DATA</p>
                    <p style="color: white; margin: 5px 0; font-weight: 600;">
                        {train_start_dt.strftime('%Y-%m-%d')} → {train_end_dt.strftime('%Y-%m-%d')}
                    </p>
                    <p style="color: #ffaa00; margin: 0; font-size: 0.8rem;">
                        Model: {model_metadata.get('version', 'unknown')}
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                # Check for overlap
                if backtest_start < train_end_dt:
                    overlap_pct = 0
                    if backtest_end > train_start_dt:
                        # Calculate overlap
                        overlap_start = max(backtest_start, train_start_dt)
                        overlap_end = min(backtest_end, train_end_dt)
                        if overlap_end > overlap_start:
                            total_backtest = (backtest_end - backtest_start).total_seconds()
                            overlap_seconds = (overlap_end - overlap_start).total_seconds()
                            overlap_pct = (overlap_seconds / total_backtest) * 100
                    
                    if overlap_pct > 0:
                        st.warning(f"""
                        ⚠️ **IN-SAMPLE WARNING**: {overlap_pct:.1f}% of backtest data was seen during training!
                        
                        - Model trained until: **{train_end_dt.strftime('%Y-%m-%d')}**
                        - Backtest starts from: **{backtest_start.strftime('%Y-%m-%d')}**
                        
                        For valid out-of-sample testing, use data **after {train_end_dt.strftime('%Y-%m-%d')}**.
                        """)
                elif backtest_start > train_end_dt:
                    st.success(f"✅ **OUT-OF-SAMPLE**: Backtest uses data after model training (valid test)")
            else:
                st.markdown(f"""
                <div style="background: #252542; padding: 12px 15px; border-radius: 8px; border-left: 4px solid #888;">
                    <p style="color: #888; margin: 0; font-size: 0.75rem;">🤖 MODEL TRAINING DATA</p>
                    <p style="color: #888; margin: 5px 0;">
                        ⚠️ Training dates not saved in model metadata
                    </p>
                    <p style="color: #888; margin: 0; font-size: 0.8rem;">
                        Re-train model to save date ranges
                    </p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: #252542; padding: 12px 15px; border-radius: 8px; border-left: 4px solid #888;">
                <p style="color: #888; margin: 0; font-size: 0.75rem;">🤖 MODEL TRAINING DATA</p>
                <p style="color: #888; margin: 5px 0;">
                    ⚠️ No metadata available
                </p>
                <p style="color: #888; margin: 0; font-size: 0.8rem;">
                    Re-train model to save date ranges
                </p>
            </div>
            """, unsafe_allow_html=True)


def render_xgb_section(df_full, ml_service, selected_name: str, xgb_data: pd.DataFrame | None = None):
    """
    Render XGBoost ML backtest section with simulation.
    
    Args:
        df_full: Full OHLCV DataFrame
        ml_service: ML inference service
        selected_name: Selected symbol name
    """
    st.markdown("---")
    st.markdown("### 🤖 XGBoost ML Backtest Chart")
    
    if not ml_service.is_available:
        st.warning(f"""
        **⚠️ XGBoost Model Not Available**
        
        {ml_service.error_message or 'Models not found'}
        
        **To enable:**
        1. Run training: `python agents/ml-training/train.py`
        2. Copy models to container
        3. Restart frontend
        """)
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # SHOW BACKTEST DATE RANGE AND MODEL TRAINING DATES
    # ═══════════════════════════════════════════════════════════════════
    _render_date_range_info(df_full, ml_service)
    
    st.markdown("""
    <p style="color: #a0a0a0; font-size: 0.85rem;">
    XGBoost ML model predictions using <b>69 technical features</b>.
    Simulate trades with <b>Trailing Stop</b> for realistic backtest.
    Scores normalized using <b>Percentile Ranking</b>.
    </p>
    """, unsafe_allow_html=True)

    # Reserve UI space for diagnostics.
    # NOTE: We render the expander *after* running inference so the report always
    # reflects the current backtest run (and not a stale report from another tab).
    diagnostics_placeholder = st.empty()
    
    # XGB Settings in expander
    xgb_settings = _render_xgb_settings()
    
    # Calculate XGB scores if not precomputed
    if xgb_data is None:
        xgb_data = _compute_xgb_scores(df_full, ml_service)

    # Feature alignment diagnostics (rendered after inference to avoid stale data)
    with diagnostics_placeholder.container():
        _render_feature_alignment_diagnostics(
            ml_service,
            context_note="Based on the latest batch inference executed in this backtest run.",
        )
    
    if xgb_data is None:
        st.warning("⚠️ Could not generate XGB signals")
        return
    
    # Create XGB chart
    _render_xgb_chart(df_full, xgb_data, selected_name, xgb_settings['threshold'])
    
    # XGB signal statistics
    _render_xgb_statistics(xgb_data, xgb_settings['threshold'])
    
    # XGB Simulation section
    _render_xgb_simulation(df_full, xgb_data, xgb_settings, selected_name)
    
    # ═══════════════════════════════════════════════════════════════════
    # TRAILING STOP OPTIMIZATION SECTION
    # ═══════════════════════════════════════════════════════════════════
    from .optimization import render_optimization_section
    render_optimization_section(df_full, xgb_data, selected_name)


def _render_xgb_settings() -> dict:
    """Render XGB simulation settings and return values"""
    with st.expander("⚙️ XGB Simulation Settings", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            threshold = st.slider(
                "🎯 Entry Threshold",
                min_value=10,
                max_value=80,
                value=40,
                step=5,
                help="XGB score threshold to enter trades"
            )
        
        with col2:
            stop_loss = st.slider(
                "🛑 Stop Loss %",
                min_value=0.5,
                max_value=5.0,
                value=2.0,
                step=0.5,
                help="Fixed stop loss percentage"
            )
        
        with col3:
            take_profit = st.slider(
                "🎯 Take Profit %",
                min_value=1.0,
                max_value=10.0,
                value=4.0,
                step=0.5,
                help="Take profit percentage"
            )
        
        with col4:
            trailing_stop = st.slider(
                "📈 Trailing Stop %",
                min_value=0.5,
                max_value=3.0,
                value=1.5,
                step=0.5,
                help="Trailing stop percentage (activated after profit)"
            )
        
        col1, col2 = st.columns(2)
        with col1:
            trailing_activation = st.slider(
                "🔓 Trailing Activation %",
                min_value=0.5,
                max_value=3.0,
                value=1.0,
                step=0.5,
                help="Profit % needed to activate trailing stop"
            )
        with col2:
            max_holding = st.slider(
                "⏰ Max Holding (candles)",
                min_value=0,
                max_value=100,
                value=50,
                step=10,
                help="Force exit after N candles (0=disabled)"
            )
    
    return {
        'threshold': threshold,
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'trailing_stop': trailing_stop,
        'trailing_activation': trailing_activation,
        'max_holding': max_holding
    }


def _compute_xgb_scores(df_full, ml_service):
    """Compute XGB scores for all candles"""
    try:
        from services.ml_inference import compute_ml_features, build_normalized_xgb_frame
        
        with st.spinner("🔄 Computing 69 features and running XGB inference..."):
            # Compute all 69 features required by the model
            df_with_features = compute_ml_features(df_full)
            
            # Predict batch with all features
            df_with_predictions = ml_service.predict_batch(df_with_features)
            
            if 'pred_score_long' in df_with_predictions.columns:
                # Canonical normalization (0..100 long/short + net -100..+100)
                xgb_data = build_normalized_xgb_frame(df_with_predictions)
                
                # Debug stats
                with st.expander("📊 XGB Score Debug (Ranking-Based)", expanded=False):
                    st.info("⚡ Model uses **PERCENTILE RANKING** (canonical normalization)")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**LONG Model Raw:**")
                        st.write(f"Min: {df_with_predictions['pred_score_long'].min():.6f}")
                        st.write(f"Max: {df_with_predictions['pred_score_long'].max():.6f}")
                        st.write(f"Mean: {df_with_predictions['pred_score_long'].mean():.6f}")
                        st.write("**Normalized (0..100):**")
                        st.write(f"Range: {xgb_data['score_long_0_100'].min():.0f} to {xgb_data['score_long_0_100'].max():.0f}")
                    with col2:
                        st.write("**SHORT Model Raw:**")
                        st.write(f"Min: {df_with_predictions['pred_score_short'].min():.6f}")
                        st.write(f"Max: {df_with_predictions['pred_score_short'].max():.6f}")
                        st.write(f"Mean: {df_with_predictions['pred_score_short'].mean():.6f}")
                        st.write("**Normalized (0..100):**")
                        st.write(f"Range: {xgb_data['score_short_0_100'].min():.0f} to {xgb_data['score_short_0_100'].max():.0f}")
                
                return xgb_data
            
    except Exception as e:
        st.error(f"❌ Error calculating XGB scores: {e}")
    
    return None


def _render_feature_alignment_diagnostics(ml_service, *, context_note: str | None = None):
    """Show alignment diagnostics to detect heavy feature auto-filling.

    The report is computed during the last inference call via
    `align_features_dataframe_with_report`.
    """
    report = None
    if hasattr(ml_service, 'get_alignment_report'):
        report = ml_service.get_alignment_report()

    # Report is available only after at least one inference call.
    with st.expander("🧩 Feature Alignment Diagnostics", expanded=False):
        if context_note:
            st.caption(context_note)

        if report is None:
            st.caption(
                "Run XGB inference once to see alignment diagnostics. "
                "If many features are missing and get auto-filled, results can be misleading."
            )
            return

        missing = report.filled_count
        expected = report.expected_count
        dropped = report.dropped_count
        ratio = report.filled_ratio * 100

        col1, col2, col3 = st.columns(3)
        col1.metric("Expected features", expected)
        col2.metric("Missing (auto-filled)", missing)
        col3.metric("Extra (dropped)", dropped)

        if ratio <= 5:
            st.success(f"✅ Alignment looks good: only {ratio:.1f}% features were auto-filled")
        elif ratio <= 20:
            st.warning(f"⚠️ Alignment warning: {ratio:.1f}% features were auto-filled")
        else:
            st.error(
                f"❌ Alignment is likely unreliable: {ratio:.1f}% features were auto-filled. "
                "Backtest/inference results may be distorted."
            )

        if report.missing_features:
            st.caption("Missing features (first 25):")
            st.code("\n".join(report.missing_features[:25]))


def _render_xgb_chart(df_full, xgb_data, selected_name: str, threshold: float):
    """Render XGB-only chart"""
    from ai.visualizations.backtest_charts import create_xgb_chart
    xgb_fig = create_xgb_chart(df_full, xgb_data, selected_name, threshold)
    st.plotly_chart(xgb_fig, width='stretch', key="xgb_chart")


def _render_xgb_statistics(xgb_data, threshold: float):
    """Render XGB signal statistics"""
    # Use net score for direction thresholds
    long_signals = (xgb_data['net_score_-100_100'] > threshold).sum()
    short_signals = (xgb_data['net_score_-100_100'] < -threshold).sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📈 XGB LONG Signals", long_signals)
    col2.metric("📉 XGB SHORT Signals", short_signals)
    col3.metric("📊 Total XGB Signals", long_signals + short_signals)


def _render_xgb_simulation(df_full, xgb_data, settings: dict, selected_name: str):
    """Render XGB simulation with trailing stop"""
    st.markdown("---")
    st.markdown("#### 🎯 XGB Trade Simulation (with Trailing Stop)")
    
    if st.button("🚀 Run XGB Simulation", type="primary", use_container_width=True, key="run_xgb_sim"):
        try:
            from ai.backtest.xgb_simulator import run_xgb_simulation, XGBSimulatorConfig
            
            # Create config from settings
            xgb_config = XGBSimulatorConfig(
                entry_threshold=settings['threshold'],
                stop_loss_pct=settings['stop_loss'],
                take_profit_pct=settings['take_profit'],
                trailing_stop_pct=settings['trailing_stop'],
                trailing_activation_pct=settings['trailing_activation'],
                max_holding_candles=settings['max_holding'],
                min_holding_candles=2
            )
            
            with st.spinner("🔄 Running XGB simulation with trailing stop..."):
                # Run simulation
                xgb_sim_result = run_xgb_simulation(
                    df=df_full,
                    xgb_scores=xgb_data['net_score_-100_100'],
                    config=xgb_config
                )
                
                # Store in session state
                st.session_state['xgb_sim_result'] = xgb_sim_result
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Error running XGB simulation: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # Display results if available
    if 'xgb_sim_result' in st.session_state:
        _display_simulation_results(st.session_state['xgb_sim_result'], selected_name)


def _display_simulation_results(xgb_sim_result, selected_name: str):
    """Display XGB simulation results"""
    from ai.visualizations.xgb_charts import create_xgb_simulation_chart, create_xgb_stats_table
    
    xgb_stats = xgb_sim_result.get_statistics()
    
    try:
        # Show stats table
        st.markdown(create_xgb_stats_table(xgb_stats), unsafe_allow_html=True)
        
        # Create and display simulation chart
        xgb_sim_fig = create_xgb_simulation_chart(xgb_sim_result, selected_name)
        st.plotly_chart(xgb_sim_fig, width='stretch', key="xgb_sim_chart")
        
        # Trade list
        if xgb_sim_result.trades:
            with st.expander(f"📋 XGB Trade Details ({len(xgb_sim_result.trades)} trades)", expanded=False):
                for trade in xgb_sim_result.trades:
                    trade_emoji = "🟢" if trade.trade_type.value == "LONG" else "🔴"
                    result_emoji = "✅" if trade.is_winner else "❌"
                    exit_reason = trade.exit_reason.value if trade.exit_reason else "N/A"
                    
                    st.markdown(f"""
                    <div style="background: #1e1e2e; padding: 10px 15px; border-radius: 8px; margin: 5px 0; 
                                border-left: 3px solid {'#00ff88' if trade.is_winner else '#ff4757'};">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span>{result_emoji} {trade_emoji} <b>#{trade.trade_id}</b> {trade.trade_type.value}</span>
                            <span style="color: {'#00ff88' if trade.is_winner else '#ff4757'}; font-weight: 700;">
                                {trade.pnl_pct:+.2f}%
                            </span>
                        </div>
                        <div style="color: #888; font-size: 0.8rem; margin-top: 5px;">
                            Entry: ${trade.entry_price:,.2f} | Exit: ${trade.exit_price:,.2f} | 
                            <span style="color: #ffaa00;">{exit_reason}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
    except Exception as e:
        st.error(f"❌ Error displaying results: {e}")
