"""
🗄️ ML Labels Database Explorer

This module provides an interactive SQL query interface
for exploring ML training labels stored in the database.
"""

import streamlit as st
import pandas as pd
from io import BytesIO

from database import (
    execute_custom_query,
    get_ml_labels_table_schema,
    get_available_symbols_for_labels,
    get_ml_labels_full,
    get_ml_labels_stats,
    get_ml_labels_inventory,
    ML_LABELS_EXAMPLE_QUERIES
)


def render_database_explorer():
    """Render the Database Explorer section"""
    
    st.markdown("### 🗄️ Database Explorer")
    st.caption("Query and explore ML training labels with SQL")
    
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
        
        # Display table
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=400
        )
        
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
    with st.expander("📋 Table Schema", expanded=False):
        schema = get_ml_labels_table_schema()
        
        if schema:
            schema_df = pd.DataFrame(schema)
            st.dataframe(
                schema_df[['name', 'type', 'notnull']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Schema not available")
    
    st.divider()
    
    # === EXAMPLE QUERIES ===
    st.markdown("#### 🔍 Example Queries")
    st.caption("Click to load a pre-built query")
    
    # Query selector
    query_names = list(ML_LABELS_EXAMPLE_QUERIES.keys())
    
    cols = st.columns(3)
    
    selected_query = None
    
    for i, name in enumerate(query_names):
        col_idx = i % 3
        with cols[col_idx]:
            if st.button(name, key=f"example_query_{i}", use_container_width=True):
                selected_query = ML_LABELS_EXAMPLE_QUERIES[name]
                st.session_state['current_query'] = selected_query
    
    st.divider()
    
    # === CUSTOM QUERY ===
    st.markdown("#### 💻 Custom SQL Query")
    
    # Get query from session state or use default
    default_query = st.session_state.get('current_query', """SELECT 
    timestamp,
    symbol,
    timeframe,
    ROUND(close, 2) as close,
    ROUND(score_long * 100, 4) as score_long_pct,
    ROUND(score_short * 100, 4) as score_short_pct,
    exit_type_long
FROM ml_training_labels
ORDER BY timestamp DESC
LIMIT 100""")
    
    query = st.text_area(
        "Enter SQL Query:",
        value=default_query,
        height=200,
        key="sql_query_input",
        help="Only SELECT queries are allowed. Query will be auto-limited to 1000 rows."
    )
    
    # Query options
    col_opt1, col_opt2 = st.columns(2)
    
    with col_opt1:
        max_rows = st.selectbox(
            "Max Rows",
            [100, 500, 1000, 5000],
            index=2,
            key="query_max_rows"
        )
    
    with col_opt2:
        # Execute button
        execute_btn = st.button("🚀 Execute Query", type="primary", use_container_width=True, key="execute_query_btn")
    
    # Execute query
    if execute_btn or st.session_state.get('last_query_result') is not None:
        
        if execute_btn:
            with st.spinner("Executing query..."):
                result_df, error = execute_custom_query(query, limit=max_rows)
                
                if error:
                    st.error(f"❌ Query Error: {error}")
                    st.session_state['last_query_result'] = None
                else:
                    st.session_state['last_query_result'] = result_df
                    st.session_state['last_query'] = query
        
        result_df = st.session_state.get('last_query_result')
        
        if result_df is not None and len(result_df) > 0:
            st.success(f"✅ Query returned **{len(result_df):,}** rows")
            
            # Display results
            st.dataframe(
                result_df,
                use_container_width=True,
                hide_index=True,
                height=400
            )
            
            # Download button
            csv_buffer = BytesIO()
            result_df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            
            st.download_button(
                label="📥 Download Results (CSV)",
                data=csv_data,
                file_name=f"query_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        elif result_df is not None:
            st.info("Query returned 0 rows")
    
    st.divider()
    
    # === QUICK BROWSE ===
    st.markdown("#### 🔎 Quick Browse")
    st.caption("Browse labels by symbol and timeframe")
    
    browse_col1, browse_col2, browse_col3 = st.columns(3)
    
    with browse_col1:
        available_symbols = get_available_symbols_for_labels()
        browse_symbol = st.selectbox(
            "Symbol",
            ["All"] + available_symbols,
            format_func=lambda x: x.replace('/USDT:USDT', '') if x != "All" else "All Symbols",
            key="browse_symbol"
        )
    
    with browse_col2:
        browse_timeframe = st.selectbox(
            "Timeframe",
            ["All", "15m", "1h"],
            key="browse_timeframe"
        )
    
    with browse_col3:
        browse_limit = st.selectbox(
            "Rows",
            [100, 500, 1000, 5000],
            index=1,
            key="browse_limit"
        )
    
    if st.button("🔍 Browse", key="browse_btn"):
        
        symbol_filter = None if browse_symbol == "All" else browse_symbol
        tf_filter = None if browse_timeframe == "All" else browse_timeframe
        
        with st.spinner("Loading data..."):
            browse_df = get_ml_labels_full(
                symbol=symbol_filter,
                timeframe=tf_filter,
                limit=browse_limit
            )
        
        if browse_df is not None and len(browse_df) > 0:
            st.success(f"Found **{len(browse_df):,}** labels")
            
            # Format for display
            display_df = browse_df.copy()
            
            # Select columns to show
            display_cols = [
                'timestamp', 'symbol', 'timeframe', 'close',
                'score_long', 'score_short',
                'realized_return_long', 'realized_return_short',
                'mfe_long', 'mae_long',
                'bars_held_long', 'exit_type_long'
            ]
            
            available_cols = [c for c in display_cols if c in display_df.columns]
            display_df = display_df[available_cols]
            
            # Format numeric columns
            for col in ['score_long', 'score_short', 'realized_return_long', 'realized_return_short', 'mfe_long', 'mae_long']:
                if col in display_df.columns:
                    display_df[col] = (display_df[col] * 100).round(4)
            
            if 'close' in display_df.columns:
                display_df['close'] = display_df['close'].round(2)
            
            if 'symbol' in display_df.columns:
                display_df['symbol'] = display_df['symbol'].str.replace('/USDT:USDT', '')
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                height=400
            )
            
            # Download
            csv_buffer = BytesIO()
            browse_df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            
            st.download_button(
                label="📥 Download Full Data (CSV)",
                data=csv_data,
                file_name=f"labels_{browse_symbol}_{browse_timeframe}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_browse"
            )
        else:
            st.info("No data found for selected filters")
    
    # === SQL REFERENCE ===
    st.divider()
    
    with st.expander("📚 SQL Reference", expanded=False):
        st.markdown("""
        ### Available Columns
        
        | Column | Type | Description |
        |--------|------|-------------|
        | `id` | INTEGER | Primary key |
        | `symbol` | TEXT | Trading pair (e.g., 'BTC/USDT:USDT') |
        | `timeframe` | TEXT | '15m' or '1h' |
        | `timestamp` | TEXT | Candle timestamp |
        | `open`, `high`, `low`, `close` | REAL | OHLC prices |
        | `volume` | REAL | Trading volume |
        | `score_long` | REAL | LONG score (main ML target) |
        | `score_short` | REAL | SHORT score (main ML target) |
        | `realized_return_long/short` | REAL | Actual return % |
        | `mfe_long/short` | REAL | Max Favorable Excursion |
        | `mae_long/short` | REAL | Max Adverse Excursion |
        | `bars_held_long/short` | INTEGER | Bars until exit |
        | `exit_type_long/short` | TEXT | 'trailing' or 'time' |
        | `trailing_stop_pct` | REAL | Config: trailing stop % |
        | `max_bars` | INTEGER | Config: max bars |
        | `time_penalty_lambda` | REAL | Config: λ coefficient |
        | `trading_cost` | REAL | Config: trading cost |
        | `generated_at` | TEXT | Generation timestamp |
        
        ### Example Queries
        
        ```sql
        -- Count labels per symbol
        SELECT symbol, COUNT(*) as count 
        FROM ml_training_labels 
        GROUP BY symbol;
        
        -- Average score by exit type
        SELECT exit_type_long, AVG(score_long) 
        FROM ml_training_labels 
        GROUP BY exit_type_long;
        
        -- Best trades
        SELECT * FROM ml_training_labels 
        WHERE score_long > 0.02 
        ORDER BY score_long DESC;
        ```
        """)
