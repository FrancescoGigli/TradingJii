"""
GA Orchestrator - Regista del processo di ottimizzazione

Coordina l'intero flusso di ottimizzazione tramite Algoritmo Genetico:
1. Carica dati storici e modelli XGBoost
2. Configura GA engine
3. Esegue ottimizzazione
4. Salva best StrategyParams
5. Genera report comparativo

BLOCCO 3: Strategy Optimizer
"""

from __future__ import annotations
from typing import Tuple, Dict, Any
from pathlib import Path
import logging
import json
from datetime import datetime

from strategy_optimizer.strategy_params import StrategyParams
from strategy_optimizer.genetic_algorithm import GeneticAlgorithmEngine
from strategy_optimizer.backtest_simulator import BacktestSimulator
from strategy_optimizer.fitness_evaluator import FitnessEvaluator, PerformanceMetrics

_LOG = logging.getLogger(__name__)


class GAOrchestrator:
    """
    Orchestratore completo del processo di ottimizzazione GA
    
    Responsabilità:
    - Setup hyperparametri GA
    - Caricamento dati e modelli
    - Esecuzione ottimizzazione
    - Salvataggio risultati
    - Confronto con baseline
    """
    
    def __init__(
        self,
        initial_capital: float = 1000.0,
        duration_days: int = 90,
        output_dir: str = "ga_results",
    ):
        """
        Args:
            initial_capital: Capitale iniziale per backtest
            duration_days: Durata periodo test (per CAGR)
            output_dir: Directory per salvare risultati
        """
        self.initial_capital = initial_capital
        self.duration_days = duration_days
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Results tracking
        self.baseline_params = None
        self.baseline_metrics = None
        self.optimized_params = None
        self.optimized_metrics = None
        
        _LOG.info(f"🎯 GAOrchestrator initialized:")
        _LOG.info(f"   Capital: ${initial_capital:.2f}")
        _LOG.info(f"   Duration: {duration_days} days")
        _LOG.info(f"   Output: {output_dir}")
    
    def run_optimization(
        self,
        model,
        scaler,
        X_test,
        df_test,
        population_size: int = 30,
        n_generations: int = 20,
        save_results: bool = True,
        compare_with_baseline: bool = True,
    ) -> Tuple[StrategyParams, PerformanceMetrics]:
        """
        Esegue ottimizzazione GA completa
        
        Args:
            model: Modello XGBoost trained
            scaler: Scaler fitted
            X_test: Features test
            df_test: DataFrame test
            population_size: Dimensione popolazione GA
            n_generations: Numero generazioni GA
            save_results: Salva risultati su file
            compare_with_baseline: Confronta con parametri attuali
            
        Returns:
            (best_params, best_metrics)
        """
        _LOG.info("="*80)
        _LOG.info("🧬 STARTING GENETIC ALGORITHM OPTIMIZATION")
        _LOG.info("="*80)
        
        # STEP 1: Baseline (parametri attuali)
        if compare_with_baseline:
            _LOG.info("\n📊 STEP 1: Evaluating baseline (current parameters)...")
            self.baseline_params = StrategyParams.from_config()
            self.baseline_metrics = self._evaluate_params(
                self.baseline_params, model, scaler, X_test, df_test
            )
            _LOG.info(f"   Baseline fitness: {self.baseline_metrics.fitness_score:.2f}")
        
        # STEP 2: GA Optimization
        _LOG.info("\n🧬 STEP 2: Running Genetic Algorithm...")
        self.optimized_params, self.optimized_metrics = self._run_ga(
            model, scaler, X_test, df_test, population_size, n_generations
        )
        _LOG.info(f"   Optimized fitness: {self.optimized_metrics.fitness_score:.2f}")
        
        # STEP 3: Comparison
        if compare_with_baseline:
            _LOG.info("\n📊 STEP 3: Comparing results...")
            improvement = self._calculate_improvement()
            self._display_comparison()
        
        # STEP 4: Save results
        if save_results:
            _LOG.info("\n💾 STEP 4: Saving results...")
            self._save_results()
        
        _LOG.info("\n" + "="*80)
        _LOG.info("✅ GA OPTIMIZATION COMPLETE")
        _LOG.info("="*80)
        
        return self.optimized_params, self.optimized_metrics
    
    def _evaluate_params(
        self,
        params: StrategyParams,
        model,
        scaler,
        X_test,
        df_test
    ) -> PerformanceMetrics:
        """Valuta un set di parametri tramite backtest"""
        simulator = BacktestSimulator(initial_capital=self.initial_capital)
        
        trades, metrics = simulator.backtest_with_signals_from_model(
            model=model,
            scaler=scaler,
            X_test=X_test,
            df_test=df_test,
            params=params,
            duration_days=self.duration_days
        )
        
        return metrics
    
    def _run_ga(
        self,
        model,
        scaler,
        X_test,
        df_test,
        population_size: int,
        n_generations: int
    ) -> Tuple[StrategyParams, PerformanceMetrics]:
        """Esegue GA e restituisce best params + metrics"""
        
        # Create fitness function
        def fitness_function(params: StrategyParams) -> float:
            """Fitness function che backtesta i parametri"""
            metrics = self._evaluate_params(params, model, scaler, X_test, df_test)
            return metrics.fitness_score
        
        # Create GA engine
        ga_engine = GeneticAlgorithmEngine(
            population_size=population_size,
            n_generations=n_generations,
            crossover_prob=0.8,
            mutation_prob=0.2,
            mutation_indpb=0.1,
            tournament_size=3,
            elite_size=2,
        )
        
        # Run optimization
        best_params, _ = ga_engine.optimize(
            fitness_function=fitness_function,
            verbose=True
        )
        
        # Evaluate best params per ottenere metrics complete
        best_metrics = self._evaluate_params(best_params, model, scaler, X_test, df_test)
        
        # Update params con fitness
        best_params.fitness_score = best_metrics.fitness_score
        best_params.generation = n_generations
        
        # Save evolution plot
        try:
            plot_path = self.output_dir / "ga_evolution.png"
            ga_engine.plot_evolution(save_path=str(plot_path))
        except Exception as e:
            _LOG.warning(f"Could not save evolution plot: {e}")
        
        return best_params, best_metrics
    
    def _calculate_improvement(self) -> Dict[str, float]:
        """Calcola miglioramento % rispetto a baseline"""
        if not self.baseline_metrics or not self.optimized_metrics:
            return {}
        
        return {
            'fitness': self._pct_change(
                self.baseline_metrics.fitness_score,
                self.optimized_metrics.fitness_score
            ),
            'cagr': self._pct_change(
                self.baseline_metrics.cagr,
                self.optimized_metrics.cagr
            ),
            'sharpe': self._pct_change(
                self.baseline_metrics.sharpe_ratio,
                self.optimized_metrics.sharpe_ratio
            ),
            'max_dd': self._pct_change(
                self.baseline_metrics.max_drawdown_pct,
                self.optimized_metrics.max_drawdown_pct,
                lower_is_better=True
            ),
            'win_rate': self._pct_change(
                self.baseline_metrics.win_rate,
                self.optimized_metrics.win_rate
            ),
        }
    
    def _pct_change(self, old: float, new: float, lower_is_better: bool = False) -> float:
        """Calcola variazione percentuale"""
        if old == 0:
            return 0.0
        
        change = ((new - old) / abs(old)) * 100
        
        if lower_is_better:
            change = -change  # Inverti per metriche negative
        
        return change
    
    def _display_comparison(self):
        """Display confronto baseline vs optimized"""
        if not self.baseline_metrics or not self.optimized_metrics:
            return
        
        evaluator = FitnessEvaluator()
        comparison_str = evaluator.compare_metrics(
            self.baseline_metrics,
            self.optimized_metrics
        )
        
        _LOG.info(comparison_str)
        
        # Additional params comparison
        _LOG.info("\n=== PARAMETER CHANGES ===\n")
        _LOG.info(f"Confidence Buy:    {self.baseline_params.min_confidence_buy:.2%} → "
                 f"{self.optimized_params.min_confidence_buy:.2%}")
        _LOG.info(f"Stop Loss:         {self.baseline_params.sl_percentage:.2%} → "
                 f"{self.optimized_params.sl_percentage:.2%}")
        _LOG.info(f"Leverage:          {self.baseline_params.leverage_base} → "
                 f"{self.optimized_params.leverage_base}")
        _LOG.info(f"Risk/Reward:       {self.baseline_params.min_risk_reward:.2f} → "
                 f"{self.optimized_params.min_risk_reward:.2f}")
    
    def _save_results(self):
        """Salva risultati su file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save optimized params
        params_file = self.output_dir / f"best_params_{timestamp}.json"
        with open(params_file, 'w') as f:
            json.dump(self.optimized_params.to_dict(), f, indent=2)
        _LOG.info(f"   Saved params: {params_file}")
        
        # Save metrics comparison
        if self.baseline_metrics and self.optimized_metrics:
            comparison_file = self.output_dir / f"comparison_{timestamp}.json"
            comparison_data = {
                'baseline': self.baseline_metrics.to_dict(),
                'optimized': self.optimized_metrics.to_dict(),
                'improvement': self._calculate_improvement(),
                'timestamp': timestamp,
            }
            with open(comparison_file, 'w') as f:
                json.dump(comparison_data, f, indent=2)
            _LOG.info(f"   Saved comparison: {comparison_file}")
        
        # Save text report
        report_file = self.output_dir / f"report_{timestamp}.txt"
        with open(report_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("GA OPTIMIZATION REPORT\n")
            f.write("="*80 + "\n\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Duration: {self.duration_days} days\n")
            f.write(f"Initial Capital: ${self.initial_capital:.2f}\n\n")
            
            if self.baseline_metrics:
                f.write("BASELINE PERFORMANCE:\n")
                f.write(f"  Fitness: {self.baseline_metrics.fitness_score:.2f}\n")
                f.write(f"  CAGR: {self.baseline_metrics.cagr:.2f}%\n")
                f.write(f"  Sharpe: {self.baseline_metrics.sharpe_ratio:.2f}\n")
                f.write(f"  Max DD: {self.baseline_metrics.max_drawdown_pct:.2f}%\n")
                f.write(f"  Win Rate: {self.baseline_metrics.win_rate:.1%}\n\n")
            
            if self.optimized_metrics:
                f.write("OPTIMIZED PERFORMANCE:\n")
                f.write(f"  Fitness: {self.optimized_metrics.fitness_score:.2f}\n")
                f.write(f"  CAGR: {self.optimized_metrics.cagr:.2f}%\n")
                f.write(f"  Sharpe: {self.optimized_metrics.sharpe_ratio:.2f}\n")
                f.write(f"  Max DD: {self.optimized_metrics.max_drawdown_pct:.2f}%\n")
                f.write(f"  Win Rate: {self.optimized_metrics.win_rate:.1%}\n\n")
            
            if self.baseline_metrics and self.optimized_metrics:
                improvement = self._calculate_improvement()
                f.write("IMPROVEMENT:\n")
                for metric, change in improvement.items():
                    f.write(f"  {metric}: {change:+.2f}%\n")
        
        _LOG.info(f"   Saved report: {report_file}")
    
    def load_best_params(self, params_file: str = None) -> StrategyParams:
        """
        Carica best params da file
        
        Args:
            params_file: Path specifico (optional). Se None, carica il più recente
            
        Returns:
            StrategyParams
        """
        if params_file is None:
            # Find most recent params file
            params_files = list(self.output_dir.glob("best_params_*.json"))
            if not params_files:
                raise FileNotFoundError(f"No params files found in {self.output_dir}")
            params_file = max(params_files, key=lambda p: p.stat().st_mtime)
        
        with open(params_file, 'r') as f:
            data = json.load(f)
        
        params = StrategyParams.from_dict(data)
        _LOG.info(f"✅ Loaded params from {params_file}")
        
        return params


def quick_optimize(
    model,
    scaler,
    X_test,
    df_test,
    population_size: int = 20,
    n_generations: int = 10,
) -> StrategyParams:
    """
    Quick GA optimization con parametri ridotti (per testing)
    
    Args:
        model: Modello XGBoost
        scaler: Scaler
        X_test: Features test
        df_test: DataFrame test
        population_size: Dimensione popolazione
        n_generations: Numero generazioni
        
    Returns:
        Best StrategyParams
    """
    orchestrator = GAOrchestrator(
        initial_capital=1000.0,
        duration_days=90
    )
    
    best_params, best_metrics = orchestrator.run_optimization(
        model=model,
        scaler=scaler,
        X_test=X_test,
        df_test=df_test,
        population_size=population_size,
        n_generations=n_generations,
        save_results=True,
        compare_with_baseline=True
    )
    
    return best_params


if __name__ == "__main__":
    # Test del modulo
    print("=== Test GAOrchestrator ===\n")
    
    print("Creating test orchestrator...")
    orchestrator = GAOrchestrator(
        initial_capital=1000.0,
        duration_days=90,
        output_dir="test_ga_results"
    )
    
    print(f"Output directory: {orchestrator.output_dir}")
    print(f"Initial capital: ${orchestrator.initial_capital:.2f}")
    
    # Test parameter loading/saving
    test_params = StrategyParams.from_config()
    test_params.fitness_score = 42.5
    
    # Save test params
    test_file = orchestrator.output_dir / "test_params.json"
    with open(test_file, 'w') as f:
        json.dump(test_params.to_dict(), f, indent=2)
    
    print(f"\nSaved test params to: {test_file}")
    
    # Load back
    loaded_params = orchestrator.load_best_params(str(test_file))
    print(f"Loaded params: {loaded_params}")
    
    print("\n✅ GAOrchestrator test complete")
    print(f"   Check {orchestrator.output_dir} for test files")
