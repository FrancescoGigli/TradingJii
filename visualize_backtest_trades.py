#!/usr/bin/env python3
"""
📊 BACKTEST TRADES VISUALIZER

Visualizza grafici interattivi HTML dei trade del backtest.
Crea UN FILE HTML SEPARATO per ogni simbolo.

NUOVO: Scarica candele on-demand da Bybit invece di usare dati salvati.

UTILIZZO:
    python visualize_backtest_trades.py
"""

import json
import plotly.graph_objects as go
import pandas as pd
from pathlib import Path
from termcolor import colored
from datetime import datetime, timedelta
import warnings
import asyncio
import ccxt.async_support as ccxt
import sys

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


async def download_candles_for_visualization(symbol, timeframe, trades, viz_timeframe=None):
    """
    Scarica candele da Bybit per il periodo dei trade
    
    Args:
        symbol: Simbolo da scaricare (es. 'BTC/USDT:USDT')
        timeframe: Timeframe del backtest (es. '15m')
        trades: Lista di trade per determinare il range temporale
        viz_timeframe: Timeframe per visualizzazione (default None = usa timeframe backtest)
        
    Returns:
        DataFrame con candele OHLCV filtrate per il periodo rilevante
    """
    # Usa timeframe backtest se viz_timeframe non specificato
    if viz_timeframe is None:
        viz_timeframe = timeframe
    
    print(colored(f"      📥 Downloading {viz_timeframe} candles...", "cyan"), end=" ", flush=True)
    
    try:
        # Determina range temporale dai trade
        dates = [pd.to_datetime(t['entry_date']) for t in trades] + [pd.to_datetime(t['exit_date']) for t in trades]
        start_date = min(dates) - timedelta(days=7)  # Margine 1 settimana prima
        end_date = max(dates) + timedelta(days=7)    # Margine 1 settimana dopo
        
        # Crea exchange instance
        exchange = ccxt.bybit({'enableRateLimit': True, 'timeout': 30000})
        
        try:
            # Usa fetcher esistente per download con cache (usa viz_timeframe, non timeframe backtest)
            from fetcher import fetch_and_save_data
            df = await fetch_and_save_data(exchange, symbol, viz_timeframe)
            
            if df is None or len(df) == 0:
                print(colored("❌ No data", "red"))
                return None
            
            # Filtra per range rilevante
            df_filtered = df[(df.index >= start_date) & (df.index <= end_date)]
            
            print(colored(f"✓ {len(df_filtered)} candles", "green"))
            return df_filtered
            
        finally:
            await exchange.close()
            
    except Exception as e:
        print(colored(f"❌ Error: {str(e)}", "red"))
        return None


def create_separate_chart(symbol, candles_df, trades, timeframe, output_dir='visualizations'):
    """
    Crea grafico separato per un simbolo
    
    Args:
        symbol: Simbolo trading
        candles_df: DataFrame con candele OHLCV (già filtrato per range rilevante)
        trades: Lista di trade da visualizzare
        timeframe: Timeframe delle candele (es. '15m')
        output_dir: Directory output
        
    Returns:
        Path del file HTML generato
    """
    # Create figure
    fig = go.Figure()
    
    # Use DatetimeIndex for x-axis
    x_data = candles_df.index
    
    # Add candlestick chart
    fig.add_trace(go.Candlestick(
        x=x_data,
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
    
    # Add trade markers
    for idx, trade in enumerate(trades):
        entry_time = pd.to_datetime(trade['entry_date'])
        exit_time = pd.to_datetime(trade['exit_date'])
        entry_price = trade['entry_price']
        exit_price = trade['exit_price']
        pnl = trade['pnl_pct']
        result = trade['result']
        xgb_conf = trade['xgb_confidence']
        rl_conf = trade['rl_confidence']
        
        # Entry marker (triangolo verde su - PIÙ GRANDE E VISIBILE)
        fig.add_trace(go.Scatter(
            x=[entry_time], y=[entry_price], mode='markers',
            marker=dict(
                symbol='triangle-up', 
                size=12,  # Aumentato da 7 a 12
                color='rgb(0, 255, 0)',  # Verde brillante opaco
                line=dict(width=2, color='darkgreen')  # Bordo più spesso
            ),
            name='Entry', showlegend=False,
            hovertemplate=(f"<b>ENTRY #{idx+1}</b><br>"
                          f"Price: ${entry_price:,.2f}<br>"
                          f"XGB: {xgb_conf*100:.1f}%<br>"
                          f"RL: {rl_conf*100:.1f}%<br>"
                          f"<extra></extra>")
        ))
        
        # Exit marker (PIÙ GRANDE E CONTRASTO MAGGIORE)
        if result == 'WIN':
            exit_color = 'rgb(0, 220, 0)'  # Verde brillante
            exit_border = 'rgb(0, 100, 0)'  # Verde scuro
            line_color = 'rgba(0, 255, 0, 0.3)'  # Verde trasparente
        else:
            exit_color = 'rgb(255, 50, 50)'  # Rosso brillante e MOLTO VISIBILE
            exit_border = 'rgb(139, 0, 0)'  # Rosso scuro
            line_color = 'rgba(255, 50, 50, 0.4)'  # Rosso trasparente
        
        fig.add_trace(go.Scatter(
            x=[exit_time], y=[exit_price], mode='markers',
            marker=dict(
                symbol='triangle-down', 
                size=12,  # Aumentato da 7 a 12
                color=exit_color,
                line=dict(width=2, color=exit_border)  # Bordo più spesso
            ),
            name='Exit', showlegend=False,
            hovertemplate=(f"<b>EXIT #{idx+1} ({result})</b><br>"
                          f"Price: ${exit_price:,.2f}<br>"
                          f"P&L: {pnl:+.2f}%<br>"
                          f"Duration: {trade['duration_hours']:.1f}h<br>"
                          f"Reason: {trade.get('exit_reason', 'N/A')}<br>"
                          f"<extra></extra>")
        ))
        
        # Linea ORIZZONTALE al prezzo di ENTRY (per mostrare il livello esatto)
        fig.add_shape(
            type="line",
            x0=entry_time - timedelta(hours=1),  # Inizia 1 ora prima
            x1=entry_time + timedelta(hours=1),  # Finisce 1 ora dopo
            y0=entry_price,
            y1=entry_price,
            line=dict(color='rgb(0, 255, 0)', width=2, dash='solid'),
            opacity=0.5
        )
        
        # Linea ORIZZONTALE al prezzo di EXIT (per mostrare il livello esatto)
        fig.add_shape(
            type="line",
            x0=exit_time - timedelta(hours=1),  # Inizia 1 ora prima
            x1=exit_time + timedelta(hours=1),  # Finisce 1 ora dopo
            y0=exit_price,
            y1=exit_price,
            line=dict(color=exit_color, width=2, dash='solid'),
            opacity=0.6
        )
        
        # Linea che collega entry a exit (colore basato su WIN/LOSS)
        fig.add_shape(
            type="line", 
            x0=entry_time, x1=exit_time, 
            y0=entry_price, y1=exit_price,  # Da entry_price a exit_price (mostra movimento)
            line=dict(color=line_color, width=1.5, dash="dot"), 
            opacity=0.7
        )
        
        # Annotazioni PER TUTTI I TRADE (non solo > 5%)
        annotation_color = 'rgb(0, 200, 0)' if result == 'WIN' else 'rgb(255, 50, 50)'
        
        fig.add_annotation(
            x=exit_time, y=exit_price, 
            text=f"{pnl:+.1f}%",
            showarrow=True, 
            arrowhead=2, 
            arrowsize=1.0, 
            arrowwidth=2,  # Freccia più spessa
            arrowcolor=annotation_color,
            ax=40 if result == 'WIN' else -40,  # Più distanziata
            ay=-30 if result == 'WIN' else 30,
            font=dict(size=10, color=annotation_color, family="Arial Black"),  # Testo più grande e bold
            bgcolor="rgba(0, 0, 0, 0.8)",  # Background scuro
            bordercolor=annotation_color, 
            borderwidth=2,  # Bordo più spesso
            opacity=1.0  # Completamente opaco
        )
    
    # Calculate statistics
    wins = sum(1 for t in trades if t['result'] == 'WIN')
    losses = len(trades) - wins
    win_rate = (wins / len(trades) * 100) if trades else 0
    
    # Determine actual visualization timeframe from candles
    if len(candles_df) > 1:
        time_diff = (candles_df.index[1] - candles_df.index[0]).total_seconds() / 60
        if time_diff < 60:
            viz_tf = f"{int(time_diff)}m"
        elif time_diff < 1440:
            viz_tf = f"{int(time_diff/60)}h"
        else:
            viz_tf = f"{int(time_diff/1440)}d"
    else:
        viz_tf = "1m"
    
    # Layout stile TradingView
    fig.update_layout(
        title=dict(
            text=f"{symbol} | Backtest: {timeframe} | Chart: {viz_tf} | {len(trades)} Trades | WR: {win_rate:.1f}% | {wins}W/{losses}L", 
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
    
    # Update candlestick colors
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


async def create_interactive_charts(viz_data):
    """
    Crea grafici interattivi SEPARATI per ogni simbolo
    Scarica candele on-demand da Bybit
    """
    symbols = list(viz_data.keys())
    num_symbols = len(symbols)
    total_trades = sum(len(viz_data[s]['trades']) for s in symbols)
    
    print(colored(f"\n📊 Creating {num_symbols} chart files with live data...", "yellow"))
    print(colored(f"   Total trades: {total_trades}", "yellow"))
    
    Path('visualizations').mkdir(exist_ok=True)
    
    output_files = []
    
    # Process each symbol
    for idx, symbol in enumerate(symbols, 1):
        data = viz_data[symbol]
        trades = data['trades']
        timeframe = data['timeframe']
        
        print(colored(f"\n   [{idx}/{num_symbols}] {symbol}", "cyan"))
        
        # Download candele da Bybit
        candles_df = await download_candles_for_visualization(symbol, timeframe, trades)
        
        if candles_df is None or len(candles_df) == 0:
            print(colored(f"      ⚠️ Skipping {symbol} (no candle data)", "yellow"))
            continue
        
        # Genera grafico
        print(colored(f"      📊 Generating chart...", "cyan"), end=" ", flush=True)
        output_file = create_separate_chart(symbol, candles_df, trades, timeframe)
        output_files.append(output_file)
        print(colored(f"✓ {output_file.name}", "green"))
    
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


async def main_async():
    """Main async entry point"""
    print(colored("\n🎨 BACKTEST TRADES VISUALIZER (ON-DEMAND DATA)", "cyan", attrs=['bold']))
    print(colored("="*80 + "\n", "cyan"))
    
    # Load metadata
    viz_data = load_visualization_data()
    
    if not viz_data:
        return
    
    # Print summary
    print_summary(viz_data)
    
    # Create interactive charts (download candele on-demand)
    output_files = await create_interactive_charts(viz_data)
    
    if not output_files:
        print(colored("\n❌ No charts generated!", "red"))
        return
    
    print(colored("\n" + "="*80, "green"))
    print(colored("✅ ALL CHARTS GENERATED!", "green", attrs=['bold']))
    print(colored("="*80, "green"))
    print(colored("\n📁 Generated files:", "cyan"))
    for f in output_files:
        print(colored(f"   • {f.name}", "yellow"))
    
    print(colored("\n💡 Open any file in browser to explore trades!", "cyan"))
    print(colored(f"   Example: start visualizations\\{output_files[0].name}", "yellow"))


def main():
    """Entry point wrapper"""
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
