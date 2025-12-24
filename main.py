"""
📥 Download Dati Crypto - Main Script

Scarica le ultime 1000 candele OHLCV per i top 50 simboli per volume
e le salva in un database SQLite locale.

Uso:
    python main.py              # Download completo
    python main.py --stats      # Mostra solo statistiche database
    python main.py --symbols 10 # Scarica solo 10 simboli
"""

import sys
import asyncio
import argparse

# Fix per Windows - usa SelectorEventLoop per compatibilità con aiodns
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import ccxt.async_support as ccxt
from termcolor import colored
from datetime import datetime

import config
from fetcher import download_and_save, display_download_summary
from core.database_cache import DatabaseCache, display_database_stats


def print_banner():
    """Stampa banner iniziale"""
    print(colored("\n" + "="*60, "cyan", attrs=['bold']))
    print(colored("📥 DOWNLOAD DATI CRYPTO - Bybit", "cyan", attrs=['bold']))
    print(colored("="*60, "cyan", attrs=['bold']))
    print(colored(f"⏰ Avvio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "white"))
    print(colored(f"📊 Simboli: Top {config.TOP_SYMBOLS_COUNT} per volume", "white"))
    print(colored(f"⏱️  Timeframes: {', '.join(config.ENABLED_TIMEFRAMES)}", "white"))
    print(colored(f"🕯️ Candele per simbolo: {config.CANDLES_LIMIT}", "white"))
    print(colored("="*60, "cyan", attrs=['bold']))


async def main(args):
    """Funzione principale"""
    
    # Inizializza database
    db_cache = DatabaseCache()
    
    # Se richieste solo statistiche, mostrare e uscire
    if args.stats:
        display_database_stats(db_cache)
        return
    
    print_banner()
    
    # Configura exchange Bybit
    exchange = ccxt.bybit(config.exchange_config)
    
    try:
        # Override numero simboli se specificato
        if args.symbols:
            config.TOP_SYMBOLS_COUNT = args.symbols
        
        # Override timeframes se specificati
        timeframes = None
        if args.timeframe:
            timeframes = [args.timeframe]
        
        # Esegui download
        stats = await download_and_save(
            exchange=exchange,
            db_cache=db_cache,
            timeframes=timeframes,
            limit=config.CANDLES_LIMIT
        )
        
        # Mostra riepilogo
        display_download_summary(stats)
        
        # Mostra statistiche database
        display_database_stats(db_cache)
        
        print(colored("\n✅ Download completato con successo!", "green", attrs=['bold']))
        
    except KeyboardInterrupt:
        print(colored("\n\n⚠️ Download interrotto dall'utente", "yellow"))
        
    except Exception as e:
        print(colored(f"\n❌ Errore: {e}", "red"))
        raise
        
    finally:
        # Chiudi connessione exchange
        await exchange.close()


def parse_args():
    """Parsing argomenti da linea di comando"""
    parser = argparse.ArgumentParser(
        description='Download dati OHLCV da Bybit',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Esempi:
  python main.py                    # Download completo
  python main.py --stats            # Solo statistiche database
  python main.py --symbols 10       # Top 10 simboli
  python main.py --timeframe 1h     # Solo timeframe 1h
        '''
    )
    
    parser.add_argument(
        '--stats', 
        action='store_true',
        help='Mostra solo statistiche database senza scaricare'
    )
    
    parser.add_argument(
        '--symbols', 
        type=int,
        help=f'Numero di simboli da scaricare (default: {config.TOP_SYMBOLS_COUNT})'
    )
    
    parser.add_argument(
        '--timeframe', 
        type=str,
        choices=['5m', '15m', '30m', '1h', '4h'],
        help='Scarica solo un timeframe specifico'
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
