"""
📊 Training Results Dashboard - Enhanced Version

Displays training results with:
- Detailed metrics tables (LONG & SHORT)
- Feature importance charts
- Precision@K charts with radar
- Automatic GPT-4o analysis on load
- Real-time Bitcoin inference using live OHLCV data
"""

import streamlit as st
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import os
import pandas as pd

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


# Color scheme
COLORS = {
    'primary': '#00ffff',
    'secondary': '#ff6b6b',
    'success': '#4ade80',
    'warning': '#fbbf24',
    'background': '#0a0a1a',
    'card': '#1a1a2e',
    'text': '#e0e0ff',
    'grid': '#2a2a4a'
}


def get_model_dir() -> Path:
    """Get models directory path."""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    return Path(shared_path) / "models"


def load_metadata(timeframe: str) -> Optional[Dict[str, Any]]:
    """Load metadata for a specific timeframe."""
    model_dir = get_model_dir()
    metadata_path = model_dir / f"metadata_{timeframe}_latest.json"
    
    if not metadata_path.exists():
        return None
    
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def render_training_summary(meta: Dict[str, Any]):
    """Render training summary metrics with quality badge."""
    metrics_long = meta.get('metrics_long', {})
    metrics_short = meta.get('metrics_short', {})
    
    spearman_long = metrics_long.get('ranking', {}).get('spearman_corr', 0)
    spearman_short = metrics_short.get('ranking', {}).get('spearman_corr', 0)
    
    # Quality badge
    avg_spearman = (spearman_long + spearman_short) / 2
    if avg_spearman >= 0.2:
        quality = ("🟢", "Excellent", "#4ade80")
    elif avg_spearman >= 0.15:
        quality = ("🟡", "Good", "#fbbf24")
    elif avg_spearman >= 0.1:
        quality = ("🟠", "Acceptable", "#f97316")
    else:
        quality = ("🔴", "Needs Improvement", "#ff6b6b")
    
    # Header with quality badge
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1a1a2e, #16213e); 
                border: 1px solid #2a2a4a; border-radius: 12px; padding: 16px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h3 style="color: #e0e0ff; margin: 0;">📊 {meta.get('timeframe', 'N/A').upper()} Model</h3>
            <span style="background: {quality[2]}22; color: {quality[2]}; 
                        padding: 6px 14px; border-radius: 20px; font-weight: bold;">
                {quality[0]} {quality[1]}
            </span>
        </div>
        <p style="color: #888; margin: 8px 0 0 0; font-size: 13px;">
            Version: <code style="background: #333; padding: 2px 6px; border-radius: 4px;">{meta.get('version', 'N/A')[:20]}...</code>
            | Trained: {meta.get('created_at', 'N/A')[:19].replace('T', ' ')}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Basic metrics grid
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("📊 Features", meta.get('n_features', 0))
    with col2:
        st.metric("📚 Train", f"{meta.get('n_train_samples', 0):,}")
    with col3:
        st.metric("🧪 Test", f"{meta.get('n_test_samples', 0):,}")
    with col4:
        duration_min = meta.get('training_duration_seconds', 0) / 60
        st.metric("⏱️ Time", f"{duration_min:.1f}m")
    with col5:
        st.metric("🔄 Trials", meta.get('n_trials', 0))
    with col6:
        st.metric("📈 Avg Spearman", f"{avg_spearman:.3f}")


def render_detailed_metrics_table(meta: Dict[str, Any]):
    """Render detailed metrics tables for LONG and SHORT models."""
    metrics_long = meta.get('metrics_long', {})
    metrics_short = meta.get('metrics_short', {})
    
    st.markdown("### 📋 Detailed Model Metrics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📈 LONG Model")
        long_data = {
            "Metric": [
                "Spearman Correlation",
                "R² Score",
                "RMSE",
                "MAE",
                "Top 1% Positive",
                "Top 5% Positive", 
                "Top 10% Positive",
                "Top 20% Positive"
            ],
            "Value": [
                f"{metrics_long.get('ranking', {}).get('spearman_corr', 0):.4f}",
                f"{metrics_long.get('test_r2', 0):.4f}",
                f"{metrics_long.get('test_rmse', 0):.6f}",
                f"{metrics_long.get('test_mae', 0):.6f}",
                f"{metrics_long.get('ranking', {}).get('top1pct_positive', 0):.1f}%",
                f"{metrics_long.get('ranking', {}).get('top5pct_positive', 0):.1f}%",
                f"{metrics_long.get('ranking', {}).get('top10pct_positive', 0):.1f}%",
                f"{metrics_long.get('ranking', {}).get('top20pct_positive', 0):.1f}%"
            ]
        }
        st.dataframe(
            pd.DataFrame(long_data),
            hide_index=True,
            use_container_width=True
        )
    
    with col2:
        st.markdown("#### 📉 SHORT Model")
        short_data = {
            "Metric": [
                "Spearman Correlation",
                "R² Score",
                "RMSE",
                "MAE",
                "Top 1% Positive",
                "Top 5% Positive",
                "Top 10% Positive",
                "Top 20% Positive"
            ],
            "Value": [
                f"{metrics_short.get('ranking', {}).get('spearman_corr', 0):.4f}",
                f"{metrics_short.get('test_r2', 0):.4f}",
                f"{metrics_short.get('test_rmse', 0):.6f}",
                f"{metrics_short.get('test_mae', 0):.6f}",
                f"{metrics_short.get('ranking', {}).get('top1pct_positive', 0):.1f}%",
                f"{metrics_short.get('ranking', {}).get('top5pct_positive', 0):.1f}%",
                f"{metrics_short.get('ranking', {}).get('top10pct_positive', 0):.1f}%",
                f"{metrics_short.get('ranking', {}).get('top20pct_positive', 0):.1f}%"
            ]
        }
        st.dataframe(
            pd.DataFrame(short_data),
            hide_index=True,
            use_container_width=True
        )


def render_hyperparams_section(meta: Dict[str, Any]):
    """Render hyperparameters section."""
    st.markdown("### ⚙️ Best Hyperparameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### LONG Model")
        params_long = meta.get('best_params_long', {})
        if params_long:
            params_df = pd.DataFrame([
                {"Parameter": k, "Value": str(v)} 
                for k, v in params_long.items()
            ])
            st.dataframe(params_df, hide_index=True, use_container_width=True)
        else:
            st.info("No hyperparameters available")
    
    with col2:
        st.markdown("#### SHORT Model")
        params_short = meta.get('best_params_short', {})
        if params_short:
            params_df = pd.DataFrame([
                {"Parameter": k, "Value": str(v)} 
                for k, v in params_short.items()
            ])
            st.dataframe(params_df, hide_index=True, use_container_width=True)
        else:
            st.info("No hyperparameters available")


def create_feature_importance_chart(meta: Dict[str, Any]) -> Optional[go.Figure]:
    """Create feature importance bar chart."""
    fi_long = meta.get('feature_importance_long', {})
    fi_short = meta.get('feature_importance_short', {})
    
    if not fi_long or not fi_short:
        return None
    
    top_long = list(fi_long.items())[:10]
    top_short = list(fi_short.items())[:10]
    
    fig = make_subplots(rows=1, cols=2, 
                        subplot_titles=("📈 LONG Model", "📉 SHORT Model"),
                        horizontal_spacing=0.15)
    
    fig.add_trace(go.Bar(
        y=[f[0] for f in reversed(top_long)],
        x=[f[1] for f in reversed(top_long)],
        orientation='h',
        marker_color=COLORS['primary'],
        text=[f'{f[1]:.3f}' for f in reversed(top_long)],
        textposition='outside'
    ), row=1, col=1)
    
    fig.add_trace(go.Bar(
        y=[f[0] for f in reversed(top_short)],
        x=[f[1] for f in reversed(top_short)],
        orientation='h',
        marker_color=COLORS['secondary'],
        text=[f'{f[1]:.3f}' for f in reversed(top_short)],
        textposition='outside'
    ), row=1, col=2)
    
    fig.update_layout(
        title="🔬 Feature Importance (Top 10)",
        plot_bgcolor=COLORS['card'],
        paper_bgcolor=COLORS['background'],
        font=dict(color=COLORS['text']),
        showlegend=False,
        height=400,
        margin=dict(l=120, r=80)
    )
    
    fig.update_xaxes(gridcolor=COLORS['grid'])
    fig.update_yaxes(gridcolor=COLORS['grid'])
    
    return fig


def create_metrics_comparison_chart(meta: Dict[str, Any]) -> go.Figure:
    """Create metrics comparison radar chart."""
    metrics_long = meta.get('metrics_long', {})
    metrics_short = meta.get('metrics_short', {})
    
    categories = ['Spearman', 'R²', 'Top1% +', 'Top5% +', 'Top10% +']
    
    long_values = [
        metrics_long.get('ranking', {}).get('spearman_corr', 0) * 100,
        metrics_long.get('test_r2', 0) * 100,
        metrics_long.get('ranking', {}).get('top1pct_positive', 0),
        metrics_long.get('ranking', {}).get('top5pct_positive', 0),
        metrics_long.get('ranking', {}).get('top10pct_positive', 0),
    ]
    
    short_values = [
        metrics_short.get('ranking', {}).get('spearman_corr', 0) * 100,
        metrics_short.get('test_r2', 0) * 100,
        metrics_short.get('ranking', {}).get('top1pct_positive', 0),
        metrics_short.get('ranking', {}).get('top5pct_positive', 0),
        metrics_short.get('ranking', {}).get('top10pct_positive', 0),
    ]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=long_values + [long_values[0]],
        theta=categories + [categories[0]],
        fill='toself',
        name='LONG',
        line_color=COLORS['primary'],
        fillcolor='rgba(0, 255, 255, 0.2)'
    ))
    
    fig.add_trace(go.Scatterpolar(
        r=short_values + [short_values[0]],
        theta=categories + [categories[0]],
        fill='toself',
        name='SHORT',
        line_color=COLORS['secondary'],
        fillcolor='rgba(255, 107, 107, 0.2)'
    ))
    
    max_val = max(max(long_values), max(short_values)) if long_values and short_values else 100
    
    fig.update_layout(
        title="📊 Model Comparison (Radar)",
        polar=dict(
            bgcolor=COLORS['card'],
            radialaxis=dict(
                visible=True,
                range=[0, max_val * 1.2],
                gridcolor=COLORS['grid']
            ),
            angularaxis=dict(gridcolor=COLORS['grid'])
        ),
        paper_bgcolor=COLORS['background'],
        font=dict(color=COLORS['text']),
        showlegend=True,
        height=400
    )
    
    return fig


def create_precision_chart(meta: Dict[str, Any]) -> go.Figure:
    """Create Precision@K bar chart."""
    metrics_long = meta.get('metrics_long', {})
    metrics_short = meta.get('metrics_short', {})
    
    k_values = ['Top 1%', 'Top 5%', 'Top 10%', 'Top 20%']
    
    long_precision = [
        metrics_long.get('ranking', {}).get('top1pct_positive', 0),
        metrics_long.get('ranking', {}).get('top5pct_positive', 0),
        metrics_long.get('ranking', {}).get('top10pct_positive', 0),
        metrics_long.get('ranking', {}).get('top20pct_positive', 0),
    ]
    
    short_precision = [
        metrics_short.get('ranking', {}).get('top1pct_positive', 0),
        metrics_short.get('ranking', {}).get('top5pct_positive', 0),
        metrics_short.get('ranking', {}).get('top10pct_positive', 0),
        metrics_short.get('ranking', {}).get('top20pct_positive', 0),
    ]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='LONG',
        x=k_values,
        y=long_precision,
        marker_color=COLORS['primary'],
        text=[f'{v:.1f}%' for v in long_precision],
        textposition='outside'
    ))
    
    fig.add_trace(go.Bar(
        name='SHORT',
        x=k_values,
        y=short_precision,
        marker_color=COLORS['secondary'],
        text=[f'{v:.1f}%' for v in short_precision],
        textposition='outside'
    ))
    
    fig.add_hline(y=50, line_dash="dash", line_color=COLORS['warning'],
                  annotation_text="Random (50%)")
    
    fig.update_layout(
        title="🎯 Precision@K (% Profitable Predictions)",
        barmode='group',
        plot_bgcolor=COLORS['card'],
        paper_bgcolor=COLORS['background'],
        font=dict(color=COLORS['text']),
        xaxis=dict(gridcolor=COLORS['grid']),
        yaxis=dict(gridcolor=COLORS['grid'], title="% Positive", range=[0, 100]),
        legend=dict(bgcolor='rgba(0,0,0,0.5)'),
        height=350
    )
    
    return fig


def _build_model_analysis_prompt(meta: Dict[str, Any]) -> str:
    """Build prompt for GPT model analysis."""
    metrics_long = meta.get('metrics_long', {})
    metrics_short = meta.get('metrics_short', {})
    
    return f"""ANALYZE THIS ML TRADING MODEL (respond in English):

**Training Configuration:**
- Timeframe: {meta.get('timeframe', 'N/A')}
- Features: {meta.get('n_features', 0)}
- Training samples: {meta.get('n_train_samples', 0):,}
- Test samples: {meta.get('n_test_samples', 0):,}
- Optuna trials: {meta.get('n_trials', 0)}

**LONG Model Metrics:**
- Spearman Correlation: {metrics_long.get('ranking', {}).get('spearman_corr', 0):.4f}
- R²: {metrics_long.get('test_r2', 0):.4f}
- RMSE: {metrics_long.get('test_rmse', 0):.6f}
- Top 1% Positive: {metrics_long.get('ranking', {}).get('top1pct_positive', 0):.1f}%
- Top 5% Positive: {metrics_long.get('ranking', {}).get('top5pct_positive', 0):.1f}%
- Top 10% Positive: {metrics_long.get('ranking', {}).get('top10pct_positive', 0):.1f}%

**SHORT Model Metrics:**
- Spearman Correlation: {metrics_short.get('ranking', {}).get('spearman_corr', 0):.4f}
- R²: {metrics_short.get('test_r2', 0):.4f}
- Top 1% Positive: {metrics_short.get('ranking', {}).get('top1pct_positive', 0):.1f}%
- Top 5% Positive: {metrics_short.get('ranking', {}).get('top5pct_positive', 0):.1f}%

**Top 5 Features (LONG):**
{', '.join(list(meta.get('feature_importance_long', {}).keys())[:5])}

**Top 5 Features (SHORT):**
{', '.join(list(meta.get('feature_importance_short', {}).keys())[:5])}

**Best Hyperparameters (LONG):**
{json.dumps(meta.get('best_params_long', {}), indent=2)}

Analyze the model quality, provide actionable insights for trading."""


def _get_or_generate_analysis(meta: Dict[str, Any], timeframe: str) -> Optional[Dict]:
    """Get cached analysis or generate new one automatically."""
    cache_key = f"gpt_analysis_{timeframe}"
    
    # Check session state cache
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    # Try to generate analysis
    try:
        from services.openai_service import get_openai_service
        service = get_openai_service()
        
        if not service.is_available:
            return None
        
        prompt = _build_model_analysis_prompt(meta)
        
        client = service._get_client()
        if not client:
            return None
        
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert ML/trading model analyst.
Analyze XGBoost model training results and provide actionable insights.
All responses must be in English.
Focus on: model quality, trading viability, feature insights, improvements."""
                },
                {"role": "user", "content": prompt}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "model_analysis",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "quality_rating": {
                                "type": "string",
                                "enum": ["excellent", "good", "acceptable", "poor"]
                            },
                            "quality_emoji": {"type": "string"},
                            "summary": {"type": "string"},
                            "strengths": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "weaknesses": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "recommendations": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "trading_viability": {"type": "string"},
                            "comparison_note": {"type": "string"}
                        },
                        "required": ["quality_rating", "quality_emoji", "summary",
                                    "strengths", "weaknesses", "recommendations",
                                    "trading_viability", "comparison_note"],
                        "additionalProperties": False
                    }
                }
            },
            temperature=0.3
        )
        
        analysis = json.loads(completion.choices[0].message.content)
        
        # Cache it
        st.session_state[cache_key] = analysis
        return analysis
        
    except Exception:
        return None


def render_gpt_analysis(meta: Dict[str, Any], timeframe: str):
    """Render GPT analysis section with auto-load."""
    st.markdown("### 🤖 AI Analysis (GPT-4o)")
    
    # Auto-generate on first load
    with st.spinner("🤖 Generating AI analysis..."):
        analysis = _get_or_generate_analysis(meta, timeframe)
    
    if analysis:
        _display_analysis_card(analysis)
        
        # Regenerate button
        if st.button("🔄 Regenerate Analysis", key="regen_analysis"):
            cache_key = f"gpt_analysis_{timeframe}"
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            st.rerun()
    else:
        st.warning("⚠️ OpenAI API not configured. Set OPENAI_API_KEY in .env")


def _display_analysis_card(analysis: Dict[str, Any]):
    """Display AI analysis as styled card."""
    rating_colors = {
        'excellent': '#4ade80',
        'good': '#fbbf24',
        'acceptable': '#f97316',
        'poor': '#ff6b6b'
    }
    
    rating = analysis.get('quality_rating', 'unknown')
    color = rating_colors.get(rating, '#888')
    emoji = analysis.get('quality_emoji', '⚪')
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1a1a2e, #2a2a4a); 
                padding: 20px; border-radius: 12px; border: 1px solid {color}; margin: 10px 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <span style="font-size: 15px; color: #e0e0ff;">{analysis.get('summary', '')}</span>
            <span style="background: {color}; color: black; padding: 4px 12px; 
                        border-radius: 20px; font-weight: bold;">
                {emoji} {rating.title()}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**✅ Strengths:**")
        for s in analysis.get('strengths', []):
            st.markdown(f"- {s}")
    
    with col2:
        st.markdown("**⚠️ Weaknesses:**")
        for w in analysis.get('weaknesses', []):
            st.markdown(f"- {w}")
    
    st.markdown("**💡 Recommendations:**")
    for r in analysis.get('recommendations', []):
        st.markdown(f"- {r}")
    
    if analysis.get('trading_viability'):
        st.info(f"📈 **Trading Viability:** {analysis['trading_viability']}")


def render_realtime_btc_inference(meta: Dict[str, Any], timeframe: str):
    """Render real-time Bitcoin inference using live OHLCV data."""
    st.markdown("### 📈 Real-Time Bitcoin Inference")
    st.caption("Using live OHLCV data from realtime_ohlcv table (same as Top Coins tab)")
    
    try:
        from database.ohlcv import get_ohlcv_with_indicators
        from services.local_models import load_models, load_model_metadata
        
        # Get real-time BTC data
        symbol = "BTC/USDT:USDT"
        df = get_ohlcv_with_indicators(symbol, timeframe, limit=200)
        
        if df.empty:
            st.warning(f"⚠️ No real-time data for {symbol} ({timeframe})")
            st.info("Make sure the data-fetcher container is running and has BTC data.")
            return
        
        # Load models directly
        model_long, model_short, scaler = load_models(timeframe)
        
        if model_long is None:
            st.warning("⚠️ Models not loaded. Train models first.")
            st.code(f"python train_local.py --timeframe {timeframe} --trials 20", language="bash")
            return
        
        # Load metadata to get expected feature names
        model_meta = load_model_metadata(timeframe)
        if model_meta is None:
            st.error("Failed to load model metadata")
            return
        
        # Run inference on last 200 candles
        with st.spinner("Running inference on 200 candles..."):
            scores_long, scores_short = _run_inference_realtime(
                df, model_long, model_short, scaler, model_meta.feature_names
            )
        
        if scores_long is None:
            st.error("Failed to run inference - check feature compatibility")
            return
        
        # Current signal
        current_long = scores_long[-1] if len(scores_long) > 0 else 0
        current_short = scores_short[-1] if len(scores_short) > 0 else 0
        net_score = (current_long - current_short) / 2
        
        # Signal card
        if net_score > 30:
            signal, signal_color = "🟢 STRONG BUY", "#4ade80"
        elif net_score > 10:
            signal, signal_color = "🟡 BUY", "#fbbf24"
        elif net_score < -30:
            signal, signal_color = "🔴 STRONG SELL", "#ff6b6b"
        elif net_score < -10:
            signal, signal_color = "🟠 SELL", "#f97316"
        else:
            signal, signal_color = "⚪ NEUTRAL", "#888"
        
        # Display signal
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div style="background: {signal_color}22; border: 1px solid {signal_color};
                        border-radius: 10px; padding: 15px; text-align: center;">
                <h2 style="color: {signal_color}; margin: 0;">{signal}</h2>
                <p style="color: #888; margin: 5px 0 0 0;">Current Signal</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.metric("📈 LONG Score", f"{current_long:.1f}")
        
        with col3:
            st.metric("📉 SHORT Score", f"{current_short:.1f}")
        
        with col4:
            st.metric("📊 Net Score", f"{net_score:.1f}")
        
        # Chart with candlesticks and ML scores
        if PLOTLY_AVAILABLE:
            fig = _create_btc_inference_chart(df, scores_long, scores_short)
            st.plotly_chart(fig, use_container_width=True)
        
        # Data info
        st.caption(f"📊 Data: {len(df)} candles | Last: {df.index[-1]} | Timeframe: {timeframe}")
        
    except ImportError as e:
        st.error(f"Import error: {e}")
    except Exception as e:
        st.error(f"Error: {e}")
        import traceback
        with st.expander("Debug Info"):
            st.code(traceback.format_exc())


def _run_inference_realtime(
    df: pd.DataFrame, 
    model_long, 
    model_short, 
    scaler,
    expected_features: list
) -> Tuple:
    """Run inference on realtime dataframe with proper feature mapping."""
    try:
        # Map realtime_ohlcv columns to model expected features
        # realtime_ohlcv has: bb_mid, bb_upper, bb_lower
        # model might expect: bb_middle (if trained on historical)
        column_mapping = {
            'bb_mid': 'bb_middle',  # realtime uses bb_mid
        }
        
        # Create a copy and rename columns if needed
        df_features = df.copy()
        for old_name, new_name in column_mapping.items():
            if old_name in df_features.columns and new_name not in df_features.columns:
                df_features[new_name] = df_features[old_name]
        
        # Get available features from the dataframe
        available_features = []
        for f in expected_features:
            if f in df_features.columns:
                available_features.append(f)
        
        if len(available_features) < 3:
            return None, None
        
        # Prepare features matrix
        X = df_features[available_features].copy()
        X = X.fillna(method='ffill').fillna(0)
        
        # Scale features
        try:
            X_scaled = scaler.transform(X)
        except Exception:
            # If scaler fails, use raw values
            X_scaled = X.values
        
        # Run inference
        scores_long = model_long.predict(X_scaled) * 100  # Scale to -100 to 100
        scores_short = model_short.predict(X_scaled) * 100
        
        return list(scores_long), list(scores_short)
        
    except Exception as e:
        print(f"Inference error: {e}")
        return None, None


def _create_btc_inference_chart(df: pd.DataFrame, 
                                scores_long: list, 
                                scores_short: list) -> go.Figure:
    """Create candlestick chart with ML scores overlay."""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=("BTC/USDT - Price", "ML Scores")
    )
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='BTC',
        increasing_line_color=COLORS['success'],
        decreasing_line_color=COLORS['secondary']
    ), row=1, col=1)
    
    # ML Scores
    fig.add_trace(go.Scatter(
        x=df.index,
        y=scores_long,
        name='LONG Score',
        line=dict(color=COLORS['primary'], width=2)
    ), row=2, col=1)
    
    fig.add_trace(go.Scatter(
        x=df.index,
        y=scores_short,
        name='SHORT Score',
        line=dict(color=COLORS['secondary'], width=2)
    ), row=2, col=1)
    
    # Zero line
    fig.add_hline(y=0, line_dash="dash", line_color="#555", row=2, col=1)
    
    fig.update_layout(
        title="📈 BTC Real-Time Inference (200 Candles)",
        plot_bgcolor=COLORS['card'],
        paper_bgcolor=COLORS['background'],
        font=dict(color=COLORS['text']),
        xaxis_rangeslider_visible=False,
        height=600,
        showlegend=True,
        legend=dict(bgcolor='rgba(0,0,0,0.5)')
    )
    
    fig.update_xaxes(gridcolor=COLORS['grid'])
    fig.update_yaxes(gridcolor=COLORS['grid'])
    
    return fig


def render_training_results_dashboard():
    """Main entry point - render full training results dashboard."""
    st.markdown("## 📊 Training Results Dashboard")
    st.caption("Detailed metrics, AI analysis, and real-time inference")
    
    # Timeframe selector
    available_tfs = []
    model_dir = get_model_dir()
    
    for tf in ['15m', '1h']:
        if (model_dir / f"metadata_{tf}_latest.json").exists():
            available_tfs.append(tf)
    
    if not available_tfs:
        st.warning("⚠️ No trained models found. Run training first!")
        st.code("python train_local.py --timeframe 15m --trials 10", language="bash")
        return
    
    selected_tf = st.selectbox(
        "Select Timeframe",
        available_tfs,
        format_func=lambda x: f"{'🔵' if x == '15m' else '🟢'} {x.upper()} Model"
    )
    
    meta = load_metadata(selected_tf)
    
    if not meta:
        st.error(f"Failed to load metadata for {selected_tf}")
        return
    
    # 1. Summary
    render_training_summary(meta)
    
    st.divider()
    
    # 2. Detailed Metrics Tables
    render_detailed_metrics_table(meta)
    
    st.divider()
    
    # 3. Hyperparameters
    with st.expander("⚙️ Best Hyperparameters", expanded=False):
        render_hyperparams_section(meta)
    
    st.divider()
    
    # 4. Charts
    if PLOTLY_AVAILABLE:
        st.markdown("### 🔬 Feature Importance")
        fig_fi = create_feature_importance_chart(meta)
        if fig_fi:
            st.plotly_chart(fig_fi, use_container_width=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🎯 Precision@K")
            fig_prec = create_precision_chart(meta)
            if fig_prec:
                st.plotly_chart(fig_prec, use_container_width=True)
        
        with col2:
            st.markdown("### 📊 Model Comparison")
            fig_radar = create_metrics_comparison_chart(meta)
            if fig_radar:
                st.plotly_chart(fig_radar, use_container_width=True)
    
    st.divider()
    
    # 5. GPT Analysis (auto-generated)
    render_gpt_analysis(meta, selected_tf)
    
    st.divider()
    
    # 6. Real-time BTC Inference
    render_realtime_btc_inference(meta, selected_tf)
    
    st.divider()
    
    # 7. Raw JSON
    with st.expander("📋 Raw Metadata (JSON)"):
        st.json(meta)


__all__ = ['render_training_results_dashboard']
