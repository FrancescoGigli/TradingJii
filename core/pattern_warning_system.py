#!/usr/bin/env python3
"""
⚠️ PATTERN WARNING SYSTEM

Sistema preventivo che avvisa PRIMA di aprire un trade se ci sono pattern pericolosi noti
basati sulla storia recente dei fallimenti.

FEATURES:
- Check similarità con trade falliti recenti
- Check alta volatilità con storia fallimenti
- Check segnali deboli con pattern negativi
- Raccomandazioni actionable per ogni warning
"""

import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from termcolor import colored


class PatternWarningSystem:
    """
    Sistema di warning preventivo per evitare di ripetere errori noti
    """
    
    def __init__(self, online_learning_manager):
        self.learning_manager = online_learning_manager
        
        # Threshold per warnings
        self.min_failures_for_warning = 3  # Minimo 3 fallimenti per pattern warning
        self.similarity_threshold = 0.7  # 70% similarità per warning
        self.high_volatility_threshold = 0.05  # 5% volatilità = alta
        self.weak_signal_threshold = 0.70  # Sotto 70% confidence = debole
        
        # Lookback windows
        self.recent_window_hours = 72  # Ultimi 3 giorni
        self.pattern_memory_trades = 20  # Ultimi 20 trade
        
    
    def check_before_opening(self, symbol: str, signal_data: Dict, market_context: Dict) -> Tuple[List[str], bool]:
        """
        CHECK PREVENTIVO prima di aprire trade
        
        Args:
            symbol: Symbol da tradare
            signal_data: Dati del segnale
            market_context: Contesto di mercato
            
        Returns:
            Tuple[List[str], bool]: (lista warnings, should_skip_trade)
        """
        warnings = []
        critical_warnings = 0
        
        try:
            # Check 1: Simile a trade fallito recente?
            similar_failures = self._check_similar_failures(symbol, signal_data, market_context)
            if similar_failures:
                count = len(similar_failures)
                warnings.append(f"⚠️ {count} trade simili falliti recentemente su {symbol}")
                if count >= 3:
                    critical_warnings += 1
            
            # Check 2: Alta volatilità con storia negativa?
            volatility = market_context.get('volatility', 0.0)
            if volatility > self.high_volatility_threshold:
                high_vol_failures = self._check_high_volatility_failures()
                if len(high_vol_failures) >= self.min_failures_for_warning:
                    warnings.append(f"⚠️ Alta volatilità ({volatility:.1%}) - {len(high_vol_failures)} fallimenti recenti in queste condizioni")
                    if len(high_vol_failures) >= 5:
                        critical_warnings += 1
            
            # Check 3: Segnale debole con pattern negativo?
            confidence = signal_data.get('confidence', 0.0)
            if confidence < self.weak_signal_threshold:
                weak_signal_failures = self._check_weak_signal_failures()
                if len(weak_signal_failures) >= self.min_failures_for_warning:
                    warnings.append(f"⚠️ Segnale debole ({confidence:.1%}) - {len(weak_signal_failures)} fallimenti recenti con confidence < 70%")
                    if len(weak_signal_failures) >= 5:
                        critical_warnings += 1
            
            # Check 4: Symbol con bad track record?
            symbol_failures = self._check_symbol_performance(symbol)
            if symbol_failures['total'] >= 3 and symbol_failures['win_rate'] < 30:
                warnings.append(f"⚠️ {symbol} ha win rate {symbol_failures['win_rate']:.0f}% (molto basso)")
                critical_warnings += 1
            
            # Check 5: Timeframe consensus debole?
            tf_predictions = signal_data.get('tf_predictions', {})
            if tf_predictions:
                consensus_strength = self._check_timeframe_consensus(tf_predictions)
                if consensus_strength < 0.66:  # Meno di 2/3 accordo
                    warnings.append(f"⚠️ Consensus timeframe debole ({consensus_strength:.0%}) - solo {int(consensus_strength * len(tf_predictions))}/{len(tf_predictions)} concordano")
            
            # Decide se skippare il trade
            should_skip = critical_warnings >= 2  # 2+ critical warnings = skip consigliato
            
            return warnings, should_skip
            
        except Exception as e:
            logging.error(f"Error in pattern warning check: {e}")
            return [], False
    
    def _check_similar_failures(self, symbol: str, signal_data: Dict, market_context: Dict) -> List[Dict]:
        """
        Trova trade falliti simili nelle ultime 72h
        
        Similarità basata su:
        - Stesso symbol
        - Direction simile
        - Confidence range simile
        - Market conditions simili
        """
        try:
            if not self.learning_manager or not hasattr(self.learning_manager, 'completed_trades'):
                return []
            
            completed_trades = self.learning_manager.completed_trades
            if not completed_trades:
                return []
            
            # Filtra solo fallimenti recenti
            recent_cutoff = datetime.now() - timedelta(hours=self.recent_window_hours)
            recent_failures = [
                trade for trade in completed_trades[-self.pattern_memory_trades:]
                if not trade.get('success', False) and 
                   datetime.fromisoformat(trade.get('close_timestamp', '2020-01-01')) > recent_cutoff
            ]
            
            if not recent_failures:
                return []
            
            # Cerca similarità
            similar_failures = []
            target_direction = signal_data.get('signal_name', '')
            target_confidence = signal_data.get('confidence', 0.0)
            target_volatility = market_context.get('volatility', 0.0)
            
            for failure in recent_failures:
                similarity_score = 0.0
                factors = 0
                
                # Check 1: Stesso symbol (peso 40%)
                if failure.get('symbol') == symbol:
                    similarity_score += 0.4
                factors += 1
                
                # Check 2: Direction simile (peso 20%)
                failure_direction = failure.get('signal_data', {}).get('signal_name', '')
                if failure_direction == target_direction:
                    similarity_score += 0.2
                factors += 1
                
                # Check 3: Confidence range simile (peso 20%)
                failure_confidence = failure.get('signal_data', {}).get('confidence', 0.0)
                confidence_diff = abs(target_confidence - failure_confidence)
                if confidence_diff < 0.10:  # Entro 10%
                    similarity_score += 0.2
                factors += 1
                
                # Check 4: Volatilità simile (peso 20%)
                failure_volatility = failure.get('market_context', {}).get('volatility', 0.0)
                volatility_diff = abs(target_volatility - failure_volatility)
                if volatility_diff < 0.02:  # Entro 2%
                    similarity_score += 0.2
                factors += 1
                
                # Normalizza score
                if factors > 0:
                    similarity_score = similarity_score / factors * 4  # Riporta a scala 0-1
                
                if similarity_score >= self.similarity_threshold:
                    similar_failures.append({
                        'trade': failure,
                        'similarity': similarity_score
                    })
            
            return similar_failures
            
        except Exception as e:
            logging.error(f"Error checking similar failures: {e}")
            return []
    
    def _check_high_volatility_failures(self) -> List[Dict]:
        """
        Trova fallimenti recenti durante alta volatilità
        """
        try:
            if not self.learning_manager or not hasattr(self.learning_manager, 'completed_trades'):
                return []
            
            completed_trades = self.learning_manager.completed_trades
            if not completed_trades:
                return []
            
            # Ultimi N trade
            recent_trades = completed_trades[-self.pattern_memory_trades:]
            
            # Filtra fallimenti con alta volatilità
            high_vol_failures = [
                trade for trade in recent_trades
                if not trade.get('success', False) and
                   trade.get('market_context', {}).get('volatility', 0.0) > self.high_volatility_threshold
            ]
            
            return high_vol_failures
            
        except Exception as e:
            logging.error(f"Error checking high volatility failures: {e}")
            return []
    
    def _check_weak_signal_failures(self) -> List[Dict]:
        """
        Trova fallimenti recenti con segnali deboli
        """
        try:
            if not self.learning_manager or not hasattr(self.learning_manager, 'completed_trades'):
                return []
            
            completed_trades = self.learning_manager.completed_trades
            if not completed_trades:
                return []
            
            # Ultimi N trade
            recent_trades = completed_trades[-self.pattern_memory_trades:]
            
            # Filtra fallimenti con confidence bassa
            weak_signal_failures = [
                trade for trade in recent_trades
                if not trade.get('success', False) and
                   trade.get('signal_data', {}).get('confidence', 1.0) < self.weak_signal_threshold
            ]
            
            return weak_signal_failures
            
        except Exception as e:
            logging.error(f"Error checking weak signal failures: {e}")
            return []
    
    def _check_symbol_performance(self, symbol: str) -> Dict:
        """
        Analizza performance storica di uno specifico symbol
        """
        try:
            if not self.learning_manager or not hasattr(self.learning_manager, 'completed_trades'):
                return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0}
            
            completed_trades = self.learning_manager.completed_trades
            if not completed_trades:
                return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0}
            
            # Filtra per symbol
            symbol_trades = [
                trade for trade in completed_trades
                if trade.get('symbol') == symbol
            ]
            
            if not symbol_trades:
                return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0}
            
            wins = sum(1 for trade in symbol_trades if trade.get('success', False))
            losses = len(symbol_trades) - wins
            win_rate = (wins / len(symbol_trades)) * 100 if len(symbol_trades) > 0 else 0
            
            return {
                'total': len(symbol_trades),
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate
            }
            
        except Exception as e:
            logging.error(f"Error checking symbol performance: {e}")
            return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0}
    
    def _check_timeframe_consensus(self, tf_predictions: Dict) -> float:
        """
        Calcola strength del consensus tra timeframes
        
        Returns:
            float: Percentuale di agreement (0.0 - 1.0)
        """
        try:
            if not tf_predictions:
                return 1.0  # No data = assume OK
            
            # Count predictions
            prediction_counts = {}
            for tf, pred in tf_predictions.items():
                signal_name = ['SELL', 'BUY', 'NEUTRAL'][pred] if isinstance(pred, int) else str(pred)
                prediction_counts[signal_name] = prediction_counts.get(signal_name, 0) + 1
            
            # Find majority
            if not prediction_counts:
                return 1.0
            
            max_count = max(prediction_counts.values())
            total_count = len(tf_predictions)
            
            consensus_strength = max_count / total_count if total_count > 0 else 0.0
            
            return consensus_strength
            
        except Exception as e:
            logging.error(f"Error checking timeframe consensus: {e}")
            return 1.0  # Error = assume OK
    
    def display_warnings(self, symbol: str, warnings: List[str], should_skip: bool):
        """
        Mostra i warnings nel terminale con colori appropriati
        """
        try:
            symbol_short = symbol.replace('/USDT:USDT', '')
            
            if not warnings:
                return  # Nessun warning da mostrare
            
            print(colored("=" * 80, "yellow"))
            print(colored(f"⚠️  PATTERN WARNINGS per {symbol_short}", "yellow", attrs=["bold"]))
            print(colored("=" * 80, "yellow"))
            
            for i, warning in enumerate(warnings, 1):
                print(colored(f"  {i}. {warning}", "yellow"))
            
            if should_skip:
                print(colored("\n🛑 RACCOMANDAZIONE: SKIP questo trade (troppi warning critici)", "red", attrs=["bold"]))
            else:
                print(colored("\n💡 RACCOMANDAZIONE: Procedi con cautela", "yellow"))
            
            print(colored("=" * 80, "yellow"))
            
        except Exception as e:
            logging.error(f"Error displaying warnings: {e}")
    
    def get_recommendations(self, warnings: List[str]) -> List[str]:
        """
        Genera raccomandazioni basate sui warnings
        """
        recommendations = []
        
        try:
            for warning in warnings:
                if "simili falliti" in warning.lower():
                    recommendations.append("🔍 Rivedi decisione - pattern simile ha fallito")
                
                if "alta volatilità" in warning.lower():
                    recommendations.append("🛡️ Aumenta stop loss per protezione extra")
                
                if "segnale debole" in warning.lower():
                    recommendations.append("📊 Aspetta segnale più forte (>70% confidence)")
                
                if "win rate" in warning.lower() and "basso" in warning.lower():
                    recommendations.append(f"⚠️ Considera di evitare questo symbol")
                
                if "consensus" in warning.lower() and "debole" in warning.lower():
                    recommendations.append("🎯 Aspetta maggior accordo tra timeframes (>66%)")
            
            return recommendations
            
        except Exception as e:
            logging.error(f"Error generating recommendations: {e}")
            return []


# Global instance (will be initialized with online learning manager)
global_pattern_warning_system = None


def initialize_pattern_warning_system(online_learning_manager):
    """Initialize the global pattern warning system"""
    global global_pattern_warning_system
    if global_pattern_warning_system is None:
        global_pattern_warning_system = PatternWarningSystem(online_learning_manager)
        logging.info(colored("⚠️ Pattern Warning System initialized", "green"))
    return global_pattern_warning_system
