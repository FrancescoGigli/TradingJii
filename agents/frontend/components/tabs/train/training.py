"""
🚀 Train Tab - Step 3: Interactive Training

Training is now handled by the ml-training container.
This UI only submits jobs and monitors progress via polling.

Features:
- Current model status display
- Submit training requests
- Real-time progress monitoring (polling every 3s)
- Display results when complete
"""

import streamlit as st
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional

from database import get_connection

# Training service (simplified - no XGBoost here)
try:
    from services.training_service import (
        submit_training_request,
        get_training_job_status,
        get_active_training_job,
        get_training_history,
        cancel_training_job,
        load_model_metadata,
        get_training_labels_count,
        model_exists
    )
    from database.training_jobs import TrainingJob
    SERVICE_AVAILABLE = True
except ImportError as e:
    SERVICE_AVAILABLE = False
    IMPORT_ERROR = str(e)

# Visualization imports (optional)
try:
    from ai.visualizations.training_charts import (
        create_metrics_comparison,
        create_precision_at_k_chart,
        create_training_summary_card
    )
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False


def _render_progress_bar(job: TrainingJob):
    """Render progress bar for active job."""
    progress = job.progress_pct / 100
    
    # Status emoji
    if job.status == 'pending':
        emoji = "⏳"
        status_text = "Waiting for ml-training container..."
    elif job.status == 'running':
        emoji = "🔄"
        model_phase = job.current_model or "LONG"
        trial_info = f"Trial {job.current_trial}/{job.total_trials}"
        status_text = f"Training {model_phase} model - {trial_info}"
    else:
        emoji = "✅" if job.status == 'completed' else "❌"
        status_text = job.status.capitalize()
    
    st.markdown(f"### {emoji} Training Status: **{job.status.upper()}**")
    st.progress(progress)
    st.caption(status_text)
    
    # Show best scores if available
    col1, col2 = st.columns(2)
    with col1:
        if job.best_score_long:
            st.metric("📈 Best LONG Spearman", f"{job.best_score_long:.4f}")
    with col2:
        if job.best_score_short:
            st.metric("📉 Best SHORT Spearman", f"{job.best_score_short:.4f}")


def _render_active_job(job: TrainingJob):
    """Render active job monitoring section."""
    st.markdown("---")
    st.markdown("### 🔄 Active Training Job")
    
    _render_progress_bar(job)
    
    # Estimated time
    if job.status == 'running' and job.current_trial > 0:
        # Rough estimate: ~3 seconds per trial
        remaining_trials = job.total_trials - job.current_trial
        eta_seconds = remaining_trials * 3
        eta_min = eta_seconds // 60
        eta_sec = eta_seconds % 60
        st.caption(f"⏱️ Estimated time remaining: ~{eta_min}m {eta_sec}s")
    
    # Cancel button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🛑 Cancel", key="cancel_job"):
            if cancel_training_job(job.id):
                st.warning("⚠️ Cancellation requested")
                time.sleep(1)
                st.rerun()
    with col2:
        if st.button("🔄 Refresh", key="refresh_job"):
            st.rerun()
    
    # Auto-refresh hint
    st.info("💡 Progress updates automatically every 3 seconds while training is active.")
    
    # Trial log (if available)
    if job.trial_log and len(job.trial_log) > 0:
        with st.expander("📝 Trial Log (last 10)", expanded=False):
            for trial in reversed(job.trial_log[-10:]):
                model = trial.get('model', '?')
                trial_num = trial.get('trial', 0)
                spearman = trial.get('spearman', 0)
                emoji = "📈" if model == 'LONG' else "📉"
                st.text(f"{emoji} {model} Trial {trial_num}: Spearman = {spearman:.4f}")


def _render_current_models():
    """Render the current trained models status section."""
    st.markdown("#### 📦 Current Trained Models")
    
    meta_15m = load_model_metadata('15m')
    meta_1h = load_model_metadata('1h')
    
    if not meta_15m and not meta_1h:
        st.warning("⚠️ **No trained models found.** Train a model to see results here.")
        return
    
    # Tabs for each timeframe
    available_tabs = []
    if meta_15m:
        available_tabs.append("🔵 15m Model")
    if meta_1h:
        available_tabs.append("🟢 1h Model")
    
    if len(available_tabs) == 2:
        tab1, tab2 = st.tabs(available_tabs)
        _render_model_details(tab1, meta_15m, '15m')
        _render_model_details(tab2, meta_1h, '1h')
    elif meta_15m:
        _render_model_details(st, meta_15m, '15m')
    elif meta_1h:
        _render_model_details(st, meta_1h, '1h')


def _render_model_details(container, metadata: Dict[str, Any], timeframe: str):
    """Render detailed model info."""
    with container:
        # Summary card (if charts available)
        if CHARTS_AVAILABLE:
            result_dict = {
                'success': True,
                'timeframe': timeframe,
                'version': metadata.get('version', 'Unknown'),
                'metrics_long': metadata.get('metrics_long', {}),
                'metrics_short': metadata.get('metrics_short', {}),
                'n_features': metadata.get('n_features', 0),
                'n_train': metadata.get('n_train_samples', 0),
                'n_test': metadata.get('n_test_samples', 0),
                'best_params_long': metadata.get('best_params_long', {}),
                'best_params_short': metadata.get('best_params_short', {}),
                'n_trials': metadata.get('n_trials', 0),
                'error': ''
            }
            
            summary_html = create_training_summary_card(result_dict, timeframe)
            st.markdown(summary_html, unsafe_allow_html=True)
        else:
            # Simple fallback
            metrics_long = metadata.get('metrics_long', {})
            metrics_short = metadata.get('metrics_short', {})
            
            col1, col2 = st.columns(2)
            with col1:
                ranking = metrics_long.get('ranking', {})
                st.metric("📈 LONG Spearman", f"{ranking.get('spearman_corr', 0):.4f}")
            with col2:
                ranking = metrics_short.get('ranking', {})
                st.metric("📉 SHORT Spearman", f"{ranking.get('spearman_corr', 0):.4f}")
        
        # Training date
        created_at = metadata.get('created_at', 'Unknown')
        if created_at != 'Unknown':
            st.caption(f"📅 Trained on: {created_at[:19].replace('T', ' ')}")
        
        # Metrics charts (if available)
        if CHARTS_AVAILABLE:
            metrics_long = metadata.get('metrics_long', {})
            metrics_short = metadata.get('metrics_short', {})
            
            if metrics_long and metrics_short:
                col1, col2 = st.columns(2)
                
                with col1:
                    fig = create_metrics_comparison(metrics_long, metrics_short)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = create_precision_at_k_chart(metrics_long, metrics_short)
                    st.plotly_chart(fig, use_container_width=True)
        
        # Data range
        data_range = metadata.get('data_range', {})
        if data_range:
            with st.expander("📊 Training Data Range"):
                st.markdown(f"""
                - **Train Start:** {data_range.get('train_start', 'N/A')}
                - **Train End:** {data_range.get('train_end', 'N/A')}
                - **Test Start:** {data_range.get('test_start', 'N/A')}
                - **Test End:** {data_range.get('test_end', 'N/A')}
                """)


def _render_new_training_form():
    """Render form to submit new training job."""
    st.markdown("#### 🎯 Train New Model")
    
    # Check labels availability
    labels_15m = get_training_labels_count('15m')
    labels_1h = get_training_labels_count('1h')
    
    if labels_15m == 0 and labels_1h == 0:
        st.error("❌ **No training labels available!**")
        st.info("Complete **Step 2 (Labeling)** first to generate training data.")
        return
    
    # Data overview
    with st.expander("📊 Available Training Data", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("15m Samples", f"{labels_15m:,}")
        c2.metric("1h Samples", f"{labels_1h:,}")
        c3.metric("Total", f"{labels_15m + labels_1h:,}")
    
    # Configuration
    col1, col2 = st.columns(2)
    
    with col1:
        # Timeframe selection
        options = []
        if labels_15m > 0:
            options.append("15m")
        if labels_1h > 0:
            options.append("1h")
        
        selected_tf = st.selectbox(
            "Select Timeframe",
            options,
            key="train_tf_select"
        )
    
    with col2:
        n_trials = st.slider(
            "Optuna Trials",
            min_value=10,
            max_value=50,
            value=20,
            step=5,
            key="n_trials_slider"
        )
    
    # Estimated time
    est_time_min = (n_trials / 15) * 5  # ~5 minutes for 15 trials
    est_time_max = est_time_min * 1.5
    st.info(f"⏱️ Estimated time: **{est_time_min:.0f}-{est_time_max:.0f} minutes** for {n_trials} trials")
    
    # Submit button
    if st.button("🚀 Start Training", use_container_width=True, type="primary"):
        job_id = submit_training_request(
            timeframe=selected_tf,
            n_trials=n_trials,
            train_ratio=0.8
        )
        
        if job_id:
            st.success(f"✅ Training job submitted! Job ID: {job_id}")
            st.info("🔄 The ml-training container will start processing shortly...")
            # Store job ID in session state for tracking
            st.session_state['active_job_id'] = job_id
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Failed to submit training job")


def render_training_step():
    """Render Step 3: Interactive XGBoost Training."""
    st.markdown("### 🚀 Step 3: Interactive Training")
    st.caption("Submit training jobs - execution handled by ml-training container")
    
    # Check service availability
    if not SERVICE_AVAILABLE:
        st.error(f"❌ **Training service error:** {IMPORT_ERROR}")
        return
    
    # Check for active training job
    active_job = get_active_training_job()
    
    if active_job:
        # Show active job progress
        _render_active_job(active_job)
        
        # Auto-refresh if running
        if active_job.status in ('pending', 'running'):
            time.sleep(3)  # Wait 3 seconds
            st.rerun()
        
        # If completed, show results
        if active_job.status == 'completed':
            st.success("✅ Training completed!")
            st.balloons()
            st.info("🔄 Refresh the page to see updated models above.")
    else:
        # Show current models
        _render_current_models()
        
        st.divider()
        
        # Show form to submit new training
        _render_new_training_form()
    
    # Training history
    st.markdown("---")
    with st.expander("📜 Training History", expanded=False):
        history = get_training_history(limit=5)
        if history:
            for job in history:
                status_emoji = {
                    'completed': '✅',
                    'failed': '❌',
                    'cancelled': '🛑',
                    'running': '🔄',
                    'pending': '⏳'
                }.get(job.status, '❓')
                
                st.markdown(f"""
                **{status_emoji} Job {job.id}** - {job.timeframe} | {job.status}
                - Requested: {job.requested_at[:19] if job.requested_at else 'N/A'}
                - Progress: {job.progress_pct:.0f}%
                """)
        else:
            st.info("No training history yet.")


__all__ = ['render_training_step']
