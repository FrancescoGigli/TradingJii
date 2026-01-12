"""
🗄️ ML Labels Database Explorer

This module provides an interactive interface
for exploring ML training labels stored in the database.
"""

import streamlit as st
import pandas as pd
from io import BytesIO

from database import (
    get_ml_labels_table_schema,
    get_ml_labels_stats,
    get_ml_labels_inventory,
)


def render_database_explorer():
    """Render the Database Explorer section"""
    
    st.markdown("### 🗄️ Database Explorer")
    st.caption("Explore ML training labels stored in the database")
    
    # Check if we have data
    db_stats = get_ml_labels_stats()
    
    if not db_stats.get('exists') or db_stats.get('empty'):
        st.warning("📭 No labels in database. Generate labels first using the 'Generate' tab.")
        return
    
    # === QUICK STATS ===
    st.markdown("#### 📊 Database Overview")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📊 Total Labels", f"{db_stats.get('total_labels', 0):,}")
    m2.metric("🪙 Symbols", db_stats.get('symbols', 0))
    m3.metric("⏱️ Timeframes", db_stats.get('timeframes', 0))
    m4.metric("📅 Last Generated", db_stats.get('last_generated', 'N/A')[:10] if db_stats.get('last_generated') else 'N/A')
    
    st.divider()
    
    # === LABELS INVENTORY TABLE ===
    st.markdown("#### 🗂️ Labels Inventory")
    st.caption("Labels per coin by timeframe, ordered by volume rank")
    
    inventory = get_ml_labels_inventory()
    
    if inventory:
        # Convert to DataFrame for display
        inv_df = pd.DataFrame(inventory)
        
        # Format for display
        display_df = pd.DataFrame({
            'Rank': inv_df['rank'],
            'Symbol': inv_df['symbol'].str.replace('/USDT:USDT', ''),
            '15m Labels': inv_df['labels_15m'].apply(lambda x: f"{x:,}" if x > 0 else "-"),
            '1h Labels': inv_df['labels_1h'].apply(lambda x: f"{x:,}" if x > 0 else "-"),
            'Avg Score 15m': inv_df['avg_score_long_15m'].apply(lambda x: f"{x:.3f}%" if pd.notna(x) else "-"),
            'Avg Score 1h': inv_df['avg_score_long_1h'].apply(lambda x: f"{x:.3f}%" if pd.notna(x) else "-"),
            '% Positive 15m': inv_df['pct_positive_15m'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "-"),
            '% Positive 1h': inv_df['pct_positive_1h'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "-"),
        })
        
        # Summary metrics
        total_labels = sum(inv_df['labels_15m']) + sum(inv_df['labels_1h'])
        symbols_with_15m = sum(inv_df['labels_15m'] > 0)
        symbols_with_1h = sum(inv_df['labels_1h'] > 0)
        
        sm1, sm2, sm3 = st.columns(3)
        sm1.metric("📊 Total Labels", f"{total_labels:,}")
        sm2.metric("🕒 Symbols with 15m", symbols_with_15m)
        sm3.metric("⏰ Symbols with 1h", symbols_with_1h)
        
        # Apply styled visualization - Split into 2 columns
        def style_inventory_table(df):
            def style_number_cell(val):
                if isinstance(val, str) and val != '-':
                    return 'color: #00ccff'
                return 'color: #666666'
            
            def style_score_cell(val):
                if isinstance(val, str) and val != '-':
                    # Parse the value to check if positive or negative
                    try:
                        num = float(val.replace('%', ''))
                        if num > 0:
                            return 'color: #00ff88; font-weight: bold'
                        elif num < 0:
                            return 'color: #ff4444; font-weight: bold'
                    except:
                        pass
                    return 'color: #00ccff'
                return 'color: #666666'
            
            return df.style.applymap(
                style_number_cell,
                subset=['15m Labels', '1h Labels']
            ).applymap(
                style_score_cell,
                subset=['Avg Score 15m', 'Avg Score 1h', '% Positive 15m', '% Positive 1h']
            ).set_properties(**{
                'background-color': '#1a1a2e',
                'color': '#ffffff',
                'border-color': '#333355',
                'font-size': '12px'
            }).set_table_styles([
                {'selector': '', 'props': [
                    ('width', '100%'),
                    ('table-layout', 'fixed')
                ]},
                {'selector': 'th', 'props': [
                    ('background-color', '#252540'),
                    ('color', '#ffffff'),
                    ('font-weight', 'bold'),
                    ('padding', '6px 8px'),
                    ('border-bottom', '2px solid #00ff88'),
                    ('font-size', '12px'),
                    ('text-align', 'center')
                ]},
                {'selector': 'td', 'props': [
                    ('padding', '5px 8px'),
                    ('border-bottom', '1px solid #333355'),
                    ('text-align', 'center')
                ]}
            ])
        
        # Split into 2 columns of 50 rows each
        half = len(display_df) // 2
        df_left = display_df.iloc[:half].reset_index(drop=True)
        df_right = display_df.iloc[half:].reset_index(drop=True)
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown(f"**Coins 1-{half}**")
            st.markdown(style_inventory_table(df_left).to_html(escape=False), unsafe_allow_html=True)
        
        with col_right:
            st.markdown(f"**Coins {half+1}-{len(display_df)}**")
            st.markdown(style_inventory_table(df_right).to_html(escape=False), unsafe_allow_html=True)
        
        # Download inventory
        csv_buffer = BytesIO()
        inv_df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()
        
        st.download_button(
            label="📥 Download Inventory (CSV)",
            data=csv_data,
            file_name=f"ml_labels_inventory_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key="download_inventory"
        )
    else:
        st.info("📭 No labels inventory available")
    
    st.divider()
    
    # === SCHEMA INFO ===
    with st.expander("📋 ML Labels Table Schema (25 columns)", expanded=False):
        st.caption("Schema of the ml_labels table - contains labels ONLY (no features/indicators)")
        
        schema = get_ml_labels_table_schema()
        
        if schema:
            schema_df = pd.DataFrame(schema)
            display_schema = schema_df[['name', 'type', 'notnull']].copy()
            display_schema['notnull'] = display_schema['notnull'].apply(lambda x: '✅' if x else '❌')
            display_schema.columns = ['Column Name', 'Data Type', 'Required']
            
            # Style schema table
            def style_schema(df):
                def style_type(val):
                    if 'REAL' in str(val):
                        return 'color: #00ccff'
                    elif 'INTEGER' in str(val):
                        return 'color: #ffaa00'
                    elif 'TEXT' in str(val):
                        return 'color: #00ff88'
                    return 'color: #ffffff'
                
                return df.style.applymap(
                    style_type,
                    subset=['Data Type']
                ).set_properties(**{
                    'background-color': '#1a1a2e',
                    'color': '#ffffff',
                    'border-color': '#333355',
                    'font-size': '12px'
                }).set_table_styles([
                    {'selector': '', 'props': [('width', '100%')]},
                    {'selector': 'th', 'props': [
                        ('background-color', '#252540'),
                        ('color', '#ffffff'),
                        ('font-weight', 'bold'),
                        ('padding', '8px'),
                        ('border-bottom', '2px solid #00ff88')
                    ]},
                    {'selector': 'td', 'props': [
                        ('padding', '6px 10px'),
                        ('border-bottom', '1px solid #333355')
                    ]}
                ])
            
            st.markdown(style_schema(display_schema).to_html(escape=False), unsafe_allow_html=True)
            
            # Quick summary
            st.markdown(f"""
            **📊 Schema Summary:**
            - Total columns: **{len(schema_df)}**
            - REAL (numeric): **{len(schema_df[schema_df['type'] == 'REAL'])}** (scores, MFE/MAE, etc.)
            - INTEGER: **{len(schema_df[schema_df['type'] == 'INTEGER'])}** (bars_held, etc.)
            - TEXT: **{len(schema_df[schema_df['type'] == 'TEXT'])}** (symbol, timeframe, exit_type)
            
            ⚠️ **Note:** This is the labels-only schema. The **Export tab** joins labels with 64 indicators/features 
            from historical_data, resulting in ~88 total columns.
            """)
        else:
            st.info("Schema not available")
