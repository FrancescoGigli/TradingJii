"""
📋 Labeling Table Module

Labels table preview with first 50 + last 50 rows display in MARKDOWN format.
Uses v_xgb_training VIEW to show OHLCV + indicators + labels together.
"""

import streamlit as st
import pandas as pd
from typing import Optional
from database import get_connection


def get_labels_for_table(symbol: str, timeframe: str, limit: int = 10000) -> pd.DataFrame:
    """
    Get labels data from v_xgb_training VIEW (includes OHLCV + indicators + labels).
    
    Args:
        symbol: Symbol to filter
        timeframe: Timeframe ('15m' or '1h')
        limit: Maximum rows to fetch
    
    Returns:
        DataFrame with complete data (OHLCV + indicators + labels)
    """
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        # Use v_xgb_training VIEW - has everything joined!
        # SELECT ALL 24 columns from the VIEW
        query = '''
            SELECT 
                symbol,
                timeframe,
                timestamp,
                open, high, low, close, volume,
                rsi, atr, macd,
                score_long,
                score_short,
                realized_return_long,
                realized_return_short,
                mfe_long,
                mfe_short,
                mae_long,
                mae_short,
                bars_held_long,
                bars_held_short,
                exit_type_long,
                exit_type_short,
                atr_pct
            FROM v_xgb_training
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp ASC
            LIMIT ?
        '''
        
        df = pd.read_sql_query(query, conn, params=(symbol, timeframe, limit))
        
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        return df
        
    except Exception as e:
        # Fallback to training_labels if VIEW doesn't exist
        st.warning(f"VIEW not found, using training_labels: {e}")
        try:
            query = '''
                SELECT 
                    timestamp,
                    score_long,
                    score_short,
                    realized_return_long,
                    realized_return_short,
                    exit_type_long,
                    exit_type_short,
                    bars_held_long,
                    bars_held_short,
                    mae_long,
                    mae_short,
                    mfe_long,
                    mfe_short,
                    atr_pct
                FROM training_labels
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp ASC
                LIMIT ?
            '''
            df = pd.read_sql_query(query, conn, params=(symbol, timeframe, limit))
            if len(df) > 0:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        except:
            return pd.DataFrame()
    finally:
        conn.close()


def df_to_markdown_table(df: pd.DataFrame) -> str:
    """
    Convert DataFrame to markdown table string.
    
    Args:
        df: DataFrame to convert
    
    Returns:
        Markdown table string
    """
    if df is None or len(df) == 0:
        return ""
    
    # Build header
    headers = "| " + " | ".join(df.columns) + " |"
    separator = "| " + " | ".join(["---" for _ in df.columns]) + " |"
    
    # Build rows
    rows = []
    for _, row in df.iterrows():
        row_str = "| " + " | ".join([str(v) for v in row.values]) + " |"
        rows.append(row_str)
    
    return "\n".join([headers, separator] + rows)


def _render_html_table(df: pd.DataFrame, height: int = 400):
    """
    Render DataFrame as styled HTML table with dark theme - ALL COLUMNS VISIBLE.
    
    Args:
        df: DataFrame to display
        height: Height of the scrollable container
    """
    if df is None or len(df) == 0:
        st.warning("No data to display")
        return
    
    # Generate CSS for the table
    table_css = """
    <style>
        .custom-table-container {
            max-height: HEIGHT_PLACEHOLDERpx;
            overflow-y: auto;
            overflow-x: auto;
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 10px;
            background: #0d1117;
        }
        .custom-table {
            width: 100%;
            border-collapse: collapse;
            font-family: 'Rajdhani', monospace;
            font-size: 13px;
            white-space: nowrap;
        }
        .custom-table thead {
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .custom-table th {
            background: linear-gradient(135deg, #1a1f2e 0%, #2d3548 100%);
            color: #00ffff !important;
            padding: 12px 10px;
            text-align: left;
            border-bottom: 2px solid rgba(0, 255, 255, 0.5);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .custom-table td {
            background: #0d1117;
            color: #e0e0ff !important;
            padding: 10px;
            border-bottom: 1px solid rgba(0, 255, 255, 0.1);
        }
        .custom-table tr:hover td {
            background: rgba(0, 255, 255, 0.1);
        }
        .custom-table tr:nth-child(even) td {
            background: rgba(15, 20, 40, 0.5);
        }
        .custom-table tr:nth-child(even):hover td {
            background: rgba(0, 255, 255, 0.15);
        }
        /* Specific column styling */
        .col-positive { color: #00ff88 !important; font-weight: 600; }
        .col-negative { color: #ff4757 !important; font-weight: 600; }
        .col-neutral { color: #ffc107 !important; }
        .col-time { color: #8899aa !important; font-family: monospace; }
    </style>
    """.replace('HEIGHT_PLACEHOLDER', str(height))
    
    # Build HTML table
    html_rows = []
    
    # Header
    header_cells = "".join([f"<th>{col}</th>" for col in df.columns])
    html_rows.append(f"<thead><tr>{header_cells}</tr></thead>")
    
    # Body
    html_rows.append("<tbody>")
    for _, row in df.iterrows():
        cells = []
        for col, val in zip(df.columns, row.values):
            # Apply styling based on column/value
            cell_class = ""
            if col == 'timestamp':
                cell_class = "col-time"
            elif 'return' in str(col) or 'score' in str(col) or 'mfe' in str(col) or 'mae' in str(col):
                try:
                    # Check if positive/negative
                    val_str = str(val).replace('%', '')
                    if float(val_str) > 0:
                        cell_class = "col-positive"
                    elif float(val_str) < 0:
                        cell_class = "col-negative"
                except:
                    pass
            elif col in ['exit_type_long', 'exit_type_short']:
                if val == 'trailing':
                    cell_class = "col-positive"
                elif val == 'stop':
                    cell_class = "col-negative"
                else:
                    cell_class = "col-neutral"
            
            cells.append(f'<td class="{cell_class}">{val}</td>')
        
        html_rows.append(f"<tr>{''.join(cells)}</tr>")
    html_rows.append("</tbody>")
    
    # Combine
    table_html = f"""
    {table_css}
    <div class="custom-table-container">
        <table class="custom-table">
            {''.join(html_rows)}
        </table>
    </div>
    """
    
    st.markdown(table_html, unsafe_allow_html=True)


def render_labels_table_preview(symbol: str, timeframe: str):
    """
    Render labels table preview in MARKDOWN format: First 50 + ... + Last 50 rows.
    
    Shows OHLCV + indicators + labels from v_xgb_training VIEW:
    - timestamp, open, high, low, close
    - score_long / score_short
    - return_long / return_short
    - exit_type_long / exit_type_short
    - bars_held, rsi, atr
    
    Args:
        symbol: Symbol to display
        timeframe: Timeframe ('15m' or '1h')
    """
    
    st.markdown("#### 📋 Labels Table Preview")
    st.caption(f"Data from **v_xgb_training** VIEW for **{symbol.replace('/USDT:USDT', '')}** ({timeframe})")
    
    # Get labels from VIEW (includes OHLCV + indicators)
    df = get_labels_for_table(symbol, timeframe)
    
    if df is None or len(df) == 0:
        st.warning("No labels data available for this symbol/timeframe")
        return
    
    # Show ALL columns from VIEW
    df_display = df.copy()
    
    if len(df_display.columns) == 0:
        st.warning("No columns found in data")
        return
    
    # Format timestamp
    df_display['timestamp'] = df_display['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
    
    # Format numeric columns
    for col in df_display.columns:
        if col in ['open', 'high', 'low', 'close']:
            # Price - show 2 decimals for BTC, more for others
            df_display[col] = df_display[col].round(2)
        elif 'return' in col:
            # Show returns as percentage
            df_display[col] = (df_display[col] * 100).round(3).astype(str) + '%'
        elif col == 'score_long' or col == 'score_short':
            df_display[col] = df_display[col].round(5)
        elif col == 'rsi':
            df_display[col] = df_display[col].round(1)
        elif col == 'atr':
            df_display[col] = df_display[col].round(4)
    
    # Keep FULL column names - no abbreviations
    # All 24 columns from v_xgb_training VIEW are displayed as-is
    
    total_rows = len(df_display)
    
    # Display stats
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Rows", f"{total_rows:,}")
    
    avg_score_long = df['score_long'].mean() if 'score_long' in df.columns else 0
    col2.metric("Avg Score LONG", f"{avg_score_long:.5f}")
    
    avg_score_short = df['score_short'].mean() if 'score_short' in df.columns else 0
    col3.metric("Avg Score SHORT", f"{avg_score_short:.5f}")
    
    if 'exit_type_long' in df.columns:
        trailing_pct = (df['exit_type_long'] == 'trailing').mean() * 100
        col4.metric("% Trailing", f"{trailing_pct:.1f}%")
    
    st.markdown("---")
    
    if total_rows <= 400:
        # Show all if less than 400 rows
        st.markdown("**All rows:**")
        # Use HTML table for proper visibility
        _render_html_table(df_display, height=600)
    else:
        # Show first 200 + separator + last 200 with scroll (to align with chart)
        first_200 = df_display.head(200)
        last_200 = df_display.tail(200)
        
        # First 200 rows
        st.markdown(f"**🔼 First 200 rows (oldest data)**")
        _render_html_table(first_200, height=500)
        
        # Separator
        st.info(f"... {total_rows - 400:,} rows hidden ...")
        
        # Last 200 rows
        st.markdown(f"**🔽 Last 200 rows (newest data)**")
        _render_html_table(last_200, height=500)
    
    st.caption(f"Total: {total_rows:,} rows | Source: v_xgb_training VIEW (OHLCV + Indicators + Labels)")
    
    # Summary statistics
    with st.expander("📈 Summary Statistics", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**LONG Labels:**")
            if 'score_long' in df.columns:
                st.write(f"- Mean Score: {df['score_long'].mean():.5f}")
                st.write(f"- Std Score: {df['score_long'].std():.5f}")
                st.write(f"- Min Score: {df['score_long'].min():.5f}")
                st.write(f"- Max Score: {df['score_long'].max():.5f}")
                st.write(f"- % Positive: {(df['score_long'] > 0).mean() * 100:.1f}%")
            
            if 'exit_type_long' in df.columns:
                st.markdown("**Exit Distribution (LONG):**")
                exit_counts = df['exit_type_long'].value_counts()
                for exit_type, count in exit_counts.items():
                    pct = count / len(df) * 100
                    st.write(f"- {exit_type}: {count:,} ({pct:.1f}%)")
        
        with col2:
            st.markdown("**SHORT Labels:**")
            if 'score_short' in df.columns:
                st.write(f"- Mean Score: {df['score_short'].mean():.5f}")
                st.write(f"- Std Score: {df['score_short'].std():.5f}")
                st.write(f"- Min Score: {df['score_short'].min():.5f}")
                st.write(f"- Max Score: {df['score_short'].max():.5f}")
                st.write(f"- % Positive: {(df['score_short'] > 0).mean() * 100:.1f}%")
            
            if 'exit_type_short' in df.columns:
                st.markdown("**Exit Distribution (SHORT):**")
                exit_counts = df['exit_type_short'].value_counts()
                for exit_type, count in exit_counts.items():
                    pct = count / len(df) * 100
                    st.write(f"- {exit_type}: {count:,} ({pct:.1f}%)")
        
        # OHLCV Summary
        st.markdown("---")
        st.markdown("**Price Range:**")
        if 'close' in df.columns:
            st.write(f"- Close Min: {df['close'].min():.2f}")
            st.write(f"- Close Max: {df['close'].max():.2f}")
            st.write(f"- Close Avg: {df['close'].mean():.2f}")
        if 'rsi' in df.columns:
            st.write(f"- RSI Avg: {df['rsi'].mean():.1f}")


def get_labels_summary_by_symbol(timeframe: str) -> pd.DataFrame:
    """
    Get summary of labels per symbol for the given timeframe.
    
    Args:
        timeframe: '15m' or '1h'
    
    Returns:
        DataFrame with per-symbol summary
    """
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        query = '''
            SELECT 
                symbol,
                COUNT(*) as total_labels,
                AVG(score_long) as avg_score_long,
                AVG(score_short) as avg_score_short,
                SUM(CASE WHEN score_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pct_positive_long,
                SUM(CASE WHEN exit_type_long = 'trailing' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pct_trailing_long,
                MIN(timestamp) as first_ts,
                MAX(timestamp) as last_ts
            FROM training_labels
            WHERE timeframe = ?
            GROUP BY symbol
            ORDER BY symbol
        '''
        
        df = pd.read_sql_query(query, conn, params=(timeframe,))
        return df
        
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()


def render_labels_summary_table(timeframe: str):
    """
    Render summary table showing all symbols with their label stats in MARKDOWN.
    
    Args:
        timeframe: '15m' or '1h'
    """
    
    st.markdown(f"#### 📊 Labels Summary by Symbol ({timeframe})")
    
    df = get_labels_summary_by_symbol(timeframe)
    
    if df is None or len(df) == 0:
        st.warning(f"No labels available for {timeframe}")
        return
    
    # Format for display
    df_display = df.copy()
    df_display['symbol'] = df_display['symbol'].str.replace('/USDT:USDT', '')
    df_display['avg_score_long'] = df_display['avg_score_long'].round(5)
    df_display['avg_score_short'] = df_display['avg_score_short'].round(5)
    df_display['pct_positive_long'] = df_display['pct_positive_long'].round(1).astype(str) + '%'
    df_display['pct_trailing_long'] = df_display['pct_trailing_long'].round(1).astype(str) + '%'
    
    # Rename columns
    df_display = df_display.rename(columns={
        'symbol': 'Symbol',
        'total_labels': 'Labels',
        'avg_score_long': 'Avg LONG',
        'avg_score_short': 'Avg SHORT',
        'pct_positive_long': '% Pos LONG',
        'pct_trailing_long': '% Trailing',
        'first_ts': 'From',
        'last_ts': 'To'
    })
    
    # Convert to markdown
    markdown_table = df_to_markdown_table(df_display)
    st.markdown(markdown_table)
    
    # Summary
    total_labels = df['total_labels'].sum()
    avg_score = df['avg_score_long'].mean()
    st.caption(f"Total: {total_labels:,} labels across {len(df)} symbols | Overall avg LONG score: {avg_score:.5f}")


__all__ = [
    'render_labels_table_preview',
    'render_labels_summary_table',
    'get_labels_for_table',
    'get_labels_summary_by_symbol',
    'df_to_markdown_table'
]
