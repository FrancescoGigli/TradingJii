"""
📦 ML Dataset Export - Export joined training data

This module handles the export of complete ML training datasets
with features (indicators) + labels (targets) joined together.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import io

from database import (
    get_ml_training_dataset,
    get_available_symbols_for_labels,
    get_ml_labels_stats,
)


def render_export_dataset():
    """Render the Export Dataset section"""
    
    st.markdown("### 📦 Export ML Training Dataset")
    st.caption("Export complete dataset with features (indicators) + labels (targets)")
    
    # Get available symbols
    available_symbols = get_available_symbols_for_labels()
    
    if not available_symbols:
        st.warning("⚠️ No ML labels available. Generate labels first in the 'Generate' tab.")
        return
    
    # === CONFIGURATION ===
    col1, col2 = st.columns(2)
    
    with col1:
        # Symbol selection
        symbol_mode = st.radio(
            "Symbols",
            ["All", "Single", "Multiple"],
            key="export_symbol_mode",
            horizontal=True
        )
        
        selected_symbols = []
        if symbol_mode == "Single":
            single_symbol = st.selectbox(
                "Select Symbol",
                options=available_symbols,
                key="export_single_symbol"
            )
            selected_symbols = [single_symbol] if single_symbol else []
        elif symbol_mode == "Multiple":
            selected_symbols = st.multiselect(
                "Select Symbols",
                options=available_symbols,
                default=available_symbols[:5] if len(available_symbols) > 5 else available_symbols,
                key="export_multi_symbols"
            )
    
    with col2:
        # Timeframe selection
        timeframe = st.selectbox(
            "Timeframe",
            options=["All", "15m", "1h"],
            index=0,
            key="export_timeframe"
        )
        
        # Limit
        limit_enabled = st.checkbox("Limit rows", value=False, key="export_limit_enabled")
        if limit_enabled:
            limit = st.number_input("Max rows", min_value=1000, max_value=10000000, 
                                    value=100000, step=10000, key="export_limit")
        else:
            limit = None
    
    st.divider()
    
    # === PREVIEW BUTTON ===
    if st.button("🔍 Preview Dataset", type="primary", use_container_width=True, key="preview_btn"):
        with st.spinner("Loading dataset..."):
            # Get data
            symbol = selected_symbols[0] if symbol_mode == "Single" and selected_symbols else None
            symbols = selected_symbols if symbol_mode == "Multiple" else None
            tf = timeframe if timeframe != "All" else None
            
            df, stats, errors = get_ml_training_dataset(
                symbol=symbol,
                timeframe=tf,
                symbols=symbols,
                limit=limit
            )
            
            # Store in session state for download
            st.session_state['export_df'] = df
            st.session_state['export_stats'] = stats
            st.session_state['export_errors'] = errors
    
    # === SHOW RESULTS ===
    if 'export_df' in st.session_state and len(st.session_state['export_df']) > 0:
        df = st.session_state['export_df']
        stats = st.session_state['export_stats']
        errors = st.session_state['export_errors']
        
        # Stats metrics
        st.markdown("#### 📊 Dataset Statistics")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📊 Total Rows", f"{stats.get('total_rows', 0):,}")
        m2.metric("🪙 Symbols", stats.get('symbols', 0))
        m3.metric("📈 Features", stats.get('features_count', 0))
        m4.metric("🎯 Labels", stats.get('labels_count', 0))
        
        m5, m6, m7, m8 = st.columns(4)
        m5.metric("📅 From", stats.get('date_from', 'N/A'))
        m6.metric("📅 To", stats.get('date_to', 'N/A'))
        m7.metric("📊 Total Columns", stats.get('total_columns', 0))
        m8.metric("⚠️ Null %", f"{stats.get('null_percentage', 0):.2f}%")
        
        # Label distribution
        if 'avg_score_long' in stats:
            st.markdown("#### 🎯 Label Distribution")
            l1, l2, l3, l4 = st.columns(4)
            l1.metric("Avg Score LONG", f"{stats.get('avg_score_long', 0)*100:.3f}%")
            l2.metric("% Positive LONG", f"{stats.get('pct_positive_long', 0):.1f}%")
            l3.metric("% Negative LONG", f"{stats.get('pct_negative_long', 0):.1f}%")
            l4.metric("Avg Score SHORT", f"{stats.get('avg_score_short', 0)*100:.3f}%")
        
        # Warnings/Errors
        if errors:
            with st.expander(f"⚠️ {len(errors)} Warnings", expanded=False):
                for err in errors:
                    st.warning(err)
        
        # Data quality checks
        st.markdown("#### ✅ Data Quality Checks")
        
        checks = []
        if stats.get('total_rows', 0) > 0:
            checks.append(("✅", "Has data", f"{stats['total_rows']:,} rows"))
        else:
            checks.append(("❌", "No data", "Dataset is empty"))
        
        if stats.get('null_percentage', 100) < 5:
            checks.append(("✅", "Low null values", f"{stats.get('null_percentage', 0):.2f}%"))
        elif stats.get('null_percentage', 100) < 20:
            checks.append(("⚠️", "Some null values", f"{stats.get('null_percentage', 0):.2f}%"))
        else:
            checks.append(("❌", "High null values", f"{stats.get('null_percentage', 0):.2f}%"))
        
        if stats.get('features_count', 0) > 10:
            checks.append(("✅", "Good feature count", f"{stats.get('features_count', 0)} features"))
        else:
            checks.append(("⚠️", "Low feature count", f"{stats.get('features_count', 0)} features"))
        
        for icon, check, detail in checks:
            st.write(f"{icon} **{check}**: {detail}")
        
        # Preview data
        st.markdown("#### 👀 Data Preview (first 100 rows)")
        
        # Show column groups
        feature_cols = [c for c in df.columns if c not in ['timestamp', 'symbol', 'timeframe', 
                       'open', 'high', 'low', 'close', 'volume',
                       'score_long', 'score_short', 'realized_return_long', 'realized_return_short',
                       'mfe_long', 'mae_long', 'mfe_short', 'mae_short',
                       'bars_held_long', 'bars_held_short', 'exit_type_long', 'exit_type_short',
                       'trailing_stop_pct', 'max_bars', 'time_penalty_lambda', 'trading_cost']]
        
        with st.expander(f"📊 Feature Columns ({len(feature_cols)})", expanded=False):
            st.write(", ".join(feature_cols[:50]))
            if len(feature_cols) > 50:
                st.write(f"... and {len(feature_cols) - 50} more")
        
        st.dataframe(df.head(100), use_container_width=True)
        
        # === DOWNLOAD BUTTONS ===
        st.markdown("#### 📥 Download")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV download
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
            filename_base = f"ml_dataset_{stats.get('symbols', 'all')}sym_{stats.get('total_rows', 0)}rows_{timestamp_str}"
            
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name=f"{filename_base}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # Parquet download (if pyarrow available)
            try:
                parquet_buffer = io.BytesIO()
                df.to_parquet(parquet_buffer, index=False)
                parquet_data = parquet_buffer.getvalue()
                
                st.download_button(
                    label="📥 Download Parquet",
                    data=parquet_data,
                    file_name=f"{filename_base}.parquet",
                    mime="application/octet-stream",
                    use_container_width=True
                )
            except Exception:
                st.info("💡 Parquet export requires pyarrow package")
        
        # Per-symbol breakdown
        if 'rows_per_symbol' in stats and len(stats['rows_per_symbol']) > 1:
            st.markdown("#### 🪙 Rows per Symbol")
            
            symbol_df = pd.DataFrame([
                {'Symbol': sym.replace('/USDT:USDT', ''), 'Rows': count}
                for sym, count in sorted(stats['rows_per_symbol'].items(), 
                                         key=lambda x: x[1], reverse=True)
            ])
            
            st.dataframe(symbol_df, use_container_width=True, hide_index=True)
    
    elif 'export_stats' in st.session_state and st.session_state['export_stats'].get('error'):
        st.error(f"❌ {st.session_state['export_stats']['error']}")
