"""
📊 Train Tab - Step 4: Models

View and manage trained models:
- List all available models
- View metrics and metadata
- Compare versions
- Delete old models
"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import os


def get_model_dir() -> Path:
    """Get models directory path"""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    
    if Path(shared_path).exists():
        model_dir = Path(shared_path) / "models"
    else:
        # Local development
        base = Path(__file__).parent.parent.parent.parent.parent
        model_dir = base / "shared" / "models"
    
    return model_dir


def get_available_models() -> list:
    """Get list of available model versions"""
    model_dir = get_model_dir()
    
    if not model_dir.exists():
        return []
    
    # Find all metadata files
    metadata_files = list(model_dir.glob("metadata_*.json"))
    
    models = []
    for f in metadata_files:
        if f.name == "metadata_latest.json":
            continue
        
        try:
            with open(f, 'r') as file:
                meta = json.load(file)
                
                # Extract version from filename
                version = f.stem.replace("metadata_", "")
                
                models.append({
                    'version': version,
                    'created_at': meta.get('created_at', ''),
                    'timeframe': meta.get('timeframe', meta.get('timeframes', ['?'])),
                    'n_features': meta.get('n_features', 0),
                    'n_train': meta.get('n_train_samples', 0),
                    'n_test': meta.get('n_test_samples', 0),
                    'r2_long': meta.get('metrics_long', {}).get('test_r2', 0),
                    'r2_short': meta.get('metrics_short', {}).get('test_r2', 0),
                    'spearman_long': meta.get('metrics_long', {}).get('ranking', {}).get('spearman_corr', 
                                     meta.get('metrics_long', {}).get('test_spearman', 0)),
                    'spearman_short': meta.get('metrics_short', {}).get('ranking', {}).get('spearman_corr',
                                      meta.get('metrics_short', {}).get('test_spearman', 0)),
                    'is_optuna': 'optuna' in version.lower(),
                    'file_path': str(f)
                })
        except Exception as e:
            continue
    
    # Sort by creation date (newest first)
    models.sort(key=lambda x: x['created_at'], reverse=True)
    
    return models


def load_model_metadata(version: str) -> dict:
    """Load full metadata for a specific version"""
    model_dir = get_model_dir()
    metadata_path = model_dir / f"metadata_{version}.json"
    
    if not metadata_path.exists():
        return {}
    
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except:
        return {}


def delete_model(version: str) -> bool:
    """Delete a model version"""
    model_dir = get_model_dir()
    
    files_to_delete = [
        f"model_long_{version}.pkl",
        f"model_short_{version}.pkl",
        f"scaler_{version}.pkl",
        f"metadata_{version}.json"
    ]
    
    try:
        for filename in files_to_delete:
            file_path = model_dir / filename
            if file_path.exists():
                file_path.unlink()
        return True
    except Exception as e:
        return False


def render_models_step():
    """Render Step 4: Model viewer"""
    
    st.markdown("### 📊 Step 4: Models")
    st.caption("View and manage trained XGBoost models")
    
    # Get available models
    models = get_available_models()
    
    if not models:
        st.warning("⚠️ **No trained models found!**")
        st.info("Complete **Step 3 (Training)** first to train a model.")
        return
    
    # === MODELS LIST ===
    st.markdown("#### 📋 Available Models")
    
    # Create summary table
    df_models = pd.DataFrame(models)
    df_display = df_models[['version', 'created_at', 'timeframe', 'n_features', 
                            'r2_long', 'spearman_long', 'is_optuna']].copy()
    
    # Format columns
    df_display['created_at'] = df_display['created_at'].str[:19]
    df_display['r2_long'] = df_display['r2_long'].apply(lambda x: f"{x:.4f}")
    df_display['spearman_long'] = df_display['spearman_long'].apply(lambda x: f"{x:.4f}")
    df_display['is_optuna'] = df_display['is_optuna'].apply(lambda x: "🔮 Optuna" if x else "⚙️ Manual")
    
    df_display.columns = ['Version', 'Created', 'Timeframe', 'Features', 'R² (Long)', 'Spearman', 'Type']
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    st.caption(f"Total: {len(models)} model(s)")
    
    # === MODEL DETAILS ===
    st.divider()
    st.markdown("#### 🔍 Model Details")
    
    # Select model
    version_options = [m['version'] for m in models]
    selected_version = st.selectbox(
        "Select Model Version",
        version_options,
        key="model_version_select"
    )
    
    if selected_version:
        metadata = load_model_metadata(selected_version)
        
        if metadata:
            # Header info
            col1, col2, col3 = st.columns(3)
            col1.metric("Version", selected_version[:15] + "...")
            col2.metric("Created", metadata.get('created_at', '')[:10])
            
            tf = metadata.get('timeframe', metadata.get('timeframes', '?'))
            if isinstance(tf, list):
                tf = ', '.join(tf)
            col3.metric("Timeframe", tf)
            
            # Training info
            st.markdown("---")
            st.markdown("**📈 Training Overview:**")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Features", metadata.get('n_features', 0))
            c2.metric("Train Samples", f"{metadata.get('n_train_samples', 0):,}")
            c3.metric("Test Samples", f"{metadata.get('n_test_samples', 0):,}")
            c4.metric("Train Ratio", f"{metadata.get('train_ratio', 0.8)*100:.0f}%")
            
            # Data range
            data_range = metadata.get('data_range', {})
            if data_range:
                st.markdown("---")
                st.markdown("**📅 Data Range:**")
                
                c1, c2 = st.columns(2)
                c1.write(f"**Train:** {data_range.get('train_start', '')[:10]} → {data_range.get('train_end', '')[:10]}")
                c2.write(f"**Test:** {data_range.get('test_start', '')[:10]} → {data_range.get('test_end', '')[:10]}")
            
            # Metrics
            st.markdown("---")
            st.markdown("**📊 Model Metrics:**")
            
            metrics_long = metadata.get('metrics_long', {})
            metrics_short = metadata.get('metrics_short', {})
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**LONG Model:**")
                
                # Regression metrics
                r2 = metrics_long.get('test_r2', 0)
                rmse = metrics_long.get('test_rmse', 0)
                mae = metrics_long.get('test_mae', metrics_long.get('test_rmse', 0))
                
                st.write(f"- R²: **{r2:.4f}**")
                st.write(f"- RMSE: **{rmse:.6f}**")
                st.write(f"- MAE: **{mae:.6f}**")
                
                # Ranking metrics
                ranking = metrics_long.get('ranking', {})
                if ranking:
                    st.write(f"- Spearman: **{ranking.get('spearman_corr', 0):.4f}**")
                elif 'test_spearman' in metrics_long:
                    st.write(f"- Spearman: **{metrics_long['test_spearman']:.4f}**")
            
            with col2:
                st.markdown("**SHORT Model:**")
                
                r2 = metrics_short.get('test_r2', 0)
                rmse = metrics_short.get('test_rmse', 0)
                mae = metrics_short.get('test_mae', metrics_short.get('test_rmse', 0))
                
                st.write(f"- R²: **{r2:.4f}**")
                st.write(f"- RMSE: **{rmse:.6f}**")
                st.write(f"- MAE: **{mae:.6f}**")
                
                ranking = metrics_short.get('ranking', {})
                if ranking:
                    st.write(f"- Spearman: **{ranking.get('spearman_corr', 0):.4f}**")
                elif 'test_spearman' in metrics_short:
                    st.write(f"- Spearman: **{metrics_short['test_spearman']:.4f}**")
            
            # Precision@K Analysis
            ranking_long = metrics_long.get('ranking', {})
            if ranking_long:
                st.markdown("---")
                st.markdown("**🎯 Precision@K (LONG):**")
                
                prec_data = []
                for k in [1, 5, 10, 20]:
                    avg_key = f'top{k}pct_avg_score'
                    pos_key = f'top{k}pct_positive'
                    
                    if avg_key in ranking_long:
                        prec_data.append({
                            'Top K%': f"{k}%",
                            'Avg Score': f"{ranking_long[avg_key]:.5f}",
                            '% Positive': f"{ranking_long.get(pos_key, 0):.1f}%"
                        })
                
                if prec_data:
                    st.dataframe(pd.DataFrame(prec_data), use_container_width=True, hide_index=True)
            
            # XGBoost Parameters
            xgb_params = metadata.get('xgboost_params', metadata.get('best_params_long', {}))
            if xgb_params:
                with st.expander("⚙️ XGBoost Parameters"):
                    # Filter out non-param keys
                    param_keys = ['n_estimators', 'max_depth', 'learning_rate', 'min_child_weight',
                                  'subsample', 'colsample_bytree', 'reg_alpha', 'reg_lambda']
                    
                    for key in param_keys:
                        if key in xgb_params:
                            st.write(f"- {key}: **{xgb_params[key]}**")
            
            # Feature list
            features = metadata.get('feature_names', [])
            if features:
                with st.expander(f"📋 Features ({len(features)})"):
                    st.write(", ".join(features))
            
            # Model files
            with st.expander("📁 Model Files"):
                model_dir = get_model_dir()
                files = [
                    f"model_long_{selected_version}.pkl",
                    f"model_short_{selected_version}.pkl",
                    f"scaler_{selected_version}.pkl",
                    f"metadata_{selected_version}.json"
                ]
                
                for f in files:
                    fpath = model_dir / f
                    if fpath.exists():
                        size_kb = fpath.stat().st_size / 1024
                        st.write(f"✅ `{f}` ({size_kb:.1f} KB)")
                    else:
                        st.write(f"❌ `{f}` (missing)")
            
            # Delete button
            st.markdown("---")
            
            if st.button("🗑️ Delete This Model", type="secondary", use_container_width=True):
                st.session_state['confirm_delete'] = selected_version
            
            if st.session_state.get('confirm_delete') == selected_version:
                st.warning(f"⚠️ Are you sure you want to delete version `{selected_version}`?")
                
                c1, c2 = st.columns(2)
                if c1.button("✅ Yes, Delete", type="primary"):
                    if delete_model(selected_version):
                        st.success("✅ Model deleted!")
                        st.session_state['confirm_delete'] = None
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete model")
                
                if c2.button("❌ Cancel"):
                    st.session_state['confirm_delete'] = None
                    st.rerun()
        else:
            st.error("❌ Could not load metadata for this version")


__all__ = ['render_models_step']
