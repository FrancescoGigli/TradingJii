"""
Signal Processor for the trading bot
Handles signal processing, RL filtering, and decision analysis
"""

import logging
from termcolor import colored

from utils.display_utils import calculate_ensemble_confidence, display_symbol_decision_analysis


class SignalProcessor:
    """
    Processes ML predictions into trading signals and applies RL filtering
    """
    
    def __init__(self):
        self.rl_agent_available = False
        self.position_manager_available = False
        
        # Try to import RL agent
        try:
            from core.rl_agent import global_rl_agent, build_market_context
            self.global_rl_agent = global_rl_agent
            self.build_market_context = build_market_context
            self.rl_agent_available = True
        except ImportError:
            logging.warning("⚠️ RL Agent not available")
            self.rl_agent_available = False
        
        # Try to import position manager
        try:
            from core.smart_position_manager import global_smart_position_manager
            self.position_manager = global_smart_position_manager
            self.position_manager_available = True
        except ImportError:
            logging.warning("⚠️ Position Manager not available")
            self.position_manager_available = False

    async def process_prediction_results(self, prediction_results, all_symbol_data):
        """
        Process ML prediction results into trading signals
        
        Args:
            prediction_results: Results from ML predictions
            all_symbol_data: Market data for all symbols
            
        Returns:
            list: List of processed signals ready for execution
        """
        all_signals = []
        
        logging.info(colored("🔧 Processing prediction results for execution...", "yellow"))
        
        for symbol, (ensemble_value, final_signal, tf_predictions) in prediction_results.items():
            try:
                symbol_short = symbol.replace('/USDT:USDT', '')
                logging.debug(f"🔍 Processing {symbol_short}: ensemble={ensemble_value}, signal={final_signal}")
                
                if ensemble_value is None or final_signal is None or final_signal == 2:
                    logging.debug(f"⏭️ Skipping {symbol_short}: ensemble={ensemble_value}, signal={final_signal}")
                    continue

                # Store signal with confidence details
                confidence_explanation = calculate_ensemble_confidence(tf_predictions, ensemble_value)
                
                # Get current price for ranking
                try:
                    # Use exchange to get current price - this would need to be passed in
                    # For now, use 0 as placeholder
                    current_price = 0
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
                
                # Apply RL filter
                if self.rl_agent_available:
                    rl_approved = await self._apply_rl_filter(signal_data, all_symbol_data[symbol])
                    if rl_approved:
                        all_signals.append(signal_data)
                        logging.info(f"✅ Added to execution queue: {symbol_short} {signal_data['signal_name']} (XGB:{ensemble_value:.1%}, RL approved)")
                    else:
                        logging.info(f"❌ RL Rejected execution: {symbol_short} {signal_data['signal_name']}")
                else:
                    # No RL available, accept all XGBoost signals
                    all_signals.append(signal_data)
                    logging.info(f"➕ Added (no RL): {symbol_short} {signal_data['signal_name']} (XGB:{ensemble_value:.1%})")
                
            except Exception as e:
                logging.error(f"Error processing signal for {symbol}: {e}")
                continue
        
        # Sort by ML confidence (highest first)
        all_signals.sort(key=lambda x: x.get('confidence', 0.0), reverse=True)
        
        logging.info(colored(f"🔢 Final signals ready for execution: {len(all_signals)}", "cyan"))
        for i, sig in enumerate(all_signals, 1):
            logging.debug(f"   {i}. {sig['symbol'].replace('/USDT:USDT', '')} {sig['signal_name']} - {sig['confidence']:.1%}")
        
        return all_signals

    async def _apply_rl_filter(self, signal_data, dataframes):
        """
        Apply RL filtering to a signal
        
        Args:
            signal_data: Signal data to filter
            dataframes: Market dataframes for the symbol
            
        Returns:
            bool: True if signal is approved by RL agent
        """
        try:
            # Build market context for RL decision
            market_context = self.build_market_context(signal_data['symbol'], dataframes)
            portfolio_state = self.position_manager.get_session_summary() if self.position_manager_available else {}
            
            # Get RL decision
            should_execute, rl_confidence, rl_details = self.global_rl_agent.should_execute_signal(
                signal_data, market_context, portfolio_state
            )
            
            # Store RL details in signal data for analysis
            signal_data['rl_approved'] = should_execute
            signal_data['rl_confidence'] = rl_confidence
            signal_data['rl_details'] = rl_details
            
            symbol_short = signal_data['symbol'].replace('/USDT:USDT', '')
            logging.debug(f"🤖 RL Decision for {symbol_short}: should_execute={should_execute}, confidence={rl_confidence:.1%}")
            
            return should_execute
            
        except Exception as rl_error:
            logging.warning(f"RL filter error for {signal_data['symbol']}: {rl_error}")
            # Fallback: accept signal without RL filtering
            signal_data['rl_approved'] = True
            signal_data['rl_confidence'] = 0.6
            signal_data['rl_details'] = {
                'primary_reason': f'RL Error: {str(rl_error)[:50]}...',
                'factors': {},
                'final_verdict': 'ERROR_FALLBACK'
            }
            return True

    def display_complete_analysis(self, prediction_results, all_symbol_data):
        """
        Display complete analysis for all symbols showing decision pipeline
        
        Args:
            prediction_results: ML prediction results
            all_symbol_data: Market data for symbols
        """
        print(colored(f"\n🔍 COMPLETE ANALYSIS FOR ALL SYMBOLS ({len(prediction_results)}/10)", "cyan", attrs=['bold']))
        print(colored("=" * 80, "cyan"))
        
        # Process ALL prediction results and show decision analysis
        for symbol, (ensemble_value, final_signal, tf_predictions) in prediction_results.items():
            try:
                # Create signal data for analysis display
                signal_name = 'BUY' if final_signal == 1 else 'SELL' if final_signal == 0 else 'NEUTRAL'
                signal_data = {
                    'symbol': symbol,
                    'signal': final_signal,
                    'signal_name': signal_name,
                    'confidence': ensemble_value if ensemble_value is not None else 0.0,
                    'tf_predictions': tf_predictions,
                    'price': 0
                }
                
                # Handle NEUTRAL signals (skip RL analysis)
                if final_signal is None or final_signal == 2 or ensemble_value is None:
                    signal_data['rl_approved'] = False
                    signal_data['rl_confidence'] = 0.0
                    signal_data['rl_details'] = {
                        'primary_reason': 'NEUTRAL signal - no RL analysis performed',
                        'factors': {},
                        'final_verdict': 'SKIPPED_NEUTRAL'
                    }
                    signal_data['signal_name'] = 'NEUTRAL'
                
                # Get RL decision for BUY/SELL signals only
                elif self.rl_agent_available and final_signal in [0, 1]:
                    try:
                        market_context = self.build_market_context(symbol, all_symbol_data[symbol])
                        portfolio_state = self.position_manager.get_session_summary() if self.position_manager_available else {}
                        
                        # Get RL decision with detailed analysis
                        should_execute, rl_confidence, rl_details = self.global_rl_agent.should_execute_signal(
                            signal_data, market_context, portfolio_state
                        )
                        
                        signal_data['rl_approved'] = should_execute
                        signal_data['rl_confidence'] = rl_confidence
                        signal_data['rl_details'] = rl_details
                        
                    except Exception as rl_error:
                        logging.warning(f"RL analysis error for {symbol}: {rl_error}")
                        # Fallback: no RL data
                        signal_data['rl_approved'] = False
                        signal_data['rl_confidence'] = 0.0
                        signal_data['rl_details'] = {
                            'primary_reason': f'RL Error: {str(rl_error)[:50]}...',
                            'factors': {},
                            'final_verdict': 'ERROR_FALLBACK'
                        }
                else:
                    # RL not available but signal is BUY/SELL
                    signal_data['rl_approved'] = True  # Default approve when RL unavailable
                    signal_data['rl_confidence'] = 0.6
                    signal_data['rl_details'] = {
                        'primary_reason': 'RL system not available',
                        'factors': {},
                        'final_verdict': 'RL_UNAVAILABLE'
                    }
                
                # Show decision analysis for this symbol
                display_symbol_decision_analysis(
                    symbol, 
                    signal_data,
                    rl_available=self.rl_agent_available,
                    risk_manager_available=True
                )
                
            except Exception as e:
                logging.error(f"Error in decision analysis for {symbol}: {e}")
                continue
        
        print(colored("=" * 80, "cyan"))

    async def get_current_price(self, exchange, symbol):
        """
        Get current price for a symbol
        
        Args:
            exchange: Exchange instance
            symbol: Symbol to get price for
            
        Returns:
            float: Current price or 0 if error
        """
        try:
            ticker = await exchange.fetch_ticker(symbol)
            return ticker.get('last', 0)
        except Exception as e:
            logging.warning(f"Could not get price for {symbol}: {e}")
            return 0

    def is_rl_available(self):
        """Check if RL agent is available"""
        return self.rl_agent_available

    def is_position_manager_available(self):
        """Check if position manager is available"""
        return self.position_manager_available


# Global instance for easy access
global_signal_processor = SignalProcessor()
