"""
🔬 Labeling Optuna UI

Optuna optimization UI for label parameters:
- Configurable search ranges
- Visualization of results
- Integration with labeling pipeline
"""

import streamlit as st
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Tuple

from ai.core.labels import TrailingLabelConfig
from .labeling_db import get_training_features_symbols, get_training_features_data
from .labeling_pipeline import run_labeling_pipeline_both


# ═══════════════════════════════════════════════════════════════════════════════
# OPTUNA SEARCH RANGES (defaults)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class OptunaSearchRanges:
    """Configurable search ranges for Optuna optimization"""
    
    # 15m Trailing Stop (%)
    trailing_15m_min: float = 0.5
    trailing_15m_max: float = 3.0
    
    # 1h Trailing Stop (%)
    trailing_1h_min: float = 1.0
    trailing_1h_max: float = 5.0
    
    # 15m Max Bars
    max_bars_15m_min: int = 12
    max_bars_15m_max: int = 96
    
    # 1h Max Bars
    max_bars_1h_min: int = 6
    max_bars_1h_max: int = 48
    
    # Time Penalty Lambda
    lambda_min: float = 0.0001
    lambda_max: float = 0.01
    
    # Trading Cost
    cost_min: float = 0.0005
    cost_max: float = 0.003


def render_optuna_search_ranges() -> OptunaSearchRanges:
    """Render UI for configuring Optuna search ranges - returns config"""
    
    ranges = OptunaSearchRanges()
    
    st.markdown("##### 📐 Optuna Search Ranges")
    st.caption("Configure the parameter ranges that Optuna will search")
    
    # Create 3 columns for the ranges
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**📊 15m Parameters**")
        
        trailing_15m = st.slider(
            "Trailing Stop Range (15m)",
            min_value=0.3,
            max_value=5.0,
            value=(0.5, 3.0),
            step=0.1,
            format="%.1f%%",
            key="optuna_range_ts_15m",
            help="Search range for 15m trailing stop percentage"
        )
        ranges.trailing_15m_min = trailing_15m[0]
        ranges.trailing_15m_max = trailing_15m[1]
        
        max_bars_15m = st.slider(
            "Max Bars Range (15m)",
            min_value=6,
            max_value=144,
            value=(12, 96),
            step=6,
            key="optuna_range_mb_15m",
            help="Search range for 15m max bars"
        )
        ranges.max_bars_15m_min = max_bars_15m[0]
        ranges.max_bars_15m_max = max_bars_15m[1]
    
    with col2:
        st.markdown("**📊 1h Parameters**")
        
        trailing_1h = st.slider(
            "Trailing Stop Range (1h)",
            min_value=0.5,
            max_value=8.0,
            value=(1.0, 5.0),
            step=0.1,
            format="%.1f%%",
            key="optuna_range_ts_1h",
            help="Search range for 1h trailing stop percentage"
        )
        ranges.trailing_1h_min = trailing_1h[0]
        ranges.trailing_1h_max = trailing_1h[1]
        
        max_bars_1h = st.slider(
            "Max Bars Range (1h)",
            min_value=6,
            max_value=72,
            value=(6, 48),
            step=6,
            key="optuna_range_mb_1h",
            help="Search range for 1h max bars"
        )
        ranges.max_bars_1h_min = max_bars_1h[0]
        ranges.max_bars_1h_max = max_bars_1h[1]
    
    with col3:
        st.markdown("**💰 Common Parameters**")
        
        lambda_range = st.slider(
            "Time Penalty (λ) Range",
            min_value=0.0001,
            max_value=0.02,
            value=(0.0001, 0.01),
            step=0.0001,
            format="%.4f",
            key="optuna_range_lambda",
            help="Search range for time penalty"
        )
        ranges.lambda_min = lambda_range[0]
        ranges.lambda_max = lambda_range[1]
        
        cost_range = st.slider(
            "Trading Cost Range",
            min_value=0.0001,
            max_value=0.005,
            value=(0.0005, 0.003),
            step=0.0001,
            format="%.4f",
            key="optuna_range_cost",
            help="Search range for trading cost"
        )
        ranges.cost_min = cost_range[0]
        ranges.cost_max = cost_range[1]
    
    # Summary of ranges
    st.markdown("---")
    st.markdown("**📋 Search Space Summary:**")
    
    summary = f"""
| Parameter | 15m Range | 1h Range |
|-----------|-----------|----------|
| **Trailing Stop** | {ranges.trailing_15m_min:.1f}% - {ranges.trailing_15m_max:.1f}% | {ranges.trailing_1h_min:.1f}% - {ranges.trailing_1h_max:.1f}% |
| **Max Bars** | {ranges.max_bars_15m_min} - {ranges.max_bars_15m_max} | {ranges.max_bars_1h_min} - {ranges.max_bars_1h_max} |
| **Time Penalty (λ)** | {ranges.lambda_min:.4f} - {ranges.lambda_max:.4f} | (same) |
| **Trading Cost** | {ranges.cost_min:.4f} - {ranges.cost_max:.4f} | (same) |
"""
    st.markdown(summary)
    
    return ranges


def render_optuna_section(symbols_15m: list, symbols_1h: list):
    """Render the complete Optuna optimization section"""
    
    st.markdown("#### 🔬 Optuna Optimization")
    
    use_optuna = st.checkbox(
        "**Use Optuna** to auto-optimize label parameters",
        value=False,
        key="use_optuna_labeling",
        help="Optuna finds the best trailing stop parameters automatically"
    )
    
    if not use_optuna:
        return None, None, None, None, False
    
    st.info("🤖 Optuna will find optimal parameters for **both 15m and 1h** timeframes")
    
    with st.expander("⚡ Optuna Configuration", expanded=True):
        # Basic settings
        opt_col1, opt_col2 = st.columns(2)
        
        with opt_col1:
            optuna_objective = st.selectbox(
                "Optimization Objective",
                ["win_rate", "sharpe_ratio", "profit_factor", "expected_value"],
                index=0,
                key="optuna_objective_labeling",
                help="Metric to maximize"
            )
            
            n_trials = st.slider(
                "Number of Trials",
                min_value=10,
                max_value=200,
                value=50,
                step=10,
                key="n_trials_labeling"
            )
        
        with opt_col2:
            timeout_minutes = st.slider(
                "Timeout (minutes)",
                min_value=1,
                max_value=30,
                value=5,
                key="timeout_labeling"
            )
            
            n_samples = st.slider(
                "Sample Symbols",
                min_value=1,
                max_value=min(10, len(symbols_15m)),
                value=min(3, len(symbols_15m)),
                key="n_samples_labeling",
                help="Number of symbols to use for optimization (more = slower but more accurate)"
            )
        
        st.divider()
        
        # Search ranges
        ranges = render_optuna_search_ranges()
    
    return optuna_objective, n_trials, timeout_minutes, ranges, True


def run_optuna_optimization(
    optuna_objective: str,
    n_trials: int,
    timeout_minutes: int,
    ranges: OptunaSearchRanges,
    n_samples: int,
    symbols_15m: list,
    symbols_1h: list
) -> Tuple[Dict, Dict]:
    """Run Optuna optimization and return results"""
    
    try:
        from ai.optimizer.label_optimizer import LabelOptimizer, PARAM_SEARCH_SPACE
        from ai.visualizations.optuna_charts import (
            create_optimization_history_chart,
            create_param_importance_chart
        )
        
        status_container = st.empty()
        progress_container = st.empty()
        
        status_container.info("🔄 Loading sample data for optimization...")
        
        # Load sample data
        sample_symbols = symbols_15m[:n_samples]
        
        all_data_15m = []
        for sym in sample_symbols:
            df = get_training_features_data(sym, '15m')
            if len(df) > 0:
                all_data_15m.append(df)
        
        all_data_1h = []
        for sym in sample_symbols:
            df = get_training_features_data(sym, '1h')
            if len(df) > 0:
                all_data_1h.append(df)
        
        if not all_data_15m or not all_data_1h:
            st.error("Failed to load data for optimization")
            return None, None
        
        combined_15m = pd.concat(all_data_15m)
        combined_1h = pd.concat(all_data_1h)
        
        # Update PARAM_SEARCH_SPACE with user-defined ranges
        PARAM_SEARCH_SPACE['trailing_stop_pct_15m'] = {
            'low': ranges.trailing_15m_min / 100,
            'high': ranges.trailing_15m_max / 100,
            'step': 0.001
        }
        PARAM_SEARCH_SPACE['trailing_stop_pct_1h'] = {
            'low': ranges.trailing_1h_min / 100,
            'high': ranges.trailing_1h_max / 100,
            'step': 0.001
        }
        PARAM_SEARCH_SPACE['max_bars_15m'] = {
            'low': ranges.max_bars_15m_min,
            'high': ranges.max_bars_15m_max,
            'step': 6
        }
        PARAM_SEARCH_SPACE['max_bars_1h'] = {
            'low': ranges.max_bars_1h_min,
            'high': ranges.max_bars_1h_max,
            'step': 6
        }
        PARAM_SEARCH_SPACE['time_penalty_lambda'] = {
            'low': ranges.lambda_min,
            'high': ranges.lambda_max,
            'log': True
        }
        PARAM_SEARCH_SPACE['trading_cost'] = {
            'low': ranges.cost_min,
            'high': ranges.cost_max,
            'step': 0.0005
        }
        
        status_container.info(f"🚀 Running Optuna with {n_trials} trials...")
        progress_bar = progress_container.progress(0)
        
        # Optimize 15m
        st.markdown("##### 📊 Optimizing 15m parameters...")
        optimizer_15m = LabelOptimizer(
            ohlcv_df=combined_15m,
            timeframe='15m',
            n_trials=n_trials // 2,
            timeout=timeout_minutes * 30
        )
        result_15m = optimizer_15m.optimize()
        progress_bar.progress(50)
        
        # Optimize 1h
        st.markdown("##### 📊 Optimizing 1h parameters...")
        optimizer_1h = LabelOptimizer(
            ohlcv_df=combined_1h,
            timeframe='1h',
            n_trials=n_trials // 2,
            timeout=timeout_minutes * 30
        )
        result_1h = optimizer_1h.optimize()
        progress_bar.progress(100)
        
        return result_15m, result_1h
        
    except ImportError as e:
        st.error(f"❌ Optuna optimizer not available: {e}")
        return None, None
    except Exception as e:
        st.error(f"❌ Optimization failed: {e}")
        import traceback
        st.code(traceback.format_exc())
        return None, None


def display_optuna_results(result_15m, result_1h, objective: str):
    """Display Optuna optimization results with charts"""
    
    from ai.visualizations.optuna_charts import (
        create_optimization_history_chart,
        create_param_importance_chart
    )
    
    st.success("✅ Optimization complete!")
    
    # 15m Results
    st.markdown("### 📈 15 Minutes - Results")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Best " + objective.replace('_', ' ').title(), 
                  f"{result_15m.best_value:.4f}")
    with col2:
        st.metric("Trailing Stop", 
                  f"{result_15m.best_params.get('trailing_stop_pct_15m', 0.015)*100:.2f}%")
    with col3:
        st.metric("Max Bars", 
                  f"{result_15m.best_params.get('max_bars_15m', 48)}")
    with col4:
        st.metric("Time Penalty", 
                  f"{result_15m.best_params.get('time_penalty_lambda', 0.001):.4f}")
    
    if hasattr(result_15m, 'study'):
        fig_history_15m = create_optimization_history_chart(result_15m.study, "15m Optimization History")
        st.plotly_chart(fig_history_15m, use_container_width=True)
        
        if result_15m.param_importances:
            fig_importance_15m = create_param_importance_chart(result_15m.param_importances, "15m Parameter Importance")
            st.plotly_chart(fig_importance_15m, use_container_width=True)
    
    st.markdown("---")
    
    # 1h Results
    st.markdown("### 📈 1 Hour - Results")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Best " + objective.replace('_', ' ').title(), 
                  f"{result_1h.best_value:.4f}")
    with col2:
        st.metric("Trailing Stop", 
                  f"{result_1h.best_params.get('trailing_stop_pct_1h', 0.025)*100:.2f}%")
    with col3:
        st.metric("Max Bars", 
                  f"{result_1h.best_params.get('max_bars_1h', 24)}")
    with col4:
        st.metric("Time Penalty", 
                  f"{result_1h.best_params.get('time_penalty_lambda', 0.001):.4f}")
    
    if hasattr(result_1h, 'study'):
        fig_history_1h = create_optimization_history_chart(result_1h.study, "1h Optimization History")
        st.plotly_chart(fig_history_1h, use_container_width=True)
        
        if result_1h.param_importances:
            fig_importance_1h = create_param_importance_chart(result_1h.param_importances, "1h Parameter Importance")
            st.plotly_chart(fig_importance_1h, use_container_width=True)


def generate_labels_with_optimal_params(result_15m, result_1h, symbols_15m: list, symbols_1h: list):
    """Generate labels using optimal parameters from Optuna"""
    
    config = TrailingLabelConfig()
    config.trailing_stop_pct_15m = result_15m.best_params.get('trailing_stop_pct_15m', 0.015)
    config.trailing_stop_pct_1h = result_1h.best_params.get('trailing_stop_pct_1h', 0.025)
    config.max_bars_15m = result_15m.best_params.get('max_bars_15m', 48)
    config.max_bars_1h = result_1h.best_params.get('max_bars_1h', 24)
    config.time_penalty_lambda = result_15m.best_params.get('time_penalty_lambda', 0.001)
    config.trading_cost = result_15m.best_params.get('trading_cost', 0.001)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_symbols = len(symbols_15m) + len(symbols_1h)
    
    def update_progress(current, total, symbol, timeframe):
        if timeframe == '15m':
            overall = current
        else:
            overall = len(symbols_15m) + current
        progress_bar.progress(overall / total_symbols)
        status_text.text(f"Processing {timeframe}: {symbol.replace('/USDT:USDT', '')}")
    
    success, message = run_labeling_pipeline_both(config, update_progress)
    
    if success:
        st.success(f"✅ {message}")
        st.cache_data.clear()
    else:
        st.error(f"❌ {message}")


__all__ = [
    'OptunaSearchRanges',
    'render_optuna_search_ranges',
    'render_optuna_section',
    'run_optuna_optimization',
    'display_optuna_results',
    'generate_labels_with_optimal_params'
]
