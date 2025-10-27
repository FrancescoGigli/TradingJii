#!/usr/bin/env python3
"""
🎯 BACKTEST CALIBRATION SYSTEM (PARALLELIZZATO)

Script per generare calibration table basata su backtest storico.
Versione ottimizzata con multi-threading CPU.

UTILIZZO:
    python backtest_calibration.py --months 3
"""

import asyncio
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from termcolor import colored
from tqdm import tqdm
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Silence numpy warnings
warnings.filterwarnings('ignore', category=RuntimeWarning)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
_LOG = logging.getLogger(__name__)

# Import modules
from config import (
    LEVERAGE, SL_FIXED_PCT, TRAILING_TRIGGER_PCT,
    TRAILING_DISTANCE_ROE_OPTIMAL, get_timesteps_for_timeframe
)
from core.confidence_calibrator import CalibrationAnalyzer
from core.ml_predictor import RobustMLPredictor
from core.rl_agent import global_rl_agent, build_market_context
from data_utils import prepare_data
import ccxt.async_support as ccxt


def create_exchange():
    """Create Bybit exchange instance for backtest"""
    return ccxt.bybit({'enableRateLimit': True, 'timeout': 30000})


class BacktestTradeManager:
    """Simulatore trade per backtest con SL/trailing"""
    
    def __init__(self):
        self.active_trades: Dict[str, Dict] = {}
        self.completed_trades: List[Dict] = []
        self.leverage = LEVERAGE
        self.sl_pct = SL_FIXED_PCT
        self.trailing_trigger_pct = TRAILING_TRIGGER_PCT
        self.trailing_distance_roe = TRAILING_DISTANCE_ROE_OPTIMAL
    
    def open_trade(self, symbol, entry_price, entry_time, xgb_confidence, rl_confidence, tf_predictions):
        sl_price = entry_price * (1 - self.sl_pct)
        trailing_trigger = entry_price * (1 + self.trailing_trigger_pct)
        
        self.active_trades[symbol] = {
            'symbol': symbol, 'entry_price': entry_price, 'entry_time': entry_time,
            'sl_price': sl_price, 'trailing_active': False, 'trailing_stop': None,
            'highest_price': entry_price, 'xgb_confidence': xgb_confidence,
            'rl_confidence': rl_confidence, 'tf_predictions': tf_predictions,
            'trailing_trigger_price': trailing_trigger
        }
    
    def update_trades(self, symbol, current_price, current_time):
        if symbol not in self.active_trades:
            return
        
        trade = self.active_trades[symbol]
        entry_price = trade['entry_price']
        
        if current_price > trade['highest_price']:
            trade['highest_price'] = current_price
        
        if current_price <= trade['sl_price']:
            self._close_trade(symbol, current_price, current_time, 'stop_loss')
            return
        
        if not trade['trailing_active'] and current_price >= trade['trailing_trigger_price']:
            trade['trailing_active'] = True
            current_roe = (current_price - entry_price) / entry_price * self.leverage
            protected_roe = current_roe - self.trailing_distance_roe
            trade['trailing_stop'] = entry_price * (1 + protected_roe / self.leverage)
        
        if trade['trailing_active']:
            current_roe = (current_price - entry_price) / entry_price * self.leverage
            protected_roe = current_roe - self.trailing_distance_roe
            new_trailing = entry_price * (1 + protected_roe / self.leverage)
            if new_trailing > trade['trailing_stop']:
                trade['trailing_stop'] = new_trailing
            
            if current_price <= trade['trailing_stop']:
                self._close_trade(symbol, current_price, current_time, 'trailing_stop')
    
    def _close_trade(self, symbol, exit_price, exit_time, reason):
        if symbol not in self.active_trades:
            return
        
        trade = self.active_trades[symbol]
        price_change = (exit_price - trade['entry_price']) / trade['entry_price']
        pnl_pct = price_change * self.leverage * 100
        result = 'WIN' if pnl_pct > 0 else 'LOSS'
        
        try:
            duration = (datetime.fromisoformat(exit_time) - datetime.fromisoformat(trade['entry_time'])).total_seconds() / 3600
        except:
            duration = 0
        
        self.completed_trades.append({
            'symbol': symbol, 'entry_date': trade['entry_time'], 'entry_price': trade['entry_price'],
            'exit_date': exit_time, 'exit_price': exit_price,
            'xgb_confidence': trade['xgb_confidence'], 'rl_confidence': trade['rl_confidence'],
            'tf_predictions': trade['tf_predictions'], 'result': result,
            'pnl_pct': round(pnl_pct, 2), 'duration_hours': round(duration, 2),
            'exit_reason': reason, 'stop_loss': self.sl_pct,
            'trailing_trigger': self.trailing_trigger_pct, 'trailing_distance': self.trailing_distance_roe
        })
        
        _LOG.info(f"{'🟢' if result == 'WIN' else '🔴'} {symbol}: {result} {pnl_pct:+.2f}% | {reason}")
        del self.active_trades[symbol]
    
    def get_completed_trades(self):
        return self.completed_trades


async def download_historical_data(exchange, symbol, timeframe, months=6):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)
        
        from fetcher import fetch_and_save_data
        df = await fetch_and_save_data(exchange, symbol, timeframe)
        
        if df is None or len(df) < 100:
            return None
        
        return df[df.index >= start_date]
    except Exception as e:
        _LOG.error(f"Error downloading {symbol} {timeframe}: {e}")
        return None


async def process_single_symbol(symbol, timeframes, months, ml_predictor):
    """Processa un singolo simbolo (eseguito in parallelo)"""
    exchange = create_exchange()
    
    try:
        # Download data
        historical_data = {}
        for tf in timeframes:
            df = await download_historical_data(exchange, symbol, tf, months)
            if df is not None:
                historical_data[tf] = df
        
        if not historical_data:
            return [], None, 0, 0
        
        trade_manager = BacktestTradeManager()
        primary_df = historical_data[timeframes[0]]
        
        _LOG.info(f"🔄 {symbol}: Walk-forward ({len(primary_df)} candles)")
        
        signals_count = 0
        trades_count = 0
        required_candles = max([get_timesteps_for_timeframe(tf) for tf in timeframes])
        
        for candle_idx in range(len(primary_df)):
            current_candle = primary_df.iloc[candle_idx]
            current_price = current_candle['close']
            current_time = current_candle.name.isoformat()
            
            trade_manager.update_trades(symbol, current_price, current_time)
            
            if symbol in trade_manager.active_trades or candle_idx < required_candles:
                continue
            
            # Prepare data
            dataframes_for_pred = {}
            for tf in timeframes:
                if tf in historical_data:
                    df_tf = historical_data[tf]
                    idx = df_tf.index.get_indexer([current_candle.name], method='ffill')[0]
                    if idx >= 0:
                        dataframes_for_pred[tf] = df_tf.iloc[:idx+1]
            
            if not dataframes_for_pred:
                continue
            
            try:
                # ML Prediction
                ensemble_conf, final_signal, tf_preds = ml_predictor.predict_for_symbol(
                    symbol, dataframes_for_pred, required_candles
                )
                
                if ensemble_conf is None or final_signal != 1:
                    continue
                
                signals_count += 1
                
                # RL Filter
                market_ctx = build_market_context(symbol, dataframes_for_pred)
                portfolio_state = {
                    'available_balance': 1000.0, 'wallet_balance': 1000.0,
                    'active_positions': len(trade_manager.active_trades),
                    'total_realized_pnl': 0.0, 'unrealized_pnl_pct': 0.0
                }
                
                should_execute, rl_conf, _ = global_rl_agent.should_execute_signal(
                    {'symbol': symbol, 'confidence': ensemble_conf, 'tf_predictions': tf_preds},
                    market_ctx, portfolio_state
                )
                
                if not should_execute:
                    continue
                
                trade_manager.open_trade(symbol, current_price, current_time, ensemble_conf, rl_conf, tf_preds)
                trades_count += 1
                
            except:
                continue
        
        # Close remaining
        for ts in list(trade_manager.active_trades.keys()):
            last = primary_df.iloc[-1]
            trade_manager._close_trade(ts, last['close'], last.name.isoformat(), 'backtest_end')
        
        # Viz data
        symbol_trades = trade_manager.get_completed_trades()
        viz_data = None
        if symbol_trades:
            viz_data = {
                'candles': primary_df[['open', 'high', 'low', 'close', 'volume']].copy(),
                'trades': symbol_trades,
                'num_trades': len(symbol_trades)
            }
        
        _LOG.info(f"✅ {symbol}: {trades_count} trades from {signals_count} signals")
        return symbol_trades, viz_data, signals_count, trades_count
        
    finally:
        await exchange.close()


def run_symbol_sync(args):
    """Wrapper sincrono per thread pool"""
    symbol, timeframes, months, ml_predictor = args
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return symbol, loop.run_until_complete(
            process_single_symbol(symbol, timeframes, months, ml_predictor)
        )
    finally:
        loop.close()


async def run_backtest_calibration(symbols, timeframes, months=6, max_workers=8):
    """Esegui backtest PARALLELIZZATO"""
    _LOG.info("=" * 100)
    _LOG.info("🎯 STARTING PARALLEL BACKTEST CALIBRATION")
    _LOG.info("=" * 100)
    _LOG.info(f"Symbols: {len(symbols)} | Workers: {max_workers} | Period: {months} months")
    _LOG.info("=" * 100)
    
    # Load ML models
    _LOG.info("\n📚 Loading ML models...")
    ml_predictor = RobustMLPredictor(timeframes=timeframes)
    
    if not ml_predictor.is_operational():
        _LOG.error("❌ ML models not loaded")
        return
    
    _LOG.info("✅ ML models loaded")
    
    # Disable calibration during backtest
    from core.confidence_calibrator import global_calibrator
    original_state = global_calibrator.is_calibrated
    global_calibrator.is_calibrated = False
    _LOG.info("🔧 Calibration disabled (collecting RAW confidence)")
    
    # Parallel processing
    _LOG.info(f"\n🚀 Starting parallel processing with {max_workers} workers...")
    
    all_trades = []
    all_viz_data = {}
    total_signals = 0
    total_trades = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all symbols
        futures = {
            executor.submit(run_symbol_sync, (sym, timeframes, months, ml_predictor)): sym 
            for sym in symbols
        }
        
        # Progress bar
        with tqdm(total=len(symbols), desc="📊 Symbols", unit="symbol") as pbar:
            for future in as_completed(futures):
                try:
                    symbol, (trades, viz_data, sigs, trd_cnt) = future.result()
                    
                    all_trades.extend(trades)
                    if viz_data:
                        all_viz_data[symbol] = viz_data
                    
                    total_signals += sigs
                    total_trades += trd_cnt
                    
                    pbar.set_description(f"📊 Completed {symbol[:15]}")
                    pbar.update(1)
                    
                except Exception as e:
                    symbol = futures[future]
                    _LOG.error(f"❌ Error processing {symbol}: {e}")
                    pbar.update(1)
    
    _LOG.info("\n" + "=" * 100)
    _LOG.info("📊 BACKTEST COMPLETED")
    _LOG.info("=" * 100)
    _LOG.info(f"Total signals: {total_signals}")
    _LOG.info(f"Total trades: {total_trades}")
    _LOG.info(f"Completed trades: {len(all_trades)}")
    
    if not all_trades:
        _LOG.error("❌ No trades completed")
        return
    
    # Statistics
    wins = sum(1 for t in all_trades if t['result'] == 'WIN')
    losses = len(all_trades) - wins
    win_rate = (wins / len(all_trades)) * 100
    avg_pnl = np.mean([t['pnl_pct'] for t in all_trades])
    
    _LOG.info(f"Win rate: {win_rate:.1f}% ({wins}W/{losses}L)")
    _LOG.info(f"Average PnL: {avg_pnl:+.2f}%")
    
    # Generate calibration
    _LOG.info("\n🎯 Generating calibration table...")
    analyzer = CalibrationAnalyzer()
    for trade in all_trades:
        analyzer.add_trade(trade)
    
    analyzer.analyze_and_generate_calibration("confidence_calibration.json")
    
    # Restore calibration
    global_calibrator.is_calibrated = original_state
    global_calibrator.load_calibration()
    _LOG.info("🔧 Calibration re-enabled with new data")
    
    _LOG.info("\n✅ CALIBRATION COMPLETE!")
    _LOG.info(f"📁 File: confidence_calibration.json")
    _LOG.info(f"📊 Based on {len(all_trades)} trades")
    
    # Save viz data (top 5)
    if all_viz_data:
        top_5 = sorted(all_viz_data.items(), key=lambda x: x[1]['num_trades'], reverse=True)[:5]
        
        viz_export = {}
        for symbol, data in top_5:
            viz_export[symbol] = {
                'candles': data['candles'].reset_index().to_dict('records'),
                'trades': data['trades'],
                'num_trades': data['num_trades']
            }
        
        import json
        with open('backtest_visualization_data.json', 'w') as f:
            json.dump(viz_export, f, indent=2, default=str)
        
        _LOG.info(f"\n📊 Viz data saved: backtest_visualization_data.json")
        _LOG.info(f"   Top 5: {[s for s, _ in top_5]}")


async def get_top_symbols(exchange, top_n=30):
    """Ottieni top N simboli per volume da Bybit (come in main.py)"""
    try:
        _LOG.info(f"🔍 Fetching top {top_n} symbols by volume from Bybit...")
        
        # Load markets
        markets = await exchange.load_markets()
        
        # Filter USDT perpetual futures
        usdt_perps = [
            {'symbol': symbol, 'info': market}
            for symbol, market in markets.items()
            if market.get('quote') == 'USDT' 
            and market.get('settle') == 'USDT'
            and market.get('type') == 'swap'
            and market.get('active', True)
        ]
        
        # Get tickers for volume sorting
        tickers = await exchange.fetch_tickers()
        
        # Add volume info
        for item in usdt_perps:
            symbol = item['symbol']
            if symbol in tickers:
                item['volume'] = tickers[symbol].get('quoteVolume', 0) or 0
            else:
                item['volume'] = 0
        
        # Sort by volume and take top N
        sorted_symbols = sorted(usdt_perps, key=lambda x: x['volume'], reverse=True)[:top_n]
        
        symbols = [item['symbol'] for item in sorted_symbols]
        
        _LOG.info(f"✅ Selected top {len(symbols)} symbols by 24h volume")
        _LOG.info(f"   Top 5: {symbols[:5]}")
        
        return symbols
        
    except Exception as e:
        _LOG.error(f"❌ Error fetching symbols: {e}")
        _LOG.warning("⚠️ Using fallback predefined symbols...")
        
        # Fallback to predefined list
        return [
            'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'BNB/USDT:USDT',
            'XRP/USDT:USDT', 'DOGE/USDT:USDT', 'ADA/USDT:USDT', 'TRX/USDT:USDT',
            'DOT/USDT:USDT', 'MATIC/USDT:USDT', 'LINK/USDT:USDT', 'AVAX/USDT:USDT',
            'LTC/USDT:USDT', 'ATOM/USDT:USDT', 'UNI/USDT:USDT', 'NEAR/USDT:USDT',
            'FIL/USDT:USDT', 'APT/USDT:USDT', 'ARB/USDT:USDT', 'OP/USDT:USDT',
            'AAVE/USDT:USDT', 'FTM/USDT:USDT', 'INJ/USDT:USDT', 'SUI/USDT:USDT',
            'SEI/USDT:USDT', 'PEPE/USDT:USDT', 'WLD/USDT:USDT', 'TIA/USDT:USDT',
            'ALGO/USDT:USDT', 'ETC/USDT:USDT'
        ]


async def main():
    parser = argparse.ArgumentParser(description='Parallel backtest calibration')
    parser.add_argument('--months', type=int, default=6, help='Months of data (default: 6)')
    parser.add_argument('--workers', type=int, default=8, help='Parallel workers (default: 8)')
    parser.add_argument('--symbols', type=int, default=30, help='Number of top symbols (default: 30)')
    args = parser.parse_args()
    
    from config import ENABLED_TIMEFRAMES
    
    # Get top symbols dynamically from Bybit
    exchange = create_exchange()
    try:
        symbols = await get_top_symbols(exchange, top_n=args.symbols)
    finally:
        await exchange.close()
    
    _LOG.info(f"✅ Using {len(symbols)} symbols with {args.workers} workers")
    
    try:
        await run_backtest_calibration(symbols, ENABLED_TIMEFRAMES, args.months, args.workers)
    finally:
        # Close any remaining aiohttp sessions
        await asyncio.sleep(0.25)  # Allow pending tasks to complete
        _LOG.info("✅ All sessions closed")


if __name__ == "__main__":
    print(colored("\n" + "="*100, "cyan", attrs=['bold']))
    print(colored("🎯 PARALLEL BACKTEST CALIBRATION SYSTEM", "cyan", attrs=['bold']))
    print(colored("="*100 + "\n", "cyan", attrs=['bold']))
    
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
