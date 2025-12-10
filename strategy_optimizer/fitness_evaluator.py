"""
Fitness Evaluator - Calcolo metriche performance per Algoritmo Genetico

Valuta la qualità di un set di parametri (cromosoma) analizzando i risultati
di un backtest e calcolando metriche standardizzate.

BLOCCO 3: Strategy Optimizer
"""

from __future__ import annotations
from typing import List, Dict, Any
from dataclasses import dataclass
import numpy as np
import logging

_LOG = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """Singolo trade simulato"""
    symbol: str
    entry_time: str
    exit_time: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    exit_price: float
    position_size: float
    leverage: int
    margin_used: float
    pnl_usd: float
    pnl_pct: float
    roe_pct: float  # Return on Equity (PnL / Margin)
    exit_reason: str  # 'TP', 'SL', 'TIMEOUT', etc.
    confidence: float
    volatility: float


@dataclass
class PerformanceMetrics:
    """Metriche di performance complete"""
    # Metriche primarie
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # P&L
    total_pnl_usd: float
    total_pnl_pct: float
    avg_win_usd: float
    avg_loss_usd: float
    avg_roe: float
    
    # Risk metrics
    max_drawdown_pct: float
    max_drawdown_usd: float
    sharpe_ratio: float
    sortino_ratio: float
    profit_factor: float
    
    # Return metrics
    cagr: float  # Compound Annual Growth Rate
    total_return_pct: float
    
    # Trade quality
    avg_risk_reward: float
    sl_hit_rate: float
    tp_hit_rate: float
    avg_trade_duration_hours: float
    
    # Fitness score
    fitness_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario"""
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'total_pnl_usd': self.total_pnl_usd,
            'total_pnl_pct': self.total_pnl_pct,
            'avg_win_usd': self.avg_win_usd,
            'avg_loss_usd': self.avg_loss_usd,
            'avg_roe': self.avg_roe,
            'max_drawdown_pct': self.max_drawdown_pct,
            'max_drawdown_usd': self.max_drawdown_usd,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'profit_factor': self.profit_factor,
            'cagr': self.cagr,
            'total_return_pct': self.total_return_pct,
            'avg_risk_reward': self.avg_risk_reward,
            'sl_hit_rate': self.sl_hit_rate,
            'tp_hit_rate': self.tp_hit_rate,
            'avg_trade_duration_hours': self.avg_trade_duration_hours,
            'fitness_score': self.fitness_score,
        }


class FitnessEvaluator:
    """
    Valutatore fitness per Algoritmo Genetico
    
    Calcola metriche di performance da una lista di trade simulati e
    combina le metriche in un singolo fitness score.
    """
    
    def __init__(
        self,
        initial_capital: float = 1000.0,
        cagr_weight: float = 0.5,
        sharpe_weight: float = 0.3,
        drawdown_penalty: float = 0.2,
        min_trades_threshold: int = 10,
    ):
        """
        Args:
            initial_capital: Capitale iniziale per calcoli
            cagr_weight: Peso CAGR nella fitness
            sharpe_weight: Peso Sharpe Ratio nella fitness
            drawdown_penalty: Penalità drawdown nella fitness
            min_trades_threshold: Numero minimo trade richiesto
        """
        self.initial_capital = initial_capital
        self.cagr_weight = cagr_weight
        self.sharpe_weight = sharpe_weight
        self.drawdown_penalty = drawdown_penalty
        self.min_trades_threshold = min_trades_threshold
    
    def evaluate(self, trades: List[TradeResult], duration_days: int = 90) -> PerformanceMetrics:
        """
        Valuta performance da lista trade
        
        Args:
            trades: Lista trade simulati
            duration_days: Durata periodo di test in giorni
            
        Returns:
            PerformanceMetrics complete
        """
        if not trades:
            return self._create_zero_metrics()
        
        # Calcola metriche base
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.pnl_usd > 0)
        losing_trades = sum(1 for t in trades if t.pnl_usd < 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        # P&L
        total_pnl_usd = sum(t.pnl_usd for t in trades)
        total_pnl_pct = (total_pnl_usd / self.initial_capital) * 100
        
        wins = [t.pnl_usd for t in trades if t.pnl_usd > 0]
        losses = [t.pnl_usd for t in trades if t.pnl_usd < 0]
        
        avg_win_usd = np.mean(wins) if wins else 0.0
        avg_loss_usd = np.mean(losses) if losses else 0.0
        avg_roe = np.mean([t.roe_pct for t in trades]) if trades else 0.0
        
        # Equity curve per drawdown
        equity_curve = self._calculate_equity_curve(trades)
        max_drawdown_pct, max_drawdown_usd = self._calculate_max_drawdown(equity_curve)
        
        # Risk metrics
        returns = [t.roe_pct / 100 for t in trades]  # Convert to decimal
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        sortino_ratio = self._calculate_sortino_ratio(returns)
        
        # Profit factor
        total_wins = sum(wins) if wins else 0.0
        total_losses = abs(sum(losses)) if losses else 0.0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
        
        # CAGR
        final_capital = self.initial_capital + total_pnl_usd
        cagr = self._calculate_cagr(self.initial_capital, final_capital, duration_days)
        total_return_pct = ((final_capital - self.initial_capital) / self.initial_capital) * 100
        
        # Trade quality
        avg_risk_reward = abs(avg_win_usd / avg_loss_usd) if avg_loss_usd != 0 else 0.0
        sl_hit_rate = sum(1 for t in trades if t.exit_reason == 'SL') / total_trades if total_trades > 0 else 0.0
        tp_hit_rate = sum(1 for t in trades if t.exit_reason == 'TP') / total_trades if total_trades > 0 else 0.0
        
        # Trade duration (mock - needs real timestamps)
        avg_trade_duration_hours = 4.0  # Placeholder
        
        # Calculate fitness score
        fitness_score = self._calculate_fitness(
            cagr=cagr,
            sharpe_ratio=sharpe_ratio,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=total_trades,
            win_rate=win_rate,
        )
        
        return PerformanceMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl_usd=total_pnl_usd,
            total_pnl_pct=total_pnl_pct,
            avg_win_usd=avg_win_usd,
            avg_loss_usd=avg_loss_usd,
            avg_roe=avg_roe,
            max_drawdown_pct=max_drawdown_pct,
            max_drawdown_usd=max_drawdown_usd,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            profit_factor=profit_factor,
            cagr=cagr,
            total_return_pct=total_return_pct,
            avg_risk_reward=avg_risk_reward,
            sl_hit_rate=sl_hit_rate,
            tp_hit_rate=tp_hit_rate,
            avg_trade_duration_hours=avg_trade_duration_hours,
            fitness_score=fitness_score,
        )
    
    def _calculate_equity_curve(self, trades: List[TradeResult]) -> np.ndarray:
        """Calcola equity curve cumulativa"""
        equity = [self.initial_capital]
        for trade in trades:
            equity.append(equity[-1] + trade.pnl_usd)
        return np.array(equity)
    
    def _calculate_max_drawdown(self, equity_curve: np.ndarray) -> tuple[float, float]:
        """Calcola maximum drawdown in % e USD"""
        if len(equity_curve) == 0:
            return 0.0, 0.0
        
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = equity_curve - running_max
        max_drawdown_usd = abs(np.min(drawdown))
        max_drawdown_pct = (max_drawdown_usd / self.initial_capital) * 100 if self.initial_capital > 0 else 0.0
        
        return max_drawdown_pct, max_drawdown_usd
    
    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.0) -> float:
        """Calcola Sharpe Ratio annualizzato"""
        if not returns or len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        avg_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        if std_return == 0:
            return 0.0
        
        # Annualize (assume ~250 trading days)
        sharpe = (avg_return - risk_free_rate) / std_return
        sharpe_annualized = sharpe * np.sqrt(250)
        
        return sharpe_annualized
    
    def _calculate_sortino_ratio(self, returns: List[float], risk_free_rate: float = 0.0) -> float:
        """Calcola Sortino Ratio (considera solo downside risk)"""
        if not returns or len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        avg_return = np.mean(returns_array)
        
        # Solo negative returns per downside deviation
        downside_returns = returns_array[returns_array < 0]
        if len(downside_returns) == 0:
            return 0.0
        
        downside_std = np.std(downside_returns)
        if downside_std == 0:
            return 0.0
        
        sortino = (avg_return - risk_free_rate) / downside_std
        sortino_annualized = sortino * np.sqrt(250)
        
        return sortino_annualized
    
    def _calculate_cagr(self, initial: float, final: float, days: int) -> float:
        """Calcola Compound Annual Growth Rate"""
        if initial <= 0 or final <= 0 or days <= 0:
            return 0.0
        
        years = days / 365.25
        cagr = ((final / initial) ** (1 / years) - 1) * 100
        
        return cagr
    
    def _calculate_fitness(
        self,
        cagr: float,
        sharpe_ratio: float,
        max_drawdown_pct: float,
        total_trades: int,
        win_rate: float,
    ) -> float:
        """
        Formula fitness combinata
        
        Fitness = (CAGR × w1) + (Sharpe × w2) - (MaxDD × w3) + bonuses - penalties
        
        Args:
            cagr: Compound Annual Growth Rate
            sharpe_ratio: Sharpe Ratio
            max_drawdown_pct: Maximum Drawdown in %
            total_trades: Numero totale trade
            win_rate: Win rate
            
        Returns:
            Fitness score (più alto = migliore)
        """
        # Base fitness
        fitness = (
            cagr * self.cagr_weight +
            sharpe_ratio * self.sharpe_weight -
            max_drawdown_pct * self.drawdown_penalty
        )
        
        # Penalty per troppo pochi trade
        if total_trades < self.min_trades_threshold:
            penalty = (self.min_trades_threshold - total_trades) * 0.5
            fitness -= penalty
        
        # Penalty per win rate troppo bassa (< 40%)
        if win_rate < 0.40:
            fitness -= (0.40 - win_rate) * 10
        
        # Bonus per win rate alta (> 60%)
        if win_rate > 0.60:
            fitness += (win_rate - 0.60) * 5
        
        # Penalty per drawdown eccessivo (> 30%)
        if max_drawdown_pct > 30.0:
            fitness -= (max_drawdown_pct - 30.0) * 0.5
        
        return max(0.0, fitness)  # Non negative
    
    def _create_zero_metrics(self) -> PerformanceMetrics:
        """Crea metriche zero per caso senza trade"""
        return PerformanceMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl_usd=0.0,
            total_pnl_pct=0.0,
            avg_win_usd=0.0,
            avg_loss_usd=0.0,
            avg_roe=0.0,
            max_drawdown_pct=0.0,
            max_drawdown_usd=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            profit_factor=0.0,
            cagr=0.0,
            total_return_pct=0.0,
            avg_risk_reward=0.0,
            sl_hit_rate=0.0,
            tp_hit_rate=0.0,
            avg_trade_duration_hours=0.0,
            fitness_score=0.0,
        )
    
    def compare_metrics(self, metrics1: PerformanceMetrics, metrics2: PerformanceMetrics) -> str:
        """
        Confronta due set di metriche e restituisce summary
        
        Args:
            metrics1: Prima metrica (es. baseline)
            metrics2: Seconda metrica (es. ottimizzata)
            
        Returns:
            String con confronto formattato
        """
        def delta(val1, val2, is_pct=False):
            diff = val2 - val1
            sign = "+" if diff > 0 else ""
            if is_pct:
                return f"{sign}{diff:.2f}pp"
            else:
                return f"{sign}{diff:.2f}"
        
        comparison = f"""
=== CONFRONTO PERFORMANCE ===

Fitness Score:    {metrics1.fitness_score:.2f} → {metrics2.fitness_score:.2f} ({delta(metrics1.fitness_score, metrics2.fitness_score)})

Trade Metrics:
  Total Trades:   {metrics1.total_trades} → {metrics2.total_trades}
  Win Rate:       {metrics1.win_rate:.1%} → {metrics2.win_rate:.1%} ({delta(metrics1.win_rate, metrics2.win_rate, True)})
  
Returns:
  CAGR:           {metrics1.cagr:.2f}% → {metrics2.cagr:.2f}% ({delta(metrics1.cagr, metrics2.cagr)})
  Total Return:   {metrics1.total_return_pct:.2f}% → {metrics2.total_return_pct:.2f}% ({delta(metrics1.total_return_pct, metrics2.total_return_pct)})
  
Risk:
  Max Drawdown:   {metrics1.max_drawdown_pct:.2f}% → {metrics2.max_drawdown_pct:.2f}% ({delta(metrics1.max_drawdown_pct, metrics2.max_drawdown_pct)})
  Sharpe Ratio:   {metrics1.sharpe_ratio:.2f} → {metrics2.sharpe_ratio:.2f} ({delta(metrics1.sharpe_ratio, metrics2.sharpe_ratio)})
  
Quality:
  Avg R/R:        {metrics1.avg_risk_reward:.2f} → {metrics2.avg_risk_reward:.2f} ({delta(metrics1.avg_risk_reward, metrics2.avg_risk_reward)})
  SL Hit Rate:    {metrics1.sl_hit_rate:.1%} → {metrics2.sl_hit_rate:.1%} ({delta(metrics1.sl_hit_rate, metrics2.sl_hit_rate, True)})
"""
        return comparison


if __name__ == "__main__":
    # Test del modulo
    print("=== Test FitnessEvaluator ===\n")
    
    # Mock trades for testing
    mock_trades = [
        TradeResult(
            symbol="BTC/USDT:USDT",
            entry_time="2024-01-01 10:00",
            exit_time="2024-01-01 14:00",
            direction="LONG",
            entry_price=40000,
            exit_price=41000,
            position_size=0.01,
            leverage=5,
            margin_used=80,
            pnl_usd=10,
            pnl_pct=12.5,
            roe_pct=12.5,
            exit_reason="TP",
            confidence=0.75,
            volatility=0.05,
        ),
        TradeResult(
            symbol="ETH/USDT:USDT",
            entry_time="2024-01-02 10:00",
            exit_time="2024-01-02 12:00",
            direction="SHORT",
            entry_price=2500,
            exit_price=2450,
            position_size=0.1,
            leverage=5,
            margin_used=50,
            pnl_usd=5,
            pnl_pct=10.0,
            roe_pct=10.0,
            exit_reason="TP",
            confidence=0.70,
            volatility=0.04,
        ),
        TradeResult(
            symbol="SOL/USDT:USDT",
            entry_time="2024-01-03 10:00",
            exit_time="2024-01-03 11:00",
            direction="LONG",
            entry_price=100,
            exit_price=95,
            position_size=0.5,
            leverage=5,
            margin_used=10,
            pnl_usd=-2.5,
            pnl_pct=-25.0,
            roe_pct=-25.0,
            exit_reason="SL",
            confidence=0.65,
            volatility=0.08,
        ),
    ]
    
    # Create evaluator
    evaluator = FitnessEvaluator(initial_capital=1000.0)
    
    # Evaluate
    metrics = evaluator.evaluate(mock_trades, duration_days=90)
    
    print("Performance Metrics:")
    print(f"Total Trades: {metrics.total_trades}")
    print(f"Win Rate: {metrics.win_rate:.1%}")
    print(f"Total P&L: ${metrics.total_pnl_usd:.2f} ({metrics.total_pnl_pct:.2f}%)")
    print(f"CAGR: {metrics.cagr:.2f}%")
    print(f"Max Drawdown: {metrics.max_drawdown_pct:.2f}%")
    print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    print(f"Profit Factor: {metrics.profit_factor:.2f}")
    print(f"\n🎯 FITNESS SCORE: {metrics.fitness_score:.2f}")
