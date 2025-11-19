#!/usr/bin/env python3
"""
📊 DISPLAY BYBIT TRADING HISTORY

Script per mostrare la Trading History ESATTAMENTE come appare su Bybit.
Recupera i dati dall'endpoint closed-pnl e li visualizza in formato tabellare.

TUTTI i campi vengono presi DIRETTAMENTE da Bybit:
- Symbol
- Side (Long/Short)
- Qty (contracts)
- Order Type
- Entry Price
- Exit Price
- Closed P&L (USDT)
- Closed P&L (%)
- Leverage
- Order ID
- Created Time
- Updated Time (Close Time)
- ecc...
"""

import sys
import os
import asyncio
import json
from datetime import datetime
from pathlib import Path

# Fix per Windows event loop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Aggiungi parent directory al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ccxt.async_support as ccxt
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import config


async def fetch_bybit_trading_history(days: int = 7, limit: int = 50):
    """
    Recupera la Trading History COMPLETA da Bybit closed-pnl endpoint
    
    Args:
        days: Giorni nel passato (max 7 per Bybit)
        limit: Numero massimo di trade da recuperare
    
    Returns:
        List[Dict]: Lista di trade con TUTTI i dettagli da Bybit
    """
    console = Console()
    
    console.print(f"\n[cyan]🔍 Fetching Bybit Trading History (last {days} days)...[/cyan]\n")
    
    try:
        # Setup exchange
        exchange = ccxt.bybit({
            'apiKey': config.API_KEY,
            'secret': config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'recvWindow': 50000
            }
        })
        
        # Calculate time range (Bybit STRICT 7 days max)
        from datetime import timedelta
        
        if days > 7:
            console.print(f"[yellow]⚠️  Bybit limits to 7 days, adjusting from {days}[/yellow]")
            days = 7
        
        now = datetime.now()
        end_time = int(now.timestamp() * 1000)
        start_time = int((now - timedelta(days=days)).timestamp() * 1000)
        
        # ✅ VERIFIED CORRECT ENDPOINT - /v5/position/closed-pnl
        console.print("[cyan]📡 Calling Bybit API: /v5/position/closed-pnl...[/cyan]")
        
        response = await exchange.private_get_v5_position_closed_pnl({
            'category': 'linear',
            'startTime': start_time,
            'endTime': end_time,
            'limit': limit
        })
        
        await exchange.close()
        
        # Check response
        ret_code = response.get('retCode', -1)
        if int(ret_code) != 0:
            ret_msg = response.get('retMsg', 'Unknown error')
            console.print(f"[red]❌ Bybit API Error (code {ret_code}): {ret_msg}[/red]")
            return []
        
        # Extract trades
        trades = response.get('result', {}).get('list', [])
        
        console.print(f"[green]✅ Found {len(trades)} closed positions[/green]\n")
        
        return trades
        
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return []


def display_trading_history_table(trades: list):
    """
    Mostra la Trading History in formato tabella IDENTICO a Bybit
    
    COLONNE ESATTAMENTE COME SU BYBIT:
    - Symbol
    - Side
    - Qty
    - Order Type
    - Avg Entry Price
    - Avg Exit Price
    - Closed P&L (USDT)
    - Closed P&L (%)
    - Leverage
    - Open Fee
    - Close Fee
    - Total Fee
    - Created Time (apertura)
    - Updated Time (chiusura)
    - Order ID
    """
    console = Console()
    
    if not trades:
        console.print("[yellow]📭 No trades found[/yellow]")
        return
    
    # Crea tabella
    table = Table(
        title="💰 BYBIT TRADING HISTORY (Closed Positions)",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan"
    )
    
    # Colonne ESATTE come su Bybit
    table.add_column("Symbol", style="cyan", justify="left")
    table.add_column("Side", style="white", justify="center")
    table.add_column("Qty", style="white", justify="right")
    table.add_column("Entry Price", style="white", justify="right")
    table.add_column("Exit Price", style="white", justify="right")
    table.add_column("Closed P&L", style="white", justify="right")
    table.add_column("P&L %", style="white", justify="right")
    table.add_column("Lev", style="white", justify="center")
    table.add_column("Open Fee", style="white", justify="right")
    table.add_column("Close Fee", style="white", justify="right")
    table.add_column("Created Time", style="white", justify="center")
    table.add_column("Updated Time", style="white", justify="center")
    
    # Aggiungi ogni trade
    total_pnl = 0
    total_fees = 0
    
    for trade in trades:
        try:
            # Estrai dati ESATTI da Bybit
            symbol = trade.get('symbol', 'UNKNOWN').replace('USDT', '')
            side = trade.get('side', '').upper()
            qty = float(trade.get('qty', 0) or 0)
            entry_price = float(trade.get('avgEntryPrice', 0) or 0)
            exit_price = float(trade.get('avgExitPrice', 0) or 0)
            closed_pnl = float(trade.get('closedPnl', 0) or 0)
            leverage = float(trade.get('leverage', 0) or 0)
            open_fee = float(trade.get('openFee', 0) or 0)
            close_fee = float(trade.get('closeFee', 0) or 0)
            
            # Calculate %
            notional = qty * entry_price
            margin = notional / leverage if leverage > 0 else notional
            pnl_pct = (closed_pnl / margin * 100) if margin > 0 else 0
            
            # Timestamps
            created_time = 'Unknown'
            updated_time = 'Unknown'
            
            if trade.get('createdTime'):
                try:
                    ts = int(trade['createdTime']) / 1000
                    created_time = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
                except:
                    pass
            
            if trade.get('updatedTime'):
                try:
                    ts = int(trade['updatedTime']) / 1000
                    updated_time = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
                except:
                    pass
            
            # Color per PnL
            if closed_pnl > 0:
                pnl_color = "green"
                pnl_pct_color = "green"
            elif closed_pnl < 0:
                pnl_color = "red"
                pnl_pct_color = "red"
            else:
                pnl_color = "white"
                pnl_pct_color = "white"
            
            side_emoji = "🟢 LONG" if side == "BUY" else "🔴 SHORT"
            
            # Aggiungi riga
            table.add_row(
                symbol,
                side_emoji,
                f"{qty:.4f}",
                f"${entry_price:.6f}",
                f"${exit_price:.6f}",
                f"[{pnl_color}]{closed_pnl:+.4f}[/{pnl_color}]",
                f"[{pnl_pct_color}]{pnl_pct:+.2f}%[/{pnl_pct_color}]",
                f"{leverage:.0f}x",
                f"${abs(open_fee):.4f}",
                f"${abs(close_fee):.4f}",
                created_time,
                updated_time
            )
            
            total_pnl += closed_pnl
            total_fees += abs(open_fee) + abs(close_fee)
            
        except Exception as e:
            console.print(f"[red]⚠️  Error processing trade: {e}[/red]")
            continue
    
    # Mostra tabella
    console.print(table)
    
    # Summary
    pnl_color = "green" if total_pnl > 0 else "red" if total_pnl < 0 else "white"
    
    summary_text = (
        f"📊 TOTAL CLOSED P&L: [{pnl_color}]{total_pnl:+.2f} USDT[/{pnl_color}]\n"
        f"💸 TOTAL FEES PAID: ${total_fees:.2f} USDT\n"
        f"🔢 TOTAL TRADES: {len(trades)}"
    )
    
    console.print(Panel(summary_text, title="Summary", border_style="cyan"))


def save_to_json(trades: list, filename: str = "data_cache/bybit_trading_history_full.json"):
    """
    Salva i dati COMPLETI in JSON esattamente come vengono da Bybit
    
    Args:
        trades: Lista di trade da Bybit
        filename: Nome del file dove salvare
    """
    console = Console()
    
    try:
        # Create directory if needed
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare data
        data = {
            'metadata': {
                'source': 'Bybit /v5/position/closed-pnl',
                'fetched_at': datetime.now().isoformat(),
                'total_trades': len(trades)
            },
            'trades': trades
        }
        
        # Save
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        console.print(f"\n[green]💾 Saved to: {filename}[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Error saving JSON: {e}[/red]")


async def main():
    """Main function"""
    console = Console()
    
    console.print(Panel.fit(
        "📊 BYBIT TRADING HISTORY VIEWER\n\n"
        "Mostra la Trading History ESATTAMENTE come su Bybit\n"
        "Tutti i dati vengono presi direttamente dall'endpoint closed-pnl",
        border_style="cyan"
    ))
    
    # Fetch da Bybit
    trades = await fetch_bybit_trading_history(days=7, limit=50)
    
    if not trades:
        console.print("[yellow]📭 No closed positions found[/yellow]")
        return
    
    # Display come su Bybit
    display_trading_history_table(trades)
    
    # Save to JSON
    save_to_json(trades)
    
    console.print(f"\n[cyan]✅ Done! Check 'data_cache/bybit_trading_history_full.json' for full data[/cyan]\n")


if __name__ == "__main__":
    asyncio.run(main())
