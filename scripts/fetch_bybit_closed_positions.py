#!/usr/bin/env python3
"""
📊 BYBIT CLOSED POSITIONS FETCHER

Script standalone per recuperare e visualizzare le ultime posizioni chiuse su Bybit.
Mostra tutti i dettagli: PnL, fee, timestamp, durata, ecc.
Utile per verificare allineamento con trade_history.json

Uso: python scripts/fetch_bybit_closed_positions.py [--limit 20] [--days 7]
"""

import asyncio
import ccxt.async_support as ccxt
import os
import sys
from datetime import datetime, timedelta
from termcolor import colored
from pathlib import Path
import json
import platform

# Fix for Windows aiodns issue
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import config for credentials
try:
    from dotenv import load_dotenv, find_dotenv
    _env_file = find_dotenv()
    if _env_file:
        load_dotenv(_env_file, override=False)
except:
    pass

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")


async def fetch_closed_positions(limit=20, days_back=7):
    """
    Recupera le ultime posizioni chiuse da Bybit
    
    Args:
        limit: Numero massimo di posizioni da recuperare
        days_back: Giorni nel passato da cui cercare
    
    Returns:
        List[Dict]: Lista di posizioni chiuse con dettagli
    """
    if not API_KEY or not API_SECRET:
        print(colored("❌ ERRORE: API key non trovate!", "red"))
        print(colored("💡 Assicurati di avere BYBIT_API_KEY e BYBIT_API_SECRET nel .env", "yellow"))
        return []
    
    print(colored("🔗 Connessione a Bybit...", "cyan"))
    
    # Create exchange instance
    exchange = ccxt.bybit({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
            'recvWindow': 60000,
        }
    })
    
    try:
        # Bybit API limit: max 7 days range
        if days_back > 7:
            print(colored(f"⚠️ Attenzione: Bybit limita il range a 7 giorni. Uso 7 giorni invece di {days_back}.", "yellow"))
            days_back = 7
        
        # Calculate start time - ensure exactly 7 days or less
        # Bybit is VERY strict: end_time - start_time must be <= 7 days (604800000 ms)
        now = datetime.now()
        end_time = int(now.timestamp() * 1000)
        start_datetime = now - timedelta(days=days_back)
        start_time = int(start_datetime.timestamp() * 1000)
        
        # Double check the range doesn't exceed 7 days
        time_range_days = (end_time - start_time) / (1000 * 60 * 60 * 24)
        if time_range_days > 7:
            # Adjust to exactly 7 days
            start_time = end_time - (7 * 24 * 60 * 60 * 1000)
            print(colored(f"⚠️ Range aggiustato a esattamente 7 giorni", "yellow"))
        
        print(colored(f"📥 Recupero posizioni chiuse (ultimi {days_back} giorni)...", "cyan"))
        
        # Use Bybit V5 API directly for closed PnL
        # API endpoint: GET /v5/position/closed-pnl
        try:
            response = await exchange.private_get_v5_position_closed_pnl({
                'category': 'linear',
                'startTime': start_time,
                'endTime': end_time,
                'limit': limit
            })
            
            # Extract response codes
            ret_code = response.get('retCode', -1)
            ret_msg = response.get('retMsg', 'Unknown')
            
            # Check for API errors (retCode 0 = success, others = error)
            # Note: Bybit returns retCode as string, need to convert to int
            if int(ret_code) != 0:
                print(colored(f"❌ Errore API Bybit (code {ret_code}): {ret_msg}", "red"))
                await exchange.close()
                return []
            
            # Success! Extract data
            closed_pnl_list = response.get('result', {}).get('list', [])
            
            if len(closed_pnl_list) == 0:
                print(colored(f"📭 Nessuna posizione chiusa trovata negli ultimi {days_back} giorni", "yellow"))
                print(colored(f"💡 Prova ad aumentare --days oppure verifica che ci siano trade chiusi su Bybit", "cyan"))
            else:
                print(colored(f"✅ Trovate {len(closed_pnl_list)} posizioni chiuse", "green"))
            
        except Exception as api_error:
            print(colored(f"❌ Errore chiamata API: {api_error}", "red"))
            print(colored("💡 Tentativo con metodo alternativo (fetch_my_trades)...", "yellow"))
            
            # Fallback: usa fetch_my_trades per ottenere trade history
            closed_pnl_list = []
            
            # Get list of all symbols with recent activity
            try:
                # Fetch recent trades for all markets
                all_markets = await exchange.load_markets()
                usdt_perpetuals = [s for s in all_markets.keys() if '/USDT:USDT' in s]
                
                print(colored(f"📊 Scansione {len(usdt_perpetuals)} simboli USDT perpetual...", "cyan"))
                
                # Sample first 50 most liquid symbols to avoid timeout
                for symbol in usdt_perpetuals[:50]:
                    try:
                        trades = await exchange.fetch_my_trades(
                            symbol=symbol,
                            since=start_time,
                            limit=100
                        )
                        
                        if trades:
                            # Group trades by position
                            # This is a simplified approach - Bybit returns individual fills
                            for trade in trades[:limit]:
                                if trade.get('info'):
                                    closed_pnl_list.append(trade['info'])
                        
                        # Limit check to avoid too many API calls
                        if len(closed_pnl_list) >= limit:
                            break
                            
                    except Exception as symbol_error:
                        # Skip symbols with errors
                        continue
                
                print(colored(f"✅ Trovati {len(closed_pnl_list)} trade individuali", "green"))
                
            except Exception as fallback_error:
                print(colored(f"❌ Anche il metodo alternativo è fallito: {fallback_error}", "red"))
                await exchange.close()
                return []
        
        # Process and enrich data
        positions = []
        
        for pnl_record in closed_pnl_list:
            try:
                # Extract symbol
                symbol_raw = pnl_record.get('symbol', '')
                if not symbol_raw:
                    continue
                
                # Convert Bybit format to ccxt format
                if '/' not in symbol_raw:
                    symbol = f"{symbol_raw.replace('USDT', '')}/USDT:USDT"
                else:
                    symbol = symbol_raw
                
                # Extract data from PnL record (Bybit V5 API format)
                position_data = {
                    'symbol': symbol,
                    'symbol_short': symbol.replace('/USDT:USDT', '').replace(':USDT', ''),
                    'side': pnl_record.get('side', 'UNKNOWN').upper(),
                    'entry_price': float(pnl_record.get('avgEntryPrice', 0) or 0),
                    'exit_price': float(pnl_record.get('avgExitPrice', 0) or 0),
                    'quantity': float(pnl_record.get('qty', 0) or pnl_record.get('closedSize', 0) or 0),
                    'leverage': float(pnl_record.get('leverage', 0) or 0),
                    
                    # PnL and fees from Bybit
                    'closed_pnl': float(pnl_record.get('closedPnl', 0) or 0),
                    'realized_pnl': float(pnl_record.get('closedPnl', 0) or 0),
                    'open_fee': float(pnl_record.get('openFee', 0) or 0),
                    'close_fee': float(pnl_record.get('closeFee', 0) or 0),
                    'total_fees': float(pnl_record.get('openFee', 0) or 0) + float(pnl_record.get('closeFee', 0) or 0),
                    
                    # Timestamps
                    'created_time': pnl_record.get('createdTime'),
                    'updated_time': pnl_record.get('updatedTime'),
                    
                    # Order info
                    'order_id': pnl_record.get('orderId'),
                    'order_type': pnl_record.get('orderType'),
                    'fill_count': pnl_record.get('fillCount', 0),
                }
                
                # Skip if no meaningful data
                if position_data['entry_price'] == 0 or position_data['quantity'] == 0:
                    continue
                
                # Calculate additional metrics
                if position_data['entry_price'] > 0 and position_data['exit_price'] > 0:
                    price_change = (position_data['exit_price'] - position_data['entry_price']) / position_data['entry_price']
                    if position_data['side'] == 'SELL':
                        price_change = -price_change
                    
                    position_data['price_change_pct'] = price_change * 100
                    if position_data['leverage'] > 0:
                        position_data['roe_pct'] = price_change * 100 * position_data['leverage']
                    else:
                        position_data['roe_pct'] = 0
                
                # Calculate notional and margin
                if position_data['quantity'] > 0 and position_data['entry_price'] > 0:
                    position_data['notional'] = position_data['quantity'] * position_data['entry_price']
                    if position_data['leverage'] > 0:
                        position_data['margin'] = position_data['notional'] / position_data['leverage']
                    else:
                        position_data['margin'] = position_data['notional']
                
                # Calculate duration
                if position_data['created_time'] and position_data['updated_time']:
                    try:
                        created = datetime.fromtimestamp(int(position_data['created_time']) / 1000)
                        updated = datetime.fromtimestamp(int(position_data['updated_time']) / 1000)
                        duration = updated - created
                        position_data['duration_minutes'] = duration.total_seconds() / 60
                        position_data['created_time_str'] = created.strftime('%Y-%m-%d %H:%M:%S')
                        position_data['updated_time_str'] = updated.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        position_data['duration_minutes'] = 0
                        position_data['created_time_str'] = 'N/A'
                        position_data['updated_time_str'] = 'N/A'
                
                positions.append(position_data)
                
            except Exception as e:
                print(colored(f"⚠️ Errore processando posizione: {e}", "yellow"))
                continue
        
        await exchange.close()
        return positions
        
    except Exception as e:
        print(colored(f"❌ Errore recuperando dati: {e}", "red"))
        await exchange.close()
        return []


def display_positions(positions):
    """Mostra le posizioni in formato tabellare"""
    if not positions:
        print(colored("\n📭 Nessuna posizione chiusa trovata", "yellow"))
        return
    
    print()
    print(colored("=" * 120, "cyan"))
    print(colored("📊 POSIZIONI CHIUSE SU BYBIT", "cyan", attrs=['bold']))
    print(colored("=" * 120, "cyan"))
    print()
    
    # Statistics
    total_pnl = sum(p.get('realized_pnl', 0) for p in positions)
    wins = sum(1 for p in positions if p.get('realized_pnl', 0) > 0)
    losses = sum(1 for p in positions if p.get('realized_pnl', 0) < 0)
    win_rate = (wins / len(positions) * 100) if positions else 0
    
    print(colored("📈 STATISTICHE GENERALI:", "white", attrs=['bold']))
    print(f"   Totale posizioni: {len(positions)}")
    print(f"   Vincite: {wins} | Perdite: {losses}")
    print(f"   Win Rate: {win_rate:.1f}%")
    pnl_color = "green" if total_pnl >= 0 else "red"
    print(f"   PnL Totale: {colored(f'${total_pnl:+.2f}', pnl_color, attrs=['bold'])}")
    print()
    print(colored("-" * 120, "white"))
    print()
    
    # Display each position
    for i, pos in enumerate(positions, 1):
        symbol_short = pos['symbol_short']
        side = pos['side']
        entry = pos.get('entry_price', 0)
        exit_price = pos.get('exit_price', 0)
        quantity = pos.get('quantity', 0)
        leverage = pos.get('leverage', 0)
        
        realized_pnl = pos.get('realized_pnl', 0)
        roe_pct = pos.get('roe_pct', 0)
        
        created = pos.get('created_time_str', 'N/A')
        updated = pos.get('updated_time_str', 'N/A')
        duration = pos.get('duration_minutes', 0)
        
        margin = pos.get('margin', 0)
        notional = pos.get('notional', 0)
        
        # Colors
        side_emoji = "🟢" if side == 'BUY' else "🔴"
        pnl_color = "green" if realized_pnl >= 0 else "red"
        pnl_sign = "+" if realized_pnl >= 0 else ""
        
        print(colored(f"═══ POSIZIONE #{i} ═══", "yellow", attrs=['bold']))
        print(f"{side_emoji} {symbol_short:12} | {side:4}")
        print()
        print(colored("📊 DETTAGLI POSIZIONE:", "white"))
        print(f"   Entry: ${entry:.6f}")
        print(f"   Exit:  ${exit_price:.6f}")
        print(f"   Qty:   {quantity:.4f} contracts")
        print(f"   Lev:   {leverage}x")
        print()
        print(colored("💰 ECONOMICS:", "white"))
        print(f"   Notional: ${notional:.2f}")
        print(f"   Margin:   ${margin:.2f}")
        print(f"   PnL:      {colored(f'{pnl_sign}${realized_pnl:.2f}', pnl_color, attrs=['bold'])}")
        print(f"   ROE:      {colored(f'{pnl_sign}{roe_pct:.2f}%', pnl_color, attrs=['bold'])}")
        print()
        print(colored("⏱️ TIMING:", "white"))
        print(f"   Apertura:  {created}")
        print(f"   Chiusura:  {updated}")
        print(f"   Durata:    {duration:.1f} minuti")
        print()
        print(colored("-" * 120, "white"))
        print()
    
    print(colored("=" * 120, "cyan"))
    print()


def compare_with_local_history(positions):
    """Confronta con trade_history.json locale se esiste"""
    history_file = "data_cache/trade_history.json"
    
    if not os.path.exists(history_file):
        print(colored("\n💡 File trade_history.json non trovato - verrà creato al prossimo avvio del bot", "yellow"))
        return
    
    print()
    print(colored("=" * 120, "green"))
    print(colored("🔍 CONFRONTO CON TRADE HISTORY LOCALE", "green", attrs=['bold']))
    print(colored("=" * 120, "green"))
    print()
    
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            local_data = json.load(f)
        
        local_trades = local_data.get('trades', [])
        closed_local = [t for t in local_trades if t['status'] == 'CLOSED']
        
        print(f"📊 Trade locali chiusi: {len(closed_local)}")
        print(f"📊 Trade Bybit recuperati: {len(positions)}")
        print()
        
        # Calculate local stats
        if closed_local:
            local_pnl = sum(t.get('realized_pnl_usd', 0) for t in closed_local if t.get('realized_pnl_usd'))
            local_wins = sum(1 for t in closed_local if t.get('realized_pnl_usd', 0) > 0)
            local_losses = sum(1 for t in closed_local if t.get('realized_pnl_usd', 0) < 0)
            local_win_rate = (local_wins / len(closed_local) * 100) if closed_local else 0
            
            # Bybit stats
            bybit_pnl = sum(p.get('realized_pnl', 0) for p in positions)
            bybit_wins = sum(1 for p in positions if p.get('realized_pnl', 0) > 0)
            bybit_losses = sum(1 for p in positions if p.get('realized_pnl', 0) < 0)
            bybit_win_rate = (bybit_wins / len(positions) * 100) if positions else 0
            
            print(colored("STATISTICHE LOCALI:", "cyan"))
            print(f"   Win Rate: {local_win_rate:.1f}%")
            print(f"   PnL Totale: ${local_pnl:+.2f}")
            print()
            
            print(colored("STATISTICHE BYBIT:", "yellow"))
            print(f"   Win Rate: {bybit_win_rate:.1f}%")
            print(f"   PnL Totale: ${bybit_pnl:+.2f}")
            print()
            
            # Differences
            pnl_diff = abs(local_pnl - bybit_pnl)
            win_rate_diff = abs(local_win_rate - bybit_win_rate)
            
            if pnl_diff < 1.0 and win_rate_diff < 5.0:
                print(colored("✅ ALLINEAMENTO PERFETTO! Statistiche coerenti tra locale e Bybit", "green", attrs=['bold']))
            elif pnl_diff < 5.0 and win_rate_diff < 10.0:
                print(colored("⚠️ Piccole differenze rilevate (probabilmente dovute a timing diverso)", "yellow"))
                print(f"   Diff PnL: ${pnl_diff:.2f}")
                print(f"   Diff Win Rate: {win_rate_diff:.1f}%")
            else:
                print(colored("❌ ATTENZIONE: Differenze significative rilevate!", "red", attrs=['bold']))
                print(f"   Diff PnL: ${pnl_diff:.2f}")
                print(f"   Diff Win Rate: {win_rate_diff:.1f}%")
                print(colored("   💡 Possibili cause:", "yellow"))
                print("      - Trade logging attivato solo recentemente")
                print("      - Alcuni trade chiusi prima dell'attivazione del logger")
                print("      - Range temporale diverso")
        
    except Exception as e:
        print(colored(f"⚠️ Errore leggendo history locale: {e}", "yellow"))
    
    print()
    print(colored("=" * 120, "green"))
    print()


def export_to_json(positions, filename="bybit_closed_positions.json"):
    """Esporta le posizioni in un file JSON"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'fetched_at': datetime.now().isoformat(),
                'total_positions': len(positions),
                'positions': positions
            }, f, indent=2, ensure_ascii=False, default=str)
        
        print(colored(f"💾 Dati esportati in: {filename}", "green"))
        return True
    except Exception as e:
        print(colored(f"❌ Errore esportazione: {e}", "red"))
        return False


async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch closed positions from Bybit')
    parser.add_argument('--limit', type=int, default=20, help='Max number of positions to fetch (default: 20)')
    parser.add_argument('--days', type=int, default=7, help='Days to look back (default: 7)')
    parser.add_argument('--export', action='store_true', help='Export to JSON file')
    parser.add_argument('--compare', action='store_true', help='Compare with local trade_history.json')
    
    args = parser.parse_args()
    
    print()
    print(colored("╔════════════════════════════════════════════════════════════════════════════╗", "cyan", attrs=['bold']))
    print(colored("║              📊 BYBIT CLOSED POSITIONS FETCHER                             ║", "cyan", attrs=['bold']))
    print(colored("╚════════════════════════════════════════════════════════════════════════════╝", "cyan", attrs=['bold']))
    print()
    
    # Fetch positions
    positions = await fetch_closed_positions(limit=args.limit, days_back=args.days)
    
    if not positions:
        print(colored("\n❌ Nessun dato recuperato da Bybit", "red"))
        return
    
    # Display positions
    display_positions(positions)
    
    # Compare with local history
    if args.compare:
        compare_with_local_history(positions)
    
    # Export to JSON
    if args.export:
        export_to_json(positions)
    
    # Tips
    print(colored("💡 SUGGERIMENTI:", "cyan"))
    print(colored("   • Usa --compare per confrontare con trade_history.json locale", "white"))
    print(colored("   • Usa --export per salvare i dati in JSON", "white"))
    print(colored("   • Usa --limit N per cambiare il numero di posizioni (default: 20)", "white"))
    print(colored("   • Usa --days N per cambiare il range temporale (default: 7 giorni)", "white"))
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Terminato dall'utente")
    except Exception as e:
        print(colored(f"\n❌ Errore: {e}", "red"))
        import traceback
        traceback.print_exc()
