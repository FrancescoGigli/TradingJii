"""
🎯 Signals Display - Dual signal comparison (Tech vs XGB)
"""

import streamlit as st
from ai.core.config import get_confidence_level
from ai.visualizations.backtest_charts import create_confidence_gauge


def render_signal_comparison(
    result,
    ml_service,
    df_full,
    entry_threshold: int,
    xgb_data=None,
    xgb_frames: dict | None = None,
):
    """
    Render dual signal comparison: Technical vs XGBoost.
    
    Args:
        result: BacktestResult object
        ml_service: ML inference service
        df_full: Full OHLCV DataFrame
        entry_threshold: Entry threshold value
    """
    st.markdown("---")
    st.markdown("### 🎯 Current Signals Comparison")
    st.markdown("""
    <p style="color: #a0a0a0; font-size: 0.85rem;">
    Compare <b>Signal Calculator</b> (technical indicators) with <b>XGBoost ML Model</b> predictions.
    Both scores are normalized to <b>-100 / +100</b> range for easy comparison.
    </p>
    """, unsafe_allow_html=True)

    with st.expander("ℹ️ How XGB normalization works (why you may see +100)", expanded=False):
        st.markdown(
            """
**What you are looking at**

- **LONG (0..100)** and **SHORT (0..100)** are **percentile ranks** of the raw model outputs
  within the *currently selected window* (the candles you loaded in Test/Backtest).
- **NET (-100..+100)** is computed as:

  `NET = LONG_0_100 - SHORT_0_100`

**Why +100 can happen often**

- If the **latest candle** is the *top-ranked* LONG score in your window and/or the
  *bottom-ranked* SHORT score (after the optional “short inversion” step), the percentile rank
  becomes **100**, and the NET can reach **+100**.

**Important note**

- These values are **relative ranks**, not probabilities.
- If you want a less “extreme” display, we can switch the UI to show
  **rolling percentiles** (e.g., last 200 candles) instead of the full window.
            """
        )
    
    # Get current technical signal
    current_confidence = result.confidence_scores.iloc[-1]
    level_info = get_confidence_level(current_confidence)
    components_data = result.signal_components
    
    # Use precomputed batch-normalized scores if available.
    # This keeps the displayed score consistent with the XGB chart and simulation.
    xgb_last = None
    if xgb_data is not None and len(xgb_data) > 0:
        try:
            xgb_last = xgb_data.iloc[-1]
        except Exception:
            xgb_last = None

    # Keep raw model prediction for metadata (version) / availability checks.
    # Note: its built-in normalization may differ; we do NOT use it for the main score.
    last_row = df_full.iloc[-1]
    ml_prediction = ml_service.predict(last_row) if ml_service.is_available else None
    
    # Two main columns for the two systems
    col_tech, col_xgb = st.columns(2)
    
    # ═══════════════════════════════════════════════════════════════════
    # LEFT COLUMN: SIGNAL CALCULATOR (Technical Indicators)
    # ═══════════════════════════════════════════════════════════════════
    with col_tech:
        _render_technical_signal(current_confidence, level_info, components_data)
    
    # ═══════════════════════════════════════════════════════════════════
    # RIGHT COLUMN: XGB MODEL (Machine Learning)
    # ═══════════════════════════════════════════════════════════════════
    with col_xgb:
        _render_xgb_signal(ml_service, ml_prediction, xgb_last, xgb_data, xgb_frames)
    
    # ═══════════════════════════════════════════════════════════════════
    # SIGNAL COMPARISON SUMMARY
    # ═══════════════════════════════════════════════════════════════════
    _render_signal_summary(current_confidence, ml_service, ml_prediction, xgb_last)
    
    return current_confidence, ml_prediction


def _render_technical_signal(current_confidence, level_info, components_data):
    """Render technical signal column"""
    st.markdown("#### 📊 Signal Calculator")
    st.caption("RSI + MACD + Bollinger Bands")
    
    # Determine color based on score
    if current_confidence > 30:
        tech_color = "#00ff88"
        tech_signal = "LONG"
    elif current_confidence < -30:
        tech_color = "#ff4757"
        tech_signal = "SHORT"
    else:
        tech_color = "#ffaa00"
        tech_signal = "NEUTRAL"
    
    # Main score display
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                padding: 20px; border-radius: 12px; border-left: 5px solid {tech_color};
                text-align: center; margin-bottom: 15px;">
        <p style="color: #888; margin: 0 0 10px 0; font-size: 0.9rem;">CONFIDENCE SCORE</p>
        <p style="font-size: 3rem; margin: 0 0 10px 0; color: {tech_color}; font-weight: 800;">
            {current_confidence:+.1f}
        </p>
        <p style="color: {tech_color}; margin: 0; font-size: 1.1rem; font-weight: 600;">
            {level_info['label']} → {tech_signal}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Confidence gauge
    gauge_fig = create_confidence_gauge(current_confidence)
    st.plotly_chart(gauge_fig, width='stretch', key="gauge_tech")
    
    # Components breakdown
    st.markdown("**📈 Component Scores:**")
    rsi_score = components_data.rsi_score.iloc[-1]
    macd_score = components_data.macd_score.iloc[-1]
    bb_score = components_data.bb_score.iloc[-1]
    
    c1, c2, c3 = st.columns(3)
    c1.metric("RSI", f"{rsi_score:+.1f}")
    c2.metric("MACD", f"{macd_score:+.1f}")
    c3.metric("BB", f"{bb_score:+.1f}")


def _render_xgb_signal(ml_service, ml_prediction, xgb_last, xgb_data, xgb_frames):
    """Render XGB signal column"""
    st.markdown("#### 🤖 XGBoost Model")
    st.caption("69 Technical Features → ML Prediction")
    
    if xgb_frames:
        st.markdown("**⏱️ Timeframe models (side-by-side):**")

        # Deterministic ordering
        order = ["15m", "1h"]
        available = [tf for tf in order if tf in xgb_frames]
        available += [tf for tf in xgb_frames.keys() if tf not in available]

        cols = st.columns(len(available)) if available else []
        for idx, tf in enumerate(available):
            frame = xgb_frames.get(tf)
            if frame is None or len(frame) == 0:
                continue

            last = frame.iloc[-1]
            long_0_100 = float(last.get("score_long_0_100", 50.0))
            short_0_100 = float(last.get("score_short_0_100", 50.0))
            net = float(last.get("net_score_-100_100", 0.0))

            if net > 20:
                color = "#00ff88"
                direction = "LONG"
            elif net < -20:
                color = "#ff4757"
                direction = "SHORT"
            else:
                color = "#ffaa00"
                direction = "NEUTRAL"

            with cols[idx]:
                st.markdown(
                    f"""
<div style="background: #1e1e2e; padding: 12px; border-radius: 10px; border-left: 4px solid {color};">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
    <span style="color:#9ca3af; font-size:0.8rem;">Model</span>
    <span style="color:#e0e0ff; font-weight:700;">{tf}</span>
  </div>
  <div style="text-align:center;">
    <div style="color:{color}; font-size:1.8rem; font-weight:900; margin: 2px 0;">{net:+.1f}</div>
    <div style="color:#9ca3af; font-size:0.85rem;">NET (-100..+100)</div>
    <div style="color:#9ca3af; font-size:0.85rem; margin-top:6px;">LONG: {long_0_100:.1f} | SHORT: {short_0_100:.1f}</div>
    <div style="color:{color}; font-size:0.9rem; font-weight:700; margin-top:4px;">{direction}</div>
  </div>
</div>
                    """,
                    unsafe_allow_html=True,
                )

        # Still show gauges for the "primary" frame (xgb_data / xgb_last)
        if xgb_last is not None:
            st.markdown("---")
    
    if xgb_last is not None:
        # Canonical normalization: 0..100 for long/short and net -100..+100
        xgb_long_0_100 = float(xgb_last.get('score_long_0_100', 50.0))
        xgb_short_0_100 = float(xgb_last.get('score_short_0_100', 50.0))
        xgb_net = float(xgb_last.get('net_score_-100_100', 0.0))
        
        # Determine main signal (use net)
        combined_xgb = xgb_net
        
        if combined_xgb > 20:
            xgb_color = "#00ff88"
            xgb_signal = "LONG"
        elif combined_xgb < -20:
            xgb_color = "#ff4757"
            xgb_signal = "SHORT"
        else:
            xgb_color = "#ffaa00"
            xgb_signal = "NEUTRAL"
        
        # Main score display
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                    padding: 20px; border-radius: 12px; border-left: 5px solid {xgb_color};
                    text-align: center; margin-bottom: 15px;">
            <p style="color: #888; margin: 0 0 10px 0; font-size: 0.9rem;">XGB NET SCORE (Normalized)</p>
            <p style="font-size: 3rem; margin: 0 0 10px 0; color: {xgb_color}; font-weight: 800;">
                {combined_xgb:+.1f}
            </p>
            <p style="color: #9ca3af; margin: 0 0 6px 0; font-size: 0.85rem;">
                LONG: {xgb_long_0_100:.1f} / 100 &nbsp;|&nbsp; SHORT: {xgb_short_0_100:.1f} / 100
            </p>
            <p style="color: {xgb_color}; margin: 0; font-size: 1.1rem; font-weight: 600;">
                {xgb_signal}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # XGB gauge
        xgb_gauge_fig = create_confidence_gauge(combined_xgb)
        st.plotly_chart(xgb_gauge_fig, width='stretch', key="gauge_xgb")
        
        # LONG and SHORT scores
        st.markdown("**📈 Model Scores:**")
        c1, c2, c3 = st.columns(3)
        
        long_delta = f"raw: {float(xgb_last.get('score_long_raw', 0.0)):+.5f}" if xgb_last is not None else "raw: N/A"
        c1.metric("📈 LONG (0..100)", f"{xgb_long_0_100:.1f}", delta=long_delta)
        
        short_delta = f"raw: {float(xgb_last.get('score_short_raw', 0.0)):+.5f}" if xgb_last is not None else "raw: N/A"
        c2.metric("📉 SHORT (0..100)", f"{xgb_short_0_100:.1f}", delta=short_delta)
        
        if xgb_last is not None:
            short_inverted = bool(xgb_last.get("short_inverted", False))
        else:
            short_inverted = False

        model_label = "batch"
        if ml_prediction is not None:
            model_label = ml_prediction.model_version[:8]

        c3.metric(
            "🔄 Model",
            model_label,
            delta=f"short inverted: {'yes' if short_inverted else 'no'}",
        )

        if xgb_data is not None and len(xgb_data) > 0:
            with st.expander("📊 Normalization window stats", expanded=False):
                try:
                    st.write("**Window ranges (normalized):**")
                    st.write(
                        f"LONG 0..100 range: {xgb_data['score_long_0_100'].min():.0f} → {xgb_data['score_long_0_100'].max():.0f}"
                    )
                    st.write(
                        f"SHORT 0..100 range: {xgb_data['score_short_0_100'].min():.0f} → {xgb_data['score_short_0_100'].max():.0f}"
                    )
                    st.write(
                        f"NET -100..+100 range: {xgb_data['net_score_-100_100'].min():.1f} → {xgb_data['net_score_-100_100'].max():.1f}"
                    )
                except Exception:
                    st.caption("Window stats not available")
    
    else:
        # ML not available
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #2a1a1a 0%, #1a1a2e 100%); 
                    padding: 20px; border-radius: 12px; border-left: 5px solid #ff4757;
                    text-align: center; margin-bottom: 15px;">
            <p style="color: #888; margin: 0 0 10px 0; font-size: 0.9rem;">XGB SCORE</p>
            <p style="font-size: 2rem; margin: 0 0 10px 0; color: #ff4757; font-weight: 800;">
                N/A
            </p>
            <p style="color: #888; margin: 0; font-size: 0.9rem;">
                Model not loaded
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.warning(f"""
        **⚠️ ML Model Not Available**
        
        {ml_service.error_message or 'Models not found'}
        
        **To enable:**
        1. Run training: `python agents/ml-training/train.py`
        2. Restart frontend
        """)


def _render_signal_summary(current_confidence, ml_service, ml_prediction, xgb_last):
    """Render signal comparison summary"""
    st.markdown("---")
    st.markdown("#### 🔍 Signal Comparison")
    
    if ml_service.is_available and xgb_last is not None:
        xgb_norm = float(xgb_last.get('net_score_-100_100', 0.0))
        
        # Agreement check
        tech_direction = "LONG" if current_confidence > 20 else "SHORT" if current_confidence < -20 else "NEUTRAL"
        xgb_direction = "LONG" if xgb_norm > 20 else "SHORT" if xgb_norm < -20 else "NEUTRAL"
        
        if tech_direction == xgb_direction and tech_direction != "NEUTRAL":
            agreement_color = "#00ff88"
            agreement_text = f"✅ **AGREEMENT**: Both signals point to **{tech_direction}**"
        elif tech_direction == "NEUTRAL" or xgb_direction == "NEUTRAL":
            agreement_color = "#ffaa00"
            agreement_text = f"⏸️ **NEUTRAL**: Tech={tech_direction}, XGB={xgb_direction}"
        else:
            agreement_color = "#ff4757"
            agreement_text = f"❌ **CONFLICT**: Tech={tech_direction}, XGB={xgb_direction}"
        
        col1, col2, col3 = st.columns([2, 2, 2])
        
        with col1:
            st.markdown(f"""
            <div style="background: #1e1e2e; padding: 12px; border-radius: 8px; text-align: center;">
                <p style="color: #888; margin: 0 0 5px 0; font-size: 0.8rem;">📊 Technical</p>
                <p style="font-size: 1.5rem; margin: 0; color: {'#00ff88' if current_confidence > 20 else '#ff4757' if current_confidence < -20 else '#ffaa00'}; font-weight: 700;">
                    {current_confidence:+.1f}
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style="background: #1e1e2e; padding: 12px; border-radius: 8px; text-align: center;">
                <p style="color: #888; margin: 0 0 5px 0; font-size: 0.8rem;">🤖 XGBoost (net)</p>
                <p style="font-size: 1.5rem; margin: 0; color: {'#00ff88' if xgb_norm > 20 else '#ff4757' if xgb_norm < -20 else '#ffaa00'}; font-weight: 700;">
                    {xgb_norm:+.1f}
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div style="background: #1e1e2e; padding: 12px; border-radius: 8px; text-align: center; border-left: 3px solid {agreement_color};">
                <p style="color: #888; margin: 0 0 5px 0; font-size: 0.8rem;">Status</p>
                <p style="font-size: 1rem; margin: 0; color: {agreement_color}; font-weight: 600;">
                    {tech_direction} vs {xgb_direction}
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        st.info(agreement_text)
    else:
        st.info("📊 Technical Signal: **{:.1f}** | 🤖 XGB: **N/A** (model not loaded)".format(current_confidence))
