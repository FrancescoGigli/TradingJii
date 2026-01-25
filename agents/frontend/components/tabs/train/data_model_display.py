"""
📋 Data Model Display Component

Reusable component to show input/output data model information for each tab:
- Table/view name
- Exists status
- Feature count and names
- Row count
- Timeframe
- Date range
"""

import streamlit as st
from typing import Dict, List, Optional
from database import get_connection


# Dark theme CSS for expanders and content
DARK_THEME_CSS = """
<style>
    /* Dark theme for expander content */
    .stExpander > div[data-testid="stExpanderContent"] {
        background-color: #0d1117 !important;
    }
    .stExpander > div[data-testid="stExpanderContent"] > div {
        background-color: #0d1117 !important;
    }
    /* Feature/label columns with dark background */
    .feature-column {
        background: #1e2130;
        padding: 4px 8px;
        border-radius: 4px;
        margin: 2px 0;
        color: #e0e0ff;
    }
    .feature-column code {
        background: #2d3748;
        padding: 2px 6px;
        border-radius: 4px;
        color: #00ffff;
    }
</style>
"""


def _render_columns_html(columns: List[str]) -> str:
    """
    Render a list of column names as styled HTML grid with dark theme.
    
    Args:
        columns: List of column names
    
    Returns:
        HTML string with styled column badges
    """
    if not columns:
        return ""
    
    # Create 3-column grid
    items_html = ""
    for col in columns:
        items_html += f"""
        <div style="
            display: inline-block;
            background: #2d3748;
            color: #00ffff;
            padding: 4px 10px;
            border-radius: 6px;
            margin: 4px;
            font-family: monospace;
            font-size: 0.85em;
        ">• {col}</div>
        """
    
    return f"""
    <div style="
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        padding: 10px;
        background: #0d1117;
        border-radius: 8px;
    ">
        {items_html}
    </div>
    """


def get_table_info(table_name: str) -> Dict:
    """
    Get comprehensive info about a table or view.
    
    Args:
        table_name: Name of table or view
    
    Returns:
        Dictionary with table info
    """
    conn = get_connection()
    if not conn:
        return {'exists': False, 'error': 'No database connection'}
    
    try:
        cur = conn.cursor()
        
        # Check if table/view exists
        cur.execute("""
            SELECT type FROM sqlite_master 
            WHERE name=? AND type IN ('table', 'view')
        """, (table_name,))
        result = cur.fetchone()
        
        if not result:
            return {
                'exists': False,
                'name': table_name,
                'error': f'Table/view {table_name} not found'
            }
        
        table_type = result[0]
        
        # Get columns
        cur.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cur.fetchall()]
        
        # Categorize columns
        metadata_cols = {'id', 'symbol', 'timeframe', 'timestamp', 'fetched_at', 'interpolated'}
        label_cols = {c for c in columns if any(x in c.lower() for x in 
                      ['score', 'return', 'mfe', 'mae', 'bars_held', 'exit_type', 'atr_pct'])}
        feature_cols = [c for c in columns if c not in metadata_cols and c not in label_cols]
        
        # Get row count
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cur.fetchone()[0]
        except Exception:
            row_count = -1
        
        # Get timeframe and date range (if applicable columns exist)
        timeframes = []
        date_range = {'min': None, 'max': None}
        
        if 'timeframe' in columns:
            try:
                cur.execute(f"SELECT DISTINCT timeframe FROM {table_name}")
                timeframes = [row[0] for row in cur.fetchall()]
            except Exception:
                pass
        
        if 'timestamp' in columns:
            try:
                cur.execute(f"SELECT MIN(timestamp), MAX(timestamp) FROM {table_name}")
                row = cur.fetchone()
                if row:
                    date_range['min'] = row[0]
                    date_range['max'] = row[1]
            except Exception:
                pass
        
        # Get symbol count
        symbol_count = 0
        if 'symbol' in columns:
            try:
                cur.execute(f"SELECT COUNT(DISTINCT symbol) FROM {table_name}")
                symbol_count = cur.fetchone()[0]
            except Exception:
                pass
        
        return {
            'exists': True,
            'name': table_name,
            'type': table_type,
            'total_columns': len(columns),
            'columns': columns,
            'feature_columns': feature_cols,
            'feature_count': len(feature_cols),
            'label_columns': list(label_cols),
            'label_count': len(label_cols),
            'row_count': row_count,
            'symbol_count': symbol_count,
            'timeframes': timeframes,
            'date_range': date_range
        }
    except Exception as e:
        return {'exists': False, 'name': table_name, 'error': str(e)}
    finally:
        conn.close()


def render_data_model_card(
    title: str,
    table_name: str,
    direction: str = "INPUT",
    color: str = "#4a90d9"
) -> Dict:
    """
    Render a styled card showing data model information.
    
    Args:
        title: Card title (e.g., "Input Data")
        table_name: Name of table or view to inspect
        direction: "INPUT" or "OUTPUT"
        color: Border color for the card
    
    Returns:
        Table info dictionary
    """
    info = get_table_info(table_name)
    
    # Status indicator
    if info['exists']:
        status = "✅"
        status_color = "#4ade80"
    else:
        status = "❌"
        status_color = "#ef4444"
    
    # Card HTML
    st.markdown(f"""
    <div style="
        padding: 15px; 
        border-radius: 8px; 
        background: #1e2130; 
        border-left: 4px solid {color};
        margin-bottom: 10px;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h4 style="margin: 0; color: {color};">
                {direction}: {title}
            </h4>
            <span style="color: {status_color}; font-size: 1.2em;">{status}</span>
        </div>
        <div style="color: #9ca3af; font-size: 0.9em; margin-top: 5px;">
            📊 <code style="background: #2d3748; padding: 2px 6px; border-radius: 4px;">{table_name}</code>
            <span style="margin-left: 10px;">({info.get('type', 'unknown')})</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if info['exists']:
        # Metrics row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Rows", f"{info['row_count']:,}" if info['row_count'] >= 0 else "N/A")
        with col2:
            st.metric("Symbols", f"{info['symbol_count']:,}" if info['symbol_count'] > 0 else "N/A")
        with col3:
            st.metric("Features", info['feature_count'])
        with col4:
            tf_str = ", ".join(info['timeframes']) if info['timeframes'] else "N/A"
            st.metric("Timeframes", tf_str)
        
        # Date range
        if info['date_range']['min']:
            st.caption(f"📅 Date range: `{info['date_range']['min'][:19]}` → `{info['date_range']['max'][:19]}`")
        
        # Features list (collapsible)
        with st.expander(f"📋 Feature columns ({info['feature_count']})", expanded=False):
            if info['feature_columns']:
                # Use HTML with dark theme styling
                features_html = _render_columns_html(sorted(info['feature_columns']))
                st.markdown(features_html, unsafe_allow_html=True)
            else:
                st.info("No feature columns found")
        
        # Label columns (if any)
        if info['label_count'] > 0:
            with st.expander(f"🏷️ Label columns ({info['label_count']})", expanded=False):
                labels_html = _render_columns_html(sorted(info['label_columns']))
                st.markdown(labels_html, unsafe_allow_html=True)
    else:
        st.error(f"⚠️ {info.get('error', 'Table not found')}")
    
    return info


def render_pipeline_io_section(
    step_name: str,
    input_table: Optional[str] = None,
    output_table: Optional[str] = None,
    input_title: str = "Input Data",
    output_title: str = "Output Data"
):
    """
    Render a complete input/output section for a pipeline step.
    
    Args:
        step_name: Name of the step (for header)
        input_table: Name of input table/view (or None)
        output_table: Name of output table/view (or None)
        input_title: Display title for input
        output_title: Display title for output
    """
    # Inject dark theme CSS
    st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)
    
    with st.expander(f"📊 Data Model: {step_name}", expanded=False):
        st.markdown("---")
        
        if input_table and output_table:
            col1, col2 = st.columns(2)
            
            with col1:
                render_data_model_card(
                    title=input_title,
                    table_name=input_table,
                    direction="📥 INPUT",
                    color="#60a5fa"  # Blue
                )
            
            with col2:
                render_data_model_card(
                    title=output_title,
                    table_name=output_table,
                    direction="📤 OUTPUT",
                    color="#34d399"  # Green
                )
        elif input_table:
            render_data_model_card(
                title=input_title,
                table_name=input_table,
                direction="📥 INPUT",
                color="#60a5fa"
            )
        elif output_table:
            render_data_model_card(
                title=output_title,
                table_name=output_table,
                direction="📤 OUTPUT",
                color="#34d399"
            )
        
        st.markdown("---")


# Predefined configs for each step
STEP_CONFIGS = {
    'step1_data': {
        'name': 'Step 1: Data Download',
        'input_table': None,  # Input is external API (Bybit), not a database table
        'input_title': 'Bybit API (external)',
        'output_table': 'training_data',
        'output_title': 'Training Data (OHLCV + indicators)'
    },
    'step2_labeling': {
        'name': 'Step 2: Labeling',
        'input_table': 'training_data',
        'input_title': 'Training Data',
        'output_table': 'training_labels',
        'output_title': 'Training Labels'
    },
    'step3_training': {
        'name': 'Step 3: Training',
        'input_table': 'v_xgb_training',
        'input_title': 'XGB Training View (features + labels)',
        'output_table': None,  # Output is model files, not a database table
        'output_title': 'Trained Models (files)'
    },
    'step4_models': {
        'name': 'Step 4: Model Evaluation',
        'input_table': 'v_xgb_training',
        'input_title': 'XGB Training View',
        'output_table': None,  # Output is predictions displayed in UI
        'output_title': 'Model Predictions'
    }
}


def render_step_data_model(step_key: str):
    """
    Render data model section for a specific step using predefined config.
    
    Args:
        step_key: One of 'step1_data', 'step2_labeling', 'step3_training', 'step4_models'
    """
    config = STEP_CONFIGS.get(step_key)
    if not config:
        st.error(f"Unknown step: {step_key}")
        return
    
    render_pipeline_io_section(
        step_name=config['name'],
        input_table=config['input_table'],
        output_table=config['output_table'],
        input_title=config['input_title'],
        output_title=config['output_title']
    )


__all__ = [
    'get_table_info',
    'render_data_model_card',
    'render_pipeline_io_section',
    'render_step_data_model',
    'STEP_CONFIGS'
]
