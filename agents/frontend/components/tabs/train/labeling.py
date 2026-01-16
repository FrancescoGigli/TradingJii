"""
🏷️ Train Tab - Step 2: Labeling

Generate training labels using Trailing Stop simulation:
- Load data from training_features
- Configure trailing stop parameters
- Generate score_long / score_short labels
- Remove last N rows (lookahead) - 15m comanda
- Save to training_labels table
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from database import get_connection

# Import the TrailingStopLabeler
from ai.core.labels import TrailingStopLabeler, TrailingLabelConfig


def get_training_features_symbols(timeframe: str) -> list:
    """Get only symbols with >= 95% data completeness for BOTH timeframes"""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        
        # Expected candles (approx 12 months)
        expected_15m = 35000
        expected_1h = 8760
        threshold = 0.95  # 95% completeness required
        
        # Get symbols that are complete for BOTH 15m AND 1h (like Coin Inventory)
        cur.execute('''
            SELECT symbol
            FROM (
                SELECT 
                    symbol,
                    SUM(CASE WHEN timeframe = '15m' THEN 1 ELSE 0 END) as candles_15m,
                    SUM(CASE WHEN timeframe = '1h' THEN 1 ELSE 0 END) as candles_1h
                FROM historical_ohlcv
                GROUP BY symbol
            )
            WHERE 
                CAST(candles_15m AS REAL) / ? >= ? 
                AND CAST(candles_1h AS REAL) / ? >= ?
            ORDER BY symbol
        ''', (expected_15m, threshold, expected_1h, threshold))
        
        return [r[0] for r in cur.fetchall()]
    except Exception as e:
        return []
    finally:
        conn.close()


def get_training_features_data(symbol: str, timeframe: str) -> pd.DataFrame:
    """Load data from historical_ohlcv for a specific symbol"""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    try:
        # Use historical_ohlcv table (the actual data source)
        df = pd.read_sql_query('''
            SELECT * FROM historical_ohlcv 
            WHERE symbol=? AND timeframe=?
            ORDER BY timestamp
        ''', conn, params=(symbol, timeframe))
        
        if len(df) > 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        
        return df
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()


def get_training_labels_stats():
    """Get stats from training_labels table"""
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_labels'")
        if not cur.fetchone():
            return None
        
        cur.execute('''
            SELECT 
                COUNT(DISTINCT symbol) as symbols,
                COUNT(*) as total_rows,
                MIN(timestamp) as min_date,
                MAX(timestamp) as max_date,
                timeframe,
                AVG(score_long) as avg_score_long,
                AVG(score_short) as avg_score_short
            FROM training_labels
            GROUP BY timeframe
        ''')
        
        results = {}
        for row in cur.fetchall():
            results[row[4]] = {
                'symbols': row[0],
                'total_rows': row[1],
                'min_date': row[2],
                'max_date': row[3],
                'avg_score_long': row[5],
                'avg_score_short': row[6]
            }
        return results
    except Exception as e:
        return None
    finally:
        conn.close()


def create_training_labels_table():
    """Create training_labels table if not exists - SIMPLIFIED (OHLCV + labels only)"""
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        
        # Drop old table if exists (schema changed)
        cur.execute('DROP TABLE IF EXISTS training_labels')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS training_labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                -- OHLCV
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                -- LABELS (trailing stop based)
                score_long REAL,
                score_short REAL,
                realized_return_long REAL,
                realized_return_short REAL,
                mfe_long REAL,
                mfe_short REAL,
                mae_long REAL,
                mae_short REAL,
                bars_held_long INTEGER,
                bars_held_short INTEGER,
                exit_type_long TEXT,
                exit_type_short TEXT,
                UNIQUE(symbol, timeframe, timestamp)
            )
        ''')
        
        # Create indexes
        cur.execute('CREATE INDEX IF NOT EXISTS idx_tl_symbol_tf_ts ON training_labels(symbol, timeframe, timestamp)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_tl_score_long ON training_labels(score_long)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_tl_score_short ON training_labels(score_short)')
        
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()


def generate_and_save_labels(
    symbol: str, 
    timeframe: str, 
    config: TrailingLabelConfig,
    max_bars: int
) -> tuple:
    """Generate labels for a symbol and save to training_labels"""
    
    # Load features data
    df = get_training_features_data(symbol, timeframe)
    if df is None or len(df) == 0:
        return False, 0, "No data available"
    
    # Generate labels using TrailingStopLabeler
    labeler = TrailingStopLabeler(config)
    labels_df = labeler.generate_labels_for_timeframe(df, timeframe)
    
    # Merge features with labels
    result_df = df.join(labels_df)
    
    # Remove last max_bars rows (lookahead - invalid labels)
    valid_mask = result_df[f'exit_type_long_{timeframe}'] != 'invalid'
    result_df = result_df[valid_mask]
    
    # Drop rows with any NULL in label columns
    label_cols = [f'score_long_{timeframe}', f'score_short_{timeframe}']
    result_df = result_df.dropna(subset=label_cols)
    
    if len(result_df) == 0:
        return False, 0, "No valid labels generated"
    
    # Save to database
    conn = get_connection()
    if not conn:
        return False, 0, "Database connection failed"
    
    try:
        cur = conn.cursor()
        
        # Delete existing data for this symbol/timeframe
        cur.execute('DELETE FROM training_labels WHERE symbol=? AND timeframe=?', (symbol, timeframe))
        
        # Reset index for iteration
        result_df = result_df.reset_index()
        
        # Insert rows - SIMPLIFIED (OHLCV + labels only)
        for _, row in result_df.iterrows():
            cur.execute('''
                INSERT INTO training_labels 
                (timestamp, symbol, timeframe, open, high, low, close, volume,
                 score_long, score_short, 
                 realized_return_long, realized_return_short,
                 mfe_long, mfe_short, mae_long, mae_short,
                 bars_held_long, bars_held_short,
                 exit_type_long, exit_type_short)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(row['timestamp']),
                symbol,
                timeframe,
                row['open'], row['high'], row['low'], row['close'], row['volume'],
                row[f'score_long_{timeframe}'],
                row[f'score_short_{timeframe}'],
                row[f'realized_return_long_{timeframe}'],
                row[f'realized_return_short_{timeframe}'],
                row[f'mfe_long_{timeframe}'],
                row[f'mfe_short_{timeframe}'],
                row[f'mae_long_{timeframe}'],
                row[f'mae_short_{timeframe}'],
                int(row[f'bars_held_long_{timeframe}']),
                int(row[f'bars_held_short_{timeframe}']),
                row[f'exit_type_long_{timeframe}'],
                row[f'exit_type_short_{timeframe}']
            ))
        
        conn.commit()
        return True, len(result_df), "Success"
        
    except Exception as e:
        return False, 0, str(e)
    finally:
        conn.close()


def run_labeling_pipeline(timeframe: str, config: TrailingLabelConfig, progress_callback=None):
    """Run labeling for all symbols in training_features"""
    
    # Create table
    if not create_training_labels_table():
        return False, "Failed to create training_labels table"
    
    # Get symbols
    symbols = get_training_features_symbols(timeframe)
    if not symbols:
        return False, "No symbols found in training_features"
    
    # Get max_bars for lookahead removal
    max_bars = config.get_max_bars(timeframe)
    
    total_rows = 0
    errors = []
    
    for i, symbol in enumerate(symbols):
        if progress_callback:
            progress_callback(i + 1, len(symbols), symbol)
        
        success, rows, message = generate_and_save_labels(symbol, timeframe, config, max_bars)
        
        if success:
            total_rows += rows
        else:
            errors.append(f"{symbol}: {message}")
    
    if errors and len(errors) == len(symbols):
        return False, f"All symbols failed. First error: {errors[0]}"
    
    return True, f"Generated labels for {len(symbols) - len(errors)} symbols, {total_rows:,} total rows"


def get_label_statistics(timeframe: str) -> dict:
    """Get statistics about generated labels"""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        
        cur.execute('''
            SELECT 
                COUNT(*) as total,
                AVG(score_long) as avg_score_long,
                AVG(score_short) as avg_score_short,
                SUM(CASE WHEN score_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pct_positive_long,
                SUM(CASE WHEN score_short > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pct_positive_short,
                AVG(realized_return_long) as avg_return_long,
                AVG(realized_return_short) as avg_return_short,
                AVG(bars_held_long) as avg_bars_long,
                AVG(bars_held_short) as avg_bars_short,
                SUM(CASE WHEN exit_type_long = 'trailing' THEN 1 ELSE 0 END) as trailing_exits_long,
                SUM(CASE WHEN exit_type_long = 'time' THEN 1 ELSE 0 END) as time_exits_long
            FROM training_labels
            WHERE timeframe = ?
        ''', (timeframe,))
        
        row = cur.fetchone()
        if row and row[0] > 0:
            return {
                'total_samples': row[0],
                'avg_score_long': row[1],
                'avg_score_short': row[2],
                'pct_positive_long': row[3],
                'pct_positive_short': row[4],
                'avg_return_long': row[5] * 100,  # Convert to percentage
                'avg_return_short': row[6] * 100,
                'avg_bars_long': row[7],
                'avg_bars_short': row[8],
                'trailing_exits_long': row[9],
                'time_exits_long': row[10]
            }
        return {}
    except Exception as e:
        return {}
    finally:
        conn.close()


def render_labeling_step():
    """Render Step 2: Label generation"""
    
    st.markdown("### 🏷️ Step 2: Labeling")
    st.caption("Generate training labels using Trailing Stop simulation")
    
    # === CHECK PREREQUISITE ===
    symbols_15m = get_training_features_symbols('15m')
    symbols_1h = get_training_features_symbols('1h')
    
    if not symbols_15m and not symbols_1h:
        st.error("❌ **No training features available!**")
        st.info("Complete **Step 1 (Data)** first to prepare training features.")
        return
    
    # Show available COMPLETE data clearly
    st.markdown("#### 📥 Available Data (COMPLETE downloads only)")
    c1, c2 = st.columns(2)
    c1.metric("15m Symbols (COMPLETE)", len(symbols_15m))
    c2.metric("1h Symbols (COMPLETE)", len(symbols_1h))
    
    st.info(f"ℹ️ **Labeling will use {len(symbols_15m)} symbols for 15m and {len(symbols_1h)} symbols for 1h** (only fully downloaded coins)")
    
    # === EXISTING LABELS ===
    st.divider()
    st.markdown("#### 📤 Training Labels Status")
    
    labels_stats = get_training_labels_stats()
    
    if labels_stats:
        for tf, data in labels_stats.items():
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(f"Timeframe", tf)
            col2.metric("Symbols", data['symbols'])
            col3.metric("Rows", f"{data['total_rows']:,}")
            col4.metric("Avg Score (Long)", f"{data['avg_score_long']:.4f}")
        
        st.success("✅ Training labels exist")
    else:
        st.warning("⚠️ No training labels generated yet")
    
    # === CONFIGURATION ===
    st.divider()
    st.markdown("#### ⚙️ Label Configuration")
    
    # Timeframe selection
    selected_tf = st.selectbox("Select Timeframe", ["15m", "1h"], key="label_tf_select")
    
    # Configuration expander
    with st.expander("🔧 Trailing Stop Parameters", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Trailing Stop %**")
            trailing_pct = st.slider(
                f"Trailing Stop ({selected_tf})",
                min_value=0.5,
                max_value=5.0,
                value=1.5 if selected_tf == '15m' else 2.5,
                step=0.1,
                format="%.1f%%",
                key="trailing_pct"
            )
            
            max_bars = st.slider(
                f"Max Bars ({selected_tf})",
                min_value=12,
                max_value=96,
                value=48 if selected_tf == '15m' else 24,
                key="max_bars"
            )
        
        with col2:
            st.markdown("**Cost & Penalty**")
            time_penalty = st.slider(
                "Time Penalty λ",
                min_value=0.0001,
                max_value=0.01,
                value=0.001,
                step=0.0001,
                format="%.4f",
                key="time_penalty"
            )
            
            trading_cost = st.slider(
                "Trading Cost",
                min_value=0.0,
                max_value=0.005,
                value=0.001,
                step=0.0001,
                format="%.4f",
                key="trading_cost"
            )
        
        # Show formula
        st.markdown("---")
        st.markdown("**Score Formula:**")
        st.code("score = R - λ*log(1+D) - costs", language="text")
        st.caption("Where R = realized return, D = bars held, λ = time penalty")
    
    # === ACTION BUTTONS ===
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🏷️ Generate Labels", use_container_width=True, type="primary"):
            st.session_state['start_labeling'] = True
    
    with col2:
        if st.button("📊 View Statistics", use_container_width=True, type="secondary"):
            st.session_state['show_label_stats'] = True
    
    # === LABELING PROCESS ===
    if st.session_state.get('start_labeling'):
        st.divider()
        st.markdown(f"#### 🔄 Generating Labels ({selected_tf})")
        
        # Create config
        config = TrailingLabelConfig()
        if selected_tf == '15m':
            config.trailing_stop_pct_15m = trailing_pct / 100
            config.max_bars_15m = max_bars
        else:
            config.trailing_stop_pct_1h = trailing_pct / 100
            config.max_bars_1h = max_bars
        config.time_penalty_lambda = time_penalty
        config.trading_cost = trading_cost
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(current, total, symbol):
            progress_bar.progress(current / total)
            status_text.text(f"Processing {current}/{total}: {symbol.replace('/USDT:USDT', '')}")
        
        success, message = run_labeling_pipeline(selected_tf, config, update_progress)
        
        if success:
            st.success(f"✅ {message}")
            st.cache_data.clear()
        else:
            st.error(f"❌ {message}")
        
        st.session_state['start_labeling'] = False
    
    # === STATISTICS ===
    if st.session_state.get('show_label_stats'):
        st.divider()
        st.markdown(f"#### 📊 Label Statistics ({selected_tf})")
        
        stats = get_label_statistics(selected_tf)
        
        if stats:
            # Main metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Samples", f"{stats['total_samples']:,}")
            c2.metric("Avg Score (Long)", f"{stats['avg_score_long']:.5f}")
            c3.metric("Avg Score (Short)", f"{stats['avg_score_short']:.5f}")
            c4.metric("% Positive (Long)", f"{stats['pct_positive_long']:.1f}%")
            
            # Detailed metrics
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**LONG Labels:**")
                st.write(f"- Avg Return: {stats['avg_return_long']:.2f}%")
                st.write(f"- Avg Bars Held: {stats['avg_bars_long']:.1f}")
                st.write(f"- Trailing Exits: {stats['trailing_exits_long']:,}")
                st.write(f"- Time Exits: {stats['time_exits_long']:,}")
            
            with col2:
                st.markdown("**SHORT Labels:**")
                st.write(f"- Avg Return: {stats['avg_return_short']:.2f}%")
                st.write(f"- Avg Bars Held: {stats['avg_bars_short']:.1f}")
                st.write(f"- % Positive: {stats['pct_positive_short']:.1f}%")
        else:
            st.warning("No label statistics available. Generate labels first.")
        
        if st.button("Close Statistics"):
            st.session_state['show_label_stats'] = False
            st.rerun()


__all__ = ['render_labeling_step']
