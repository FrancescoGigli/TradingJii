import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import glob
from PIL import Image
import numpy as np

# Define paths
BASE_DIR = os.path.join('logs', 'backtest', 'batch')
SUMMARY_FILE = os.path.join(BASE_DIR, 'summary.csv')

st.set_page_config(layout="wide", page_title="Batch Backtest Dashboard", page_icon="📈")

# Add custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 42px;
        font-weight: bold;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 20px;
    }
    .section-header {
        font-size: 24px;
        font-weight: bold;
        color: #1E88E5;
        margin-top: 20px;
        margin-bottom: 10px;
        border-bottom: 2px solid #1E88E5;
        padding-bottom: 5px;
    }
    .metric-container {
        background-color: #f9f9f9;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #ddd;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }
    .metric-container:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .metric-title {
        font-weight: bold;
        font-size: 16px;
        color: #444;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #1E88E5;
    }
    .metric-unit {
        font-size: 14px;
        color: #777;
    }
    .stPlotlyChart {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 10px;
        background-color: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .trade-positive {
        color: #4CAF50;
        font-weight: bold;
    }
    .trade-negative {
        color: #F44336;
        font-weight: bold;
    }
    .config-card {
        background-color: #f0f7ff;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #1E88E5;
        margin-bottom: 15px;
    }
    .info-tooltip {
        color: #1E88E5;
        cursor: help;
    }
    /* Table styling */
    .dataframe {
        border-collapse: collapse;
        width: 100%;
    }
    .dataframe th {
        background-color: #1E88E5;
        color: white;
        padding: 8px;
        text-align: left;
    }
    .dataframe td {
        padding: 8px;
        border-bottom: 1px solid #ddd;
    }
    .dataframe tr:nth-child(even) {
        background-color: #f2f2f2;
    }
    .dataframe tr:hover {
        background-color: #e6f2ff;
    }
</style>
""", unsafe_allow_html=True)

# Main header with animation
st.markdown("""
<div class='main-header'>📊 Batch Backtest Dashboard</div>
<div style='text-align:center; margin-bottom:20px;'>
    <span style='color:#777; font-style:italic;'>Visualizzazione completa dei risultati di backtest</span>
</div>
""", unsafe_allow_html=True)

# Sidebar configuration
st.sidebar.title("Dashboard Controls")

# Load data
@st.cache_data
def load_data(path):
    if os.path.exists(path):
        df = pd.read_csv(path)
        # Ensure numeric types for relevant columns
        numeric_cols = ['total_return', 'win_rate', 'sharpe_ratio', 'max_drawdown', 'profit_factor', 'take_profit_pct', 'stop_loss_pct', 'leverage']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    return pd.DataFrame()

# Load trade data if available
@st.cache_data
def load_trade_data(symbol, timeframe):
    pattern = os.path.join(BASE_DIR, f"trades_{symbol.replace('/', '_').replace(':USDT', '')}_{timeframe}_*.csv")
    files = glob.glob(pattern)
    
    if files:
        latest_file = max(files, key=os.path.getctime)
        trades_df = pd.read_csv(latest_file)
        return trades_df
    return None

df = load_data(SUMMARY_FILE)

if df.empty:
    st.error("⚠️ No backtest summary data found. Please run batch_backtest.py first.")
else:
    # Display view mode selector
    view_mode = st.sidebar.radio("Select View Mode", ["Overall Summary", "Parameter Analysis", "Performance Charts", "Detailed Results"])
    
    if view_mode == "Overall Summary":
        st.markdown("<div class='section-header'>📊 Overall Performance Summary</div>", unsafe_allow_html=True)
        
        # Calculate additional statistics
        best_return = df['total_return'].max()
        worst_return = df['total_return'].min()
        best_combination = df.loc[df['total_return'].idxmax()]
        worst_combination = df.loc[df['total_return'].idxmin()]
        
        # Display key metrics in a 2x4 grid
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("<div class='metric-container'><div class='metric-title'>Total Backtests</div><div class='metric-value'>{}</div><div class='metric-unit'>combinations</div></div>".format(len(df)), unsafe_allow_html=True)
        
        with col2:
            avg_return = df['total_return'].mean().round(2)
            color = "green" if avg_return > 0 else "red"
            st.markdown("<div class='metric-container'><div class='metric-title'>Avg. Total Return</div><div class='metric-value' style='color:{};'>{}</div><div class='metric-unit'>%</div></div>".format(color, avg_return), unsafe_allow_html=True)
        
        with col3:
            st.markdown("<div class='metric-container'><div class='metric-title'>Avg. Win Rate</div><div class='metric-value'>{}</div><div class='metric-unit'>%</div></div>".format(df['win_rate'].mean().round(2)), unsafe_allow_html=True)
        
        with col4:
            st.markdown("<div class='metric-container'><div class='metric-title'>Avg. Max Drawdown</div><div class='metric-value'>{}</div><div class='metric-unit'>%</div></div>".format(df['max_drawdown'].mean().round(2)), unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("<div class='metric-container'><div class='metric-title'>Best Return</div><div class='metric-value' style='color:green;'>{}</div><div class='metric-unit'>%</div></div>".format(best_return.round(2)), unsafe_allow_html=True)
        
        with col2:
            st.markdown("<div class='metric-container'><div class='metric-title'>Worst Return</div><div class='metric-value' style='color:red;'>{}</div><div class='metric-unit'>%</div></div>".format(worst_return.round(2)), unsafe_allow_html=True)
        
        with col3:
            st.markdown("<div class='metric-container'><div class='metric-title'>Avg. Sharpe Ratio</div><div class='metric-value'>{}</div><div class='metric-unit'></div></div>".format(df['sharpe_ratio'].mean().round(2)), unsafe_allow_html=True)
        
        with col4:
            st.markdown("<div class='metric-container'><div class='metric-title'>Avg. Profit Factor</div><div class='metric-value'>{}</div><div class='metric-unit'></div></div>".format(df['profit_factor'].mean().round(2)), unsafe_allow_html=True)
        
        # Best and Worst Combinations
        st.markdown("<div class='section-header'>🏆 Best & Worst Combinations</div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Best Combination")
            st.info(f"""
            • **Symbol**: {best_combination['symbol']}
            • **Timeframe**: {best_combination['timeframe']}
            • **Take Profit**: {best_combination['take_profit_pct']}%
            • **Stop Loss**: {best_combination['stop_loss_pct']}%
            • **Leverage**: {best_combination['leverage']}x
            • **Return**: {best_combination['total_return']:.2f}%
            • **Win Rate**: {best_combination['win_rate']:.2f}%
            • **Sharpe Ratio**: {best_combination['sharpe_ratio']:.2f}
            • **Max Drawdown**: {best_combination['max_drawdown']:.2f}%
            """)
            
        with col2:
            st.subheader("Worst Combination")
            st.error(f"""
            • **Symbol**: {worst_combination['symbol']}
            • **Timeframe**: {worst_combination['timeframe']}
            • **Take Profit**: {worst_combination['take_profit_pct']}%
            • **Stop Loss**: {worst_combination['stop_loss_pct']}%
            • **Leverage**: {worst_combination['leverage']}x
            • **Return**: {worst_combination['total_return']:.2f}%
            • **Win Rate**: {worst_combination['win_rate']:.2f}%
            • **Sharpe Ratio**: {worst_combination['sharpe_ratio']:.2f}
            • **Max Drawdown**: {worst_combination['max_drawdown']:.2f}%
            """)
        
        # Distribution of returns
        st.markdown("<div class='section-header'>📝 Return Distribution</div>", unsafe_allow_html=True)
        
        fig = px.histogram(df, x="total_return", nbins=20, 
                         title="Distribution of Total Returns",
                         color_discrete_sequence=['#1E88E5'])
        fig.add_vline(x=0, line_dash="dash", line_color="red")
        fig.update_layout(xaxis_title="Total Return (%)", yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True)
        
    elif view_mode == "Parameter Analysis":
        st.markdown("<div class='section-header'>🔍 Parameter Analysis</div>", unsafe_allow_html=True)
        
        # Parameter impact analysis
        col1, col2 = st.columns(2)
        
        with col1:
            # Impact of Take Profit
            tp_analysis = df.groupby('take_profit_pct').agg({
                'total_return': 'mean',
                'win_rate': 'mean',
                'sharpe_ratio': 'mean',
                'max_drawdown': 'mean'
            }).reset_index()
            
            fig = px.line(tp_analysis, x='take_profit_pct', y=['total_return', 'win_rate'],
                        title="Impact of Take Profit on Performance",
                        labels={'take_profit_pct': 'Take Profit (%)', 'value': 'Value', 'variable': 'Metric'})
            fig.update_layout(legend_title_text='Metric')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Impact of Stop Loss
            sl_analysis = df.groupby('stop_loss_pct').agg({
                'total_return': 'mean',
                'win_rate': 'mean',
                'sharpe_ratio': 'mean',
                'max_drawdown': 'mean'
            }).reset_index()
            
            fig = px.line(sl_analysis, x='stop_loss_pct', y=['total_return', 'win_rate'],
                        title="Impact of Stop Loss on Performance",
                        labels={'stop_loss_pct': 'Stop Loss (%)', 'value': 'Value', 'variable': 'Metric'})
            fig.update_layout(legend_title_text='Metric')
            st.plotly_chart(fig, use_container_width=True)
        
        # Heatmap for parameter combinations
        st.markdown("<div class='section-header'>🔥 Parameter Combination Heatmap</div>", unsafe_allow_html=True)
        
        # Create pivot table for TP vs SL with avg return
        pivot_df = df.pivot_table(
            values='total_return', 
            index='take_profit_pct', 
            columns='stop_loss_pct', 
            aggfunc='mean'
        )
        
        fig = px.imshow(pivot_df, 
                      labels=dict(x="Stop Loss (%)", y="Take Profit (%)", color="Avg. Return (%)"),
                      x=pivot_df.columns, 
                      y=pivot_df.index,
                      color_continuous_scale='RdBu_r',
                      aspect="auto")
        fig.update_layout(title="Average Return by TP/SL Combination")
        st.plotly_chart(fig, use_container_width=True)
        
        # Timeframe comparison
        st.markdown("<div class='section-header'>⏱️ Timeframe Comparison</div>", unsafe_allow_html=True)
        
        timeframe_analysis = df.groupby('timeframe').agg({
            'total_return': 'mean',
            'win_rate': 'mean',
            'sharpe_ratio': 'mean',
            'max_drawdown': 'mean'
        }).reset_index()
        
        fig = px.bar(timeframe_analysis, x='timeframe', y='total_return',
                   title="Average Return by Timeframe",
                   labels={'timeframe': 'Timeframe', 'total_return': 'Avg. Return (%)'},
                   color='total_return',
                   color_continuous_scale='Bluered_r')
        st.plotly_chart(fig, use_container_width=True)
        
    elif view_mode == "Performance Charts":
        st.markdown("<div class='section-header'>📈 Performance Charts</div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_symbol = st.selectbox("Select Symbol", ['All'] + df['symbol'].unique().tolist())
        
        with col2:
            selected_timeframe = st.selectbox("Select Timeframe", ['All'] + df['timeframe'].unique().tolist())
        
        # Filter data based on selections
        filtered_data = df.copy()
        if selected_symbol != 'All':
            filtered_data = filtered_data[filtered_data['symbol'] == selected_symbol]
        if selected_timeframe != 'All':
            filtered_data = filtered_data[filtered_data['timeframe'] == selected_timeframe]
        
        # Display equity charts if available and specific symbol/timeframe is selected
        if selected_symbol != 'All' and selected_timeframe != 'All':
            symbol_safe = selected_symbol.replace('/', '_').replace(':USDT', '')
            equity_chart_path = os.path.join(BASE_DIR, f"equity_{symbol_safe}_{selected_timeframe}.png")
            trade_chart_path = os.path.join(BASE_DIR, f"backtest_{symbol_safe}_{selected_timeframe}.png")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if os.path.exists(equity_chart_path):
                    st.subheader("Equity Curve")
                    st.image(equity_chart_path, caption=f"Equity curve for {selected_symbol} ({selected_timeframe})")
                else:
                    st.warning(f"No equity chart found for {selected_symbol} ({selected_timeframe})")
            
            with col2:
                if os.path.exists(trade_chart_path):
                    st.subheader("Price and Trades")
                    st.image(trade_chart_path, caption=f"Trades for {selected_symbol} ({selected_timeframe})")
                else:
                    st.warning(f"No trade chart found for {selected_symbol} ({selected_timeframe})")
            
            # Load and display trade data if available
            trades_df = load_trade_data(selected_symbol, selected_timeframe)
            if trades_df is not None and not trades_df.empty:
                st.subheader("Trade History")
                
                # Show backtest configuration information
                st.markdown("<div class='section-header'>⚙️ Backtest Configuration</div>", unsafe_allow_html=True)
                
                # Extract configuration data for this backtest from the dataframe
                config_data = df[(df['symbol'] == selected_symbol) & (df['timeframe'] == selected_timeframe)].iloc[0]
                
                st.markdown(
                    f"""
                    <div class="config-card">
                        <h3>Trading Parameters</h3>
                        <table style="width:100%">
                            <tr>
                                <td><strong>Symbol:</strong></td>
                                <td>{selected_symbol}</td>
                                <td><strong>Timeframe:</strong></td>
                                <td>{selected_timeframe}</td>
                            </tr>
                            <tr>
                                <td><strong>Take Profit:</strong></td>
                                <td>{config_data['take_profit_pct']}%</td>
                                <td><strong>Stop Loss:</strong></td>
                                <td>{config_data['stop_loss_pct']}%</td>
                            </tr>
                            <tr>
                                <td><strong>Leverage:</strong></td>
                                <td>{config_data['leverage']}x</td>
                                <td><strong>Duration:</strong></td>
                                <td>{config_data['avg_trade_duration']} bars (avg)</td>
                            </tr>
                        </table>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                # Check if required columns exist in trades_df before creating PnL visualization
                required_cols = ['entry_time', 'pnl', 'side', 'entry_price', 'exit_price']
                if all(col in trades_df.columns for col in required_cols):
                    # Calculate pnl_percent if not already present
                    if 'pnl_percent' not in trades_df.columns:
                        trades_df['pnl_percent'] = abs(trades_df['pnl']) * 100 / trades_df['entry_price']
                    
                    # Enhanced trade visualization
                    st.markdown("<div class='section-header'>💹 Trade PnL History</div>", unsafe_allow_html=True)
                    
                    # Create a more informative scatter plot
                    fig = px.scatter(
                        trades_df, 
                        x='entry_time', 
                        y='pnl', 
                        color='side',
                        color_discrete_map={'BUY': '#4CAF50', 'SELL': '#F44336'},
                        size='pnl_percent',
                        hover_data=[
                            'entry_price', 
                            'exit_price', 
                            'pnl_percent', 
                            'exit_reason',
                            'duration'
                        ],
                        title=f"Trade PnL History - {selected_symbol} ({selected_timeframe})"
                    )
                    
                    # Add a zero line to better visualize winning vs losing trades
                    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
                    
                    # Update layout for better visualization
                    fig.update_layout(
                        hovermode='closest',
                        xaxis_title="Entry Time",
                        yaxis_title="Profit/Loss",
                        height=500,
                        legend_title="Trade Side"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Add distribution of trade returns
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Distribution of trade returns
                        fig = px.histogram(
                            trades_df, 
                            x='pnl',
                            nbins=30, 
                            color_discrete_sequence=['#1E88E5'],
                            title="Distribution of Trade PnL"
                        )
                        fig.add_vline(x=0, line_dash="dash", line_color="gray")
                        fig.update_layout(
                            xaxis_title="Profit/Loss",
                            yaxis_title="Number of Trades"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        # Show PnL by trade side
                        fig = px.box(
                            trades_df,
                            x='side',
                            y='pnl',
                            color='side',
                            color_discrete_map={'BUY': '#4CAF50', 'SELL': '#F44336'},
                            title="PnL by Trade Side"
                        )
                        fig.update_layout(
                            xaxis_title="Trade Side",
                            yaxis_title="Profit/Loss"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Enhanced trade statistics
                    st.markdown("<div class='section-header'>📊 Detailed Trade Analytics</div>", unsafe_allow_html=True)
                    
                    winning_trades = trades_df[trades_df['pnl'] > 0]
                    losing_trades = trades_df[trades_df['pnl'] < 0]
                    
                    # First row of metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.markdown("<div class='metric-container'><div class='metric-title'>Total Trades</div><div class='metric-value'>{}</div><div class='metric-unit'>trades</div></div>".format(len(trades_df)), unsafe_allow_html=True)
                    with col2:
                        win_rate = len(winning_trades) / len(trades_df) * 100 if len(trades_df) > 0 else 0
                        st.markdown("<div class='metric-container'><div class='metric-title'>Win Rate</div><div class='metric-value'>{:.2f}</div><div class='metric-unit'>%</div></div>".format(win_rate), unsafe_allow_html=True)
                    with col3:
                        avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
                        st.markdown("<div class='metric-container'><div class='metric-title'>Avg. Winning Trade</div><div class='metric-value' style='color:#4CAF50;'>{:.2f}</div><div class='metric-unit'></div></div>".format(avg_win), unsafe_allow_html=True)
                    with col4:
                        avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0
                        st.markdown("<div class='metric-container'><div class='metric-title'>Avg. Losing Trade</div><div class='metric-value' style='color:#F44336;'>{:.2f}</div><div class='metric-unit'></div></div>".format(avg_loss), unsafe_allow_html=True)
                    
                    # Second row of metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        profit_factor = abs(winning_trades['pnl'].sum() / losing_trades['pnl'].sum()) if len(losing_trades) > 0 and losing_trades['pnl'].sum() != 0 else 0
                        st.markdown("<div class='metric-container'><div class='metric-title'>Profit Factor</div><div class='metric-value'>{:.2f}</div></div>".format(profit_factor), unsafe_allow_html=True)
                    with col2:
                        max_win = winning_trades['pnl'].max() if len(winning_trades) > 0 else 0
                        st.markdown("<div class='metric-container'><div class='metric-title'>Largest Win</div><div class='metric-value' style='color:#4CAF50;'>{:.2f}</div></div>".format(max_win), unsafe_allow_html=True)
                    with col3:
                        max_loss = losing_trades['pnl'].min() if len(losing_trades) > 0 else 0
                        st.markdown("<div class='metric-container'><div class='metric-title'>Largest Loss</div><div class='metric-value' style='color:#F44336;'>{:.2f}</div></div>".format(max_loss), unsafe_allow_html=True)
                    with col4:
                        avg_duration = trades_df['duration'].mean() if 'duration' in trades_df else 0
                        st.markdown("<div class='metric-container'><div class='metric-title'>Avg. Trade Duration</div><div class='metric-value'>{:.1f}</div><div class='metric-unit'>bars</div></div>".format(avg_duration), unsafe_allow_html=True)
                
                # Display enhanced trade table with coloring
                st.markdown("<div class='section-header'>📋 Trade Log</div>", unsafe_allow_html=True)
                
                # Format the trades dataframe for better display
                if not trades_df.empty:
                    display_trades = trades_df.copy()
                    
                    # Format columns for better display
                    if 'pnl' in display_trades:
                        # Format PnL with colored values
                        def color_pnl(val):
                            color = 'green' if val > 0 else 'red' if val < 0 else 'black'
                            return f'color: {color}; font-weight: bold'
                        
                        # Apply the styling
                        styled_trades = display_trades.style.applymap(color_pnl, subset=['pnl'])
                        
                        # Display the styled dataframe
                        st.dataframe(styled_trades, use_container_width=True)
                    else:
                        st.dataframe(display_trades, use_container_width=True)
        else:
            # Show comparison charts for multiple symbols/timeframes
            symbols_to_compare = df['symbol'].unique() if selected_symbol == 'All' else [selected_symbol]
            timeframes_to_compare = df['timeframe'].unique() if selected_timeframe == 'All' else [selected_timeframe]
            
            comparison_data = []
            for symbol in symbols_to_compare:
                for tf in timeframes_to_compare:
                    row = df[(df['symbol'] == symbol) & (df['timeframe'] == tf)]
                    if not row.empty:
                        comparison_data.append({
                            'symbol': symbol,
                            'timeframe': tf,
                            'total_return': row['total_return'].values[0],
                            'win_rate': row['win_rate'].values[0],
                            'sharpe_ratio': row['sharpe_ratio'].values[0],
                            'max_drawdown': row['max_drawdown'].values[0]
                        })
            
            if comparison_data:
                comparison_df = pd.DataFrame(comparison_data)
                
                # Create comparison charts
                fig = px.bar(comparison_df, x='symbol', y='total_return', color='timeframe',
                           barmode='group',
                           title="Return Comparison by Symbol and Timeframe",
                           labels={'symbol': 'Symbol', 'total_return': 'Total Return (%)', 'timeframe': 'Timeframe'})
                st.plotly_chart(fig, use_container_width=True)
                
                # Radar chart for multi-metric comparison if we have a small number of combinations
                if len(comparison_df) <= 5:  # Limit to 5 for readability
                    categories = ['total_return', 'win_rate', 'sharpe_ratio']
                    fig = go.Figure()
                    
                    for index, row in comparison_df.iterrows():
                        fig.add_trace(go.Scatterpolar(
                            r=[row['total_return'], row['win_rate'], row['sharpe_ratio']],
                            theta=categories,
                            fill='toself',
                            name=f"{row['symbol']} ({row['timeframe']})"
                        ))
                    
                    fig.update_layout(
                        polar=dict(
                            radialaxis=dict(
                                visible=True,
                            )),
                        showlegend=True,
                        title="Multi-Metric Comparison"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No comparison data available for the selected filters.")
    
    # Detailed Results mode (always available with filters)
    if view_mode == "Detailed Results":
        st.markdown("<div class='section-header'>🧮 Detailed Results and Filters</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='section-header'>🔍 Filter Results</div>", unsafe_allow_html=True)
        
        # Put filters in the sidebar
        st.sidebar.markdown("### 🔍 Data Filters")
        
        # Filters
        all_symbols = ['All'] + df['symbol'].unique().tolist()
        selected_symbol = st.sidebar.selectbox("Select Symbol", all_symbols)

        all_timeframes = ['All'] + df['timeframe'].unique().tolist()
        selected_timeframe = st.sidebar.selectbox("Select Timeframe", all_timeframes)

        # Dynamic sliders for TP, SL, Leverage based on available data
        # Ensure min and max values are different for sliders
        min_tp, max_tp = df['take_profit_pct'].min(), df['take_profit_pct'].max()
        if min_tp == max_tp:
            min_tp = min_tp - 0.1 if min_tp > 0.1 else 0
            max_tp = max_tp + 0.1
        selected_tp = st.sidebar.slider("Take Profit (%)", min_tp, max_tp, (min_tp, max_tp))

        min_sl, max_sl = df['stop_loss_pct'].min(), df['stop_loss_pct'].max()
        if min_sl == max_sl:
            min_sl = min_sl - 0.1 if min_sl > 0.1 else 0
            max_sl = max_sl + 0.1
        selected_sl = st.sidebar.slider("Stop Loss (%)", min_sl, max_sl, (min_sl, max_sl))

        min_leverage, max_leverage = float(df['leverage'].min()), float(df['leverage'].max())
        if min_leverage == max_leverage:
            min_leverage = min_leverage - 1 if min_leverage > 1 else 0
            max_leverage = max_leverage + 1
        selected_leverage = st.sidebar.slider("Leverage", min_leverage, max_leverage, (min_leverage, max_leverage))

        # Additional metric filters in expandable section
        with st.sidebar.expander("Advanced Filters"):
            # Add return filter
            min_return, max_return = float(df['total_return'].min()), float(df['total_return'].max())
            if min_return == max_return:
                min_return = float(min_return - 1)
                max_return = float(max_return + 1)
            selected_return = st.slider("Total Return (%)", float(min_return), float(max_return), (float(min_return), float(max_return)))
            
            # Add win rate filter
            min_wr, max_wr = float(df['win_rate'].min()), float(df['win_rate'].max())
            if min_wr == max_wr:
                min_wr = float(min_wr - 5) if min_wr > 5 else 0.0
                max_wr = float(max_wr + 5) if max_wr < 95 else 100.0
            selected_wr = st.slider("Win Rate (%)", float(min_wr), float(max_wr), (float(min_wr), float(max_wr)))

        filtered_df = df.copy()

        if selected_symbol != 'All':
            filtered_df = filtered_df[filtered_df['symbol'] == selected_symbol]
        if selected_timeframe != 'All':
            filtered_df = filtered_df[filtered_df['timeframe'] == selected_timeframe]
        
        filtered_df = filtered_df[
            (filtered_df['take_profit_pct'] >= selected_tp[0]) & (filtered_df['take_profit_pct'] <= selected_tp[1]) &
            (filtered_df['stop_loss_pct'] >= selected_sl[0]) & (filtered_df['stop_loss_pct'] <= selected_sl[1]) &
            (filtered_df['leverage'] >= selected_leverage[0]) & (filtered_df['leverage'] <= selected_leverage[1])
        ]

        # Apply advanced filters if they exist
        if 'selected_return' in locals():
            filtered_df = filtered_df[
                (filtered_df['total_return'] >= selected_return[0]) & 
                (filtered_df['total_return'] <= selected_return[1])
            ]
        if 'selected_wr' in locals():
            filtered_df = filtered_df[
                (filtered_df['win_rate'] >= selected_wr[0]) & 
                (filtered_df['win_rate'] <= selected_wr[1])
            ]

        # Show filtered data with color coding
        st.subheader("Filtered Results Table")
        
        # Style the dataframe
        def highlight_profit(val):
            color = 'green' if val > 0 else 'red' if val < 0 else 'black'
            return f'color: {color}'
        
        # Check if filtered_df has any rows
        if not filtered_df.empty:
            # Format and display the dataframe with better styling
            display_df = filtered_df.copy()
            # Round numeric columns for better display
            numeric_cols = ['total_return', 'win_rate', 'sharpe_ratio', 'max_drawdown', 'profit_factor']
            display_df[numeric_cols] = display_df[numeric_cols].round(2)
            
            # Apply styling
            styled_df = display_df.style.applymap(highlight_profit, subset=['total_return'])
            
            st.dataframe(styled_df, use_container_width=True)
            
            # Scatter plot matrix for multi-parameter visualization
            st.subheader("Multi-Parameter Visualization")
            
            dimensions = ['total_return', 'win_rate', 'sharpe_ratio', 'max_drawdown', 
                        'take_profit_pct', 'stop_loss_pct', 'leverage']
            
            fig = px.scatter_matrix(
                filtered_df,
                dimensions=dimensions,
                color='total_return',
                symbol='timeframe',
                title="Parameter Correlation Matrix",
                color_continuous_scale='RdBu_r'
            )
            fig.update_layout(width=1000, height=800)
            st.plotly_chart(fig, use_container_width=True)
            
            # 3D visualization
            st.subheader("3D Parameter Visualization")
            
            fig = px.scatter_3d(
                filtered_df, 
                x='take_profit_pct',
                y='stop_loss_pct',
                z='total_return',
                color='timeframe',
                size='win_rate',
                hover_data=['symbol', 'leverage', 'sharpe_ratio'],
                title="3D View: TP vs SL vs Return"
            )
            fig.update_layout(width=800, height=600)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No results to display for the selected filters.")
