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
from fetcher import fetch_markets, get_top_symbols, fetch_min_amounts, fetch_and_save_data
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

# Import enhanced terminal display
try:
    from core.terminal_display import (
        init_terminal_display, display_enhanced_signal, 
        display_analysis_progress, display_cycle_complete,
        display_model_status, display_portfolio_status, terminal_display,
        display_wallet_and_positions
    )
    ENHANCED_DISPLAY_AVAILABLE = True
    logging.info("✅ Enhanced Terminal Display loaded successfully")
except ImportError as e:
    logging.warning(f"⚠️ Enhanced Terminal Display not available: {e}")
    ENHANCED_DISPLAY_AVAILABLE = False

# Import position tracking system
try:
    from core.position_tracker import global_position_tracker
    POSITION_TRACKER_AVAILABLE = True
    logging.info("✅ Position Tracker loaded successfully")
except ImportError as e:
    logging.warning(f"⚠️ Position Tracker not available: {e}")
    POSITION_TRACKER_AVAILABLE = False

if sys.platform.startswith('win'):
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

first_cycle = True

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
    
    # Check for all types of files
    for name, dir_path in [("TRAINING METRICS", training_dir), ("BACKTEST CHARTS", backtest_dir), ("TEXT REPORTS", reports_dir)]:
        files = glob.glob(os.path.join(dir_path, "*"))
        print(colored(f"📊 {name}:", "green", attrs=['bold']))
        if files:
            for file_path in files:
                filename = os.path.basename(file_path)
                size = os.path.getsize(file_path)
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                print(f"   ✅ {filename}")
                print(f"      📄 {size:,} bytes | 📅 {mtime.strftime('%H:%M:%S')}")
        else:
            print("   📭 Nessun file trovato")
        print()
    
    print(colored("💡 TIP: Apri Windows Explorer e vai ai percorsi sopra per vedere i file!", "yellow"))
    print(colored("=" * 80, "cyan"))

async def run_integrated_backtest(symbol, timeframe, exchange):
    """
    Integrated backtesting function for demonstration
    """
    try:
        logging.info(colored(f"📈 Running integrated backtest for {symbol} [{timeframe}]", "cyan"))
        
        # Get data for backtesting
        df = await fetch_and_save_data(exchange, symbol, timeframe)
        
        if df is None or len(df) < 100:
            logging.warning(f"⚠️ Insufficient data for backtesting {symbol}")
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
        
        if backtest_results.get('stats'):
            stats = backtest_results['stats']
            logging.info(colored(f"📊 Backtest Demo Results for {symbol}:", "green"))
            logging.info(colored(f"   💰 Total Return: {stats['total_return_pct']:.2f}%", "yellow"))
            logging.info(colored(f"   🎯 Total Trades: {stats['total_trades']}", "yellow"))
            logging.info(colored(f"   ✅ Win Rate: {stats['win_rate']:.1f}%", "yellow"))
            logging.info(colored(f"   📈 Avg Return: {stats['avg_return']:.2f}%", "yellow"))
            logging.info(colored(f"   🏆 Sharpe Ratio: {stats['sharpe_ratio']:.3f}", "yellow"))
            logging.info(colored(f"   📊 Charts and reports saved to visualizations/", "green"))
        
    except Exception as e:
        logging.warning(f"Backtest demo failed for {symbol}: {e}")

async def generate_signal_backtest(symbol, dataframes, signal):
    """
    Genera automaticamente un backtest completo per il segnale eseguito
    """
    try:
        from core.visualization import run_symbol_backtest
        from trainer import label_with_future_returns
        from datetime import datetime, timedelta
        import config
        
        logging.info(colored(f"📊 Generating comprehensive backtest for {symbol}", "blue"))
        
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
                        
                        # Esegui backtest per questo periodo
                        backtest_results = run_symbol_backtest(
                            symbol, df, historical_predictions, tf,
                            start_date=start_date.strftime('%Y-%m-%d'),
                            end_date=end_date.strftime('%Y-%m-%d')
                        )
                        
                        if backtest_results.get('stats'):
                            stats = backtest_results['stats']
                            
                            logging.info(colored(f"📊 {symbol} [{tf}] - {period['name']} Backtest:", "green"))
                            logging.info(colored(f"   💰 Return: {stats['total_return_pct']:.2f}% | Win Rate: {stats['win_rate']:.1f}% | Trades: {stats['total_trades']}", "yellow"))
                            logging.info(colored(f"   📈 Sharpe: {stats['sharpe_ratio']:.3f} | Avg Return: {stats['avg_return']:.2f}%", "yellow"))
                            
                    except Exception as period_error:
                        logging.warning(f"Failed to generate {period['name']} backtest for {symbol}[{tf}]: {period_error}")
                        continue
                
                # Aggiungi analisi della confidence del segnale attuale
                logging.info(colored(f"🎯 Current Signal Analysis for {symbol} [{tf}]:", "cyan"))
                logging.info(colored(f"   Signal: {signal['signal_name']} | Confidence: {signal['confidence']:.1%}", "cyan"))
                logging.info(colored(f"   Reasoning: {signal['confidence_explanation']}", "cyan"))
                
            except Exception as tf_error:
                logging.warning(f"Failed to generate backtest for {symbol}[{tf}]: {tf_error}")
                continue
        
        logging.info(colored(f"✅ Backtesting completed for {symbol} - Check visualizations folder for charts", "green"))
        
    except Exception as e:
        logging.error(f"Error generating signal backtest for {symbol}: {e}")

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
            # Collect all signals during analysis phase
            all_signals = []
            
            logging.info(colored("🔍 PHASE 1: COLLECTING ALL SIGNALS", "cyan", attrs=['bold']))

            markets = await fetch_markets(async_exchange)
            all_symbols_analysis = [m['symbol'] for m in markets.values() if m.get('quote') == 'USDT'
                                    and m.get('active') and m.get('type') == 'swap'
                                    and not re.search('|'.join(EXCLUDED_SYMBOLS), m['symbol'])]
            top_symbols_analysis = await get_top_symbols(async_exchange, all_symbols_analysis, top_n=TOP_ANALYSIS_CRYPTO)
            logging.info(f"{colored('📊 Analyzing symbols:', 'cyan')} {len(top_symbols_analysis)} total")

            reference_counts = {}
            first_symbol = top_symbols_analysis[0]
            for tf in ENABLED_TIMEFRAMES:
                df = await fetch_and_save_data(async_exchange, first_symbol, tf)
                if df is not None:
                    reference_counts[tf] = len(df)

            usdt_balance = await get_real_balance(async_exchange)
            if usdt_balance is None:
                logging.warning(colored("⚠️ Failed to get USDT balance. Retrying in 5 seconds.", "yellow"))
                await asyncio.sleep(5)
                return
            open_positions_count = await get_open_positions(async_exchange)

            # PHASE 1: COLLECT ALL SIGNALS
            for index, symbol in enumerate(top_symbols_analysis, start=1):
                try:
                    if ENHANCED_DISPLAY_AVAILABLE:
                        display_analysis_progress(index, len(top_symbols_analysis), symbol)
                    
                    dataframes = {}
                    skip_symbol = False

                    for tf in ENABLED_TIMEFRAMES:
                        df = await fetch_and_save_data(async_exchange, symbol, tf)
                        if df is None or len(df) < reference_counts[tf] * 0.95:
                            skip_symbol = True
                            break
                        dataframes[tf] = df

                    if skip_symbol:
                        continue

                    ensemble_value, final_signal, tf_predictions = predict_signal_ensemble(
                        dataframes, xgb_models, xgb_scalers, symbol, TIME_STEPS
                    )
                    
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
                        'dataframes': dataframes
                    }
                    
                    all_signals.append(signal_data)
                    
                except Exception as e:
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

    logging.info(colored("🚀 Avvio trading bot ristrutturato", "cyan"))

    async_exchange = ccxt_async.bybit(exchange_config)
    await async_exchange.load_markets()
    await async_exchange.load_time_difference()

    try:
        markets = await fetch_markets(async_exchange)
        all_symbols = [m['symbol'] for m in markets.values() if m.get('quote') == 'USDT'
                       and m.get('active') and m.get('type') == 'swap']
        all_symbols_analysis = [s for s in all_symbols if not re.search('|'.join(EXCLUDED_SYMBOLS), s)]

        top_symbols_analysis = await get_top_symbols(async_exchange, all_symbols_analysis, top_n=TOP_ANALYSIS_CRYPTO)
        top_symbols_training = await get_top_symbols(async_exchange, all_symbols, top_n=TOP_TRAIN_CRYPTO)

        # Smart data validation
        validated_symbols = []
        for symbol in top_symbols_training:
            is_valid_symbol = True
            for tf in ENABLED_TIMEFRAMES:
                df = await fetch_and_save_data(async_exchange, symbol, tf)
                if df is not None:
                    price_cols = ['open', 'high', 'low', 'close', 'volume']
                    has_price_nans = df[price_cols].isnull().any().any()
                    has_price_infs = np.isinf(df[price_cols]).any().any()
                    too_few_valid_rows = len(df.dropna()) < 100
                    
                    if has_price_nans or has_price_infs or too_few_valid_rows:
                        is_valid_symbol = False
                        break
                else:
                    is_valid_symbol = False
                    break
            
            if is_valid_symbol:
                validated_symbols.append(symbol)
        
        top_symbols_training = validated_symbols

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
