#!/usr/bin/env python3
import sys
import os
import numpy as np
import warnings

# Sopprimi i RuntimeWarning della libreria ta (per divisioni per zero nell'ADX)
warnings.filterwarnings("ignore", category=RuntimeWarning, module="ta")
np.seterr(divide='ignore', invalid='ignore')

from datetime import timedelta
import asyncio
import logging
import re
import ccxt.async_support as ccxt_async
from termcolor import colored
from tqdm import tqdm  # Import per la progress bar

from config import (
    exchange_config,
    EXCLUDED_SYMBOLS, TIME_STEPS, TRADE_CYCLE_INTERVAL,
    MODEL_RATES,  # I rate definiti in config; la somma DEVE essere pari a 1
    TOP_TRAIN_CRYPTO, TOP_ANALYSIS_CRYPTO, EXPECTED_COLUMNS,
    TRAIN_IF_NOT_FOUND  # Variabile di controllo per il training
)
from logging_config import *
from fetcher import fetch_markets, get_top_symbols, fetch_min_amounts, fetch_and_save_data, fetch_all_data_parallel, fetch_symbol_data_parallel

# Import database cache system
try:
    from core.database_cache import global_db_cache, display_database_stats
    DATABASE_SYSTEM_LOADED = True
    logging.info("🗄️ Database system integration loaded")
except ImportError as e:
    logging.warning(f"⚠️ Database system integration not available: {e}")
    DATABASE_SYSTEM_LOADED = False
from model_loader import (
    load_xgboost_model_func
)
from trainer import (
    train_xgboost_model_wrapper
)
from predictor import predict_signal_ensemble, get_color_normal
from trade_manager import (
    get_real_balance, manage_position, get_open_positions,
    update_orders_status
)
from data_utils import prepare_data
from trainer import ensure_trained_models_dir

# Import parallel prediction system
try:
    from core.parallel_predictor import predict_all_parallel, global_parallel_predictor
    PARALLEL_PREDICTOR_AVAILABLE = True
except ImportError as e:
    logging.warning(f"⚠️ Parallel Predictor not available: {e}")
    PARALLEL_PREDICTOR_AVAILABLE = False

# Import enhanced terminal display
try:
    from core.terminal_display import (
        init_terminal_display, display_enhanced_signal, 
        display_analysis_progress, display_cycle_complete,
        display_model_status, display_portfolio_status, terminal_display,
        display_wallet_and_positions
    )
    ENHANCED_DISPLAY_AVAILABLE = True
except ImportError as e:
    logging.warning(f"⚠️ Enhanced Terminal Display not available: {e}")
    ENHANCED_DISPLAY_AVAILABLE = False

# Import position tracking system
try:
    from core.position_tracker import global_position_tracker
    POSITION_TRACKER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"⚠️ Position Tracker not available: {e}")
    POSITION_TRACKER_AVAILABLE = False

if sys.platform.startswith('win'):
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

first_cycle = True

# Global flag to suppress verbose output during training/validation
SILENT_MODE = False

# --- Sezione: Configurazione automatica/interattiva ---
def select_config():
    """
    Configuration selection with environment variable support for headless operation.
    """
    default_timeframes = "15m,30m,1h"
    
    # Check if running in non-interactive mode
    interactive_mode = os.getenv('BOT_INTERACTIVE', 'true').lower() != 'false'
    
    if interactive_mode:
        print("\n=== Configurazione Avanzata ===")
        
        # Configurazione modalità demo/live
        print("\n🎮 Scegli modalità:")
        print("1. DEMO - Solo segnali (nessun trade reale)")
        print("2. LIVE - Trading reale su Bybit")
        print("Quale modalità vuoi utilizzare? [default: 1]:")
        
        try:
            mode_input = input().strip()
        except (EOFError, KeyboardInterrupt):
            print("Input interrupted, using default values")
            mode_input = "1"
        
        if not mode_input:
            mode_input = "1"
            
        # Configurazione timeframes
        print("\nInserisci i timeframe da utilizzare tra le seguenti opzioni: '1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d' (minimo 1, massimo 3, separati da virgola) [default: 15m,30m,1h]:")
        
        try:
            tf_input = input().strip()
        except (EOFError, KeyboardInterrupt):
            print("Input interrupted, using default timeframes")
            tf_input = default_timeframes
        
        if not tf_input:
            tf_input = default_timeframes
    else:
        # Headless mode - use environment variables
        logging.info("Running in headless mode, using environment variables")
        mode_input = os.getenv('BOT_MODE', '1')
        tf_input = os.getenv('BOT_TIMEFRAMES', default_timeframes)
        
    demo_mode = mode_input == "1"
    selected_timeframes = [tf.strip() for tf in tf_input.split(',') if tf.strip()]
    
    if len(selected_timeframes) < 1 or len(selected_timeframes) > 3:
        error_msg = f"Invalid timeframe count: {len(selected_timeframes)}. Must be 1-3 timeframes."
        if interactive_mode:
            print(error_msg)
            sys.exit(1)
        else:
            logging.error(error_msg)
            logging.info("Using default timeframes instead")
            selected_timeframes = [tf.strip() for tf in default_timeframes.split(',')]

    # Solo XGBoost
    selected_models = ['xgb']
    
    config_summary = f"Modalità: {'🎮 DEMO (Solo segnali)' if demo_mode else '🔴 LIVE (Trading reale)'}, Timeframes: {', '.join(selected_timeframes)}, Modelli: XGBoost"
    
    if interactive_mode:
        print("\n=== Riepilogo Configurazione ===")
        print(config_summary)
        print("===============================\n")
    else:
        logging.info(f"Bot Configuration: {config_summary}")
    
    return selected_timeframes, selected_models, demo_mode

# Esegui la selezione e aggiorna la configurazione
selected_timeframes, selected_models, demo_mode = select_config()
import config
config.ENABLED_TIMEFRAMES = selected_timeframes
config.TIMEFRAME_DEFAULT = selected_timeframes[0]
config.DEMO_MODE = demo_mode

# Aggiorna le variabili locali per comodità
ENABLED_TIMEFRAMES = selected_timeframes
TIMEFRAME_DEFAULT = ENABLED_TIMEFRAMES[0]

# --- Calcolo dei pesi raw e normalizzati per i modelli ---
raw_weights = {}
for tf in ENABLED_TIMEFRAMES:
    raw_weights[tf] = {}
    for model in selected_models:
        raw_weights[tf][model] = MODEL_RATES.get(model, 0)
def normalize_weights(raw_weights):
    normalized = {}
    for tf, weights in raw_weights.items():
        total = sum(weights.values())
        if total > 0:
            normalized[tf] = {model: weight / total for model, weight in weights.items()}
        else:
            normalized[tf] = weights
    return normalized
normalized_weights = normalize_weights(raw_weights)

# --- Funzioni ausiliarie ---
async def track_orders():
    while True:
        await update_orders_status(async_exchange)
        await asyncio.sleep(60)

async def countdown_timer(duration):
    for remaining in tqdm(range(duration, 0, -1), desc="Attesa ciclo successivo", ncols=80, ascii=True):
        await asyncio.sleep(1)
    print()

def show_charts_info():
    """
    Mostra informazioni sui grafici generati dal trading bot
    """
    import glob
    from datetime import datetime
    
    print(colored("\n📊 GRAFICI E VISUALIZZAZIONI SALVATE", "cyan", attrs=['bold']))
    print(colored("=" * 80, "cyan"))
    
    # Directory paths
    viz_dir = os.path.join(os.getcwd(), "visualizations")
    training_dir = os.path.join(viz_dir, "training")
    backtest_dir = os.path.join(viz_dir, "backtests")
    reports_dir = os.path.join(viz_dir, "reports")
    
    print(f"{colored('📁 Directory grafici:', 'yellow')} {viz_dir}")
    print(f"{colored('📊 Training metrics:', 'yellow')} {training_dir}")
    print(f"{colored('📈 Backtest charts:', 'yellow')} {backtest_dir}")
    print(f"{colored('📄 Text reports:', 'yellow')} {reports_dir}")
    print()
    
    # Check for all types of files (SILENCED)
    for name, dir_path in [("TRAINING METRICS", training_dir), ("BACKTEST CHARTS", backtest_dir), ("TEXT REPORTS", reports_dir)]:
        files = glob.glob(os.path.join(dir_path, "*"))
        # Silenced: print(colored(f"📊 {name}:", "green", attrs=['bold']))
        if files:
            for file_path in files:
                filename = os.path.basename(file_path)
                size = os.path.getsize(file_path)
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                # Silenced: print(f"   ✅ {filename}")
                # Silenced: print(f"      📄 {size:,} bytes | 📅 {mtime.strftime('%H:%M:%S')}")
        else:
            # Silenced: print("   📭 Nessun file trovato")
            pass
        # Silenced: print()
    
    print(colored("💡 TIP: Apri Windows Explorer e vai ai percorsi sopra per vedere i file!", "yellow"))
    print(colored("=" * 80, "cyan"))

async def run_integrated_backtest(symbol, timeframe, exchange):
    """
    Integrated backtesting function for demonstration - SILENT MODE
    """
    try:
        # Get data for backtesting
        df = await fetch_and_save_data(exchange, symbol, timeframe)
        
        if df is None or len(df) < 100:
            return
        
        # Generate predictions using the same logic as training
        from trainer import label_with_future_returns
        import config
        
        predictions = label_with_future_returns(
            df,
            lookforward_steps=config.FUTURE_RETURN_STEPS,
            buy_threshold=config.RETURN_BUY_THRESHOLD,
            sell_threshold=config.RETURN_SELL_THRESHOLD
        )
        
        # Use last 30 days for demonstration
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        # Import and run backtest visualization
        from core.visualization import run_symbol_backtest
        
        backtest_results = run_symbol_backtest(
            symbol, df, predictions, timeframe,
            start_date=thirty_days_ago.strftime('%Y-%m-%d'),
            end_date=datetime.now().strftime('%Y-%m-%d')
        )
        
        # Backtest executed silently - results saved to visualizations/
        
    except Exception as e:
        pass  # Silent execution

async def generate_signal_backtest(symbol, dataframes, signal):
    """
    Genera automaticamente un backtest completo per il segnale eseguito - SILENT MODE
    """
    try:
        from core.visualization import run_symbol_backtest
        from trainer import label_with_future_returns
        from datetime import datetime, timedelta
        import config
        
        # Per ogni timeframe, genera un backtest dettagliato
        for tf, df in dataframes.items():
            try:
                # Genera le predizioni storiche usando la stessa logica del training
                historical_predictions = label_with_future_returns(
                    df,
                    lookforward_steps=config.FUTURE_RETURN_STEPS,
                    buy_threshold=config.RETURN_BUY_THRESHOLD,
                    sell_threshold=config.RETURN_SELL_THRESHOLD
                )
                
                # Test su diverse finestre temporali
                test_periods = [
                    {"name": "Last_7_days", "days": 7},
                    {"name": "Last_30_days", "days": 30},
                    {"name": "Last_90_days", "days": 90}
                ]
                
                for period in test_periods:
                    try:
                        # Calcola date di inizio e fine
                        end_date = datetime.now()
                        start_date = end_date - timedelta(days=period["days"])
                        
                        # Assicurati che ci siano abbastanza dati
                        period_df = df[df.index >= start_date.strftime('%Y-%m-%d')]
                        if len(period_df) < 50:  # Minimo 50 candele
                            continue
                        
                        # Esegui backtest per questo periodo (silently)
                        backtest_results = run_symbol_backtest(
                            symbol, df, historical_predictions, tf,
                            start_date=start_date.strftime('%Y-%m-%d'),
                            end_date=end_date.strftime('%Y-%m-%d')
                        )
                        
                        # Results processed silently - saved to visualizations/
                            
                    except Exception as period_error:
                        pass  # Silent execution
                
            except Exception as tf_error:
                pass  # Silent execution
        
        # Backtests completed silently - results saved to visualizations/
        
    except Exception as e:
        pass  # Silent execution

def calculate_ensemble_confidence(tf_predictions, ensemble_value):
    """
    Calcola come viene determinata la confidence dell'ensemble
    
    Returns: explanation string
    """
    try:
        # Conta i voti per ogni classe
        vote_counts = {}
        for tf, pred in tf_predictions.items():
            vote_counts[pred] = vote_counts.get(pred, 0) + 1
        
        # Trova il segnale vincente
        winning_signal = max(vote_counts.items(), key=lambda x: x[1])[0]
        winning_votes = vote_counts[winning_signal]
        total_votes = sum(vote_counts.values())
        
        # Calcola percentage agreement
        agreement_pct = (winning_votes / total_votes) * 100
        
        signal_names = {0: 'SELL', 1: 'BUY', 2: 'NEUTRAL'}
        
        explanation = f"Confidence {ensemble_value:.1%} = {winning_votes}/{total_votes} timeframes agree on {signal_names[winning_signal]} ({agreement_pct:.1f}% consensus)"
        
        return explanation
        
    except Exception as e:
        return f"Confidence calculation error: {e}"

async def trade_signals():
    global async_exchange, xgb_models, xgb_scalers, min_amounts

    while True:
        try:
            import time
            cycle_start_time = time.time()
            
            # Collect all signals during analysis phase
            all_signals = []
            
            logging.info(colored("🚀 PHASE 1: PARALLEL DATA COLLECTION", "cyan", attrs=['bold']))

            markets = await fetch_markets(async_exchange)
            # Filter symbols - handle empty EXCLUDED_SYMBOLS properly
            if EXCLUDED_SYMBOLS:
                all_symbols_analysis = [m['symbol'] for m in markets.values() if m.get('quote') == 'USDT'
                                        and m.get('active') and m.get('type') == 'swap'
                                        and not re.search('|'.join(EXCLUDED_SYMBOLS), m['symbol'])]
            else:
                # No exclusions - include all USDT swap symbols
                all_symbols_analysis = [m['symbol'] for m in markets.values() if m.get('quote') == 'USDT'
                                        and m.get('active') and m.get('type') == 'swap']
            top_symbols_analysis = await get_top_symbols(async_exchange, all_symbols_analysis, top_n=TOP_ANALYSIS_CRYPTO)
            logging.info(f"{colored('📊 Analyzing symbols:', 'cyan')} {len(top_symbols_analysis)} total")

            usdt_balance = await get_real_balance(async_exchange)
            if usdt_balance is None:
                logging.warning(colored("⚠️ Failed to get USDT balance. Retrying in 5 seconds.", "yellow"))
                await asyncio.sleep(5)
                return
            open_positions_count = await get_open_positions(async_exchange)

            # 📊 OPTIMIZED DATA FETCHING - Clean Output
            print(colored("\n📥 DATA DOWNLOAD - Optimized Display", "yellow", attrs=['bold']))
            
            data_fetch_start = time.time()
            all_symbol_data = {}
            successful_downloads = 0
            
            # Clean symbol-by-symbol download with organized output
            for index, symbol in enumerate(top_symbols_analysis, 1):
                symbol_short = symbol.replace('/USDT:USDT', '')
                symbol_start_time = time.time()
                
                # Clean symbol header
                print(f"\n[{index}/{len(top_symbols_analysis)}] {colored(symbol_short, 'cyan', attrs=['bold'])}")
                
                dataframes = {}
                symbol_success = True
                timeframe_results = []
                
                # Download all timeframes for this symbol
                for tf in ENABLED_TIMEFRAMES:
                    try:
                        tf_start = time.time()
                        df = await fetch_and_save_data(async_exchange, symbol, tf)
                        tf_time = time.time() - tf_start
                        
                        if df is not None and len(df) > 100:
                            dataframes[tf] = df
                            # Clean, compact timeframe result
                            timeframe_results.append(f"  📥 {tf:>3}: {len(df):,} candles ✅ ({tf_time:.1f}s)")
                        else:
                            timeframe_results.append(f"  ❌ {tf:>3}: No data")
                            symbol_success = False
                    except Exception as e:
                        timeframe_results.append(f"  ❌ {tf:>3}: Error - {str(e)[:30]}...")
                        symbol_success = False
                
                # Display results for this symbol
                for result in timeframe_results:
                    print(colored(result, 'green' if '✅' in result else 'red'))
                
                # Symbol summary
                symbol_time = time.time() - symbol_start_time
                if symbol_success and len(dataframes) == len(ENABLED_TIMEFRAMES):
                    all_symbol_data[symbol] = dataframes
                    successful_downloads += 1
                    print(colored(f"  ✅ Complete: {len(ENABLED_TIMEFRAMES)}/{len(ENABLED_TIMEFRAMES)} timeframes ({symbol_time:.1f}s total)", 'green'))
                else:
                    missing_tf = len(ENABLED_TIMEFRAMES) - len(dataframes)
                    print(colored(f"  ❌ Failed: Missing {missing_tf} timeframes", 'red'))

            data_fetch_time = time.time() - data_fetch_start
            
            print(colored("=" * 120, "yellow"))
            print(colored(f"📊 DATA DOWNLOAD SUMMARY", "cyan", attrs=['bold']))
            if len(top_symbols_analysis) > 0:
                print(colored(f"✅ Successful downloads: {successful_downloads}/{len(top_symbols_analysis)} ({successful_downloads/len(top_symbols_analysis)*100:.1f}%)", "green"))
                print(colored(f"⏱️ Total download time: {data_fetch_time:.1f}s", "green"))
                print(colored(f"⚡ Average time per symbol: {data_fetch_time/len(top_symbols_analysis):.1f}s", "green"))
            else:
                print(colored(f"❌ No symbols found for analysis!", "red"))
                print(colored(f"⏱️ Total time: {data_fetch_time:.1f}s", "yellow"))
            print(colored("=" * 120, "yellow"))

            # Filter symbols with complete data for all timeframes
            complete_symbols = list(all_symbol_data.keys())
            
            logging.info(f"📊 Symbols with complete data ready for analysis: {len(complete_symbols)}")

            if not complete_symbols:
                logging.warning(colored("⚠️ No symbols with complete data this cycle", "yellow"))
            else:
                # 🚀 PARALLEL ML PREDICTIONS - MAJOR OPTIMIZATION!
                logging.info(colored("🧠 PHASE 2: PARALLEL ML PREDICTIONS", "cyan", attrs=['bold']))
                
                if PARALLEL_PREDICTOR_AVAILABLE:
                    ml_start_time = time.time()
                    
                    # Use parallel predictor
                    prediction_results = await predict_all_parallel(
                        all_symbol_data, xgb_models, xgb_scalers, TIME_STEPS
                    )
                    
                    ml_time = time.time() - ml_start_time
                    logging.info(colored(f"✅ Parallel ML predictions completed in {ml_time:.1f}s", "green"))
                    
                else:
                    # Fallback to sequential predictions
                    logging.warning("⚠️ Using sequential ML predictions (parallel predictor not available)")
                    prediction_results = {}
                    
                    for symbol in complete_symbols:
                        dataframes = all_symbol_data[symbol]
                        result = predict_signal_ensemble(dataframes, xgb_models, xgb_scalers, symbol, TIME_STEPS)
                        prediction_results[symbol] = result

                # Process prediction results into signal format
                for symbol, (ensemble_value, final_signal, tf_predictions) in prediction_results.items():
                    try:
                        if ensemble_value is None or final_signal is None or final_signal == 2:
                            continue

                        # Store signal with confidence details
                        confidence_explanation = calculate_ensemble_confidence(tf_predictions, ensemble_value)
                        
                        # Get current price for ranking
                        try:
                            ticker = await async_exchange.fetch_ticker(symbol)
                            current_price = ticker.get('last', 0)
                        except:
                            current_price = 0
                        
                        signal_data = {
                            'symbol': symbol,
                            'signal': final_signal,
                            'signal_name': 'BUY' if final_signal == 1 else 'SELL',
                            'confidence': ensemble_value,
                            'tf_predictions': tf_predictions,
                            'confidence_explanation': confidence_explanation,
                            'price': current_price,
                            'dataframes': all_symbol_data[symbol]  # Use pre-fetched data
                        }
                        
                        all_signals.append(signal_data)
                        
                    except Exception as e:
                        logging.error(f"Error processing signal for {symbol}: {e}")
                        continue

            # PHASE 2: RANK BY CONFIDENCE AND SELECT TOP SIGNALS
            print()
            logging.info(colored("📈 PHASE 2: RANKING AND SELECTING TOP SIGNALS", "green", attrs=['bold']))
            
            if not all_signals:
                logging.warning(colored("⚠️ No signals found this cycle", "yellow"))
            else:
                # Sort by confidence (highest first)
                all_signals.sort(key=lambda x: x['confidence'], reverse=True)
                
                # Show top 10 signals
                logging.info(colored("🏆 TOP 10 SIGNALS BY CONFIDENCE:", "yellow", attrs=['bold']))
                print(colored("-" * 120, "yellow"))
                print(colored(f"{'RANK':<4} {'SYMBOL':<20} {'SIGNAL':<6} {'CONFIDENCE':<12} {'EXPLANATION':<60} {'PRICE':<12}", "white", attrs=['bold']))
                print(colored("-" * 120, "yellow"))
                
                for i, signal in enumerate(all_signals[:10], 1):
                    symbol_short = signal['symbol'].replace('/USDT:USDT', '')
                    signal_color = 'green' if signal['signal_name'] == 'BUY' else 'red'
                    
                    confidence_pct = f"{signal['confidence']:.1%}"
                    print(f"{i:<4} {symbol_short:<20} {colored(signal['signal_name'], signal_color, attrs=['bold']):<6} {confidence_pct:<12} {signal['confidence_explanation']:<60} ${signal['price']:.6f}")
                
                print(colored("-" * 120, "yellow"))
                
            # PHASE 3: EXECUTE BEST SIGNALS AND GENERATE BACKTESTS
            from config import MAX_CONCURRENT_POSITIONS
            max_positions = MAX_CONCURRENT_POSITIONS - open_positions_count
            signals_to_execute = all_signals[:min(max_positions, len(all_signals))]
            
            if signals_to_execute:
                logging.info(colored(f"🚀 PHASE 3: EXECUTING TOP {len(signals_to_execute)} SIGNALS", "blue", attrs=['bold']))
                
                for signal in signals_to_execute:
                    try:
                        symbol = signal['symbol']
                        final_signal = signal['signal']
                        dataframes = signal['dataframes']
                        
                        logging.info(colored(f"🎯 Executing {signal['signal_name']} for {symbol} (confidence: {signal['confidence']:.1%})", "cyan"))
                        
                        # Execute the trade
                        result = await manage_position(
                            async_exchange, symbol, final_signal, usdt_balance, min_amounts,
                            None, None, None, None, dataframes[TIMEFRAME_DEFAULT]
                        )
                        
                        # Generate automatic backtest for this signal
                        await generate_signal_backtest(symbol, dataframes, signal)
                        
                        if result == "insufficient_balance":
                            logging.warning(f"❌ {symbol}: Insufficient balance")
                            break  # Stop trying if no balance
                        elif result == "max_trades_reached":
                            logging.warning(f"❌ Max trades reached")
                            break  # Stop if max trades reached
                            
                    except Exception as e:
                        logging.error(f"❌ Error executing {symbol}: {e}")
                        continue
            else:
                logging.info(colored("😐 No signals to execute this cycle", "yellow"))

            # Update position tracker with current prices for real-time PnL
            if POSITION_TRACKER_AVAILABLE:
                try:
                    # Collect current prices for active positions
                    current_prices = {}
                    for symbol in top_symbols_analysis[:10]:  # Check prices for top symbols
                        try:
                            ticker = await async_exchange.fetch_ticker(symbol)
                            current_prices[symbol] = ticker.get('last', 0)
                        except:
                            continue
                    
                    # Update positions and check for closes
                    positions_to_close = global_position_tracker.update_positions(current_prices)
                    
                    # Close positions that hit TP/SL/Trailing
                    for position in positions_to_close:
                        global_position_tracker.close_position(
                            position['position_id'], 
                            position['exit_price'], 
                            position['exit_reason']
                        )
                        logging.info(colored(f"🎯 {position['symbol']} closed: {position['exit_reason']} PnL: {position['final_pnl_pct']:+.2f}%", "yellow"))
                    
                    # Display enhanced wallet status
                    summary = global_position_tracker.get_session_summary()
                    display_wallet_and_positions(summary, leverage=10)
                    
                except Exception as tracker_error:
                    logging.warning(f"Position tracker error: {tracker_error}")

            # 🏆 PERFORMANCE SUMMARY - Show optimization results
            cycle_total_time = time.time() - cycle_start_time
            
            logging.info(colored("🏆 CYCLE PERFORMANCE SUMMARY", "cyan", attrs=['bold']))
            logging.info(colored("-" * 80, "cyan"))
            
            if 'data_fetch_time' in locals():
                logging.info(colored(f"📊 Data Fetching: {data_fetch_time:.1f}s (Cache-optimized: {len(top_symbols_analysis)} symbols × {len(ENABLED_TIMEFRAMES)} TF)", "green"))
            
            if 'ml_time' in locals():
                logging.info(colored(f"🧠 ML Predictions: {ml_time:.1f}s (Parallel: {len(complete_symbols)} symbols)", "green"))
            
            # Display database performance if available
            if DATABASE_SYSTEM_LOADED:
                try:
                    db_stats = global_db_cache.get_cache_stats()
                    logging.info(colored(f"🗄️ Database Performance: {db_stats['hit_rate_pct']:.1f}% hit rate, {db_stats['total_api_calls_saved']} API calls saved", "green"))
                except Exception as db_error:
                    logging.warning(f"Database stats error: {db_error}")
            
            logging.info(colored(f"🚀 Total Cycle: {cycle_total_time:.1f}s", "yellow"))
            logging.info(colored(f"⚡ Efficiency: {(len(top_symbols_analysis) * len(ENABLED_TIMEFRAMES)) / cycle_total_time:.1f} predictions/second", "yellow"))
            
            # Show estimated speedup compared to sequential approach
            estimated_sequential_time = len(top_symbols_analysis) * len(ENABLED_TIMEFRAMES) * 2  # ~2s per symbol/timeframe sequential
            speedup_factor = estimated_sequential_time / cycle_total_time if cycle_total_time > 0 else 1
            
            logging.info(colored(f"📈 Estimated speedup: {speedup_factor:.1f}x vs sequential approach", "green"))
            
            # Display detailed database statistics every few cycles
            global first_cycle
            if first_cycle:
                first_cycle = False
                if DATABASE_SYSTEM_LOADED:
                    display_database_stats()
            
            logging.info(colored("-" * 80, "cyan"))

            # Show cycle summary  
            if ENHANCED_DISPLAY_AVAILABLE:
                display_cycle_complete()
            
            logging.info(colored("🔄 Cycle complete - waiting for next cycle", "green"))
            await countdown_timer(TRADE_CYCLE_INTERVAL)

        except Exception as e:
            logging.error(f"{colored('Error in trade cycle:', 'red')} {e}")
            await asyncio.sleep(60)

# --- Funzione Main ---
async def main():
    global async_exchange, xgb_models, xgb_scalers, min_amounts

    logging.info(colored("🚀 Avvio trading bot ristrutturato con cache ottimizzata", "cyan"))

    async_exchange = ccxt_async.bybit(exchange_config)
    await async_exchange.load_markets()
    await async_exchange.load_time_difference()

    try:
        markets = await fetch_markets(async_exchange)
        all_symbols = [m['symbol'] for m in markets.values() if m.get('quote') == 'USDT'
                       and m.get('active') and m.get('type') == 'swap']
        all_symbols_analysis = [s for s in all_symbols if not re.search('|'.join(EXCLUDED_SYMBOLS), s)]

        # 🚀 SINGLE TICKER FETCH OPTIMIZATION - Evita duplicazione
        logging.info(colored("⚡ Fetching top symbols (single optimized call)...", "yellow"))
        
        # Una sola chiamata per entrambi i set, usa il più grande dei due
        max_symbols_needed = max(TOP_ANALYSIS_CRYPTO, TOP_TRAIN_CRYPTO)
        top_symbols_all = await get_top_symbols(async_exchange, all_symbols, top_n=max_symbols_needed)
        
        # Ora TUTTI i simboli sono inclusi (no esclusioni)
        top_symbols_analysis = top_symbols_all[:TOP_ANALYSIS_CRYPTO]
        
        # Training usa tutti i simboli (stesso set di analysis ora)  
        top_symbols_training = top_symbols_all[:TOP_TRAIN_CRYPTO]
        
        # 📋 DISPLAY SELECTED SYMBOLS - ANALYSIS SYMBOLS ONLY
        logging.info(colored(f"\n📊 SIMBOLI SELEZIONATI PER ANALISI ({len(top_symbols_analysis)} totali)", "cyan", attrs=['bold']))
        print(colored("=" * 100, "cyan"))
        print(colored(f"{'RANK':<6} {'SYMBOL':<25} {'VOLUME':<20} {'NOTES':<35}", "white", attrs=['bold']))
        print(colored("-" * 100, "cyan"))
        
        # Show ONLY the symbols that will be used for analysis
        for i, symbol in enumerate(top_symbols_analysis, 1):
            try:
                ticker = await async_exchange.fetch_ticker(symbol)
                volume = ticker.get('quoteVolume', 0)
            except:
                volume = 0
            
            symbol_short = symbol.replace('/USDT:USDT', '')
            volume_formatted = f"${volume:,.0f}" if volume > 0 else "N/A"
            
            print(f"{i:<6} {colored(symbol_short, 'green'):<25} {volume_formatted:<20} {'Selected for trading analysis':<35}")
            
            # Add separator every 10 symbols for readability
            if i % 10 == 0 and i < len(top_symbols_analysis):
                print(colored("─" * 100, "blue"))
        
        print(colored("=" * 100, "cyan"))
        print(colored(f"✅ ACTIVE: {len(top_symbols_analysis)} symbols will be analyzed each cycle (ALL top volume symbols included)", "green", attrs=['bold']))
        print(colored(f"🔄 REFRESH: Symbol ranking updates every trading cycle\n", "yellow"))
        
        logging.info(f"📊 Selected: {len(top_symbols_analysis)} analysis symbols, {len(top_symbols_training)} training symbols")

        # Use top symbols directly without validation for faster startup
        logging.info(colored("🚀 Using top volume symbols directly (no validation)", "green"))

        logging.info(f"{colored('Training symbols:', 'cyan')} {len(top_symbols_training)}")
        logging.info(f"{colored('Analysis symbols:', 'cyan')} {len(top_symbols_analysis)}")

        min_amounts = await fetch_min_amounts(async_exchange, top_symbols_analysis, markets)
        ensure_trained_models_dir()
        
        # Initialize models with visualization
        xgb_models = {}
        xgb_scalers = {}
        
        logging.info(colored("🧠 Initializing ML models...", "cyan"))
        
        for tf in ENABLED_TIMEFRAMES:
            xgb_models[tf], xgb_scalers[tf] = await asyncio.to_thread(load_xgboost_model_func, tf)
        
            if not xgb_models[tf]:
                if TRAIN_IF_NOT_FOUND:
                    logging.info(colored(f"🎯 Training new model for {tf}", "yellow"))
                    
                    xgb_models[tf], xgb_scalers[tf], training_metrics = await train_xgboost_model_wrapper(
                        top_symbols_training, async_exchange, timestep=TIME_STEPS, 
                        timeframe=tf, use_future_returns=True
                    )
                    
                    if xgb_models[tf] and training_metrics:
                        logging.info(colored(f"✅ Model trained for {tf}: Accuracy {training_metrics.get('val_accuracy', 0):.3f}", "green"))
                        
                        try:
                            await run_integrated_backtest(top_symbols_training[0], tf, async_exchange)
                        except Exception as bt_error:
                            logging.warning(f"Backtest demo failed: {bt_error}")
                    
                else:
                    raise Exception(f"XGBoost model for timeframe {tf} not available. Train models first.")

        logging.info(colored("🎉 All models ready!", "green"))
        show_charts_info()

        # Start trading signals
        await asyncio.gather(trade_signals())
        
    except KeyboardInterrupt:
        logging.info(colored("Interrupt signal received. Shutting down...", "red"))
    except Exception as e:
        error_msg = str(e)
        logging.error(f"{colored('Error in main loop:', 'red')} {error_msg}")
        if "invalid request, please check your server timestamp" in error_msg:
            logging.info(colored("Timestamp error detected. Restarting script...", "red"))
            os.execv(sys.executable, [sys.executable] + sys.argv)
    finally:
        await async_exchange.close()
        logging.info(colored("Program terminated.", "red"))

if __name__ == "__main__":
    asyncio.run(main())
