"""
🚀 ML Labels Generator - Generate labels for ALL coins

This module handles the batch generation of ML training labels
for all available coins in the historical database.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import time

from database import (
    get_historical_ohlcv,
    get_historical_symbols_by_volume,
    save_ml_labels_to_db,
    get_ml_labels_stats,
    get_ml_labels_by_symbol,
    get_historical_inventory,
    get_ml_labels_inventory,
)

# Import label generator
try:
    from ai.core.labels import TrailingStopLabeler, TrailingLabelConfig
    LABELS_AVAILABLE = True
except ImportError as e:
    print(f"Labels import error: {e}")
    LABELS_AVAILABLE = False


def generate_labels_for_symbol(symbol: str, timeframe: str, config: TrailingLabelConfig, min_candles: int = 50):
    """
    Generate labels for a single symbol/timeframe.
    Uses ALL available historical data (no limit).
    
    Args:
        symbol: Trading pair symbol
        timeframe: '15m' or '1h'
        config: Label configuration
        min_candles: Minimum candles required (default 50)
    
    Returns:
        Tuple of (ohlcv_df, labels_df, rows_saved, error_msg)
    """
    try:
        # Get ALL OHLCV data (no limit - use all historical data)
        df = get_historical_ohlcv(symbol, timeframe, limit=999999)
        
        if df is None:
            return None, None, 0, "No data in database"
        
        if len(df) < min_candles:
            return None, None, 0, f"Only {len(df)} candles (need {min_candles}+)"
        
        # Generate labels
        labeler = TrailingStopLabeler(config)
        labels = labeler.generate_labels_for_timeframe(df, timeframe)
        
        if labels is None or len(labels) == 0:
            return None, None, 0, "Label generation returned empty result"
        
        # Check if we have valid labels
        valid_labels = labels[labels[f'exit_type_long_{timeframe}'] != 'invalid']
        if len(valid_labels) == 0:
            return None, None, 0, f"All {len(labels)} labels are invalid (not enough future data)"
        
        # Save to database
        config_dict = {
            'trailing_stop_pct': config.get_trailing_stop_pct(timeframe),
            'max_bars': config.get_max_bars(timeframe),
            'time_penalty_lambda': config.time_penalty_lambda,
            'trading_cost': config.trading_cost
        }
        
        rows_saved = save_ml_labels_to_db(symbol, timeframe, df, labels, config_dict)
        
        if rows_saved == 0:
            return None, None, 0, "Database save returned 0 rows"
        
        return df, labels, rows_saved, None
        
    except Exception as e:
        import traceback
        return None, None, 0, f"{str(e)}"


def render_generate_all_labels():
    """Render the Generate ALL Labels section"""
    
    st.markdown("### 🚀 Generate Labels for ALL Coins")
    st.caption("Generate and auto-save ML training labels for all available coins")
    
    if not LABELS_AVAILABLE:
        st.error("❌ ML Labels module not available")
        return
    
    # Get all symbols
    all_symbols = get_historical_symbols_by_volume()
    
    if not all_symbols:
        st.warning("⚠️ No historical data available. Please fetch historical data first.")
        return
    
    # Info
    st.info(f"📊 Found **{len(all_symbols)}** coins with historical data")
    
    # === CONFIGURATION ===
    st.markdown("#### ⚙️ Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Timeframes selection
        timeframes = st.multiselect(
            "Timeframes",
            ["15m", "1h"],
            default=["15m", "1h"],
            key="gen_all_timeframes"
        )
        
        # Info: uses ALL available data
        st.success("📊 **Uses ALL historical data** (no limit)")
    
    with col2:
        st.markdown("**Label Parameters:**")
        
        # Time penalty lambda
        lambda_val = st.slider(
            "λ (Time Penalty)",
            min_value=0.0001,
            max_value=0.01,
            value=0.001,
            step=0.0001,
            format="%.4f",
            key="gen_all_lambda"
        )
        
        # Trading cost
        cost = st.slider(
            "Trading Cost %",
            min_value=0.0,
            max_value=0.5,
            value=0.1,
            step=0.01,
            key="gen_all_cost"
        ) / 100
    
    # Trailing stop settings (per timeframe)
    st.markdown("**Trailing Stop Settings:**")
    
    ts_col1, ts_col2 = st.columns(2)
    
    with ts_col1:
        trailing_15m = st.slider(
            "Trailing Stop % (15m)",
            min_value=0.5,
            max_value=5.0,
            value=1.5,
            step=0.1,
            key="gen_all_ts_15m"
        ) / 100
        
        max_bars_15m = st.slider(
            "Max Bars (15m)",
            min_value=12,
            max_value=96,
            value=48,
            step=6,
            key="gen_all_mb_15m"
        )
    
    with ts_col2:
        trailing_1h = st.slider(
            "Trailing Stop % (1h)",
            min_value=0.5,
            max_value=5.0,
            value=2.5,
            step=0.1,
            key="gen_all_ts_1h"
        ) / 100
        
        max_bars_1h = st.slider(
            "Max Bars (1h)",
            min_value=12,
            max_value=96,
            value=24,
            step=6,
            key="gen_all_mb_1h"
        )
    
    st.divider()
    
    # === GENERATE BUTTON ===
    if st.button("🚀 GENERATE ALL LABELS", type="primary", use_container_width=True, key="gen_all_btn"):
        
        if not timeframes:
            st.error("Please select at least one timeframe")
            return
        
        # Create config
        config = TrailingLabelConfig(
            trailing_stop_pct_15m=trailing_15m,
            trailing_stop_pct_1h=trailing_1h,
            max_bars_15m=max_bars_15m,
            max_bars_1h=max_bars_1h,
            time_penalty_lambda=lambda_val,
            trading_cost=cost
        )
        
        # Progress tracking
        total_tasks = len(all_symbols) * len(timeframes)
        progress_bar = st.progress(0)
        status_text = st.empty()
        stats_container = st.empty()
        
        results = {
            'success': 0,
            'failed': 0,
            'total_rows': 0,
            'errors': []
        }
        
        # Sequential processing - one coin at a time
        completed = 0
        start_time = time.time()
        
        for symbol in all_symbols:
            sym_short = symbol.replace('/USDT:USDT', '')
            
            for tf in timeframes:
                completed += 1
                progress = completed / total_tasks
                progress_bar.progress(progress)
                
                # Calculate ETA
                elapsed = time.time() - start_time
                if completed > 1:
                    eta = (elapsed / completed) * (total_tasks - completed)
                    eta_str = f"{int(eta)}s" if eta < 60 else f"{int(eta/60)}m {int(eta%60)}s"
                else:
                    eta_str = "calculating..."
                
                status_text.text(f"Processing {sym_short} [{tf}] ({completed}/{total_tasks}) | ETA: {eta_str}")
                
                # Generate labels
                df, labels, rows_saved, error = generate_labels_for_symbol(symbol, tf, config)
                
                if error:
                    results['failed'] += 1
                    results['errors'].append(f"{sym_short} [{tf}]: {error}")
                else:
                    results['success'] += 1
                    results['total_rows'] += rows_saved
                
                # Live stats every 10 tasks
                if completed % 10 == 0 or completed == total_tasks:
                    stats_container.markdown(f"""
                    | ✅ Success | ❌ Failed | 📊 Labels | ⏱️ Speed |
                    |-----------|----------|----------|---------|
                    | {results['success']} | {results['failed']} | {results['total_rows']:,} | {completed / max(elapsed, 0.1):.1f}/s |
                    """)
        
        # Complete
        total_time = time.time() - start_time
        progress_bar.progress(1.0)
        status_text.empty()
        stats_container.empty()
        
        # Show results
        st.success(f"""
        ✅ **Generation Complete!**
        
        - ✅ Success: **{results['success']}** coin/timeframe pairs
        - ❌ Failed: **{results['failed']}** coin/timeframe pairs
        - 📊 Total labels saved: **{results['total_rows']:,}**
        """)
        
        if results['errors']:
            with st.expander(f"⚠️ {len(results['errors'])} Errors", expanded=True):
                for err in results['errors'][:30]:  # Show first 30
                    st.text(err)
                if len(results['errors']) > 30:
                    st.text(f"... and {len(results['errors']) - 30} more")
        
        st.balloons()
        
        # Store results in session state to persist after any interaction
        st.session_state['last_generation_results'] = results
        
        # Rerun to update the table with new labels
        st.rerun()
    
    # === CURRENT DB STATUS ===
    st.divider()
    st.markdown("#### 🗄️ Current Database Status")
    
    db_stats = get_ml_labels_stats()
    
    if db_stats.get('exists') and not db_stats.get('empty'):
        m1, m2, m3, m4 = st.columns(4)
        
        m1.metric("📊 Total Labels", f"{db_stats.get('total_labels', 0):,}")
        m2.metric("🪙 Symbols", db_stats.get('symbols', 0))
        m3.metric("⏱️ Timeframes", db_stats.get('timeframes', 0))
        m4.metric("📈 Avg Score (LONG)", f"{(db_stats.get('avg_score_long', 0) or 0) * 100:.3f}%")
    else:
        st.info("📭 No labels in database yet. Click 'Generate ALL Labels' to create them.")
    
    # === STATUS TABLE ===
    st.divider()
    st.markdown("#### 📋 Status per Coin (Historical vs Labels)")
    
    # Get historical inventory and labels inventory
    historical_inv = get_historical_inventory()
    labels_inv = get_ml_labels_inventory()
    
    if historical_inv:
        # Build status dict from labels inventory
        labels_dict = {}
        for item in labels_inv:
            labels_dict[item['symbol']] = item
        
        # Build comparison table
        status_data = []
        missing_15m = []
        missing_1h = []
        
        for hist in historical_inv:
            symbol = hist['symbol']
            sym_short = symbol.replace('/USDT:USDT', '')
            
            # Historical data
            has_hist_15m = hist.get('candles_15m', 0) > 0
            has_hist_1h = hist.get('candles_1h', 0) > 0
            
            # Labels data
            lab = labels_dict.get(symbol, {})
            has_labels_15m = lab.get('labels_15m', 0) > 0
            has_labels_1h = lab.get('labels_1h', 0) > 0
            
            # Status
            status_15m = "✅" if has_labels_15m else ("⚠️" if has_hist_15m else "❌")
            status_1h = "✅" if has_labels_1h else ("⚠️" if has_hist_1h else "❌")
            
            # Track missing
            if has_hist_15m and not has_labels_15m:
                missing_15m.append(symbol)
            if has_hist_1h and not has_labels_1h:
                missing_1h.append(symbol)
            
            status_data.append({
                'Rank': hist.get('rank', 999),
                'Symbol': sym_short,
                'Hist 15m': f"{hist.get('candles_15m', 0):,}" if has_hist_15m else "-",
                'Labels 15m': f"{lab.get('labels_15m', 0):,}" if has_labels_15m else "-",
                '15m': status_15m,
                'Hist 1h': f"{hist.get('candles_1h', 0):,}" if has_hist_1h else "-",
                'Labels 1h': f"{lab.get('labels_1h', 0):,}" if has_labels_1h else "-",
                '1h': status_1h,
            })
        
        # Summary metrics
        total_coins = len(status_data)
        ready_15m = sum(1 for s in status_data if s['15m'] == '✅')
        ready_1h = sum(1 for s in status_data if s['1h'] == '✅')
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🪙 Total Coins", total_coins)
        col2.metric("✅ Ready 15m", f"{ready_15m}/{total_coins}")
        col3.metric("✅ Ready 1h", f"{ready_1h}/{total_coins}")
        col4.metric("⚠️ Missing", f"{len(missing_15m) + len(missing_1h)}")
        
        # Show status table with styling - Split into 2 columns of 50 each
        status_df = pd.DataFrame(status_data)
        
        # Apply styling function
        def style_table(df):
            def style_status_cell(val):
                if val == '✅':
                    return 'color: #00ff00; font-weight: bold'
                elif val == '⚠️':
                    return 'color: #ffaa00; font-weight: bold'
                elif val == '❌':
                    return 'color: #ff4444; font-weight: bold'
                return ''
            
            def style_number_cell(val):
                if isinstance(val, str) and val != '-':
                    return 'color: #00ccff'
                return 'color: #666666'
            
            return df.style.applymap(
                style_status_cell, 
                subset=['15m', '1h']
            ).applymap(
                style_number_cell,
                subset=['Hist 15m', 'Labels 15m', 'Hist 1h', 'Labels 1h']
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
        half = len(status_df) // 2
        df_left = status_df.iloc[:half].reset_index(drop=True)
        df_right = status_df.iloc[half:].reset_index(drop=True)
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown(f"**Coins 1-{half}**")
            st.markdown(style_table(df_left).to_html(escape=False), unsafe_allow_html=True)
        
        with col_right:
            st.markdown(f"**Coins {half+1}-{len(status_df)}**")
            st.markdown(style_table(df_right).to_html(escape=False), unsafe_allow_html=True)
        
        st.caption("✅ = Labels ready | ⚠️ = Has historical but no labels | ❌ = No data")
        
        # === GENERATE MISSING BUTTON ===
        if missing_15m or missing_1h:
            st.divider()
            st.markdown("#### 🔄 Generate Missing Labels Only")
            
            missing_count = len(set(missing_15m + missing_1h))
            missing_tasks = len(missing_15m) + len(missing_1h)
            
            st.warning(f"⚠️ Found **{missing_count}** coins with missing labels ({missing_tasks} total tasks)")
            
            if st.button(f"🔄 GENERATE MISSING ONLY ({missing_tasks} tasks)", type="secondary", use_container_width=True, key="gen_missing_btn"):
                
                # Create config with current settings
                config = TrailingLabelConfig(
                    trailing_stop_pct_15m=trailing_15m,
                    trailing_stop_pct_1h=trailing_1h,
                    max_bars_15m=max_bars_15m,
                    max_bars_1h=max_bars_1h,
                    time_penalty_lambda=lambda_val,
                    trading_cost=cost
                )
                
                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                stats_container = st.empty()
                
                results = {
                    'success': 0,
                    'failed': 0,
                    'total_rows': 0,
                    'errors': []
                }
                
                # Build task list
                tasks = []
                for sym in missing_15m:
                    tasks.append((sym, '15m'))
                for sym in missing_1h:
                    tasks.append((sym, '1h'))
                
                total_tasks = len(tasks)
                completed = 0
                start_time = time.time()
                
                for symbol, tf in tasks:
                    sym_short = symbol.replace('/USDT:USDT', '')
                    completed += 1
                    progress = completed / total_tasks
                    progress_bar.progress(progress)
                    
                    # Calculate ETA
                    elapsed = time.time() - start_time
                    if completed > 1:
                        eta = (elapsed / completed) * (total_tasks - completed)
                        eta_str = f"{int(eta)}s" if eta < 60 else f"{int(eta/60)}m {int(eta%60)}s"
                    else:
                        eta_str = "calculating..."
                    
                    status_text.text(f"Processing {sym_short} [{tf}] ({completed}/{total_tasks}) | ETA: {eta_str}")
                    
                    # Generate labels
                    df, labels, rows_saved, error = generate_labels_for_symbol(symbol, tf, config)
                    
                    if error:
                        results['failed'] += 1
                        results['errors'].append(f"{sym_short} [{tf}]: {error}")
                    else:
                        results['success'] += 1
                        results['total_rows'] += rows_saved
                    
                    # Live stats every 5 tasks
                    if completed % 5 == 0 or completed == total_tasks:
                        stats_container.markdown(f"""
                        | ✅ Success | ❌ Failed | 📊 Labels | ⏱️ Speed |
                        |-----------|----------|----------|---------|
                        | {results['success']} | {results['failed']} | {results['total_rows']:,} | {completed / max(elapsed, 0.1):.1f}/s |
                        """)
                
                # Complete
                progress_bar.progress(1.0)
                status_text.empty()
                stats_container.empty()
                
                st.success(f"""
                ✅ **Missing Labels Generated!**
                
                - ✅ Success: **{results['success']}** coin/timeframe pairs
                - ❌ Failed: **{results['failed']}** coin/timeframe pairs
                - 📊 Total labels saved: **{results['total_rows']:,}**
                """)
                
                if results['errors']:
                    with st.expander(f"⚠️ {len(results['errors'])} Errors", expanded=False):
                        for err in results['errors'][:20]:
                            st.text(err)
                
                st.balloons()
                st.rerun()
        else:
            st.success("✅ All coins have labels for all timeframes!")
    
    # Clear labels option
    st.divider()
    
    with st.expander("🗑️ Clear Labels (Danger Zone)", expanded=False):
        st.warning("⚠️ This will delete ALL ML labels from the database!")
        
        confirm = st.text_input(
            "Type 'DELETE' to confirm:",
            key="confirm_delete_labels"
        )
        
        if st.button("🗑️ Clear All Labels", type="secondary", key="clear_labels_btn"):
            if confirm == "DELETE":
                from database import clear_ml_labels
                deleted = clear_ml_labels()
                st.success(f"✅ Deleted {deleted:,} labels from database")
                st.rerun()
            else:
                st.error("Please type 'DELETE' to confirm")
