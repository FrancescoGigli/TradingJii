"""
Decision Comparator - Compares XGBoost ML and AI Technical Analyst signals
Tracks agreement/disagreement statistics and implements execution strategies

This module enables head-to-head comparison of:
- XGBoost ML predictions (fast, trained on historical patterns)
- GPT-4o AI analysis (contextual, reasoned decisions)
"""

import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

from core.ai_technical_analyst import AISignal


class ExecutionStrategy(Enum):
    """Execution strategies for dual-engine system"""
    XGBOOST_ONLY = "xgboost_only"      # Use only XGBoost signals
    AI_ONLY = "ai_only"                 # Use only AI signals
    CONSENSUS = "consensus"             # Trade only when both agree
    WEIGHTED = "weighted"               # Weighted average (70% XGB, 30% AI)
    CHAMPION = "champion"               # Use best performer based on recent win rate


@dataclass
class ComparisonResult:
    """Result of comparing XGBoost and AI signals"""
    symbol: str
    
    # XGBoost signal
    xgb_direction: str  # "LONG", "SHORT"
    xgb_confidence: float  # 0-100
    
    # AI signal
    ai_direction: str  # "LONG", "SHORT", "NEUTRAL"
    ai_confidence: float  # 0-100
    ai_reasoning: str
    ai_key_factors: List[str]
    
    # Comparison results
    agreement: bool  # True if same direction
    confidence_delta: float  # Absolute difference
    
    # Consensus values (if agreement)
    consensus_direction: Optional[str]
    consensus_confidence: float
    
    # Execution decision
    should_trade: bool
    execution_reason: str
    
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class DualEngineStats:
    """Statistics for dual-engine comparison tracking"""
    
    # Session info
    session_start: datetime = field(default_factory=datetime.now)
    
    # XGBoost statistics
    xgb_signals_total: int = 0
    xgb_trades_executed: int = 0
    xgb_trades_won: int = 0
    xgb_trades_lost: int = 0
    xgb_total_pnl: float = 0.0
    xgb_avg_confidence: float = 0.0
    
    # AI statistics
    ai_signals_total: int = 0
    ai_trades_executed: int = 0
    ai_trades_won: int = 0
    ai_trades_lost: int = 0
    ai_total_pnl: float = 0.0
    ai_avg_confidence: float = 0.0
    ai_neutral_count: int = 0  # Times AI said NEUTRAL
    
    # Consensus statistics
    agreement_count: int = 0
    disagreement_count: int = 0
    consensus_trades_executed: int = 0
    consensus_trades_won: int = 0
    consensus_trades_lost: int = 0
    consensus_total_pnl: float = 0.0
    
    # Disagreement tracking
    disagreements: List[Dict] = field(default_factory=list)
    
    # Recent comparisons (for analysis)
    recent_comparisons: List[ComparisonResult] = field(default_factory=list)
    max_recent_comparisons: int = 100
    
    def get_xgb_win_rate(self) -> float:
        """Get XGBoost win rate"""
        total = self.xgb_trades_won + self.xgb_trades_lost
        return (self.xgb_trades_won / total * 100) if total > 0 else 0.0
    
    def get_ai_win_rate(self) -> float:
        """Get AI win rate"""
        total = self.ai_trades_won + self.ai_trades_lost
        return (self.ai_trades_won / total * 100) if total > 0 else 0.0
    
    def get_consensus_win_rate(self) -> float:
        """Get consensus win rate"""
        total = self.consensus_trades_won + self.consensus_trades_lost
        return (self.consensus_trades_won / total * 100) if total > 0 else 0.0
    
    def get_agreement_rate(self) -> float:
        """Get agreement rate between XGB and AI"""
        total = self.agreement_count + self.disagreement_count
        return (self.agreement_count / total * 100) if total > 0 else 0.0
    
    def get_champion(self) -> str:
        """Get current best performer"""
        xgb_wr = self.get_xgb_win_rate()
        ai_wr = self.get_ai_win_rate()
        cons_wr = self.get_consensus_win_rate()
        
        best_wr = max(xgb_wr, ai_wr, cons_wr)
        
        if cons_wr == best_wr and cons_wr > 0:
            return "CONSENSUS"
        elif ai_wr == best_wr and ai_wr > 0:
            return "AI"
        else:
            return "XGBOOST"
    
    def to_dict(self) -> Dict:
        """Get summary dictionary"""
        return {
            'session_start': self.session_start.isoformat(),
            'xgb': {
                'signals': self.xgb_signals_total,
                'executed': self.xgb_trades_executed,
                'won': self.xgb_trades_won,
                'lost': self.xgb_trades_lost,
                'win_rate': self.get_xgb_win_rate(),
                'total_pnl': self.xgb_total_pnl,
                'avg_confidence': self.xgb_avg_confidence
            },
            'ai': {
                'signals': self.ai_signals_total,
                'executed': self.ai_trades_executed,
                'won': self.ai_trades_won,
                'lost': self.ai_trades_lost,
                'win_rate': self.get_ai_win_rate(),
                'total_pnl': self.ai_total_pnl,
                'avg_confidence': self.ai_avg_confidence,
                'neutral_count': self.ai_neutral_count
            },
            'consensus': {
                'agreement_rate': self.get_agreement_rate(),
                'executed': self.consensus_trades_executed,
                'won': self.consensus_trades_won,
                'lost': self.consensus_trades_lost,
                'win_rate': self.get_consensus_win_rate(),
                'total_pnl': self.consensus_total_pnl
            },
            'champion': self.get_champion(),
            'disagreements_count': len(self.disagreements)
        }


class DecisionComparator:
    """
    Compares XGBoost ML signals with AI Technical Analyst signals
    Tracks agreement/disagreement and implements execution strategies
    """
    
    def __init__(self, default_strategy: ExecutionStrategy = ExecutionStrategy.CONSENSUS):
        self.strategy = default_strategy
        self.stats = DualEngineStats()
        
        logging.info(f"🔄 Decision Comparator initialized | Strategy: {default_strategy.value}")
    
    def set_strategy(self, strategy: ExecutionStrategy):
        """Update execution strategy"""
        self.strategy = strategy
        logging.info(f"📊 Execution strategy changed to: {strategy.value}")
    
    def compare_signal(
        self,
        xgb_signal: Dict,
        ai_signal: Optional[AISignal],
        strategy_override: Optional[ExecutionStrategy] = None
    ) -> ComparisonResult:
        """
        Compare XGBoost signal with AI signal
        
        Args:
            xgb_signal: XGBoost signal dict with signal, confidence, symbol
            ai_signal: AI Technical Analyst signal (or None if AI unavailable)
            strategy_override: Optional strategy override for this comparison
            
        Returns:
            ComparisonResult with comparison data and execution decision
        """
        symbol = xgb_signal['symbol']
        strategy = strategy_override or self.strategy
        
        # Extract XGBoost values
        xgb_direction = "LONG" if xgb_signal.get('signal', 1) == 1 else "SHORT"
        xgb_confidence = xgb_signal.get('confidence', 0) * 100  # Convert to 0-100 scale
        
        # Handle missing AI signal
        if ai_signal is None:
            # AI not available - fallback behavior
            comparison = ComparisonResult(
                symbol=symbol,
                xgb_direction=xgb_direction,
                xgb_confidence=xgb_confidence,
                ai_direction="UNAVAILABLE",
                ai_confidence=0,
                ai_reasoning="AI Technical Analyst not available",
                ai_key_factors=[],
                agreement=False,
                confidence_delta=0,
                consensus_direction=xgb_direction if strategy == ExecutionStrategy.XGBOOST_ONLY else None,
                consensus_confidence=xgb_confidence if strategy == ExecutionStrategy.XGBOOST_ONLY else 0,
                should_trade=strategy == ExecutionStrategy.XGBOOST_ONLY,
                execution_reason="AI unavailable - using XGBoost only" if strategy == ExecutionStrategy.XGBOOST_ONLY else "AI unavailable - trade skipped"
            )
            self._update_stats(comparison, ai_available=False)
            return comparison
        
        # Extract AI values
        ai_direction = ai_signal.direction
        ai_confidence = ai_signal.confidence
        ai_reasoning = ai_signal.reasoning
        ai_key_factors = ai_signal.key_factors
        
        # Check agreement
        if ai_direction == "NEUTRAL":
            agreement = False  # NEUTRAL means AI doesn't agree with any direction
        else:
            agreement = (xgb_direction == ai_direction)
        
        confidence_delta = abs(xgb_confidence - ai_confidence)
        
        # Calculate consensus values if agreement
        if agreement:
            consensus_direction = xgb_direction
            consensus_confidence = (xgb_confidence + ai_confidence) / 2
        else:
            consensus_direction = None
            consensus_confidence = 0
        
        # Determine execution based on strategy
        should_trade, execution_reason = self._decide_execution(
            strategy=strategy,
            agreement=agreement,
            xgb_direction=xgb_direction,
            xgb_confidence=xgb_confidence,
            ai_direction=ai_direction,
            ai_confidence=ai_confidence,
            consensus_confidence=consensus_confidence
        )
        
        # Create comparison result
        comparison = ComparisonResult(
            symbol=symbol,
            xgb_direction=xgb_direction,
            xgb_confidence=xgb_confidence,
            ai_direction=ai_direction,
            ai_confidence=ai_confidence,
            ai_reasoning=ai_reasoning,
            ai_key_factors=ai_key_factors,
            agreement=agreement,
            confidence_delta=confidence_delta,
            consensus_direction=consensus_direction,
            consensus_confidence=consensus_confidence,
            should_trade=should_trade,
            execution_reason=execution_reason
        )
        
        # Update statistics
        self._update_stats(comparison, ai_available=True)
        
        # Log comparison
        self._log_comparison(comparison)
        
        return comparison
    
    def _decide_execution(
        self,
        strategy: ExecutionStrategy,
        agreement: bool,
        xgb_direction: str,
        xgb_confidence: float,
        ai_direction: str,
        ai_confidence: float,
        consensus_confidence: float
    ) -> Tuple[bool, str]:
        """
        Decide whether to execute trade based on strategy
        
        Returns:
            Tuple of (should_trade, reason)
        """
        
        if strategy == ExecutionStrategy.XGBOOST_ONLY:
            # Pure XGBoost mode
            if xgb_confidence >= 65:  # Min threshold
                return True, f"XGBoost only: {xgb_confidence:.0f}% confidence"
            return False, f"XGBoost confidence too low: {xgb_confidence:.0f}%"
        
        elif strategy == ExecutionStrategy.AI_ONLY:
            # Pure AI mode
            if ai_direction == "NEUTRAL":
                return False, "AI signal is NEUTRAL"
            if ai_confidence >= 70:
                return True, f"AI only: {ai_confidence:.0f}% confidence"
            return False, f"AI confidence too low: {ai_confidence:.0f}%"
        
        elif strategy == ExecutionStrategy.CONSENSUS:
            # Both must agree
            if not agreement:
                return False, f"Disagreement: XGB={xgb_direction}, AI={ai_direction}"
            if consensus_confidence >= 70:
                return True, f"Consensus: Both agree {consensus_confidence:.0f}%"
            return False, f"Consensus confidence too low: {consensus_confidence:.0f}%"
        
        elif strategy == ExecutionStrategy.WEIGHTED:
            # Weighted average: 70% XGB, 30% AI
            if ai_direction == "NEUTRAL":
                # Only XGB contributes
                weighted_conf = xgb_confidence * 0.85  # Penalize lack of AI confirmation
                if weighted_conf >= 60:
                    return True, f"Weighted (AI neutral): {weighted_conf:.0f}%"
                return False, f"Weighted confidence too low: {weighted_conf:.0f}%"
            
            if agreement:
                weighted_conf = 0.7 * xgb_confidence + 0.3 * ai_confidence
                if weighted_conf >= 65:
                    return True, f"Weighted agree: {weighted_conf:.0f}%"
                return False, f"Weighted confidence too low: {weighted_conf:.0f}%"
            else:
                # Disagreement - use XGB direction but penalized confidence
                weighted_conf = 0.7 * xgb_confidence - 0.2 * ai_confidence
                if weighted_conf >= 50:
                    return True, f"Weighted disagree (XGB priority): {weighted_conf:.0f}%"
                return False, f"Weighted: Disagreement too strong"
        
        elif strategy == ExecutionStrategy.CHAMPION:
            # Use best performer
            champion = self.stats.get_champion()
            
            if champion == "CONSENSUS":
                if agreement and consensus_confidence >= 70:
                    return True, f"Champion (CONSENSUS): {consensus_confidence:.0f}%"
                return False, "Champion strategy: No consensus"
            
            elif champion == "AI":
                if ai_direction != "NEUTRAL" and ai_confidence >= 70:
                    return True, f"Champion (AI): {ai_confidence:.0f}%"
                return False, "Champion (AI): Low confidence or NEUTRAL"
            
            else:  # XGBOOST is champion
                if xgb_confidence >= 65:
                    return True, f"Champion (XGB): {xgb_confidence:.0f}%"
                return False, f"Champion (XGB): Low confidence"
        
        return False, "Unknown strategy"
    
    def _update_stats(self, comparison: ComparisonResult, ai_available: bool):
        """Update comparison statistics"""
        
        # Update XGBoost stats
        self.stats.xgb_signals_total += 1
        
        # Update running average confidence
        n = self.stats.xgb_signals_total
        old_avg = self.stats.xgb_avg_confidence
        self.stats.xgb_avg_confidence = old_avg + (comparison.xgb_confidence - old_avg) / n
        
        # Update AI stats
        if ai_available:
            self.stats.ai_signals_total += 1
            
            if comparison.ai_direction == "NEUTRAL":
                self.stats.ai_neutral_count += 1
            
            # Update AI running average
            n_ai = self.stats.ai_signals_total
            old_avg_ai = self.stats.ai_avg_confidence
            self.stats.ai_avg_confidence = old_avg_ai + (comparison.ai_confidence - old_avg_ai) / n_ai
            
            # Track agreement/disagreement
            if comparison.agreement:
                self.stats.agreement_count += 1
            else:
                self.stats.disagreement_count += 1
                
                # Log disagreement for analysis
                self.stats.disagreements.append({
                    'symbol': comparison.symbol,
                    'xgb_direction': comparison.xgb_direction,
                    'xgb_confidence': comparison.xgb_confidence,
                    'ai_direction': comparison.ai_direction,
                    'ai_confidence': comparison.ai_confidence,
                    'ai_reasoning': comparison.ai_reasoning,
                    'timestamp': comparison.timestamp.isoformat()
                })
        
        # Store recent comparison
        self.stats.recent_comparisons.append(comparison)
        if len(self.stats.recent_comparisons) > self.stats.max_recent_comparisons:
            self.stats.recent_comparisons.pop(0)
    
    def record_trade_outcome(
        self,
        symbol: str,
        source: str,  # "xgb", "ai", "consensus"
        pnl_usd: float,
        won: bool
    ):
        """
        Record outcome of executed trade for performance tracking
        
        Args:
            symbol: Trading symbol
            source: Which engine was used ("xgb", "ai", "consensus")
            pnl_usd: Profit/Loss in USD
            won: True if trade was profitable
        """
        if source == "xgb":
            self.stats.xgb_trades_executed += 1
            self.stats.xgb_total_pnl += pnl_usd
            if won:
                self.stats.xgb_trades_won += 1
            else:
                self.stats.xgb_trades_lost += 1
        
        elif source == "ai":
            self.stats.ai_trades_executed += 1
            self.stats.ai_total_pnl += pnl_usd
            if won:
                self.stats.ai_trades_won += 1
            else:
                self.stats.ai_trades_lost += 1
        
        elif source == "consensus":
            self.stats.consensus_trades_executed += 1
            self.stats.consensus_total_pnl += pnl_usd
            if won:
                self.stats.consensus_trades_won += 1
            else:
                self.stats.consensus_trades_lost += 1
            
            # Also count for both XGB and AI since both agreed
            self.stats.xgb_trades_executed += 1
            self.stats.xgb_total_pnl += pnl_usd
            self.stats.ai_trades_executed += 1
            self.stats.ai_total_pnl += pnl_usd
            
            if won:
                self.stats.xgb_trades_won += 1
                self.stats.ai_trades_won += 1
            else:
                self.stats.xgb_trades_lost += 1
                self.stats.ai_trades_lost += 1
        
        logging.debug(f"📊 Recorded trade outcome: {symbol} {source} {'WIN' if won else 'LOSS'} ${pnl_usd:.2f}")
    
    def _log_comparison(self, comparison: ComparisonResult):
        """Log comparison result"""
        symbol_short = comparison.symbol.replace('/USDT:USDT', '')
        
        xgb_emoji = "🟢" if comparison.xgb_direction == "LONG" else "🔴"
        ai_emoji = "🟢" if comparison.ai_direction == "LONG" else "🔴" if comparison.ai_direction == "SHORT" else "⚪"
        
        agreement_emoji = "✅" if comparison.agreement else "❌"
        trade_emoji = "✅" if comparison.should_trade else "⏭️"
        
        logging.info(
            f"🔄 {symbol_short}: "
            f"XGB {xgb_emoji}{comparison.xgb_direction}({comparison.xgb_confidence:.0f}%) vs "
            f"AI {ai_emoji}{comparison.ai_direction}({comparison.ai_confidence:.0f}%) "
            f"| {agreement_emoji} | {trade_emoji} {comparison.execution_reason}"
        )
        
        if not comparison.agreement and comparison.ai_direction != "UNAVAILABLE":
            logging.info(f"   💡 AI Reasoning: {comparison.ai_reasoning[:100]}...")
    
    def get_stats_summary(self) -> Dict:
        """Get statistics summary"""
        return self.stats.to_dict()
    
    def display_stats_dashboard(self):
        """Display beautiful stats dashboard to console"""
        stats = self.stats
        
        dashboard = """
╔═══════════════════════════════════════════════════════════╗
║          DUAL-ENGINE PERFORMANCE COMPARISON               ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  XGBoost ML Engine:                                       ║
║  • Win Rate: {xgb_wr:.1f}% ({xgb_won}W / {xgb_lost}L)
║  • Total PnL: ${xgb_pnl:.2f}
║  • Avg Confidence: {xgb_conf:.1f}%
║                                                           ║
║  GPT-4o AI Analyst:                                       ║
║  • Win Rate: {ai_wr:.1f}% ({ai_won}W / {ai_lost}L)
║  • Total PnL: ${ai_pnl:.2f}
║  • Avg Confidence: {ai_conf:.1f}%
║  • NEUTRAL signals: {ai_neutral}
║                                                           ║
║  Consensus (Both Agree):                                  ║
║  • Agreement Rate: {agree_rate:.1f}%
║  • Win Rate: {cons_wr:.1f}% ({cons_won}W / {cons_lost}L)
║  • Total PnL: ${cons_pnl:.2f}
║                                                           ║
║  🏆 CHAMPION: {champion}
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""".format(
            xgb_wr=stats.get_xgb_win_rate(),
            xgb_won=stats.xgb_trades_won,
            xgb_lost=stats.xgb_trades_lost,
            xgb_pnl=stats.xgb_total_pnl,
            xgb_conf=stats.xgb_avg_confidence,
            ai_wr=stats.get_ai_win_rate(),
            ai_won=stats.ai_trades_won,
            ai_lost=stats.ai_trades_lost,
            ai_pnl=stats.ai_total_pnl,
            ai_conf=stats.ai_avg_confidence,
            ai_neutral=stats.ai_neutral_count,
            agree_rate=stats.get_agreement_rate(),
            cons_wr=stats.get_consensus_win_rate(),
            cons_won=stats.consensus_trades_won,
            cons_lost=stats.consensus_trades_lost,
            cons_pnl=stats.consensus_total_pnl,
            champion=stats.get_champion()
        )
        
        print(dashboard)
        return dashboard
    
    def get_recent_disagreements(self, n: int = 10) -> List[Dict]:
        """Get recent disagreements for analysis"""
        return self.stats.disagreements[-n:]


# Global instance
global_decision_comparator = DecisionComparator()
