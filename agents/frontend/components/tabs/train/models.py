"""
📊 Train Tab - Step 4: ML Models Dashboard

Complete model viewer with:
- Model summary with quality badge
- Training analytics charts (optimization, metrics, precision@K)
- Feature importance visualization
- Saved AI analysis (from GPT-4o, no API call needed)
- Real-time inference on last 200 candles
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from typing import Dict, Any, Optional

from .models_inference import (
    get_model_dir, load_model_for_timeframe,
    get_realtime_symbols, fetch_realtime_data, compute_missing_indicators,
    run_inference, create_inference_chart, PLOTLY_AVAILABLE
)

# Import from shared modules (centralized)
from .shared import COLORS
from .shared.model_loader import get_available_models

# Import feature stats for reminder
from database import EXPECTED_FEATURE_COUNT

# Data model display component
from .data_model_display import render_step_data_model

# Import training charts
try:
    from ai.visualizations.training_charts import (
        create_dual_optimization_chart,
        create_metrics_comparison,
        create_precision_at_k_chart,
        create_training_summary_card
    )
    import plotly.graph_objects as go
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False


# ============================================================
# RENDERING COMPONENTS
# ============================================================

def _render_model_summary(models: dict):
    """Render model summary for 15m and 1h with tabs."""
    st.markdown("#### 📋 Trained Models")
    
    available_tfs = [tf for tf in ['15m', '1h'] if models[tf] is not None]
    
    if not available_tfs:
        st.warning("⚠️ **No trained models found.** Complete Step 3 (Training) first.")
        return
    
    # Create tabs for each timeframe
    tabs = st.tabs([f"{'🔵' if tf == '15m' else '🟢'} {tf.upper()} Model" for tf in available_tfs])
    
    for idx, tf in enumerate(available_tfs):
        with tabs[idx]:
            meta = models[tf]
            _render_single_model_summary(meta, tf)


def _render_single_model_summary(meta: Dict[str, Any], tf: str):
    """Render summary for a single timeframe model."""
    if not meta:
        return
    
    # Summary card
    if CHARTS_AVAILABLE:
        result_dict = {
            'success': True,
            'timeframe': tf,
            'version': meta.get('version', 'Unknown'),
            'metrics_long': meta.get('metrics_long', {}),
            'metrics_short': meta.get('metrics_short', {}),
            'n_features': meta.get('n_features', 0),
            'n_train': meta.get('n_train_samples', 0),
            'n_test': meta.get('n_test_samples', 0),
            'n_trials': meta.get('n_trials', 0),
            'error': ''
        }
        summary_html = create_training_summary_card(result_dict, tf)
        st.markdown(summary_html, unsafe_allow_html=True)
    
    # Quick stats
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 Features", meta.get('n_features', 0))
    col2.metric("📚 Train", f"{meta.get('n_train_samples', 0):,}")
    col3.metric("🧪 Test", f"{meta.get('n_test_samples', 0):,}")
    col4.metric("🎯 Trials", meta.get('n_trials', 0))
    
    # Training date and version
    created_at = meta.get('created_at', 'Unknown')
    version = meta.get('version', 'Unknown')
    st.caption(f"📅 Trained: `{created_at[:19].replace('T', ' ')}` | Version: `{version[:20]}...`")
    
    # === FEATURE REMINDER BOX (Phase 4 Output) ===
    n_features = meta.get('n_features', 0)
    expected = EXPECTED_FEATURE_COUNT
    is_ok = n_features >= expected - 5
    
    status_icon = "✅" if is_ok else "⚠️"
    color = "#00d4aa" if is_ok else "#ffaa00"
    
    feature_names = meta.get('feature_names', [])
    features_list = ", ".join(feature_names[:10])
    if len(feature_names) > 10:
        features_list += f", ... +{len(feature_names)-10} more"
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                padding: 12px 16px; border-radius: 8px; margin: 10px 0;
                border-left: 4px solid {color};">
        <span style="font-size: 14px; color: {color}; font-weight: bold;">
            {status_icon} Phase 4: Model trained with <code style="background: #333; padding: 2px 6px; border-radius: 4px;">{n_features}</code> features
        </span>
        <span style="color: #888; margin-left: 15px;">
            (expected: {expected})
        </span>
        <div style="color: #666; font-size: 12px; margin-top: 6px;">
            📊 <b>Features:</b> {features_list}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Warning if fewer features than expected
    if n_features < expected - 5:
        st.warning(f"⚠️ Model trained with only **{n_features}** features. Re-generate labels (Phase 2) and re-train (Phase 3) for **{expected}** features!")


def _render_training_analytics(models: dict):
    """Render training analytics section with charts."""
    st.divider()
    st.markdown("#### 📈 Training Analytics")
    
    available_tfs = [tf for tf in ['15m', '1h'] if models[tf] is not None]
    
    if not available_tfs:
        return
    
    # Timeframe selector
    selected_tf = st.selectbox(
        "Select Model", 
        available_tfs, 
        format_func=lambda x: f"{'🔵' if x == '15m' else '🟢'} {x.upper()} Model",
        key="analytics_tf"
    )
    
    meta = models[selected_tf]
    if not meta:
        return
    
    # Metrics comparison charts
    metrics_long = meta.get('metrics_long', {})
    metrics_short = meta.get('metrics_short', {})
    
    if CHARTS_AVAILABLE and metrics_long and metrics_short:
        col1, col2 = st.columns(2)
        
        with col1:
            fig = create_metrics_comparison(metrics_long, metrics_short)
            st.plotly_chart(fig, width='stretch', key=f"metrics_comp_{selected_tf}")
        
        with col2:
            fig = create_precision_at_k_chart(metrics_long, metrics_short)
            st.plotly_chart(fig, width='stretch', key=f"precision_k_{selected_tf}")
    
    # Optimization history
    trials_long = meta.get('trials_long', [])
    trials_short = meta.get('trials_short', [])
    
    if CHARTS_AVAILABLE and trials_long and trials_short:
        st.markdown("##### 🔄 Optimization History")
        fig = create_dual_optimization_chart(trials_long, trials_short)
        st.plotly_chart(fig, width='stretch', key=f"opt_history_{selected_tf}")


def _render_feature_importance(models: dict):
    """Render feature importance charts."""
    st.divider()
    st.markdown("#### 🔬 Feature Importance")
    
    available_tfs = [tf for tf in ['15m', '1h'] if models[tf] is not None]
    
    if not available_tfs:
        return
    
    selected_tf = st.selectbox(
        "Select Model", 
        available_tfs,
        format_func=lambda x: f"{'🔵' if x == '15m' else '🟢'} {x.upper()} Model",
        key="importance_tf"
    )
    
    meta = models[selected_tf]
    if not meta:
        return
    
    fi_long = meta.get('feature_importance_long', {})
    fi_short = meta.get('feature_importance_short', {})
    
    if not fi_long and not fi_short:
        st.info("⚠️ Feature importance not available. Re-train the model to generate it.")
        return
    
    if CHARTS_AVAILABLE and fi_long and fi_short:
        col1, col2 = st.columns(2)
        
        with col1:
            fig = _create_feature_importance_chart(fi_long, "LONG Model")
            st.plotly_chart(fig, width='stretch', key=f"fi_long_{selected_tf}")
        
        with col2:
            fig = _create_feature_importance_chart(fi_short, "SHORT Model")
            st.plotly_chart(fig, width='stretch', key=f"fi_short_{selected_tf}")
    
    # Feature list in expander
    features = meta.get('feature_names', [])
    if features:
        with st.expander(f"📋 Features List ({len(features)} total)"):
            st.write(", ".join(features))


def _create_feature_importance_chart(importance: Dict[str, float], title: str) -> 'go.Figure':
    """Create feature importance bar chart."""
    if not CHARTS_AVAILABLE:
        return None
    
    # Sort by importance
    sorted_items = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    features = [x[0] for x in sorted_items[:15]]  # Top 15
    values = [x[1] for x in sorted_items[:15]]
    
    # Colors
    colors = {
        'primary': '#00ffff',
        'secondary': '#ff6b6b',
        'background': '#0a0a1a',
        'card': '#1a1a2e',
        'text': '#e0e0ff',
        'grid': '#2a2a4a'
    }
    
    color = colors['primary'] if 'LONG' in title else colors['secondary']
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=features[::-1],
        x=values[::-1],
        orientation='h',
        marker_color=color,
        text=[f'{v:.3f}' for v in values[::-1]],
        textposition='outside'
    ))
    
    fig.update_layout(
        title=dict(text=f"📊 {title}", font=dict(size=14, color=colors['text'])),
        plot_bgcolor=colors['card'],
        paper_bgcolor=colors['background'],
        font=dict(color=colors['text']),
        xaxis=dict(gridcolor=colors['grid'], title="Importance"),
        yaxis=dict(gridcolor=colors['grid']),
        height=400,
        margin=dict(l=120, r=60)
    )
    
    return fig


def _render_ai_analysis(models: dict):
    """Render saved AI analysis from metadata."""
    st.divider()
    st.markdown("#### 🤖 AI Analysis")
    st.caption("Pre-computed analysis from training (no API call needed)")
    
    available_tfs = [tf for tf in ['15m', '1h'] if models[tf] is not None]
    
    if not available_tfs:
        return
    
    # Check if any model has AI analysis
    has_analysis = any(
        models[tf].get('ai_analysis') is not None 
        for tf in available_tfs
    )
    
    if not has_analysis:
        st.info("⚠️ No AI analysis saved. Enable AI Analysis during training to generate it.")
        return
    
    for tf in available_tfs:
        analysis = models[tf].get('ai_analysis')
        if analysis:
            st.markdown(f"##### {'🔵' if tf == '15m' else '🟢'} {tf.upper()} Analysis")
            _render_analysis_card(analysis)
            st.markdown("---")


def _render_analysis_card(analysis: Dict[str, Any]):
    """Render AI analysis as HTML card."""
    rating_colors = {
        'excellent': ('#4ade80', 'Excellent'),
        'good': ('#fbbf24', 'Good'),
        'acceptable': ('#f97316', 'Acceptable'),
        'poor': ('#ff6b6b', 'Poor')
    }
    
    rating = analysis.get('quality_rating', 'unknown')
    emoji = analysis.get('quality_emoji', '⚪')
    color, label = rating_colors.get(rating, ('#888', 'Unknown'))
    
    strengths = analysis.get('strengths', [])
    weaknesses = analysis.get('weaknesses', [])
    recommendations = analysis.get('recommendations', [])
    summary = analysis.get('summary', '')
    comparison = analysis.get('comparison_note', '')
    
    strengths_html = ''.join([f"<li style='color: #4ade80;'>✅ {s}</li>" for s in strengths])
    weaknesses_html = ''.join([f"<li style='color: #ff6b6b;'>⚠️ {w}</li>" for w in weaknesses])
    recommendations_html = ''.join([f"<li style='color: #00ffff;'>💡 {r}</li>" for r in recommendations])
    
    html = f"""
    <div style="
        background: linear-gradient(135deg, #1a1a2e, #2a2a4a);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid {color};
        color: white;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <span style="font-size: 14px; color: #e0e0ff;">{summary}</span>
            <span style="
                background: {color};
                color: black;
                padding: 4px 12px;
                border-radius: 20px;
                font-weight: bold;
            ">{emoji} {label}</span>
        </div>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;">
            <div>
                <h4 style="color: #4ade80; margin: 0 0 10px 0;">Strengths</h4>
                <ul style="margin: 0; padding-left: 20px; font-size: 13px;">{strengths_html}</ul>
            </div>
            <div>
                <h4 style="color: #ff6b6b; margin: 0 0 10px 0;">Weaknesses</h4>
                <ul style="margin: 0; padding-left: 20px; font-size: 13px;">{weaknesses_html}</ul>
            </div>
        </div>
        
        <div style="margin-top: 15px;">
            <h4 style="color: #00ffff; margin: 0 0 10px 0;">Recommendations</h4>
            <ul style="margin: 0; padding-left: 20px; font-size: 13px;">{recommendations_html}</ul>
        </div>
        
        {f'<div style="margin-top: 15px; padding: 10px; background: rgba(0,255,255,0.1); border-radius: 8px;"><strong>📊 Comparison:</strong> {comparison}</div>' if comparison else ''}
    </div>
    """
    
    st.markdown(html, unsafe_allow_html=True)


def _render_model_details(models: dict):
    """Render detailed model parameters section."""
    st.divider()
    
    with st.expander("🛠️ Model Details & Parameters"):
        available_tfs = [tf for tf in ['15m', '1h'] if models[tf] is not None]
        
        if not available_tfs:
            st.info("No models available")
            return
        
        selected_tf = st.selectbox(
            "Select Model", 
            available_tfs,
            format_func=lambda x: f"{x.upper()} Model",
            key="details_tf"
        )
        
        meta = models[selected_tf]
        if not meta:
            return
        
        # Data range
        data_range = meta.get('data_range', {})
        if data_range:
            st.markdown("**📊 Data Range:**")
            st.markdown(f"""
            - Train: `{data_range.get('train_start', 'N/A')[:10]}` → `{data_range.get('train_end', 'N/A')[:10]}`
            - Test: `{data_range.get('test_start', 'N/A')[:10]}` → `{data_range.get('test_end', 'N/A')[:10]}`
            """)
        
        # XGBoost parameters
        params_long = meta.get('best_params_long', {})
        params_short = meta.get('best_params_short', {})
        
        if params_long or params_short:
            st.markdown("**⚙️ XGBoost Parameters:**")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**LONG Model:**")
                for k in ['n_estimators', 'max_depth', 'learning_rate', 'subsample']:
                    if k in params_long:
                        st.write(f"- {k}: `{params_long[k]}`")
            
            with col2:
                st.markdown("**SHORT Model:**")
                for k in ['n_estimators', 'max_depth', 'learning_rate', 'subsample']:
                    if k in params_short:
                        st.write(f"- {k}: `{params_short[k]}`")


def _render_inference_section(models: dict):
    """Render real-time inference section."""
    st.divider()
    st.markdown("#### 🔮 Real-Time Inference")
    st.caption("Run predictions on the last 200 candles from real-time data")
    
    available_tfs = [tf for tf in ['15m', '1h'] if models[tf] is not None]
    
    if not available_tfs:
        st.error("❌ No models available for inference")
        return
    
    # Controls
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        symbols = get_realtime_symbols()
        if not symbols:
            for tf in available_tfs:
                if models[tf] and models[tf].get('symbols'):
                    symbols = models[tf]['symbols']
                    break
        
        if not symbols:
            st.error("No symbols found in database")
            return
        
        symbol_map = {s.replace('/USDT:USDT', '').replace('USDT', ''): s for s in symbols}
        symbol_names = list(symbol_map.keys())[:50]
        
        selected_name = st.selectbox("🪙 Select Coin", symbol_names, key="inf_sym")
        selected_symbol = symbol_map[selected_name]
    
    with col2:
        inference_tf = st.selectbox("⏱️ Timeframe", available_tfs, key="inf_tf")
    
    with col3:
        num_candles = st.selectbox("🕯️ Candles", [100, 150, 200, 300], index=2, key="inf_candles")
    
    model_info = models[inference_tf]
    st.info(f"📦 Model: **{model_info.get('version', 'Unknown')[:20]}...** ({model_info.get('n_features', 0)} features)")
    
    # Run inference
    if st.button("🚀 Run Inference", use_container_width=True, type="primary", key="run_inf"):
        _execute_inference(selected_symbol, selected_name, inference_tf, num_candles, model_info)


def _execute_inference(symbol: str, name: str, tf: str, candles: int, model_info: dict):
    """Execute and display inference results."""
    with st.spinner("Fetching data and running inference..."):
        model_long, model_short, scaler, metadata = load_model_for_timeframe(tf)
        
        if model_long is None:
            st.error(f"❌ Could not load model for {tf}")
            return
        
        feature_names = metadata.get('feature_names', [])
        df = fetch_realtime_data(symbol, tf, candles + 50)
        
        if df.empty:
            st.error("❌ No data available for this selection")
            return
        
        st.success(f"✅ Fetched {len(df)} candles")
        
        df = compute_missing_indicators(df)
        df_pred = run_inference(df, model_long, model_short, scaler, feature_names)
        df_pred = df_pred.tail(candles)
        
        # Latest predictions
        st.markdown("##### 🎯 Latest Predictions")
        
        latest = df_pred.iloc[-1]
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("💰 Price", f"${latest['close']:,.4f}")
        with col2:
            long_score = latest['pred_long_norm']
            color = "🟢" if long_score > 30 else "🔴" if long_score < -30 else "⚪"
            st.metric(f"{color} LONG", f"{long_score:.1f}")
        with col3:
            short_score = latest['pred_short_norm']
            color = "🔴" if short_score > 30 else "🟢" if short_score < -30 else "⚪"
            st.metric(f"{color} SHORT", f"{short_score:.1f}")
        with col4:
            if long_score > 50:
                signal = "🚀 STRONG LONG"
            elif long_score > 30:
                signal = "📈 LONG"
            elif short_score > 50:
                signal = "🔻 STRONG SHORT"
            elif short_score > 30:
                signal = "📉 SHORT"
            else:
                signal = "⏸️ NEUTRAL"
            st.metric("Signal", signal)
        
        # Chart
        st.markdown("##### 📊 Inference Chart")
        fig = create_inference_chart(df_pred, name, tf)
        if fig:
            st.plotly_chart(fig, width='stretch')
        
        # Statistics
        with st.expander("📈 Score Statistics"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**LONG Scores:**")
                st.write(f"- Mean: {df_pred['pred_long_norm'].mean():.2f}")
                st.write(f"- Max: {df_pred['pred_long_norm'].max():.2f}")
                st.write(f"- % Positive: {(df_pred['pred_long_norm'] > 0).mean()*100:.1f}%")
            with col2:
                st.markdown("**SHORT Scores:**")
                st.write(f"- Mean: {df_pred['pred_short_norm'].mean():.2f}")
                st.write(f"- Max: {df_pred['pred_short_norm'].max():.2f}")
                st.write(f"- % Positive: {(df_pred['pred_short_norm'] > 0).mean()*100:.1f}%")


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def render_models_step():
    """Render Step 4: Complete ML Models Dashboard."""
    
    st.markdown("### 📊 Step 4: ML Models")
    st.caption("View trained models, analytics, feature importance, and run real-time inference")
    
    # === DATA MODEL DISPLAY ===
    render_step_data_model('step4_models')
    
    # Use centralized model loader
    models = get_available_models()
    
    if models['15m'] is None and models['1h'] is None:
        st.warning("⚠️ **No trained models found!**")
        st.info("Complete **Step 3 (Training)** first to train a model.")
        st.caption(f"Looking in: `{get_model_dir()}`")
        return
    
    # Render all sections
    # Model summary - always show (lightweight)
    _render_model_summary(models)
    
    # Heavy sections wrapped in expanders for lazy loading
    with st.expander("📈 Training Analytics (Charts)", expanded=False):
        _render_training_analytics(models)
    
    with st.expander("🔬 Feature Importance", expanded=False):
        _render_feature_importance(models)
    
    with st.expander("🤖 AI Analysis", expanded=False):
        _render_ai_analysis(models)
    
    with st.expander("🛠️ Model Details & Parameters", expanded=False):
        _render_model_details(models)
    
    with st.expander("🔮 Real-Time Inference", expanded=False):
        _render_inference_section(models)


__all__ = ['render_models_step']
