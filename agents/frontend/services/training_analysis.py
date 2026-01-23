"""
🤖 Training Analysis Service - LLM-Powered Model Evaluation

Uses OpenAI GPT-4o to analyze training results and provide:
- Quality assessment
- Actionable recommendations
- Comparison between timeframes
"""

import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from services.openai_service import get_openai_service


@dataclass
class TrainingAnalysis:
    """Container for LLM training analysis"""
    quality_rating: str  # 'excellent', 'good', 'acceptable', 'poor'
    quality_emoji: str   # 🟢, 🟡, 🟠, 🔴
    summary: str
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    comparison_note: str  # If comparing timeframes
    cost_usd: float
    timestamp: datetime


def analyze_training_results(
    result: Dict[str, Any],
    timeframe: str,
    comparison_result: Optional[Dict[str, Any]] = None,
    comparison_timeframe: Optional[str] = None
) -> Optional[TrainingAnalysis]:
    """
    Analyze training results using GPT-4o.
    
    Args:
        result: Training result dictionary
        timeframe: Timeframe trained (e.g., '15m')
        comparison_result: Optional second timeframe result for comparison
        comparison_timeframe: Optional second timeframe (e.g., '1h')
    
    Returns:
        TrainingAnalysis with LLM insights, or None if API unavailable
    """
    service = get_openai_service()
    
    if not service.is_available:
        return None
    
    try:
        client = service._get_client()
        if client is None:
            return None
        
        # Build prompt
        prompt = _build_analysis_prompt(
            result, timeframe, 
            comparison_result, comparison_timeframe
        )
        
        # Call GPT-4o with structured output
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert machine learning engineer specialized in financial 
market prediction models. Analyze XGBoost training results and provide actionable insights.

Key metrics to consider:
- Spearman Correlation: Measures ranking ability. >0.2 is excellent, >0.15 is good, >0.1 is acceptable
- Precision@Top1%: % of top-predicted samples that are actually profitable. >60% is excellent
- R²: Explained variance. Low R² is normal for noisy financial data
- RMSE/MAE: Lower is better, but context matters

Be specific and actionable in your recommendations."""
                },
                {"role": "user", "content": prompt}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "training_analysis",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "quality_rating": {
                                "type": "string",
                                "enum": ["excellent", "good", "acceptable", "poor"],
                                "description": "Overall model quality"
                            },
                            "summary": {
                                "type": "string",
                                "description": "2-3 sentence summary of results"
                            },
                            "strengths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "3-4 key strengths"
                            },
                            "weaknesses": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "2-3 weaknesses or risks"
                            },
                            "recommendations": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "3-5 actionable recommendations"
                            },
                            "comparison_note": {
                                "type": "string",
                                "description": "Note comparing timeframes (if applicable)"
                            }
                        },
                        "required": ["quality_rating", "summary", "strengths", 
                                    "weaknesses", "recommendations", "comparison_note"],
                        "additionalProperties": False
                    }
                }
            },
            temperature=0.3
        )
        
        content = json.loads(completion.choices[0].message.content)
        
        # Calculate cost
        usage = completion.usage
        cost = service._calculate_cost(usage.prompt_tokens, usage.completion_tokens)
        
        # Map quality to emoji
        emoji_map = {
            'excellent': '🟢',
            'good': '🟡',
            'acceptable': '🟠',
            'poor': '🔴'
        }
        
        return TrainingAnalysis(
            quality_rating=content['quality_rating'],
            quality_emoji=emoji_map.get(content['quality_rating'], '⚪'),
            summary=content['summary'],
            strengths=content['strengths'],
            weaknesses=content['weaknesses'],
            recommendations=content['recommendations'],
            comparison_note=content['comparison_note'],
            cost_usd=cost,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        print(f"LLM Analysis error: {e}")
        return None


def _build_analysis_prompt(
    result: Dict[str, Any],
    timeframe: str,
    comparison_result: Optional[Dict[str, Any]] = None,
    comparison_timeframe: Optional[str] = None
) -> str:
    """Build the analysis prompt."""
    
    metrics_long = result.get('metrics_long', {})
    metrics_short = result.get('metrics_short', {})
    
    prompt = f"""ANALYZE THESE XGBOOST TRAINING RESULTS:

TIMEFRAME: {timeframe}

📈 LONG MODEL:
- Spearman Correlation: {metrics_long.get('ranking', {}).get('spearman_corr', 0):.4f}
- R²: {metrics_long.get('test_r2', 0):.4f}
- RMSE: {metrics_long.get('test_rmse', 0):.6f}
- Top 1% Positive: {metrics_long.get('ranking', {}).get('top1pct_positive', 0):.1f}%
- Top 5% Positive: {metrics_long.get('ranking', {}).get('top5pct_positive', 0):.1f}%
- Top 10% Positive: {metrics_long.get('ranking', {}).get('top10pct_positive', 0):.1f}%

📉 SHORT MODEL:
- Spearman Correlation: {metrics_short.get('ranking', {}).get('spearman_corr', 0):.4f}
- R²: {metrics_short.get('test_r2', 0):.4f}
- RMSE: {metrics_short.get('test_rmse', 0):.6f}
- Top 1% Positive: {metrics_short.get('ranking', {}).get('top1pct_positive', 0):.1f}%
- Top 5% Positive: {metrics_short.get('ranking', {}).get('top5pct_positive', 0):.1f}%
- Top 10% Positive: {metrics_short.get('ranking', {}).get('top10pct_positive', 0):.1f}%

TRAINING DETAILS:
- Features: {result.get('n_features', 0)}
- Training samples: {result.get('n_train', 0):,}
- Test samples: {result.get('n_test', 0):,}
- Optuna trials: {result.get('n_trials', 30)}
"""
    
    if comparison_result and comparison_timeframe:
        comp_long = comparison_result.get('metrics_long', {})
        comp_short = comparison_result.get('metrics_short', {})
        
        prompt += f"""

COMPARISON - {comparison_timeframe}:
📈 LONG: Spearman {comp_long.get('ranking', {}).get('spearman_corr', 0):.4f}, Top1% {comp_long.get('ranking', {}).get('top1pct_positive', 0):.1f}%
📉 SHORT: Spearman {comp_short.get('ranking', {}).get('spearman_corr', 0):.4f}, Top1% {comp_short.get('ranking', {}).get('top1pct_positive', 0):.1f}%

Compare the two timeframes and note which performs better for trading.
"""
    else:
        prompt += "\n(No comparison timeframe provided)"
    
    prompt += """

Provide your analysis in JSON format. Be specific and actionable."""
    
    return prompt


def format_analysis_html(analysis: TrainingAnalysis) -> str:
    """Format TrainingAnalysis as HTML for Streamlit display."""
    
    if not analysis:
        return """
        <div style="background: #1a1a2e; padding: 20px; border-radius: 12px; border: 1px solid #2a2a4a;">
            <p style="color: #888;">⚠️ LLM analysis unavailable. Check OpenAI API key.</p>
        </div>
        """
    
    rating_colors = {
        'excellent': ('#4ade80', 'Excellent'),
        'good': ('#fbbf24', 'Good'),
        'acceptable': ('#f97316', 'Acceptable'),
        'poor': ('#ff6b6b', 'Poor')
    }
    
    color, label = rating_colors.get(analysis.quality_rating, ('#888', 'Unknown'))
    
    strengths_html = ''.join([f"<li style='color: #4ade80;'>✅ {s}</li>" for s in analysis.strengths])
    weaknesses_html = ''.join([f"<li style='color: #ff6b6b;'>⚠️ {w}</li>" for w in analysis.weaknesses])
    recommendations_html = ''.join([f"<li style='color: #00ffff;'>💡 {r}</li>" for r in analysis.recommendations])
    
    return f"""
    <div style="
        background: linear-gradient(135deg, #1a1a2e, #2a2a4a);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid {color};
        color: white;
        margin-top: 20px;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <h3 style="color: #00ffff; margin: 0;">🤖 AI Analysis</h3>
            <span style="
                background: {color};
                color: black;
                padding: 4px 12px;
                border-radius: 20px;
                font-weight: bold;
            ">{analysis.quality_emoji} {label}</span>
        </div>
        
        <p style="color: #e0e0ff; font-size: 14px; line-height: 1.6;">
            {analysis.summary}
        </p>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;">
            <div>
                <h4 style="color: #4ade80; margin: 0 0 10px 0;">Strengths</h4>
                <ul style="margin: 0; padding-left: 20px; font-size: 13px;">
                    {strengths_html}
                </ul>
            </div>
            <div>
                <h4 style="color: #ff6b6b; margin: 0 0 10px 0;">Weaknesses</h4>
                <ul style="margin: 0; padding-left: 20px; font-size: 13px;">
                    {weaknesses_html}
                </ul>
            </div>
        </div>
        
        <div style="margin-top: 15px;">
            <h4 style="color: #00ffff; margin: 0 0 10px 0;">Recommendations</h4>
            <ul style="margin: 0; padding-left: 20px; font-size: 13px;">
                {recommendations_html}
            </ul>
        </div>
        
        {f'<div style="margin-top: 15px; padding: 10px; background: rgba(0,255,255,0.1); border-radius: 8px;"><strong>📊 Timeframe Comparison:</strong> {analysis.comparison_note}</div>' if analysis.comparison_note else ''}
        
        <div style="margin-top: 15px; font-size: 11px; color: #666;">
            Analysis cost: ${analysis.cost_usd:.4f} | Generated: {analysis.timestamp.strftime('%H:%M:%S')}
        </div>
    </div>
    """


__all__ = [
    'TrainingAnalysis',
    'analyze_training_results',
    'format_analysis_html'
]
