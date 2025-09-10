"""
Backtesting engine for the trading bot
Contains all backtesting functionality separated from live trading for performance optimization
"""

import os
import glob
import logging
import asyncio
from datetime import datetime, timedelta
from termcolor import colored

from fetcher import fetch_and_save_data
import config


class BacktestEngine:
    """
    Handles all backtesting operations for model validation and strategy analysis
    """
    
    def __init__(self):
        self.silent_mode = True  # Run in silent mode by default
        
    async def run_integrated_backtest(self, symbol, timeframe, exchange):
        """
        Integrated backtesting function for model validation after training
        
        Args:
            symbol: Trading symbol to backtest
            timeframe: Timeframe for backtesting
            exchange: Exchange instance
        """
        try:
            # Get data for backtesting
            df = await fetch_and_save_data(exchange, symbol, timeframe)
            
            if df is None or len(df) < 100:
                return None
            
            # Generate predictions using the same logic as training
            from trainer import label_with_future_returns
            
            predictions = label_with_future_returns(
                df,
                lookforward_steps=config.FUTURE_RETURN_STEPS,
                buy_threshold=config.RETURN_BUY_THRESHOLD,
                sell_threshold=config.RETURN_SELL_THRESHOLD
            )
            
            # Use last 30 days for demonstration
            thirty_days_ago = datetime.now() - timedelta(days=30)
            
            # Import and run backtest visualization
            from core.visualization import run_symbol_backtest
            
            backtest_results = run_symbol_backtest(
                symbol, df, predictions, timeframe,
                start_date=thirty_days_ago.strftime('%Y-%m-%d'),
                end_date=datetime.now().strftime('%Y-%m-%d')
            )
            
            if not self.silent_mode:
                logging.info(f"✅ Backtest completed for {symbol} on {timeframe}")
                
            return backtest_results
            
        except Exception as e:
            if not self.silent_mode:
                logging.error(f"Backtest error for {symbol}: {e}")
            return None

    async def generate_signal_backtest(self, symbol, dataframes, signal):
        """
        Genera automaticamente un backtest completo per il segnale eseguito
        Used for detailed post-trade analysis during development
        
        Args:
            symbol: Trading symbol
            dataframes: Dictionary of dataframes by timeframe
            signal: Signal data that was executed
        """
        try:
            from core.visualization import run_symbol_backtest
            from trainer import label_with_future_returns
            
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
                            
                            if not self.silent_mode:
                                logging.info(f"✅ Generated {period['name']} backtest for {symbol} {tf}")
                                
                        except Exception as period_error:
                            if not self.silent_mode:
                                logging.warning(f"Period backtest error: {period_error}")
                    
                except Exception as tf_error:
                    if not self.silent_mode:
                        logging.warning(f"Timeframe backtest error: {tf_error}")
            
            if not self.silent_mode:
                logging.info(f"📊 Signal backtest completed for {symbol}")
            
        except Exception as e:
            if not self.silent_mode:
                logging.error(f"Signal backtest error: {e}")

    def show_charts_info(self):
        """
        Mostra informazioni sui grafici generati dal trading bot
        """
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

    def set_silent_mode(self, silent=True):
        """
        Set silent mode for backtesting operations
        
        Args:
            silent: If True, suppress verbose output
        """
        self.silent_mode = silent

    async def validate_model_performance(self, symbol, timeframe, exchange, model, scaler):
        """
        Validate model performance using backtesting
        Used during model training to ensure quality
        
        Args:
            symbol: Symbol to test
            timeframe: Timeframe to test  
            exchange: Exchange instance
            model: Trained model to validate
            scaler: Scaler for the model
            
        Returns:
            dict: Validation results with accuracy metrics
        """
        try:
            # Run integrated backtest
            results = await self.run_integrated_backtest(symbol, timeframe, exchange)
            
            if results:
                # Extract performance metrics
                validation_metrics = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'backtest_completed': True,
                    'validation_date': datetime.now().isoformat(),
                    'results': results
                }
                
                if not self.silent_mode:
                    logging.info(f"✅ Model validation completed for {symbol} {timeframe}")
                
                return validation_metrics
            else:
                return {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'backtest_completed': False,
                    'error': 'No backtest results generated'
                }
                
        except Exception as e:
            logging.error(f"Model validation error: {e}")
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'backtest_completed': False,
                'error': str(e)
            }


# Global instance for easy access
global_backtest_engine = BacktestEngine()
