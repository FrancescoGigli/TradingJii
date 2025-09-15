#!/usr/bin/env python3
"""
🔍 DECISION EXPLAINER SYSTEM

Sistema avanzato per spiegare nel dettaglio le decisioni di trading:
- Breakdown completo delle decisioni Ensemble + RL
- Analisi numerica di tutti i fattori
- Grafici ASCII e spiegazioni chiare
- Confronti con pattern storici
"""

import logging
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from termcolor import colored


class DecisionExplainer:
    """
    Sistema per spiegare dettagliatamente le decisioni di trading
    """
    
    def __init__(self):
        self.decision_history = []
        self.max_history = 1000  # Keep last 1000 decisions for pattern analysis
        
        # Thresholds for various factors (configurable)
        self.thresholds = {
            'xgb_confidence_min': 0.65,
            'rl_confidence_min': 0.5,
            'volatility_max': 0.05,
            'trend_strength_min': 20.0,
            'balance_min_pct': 0.1,
            'rsi_oversold': 30.0,
            'rsi_overbought': 70.0,
            'volume_surge_min': 1.2
        }
        
    def explain_ensemble_decision(self, signal_data: Dict, detailed: bool = True) -> str:
        """
        Spiega nel dettaglio come l'ensemble XGBoost ha preso la decisione
        
        Args:
            signal_data: Dati del segnale con predizioni per timeframe
            detailed: Se mostrare analisi dettagliata
            
        Returns:
            str: Spiegazione formattata della decisione ensemble
        """
        try:
            symbol = signal_data.get('symbol', '').replace('/USDT:USDT', '')
            tf_predictions = signal_data.get('tf_predictions', {})
            confidence = signal_data.get('confidence', 0.0)
            signal_name = signal_data.get('signal_name', 'UNKNOWN')
            
            explanation = []
            explanation.append(colored(f"\n🧠 ENSEMBLE XGBoost ANALYSIS - {symbol}", "cyan", attrs=['bold']))
            explanation.append(colored("=" * 80, "cyan"))
            
            if not tf_predictions:
                explanation.append(colored("❌ No timeframe predictions available", "red"))
                return "\n".join(explanation)
            
            # 1. Timeframe Voting Analysis
            explanation.append(colored("📊 TIMEFRAME VOTING BREAKDOWN:", "yellow", attrs=['bold']))
            
            signal_names = {0: 'SELL', 1: 'BUY', 2: 'NEUTRAL'}
            vote_counts = {'BUY': 0, 'SELL': 0, 'NEUTRAL': 0}
            
            for tf in ['15m', '30m', '1h']:  # Ordine logico
                if tf in tf_predictions:
                    pred = tf_predictions[tf]
                    signal_str = signal_names.get(pred, 'UNKNOWN')
                    vote_counts[signal_str] += 1
                    
                    # Color coding per ogni voto
                    if signal_str == 'BUY':
                        color = 'green'
                        emoji = '📈'
                    elif signal_str == 'SELL':
                        color = 'red'
                        emoji = '📉'
                    else:
                        color = 'yellow'
                        emoji = '➡️'
                    
                    explanation.append(f"  {emoji} {tf.upper():<4}: {colored(signal_str, color, attrs=['bold'])}")
            
            # 2. Vote Counting and Consensus Analysis
            explanation.append(colored("\n🗳️ VOTING RESULTS:", "yellow", attrs=['bold']))
            total_votes = sum(vote_counts.values())
            
            for signal_type, count in vote_counts.items():
                if count > 0:
                    percentage = (count / total_votes) * 100
                    bar_length = int(percentage / 5)  # Scale for ASCII bar
                    bar = "█" * bar_length + "░" * (20 - bar_length)
                    
                    color = 'green' if signal_type == 'BUY' else 'red' if signal_type == 'SELL' else 'yellow'
                    explanation.append(f"  {signal_type:<8}: {count}/{total_votes} votes {colored(bar, color)} {percentage:.1f}%")
            
            # 3. Final Decision Logic
            explanation.append(colored("\n🎯 DECISION LOGIC:", "yellow", attrs=['bold']))
            winning_signal = max(vote_counts.items(), key=lambda x: x[1])
            winning_type, winning_count = winning_signal
            
            if winning_count > total_votes / 2:  # Majority rule
                consensus_strength = "STRONG" if winning_count == total_votes else "MAJORITY"
                color = 'green'
            elif winning_count == total_votes / 2:
                consensus_strength = "WEAK"
                color = 'yellow'
            else:
                consensus_strength = "NO CONSENSUS"
                color = 'red'
            
            explanation.append(f"  📋 Consensus: {colored(consensus_strength, color, attrs=['bold'])}")
            explanation.append(f"  🏆 Winner: {colored(winning_type, color, attrs=['bold'])} ({winning_count}/{total_votes} votes)")
            explanation.append(f"  📈 Final Confidence: {colored(f'{confidence:.1%}', 'green' if confidence >= 0.65 else 'yellow', attrs=['bold'])}")
            
            # 4. Confidence Calculation Explanation
            if detailed:
                explanation.append(colored("\n🔢 CONFIDENCE CALCULATION:", "yellow", attrs=['bold']))
                explanation.append(f"  Formula: (Winning Votes / Total Votes) × Agreement Modifier")
                explanation.append(f"  Base Score: {winning_count}/{total_votes} = {(winning_count/total_votes):.1%}")
                
                # Explain any modifiers (simplified for now)
                if consensus_strength == "STRONG":
                    explanation.append(f"  🚀 Strong Consensus Bonus: +5%")
                elif consensus_strength == "WEAK":
                    explanation.append(f"  ⚠️ Weak Consensus Penalty: -10%")
                
                explanation.append(f"  🎯 Final Result: {colored(f'{confidence:.1%}', 'cyan', attrs=['bold'])}")
            
            # 5. Decision Recommendation
            explanation.append(colored("\n✨ ENSEMBLE RECOMMENDATION:", "magenta", attrs=['bold']))
            if confidence >= self.thresholds['xgb_confidence_min']:
                explanation.append(f"  ✅ {colored('APPROVED', 'green', attrs=['bold'])} - Confidence {confidence:.1%} ≥ {self.thresholds['xgb_confidence_min']:.1%} threshold")
                explanation.append(f"  🎯 Signal: {colored(signal_name, 'green', attrs=['bold'])}")
            else:
                explanation.append(f"  ❌ {colored('REJECTED', 'red', attrs=['bold'])} - Confidence {confidence:.1%} < {self.thresholds['xgb_confidence_min']:.1%} threshold")
                explanation.append(f"  🚫 Signal too weak for execution")
            
            return "\n".join(explanation)
            
        except Exception as e:
            logging.error(f"Error explaining ensemble decision: {e}")
            return colored(f"❌ Error explaining ensemble decision: {e}", "red")
    
    def explain_rl_decision(self, signal_data: Dict, market_context: Dict, portfolio_state: Dict, rl_details: Dict, detailed: bool = True) -> str:
        """
        Spiega nel dettaglio la decisione del sistema RL
        """
        try:
            symbol = signal_data.get('symbol', '').replace('/USDT:USDT', '')
            rl_confidence = signal_data.get('rl_confidence', 0.0)
            rl_approved = signal_data.get('rl_approved', False)
            
            explanation = []
            explanation.append(colored(f"\n🤖 REINFORCEMENT LEARNING ANALYSIS - {symbol}", "magenta", attrs=['bold']))
            explanation.append(colored("=" * 80, "magenta"))
            
            # 1. RL Input State Analysis
            explanation.append(colored("📊 INPUT STATE VECTOR (12 FEATURES):", "yellow", attrs=['bold']))
            
            # XGBoost Features
            explanation.append(colored("  🧠 XGBoost Features:", "cyan"))
            tf_preds = signal_data.get('tf_predictions', {})
            xgb_confidence = signal_data.get('confidence', 0.0)
            
            explanation.append(f"    📈 Ensemble Confidence: {colored(f'{xgb_confidence:.1%}', self._get_confidence_color(xgb_confidence))}")
            for tf in ['15m', '30m', '1h']:
                if tf in tf_preds:
                    pred_val = tf_preds[tf] / 2.0  # Normalized to 0-1
                    signal_name = ['SELL', 'BUY', 'NEUTRAL'][tf_preds[tf]]
                    color = self._get_signal_color(signal_name)
                    explanation.append(f"    📊 {tf.upper()}: {colored(f'{signal_name} ({pred_val:.2f})', color)}")
            
            # Market Features
            explanation.append(colored("  🌍 Market Context Features:", "cyan"))
            volatility = market_context.get('volatility', 0.02)
            volume_surge = market_context.get('volume_surge', 1.0)
            trend_strength = market_context.get('trend_strength', 25.0)
            rsi_position = market_context.get('rsi_position', 50.0)
            
            explanation.append(f"    📉 Volatility: {colored(f'{volatility*100:.2f}%', self._get_volatility_color(volatility))}")
            explanation.append(f"    📊 Volume Surge: {colored(f'{volume_surge:.2f}x', self._get_volume_color(volume_surge))}")
            explanation.append(f"    📈 Trend Strength (ADX): {colored(f'{trend_strength:.1f}', self._get_trend_color(trend_strength))}")
            explanation.append(f"    ⚡ RSI Position: {colored(f'{rsi_position:.1f}', self._get_rsi_color(rsi_position))}")
            
            # Portfolio Features
            explanation.append(colored("  💼 Portfolio State Features:", "cyan"))
            available_balance = portfolio_state.get('available_balance', 1000)
            wallet_balance = portfolio_state.get('wallet_balance', 1000)
            balance_pct = available_balance / wallet_balance if wallet_balance > 0 else 1.0
            active_positions = portfolio_state.get('active_positions', 0)
            realized_pnl = portfolio_state.get('total_realized_pnl', 0.0)
            unrealized_pnl_pct = portfolio_state.get('unrealized_pnl_pct', 0.0)
            
            explanation.append(f"    💰 Available Balance: {colored(f'{balance_pct:.1%}', self._get_balance_color(balance_pct))}")
            explanation.append(f"    📊 Active Positions: {colored(f'{active_positions}', self._get_position_color(active_positions))}")
            explanation.append(f"    💵 Realized PnL: {colored(f'{realized_pnl:+.2f} USDT', self._get_pnl_color(realized_pnl))}")
            explanation.append(f"    📈 Unrealized PnL: {colored(f'{unrealized_pnl_pct:+.1f}%', self._get_pnl_color(unrealized_pnl_pct))}")
            
            # 2. RL Neural Network Processing
            explanation.append(colored("\n🧠 NEURAL NETWORK PROCESSING:", "yellow", attrs=['bold']))
            explanation.append(f"  🔗 Architecture: 12 inputs → 32 hidden → 16 hidden → 1 output (sigmoid)")
            explanation.append(f"  🎯 Output Probability: {colored(f'{rl_confidence:.1%}', self._get_confidence_color(rl_confidence))}")
            rl_threshold_pct = f'{self.thresholds["rl_confidence_min"]:.1%}'
            explanation.append(f"  🚧 Execution Threshold: {colored(rl_threshold_pct, 'cyan')}")
            
            # 3. Factor Analysis
            if detailed and 'factors' in rl_details:
                explanation.append(colored("\n🔍 DETAILED FACTOR ANALYSIS:", "yellow", attrs=['bold']))
                factors = rl_details['factors']
                
                for factor_name, factor_info in factors.items():
                    factor_display = factor_name.replace('_', ' ').title()
                    value = factor_info.get('value', 'N/A')
                    threshold = factor_info.get('threshold', 'N/A')
                    status = factor_info.get('status', 'OK')
                    
                    # Status color coding
                    status_color = {
                        'OK': 'green',
                        'STRONG': 'green',
                        'HIGH': 'green',
                        'WEAK': 'yellow',
                        'LOW': 'yellow',
                        'TOO_HIGH': 'red',
                        'TOO_LOW': 'red',
                        'ERROR': 'red'
                    }.get(status, 'white')
                    
                    # Create visual indicator
                    if status in ['OK', 'STRONG', 'HIGH']:
                        indicator = "✅"
                    elif status in ['WEAK', 'LOW']:
                        indicator = "⚠️"
                    else:
                        indicator = "❌"
                    
                    explanation.append(f"    {indicator} {factor_display}: {colored(value, status_color)} (limit: {threshold})")
            
            # 4. Decision Reasoning
            explanation.append(colored("\n🎯 DECISION REASONING:", "yellow", attrs=['bold']))
            
            primary_reason = rl_details.get('primary_reason', 'Unknown')
            final_verdict = rl_details.get('final_verdict', 'UNKNOWN')
            
            if rl_approved:
                explanation.append(f"  ✅ {colored('APPROVED', 'green', attrs=['bold'])} - All critical factors satisfied")
                explanation.append(f"  🚀 Primary Reason: {colored(primary_reason, 'green')}")
                
                # Show approval factors
                approvals = rl_details.get('approvals', [])
                for i, approval in enumerate(approvals[:3], 1):  # Show top 3
                    explanation.append(f"    {i}. ✅ {approval}")
                    
            else:
                explanation.append(f"  ❌ {colored('REJECTED', 'red', attrs=['bold'])} - Risk factors detected")
                explanation.append(f"  🚫 Primary Reason: {colored(primary_reason, 'red')}")
                
                # Show rejection factors
                issues = rl_details.get('issues', [])
                for i, issue in enumerate(issues[:3], 1):  # Show top 3
                    explanation.append(f"    {i}. ❌ {issue}")
            
            # 5. Historical Context (if available)
            if detailed and len(self.decision_history) > 10:
                explanation.append(colored("\n📊 HISTORICAL CONTEXT:", "yellow", attrs=['bold']))
                recent_decisions = self.decision_history[-50:]  # Last 50 decisions
                similar_confidence = [d for d in recent_decisions if abs(d.get('rl_confidence', 0) - rl_confidence) < 0.1]
                
                if similar_confidence:
                    avg_success = sum(1 for d in similar_confidence if d.get('success', False)) / len(similar_confidence)
                    explanation.append(f"  📈 Similar Confidence Success Rate: {colored(f'{avg_success:.1%}', self._get_confidence_color(avg_success))}")
                    explanation.append(f"  📊 Based on {len(similar_confidence)} similar decisions")
            
            return "\n".join(explanation)
            
        except Exception as e:
            logging.error(f"Error explaining RL decision: {e}")
            return colored(f"❌ Error explaining RL decision: {e}", "red")
    
    def explain_complete_decision(self, signal_data: Dict, market_context: Dict, portfolio_state: Dict, detailed: bool = True) -> None:
        """
        Spiega l'intera pipeline di decisione: Ensemble → RL → Final Decision
        """
        try:
            symbol = signal_data.get('symbol', '').replace('/USDT:USDT', '')
            
            print(colored(f"\n🎯 COMPLETE DECISION PIPELINE - {symbol}", "white", attrs=['bold']))
            print(colored("=" * 100, "white"))
            
            # Phase 1: Ensemble Explanation
            ensemble_explanation = self.explain_ensemble_decision(signal_data, detailed)
            print(ensemble_explanation)
            
            # Phase 2: RL Explanation (if available)
            rl_details = signal_data.get('rl_details', {})
            if rl_details and signal_data.get('rl_approved') is not None:
                rl_explanation = self.explain_rl_decision(signal_data, market_context, portfolio_state, rl_details, detailed)
                print(rl_explanation)
            else:
                print(colored("\n🤖 RL SYSTEM: Not available or not applicable", "yellow"))
            
            # Phase 3: Final Decision Summary
            print(colored(f"\n🏆 FINAL DECISION SUMMARY - {symbol}", "white", attrs=['bold']))
            print(colored("=" * 60, "white"))
            
            final_decision = signal_data.get('signal_name', 'SKIP')
            xgb_confidence = signal_data.get('confidence', 0.0)
            rl_confidence = signal_data.get('rl_confidence', 0.0)
            rl_approved = signal_data.get('rl_approved', False)
            
            # Decision path visualization
            print(f"  📊 XGBoost: {colored(f'{xgb_confidence:.1%}', self._get_confidence_color(xgb_confidence))} → {'✅' if xgb_confidence >= self.thresholds['xgb_confidence_min'] else '❌'}")
            
            if rl_details:
                print(f"  🤖 RL Filter: {colored(f'{rl_confidence:.1%}', self._get_confidence_color(rl_confidence))} → {'✅' if rl_approved else '❌'}")
                pipeline_result = "EXECUTE" if (xgb_confidence >= self.thresholds['xgb_confidence_min'] and rl_approved) else "SKIP"
            else:
                print(f"  🤖 RL Filter: {colored('BYPASSED', 'yellow')}")
                pipeline_result = "EXECUTE" if xgb_confidence >= self.thresholds['xgb_confidence_min'] else "SKIP"
            
            # Final result
            result_color = 'green' if pipeline_result == "EXECUTE" else 'red'
            result_emoji = '🚀' if pipeline_result == "EXECUTE" else '🛑'
            
            print(f"  {result_emoji} FINAL: {colored(pipeline_result, result_color, attrs=['bold'])}")
            
            if pipeline_result == "EXECUTE":
                print(f"  📈 Signal: {colored(final_decision, 'green', attrs=['bold'])}")
                print(f"  🎯 Estimated Success Probability: {colored(f'{(xgb_confidence * rl_confidence if rl_approved else xgb_confidence):.1%}', 'green')}")
            else:
                print(f"  ⏭️ Action: {colored('SKIP SIGNAL', 'red')}")
                rejection_reason = rl_details.get('primary_reason', 'Low XGBoost confidence') if rl_details else 'Low XGBoost confidence'
                print(f"  🚫 Reason: {colored(rejection_reason, 'red')}")
            
            print(colored("=" * 60, "white"))
            
            # Store decision for historical analysis
            self._store_decision(signal_data, market_context, portfolio_state)
            
        except Exception as e:
            logging.error(f"Error in complete decision explanation: {e}")
            print(colored(f"❌ Error explaining decision: {e}", "red"))
    
    def _store_decision(self, signal_data: Dict, market_context: Dict, portfolio_state: Dict):
        """Store decision in history for pattern analysis"""
        try:
            decision_record = {
                'timestamp': datetime.now().isoformat(),
                'symbol': signal_data.get('symbol', ''),
                'signal_name': signal_data.get('signal_name', ''),
                'xgb_confidence': signal_data.get('confidence', 0.0),
                'rl_confidence': signal_data.get('rl_confidence', 0.0),
                'rl_approved': signal_data.get('rl_approved', False),
                'market_volatility': market_context.get('volatility', 0.0),
                'trend_strength': market_context.get('trend_strength', 0.0),
                'portfolio_balance_pct': portfolio_state.get('available_balance', 0) / max(portfolio_state.get('wallet_balance', 1), 1),
                'executed': signal_data.get('signal_name', 'SKIP') != 'SKIP',
                'success': None  # Will be updated when trade closes
            }
            
            self.decision_history.append(decision_record)
            
            # Maintain history size limit
            if len(self.decision_history) > self.max_history:
                self.decision_history = self.decision_history[-self.max_history:]
                
        except Exception as e:
            logging.error(f"Error storing decision history: {e}")
    
    def update_decision_outcome(self, symbol: str, timestamp: str, success: bool, pnl_pct: float):
        """Update decision outcome when trade closes"""
        try:
            for decision in reversed(self.decision_history):
                if (decision['symbol'] == symbol and 
                    decision['timestamp'] == timestamp and 
                    decision['success'] is None):
                    
                    decision['success'] = success
                    decision['pnl_pct'] = pnl_pct
                    break
                    
        except Exception as e:
            logging.error(f"Error updating decision outcome: {e}")
    
    def get_success_analytics(self) -> Dict:
        """Get analytics on decision success rates"""
        try:
            completed_decisions = [d for d in self.decision_history if d.get('success') is not None]
            
            if not completed_decisions:
                return {'total_decisions': 0}
            
            total = len(completed_decisions)
            successful = sum(1 for d in completed_decisions if d['success'])
            
            # Analyze by confidence ranges
            high_confidence = [d for d in completed_decisions if d['xgb_confidence'] >= 0.7]
            medium_confidence = [d for d in completed_decisions if 0.5 <= d['xgb_confidence'] < 0.7]
            
            analytics = {
                'total_decisions': total,
                'success_rate': successful / total if total > 0 else 0,
                'high_confidence_decisions': len(high_confidence),
                'high_confidence_success_rate': sum(1 for d in high_confidence if d['success']) / len(high_confidence) if high_confidence else 0,
                'medium_confidence_decisions': len(medium_confidence),
                'medium_confidence_success_rate': sum(1 for d in medium_confidence if d['success']) / len(medium_confidence) if medium_confidence else 0,
                'avg_pnl_successful': np.mean([d.get('pnl_pct', 0) for d in completed_decisions if d['success']]),
                'avg_pnl_failed': np.mean([d.get('pnl_pct', 0) for d in completed_decisions if not d['success']]),
            }
            
            return analytics
            
        except Exception as e:
            logging.error(f"Error calculating success analytics: {e}")
            return {'total_decisions': 0, 'error': str(e)}
    
    # Helper methods for color coding
    def _get_confidence_color(self, confidence: float) -> str:
        if confidence >= 0.7: return 'green'
        elif confidence >= 0.5: return 'yellow'
        else: return 'red'
    
    def _get_signal_color(self, signal: str) -> str:
        if signal == 'BUY': return 'green'
        elif signal == 'SELL': return 'red'
        else: return 'yellow'
    
    def _get_volatility_color(self, volatility: float) -> str:
        if volatility <= 0.03: return 'green'
        elif volatility <= 0.05: return 'yellow'
        else: return 'red'
    
    def _get_volume_color(self, volume_surge: float) -> str:
        if volume_surge >= 1.5: return 'green'
        elif volume_surge >= 1.0: return 'yellow'
        else: return 'red'
    
    def _get_trend_color(self, trend_strength: float) -> str:
        if trend_strength >= 25: return 'green'
        elif trend_strength >= 20: return 'yellow'
        else: return 'red'
    
    def _get_rsi_color(self, rsi: float) -> str:
        if 40 <= rsi <= 60: return 'green'
        elif 30 <= rsi <= 70: return 'yellow'
        else: return 'red'
    
    def _get_balance_color(self, balance_pct: float) -> str:
        if balance_pct >= 0.2: return 'green'
        elif balance_pct >= 0.1: return 'yellow'
        else: return 'red'
    
    def _get_position_color(self, positions: int) -> str:
        if positions <= 3: return 'green'
        elif positions <= 5: return 'yellow'
        else: return 'red'
    
    def _get_pnl_color(self, pnl: float) -> str:
        if pnl > 0: return 'green'
        elif pnl == 0: return 'white'
        else: return 'red'


# Global instance
global_decision_explainer = DecisionExplainer()
