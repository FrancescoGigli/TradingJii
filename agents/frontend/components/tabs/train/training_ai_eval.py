"""
🤖 Training AI Evaluation Section

Uses OpenAI GPT-4o to analyze training results and provide:
- Quality assessment (Excellent/Good/Acceptable/Poor)
- Strengths and weaknesses analysis
- Recommendations for improvement
- Trading viability assessment
"""

import streamlit as st
import json
from pathlib import Path
from typing import Dict, Any, Optional
import os


# Color scheme (dark theme)
COLORS = {
    'primary': '#00ffff',
    'secondary': '#ff6b6b',
    'success': '#4ade80',
    'warning': '#fbbf24',
    'info': '#60a5fa',
    'background': '#0d1117',
    'card': '#1e2130',
    'text': '#e0e0ff',
    'muted': '#9ca3af',
    'border': '#2d3748'
}


def _get_models_dir() -> Path:
    """Get the models directory path."""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    return Path(shared_path) / "models"


def _load_metadata(timeframe: str) -> Optional[Dict[str, Any]]:
    """Load metadata for a specific timeframe."""
    models_dir = _get_models_dir()
    metadata_path = models_dir / f"metadata_{timeframe}_latest.json"
    
    if not metadata_path.exists():
        return None
    
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def render_ai_evaluation_section():
    """Render the AI evaluation section."""
    st.markdown("### 🤖 AI Training Evaluation (GPT-4o)")
    st.caption("Get AI-powered analysis of your model's training quality")
    
    # Check if any model exists
    meta_15m = _load_metadata('15m')
    meta_1h = _load_metadata('1h')
    
    if not meta_15m and not meta_1h:
        st.info("⚠️ No trained models found. Train a model first to get AI evaluation.")
        return
    
    # Timeframe selector
    available = []
    if meta_15m:
        available.append('15m')
    if meta_1h:
        available.append('1h')
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_tf = st.selectbox(
            "Select Model for AI Analysis",
            available,
            format_func=lambda x: f"{'🔵' if x == '15m' else '🟢'} {x.upper()} Model",
            key="ai_eval_tf_selector"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        generate_clicked = st.button(
            "🚀 Generate AI Evaluation",
            use_container_width=True,
            type="primary"
        )
    
    meta = meta_15m if selected_tf == '15m' else meta_1h
    
    if not meta:
        st.error("Failed to load model metadata")
        return
    
    # Check for existing analysis in session state
    analysis_key = f"ai_analysis_{selected_tf}"
    
    if generate_clicked:
        _generate_ai_analysis(meta, selected_tf)
    elif analysis_key in st.session_state:
        _display_analysis_card(st.session_state[analysis_key])
    else:
        _show_analysis_preview(meta)


def _show_analysis_preview(meta: Dict[str, Any]):
    """Show a preview of what AI analysis will evaluate."""
    metrics_long = meta.get('metrics_long', {})
    metrics_short = meta.get('metrics_short', {})
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {COLORS['card']}, {COLORS['background']});
        border: 1px dashed {COLORS['border']};
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
    ">
        <div style="color: {COLORS['muted']}; margin-bottom: 15px;">
            🔍 The AI will analyze these metrics:
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
            <div>
                <div style="color: {COLORS['primary']}; font-weight: bold; margin-bottom: 8px;">📊 Model Metrics</div>
                <ul style="color: {COLORS['text']}; margin: 0; padding-left: 20px;">
                    <li>Spearman Correlation (LONG/SHORT)</li>
                    <li>R² Score</li>
                    <li>Precision@K (Top 1%, 5%, 10%)</li>
                </ul>
            </div>
            <div>
                <div style="color: {COLORS['primary']}; font-weight: bold; margin-bottom: 8px;">📈 Training Data</div>
                <ul style="color: {COLORS['text']}; margin: 0; padding-left: 20px;">
                    <li>Features: {meta.get('n_features', 0)}</li>
                    <li>Train samples: {meta.get('n_train_samples', 0):,}</li>
                    <li>Test samples: {meta.get('n_test_samples', 0):,}</li>
                </ul>
            </div>
        </div>
        <div style="
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid {COLORS['border']};
            color: {COLORS['muted']};
            font-size: 0.9em;
        ">
            💡 Click "Generate AI Evaluation" to get a detailed analysis in English
        </div>
    </div>
    """, unsafe_allow_html=True)


def _generate_ai_analysis(meta: Dict[str, Any], timeframe: str):
    """Generate AI analysis using OpenAI GPT-4o."""
    try:
        from services.openai_service import get_openai_service
        service = get_openai_service()
        
        if not service.is_available:
            st.error("❌ OpenAI API key not configured. Set OPENAI_API_KEY in .env file.")
            return
        
        with st.spinner("🤖 Analyzing model with GPT-4o..."):
            # Build prompt with model metadata
            prompt = _build_analysis_prompt(meta)
            
            client = service._get_client()
            if not client:
                st.error("Failed to initialize OpenAI client")
                return
            
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert ML/trading model analyst.
Analyze the XGBoost model training results and provide actionable insights.
Focus on: model quality, trading viability, feature insights, and improvement suggestions.
All responses must be in English."""
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
                            "required": [
                                "quality_rating", "quality_emoji", "summary",
                                "strengths", "weaknesses", "recommendations",
                                "trading_viability", "comparison_note"
                            ],
                            "additionalProperties": False
                        }
                    }
                },
                temperature=0.3
            )
            
            analysis = json.loads(completion.choices[0].message.content)
            
            # Store in session state
            st.session_state[f"ai_analysis_{timeframe}"] = analysis
            
            # Display the analysis
            _display_analysis_card(analysis)
            
            # Show cost
            usage = completion.usage
            cost = (usage.prompt_tokens / 1_000_000) * 2.50 + \
                   (usage.completion_tokens / 1_000_000) * 10.00
            st.caption(f"💰 API Cost: ${cost:.4f}")
            
    except ImportError:
        st.error("❌ OpenAI service not available. Check installation.")
    except Exception as e:
        st.error(f"❌ Error generating analysis: {e}")


def _build_analysis_prompt(meta: Dict[str, Any]) -> str:
    """Build the prompt for model analysis."""
    metrics_long = meta.get('metrics_long', {})
    metrics_short = meta.get('metrics_short', {})
    ranking_long = metrics_long.get('ranking', {})
    ranking_short = metrics_short.get('ranking', {})
    
    prompt = f"""ANALYZE THIS ML TRADING MODEL:

**Training Configuration:**
- Timeframe: {meta.get('timeframe', 'N/A')}
- Features: {meta.get('n_features', 0)}
- Training samples: {meta.get('n_train_samples', 0):,}
- Test samples: {meta.get('n_test_samples', 0):,}
- Optuna trials: {meta.get('n_trials', 0)}

**LONG Model Metrics:**
- Spearman Correlation: {ranking_long.get('spearman_corr', 0):.4f}
- R²: {metrics_long.get('test_r2', 0):.4f}
- RMSE: {metrics_long.get('test_rmse', 0):.6f}
- Top 1% Positive: {ranking_long.get('top1pct_positive', 0):.1f}%
- Top 5% Positive: {ranking_long.get('top5pct_positive', 0):.1f}%
- Top 10% Positive: {ranking_long.get('top10pct_positive', 0):.1f}%

**SHORT Model Metrics:**
- Spearman Correlation: {ranking_short.get('spearman_corr', 0):.4f}
- R²: {metrics_short.get('test_r2', 0):.4f}
- RMSE: {metrics_short.get('test_rmse', 0):.6f}
- Top 1% Positive: {ranking_short.get('top1pct_positive', 0):.1f}%
- Top 5% Positive: {ranking_short.get('top5pct_positive', 0):.1f}%
- Top 10% Positive: {ranking_short.get('top10pct_positive', 0):.1f}%

**Top Features (LONG):**
{', '.join(list(meta.get('feature_importance_long', {}).keys())[:5])}

**Top Features (SHORT):**
{', '.join(list(meta.get('feature_importance_short', {}).keys())[:5])}

**Best Hyperparameters (LONG):**
{json.dumps(meta.get('best_params_long', {}), indent=2)}

Provide analysis in the requested JSON format.
Focus on whether this model is ready for live trading or needs improvement."""
    
    return prompt


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
    
    # Main card with rating
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {COLORS['card']}, #2a2a4a);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid {color};
        margin: 10px 0;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <span style="font-size: 15px; color: {COLORS['text']};">
                {analysis.get('summary', '')}
            </span>
            <span style="
                background: {color};
                color: black;
                padding: 6px 14px;
                border-radius: 20px;
                font-weight: bold;
            ">
                {emoji} {rating.title()}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Strengths & Weaknesses in columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        <div style="
            background: {COLORS['background']};
            border-left: 4px solid {COLORS['success']};
            padding: 15px;
            border-radius: 4px;
        ">
            <div style="color: {COLORS['success']}; font-weight: bold; margin-bottom: 10px;">
                ✅ Strengths
            </div>
        </div>
        """, unsafe_allow_html=True)
        for s in analysis.get('strengths', []):
            st.markdown(f"- {s}")
    
    with col2:
        st.markdown(f"""
        <div style="
            background: {COLORS['background']};
            border-left: 4px solid {COLORS['warning']};
            padding: 15px;
            border-radius: 4px;
        ">
            <div style="color: {COLORS['warning']}; font-weight: bold; margin-bottom: 10px;">
                ⚠️ Weaknesses
            </div>
        </div>
        """, unsafe_allow_html=True)
        for w in analysis.get('weaknesses', []):
            st.markdown(f"- {w}")
    
    # Recommendations
    st.markdown(f"""
    <div style="
        background: {COLORS['background']};
        border-left: 4px solid {COLORS['info']};
        padding: 15px;
        margin-top: 15px;
        border-radius: 4px;
    ">
        <div style="color: {COLORS['info']}; font-weight: bold; margin-bottom: 10px;">
            💡 Recommendations
        </div>
    </div>
    """, unsafe_allow_html=True)
    for r in analysis.get('recommendations', []):
        st.markdown(f"- {r}")
    
    # Trading viability
    if analysis.get('trading_viability'):
        st.info(f"📈 **Trading Viability:** {analysis['trading_viability']}")
    
    # Comparison note
    if analysis.get('comparison_note'):
        st.caption(f"📊 {analysis['comparison_note']}")


__all__ = ['render_ai_evaluation_section']
