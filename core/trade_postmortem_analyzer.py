#!/usr/bin/env python3
"""
🔍 TRADE POST-MORTEM ANALYZER

Sistema per analizzare in dettaglio i trade chiusi in perdita:
- Identifica le cause delle perdite
- Analizza se le decisioni iniziali erano corrette
- Fornisce raccomandazioni per evitare errori simili
- Genera report dettagliati salvati su file
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from termcolor import colored
import numpy as np


class TradePostmortemAnalyzer:
    """
    Analyzer per post-mortem dei trade falliti
    """
    
    def __init__(self):
        self.postmortem_dir = Path("trade_postmortem")
        self.postmortem_dir.mkdir(exist_ok=True)
        
        # Categories of failure reasons
        self.failure_categories = {
            'STOP_LOSS_HIT': 'Stop loss raggiunto - volatilità eccessiva o movimento contrario',
            'TRAILING_STOP': 'Trailing stop attivato - profit protetto ma reversal',
            'WEAK_SIGNAL': 'Segnale iniziale troppo debole - confidence bassa',
            'MARKET_REVERSAL': 'Mercato si è invertito - trend non confermato',
            'TIMING_ERROR': 'Timing errato - entrata troppo presto/tardi',
            'VOLATILITY_SPIKE': 'Spike di volatilità - mercato imprevedibile',
            'LOW_LIQUIDITY': 'Bassa liquidità - slippage eccessivo',
            'EXTERNAL_SHOCK': 'Evento esterno - news, delisting, etc.',
            'POOR_RISK_REWARD': 'Risk/Reward sfavorevole - SL troppo stretto',
            'OVEREXPOSURE': 'Eccessiva esposizione - troppo capitale allocato'
        }
    
    def analyze_failed_trade(self, trade_info: Dict, market_data: Optional[Dict] = None) -> Dict:
        """
        Analizza in dettaglio un trade fallito
        
        Args:
            trade_info: Informazioni complete sul trade
            market_data: Dati di mercato aggiuntivi (opzionale)
            
        Returns:
            Dict con l'analisi completa del fallimento
        """
        try:
            symbol = trade_info.get('symbol', '').replace('/USDT:USDT', '')
            
            analysis = {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'trade_summary': self._build_trade_summary(trade_info),
                'failure_analysis': self._analyze_failure_reasons(trade_info),
                'decision_review': self._review_initial_decision(trade_info),
                'market_conditions': self._analyze_market_conditions(trade_info, market_data),
                'risk_assessment': self._assess_risk_management(trade_info),
                'recommendations': self._generate_recommendations(trade_info),
                'severity': self._calculate_severity(trade_info),
                'lessons_learned': []
            }
            
            # Generate lessons learned
            analysis['lessons_learned'] = self._extract_lessons(analysis)
            
            return analysis
            
        except Exception as e:
            logging.error(f"Error analyzing failed trade: {e}")
            return {'error': str(e)}
    
    def _build_trade_summary(self, trade_info: Dict) -> Dict:
        """Costruisce un riassunto del trade"""
        return {
            'symbol': trade_info.get('symbol', ''),
            'side': trade_info.get('signal_data', {}).get('signal_name', 'UNKNOWN'),
            'entry_price': trade_info.get('entry_price', 0.0),
            'exit_price': trade_info.get('exit_price', 0.0),
            'pnl_percentage': trade_info.get('pnl_percentage', 0.0),
            'pnl_usd': trade_info.get('pnl_usd', 0.0),
            'duration_hours': trade_info.get('duration_hours', 0.0),
            'close_reason': trade_info.get('close_reason', 'UNKNOWN'),
            'open_time': trade_info.get('open_timestamp', ''),
            'close_time': trade_info.get('close_timestamp', '')
        }
    
    def _analyze_failure_reasons(self, trade_info: Dict) -> Dict:
        """Analizza le ragioni specifiche del fallimento"""
        close_reason = trade_info.get('close_reason', 'UNKNOWN')
        pnl_pct = trade_info.get('pnl_percentage', 0.0)
        duration_hours = trade_info.get('duration_hours', 0.0)
        
        reasons = []
        primary_category = None
        
        # Analyze based on close reason
        if close_reason == 'STOP_LOSS':
            primary_category = 'STOP_LOSS_HIT'
            reasons.append("Stop loss attivato - il mercato si è mosso contro la posizione")
            
            if duration_hours < 1:
                reasons.append("Chiusura molto rapida - possibile entrata in timing errato")
            
            if pnl_pct < -10:
                reasons.append("Perdita significativa - possibile stop loss troppo largo o slippage")
        
        elif close_reason == 'TRAILING_STOP':
            primary_category = 'TRAILING_STOP'
            reasons.append("Trailing stop attivato - il mercato ha invertito dopo essere andato in profitto")
            reasons.append("Il trade aveva raggiunto profitto prima del reversal")
        
        elif close_reason == 'MANUAL':
            primary_category = 'MARKET_REVERSAL'
            reasons.append("Chiusura manuale - possibile riconoscimento di segnale errato")
            
            if duration_hours < 2:
                reasons.append("Decisione rapida di uscire - forse segnale debole fin dall'inizio")
        
        # Analyze signal strength
        signal_data = trade_info.get('signal_data', {})
        xgb_confidence = signal_data.get('confidence', 0.0)
        
        if xgb_confidence < 0.7:
            reasons.append(f"Segnale XGBoost debole ({xgb_confidence:.1%}) - threshold minimo non ottimale")
            if primary_category is None:
                primary_category = 'WEAK_SIGNAL'
        
        # Analyze RL approval
        rl_confidence = signal_data.get('rl_confidence', 0.0)
        if rl_confidence < 0.6:
            reasons.append(f"RL confidence bassa ({rl_confidence:.1%}) - sistema aveva dubbi")
        
        # Analyze volatility
        market_context = trade_info.get('market_context', {})
        volatility = market_context.get('volatility', 0.0)
        
        if volatility > 0.05:
            reasons.append(f"Volatilità elevata ({volatility*100:.1f}%) - mercato instabile")
            if primary_category is None:
                primary_category = 'VOLATILITY_SPIKE'
        
        # Analyze trend strength
        trend_strength = market_context.get('trend_strength', 0.0)
        if trend_strength < 20:
            reasons.append(f"Trend debole (ADX {trend_strength:.1f}) - mancanza di momentum")
            if primary_category is None:
                primary_category = 'MARKET_REVERSAL'
        
        # Default category if none assigned
        if primary_category is None:
            primary_category = 'MARKET_REVERSAL'
        
        return {
            'primary_category': primary_category,
            'category_description': self.failure_categories.get(primary_category, 'Unknown'),
            'specific_reasons': reasons,
            'close_reason': close_reason,
            'confidence_scores': {
                'xgb_confidence': xgb_confidence,
                'rl_confidence': rl_confidence
            }
        }
    
    def _review_initial_decision(self, trade_info: Dict) -> Dict:
        """Rivede la decisione iniziale di apertura del trade"""
        signal_data = trade_info.get('signal_data', {})
        
        # Extract decision factors
        tf_predictions = signal_data.get('tf_predictions', {})
        xgb_confidence = signal_data.get('confidence', 0.0)
        rl_approved = signal_data.get('rl_approved', False)
        
        # Count timeframe agreement
        tf_signals = list(tf_predictions.values())
        signal_consensus = max(set(tf_signals), key=tf_signals.count) if tf_signals else None
        consensus_strength = tf_signals.count(signal_consensus) / len(tf_signals) if tf_signals else 0
        
        decision_quality = "STRONG"
        
        if consensus_strength < 0.6:
            decision_quality = "WEAK"
        elif consensus_strength < 0.8:
            decision_quality = "MODERATE"
        
        # Evaluate decision correctness
        decision_errors = []
        
        if xgb_confidence < 0.65:
            decision_errors.append("XGBoost confidence sotto threshold raccomandato (65%)")
        
        if consensus_strength < 0.66:  # Less than 2/3 agreement
            decision_errors.append("Disaccordo tra timeframes - consensus debole")
        
        if not rl_approved and rl_approved is not None:
            decision_errors.append("RL agent aveva disapprovato il trade")
        
        return {
            'decision_quality': decision_quality,
            'timeframe_consensus': {
                'strength': consensus_strength,
                'predictions': tf_predictions
            },
            'confidence_metrics': {
                'xgb_confidence': xgb_confidence,
                'rl_approved': rl_approved
            },
            'decision_errors': decision_errors,
            'should_have_traded': len(decision_errors) == 0 and xgb_confidence >= 0.7
        }
    
    def _analyze_market_conditions(self, trade_info: Dict, market_data: Optional[Dict]) -> Dict:
        """Analizza le condizioni di mercato durante il trade"""
        market_context = trade_info.get('market_context', {})
        
        conditions = {
            'volatility': market_context.get('volatility', 0.0),
            'volume_surge': market_context.get('volume_surge', 1.0),
            'trend_strength': market_context.get('trend_strength', 0.0),
            'rsi_position': market_context.get('rsi_position', 50.0)
        }
        
        condition_assessment = []
        
        # Volatility assessment
        if conditions['volatility'] > 0.05:
            condition_assessment.append("⚠️ Volatilità molto alta - mercato instabile")
        elif conditions['volatility'] < 0.02:
            condition_assessment.append("✅ Volatilità bassa - condizioni favorevoli")
        
        # Volume assessment
        if conditions['volume_surge'] < 0.8:
            condition_assessment.append("⚠️ Volume basso - possibile bassa liquidità")
        elif conditions['volume_surge'] > 1.5:
            condition_assessment.append("✅ Volume elevato - alta partecipazione")
        
        # Trend assessment
        if conditions['trend_strength'] < 20:
            condition_assessment.append("⚠️ Trend debole - direzione incerta")
        elif conditions['trend_strength'] > 40:
            condition_assessment.append("✅ Trend forte - direzione chiara")
        
        # RSI assessment
        rsi = conditions['rsi_position']
        if rsi < 30:
            condition_assessment.append("⚠️ RSI oversold - possibile reversal rialzista")
        elif rsi > 70:
            condition_assessment.append("⚠️ RSI overbought - possibile reversal ribassista")
        
        return {
            'conditions': conditions,
            'assessment': condition_assessment,
            'favorable_conditions': len([a for a in condition_assessment if a.startswith('✅')]) >= 2
        }
    
    def _assess_risk_management(self, trade_info: Dict) -> Dict:
        """Valuta la gestione del rischio del trade"""
        pnl_pct = trade_info.get('pnl_percentage', 0.0)
        pnl_usd = trade_info.get('pnl_usd', 0.0)
        close_reason = trade_info.get('close_reason', '')
        
        # Calculate risk metrics
        position_size = abs(pnl_usd / (pnl_pct / 100)) if pnl_pct != 0 else 0
        
        risk_assessment = []
        risk_score = 0  # 0-10 scale
        
        # Assess loss magnitude
        if pnl_pct < -20:
            risk_assessment.append("🔴 Perdita grave (>20%) - stop loss troppo largo")
            risk_score += 3
        elif pnl_pct < -10:
            risk_assessment.append("🟡 Perdita significativa (10-20%) - risk management da migliorare")
            risk_score += 2
        elif pnl_pct < -5:
            risk_assessment.append("🟢 Perdita contenuta (<10%) - stop loss appropriato")
            risk_score += 1
        
        # Assess stop loss execution
        if close_reason == 'STOP_LOSS':
            risk_assessment.append("✅ Stop loss eseguito correttamente - capitale protetto")
        elif close_reason == 'TRAILING_STOP':
            risk_assessment.append("✅ Trailing stop ha protetto parte dei profitti")
        elif close_reason == 'MANUAL':
            risk_assessment.append("⚠️ Chiusura manuale - consider automated stop loss")
            risk_score += 1
        
        # Portfolio exposure
        portfolio_state = trade_info.get('portfolio_state', {})
        available_balance = portfolio_state.get('available_balance', 0)
        wallet_balance = portfolio_state.get('wallet_balance', 1)
        
        if position_size > wallet_balance * 0.15:
            risk_assessment.append("🔴 Posizione troppo grande (>15% portfolio)")
            risk_score += 2
        elif position_size > wallet_balance * 0.10:
            risk_assessment.append("🟡 Posizione al limite (10-15% portfolio)")
            risk_score += 1
        
        return {
            'risk_score': min(risk_score, 10),
            'risk_level': 'HIGH' if risk_score >= 5 else 'MEDIUM' if risk_score >= 3 else 'LOW',
            'position_size_usd': position_size,
            'risk_assessment': risk_assessment,
            'stop_loss_effectiveness': close_reason in ['STOP_LOSS', 'TRAILING_STOP']
        }
    
    def _generate_recommendations(self, trade_info: Dict) -> List[str]:
        """Genera raccomandazioni per evitare errori simili"""
        recommendations = []
        
        signal_data = trade_info.get('signal_data', {})
        market_context = trade_info.get('market_context', {})
        pnl_pct = trade_info.get('pnl_percentage', 0.0)
        
        # Recommendations based on signal quality
        xgb_confidence = signal_data.get('confidence', 0.0)
        if xgb_confidence < 0.7:
            recommendations.append("📊 Aumentare threshold minimo XGBoost a 70% per ridurre segnali deboli")
        
        # Recommendations based on volatility
        volatility = market_context.get('volatility', 0.0)
        if volatility > 0.05:
            recommendations.append("⚡ Evitare trade in periodi di alta volatilità (>5%)")
            recommendations.append("📉 Implementare stop loss più stretti durante alta volatilità")
        
        # Recommendations based on trend
        trend_strength = market_context.get('trend_strength', 0.0)
        if trend_strength < 20:
            recommendations.append("📈 Richiedere trend strength minimo di 20 (ADX) prima di entrare")
        
        # Recommendations based on loss magnitude
        if pnl_pct < -15:
            recommendations.append("🛡️ Implementare stop loss più conservativi (max -10%)")
        
        # Recommendations based on timeframe consensus
        tf_predictions = signal_data.get('tf_predictions', {})
        tf_signals = list(tf_predictions.values())
        if tf_signals:
            consensus_strength = max(set(tf_signals), key=tf_signals.count) / len(tf_signals)
            if consensus_strength < 0.66:
                recommendations.append("🎯 Richiedere almeno 2/3 consensus tra timeframes")
        
        # RL recommendations
        rl_confidence = signal_data.get('rl_confidence', 0.0)
        if rl_confidence < 0.6:
            recommendations.append("🤖 Aumentare threshold RL a 60% per maggiore selettività")
        
        # Volume recommendations
        volume_surge = market_context.get('volume_surge', 1.0)
        if volume_surge < 1.0:
            recommendations.append("📊 Evitare trade con volume sotto la media")
        
        return recommendations
    
    def _calculate_severity(self, trade_info: Dict) -> str:
        """Calcola la gravità della perdita"""
        pnl_pct = trade_info.get('pnl_percentage', 0.0)
        pnl_usd = abs(trade_info.get('pnl_usd', 0.0))
        
        if pnl_pct < -20 or pnl_usd > 50:
            return "CRITICAL"
        elif pnl_pct < -10 or pnl_usd > 20:
            return "HIGH"
        elif pnl_pct < -5 or pnl_usd > 10:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _extract_lessons(self, analysis: Dict) -> List[str]:
        """Estrae lezioni chiave dall'analisi"""
        lessons = []
        
        failure = analysis.get('failure_analysis', {})
        decision = analysis.get('decision_review', {})
        risk = analysis.get('risk_assessment', {})
        
        # Primary lesson from failure category
        primary_category = failure.get('primary_category', '')
        category_desc = failure.get('category_description', '')
        if category_desc:
            lessons.append(f"📚 Lezione principale: {category_desc}")
        
        # Decision quality lesson
        if not decision.get('should_have_traded', True):
            lessons.append("🎯 Decisione errata: I segnali iniziali erano troppo deboli per giustificare il trade")
        
        # Risk management lesson
        risk_level = risk.get('risk_level', 'LOW')
        if risk_level in ['HIGH', 'CRITICAL']:
            lessons.append("⚠️ Risk management: Necessaria maggiore protezione del capitale")
        
        # Specific actionable lessons
        decision_errors = decision.get('decision_errors', [])
        if decision_errors:
            lessons.append(f"❌ Errori evitabili: {', '.join(decision_errors[:2])}")
        
        return lessons
    
    def save_postmortem_report(self, analysis: Dict) -> str:
        """Salva il report post-mortem su file"""
        try:
            symbol = analysis['symbol']
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"postmortem_{symbol}_{timestamp}.json"
            filepath = self.postmortem_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(analysis, f, indent=2, default=str)
            
            logging.info(f"📄 Post-mortem report saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logging.error(f"Error saving post-mortem report: {e}")
            return ""
    
    def display_postmortem_report(self, analysis: Dict):
        """Mostra il report post-mortem nel terminale"""
        try:
            if 'error' in analysis:
                print(colored(f"\n❌ Error in post-mortem analysis: {analysis['error']}", "red"))
                return
            
            symbol = analysis['symbol']
            severity = analysis['severity']
            
            # Header
            severity_colors = {'CRITICAL': 'red', 'HIGH': 'red', 'MEDIUM': 'yellow', 'LOW': 'green'}
            severity_color = severity_colors.get(severity, 'white')
            
            print(colored(f"\n🔍 POST-MORTEM ANALYSIS - {symbol}", "cyan", attrs=['bold']))
            print(colored("=" * 80, "cyan"))
            print(f"⚠️  Severity: {colored(severity, severity_color, attrs=['bold'])}")
            print(colored("=" * 80, "cyan"))
            
            # Trade Summary
            summary = analysis['trade_summary']
            print(colored("\n📊 TRADE SUMMARY:", "yellow", attrs=['bold']))
            print(f"  Direction: {colored(summary['side'], 'cyan')}")
            print(f"  Entry: ${summary['entry_price']:.6f}")
            print(f"  Exit: ${summary['exit_price']:.6f}")
            pnl_pct_str = f"{summary['pnl_percentage']:.2f}%"
            pnl_usd_str = f"{summary['pnl_usd']:.2f} USDT"
            print(f"  PnL: {colored(pnl_pct_str, 'red')} ({colored(pnl_usd_str, 'red')})")
            print(f"  Duration: {summary['duration_hours']:.1f} hours")
            print(f"  Close Reason: {colored(summary['close_reason'], 'yellow')}")
            
            # Failure Analysis
            failure = analysis['failure_analysis']
            print(colored("\n❌ FAILURE ANALYSIS:", "yellow", attrs=['bold']))
            print(f"  Primary Category: {colored(failure['primary_category'], 'red', attrs=['bold'])}")
            print(f"  Description: {failure['category_description']}")
            print(f"\n  Specific Reasons:")
            for reason in failure['specific_reasons']:
                print(f"    • {reason}")
            
            # Decision Review
            decision = analysis['decision_review']
            print(colored("\n🎯 DECISION REVIEW:", "yellow", attrs=['bold']))
            decision_quality = decision['decision_quality']
            quality_color = 'green' if decision_quality == 'STRONG' else 'yellow' if decision_quality == 'MODERATE' else 'red'
            print(f"  Quality: {colored(decision_quality, quality_color, attrs=['bold'])}")
            print(f"  Should Have Traded: {colored('NO' if not decision['should_have_traded'] else 'YES', 'red' if not decision['should_have_traded'] else 'green', attrs=['bold'])}")
            
            if decision['decision_errors']:
                print(f"\n  Decision Errors:")
                for error in decision['decision_errors']:
                    print(f"    ❌ {error}")
            
            # Market Conditions
            market = analysis['market_conditions']
            print(colored("\n🌍 MARKET CONDITIONS:", "yellow", attrs=['bold']))
            print(f"  Favorable: {colored('NO' if not market['favorable_conditions'] else 'YES', 'red' if not market['favorable_conditions'] else 'green')}")
            for assessment in market['assessment']:
                print(f"  {assessment}")
            
            # Risk Assessment
            risk = analysis['risk_assessment']
            print(colored("\n⚖️  RISK ASSESSMENT:", "yellow", attrs=['bold']))
            risk_level = risk['risk_level']
            risk_color = 'red' if risk_level == 'HIGH' else 'yellow' if risk_level == 'MEDIUM' else 'green'
            print(f"  Risk Level: {colored(risk_level, risk_color, attrs=['bold'])}")
            print(f"  Risk Score: {risk['risk_score']}/10")
            for assessment in risk['risk_assessment']:
                print(f"  {assessment}")
            
            # Recommendations
            recommendations = analysis['recommendations']
            if recommendations:
                print(colored("\n💡 RECOMMENDATIONS:", "yellow", attrs=['bold']))
                for i, rec in enumerate(recommendations, 1):
                    print(f"  {i}. {rec}")
            
            # Lessons Learned
            lessons = analysis['lessons_learned']
            if lessons:
                print(colored("\n📚 LESSONS LEARNED:", "green", attrs=['bold']))
                for lesson in lessons:
                    print(f"  {lesson}")
            
            print(colored("=" * 80, "cyan"))
            
        except Exception as e:
            logging.error(f"Error displaying post-mortem report: {e}")
            print(colored(f"❌ Error displaying report: {e}", "red"))
    
    def generate_session_postmortem(self, completed_trades: List[Dict]) -> Dict:
        """Genera un post-mortem completo della sessione"""
        try:
            if not completed_trades:
                return {'error': 'No completed trades to analyze'}
            
            # Filter only losing trades
            losing_trades = [t for t in completed_trades if t.get('pnl_percentage', 0) < 0]
            
            if not losing_trades:
                return {'message': 'No losing trades in this session - great job!'}
            
            session_analysis = {
                'timestamp': datetime.now().isoformat(),
                'total_trades': len(completed_trades),
                'losing_trades_count': len(losing_trades),
                'total_loss_usd': sum(t.get('pnl_usd', 0) for t in losing_trades),
                'avg_loss_pct': np.mean([t.get('pnl_percentage', 0) for t in losing_trades]),
                'worst_trade': min(losing_trades, key=lambda x: x.get('pnl_percentage', 0)),
                'common_failure_patterns': self._identify_common_patterns(losing_trades),
                'individual_analyses': []
            }
            
            # Analyze each losing trade
            for trade in losing_trades:
                analysis = self.analyze_failed_trade(trade)
                session_analysis['individual_analyses'].append(analysis)
            
            return session_analysis
            
        except Exception as e:
            logging.error(f"Error generating session post-mortem: {e}")
            return {'error': str(e)}
    
    def _identify_common_patterns(self, losing_trades: List[Dict]) -> Dict:
        """Identifica pattern comuni tra i trade perdenti"""
        patterns = {
            'weak_signals': 0,
            'high_volatility': 0,
            'weak_trend': 0,
            'quick_stops': 0,
            'low_consensus': 0
        }
        
        for trade in losing_trades:
            signal_data = trade.get('signal_data', {})
            market_context = trade.get('market_context', {})
            
            if signal_data.get('confidence', 0) < 0.7:
                patterns['weak_signals'] += 1
            
            if market_context.get('volatility', 0) > 0.05:
                patterns['high_volatility'] += 1
            
            if market_context.get('trend_strength', 0) < 20:
                patterns['weak_trend'] += 1
            
            if trade.get('duration_hours', 99) < 1:
                patterns['quick_stops'] += 1
            
            tf_preds = list(signal_data.get('tf_predictions', {}).values())
            if tf_preds:
                consensus = max(set(tf_preds), key=tf_preds.count) / len(tf_preds)
                if consensus < 0.66:
                    patterns['low_consensus'] += 1
        
        # Calculate percentages
        total = len(losing_trades)
        pattern_percentages = {k: (v / total) * 100 for k, v in patterns.items()}
        
        return {
            'patterns': patterns,
            'percentages': pattern_percentages,
            'most_common': max(pattern_percentages.items(), key=lambda x: x[1])
        }


# Global instance
global_postmortem_analyzer = TradePostmortemAnalyzer()
