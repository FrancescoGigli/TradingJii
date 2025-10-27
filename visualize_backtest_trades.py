#!/usr/bin/env python3
"""
📊 BACKTEST TRADES VISUALIZER

Visualizza grafici interattivi HTML dei trade del backtest.
Crea UN FILE HTML SEPARATO per ogni simbolo (più veloce!)

UTILIZZO:
    python visualize_backtest_trades.py
"""

import json
import plotly.graph_objects as go
import pandas as pd
from pathlib import Path
from termcolor import colored
import warnings

# Silence pandas FutureWarning
warnings.filterwarnings('ignore', category=FutureWarning)

def load_visualization_data(file_path="backtest_visualization_data.json"):
    """Carica dati visualizzazione backtest"""
    if not Path(file_path).exists():
        print(colored(f"❌ File {file_path} not found!", "red"))
        print(colored("   Run: python backtest_calibration.py first", "yellow"))
        return None
    
    with open(file_path, 'r') as f:
        return json.load(f)

def create_separate_chart(symbol, data, output_dir='visualizations'):
    """Crea grafico separato per un simbolo (VELOCE!)"""
    
    # Create single chart
    fig = go.Figure()
    
    # Convert candles to DataFrame
    candles_df = pd.DataFrame(data['candles'])
    
    # Handle index column
    if 'index' in candles_df.columns:
        candles_df['index'] = pd.to_datetime(candles_df['index'])
    else:
        if candles_df.index.name or len(candles_df.columns) > 5:
            candles_df = candles_df.reset_index()
            candles_df['index'] = pd.to_datetime(candles_df.iloc[:, 0])
        else:
            candles_df['index'] = pd.date_range(start='2025-07-01', periods=len(candles_df), freq='15T')
    
    # Filtra candele per periodo trade (solo ultimi 3 mesi dal primo trade)
    if data['trades']:
        first_trade_date = pd.to_datetime(data['trades'][0]['entry_date'])
        last_trade_date = pd.to_datetime(data['trades'][-1]['exit_date'])
        
        # Aggiungi margine: 1 settimana prima e dopo
        start_date = first_trade_date - pd.Timedelta(days=7)
        end_date = last_trade_date + pd.Timedelta(days=7)
        
        # Filtra candele
        candles_df = candles_df[
            (candles_df['index'] >= start_date) & 
            (candles_df['index'] <= end_date)
        ]
    
    # Add candlestick (PIÙ VISIBILE!)
    fig.add_trace(go.Candlestick(
        x=candles_df['index'],
        open=candles_df['open'],
        high=candles_df['high'],
        low=candles_df['low'],
        close=candles_df['close'],
        name=symbol,
        showlegend=False,
        increasing=dict(line=dict(color='#26a69a', width=2), fillcolor='#26a69a'),
        decreasing=dict(line=dict(color='#ef5350', width=2), fillcolor='#ef5350'),
        opacity=1.0
    ))
    
    # Add trades (marker PIÙ PICCOLI e trasparenti)
    for idx, trade in enumerate(data['trades']):
        entry_time = pd.to_datetime(trade['entry_date'])
        exit_time = pd.to_datetime(trade['exit_date'])
        entry_price = trade['entry_price']
        exit_price = trade['exit_price']
        pnl = trade['pnl_pct']
        result = trade['result']
        xgb_conf = trade['xgb_confidence']
        rl_conf = trade['rl_confidence']
        
        # Entry marker (PIÙ PICCOLO e semi-trasparente)
        fig.add_trace(go.Scatter(
            x=[entry_time], y=[entry_price], mode='markers',
            marker=dict(symbol='triangle-up', size=7, color='rgba(0, 255, 0, 0.6)', line=dict(width=0.5, color='darkgreen')),
            name='Entry', showlegend=False,
            hovertemplate=f"<b>ENTRY #{idx+1}</b><br>Price: ${entry_price:,.2f}<br>XGB: {xgb_conf*100:.1f}%<br>RL: {rl_conf*100:.1f}%<br><extra></extra>"
        ))
        
        # Exit marker (PIÙ PICCOLO e semi-trasparente)
        exit_color = 'rgba(0, 255, 0, 0.7)' if result == 'WIN' else 'rgba(255, 0, 0, 0.7)'
        exit_border = 'darkgreen' if result == 'WIN' else 'darkred'
        fig.add_trace(go.Scatter(
            x=[exit_time], y=[exit_price], mode='markers',
            marker=dict(symbol='triangle-down', size=7, color=exit_color, line=dict(width=0.5, color=exit_border)),
            name='Exit', showlegend=False,
            hovertemplate=f"<b>EXIT #{idx+1} ({result})</b><br>Price: ${exit_price:,.2f}<br>P&L: {pnl:+.2f}%<br>Duration: {trade['duration_hours']:.1f}h<br>Reason: {trade.get('exit_reason', 'N/A')}<br><extra></extra>"
        ))
        
        # Lines (più sottili)
        fig.add_shape(type="line", x0=entry_time, x1=exit_time, y0=entry_price, y1=entry_price,
                     line=dict(color="blue", width=0.5, dash="dot"), opacity=0.5)
        
        # Annotazioni SOLO per trade significativi (|PnL| > 5%)
        if abs(pnl) > 5.0:
            fig.add_annotation(x=exit_time, y=exit_price, text=f"{pnl:+.1f}%",
                              showarrow=True, arrowhead=2, arrowsize=0.8, arrowwidth=1.5, arrowcolor=exit_color,
                              ax=30 if result == 'WIN' else -30, ay=-20 if result == 'WIN' else 20,
                              font=dict(size=8, color=exit_color, family="Arial"),
                              bgcolor="rgba(255,255,255,0.8)", bordercolor=exit_color, borderwidth=1, opacity=0.9)
    
    # Layout con stile TradingView (dark theme)
    wins = sum(1 for t in data['trades'] if t['result'] == 'WIN')
    losses = len(data['trades']) - wins
    win_rate = (wins / len(data['trades']) * 100) if data['trades'] else 0
    
    # Calcola timeframe dalle candele (differenza media tra candele consecutive)
    if len(candles_df) > 1:
        time_diffs = candles_df['index'].diff().dropna()
        avg_diff_minutes = time_diffs.dt.total_seconds().mean() / 60
        
        if avg_diff_minutes < 60:
            timeframe_str = f"{int(avg_diff_minutes)}m"
        elif avg_diff_minutes < 1440:
            timeframe_str = f"{int(avg_diff_minutes/60)}h"
        else:
            timeframe_str = f"{int(avg_diff_minutes/1440)}d"
    else:
        timeframe_str = "15m"  # default
    
    fig.update_layout(
        title=dict(
            text=f"{symbol} ({timeframe_str}) | {len(data['trades'])} Trades | WR: {win_rate:.1f}% | Wins: {wins} | Losses: {losses}", 
            font=dict(size=16, family="Arial", color='white'),
            x=0.5, xanchor='center'
        ),
        height=700,
        showlegend=False,
        hovermode='x unified',
        template='plotly_dark',
        plot_bgcolor='#0e1117',
        paper_bgcolor='#0e1117',
        font=dict(color='white', size=12),
        xaxis=dict(
            title="Date / Time",
            gridcolor='#1e2530',
            showgrid=True,
            zeroline=False,
            color='white'
        ),
        yaxis=dict(
            title="Price (USDT)",
            gridcolor='#1e2530',
            showgrid=True,
            zeroline=False,
            side='right',
            color='white'
        ),
        margin=dict(l=50, r=50, t=80, b=50)
    )
    
    # Update candlestick colors per stile TradingView
    fig.update_traces(
        increasing_line_color='#26a69a',
        increasing_fillcolor='#26a69a',
        decreasing_line_color='#ef5350',
        decreasing_fillcolor='#ef5350',
        selector=dict(type='candlestick')
    )
    
    # Save
    safe_name = symbol.replace('/', '_').replace(':', '_')
    output_file = Path(output_dir) / f"{safe_name}_trades.html"
    fig.write_html(str(output_file))
    
    return output_file


def create_interactive_charts(viz_data):
    """Crea grafici interattivi SEPARATI per ogni simbolo (VELOCE!)"""
    
    symbols = list(viz_data.keys())
    num_symbols = len(symbols)
    total_trades = sum(len(viz_data[s]['trades']) for s in symbols)
    
    print(colored(f"\n📊 Creating {num_symbols} separate chart files...", "yellow"))
    print(colored(f"   Total trades: {total_trades}", "yellow"))
    
    Path('visualizations').mkdir(exist_ok=True)
    
    output_files = []
    
    # Process each symbol separately
    for idx, symbol in enumerate(symbols, 1):
        data = viz_data[symbol]
        
        print(colored(f"   [{idx}/{num_symbols}] Generating {symbol}...", "cyan"), end=" ", flush=True)
        
        output_file = create_separate_chart(symbol, data)
        output_files.append(output_file)
        
        print(colored(f"✓ {output_file.name}", "green"), flush=True)
    
    return output_files


def print_summary(viz_data):
    """Stampa summary dei trade visualizzati"""
    print(colored("\n" + "="*80, "cyan"))
    print(colored("📊 BACKTEST VISUALIZATION SUMMARY", "cyan", attrs=['bold']))
    print(colored("="*80, "cyan"))
    
    for symbol, data in viz_data.items():
        trades = data['trades']
        num_trades = len(trades)
        
        if num_trades == 0:
            continue
        
        wins = sum(1 for t in trades if t['result'] == 'WIN')
        losses = num_trades - wins
        win_rate = (wins / num_trades * 100) if num_trades > 0 else 0
        
        total_pnl = sum(t['pnl_pct'] for t in trades)
        avg_pnl = total_pnl / num_trades if num_trades > 0 else 0
        
        avg_xgb_conf = sum(t['xgb_confidence'] for t in trades) / num_trades * 100
        avg_rl_conf = sum(t['rl_confidence'] for t in trades) / num_trades * 100
        
        print(f"\n{colored(symbol, 'yellow', attrs=['bold'])}")
        print(f"  Trades: {num_trades} ({wins}W/{losses}L)")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Total P&L: {total_pnl:+.2f}%")
        print(f"  Avg P&L: {avg_pnl:+.2f}%")
        print(f"  Avg XGB Conf: {avg_xgb_conf:.1f}%")
        print(f"  Avg RL Conf: {avg_rl_conf:.1f}%")
    
    print(colored("\n" + "="*80, "cyan"))

def main():
    """Main entry point"""
    print(colored("\n🎨 BACKTEST TRADES VISUALIZER (SEPARATE FILES)", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan"))
    
    # Load data
    viz_data = load_visualization_data()
    
    if not viz_data:
        return
    
    # Print summary
    print_summary(viz_data)
    
    # Create interactive charts (separate files)
    output_files = create_interactive_charts(viz_data)
    
    print(colored("\n" + "="*80, "green"))
    print(colored("✅ ALL CHARTS GENERATED!", "green", attrs=['bold']))
    print(colored("="*80, "green"))
    print(colored("\n📁 Generated files:", "cyan"))
    for f in output_files:
        print(colored(f"   • {f.name}", "yellow"))
    
    print(colored("\n💡 Open any file in browser to explore trades!", "cyan"))
    print(colored(f"   Example: start visualizations\\{output_files[0].name}", "yellow"))

if __name__ == "__main__":
    main()
