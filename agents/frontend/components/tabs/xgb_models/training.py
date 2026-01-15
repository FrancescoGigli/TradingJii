"""
🚀 XGBoost Models - Training Section

Contains:
- Manual training with custom parameters
- Optuna hyperparameter optimization
"""

import streamlit as st


def render_training_section():
    """Render the training section with mode selection"""
    from services.ml_training import get_available_training_data, train_xgb_model, run_optuna_optimization
    import pandas as pd
    
    st.markdown("### 🚀 Train New Model")
    st.caption("Train XGBoost models directly from the dashboard")
    
    # ════════════════════════════════════════════════════════════════════
    # TRAINING MODE SELECTION
    # ════════════════════════════════════════════════════════════════════
    
    training_mode = st.radio(
        "Training Mode",
        options=["⚙️ Manual Parameters", "🎯 Optuna Auto-Tune"],
        horizontal=True,
        help="Manual: Set parameters yourself. Optuna: Automatic hyperparameter optimization."
    )
    
    st.divider()
    
    # Get available data
    data_info = get_available_training_data()
    
    if 'error' in data_info:
        st.error(f"❌ {data_info['error']}")
        st.info("💡 First generate ML labels in the 'ML Labels' tab")
        return
    
    # ════════════════════════════════════════════════════════════════════
    # DATA SELECTION (Common for both modes)
    # ════════════════════════════════════════════════════════════════════
    
    st.markdown("#### 📊 Select Training Data")
    
    # Filter toggle
    only_complete = st.toggle(
        "✅ Only Complete (12 months)",
        value=True,
        help="Show only symbols with ≥95% data for both 15m and 1h timeframes"
    )
    
    # Get symbol options based on filter
    if only_complete:
        available_symbols = data_info.get('complete_symbols', data_info['symbols'])
    else:
        available_symbols = data_info['symbols']
    
    col1, col2 = st.columns(2)
    
    with col1:
        selected_symbols = st.multiselect(
            "Symbols",
            options=available_symbols,
            default=available_symbols,
            help="Select which symbols to include in training"
        )
    
    with col2:
        selected_timeframes = st.multiselect(
            "Timeframes",
            options=data_info['timeframes'],
            default=data_info['timeframes'],
            help="Select which timeframes to include"
        )
    
    # Show data stats
    if selected_symbols and selected_timeframes:
        matching_counts = [c for c in data_info['counts'] 
                         if c['symbol'] in selected_symbols and c['timeframe'] in selected_timeframes]
        total_selected = sum(c['count'] for c in matching_counts)
        
        # Summary metrics
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("📊 Selected Symbols", len(selected_symbols))
        col_m2.metric("🕯️ Total Candles", f"{total_selected:,}")
        col_m3.metric("✅ Complete", f"{data_info.get('n_complete', 0)}/{data_info.get('n_total', 0)}")
        
        # ════════════════════════════════════════════════════════════════════
        # DATA DETAILS TABLE (Styled like generator.py - one row per coin)
        # ════════════════════════════════════════════════════════════════════
        
        # Group by symbol - create dict with 15m and 1h data per coin
        symbol_data = {}
        for c in matching_counts:
            sym = c['symbol']
            tf = c['timeframe']
            if sym not in symbol_data:
                symbol_data[sym] = {'15m': None, '1h': None}
            symbol_data[sym][tf] = c
        
        # Build rows for table - one row per symbol with 15m and 1h columns
        rows = []
        for idx, (symbol, data) in enumerate(symbol_data.items(), 1):
            sym_short = symbol.replace('/USDT:USDT', '')
            
            # 15m data
            d15 = data.get('15m')
            if d15:
                candles_15m = f"{d15['count']:,}"
                from_15m = d15.get('start_date', '-') or '-'
                to_15m = d15.get('end_date', '-') or '-'
                if d15.get('is_complete'):
                    status_15m = "✅"
                elif d15.get('pct', 0) >= 50:
                    status_15m = f"🔄 {d15.get('pct', 0):.0f}%"
                else:
                    status_15m = f"⚠️ {d15.get('pct', 0):.0f}%"
            else:
                candles_15m = "-"
                from_15m = "-"
                to_15m = "-"
                status_15m = "❌"
            
            # 1h data
            d1h = data.get('1h')
            if d1h:
                candles_1h = f"{d1h['count']:,}"
                from_1h = d1h.get('start_date', '-') or '-'
                to_1h = d1h.get('end_date', '-') or '-'
                if d1h.get('is_complete'):
                    status_1h = "✅"
                elif d1h.get('pct', 0) >= 50:
                    status_1h = f"🔄 {d1h.get('pct', 0):.0f}%"
                else:
                    status_1h = f"⚠️ {d1h.get('pct', 0):.0f}%"
            else:
                candles_1h = "-"
                from_1h = "-"
                to_1h = "-"
                status_1h = "❌"
            
            rows.append({
                '#': idx,
                'Symbol': sym_short,
                'Candles 15m': candles_15m,
                'From 15m': from_15m,
                'To 15m': to_15m,
                '15m': status_15m,
                'Candles 1h': candles_1h,
                'From 1h': from_1h,
                'To 1h': to_1h,
                '1h': status_1h,
            })
        
        # Create DataFrame  
        df_table = pd.DataFrame(rows)
        
        # Styled table function (like generator.py)
        def style_data_table(df):
            def style_status_cell(val):
                if '✅' in str(val):
                    return 'color: #00ff00; font-weight: bold'
                elif '🔄' in str(val):
                    return 'color: #ffaa00; font-weight: bold'
                elif '⚠️' in str(val) or '❌' in str(val):
                    return 'color: #ff4444; font-weight: bold'
                return ''
            
            def style_number_cell(val):
                if isinstance(val, str) and val != '-' and any(c.isdigit() for c in val):
                    return 'color: #00ccff'
                return 'color: #888888'
            
            # Get status columns that exist in the dataframe
            status_cols = [col for col in ['15m', '1h'] if col in df.columns]
            candles_cols = [col for col in ['Candles 15m', 'Candles 1h'] if col in df.columns]
            
            styled = df.style.applymap(
                style_status_cell, 
                subset=status_cols
            )
            if candles_cols:
                styled = styled.applymap(
                    style_number_cell,
                    subset=candles_cols
                )
            
            return styled.set_properties(**{
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
                    ('padding', '8px 10px'),
                    ('border-bottom', '2px solid #00ff88'),
                    ('font-size', '12px'),
                    ('text-align', 'center')
                ]},
                {'selector': 'td', 'props': [
                    ('padding', '6px 10px'),
                    ('border-bottom', '1px solid #333355'),
                    ('text-align', 'center')
                ]}
            ]).hide(axis='index')
        
        # Render styled table with expander (single column, no split)
        with st.expander(f"📋 Data Details ({len(symbol_data)} coins)", expanded=True):
            st.markdown(style_data_table(df_table).to_html(escape=False), unsafe_allow_html=True)
            st.caption("✅ = Complete (≥95%) | 🔄 = Partial | ⚠️ = Low data | ❌ = No data")
        
        # Warnings for incomplete data
        incomplete = [c for c in matching_counts if not c.get('is_complete', False)]
        if incomplete:
            st.warning(f"⚠️ {len(incomplete)} symbol/timeframe combinations with < 95% data")
        
        # Date range summary
        st.markdown(f"""
        <div style="background: #1e1e2e; padding: 15px; border-radius: 8px; margin: 10px 0;">
            <span style="color: #00d4ff; font-size: 1.2rem; font-weight: 700;">
                📊 {total_selected:,} training samples selected
            </span>
            <span style="color: #888; margin-left: 15px;">
                ({data_info['min_date'][:10]} → {data_info['max_date'][:10]})
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    if not selected_symbols or not selected_timeframes:
        st.warning("⚠️ Select at least one symbol and timeframe")
        return
    
    # ════════════════════════════════════════════════════════════════════
    # BRANCH: Manual vs Optuna
    # ════════════════════════════════════════════════════════════════════
    
    if training_mode == "⚙️ Manual Parameters":
        _render_manual_training(selected_symbols, selected_timeframes, train_xgb_model)
    else:
        _render_optuna_training(selected_symbols, selected_timeframes, run_optuna_optimization)


# ═══════════════════════════════════════════════════════════════════════════════
# MANUAL TRAINING
# ═══════════════════════════════════════════════════════════════════════════════

def _render_manual_training(selected_symbols: list, selected_timeframes: list, train_func):
    """Render manual training section with parameter sliders"""
    
    st.markdown("#### ⚙️ XGBoost Hyperparameters")
    st.caption("Adjust parameters - hover for descriptions")
    
    # Parameter definitions with effects
    params_config = [
        {
            'name': 'max_depth',
            'label': '🌳 Max Depth',
            'min': 2, 'max': 15, 'default': 6, 'step': 1,
            'low_effect': '⬅️ Simpler model',
            'high_effect': '➡️ Complex model',
            'help': 'Maximum depth of each tree. Lower = simpler model (underfitting risk). Higher = more complex (overfitting risk).'
        },
        {
            'name': 'learning_rate',
            'label': '📈 Learning Rate',
            'min': 0.01, 'max': 0.3, 'default': 0.05, 'step': 0.01,
            'low_effect': '⬅️ Slower learning',
            'high_effect': '➡️ Faster learning',
            'help': 'Step size shrinkage. Lower = more conservative updates (slower but stable). Higher = faster convergence (risk of overshooting).'
        },
        {
            'name': 'n_estimators',
            'label': '🌲 Number of Trees',
            'min': 100, 'max': 1000, 'default': 500, 'step': 50,
            'low_effect': '⬅️ Faster training',
            'high_effect': '➡️ Better accuracy',
            'help': 'Number of boosting rounds. More trees = better accuracy but slower training and potential overfitting.'
        },
        {
            'name': 'min_child_weight',
            'label': '👶 Min Child Weight',
            'min': 1, 'max': 50, 'default': 10, 'step': 1,
            'low_effect': '⬅️ More splits',
            'high_effect': '➡️ Fewer splits',
            'help': 'Minimum sum of weights needed in a child. Higher = more conservative (prevents overfitting on noise).'
        },
        {
            'name': 'subsample',
            'label': '📊 Subsample Ratio',
            'min': 0.5, 'max': 1.0, 'default': 0.8, 'step': 0.05,
            'low_effect': '⬅️ More regularization',
            'high_effect': '➡️ Use all data',
            'help': 'Fraction of samples used per tree. Lower = more randomness (reduces overfitting). 1.0 = use all samples.'
        },
        {
            'name': 'colsample_bytree',
            'label': '📋 Column Sample',
            'min': 0.5, 'max': 1.0, 'default': 0.8, 'step': 0.05,
            'low_effect': '⬅️ More diverse trees',
            'high_effect': '➡️ Use all features',
            'help': 'Fraction of features used per tree. Lower = more diverse trees (reduces overfitting).'
        },
    ]
    
    # Store parameters
    xgb_params = {}
    
    for param in params_config:
        st.markdown(f"**{param['label']}**")
        
        col1, col2, col3 = st.columns([1, 3, 1])
        
        with col1:
            st.caption(param['low_effect'])
        
        with col2:
            xgb_params[param['name']] = st.slider(
                param['label'],
                min_value=float(param['min']) if isinstance(param['default'], float) else param['min'],
                max_value=float(param['max']) if isinstance(param['default'], float) else param['max'],
                value=float(param['default']) if isinstance(param['default'], float) else param['default'],
                step=float(param['step']) if isinstance(param['default'], float) else param['step'],
                help=param['help'],
                label_visibility="collapsed"
            )
        
        with col3:
            st.caption(param['high_effect'])
    
    st.divider()
    
    # Train/Test Split
    st.markdown("**📊 Train/Test Split**")
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        st.caption("⬅️ More test data")
    with col2:
        train_ratio = st.slider(
            "Train Ratio",
            min_value=0.6, max_value=0.9, value=0.8, step=0.05,
            help="Percentage of data used for training. Rest is for testing.",
            label_visibility="collapsed"
        )
    with col3:
        st.caption("➡️ More train data")
    
    st.markdown(f"**Split:** {int(train_ratio*100)}% train / {int((1-train_ratio)*100)}% test")
    
    st.divider()
    
    # ════════════════════════════════════════════════════════════════════
    # TRAINING BUTTON
    # ════════════════════════════════════════════════════════════════════
    
    if st.button("🚀 START TRAINING", type="primary", use_container_width=True, key="train_manual_btn"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(progress, message):
            progress_bar.progress(progress)
            status_text.markdown(f"**{message}**")
        
        with st.spinner("Training in progress..."):
            result = train_func(
                symbols=selected_symbols,
                timeframes=selected_timeframes,
                params=xgb_params,
                train_ratio=train_ratio,
                progress_callback=update_progress
            )
        
        _display_training_results(result)


# ═══════════════════════════════════════════════════════════════════════════════
# OPTUNA AUTO-TUNE
# ═══════════════════════════════════════════════════════════════════════════════

def _render_optuna_training(selected_symbols: list, selected_timeframes: list, optuna_func):
    """Render Optuna hyperparameter optimization section"""
    
    st.markdown("#### 🎯 Optuna Hyperparameter Optimization")
    
    # Info box
    st.info("""
    **Optuna** automatically finds the best hyperparameters using TPE (Tree-structured Parzen Estimator).
    
    - **Objective**: Maximize Spearman correlation (ranking quality)
    - **Split**: 70% train / 15% validation / 15% test
    - **Parameters tuned**: max_depth, learning_rate, n_estimators, min_child_weight, subsample, colsample_bytree, reg_alpha, reg_lambda
    """)
    
    st.divider()
    
    # Number of trials
    st.markdown("**🔢 Number of Trials**")
    st.caption("More trials = better optimization but longer time")
    
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        st.caption("⬅️ Faster")
    with col2:
        n_trials = st.slider(
            "Trials",
            min_value=10, max_value=100, value=30, step=5,
            help="Number of optimization trials per model. 30-50 is usually a good balance.",
            label_visibility="collapsed"
        )
    with col3:
        st.caption("➡️ Better results")
    
    # Estimated time
    estimated_minutes = n_trials * 2  # Rough estimate
    st.markdown(f"**Estimated time:** ~{estimated_minutes}-{estimated_minutes*2} minutes (depends on data size)")
    
    st.divider()
    
    # ════════════════════════════════════════════════════════════════════
    # OPTUNA TRAINING BUTTON
    # ════════════════════════════════════════════════════════════════════
    
    if st.button("🎯 START OPTUNA OPTIMIZATION", type="primary", use_container_width=True, key="train_optuna_btn"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def update_progress(progress, message):
            progress_bar.progress(progress)
            status_text.markdown(f"**{message}**")
        
        with st.spinner("Optuna optimization in progress..."):
            result = optuna_func(
                symbols=selected_symbols,
                timeframes=selected_timeframes,
                n_trials=n_trials,
                progress_callback=update_progress
            )
        
        _display_optuna_results(result)


# ═══════════════════════════════════════════════════════════════════════════════
# RESULTS DISPLAY
# ═══════════════════════════════════════════════════════════════════════════════

def _display_training_results(result: dict):
    """Display manual training results"""
    
    if 'error' in result:
        st.error(f"❌ Training failed: {result['error']}")
        return
    
    st.success(f"✅ Training complete! Model saved: **{result['version']}**")
    
    # Show results
    st.markdown("#### 📊 Training Results")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### 📈 LONG Model")
        metrics_l = result['metrics_long']
        ranking_l = metrics_l.get('ranking', {})
        
        st.metric("Test R²", f"{metrics_l['test_r2']:.4f}")
        st.metric("Test RMSE", f"{metrics_l['test_rmse']:.6f}")
        st.metric("Spearman Corr", f"{ranking_l.get('spearman_corr', 0):.4f}")
        st.metric("Top 5% Positive", f"{ranking_l.get('top5pct_positive', 0):.1f}%")
    
    with col2:
        st.markdown("##### 📉 SHORT Model")
        metrics_s = result['metrics_short']
        ranking_s = metrics_s.get('ranking', {})
        
        st.metric("Test R²", f"{metrics_s['test_r2']:.4f}")
        st.metric("Test RMSE", f"{metrics_s['test_rmse']:.6f}")
        st.metric("Spearman Corr", f"{ranking_s.get('spearman_corr', 0):.4f}")
        st.metric("Top 5% Positive", f"{ranking_s.get('top5pct_positive', 0):.1f}%")
    
    st.markdown(f"""
    <div style="background: #10B981; padding: 15px; border-radius: 8px; margin-top: 15px;">
        <p style="color: white; margin: 0; font-weight: 700;">
            ✅ Model ready to use!
        </p>
        <p style="color: rgba(255,255,255,0.8); margin: 5px 0 0 0; font-size: 0.9rem;">
            Training data: {result['data_range']['train_start'][:10]} → {result['data_range']['train_end'][:10]}<br>
            Test data: {result['data_range']['test_start'][:10]} → {result['data_range']['test_end'][:10]}<br>
            Features: {result['n_features']} | Train samples: {result['n_train']:,} | Test samples: {result['n_test']:,}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.balloons()


def _display_optuna_results(result: dict):
    """Display Optuna optimization results"""
    
    if 'error' in result:
        st.error(f"❌ Optimization failed: {result['error']}")
        return
    
    st.success(f"✅ Optuna optimization complete! Model saved: **{result['version']}**")
    
    # Show results
    st.markdown("#### 📊 Optimization Results")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### 📈 LONG Model")
        metrics_l = result['metrics_long']
        
        st.metric("Best Spearman (Val)", f"{result['best_spearman_long']:.4f}")
        st.metric("Test Spearman", f"{metrics_l.get('test_spearman', 0):.4f}")
        st.metric("Test R²", f"{metrics_l['test_r2']:.4f}")
        st.metric("Test RMSE", f"{metrics_l['test_rmse']:.6f}")
    
    with col2:
        st.markdown("##### 📉 SHORT Model")
        metrics_s = result['metrics_short']
        
        st.metric("Best Spearman (Val)", f"{result['best_spearman_short']:.4f}")
        st.metric("Test Spearman", f"{metrics_s.get('test_spearman', 0):.4f}")
        st.metric("Test R²", f"{metrics_s['test_r2']:.4f}")
        st.metric("Test RMSE", f"{metrics_s['test_rmse']:.6f}")
    
    # Best parameters found
    st.markdown("#### 🏆 Best Hyperparameters Found")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**LONG Model:**")
        for key, value in result['best_params_long'].items():
            if isinstance(value, float):
                st.markdown(f"- `{key}`: {value:.6f}")
            else:
                st.markdown(f"- `{key}`: {value}")
    
    with col2:
        st.markdown("**SHORT Model:**")
        for key, value in result['best_params_short'].items():
            if isinstance(value, float):
                st.markdown(f"- `{key}`: {value:.6f}")
            else:
                st.markdown(f"- `{key}`: {value}")
    
    st.markdown(f"""
    <div style="background: #8B5CF6; padding: 15px; border-radius: 8px; margin-top: 15px;">
        <p style="color: white; margin: 0; font-weight: 700;">
            🎯 Optuna Model Ready!
        </p>
        <p style="color: rgba(255,255,255,0.8); margin: 5px 0 0 0; font-size: 0.9rem;">
            Trials completed: {result['n_trials']} per model<br>
            Train: {result['n_train']:,} | Val: {result['n_val']:,} | Test: {result['n_test']:,} samples<br>
            Date range: {result['data_range']['train_start'][:10]} → {result['data_range']['test_end'][:10]}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.balloons()


__all__ = ['render_training_section']
