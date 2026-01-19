"""
🗄️ Training Data Explorer

Interactive interface for exploring training_data and training_labels
"""

import streamlit as st
import pandas as pd
from io import BytesIO
from database import get_connection


def get_training_stats() -> dict:
    """Get statistics for training tables"""
    stats = {
        'training_data': {'exists': False, 'total': 0, 'symbols': 0, 'timeframes': []},
        'training_labels': {'exists': False, 'total': 0, 'symbols': 0, 'timeframes': []}
    }
    
    conn = get_connection()
    if not conn:
        return stats
    
    try:
        cur = conn.cursor()
        
        for table in ['training_data', 'training_labels']:
            cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if cur.fetchone():
                stats[table]['exists'] = True
                
                cur.execute(f'SELECT COUNT(*), COUNT(DISTINCT symbol) FROM {table}')
                row = cur.fetchone()
                stats[table]['total'] = row[0]
                stats[table]['symbols'] = row[1]
                
                cur.execute(f'SELECT DISTINCT timeframe FROM {table}')
                stats[table]['timeframes'] = [r[0] for r in cur.fetchall()]
        
        conn.close()
    except Exception as e:
        st.error(f"Database error: {e}")
    
    return stats


def get_training_data_inventory() -> pd.DataFrame:
    """Get inventory of training data by symbol"""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        df = pd.read_sql_query('''
            SELECT 
                symbol,
                SUM(CASE WHEN timeframe = '15m' THEN 1 ELSE 0 END) as rows_15m,
                SUM(CASE WHEN timeframe = '1h' THEN 1 ELSE 0 END) as rows_1h,
                MIN(timestamp) as first_date,
                MAX(timestamp) as last_date,
                AVG(close) as avg_close,
                AVG(volume) as avg_volume,
                AVG(rsi) as avg_rsi,
                AVG(atr) as avg_atr
            FROM training_data
            GROUP BY symbol
            ORDER BY rows_15m + rows_1h DESC
        ''', conn)
        conn.close()
        return df
    except:
        conn.close()
        return pd.DataFrame()


def get_training_labels_inventory() -> pd.DataFrame:
    """Get inventory of training labels by symbol"""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        df = pd.read_sql_query('''
            SELECT 
                symbol,
                SUM(CASE WHEN timeframe = '15m' THEN 1 ELSE 0 END) as labels_15m,
                SUM(CASE WHEN timeframe = '1h' THEN 1 ELSE 0 END) as labels_1h,
                AVG(CASE WHEN timeframe = '15m' THEN score_long END) as avg_long_15m,
                AVG(CASE WHEN timeframe = '1h' THEN score_long END) as avg_long_1h,
                AVG(CASE WHEN timeframe = '15m' THEN score_short END) as avg_short_15m,
                AVG(CASE WHEN timeframe = '1h' THEN score_short END) as avg_short_1h,
                SUM(CASE WHEN exit_type_long = 'trailing' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pct_trailing
            FROM training_labels
            GROUP BY symbol
            ORDER BY labels_15m + labels_1h DESC
        ''', conn)
        conn.close()
        return df
    except:
        conn.close()
        return pd.DataFrame()


def get_sample_data(table: str, symbol: str = None, timeframe: str = None, limit: int = 100) -> pd.DataFrame:
    """Get sample rows from a table"""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        query = f'SELECT * FROM {table}'
        conditions = []
        if symbol:
            conditions.append(f"symbol LIKE '%{symbol}%'")
        if timeframe:
            conditions.append(f"timeframe = '{timeframe}'")
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += f' ORDER BY timestamp DESC LIMIT {limit}'
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except:
        conn.close()
        return pd.DataFrame()


def style_dataframe(df: pd.DataFrame) -> str:
    """Apply consistent styling to dataframe"""
    
    def style_numeric(val):
        try:
            if isinstance(val, (int, float)):
                if val > 0:
                    return 'color: #00ff88'
                elif val < 0:
                    return 'color: #ff4444'
            return 'color: #ffffff'
        except:
            return 'color: #ffffff'
    
    styled = df.style.applymap(
        style_numeric
    ).set_properties(**{
        'background-color': '#1a1a2e',
        'color': '#ffffff',
        'border-color': '#333355',
        'font-size': '11px'
    }).set_table_styles([
        {'selector': '', 'props': [('width', '100%'), ('overflow-x', 'auto')]},
        {'selector': 'th', 'props': [
            ('background-color', '#252540'),
            ('color', '#ffffff'),
            ('font-weight', 'bold'),
            ('padding', '6px 8px'),
            ('border-bottom', '2px solid #00ff88'),
            ('font-size', '11px'),
            ('text-align', 'center'),
            ('white-space', 'nowrap')
        ]},
        {'selector': 'td', 'props': [
            ('padding', '4px 6px'),
            ('border-bottom', '1px solid #333355'),
            ('text-align', 'right'),
            ('white-space', 'nowrap')
        ]}
    ]).format(precision=4)
    
    return styled.to_html(escape=False)


def render_training_explorer():
    """Render the Training Data Explorer"""
    
    st.markdown("### 🗄️ Training Data Explorer")
    st.caption("Explore training_data and training_labels tables")
    
    stats = get_training_stats()
    
    # Quick stats
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 Training Data", f"{stats['training_data']['total']:,}")
    col2.metric("🏷️ Training Labels", f"{stats['training_labels']['total']:,}")
    col3.metric("🪙 Symbols (Data)", stats['training_data']['symbols'])
    col4.metric("🪙 Symbols (Labels)", stats['training_labels']['symbols'])
    
    if not stats['training_data']['exists'] and not stats['training_labels']['exists']:
        st.warning("📭 No training data found. Run the pipeline first!")
        return
    
    st.divider()
    
    # Tabs for different views
    tab_data, tab_labels, tab_sample = st.tabs([
        "📊 Training Data Inventory",
        "🏷️ Training Labels Inventory", 
        "🔍 Sample Rows"
    ])
    
    # === TRAINING DATA INVENTORY ===
    with tab_data:
        if stats['training_data']['exists']:
            st.markdown("#### 📊 Training Data by Symbol")
            st.caption("OHLCV + 16 technical indicators per symbol")
            
            inv_df = get_training_data_inventory()
            
            if len(inv_df) > 0:
                # Summary metrics
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Rows", f"{inv_df['rows_15m'].sum() + inv_df['rows_1h'].sum():,}")
                m2.metric("Symbols", len(inv_df))
                m3.metric("With 15m Data", len(inv_df[inv_df['rows_15m'] > 0]))
                m4.metric("With 1h Data", len(inv_df[inv_df['rows_1h'] > 0]))
                
                # Display table
                display_df = pd.DataFrame({
                    '#': range(1, len(inv_df) + 1),
                    'Symbol': inv_df['symbol'].str.replace('/USDT:USDT', ''),
                    '15m Rows': inv_df['rows_15m'].apply(lambda x: f"{x:,}" if x > 0 else "-"),
                    '1h Rows': inv_df['rows_1h'].apply(lambda x: f"{x:,}" if x > 0 else "-"),
                    'First Date': inv_df['first_date'].str[:10],
                    'Last Date': inv_df['last_date'].str[:10],
                    'Avg Close': inv_df['avg_close'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "-"),
                    'Avg RSI': inv_df['avg_rsi'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "-"),
                    'Avg ATR': inv_df['avg_atr'].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "-"),
                })
                
                st.markdown(style_dataframe(display_df), unsafe_allow_html=True)
                
                # Download
                st.download_button(
                    "📥 Download CSV",
                    inv_df.to_csv(index=False).encode(),
                    "training_data_inventory.csv",
                    "text/csv"
                )
            else:
                st.info("No data available")
        else:
            st.warning("training_data table not found")
    
    # === TRAINING LABELS INVENTORY ===
    with tab_labels:
        if stats['training_labels']['exists']:
            st.markdown("#### 🏷️ Training Labels by Symbol")
            st.caption("Score long/short and exit stats per symbol")
            
            inv_df = get_training_labels_inventory()
            
            if len(inv_df) > 0:
                # Summary metrics
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Labels", f"{inv_df['labels_15m'].sum() + inv_df['labels_1h'].sum():,}")
                m2.metric("Symbols", len(inv_df))
                avg_trailing = inv_df['pct_trailing'].mean()
                m3.metric("Avg % Trailing Exit", f"{avg_trailing:.1f}%")
                avg_long = inv_df['avg_long_15m'].mean()
                m4.metric("Avg Score Long (15m)", f"{avg_long:.4f}" if pd.notna(avg_long) else "N/A")
                
                # Display table
                display_df = pd.DataFrame({
                    '#': range(1, len(inv_df) + 1),
                    'Symbol': inv_df['symbol'].str.replace('/USDT:USDT', ''),
                    '15m Labels': inv_df['labels_15m'].apply(lambda x: f"{x:,}" if x > 0 else "-"),
                    '1h Labels': inv_df['labels_1h'].apply(lambda x: f"{x:,}" if x > 0 else "-"),
                    'Avg Long 15m': inv_df['avg_long_15m'].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "-"),
                    'Avg Long 1h': inv_df['avg_long_1h'].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "-"),
                    'Avg Short 15m': inv_df['avg_short_15m'].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "-"),
                    '% Trailing': inv_df['pct_trailing'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "-"),
                })
                
                st.markdown(style_dataframe(display_df), unsafe_allow_html=True)
                
                # Download
                st.download_button(
                    "📥 Download CSV",
                    inv_df.to_csv(index=False).encode(),
                    "training_labels_inventory.csv",
                    "text/csv"
                )
            else:
                st.info("No labels available")
        else:
            st.warning("training_labels table not found")
    
    # === SAMPLE ROWS ===
    with tab_sample:
        st.markdown("#### 🔍 View Sample Rows")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            table = st.selectbox(
                "Table",
                ['training_data', 'training_labels'],
                key='sample_table'
            )
        
        with col2:
            symbol = st.text_input(
                "Symbol Filter (optional)",
                placeholder="e.g. BTC",
                key='sample_symbol'
            )
        
        with col3:
            timeframe = st.selectbox(
                "Timeframe",
                ['All', '15m', '1h'],
                key='sample_tf'
            )
        
        limit = st.slider("Rows to display", 10, 500, 100)
        
        if st.button("🔄 Load Sample", type="primary"):
            tf = None if timeframe == 'All' else timeframe
            sample_df = get_sample_data(table, symbol if symbol else None, tf, limit)
            
            if len(sample_df) > 0:
                st.success(f"Loaded {len(sample_df)} rows from {table}")
                
                # Show column info
                with st.expander(f"📋 Columns ({len(sample_df.columns)})", expanded=False):
                    st.write(list(sample_df.columns))
                
                # Format numeric columns
                for col in sample_df.select_dtypes(include=['float64']).columns:
                    sample_df[col] = sample_df[col].apply(lambda x: f"{x:.6f}" if pd.notna(x) else "")
                
                st.dataframe(sample_df, use_container_width=True, height=400)
                
                # Download
                st.download_button(
                    "📥 Download Sample CSV",
                    sample_df.to_csv(index=False).encode(),
                    f"sample_{table}.csv",
                    "text/csv"
                )
            else:
                st.warning("No data found with the specified filters")


__all__ = ['render_training_explorer']
