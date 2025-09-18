"""
Configuration Manager for the trading bot
Handles interactive/headless configuration and settings management
"""

import os
import sys
import logging
import time
import threading
import select
from termcolor import colored
import config


class ConfigManager:
    """Manages bot configuration in both interactive and headless modes"""
    
    def __init__(self):
        self.selected_timeframes = []
        self.selected_models = ['xgb']  # Only XGBoost for now
        self.demo_mode = True
        self.raw_weights = {}
        self.normalized_weights = {}
    
    def select_config(self):
        """
        Configuration selection with environment variable support for headless operation.
        """
        default_timeframes = "15m,30m,1h"
        
        # Check if running in non-interactive mode
        interactive_mode = os.getenv('BOT_INTERACTIVE', 'true').lower() != 'false'
        
        if interactive_mode:
            self._interactive_config(default_timeframes)
        else:
            self._headless_config(default_timeframes)
        
        # Apply configuration to global config
        self._apply_configuration()
        
        return self.selected_timeframes, self.selected_models, self.demo_mode
    
    def _interactive_config(self, default_timeframes):
        """Handle interactive configuration"""
        print("\n=== Configurazione Avanzata ===")
        
        # Mode selection
        print("\n🎮 Scegli modalità:")
        print("1. DEMO - Solo segnali (nessun trade reale)")
        print("2. LIVE - Trading reale su Bybit")
        print("Quale modalità vuoi utilizzare? [default: 2]:")
        
        mode_input = self._input_with_timeout(5, "2")
        
        # Timeframes selection
        print("\nInserisci i timeframe da utilizzare tra le seguenti opzioni: '1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d' (minimo 1, massimo 3, separati da virgola) [default: 15m,30m,1h]:")
        
        tf_input = self._input_with_timeout(5, default_timeframes)
            
        self._process_inputs(mode_input, tf_input, default_timeframes, interactive_mode=True)
    
    def _headless_config(self, default_timeframes):
        """Handle headless configuration using environment variables"""
        logging.info("Running in headless mode, using environment variables")
        mode_input = os.getenv('BOT_MODE', '2')
        tf_input = os.getenv('BOT_TIMEFRAMES', default_timeframes)
        
        self._process_inputs(mode_input, tf_input, default_timeframes, interactive_mode=False)
    
    def _process_inputs(self, mode_input, tf_input, default_timeframes, interactive_mode=True):
        """Process configuration inputs"""
        self.demo_mode = mode_input == "1"
        self.selected_timeframes = [tf.strip() for tf in tf_input.split(',') if tf.strip()]
        
        # Validate timeframes
        if len(self.selected_timeframes) < 1 or len(self.selected_timeframes) > 3:
            error_msg = f"Invalid timeframe count: {len(self.selected_timeframes)}. Must be 1-3 timeframes."
            if interactive_mode:
                print(error_msg)
                sys.exit(1)
            else:
                logging.error(error_msg)
                logging.info("Using default timeframes instead")
                self.selected_timeframes = [tf.strip() for tf in default_timeframes.split(',')]
        
        # Display configuration summary
        config_summary = f"Modalità: {'🎮 DEMO (Solo segnali)' if self.demo_mode else '🔴 LIVE (Trading reale)'}, Timeframes: {', '.join(self.selected_timeframes)}, Modelli: XGBoost"
        
        if interactive_mode:
            print("\n=== Riepilogo Configurazione ===")
            print(config_summary)
            print("===============================\n")
        else:
            logging.info(f"Bot Configuration: {config_summary}")
    
    def _apply_configuration(self):
        """Apply configuration to global config module"""
        config.ENABLED_TIMEFRAMES = self.selected_timeframes
        config.TIMEFRAME_DEFAULT = self.selected_timeframes[0]
        config.DEMO_MODE = self.demo_mode
        
        # Calculate weights
        self._calculate_weights()
    
    def _calculate_weights(self):
        """Calculate raw and normalized weights for models"""
        self.raw_weights = {}
        for tf in self.selected_timeframes:
            self.raw_weights[tf] = {}
            for model in self.selected_models:
                self.raw_weights[tf][model] = config.MODEL_RATES.get(model, 0)
        
        self.normalized_weights = self._normalize_weights(self.raw_weights)
    
    def _normalize_weights(self, raw_weights):
        """Normalize weights to sum to 1"""
        normalized = {}
        for tf, weights in raw_weights.items():
            total = sum(weights.values())
            if total > 0:
                normalized[tf] = {model: weight / total for model, weight in weights.items()}
            else:
                normalized[tf] = weights
        return normalized
    
    def get_weights(self):
        """Get normalized weights"""
        return self.normalized_weights
    
    def get_timeframes(self):
        """Get selected timeframes"""
        return self.selected_timeframes
    
    def get_default_timeframe(self):
        """Get default timeframe"""
        return self.selected_timeframes[0] if self.selected_timeframes else "15m"
    
    def is_demo_mode(self):
        """Check if running in demo mode"""
        return self.demo_mode
    
    def _input_with_timeout(self, timeout_seconds: int, default_value: str) -> str:
        """
        Input with countdown timer - auto-selects default after timeout
        
        Args:
            timeout_seconds: Seconds to wait before using default
            default_value: Default value to use if timeout
            
        Returns:
            str: User input or default value
        """
        import threading
        import time
        
        result = [None]
        
        def input_thread():
            try:
                result[0] = input().strip()
            except (EOFError, KeyboardInterrupt):
                result[0] = ""
        
        # Start input thread
        thread = threading.Thread(target=input_thread)
        thread.daemon = True
        thread.start()
        
        # Countdown
        for remaining in range(timeout_seconds, 0, -1):
            if result[0] is not None:
                break
            print(f"\r⏰ Auto-start in {remaining}s (default: {default_value})...", end='', flush=True)
            time.sleep(1)
        
        # Check if input was provided
        if result[0] is not None:
            print()  # New line
            return result[0] if result[0] else default_value
        else:
            print(f"\r✅ Auto-selected: {default_value}                    ")
            return default_value
