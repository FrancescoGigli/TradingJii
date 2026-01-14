"""
🎯 Signals Display - Dual signal comparison (Tech vs XGB)
"""

import streamlit as st
from ai.core.config import get_confidence_level
from ai.visualizations.backtest_charts import create_confidence_gauge


def render_signal_comparison(result, ml_service, df_full, entry_threshold: int):
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
    
    # Get current technical signal
    current_confidence = result.confidence_scores.iloc[-1]
    level_info = get_confidence_level(current_confidence)
    components_data = result.signal_components
    
    # Get ML inference
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
        _render_xgb_signal(ml_service, ml_prediction)
    
    # ═══════════════════════════════════════════════════════════════════
    # SIGNAL COMPARISON SUMMARY
    # ═══════════════════════════════════════════════════════════════════
    _render_signal_summary(current_confidence, ml_service, ml_prediction)
    
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
    st.plotly_chart(gauge_fig, use_container_width=True, key="gauge_tech")
    
    # Components breakdown
    st.markdown("**📈 Component Scores:**")
    rsi_score = components_data.rsi_score.iloc[-1]
    macd_score = components_data.macd_score.iloc[-1]
    bb_score = components_data.bb_score.iloc[-1]
    
    c1, c2, c3 = st.columns(3)
    c1.metric("RSI", f"{rsi_score:+.1f}")
    c2.metric("MACD", f"{macd_score:+.1f}")
    c3.metric("BB", f"{bb_score:+.1f}")


def _render_xgb_signal(ml_service, ml_prediction):
    """Render XGB signal column"""
    st.markdown("#### 🤖 XGBoost Model")
    st.caption("69 Technical Features → ML Prediction")
    
    if ml_service.is_available and ml_prediction and ml_prediction.is_valid:
        # Use normalized score (same range as Signal Calculator)
        xgb_score_long = ml_prediction.score_long_normalized
        xgb_score_short = ml_prediction.score_short_normalized
        
        # Determine main signal
        combined_xgb = xgb_score_long - xgb_score_short
        
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
            <p style="color: #888; margin: 0 0 10px 0; font-size: 0.9rem;">XGB SCORE (Normalized)</p>
            <p style="font-size: 3rem; margin: 0 0 10px 0; color: {xgb_color}; font-weight: 800;">
                {xgb_score_long:+.1f}
            </p>
            <p style="color: {xgb_color}; margin: 0; font-size: 1.1rem; font-weight: 600;">
                {ml_prediction.signal_long} ({ml_prediction.confidence_long}) → {xgb_signal}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # XGB gauge
        xgb_gauge_fig = create_confidence_gauge(xgb_score_long)
        st.plotly_chart(xgb_gauge_fig, use_container_width=True, key="gauge_xgb")
        
        # LONG and SHORT scores
        st.markdown("**📈 Model Scores:**")
        c1, c2, c3 = st.columns(3)
        
        long_delta = f"raw: {ml_prediction.score_long:+.5f}"
        c1.metric("📈 LONG", f"{xgb_score_long:+.1f}", delta=long_delta)
        
        short_delta = f"raw: {ml_prediction.score_short:+.5f}"
        c2.metric("📉 SHORT", f"{xgb_score_short:+.1f}", delta=short_delta)
        
        c3.metric("🔄 Model", ml_prediction.model_version[:8])
    
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


def _render_signal_summary(current_confidence, ml_service, ml_prediction):
    """Render signal comparison summary"""
    st.markdown("---")
    st.markdown("#### 🔍 Signal Comparison")
    
    if ml_service.is_available and ml_prediction and ml_prediction.is_valid:
        xgb_norm = ml_prediction.score_long_normalized
        
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
                <p style="color: #888; margin: 0 0 5px 0; font-size: 0.8rem;">🤖 XGBoost</p>
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
