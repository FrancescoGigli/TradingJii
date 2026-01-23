"""
🔍 Stability Report Module

Functions for generating and rendering parameter stability reports.
Validates that labeling parameters are well-tuned for ML training.
"""

import streamlit as st
import pandas as pd
from typing import Dict


def get_stability_report(labels_df: pd.DataFrame, timeframe: str = '15m') -> Dict:
    """
    Generate a stability report for labeling parameters.
    
    Args:
        labels_df: DataFrame with labels
        timeframe: '15m' or '1h'
    
    Returns:
        Dict with stability metrics and warnings
    """
    exit_col = f'exit_type_long_{timeframe}'
    valid_mask = labels_df[exit_col].notna() & (labels_df[exit_col] != 'invalid')
    df = labels_df[valid_mask]
    
    n_valid = len(df)
    if n_valid == 0:
        return {'valid': False, 'reason': 'No valid samples'}
    
    # Calculate stability metrics
    score_long = df[f'score_long_{timeframe}']
    score_short = df[f'score_short_{timeframe}']
    mae_long = df[f'mae_long_{timeframe}']
    mae_short = df[f'mae_short_{timeframe}']
    
    # Exit type distribution
    exit_counts_long = df[f'exit_type_long_{timeframe}'].value_counts(normalize=True)
    exit_counts_short = df[f'exit_type_short_{timeframe}'].value_counts(normalize=True)
    
    report = {
        'valid': True,
        'n_samples': n_valid,
        
        # Score stability
        'long_score_mean': score_long.mean(),
        'long_score_std': score_long.std(),
        'long_positive_pct': (score_long > 0).mean() * 100,
        'short_score_mean': score_short.mean(),
        'short_score_std': score_short.std(),
        'short_positive_pct': (score_short > 0).mean() * 100,
        
        # MAE analysis
        'long_mae_mean': mae_long.mean() * 100,
        'short_mae_mean': mae_short.mean() * 100,
        
        # Exit type balance
        'long_fixed_sl_pct': exit_counts_long.get('fixed_sl', 0) * 100,
        'long_trailing_pct': exit_counts_long.get('trailing', 0) * 100,
        'long_time_pct': exit_counts_long.get('time', 0) * 100,
        'short_fixed_sl_pct': exit_counts_short.get('fixed_sl', 0) * 100,
        'short_trailing_pct': exit_counts_short.get('trailing', 0) * 100,
        'short_time_pct': exit_counts_short.get('time', 0) * 100,
    }
    
    # Stability warnings
    warnings = []
    
    # Check if score distribution is too skewed
    if report['long_positive_pct'] > 70 or report['long_positive_pct'] < 30:
        warnings.append(
            f"⚠️ LONG score distribution skewed "
            f"({report['long_positive_pct']:.1f}% positive)"
        )
    
    if report['short_positive_pct'] > 70 or report['short_positive_pct'] < 30:
        warnings.append(
            f"⚠️ SHORT score distribution skewed "
            f"({report['short_positive_pct']:.1f}% positive)"
        )
    
    # Check if fixed_sl is being hit too often
    if report['long_fixed_sl_pct'] > 50:
        warnings.append(
            f"⚠️ LONG fixed_sl hit {report['long_fixed_sl_pct']:.1f}% "
            "- consider wider k_fixed_sl"
        )
    
    if report['short_fixed_sl_pct'] > 50:
        warnings.append(
            f"⚠️ SHORT fixed_sl hit {report['short_fixed_sl_pct']:.1f}% "
            "- consider wider k_fixed_sl"
        )
    
    # Check if time exit is too common
    if report['long_time_pct'] > 40:
        warnings.append(
            f"⚠️ LONG time exit {report['long_time_pct']:.1f}% "
            "- consider increasing max_bars"
        )
    
    if report['short_time_pct'] > 40:
        warnings.append(
            f"⚠️ SHORT time exit {report['short_time_pct']:.1f}% "
            "- consider increasing max_bars"
        )
    
    report['warnings'] = warnings
    report['is_stable'] = len(warnings) == 0
    
    return report


def render_stability_report(labels_df: pd.DataFrame, timeframe: str = '15m'):
    """
    Render stability report in Streamlit.
    
    Args:
        labels_df: DataFrame with labels
        timeframe: '15m' or '1h'
    """
    report = get_stability_report(labels_df, timeframe)
    
    if not report['valid']:
        st.error(f"Cannot generate report: {report['reason']}")
        return
    
    st.subheader("🔍 Stability Report")
    
    # Overall status
    if report['is_stable']:
        st.success("✅ Parameters appear STABLE - good for ML training")
    else:
        st.warning("⚠️ Parameters may need adjustment")
        for warning in report['warnings']:
            st.warning(warning)
    
    # Metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**LONG Labels:**")
        st.write(f"- Score Mean: {report['long_score_mean']:.5f}")
        st.write(f"- Score Std: {report['long_score_std']:.5f}")
        st.write(f"- Positive: {report['long_positive_pct']:.1f}%")
        st.write(f"- Avg MAE: {report['long_mae_mean']:.2f}%")
        st.write(
            f"- Exit: fixed_sl {report['long_fixed_sl_pct']:.1f}% | "
            f"trailing {report['long_trailing_pct']:.1f}% | "
            f"time {report['long_time_pct']:.1f}%"
        )
    
    with col2:
        st.markdown("**SHORT Labels:**")
        st.write(f"- Score Mean: {report['short_score_mean']:.5f}")
        st.write(f"- Score Std: {report['short_score_std']:.5f}")
        st.write(f"- Positive: {report['short_positive_pct']:.1f}%")
        st.write(f"- Avg MAE: {report['short_mae_mean']:.2f}%")
        st.write(
            f"- Exit: fixed_sl {report['short_fixed_sl_pct']:.1f}% | "
            f"trailing {report['short_trailing_pct']:.1f}% | "
            f"time {report['short_time_pct']:.1f}%"
        )
