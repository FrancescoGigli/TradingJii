"""
📊 Train Tab - Pipeline Status Dashboard

Mostra lo stato di ogni step del pipeline con verifiche:
- Step 1: Data - Verifica training_data
- Step 2: Labeling - Verifica training_labels  
- Step 3: Training - Verifica modelli salvati
"""

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from database import get_connection


@st.cache_data(ttl=60)
def get_pipeline_status() -> dict:
    """Get status of all pipeline steps"""
    status = {
        'step1_data': {'status': '❌', 'message': 'Not started', 'details': {}},
        'step2_labels': {'status': '❌', 'message': 'Not started', 'details': {}},
        'step3_model': {'status': '❌', 'message': 'Not started', 'details': {}},
    }
    
    conn = get_connection()
    if not conn:
        return status
    
    try:
        cur = conn.cursor()
        
        # === STEP 1: Check training_data ===
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_data'")
        if cur.fetchone():
            cur.execute('''
                SELECT 
                    timeframe,
                    COUNT(*) as rows,
                    COUNT(DISTINCT symbol) as symbols,
                    MIN(timestamp) as min_date,
                    MAX(timestamp) as max_date
                FROM training_data
                GROUP BY timeframe
            ''')
            data_stats = {}
            for row in cur.fetchall():
                data_stats[row[0]] = {
                    'rows': row[1],
                    'symbols': row[2],
                    'min_date': row[3],
                    'max_date': row[4]
                }
            
            if data_stats:
                total_rows = sum(d['rows'] for d in data_stats.values())
                total_symbols = max(d['symbols'] for d in data_stats.values()) if data_stats else 0
                
                if total_rows >= 10000:
                    status['step1_data']['status'] = '✅'
                    status['step1_data']['message'] = f'{total_rows:,} rows, {total_symbols} symbols'
                elif total_rows > 0:
                    status['step1_data']['status'] = '⚠️'
                    status['step1_data']['message'] = f'{total_rows:,} rows (need more data)'
                
                status['step1_data']['details'] = data_stats
        
        # === STEP 2: Check training_labels ===
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_labels'")
        if cur.fetchone():
            cur.execute('''
                SELECT 
                    timeframe,
                    COUNT(*) as rows,
                    COUNT(DISTINCT symbol) as symbols,
                    AVG(score_long) as avg_score_long,
                    AVG(score_short) as avg_score_short,
                    SUM(CASE WHEN exit_type_long = 'trailing' THEN 1 ELSE 0 END) as trailing_exits,
                    SUM(CASE WHEN exit_type_long = 'time' THEN 1 ELSE 0 END) as time_exits
                FROM training_labels
                GROUP BY timeframe
            ''')
            label_stats = {}
            for row in cur.fetchall():
                label_stats[row[0]] = {
                    'rows': row[1],
                    'symbols': row[2],
                    'avg_score_long': row[3],
                    'avg_score_short': row[4],
                    'trailing_exits': row[5],
                    'time_exits': row[6]
                }
            
            if label_stats:
                total_labels = sum(d['rows'] for d in label_stats.values())
                
                if total_labels >= 10000:
                    status['step2_labels']['status'] = '✅'
                    status['step2_labels']['message'] = f'{total_labels:,} labels generated'
                elif total_labels > 0:
                    status['step2_labels']['status'] = '⚠️'
                    status['step2_labels']['message'] = f'{total_labels:,} labels (need more)'
                
                status['step2_labels']['details'] = label_stats
        
        conn.close()
        
    except Exception as e:
        status['step1_data']['message'] = f'Error: {str(e)}'
    
    # === STEP 3: Check models ===
    import os
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    model_dir = Path(shared_path) / 'models'
    
    if not model_dir.exists():
        model_dir = Path(__file__).parent.parent.parent.parent.parent / 'shared' / 'models'
    
    metadata_file = model_dir / 'metadata_latest.json'
    
    if metadata_file.exists():
        try:
            with open(metadata_file) as f:
                meta = json.load(f)
            
            r2_long = meta.get('metrics_long', {}).get('test_r2', 0)
            r2_short = meta.get('metrics_short', {}).get('test_r2', 0)
            spear_long = meta.get('metrics_long', {}).get('ranking', {}).get('spearman_corr', 0)
            
            if r2_long > 0 and spear_long > 0:
                status['step3_model']['status'] = '✅'
                status['step3_model']['message'] = f'Model v{meta.get("version", "?")}'
            else:
                status['step3_model']['status'] = '⚠️'
                status['step3_model']['message'] = 'Model exists but metrics low'
            
            status['step3_model']['details'] = {
                'version': meta.get('version'),
                'timeframe': meta.get('timeframe'),
                'n_features': meta.get('n_features'),
                'n_train': meta.get('n_train_samples'),
                'n_test': meta.get('n_test_samples'),
                'r2_long': r2_long,
                'r2_short': r2_short,
                'spearman_long': spear_long,
                'spearman_short': meta.get('metrics_short', {}).get('ranking', {}).get('spearman_corr', 0)
            }
        except:
            pass
    
    return status


def render_pipeline_status():
    """Render pipeline status dashboard"""
    
    st.markdown("### 📊 Pipeline Status")
    
    status = get_pipeline_status()
    
    # Status cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div style="padding: 20px; border-radius: 10px; background: #1e2130; border-left: 4px solid {'#4ade80' if '✅' in status['step1_data']['status'] else '#fbbf24' if '⚠️' in status['step1_data']['status'] else '#ef4444'}">
            <h3 style="margin:0">{status['step1_data']['status']} Step 1: Data</h3>
            <p style="margin:5px 0; color: #9ca3af">{status['step1_data']['message']}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="padding: 20px; border-radius: 10px; background: #1e2130; border-left: 4px solid {'#4ade80' if '✅' in status['step2_labels']['status'] else '#fbbf24' if '⚠️' in status['step2_labels']['status'] else '#ef4444'}">
            <h3 style="margin:0">{status['step2_labels']['status']} Step 2: Labels</h3>
            <p style="margin:5px 0; color: #9ca3af">{status['step2_labels']['message']}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="padding: 20px; border-radius: 10px; background: #1e2130; border-left: 4px solid {'#4ade80' if '✅' in status['step3_model']['status'] else '#fbbf24' if '⚠️' in status['step3_model']['status'] else '#ef4444'}">
            <h3 style="margin:0">{status['step3_model']['status']} Step 3: Model</h3>
            <p style="margin:5px 0; color: #9ca3af">{status['step3_model']['message']}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Detailed status
    with st.expander("📋 Detailed Status", expanded=False):
        
        # Step 1 details
        st.markdown("#### 📊 Step 1: Data Details")
        details1 = status['step1_data']['details']
        if details1:
            for tf, data in details1.items():
                st.write(f"**{tf}**: {data['rows']:,} rows, {data['symbols']} symbols")
                st.write(f"  Range: {data['min_date']} → {data['max_date']}")
        else:
            st.warning("No data in training_data table")
        
        st.divider()
        
        # Step 2 details
        st.markdown("#### 🏷️ Step 2: Labels Details")
        details2 = status['step2_labels']['details']
        if details2:
            for tf, data in details2.items():
                st.write(f"**{tf}**: {data['rows']:,} labels, {data['symbols']} symbols")
                st.write(f"  Avg Score Long: {data['avg_score_long']:.6f}")
                st.write(f"  Avg Score Short: {data['avg_score_short']:.6f}")
                st.write(f"  Trailing exits: {data['trailing_exits']:,} | Time exits: {data['time_exits']:,}")
        else:
            st.warning("No labels in training_labels table")
        
        st.divider()
        
        # Step 3 details
        st.markdown("#### 🤖 Step 3: Model Details")
        details3 = status['step3_model']['details']
        if details3:
            c1, c2 = st.columns(2)
            c1.metric("Version", details3.get('version', 'N/A'))
            c2.metric("Features", details3.get('n_features', 0))
            
            c1, c2 = st.columns(2)
            c1.metric("Train Samples", f"{details3.get('n_train', 0):,}")
            c2.metric("Test Samples", f"{details3.get('n_test', 0):,}")
            
            st.markdown("**Metrics:**")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("R² Long", f"{details3.get('r2_long', 0):.4f}")
            col2.metric("R² Short", f"{details3.get('r2_short', 0):.4f}")
            col3.metric("Spearman Long", f"{details3.get('spearman_long', 0):.4f}")
            col4.metric("Spearman Short", f"{details3.get('spearman_short', 0):.4f}")
        else:
            st.warning("No model found")
    
    return status


__all__ = ['render_pipeline_status', 'get_pipeline_status']
