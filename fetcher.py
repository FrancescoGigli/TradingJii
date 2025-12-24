"""
📥 Fetcher Module - Download OHLCV da Bybit

Modulo per scaricare dati OHLCV e salvarli nel database SQLite.
Può essere usato standalone o importato da altri moduli.

Uso come modulo:
    from fetcher import CryptoDataFetcher
    
    async with CryptoDataFetcher() as fetcher:
        symbols = await fetcher.get_top_symbols(n=10)
        data = await fetcher.download_symbols(symbols, timeframe='15m')
"""

import asyncio
import logging
import pandas as pd
from datetime import datetime
from asyncio import Semaphore
from termcolor import colored
from typing import List, Dict, Optional

import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class CryptoDataFetcher:
    """
    Classe principale per il download di dati crypto da Bybit.
    
    Uso:
        async with CryptoDataFetcher() as fetcher:
            symbols = await fetcher.get_top_symbols(n=10)
            data = await fetcher.download_symbols(symbols, '15m')
    """
    
    def __init__(self, exchange=None):
        """
        Inizializza il fetcher
        
        Args:
            exchange: Istanza ccxt exchange (opzionale, verrà creata automaticamente)
        """
        self._exchange = exchange
        self._own_exchange = False
        self.markets = None
        self.downloaded_symbols = []  # Traccia simboli scaricati
    
    async def __aenter__(self):
        """Context manager entry - inizializza exchange se necessario"""
        if self._exchange is None:
            import ccxt.async_support as ccxt
            self._exchange = ccxt.bybit(config.exchange_config)
            self._own_exchange = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - chiude exchange se creato internamente"""
        if self._own_exchange and self._exchange:
            await self._exchange.close()
    
    @property
    def exchange(self):
        return self._exchange
    
    async def load_markets(self) -> Dict:
        """Carica i mercati disponibili"""
        if self.markets is None:
            self.markets = await self._exchange.load_markets()
        return self.markets
    
    async def get_usdt_perpetual_symbols(self) -> List[str]:
        """
        Ottiene lista di tutti i simboli USDT perpetual futures
        
        Returns:
            Lista di simboli (es. ['BTC/USDT:USDT', 'ETH/USDT:USDT', ...])
        """
        markets = await self.load_markets()
        
        symbols = [
            symbol for symbol in markets.keys()
            if '/USDT:USDT' in symbol and markets[symbol].get('active', False)
        ]
        
        return symbols
    
    async def get_ticker_volume(self, symbol: str) -> tuple:
        """Ottiene il volume di trading per un simbolo"""
        try:
            ticker = await self._exchange.fetch_ticker(symbol)
            return symbol, ticker.get('quoteVolume', 0)
        except Exception as e:
            logging.debug(f"Errore ticker {symbol}: {e}")
            return symbol, None
    
    async def get_top_symbols(self, n: int = None, symbols: List[str] = None) -> List[str]:
        """
        Ottiene i top N simboli per volume di trading
        
        Args:
            n: Numero di simboli da restituire (default: config.TOP_SYMBOLS_COUNT)
            symbols: Lista di simboli da analizzare (default: tutti USDT perpetual)
        
        Returns:
            Lista dei top simboli ordinati per volume
        """
        if n is None:
            n = config.TOP_SYMBOLS_COUNT
        
        if symbols is None:
            symbols = await self.get_usdt_perpetual_symbols()
        
        print(colored(f"\n📊 Analizzando volumi per {len(symbols)} simboli...", "cyan"))
        
        # Fetch parallelo con rate limiting
        semaphore = Semaphore(20)
        
        async def fetch_with_semaphore(symbol):
            async with semaphore:
                return await self.get_ticker_volume(symbol)
        
        tasks = [fetch_with_semaphore(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filtra e ordina
        symbol_volumes = []
        for result in results:
            if isinstance(result, tuple) and result[1] is not None:
                symbol_volumes.append(result)
        
        symbol_volumes.sort(key=lambda x: x[1], reverse=True)
        
        selected = [x[0] for x in symbol_volumes[:n]]
        
        # Mostra simboli selezionati
        print(colored(f"✅ Top {len(selected)} simboli per volume:", "green"))
        self._print_symbols_table(selected, symbol_volumes[:n])
        
        return selected
    
    def _print_symbols_table(self, symbols: List[str], volumes: List[tuple]):
        """Stampa tabella simboli con volumi"""
        print(colored("-" * 50, "cyan"))
        print(colored(f"{'#':<4} {'Simbolo':<20} {'Volume 24h':>20}", "white", attrs=['bold']))
        print(colored("-" * 50, "cyan"))
        
        for i, (symbol, vol) in enumerate(volumes, 1):
            symbol_short = symbol.replace('/USDT:USDT', '')
            vol_str = f"${vol/1e6:.1f}M" if vol >= 1e6 else f"${vol/1e3:.1f}K"
            print(f"{i:<4} {symbol_short:<20} {vol_str:>20}")
        
        print(colored("-" * 50, "cyan"))
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 1000) -> Optional[pd.DataFrame]:
        """
        Scarica dati OHLCV per un simbolo
        
        Args:
            symbol: Simbolo (es. 'BTC/USDT:USDT')
            timeframe: Timeframe (es. '15m', '1h')
            limit: Numero massimo di candele
        
        Returns:
            DataFrame con OHLCV o None
        """
        try:
            ohlcv = await self._exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=min(limit, 1000))
            
            if not ohlcv:
                return None
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            
            return df
            
        except Exception as e:
            logging.error(f"Errore download {symbol}[{timeframe}]: {e}")
            return None
    
    async def download_symbols(
        self, 
        symbols: List[str], 
        timeframe: str, 
        limit: int = 1000,
        max_concurrent: int = 15
    ) -> Dict[str, pd.DataFrame]:
        """
        Scarica dati per una lista di simboli
        
        Args:
            symbols: Lista di simboli
            timeframe: Timeframe
            limit: Candele per simbolo
            max_concurrent: Max richieste parallele
        
        Returns:
            Dict {symbol: DataFrame}
        """
        semaphore = Semaphore(max_concurrent)
        results = {}
        
        async def fetch_single(symbol):
            async with semaphore:
                await asyncio.sleep(0.05)
                df = await self.fetch_ohlcv(symbol, timeframe, limit)
                return symbol, df
        
        print(colored(f"\n⬇️  Scaricando {len(symbols)} simboli [{timeframe}]...", "yellow"))
        
        tasks = [fetch_single(s) for s in symbols]
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        for result in completed:
            if isinstance(result, tuple) and result[1] is not None:
                results[result[0]] = result[1]
                self.downloaded_symbols.append(result[0])
                success_count += 1
        
        print(colored(f"✅ Scaricati {success_count}/{len(symbols)} simboli con successo", "green"))
        
        return results
    
    def get_downloaded_symbols(self) -> List[str]:
        """Restituisce lista dei simboli scaricati in questa sessione"""
        return list(set(self.downloaded_symbols))
    
    def print_downloaded_summary(self):
        """Stampa riepilogo simboli scaricati"""
        symbols = self.get_downloaded_symbols()
        if not symbols:
            print(colored("⚠️ Nessun simbolo scaricato", "yellow"))
            return
        
        print(colored(f"\n📋 SIMBOLI SCARICATI ({len(symbols)}):", "cyan", attrs=['bold']))
        print(colored("-" * 60, "cyan"))
        
        # Formatta in colonne
        cols = 4
        for i in range(0, len(symbols), cols):
            row = symbols[i:i+cols]
            row_str = "  ".join(s.replace('/USDT:USDT', '').ljust(15) for s in row)
            print(row_str)
        
        print(colored("-" * 60, "cyan"))


# ============================================================
# FUNZIONI STANDALONE (per compatibilità)
# ============================================================

async def fetch_markets(exchange):
    """Carica i mercati disponibili dall'exchange"""
    return await exchange.load_markets()


async def fetch_ticker_volume(exchange, symbol):
    """Ottiene il volume di un ticker"""
    try:
        ticker = await exchange.fetch_ticker(symbol)
        return symbol, ticker.get('quoteVolume')
    except Exception as e:
        logging.debug(f"Errore ticker {symbol}: {e}")
        return symbol, None


async def get_top_symbols(exchange, symbols, top_n=None):
    """Ottiene i top N simboli per volume"""
    async with CryptoDataFetcher(exchange) as fetcher:
        fetcher.markets = await exchange.load_markets()
        return await fetcher.get_top_symbols(n=top_n, symbols=symbols)


async def fetch_ohlcv(exchange, symbol, timeframe, limit=1000):
    """Scarica dati OHLCV per un simbolo"""
    async with CryptoDataFetcher(exchange) as fetcher:
        return await fetcher.fetch_ohlcv(symbol, timeframe, limit)


async def download_and_save(exchange, db_cache, symbols=None, timeframes=None, limit=1000):
    """
    Scarica dati e li salva nel database
    
    Args:
        exchange: Istanza exchange ccxt
        db_cache: Istanza DatabaseCache
        symbols: Lista simboli (se None, prende i top per volume)
        timeframes: Lista timeframes (se None, usa config.ENABLED_TIMEFRAMES)
        limit: Candele per simbolo (default: 1000)
    
    Returns:
        Dict con statistiche download
    """
    stats = {
        'symbols_processed': 0,
        'candles_saved': 0,
        'errors': 0,
        'downloaded_symbols': []
    }
    
    async with CryptoDataFetcher(exchange) as fetcher:
        # Carica mercati
        print(colored("\n🔄 Caricamento mercati Bybit...", "cyan"))
        await fetcher.load_markets()
        
        # Filtra per USDT perpetual futures
        usdt_symbols = await fetcher.get_usdt_perpetual_symbols()
        print(colored(f"📈 Trovati {len(usdt_symbols)} pairs USDT perpetual", "cyan"))
        
        # Ottieni top simboli se non specificati
        if symbols is None:
            symbols = await fetcher.get_top_symbols(config.TOP_SYMBOLS_COUNT)
        
        # Usa timeframes di default se non specificati
        if timeframes is None:
            timeframes = config.ENABLED_TIMEFRAMES
        
        # Download per ogni timeframe
        for tf in timeframes:
            print(colored(f"\n{'='*60}", "magenta"))
            print(colored(f"⏰ TIMEFRAME: {tf}", "magenta", attrs=['bold']))
            print(colored(f"{'='*60}", "magenta"))
            
            # Scarica tutti i simboli per questo timeframe
            data = await fetcher.download_symbols(symbols, tf, limit)
            
            # Salva nel database
            for symbol, df in data.items():
                if df is not None and len(df) > 0:
                    try:
                        db_cache.save_data_to_db(symbol, tf, df)
                        stats['symbols_processed'] += 1
                        stats['candles_saved'] += len(df)
                        if symbol not in stats['downloaded_symbols']:
                            stats['downloaded_symbols'].append(symbol)
                    except Exception as e:
                        logging.error(f"Errore salvataggio {symbol}[{tf}]: {e}")
                        stats['errors'] += 1
            
            print(colored(f"💾 Salvati {len(data)} simboli nel database", "green"))
        
        # Mostra simboli scaricati
        fetcher.print_downloaded_summary()
    
    return stats


def display_download_summary(stats):
    """Mostra riepilogo download"""
    print(colored("\n" + "="*60, "cyan"))
    print(colored("📊 RIEPILOGO DOWNLOAD", "cyan", attrs=['bold']))
    print(colored("="*60, "cyan"))
    print(colored(f"  ✅ Simboli processati: {stats['symbols_processed']}", "green"))
    print(colored(f"  📈 Candele totali salvate: {stats['candles_saved']:,}", "green"))
    print(colored(f"  🪙 Simboli unici: {len(stats.get('downloaded_symbols', []))}", "green"))
    if stats['errors'] > 0:
        print(colored(f"  ❌ Errori: {stats['errors']}", "red"))
    print(colored("="*60, "cyan"))
