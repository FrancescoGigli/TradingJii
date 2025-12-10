"""
Genetic Algorithm Engine - Ottimizzazione StrategyParams

Implementa l'Algoritmo Genetico usando DEAP per ottimizzare i parametri
della strategia di trading.

BLOCCO 3: Strategy Optimizer
"""

from __future__ import annotations
from typing import List, Tuple, Callable, Any
import random
import numpy as np
import logging
from dataclasses import asdict

try:
    from deap import base, creator, tools, algorithms
    DEAP_AVAILABLE = True
except ImportError:
    DEAP_AVAILABLE = False
    logging.warning("⚠️ DEAP not installed. Install with: pip install deap")

from strategy_optimizer.strategy_params import StrategyParams, create_random_params
from strategy_optimizer.backtest_simulator import BacktestSimulator
from strategy_optimizer.fitness_evaluator import PerformanceMetrics

_LOG = logging.getLogger(__name__)


class GeneticAlgorithmEngine:
    """
    Algoritmo Genetico per ottimizzazione parametri strategia
    
    Usa DEAP library per evoluzione popolazione di StrategyParams.
    Ogni individuo (cromosoma) è un set di parametri che viene valutato
    tramite backtest simulato.
    """
    
    def __init__(
        self,
        population_size: int = 50,
        n_generations: int = 30,
        crossover_prob: float = 0.8,
        mutation_prob: float = 0.2,
        mutation_indpb: float = 0.1,
        tournament_size: int = 3,
        elite_size: int = 2,
        random_seed: int = None,
    ):
        """
        Args:
            population_size: Dimensione popolazione
            n_generations: Numero generazioni
            crossover_prob: Probabilità crossover (0.8 = 80%)
            mutation_prob: Probabilità mutazione (0.2 = 20%)
            mutation_indpb: Prob. mutazione singolo gene (0.1 = 10%)
            tournament_size: Dimensione torneo per selezione (3)
            elite_size: Numero best da preservare (elitism)
            random_seed: Seed per reproducibilità
        """
        if not DEAP_AVAILABLE:
            raise ImportError("DEAP library required. Install with: pip install deap")
        
        self.population_size = population_size
        self.n_generations = n_generations
        self.crossover_prob = crossover_prob
        self.mutation_prob = mutation_prob
        self.mutation_indpb = mutation_indpb
        self.tournament_size = tournament_size
        self.elite_size = elite_size
        
        if random_seed:
            random.seed(random_seed)
            np.random.seed(random_seed)
        
        # Setup DEAP structures
        self._setup_deap()
        
        # History tracking
        self.history = {
            'best_fitness': [],
            'avg_fitness': [],
            'best_params': []
        }
        
        _LOG.info(f"🧬 GeneticAlgorithm initialized:")
        _LOG.info(f"   Population: {population_size}")
        _LOG.info(f"   Generations: {n_generations}")
        _LOG.info(f"   Crossover: {crossover_prob:.0%}")
        _LOG.info(f"   Mutation: {mutation_prob:.0%}")
    
    def _setup_deap(self):
        """Setup DEAP creator e toolbox"""
        # Cleanup previous definitions (if any)
        if hasattr(creator, "FitnessMax"):
            del creator.FitnessMax
        if hasattr(creator, "Individual"):
            del creator.Individual
        
        # Create fitness (maximize)
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        
        # Create individual (list of floats)
        creator.create("Individual", list, fitness=creator.FitnessMax)
        
        # Toolbox
        self.toolbox = base.Toolbox()
    
    def optimize(
        self,
        fitness_function: Callable[[StrategyParams], float],
        param_bounds: dict = None,
        verbose: bool = True
    ) -> Tuple[StrategyParams, PerformanceMetrics]:
        """
        Esegue ottimizzazione GA
        
        Args:
            fitness_function: Funzione che valuta un StrategyParams
                             e restituisce fitness score
            param_bounds: Bounds per parametri (optional)
            verbose: Mostra progress
            
        Returns:
            (best_params, best_metrics)
        """
        _LOG.info(f"🧬 Starting Genetic Algorithm optimization...")
        
        # Register GA operators
        self._register_operators(fitness_function, param_bounds)
        
        # Create initial population
        population = self.toolbox.population(n=self.population_size)
        
        # Evaluate initial population
        _LOG.info(f"📊 Evaluating generation 0...")
        fitnesses = list(map(self.toolbox.evaluate, population))
        for ind, fit in zip(population, fitnesses):
            ind.fitness.values = (fit,)
        
        # Evolution loop
        for gen in range(1, self.n_generations + 1):
            if verbose:
                _LOG.info(f"🧬 Generation {gen}/{self.n_generations}")
            
            # Select best for next generation
            offspring = self.toolbox.select(population, len(population) - self.elite_size)
            offspring = list(map(self.toolbox.clone, offspring))
            
            # Apply crossover
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < self.crossover_prob:
                    self.toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values
            
            # Apply mutation
            for mutant in offspring:
                if random.random() < self.mutation_prob:
                    self.toolbox.mutate(mutant)
                    del mutant.fitness.values
            
            # Evaluate individuals with invalid fitness
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = list(map(self.toolbox.evaluate, invalid_ind))
            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = (fit,)
            
            # Elitism: keep best from previous generation
            elite = tools.selBest(population, self.elite_size)
            
            # Replace population
            population[:] = elite + offspring
            
            # Track stats
            fits = [ind.fitness.values[0] for ind in population]
            best_fit = max(fits)
            avg_fit = np.mean(fits)
            
            self.history['best_fitness'].append(best_fit)
            self.history['avg_fitness'].append(avg_fit)
            
            if verbose:
                _LOG.info(f"   Best fitness: {best_fit:.2f} | Avg: {avg_fit:.2f}")
        
        # Get best individual
        best_ind = tools.selBest(population, 1)[0]
        best_params = self._individual_to_params(best_ind)
        
        _LOG.info(f"✅ GA optimization complete!")
        _LOG.info(f"   Best fitness: {best_ind.fitness.values[0]:.2f}")
        
        return best_params, None  # Metrics calcolate esternamente
    
    def _register_operators(self, fitness_function: Callable, param_bounds: dict = None):
        """Registra operatori GA nel toolbox"""
        # Individual creation
        self.toolbox.register(
            "individual",
            self._create_individual,
            param_bounds=param_bounds
        )
        
        # Population creation
        self.toolbox.register(
            "population",
            tools.initRepeat,
            list,
            self.toolbox.individual
        )
        
        # Evaluation
        self.toolbox.register("evaluate", self._evaluate_wrapper, fitness_func=fitness_function)
        
        # Selection: Tournament
        self.toolbox.register("select", tools.selTournament, tournsize=self.tournament_size)
        
        # Crossover: Uniform
        self.toolbox.register("mate", tools.cxUniform, indpb=0.5)
        
        # Mutation: Gaussian with bounds
        self.toolbox.register(
            "mutate",
            self._mutate_gaussian_bounded,
            mu=0,
            sigma=0.1,
            indpb=self.mutation_indpb,
            param_bounds=param_bounds
        )
        
        # Clone
        self.toolbox.register("clone", self._clone_individual)
    
    def _create_individual(self, param_bounds: dict = None) -> creator.Individual:
        """Crea individuo casuale"""
        # Crea StrategyParams casuale
        params = create_random_params(generation=0, bounds=param_bounds)
        
        # Converti in lista (chromosome) per DEAP
        chromosome = self._params_to_chromosome(params)
        
        return creator.Individual(chromosome)
    
    def _params_to_chromosome(self, params: StrategyParams) -> List[float]:
        """Converte StrategyParams in chromosome (lista di float)"""
        return [
            params.min_confidence_buy,
            params.min_confidence_sell,
            params.min_ret_exp,
            params.max_p_sl,
            params.weight_15m,
            params.weight_30m,
            params.weight_1h,
            params.sl_percentage,
            params.tp_atr_multiplier,
            params.min_risk_reward,
            float(params.leverage_base),
            params.max_volatility,
            params.risk_per_trade_pct,
        ]
    
    def _chromosome_to_params(self, chromosome: List[float]) -> StrategyParams:
        """Converte chromosome in StrategyParams"""
        return StrategyParams(
            min_confidence_buy=chromosome[0],
            min_confidence_sell=chromosome[1],
            min_ret_exp=chromosome[2],
            max_p_sl=chromosome[3],
            weight_15m=chromosome[4],
            weight_30m=chromosome[5],
            weight_1h=chromosome[6],
            sl_percentage=chromosome[7],
            tp_atr_multiplier=chromosome[8],
            min_risk_reward=chromosome[9],
            leverage_base=int(chromosome[10]),
            max_volatility=chromosome[11],
            risk_per_trade_pct=chromosome[12],
            # Altri parametri usano defaults
        )
    
    def _individual_to_params(self, individual: creator.Individual) -> StrategyParams:
        """Wrapper per convertire Individual DEAP in StrategyParams"""
        return self._chromosome_to_params(list(individual))
    
    def _evaluate_wrapper(self, individual: creator.Individual, fitness_func: Callable) -> float:
        """Wrapper per valutazione (converte individual → params → fitness)"""
        try:
            params = self._individual_to_params(individual)
            fitness = fitness_func(params)
            return fitness  # DEAP si aspetta un float, non una tupla
        except Exception as e:
            _LOG.warning(f"Evaluation failed: {e}")
            return 0.0  # Fitness pessima per individui invalidi
    
    def _mutate_gaussian_bounded(
        self,
        individual: creator.Individual,
        mu: float,
        sigma: float,
        indpb: float,
        param_bounds: dict = None
    ) -> Tuple[creator.Individual]:
        """
        Mutazione Gaussiana con bounds
        
        Args:
            individual: Individuo da mutare
            mu: Media gaussiana (0 = nessun bias)
            sigma: Deviazione standard (0.1 = 10% variazione)
            indpb: Probabilità mutazione per gene
            param_bounds: Bounds per ogni parametro
            
        Returns:
            Individuo mutato (tuple per DEAP)
        """
        # Default bounds (se non specificati)
        default_bounds = {
            0: (0.55, 0.80),   # min_confidence_buy
            1: (0.55, 0.80),   # min_confidence_sell
            2: (0.01, 0.05),   # min_ret_exp
            3: (0.20, 0.40),   # max_p_sl
            4: (0.8, 1.2),     # weight_15m
            5: (1.0, 1.5),     # weight_30m
            6: (1.2, 2.0),     # weight_1h
            7: (0.04, 0.10),   # sl_percentage
            8: (3.0, 8.0),     # tp_atr_multiplier
            9: (1.5, 4.0),     # min_risk_reward
            10: (3, 10),       # leverage_base
            11: (0.05, 0.12),  # max_volatility
            12: (0.01, 0.05),  # risk_per_trade_pct
        }
        
        bounds = param_bounds or default_bounds
        
        for i in range(len(individual)):
            if random.random() < indpb:
                # Applica mutazione gaussiana
                individual[i] += random.gauss(mu, sigma) * individual[i]
                
                # Clamp ai bounds
                if i in bounds:
                    min_val, max_val = bounds[i]
                    individual[i] = max(min_val, min(max_val, individual[i]))
        
        return (individual,)
    
    def _clone_individual(self, individual: creator.Individual) -> creator.Individual:
        """Clone deep di individuo"""
        return creator.Individual(list(individual))
    
    def get_history(self) -> dict:
        """Restituisce history dell'ottimizzazione"""
        return self.history
    
    def plot_evolution(self, save_path: str = None):
        """
        Plot evoluzione fitness (opzionale - richiede matplotlib)
        
        Args:
            save_path: Path per salvare immagine (optional)
        """
        try:
            import matplotlib.pyplot as plt
            
            generations = range(len(self.history['best_fitness']))
            
            plt.figure(figsize=(10, 6))
            plt.plot(generations, self.history['best_fitness'], 'b-', label='Best Fitness', linewidth=2)
            plt.plot(generations, self.history['avg_fitness'], 'r--', label='Avg Fitness', linewidth=1.5)
            plt.xlabel('Generation')
            plt.ylabel('Fitness Score')
            plt.title('Genetic Algorithm Evolution')
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            if save_path:
                plt.savefig(save_path, dpi=150, bbox_inches='tight')
                _LOG.info(f"📊 Evolution plot saved to {save_path}")
            else:
                plt.show()
            
            plt.close()
            
        except ImportError:
            _LOG.warning("⚠️ matplotlib not installed - cannot plot evolution")


def simple_ga_optimization(
    backtest_func: Callable[[StrategyParams], float],
    population_size: int = 30,
    n_generations: int = 20,
    verbose: bool = True
) -> StrategyParams:
    """
    Funzione utility per ottimizzazione GA semplificata
    
    Args:
        backtest_func: Funzione che prende StrategyParams e restituisce fitness
        population_size: Dimensione popolazione
        n_generations: Numero generazioni
        verbose: Mostra progress
        
    Returns:
        Best StrategyParams trovati
    """
    ga = GeneticAlgorithmEngine(
        population_size=population_size,
        n_generations=n_generations,
        crossover_prob=0.8,
        mutation_prob=0.2,
    )
    
    best_params, _ = ga.optimize(
        fitness_function=backtest_func,
        verbose=verbose
    )
    
    return best_params


if __name__ == "__main__":
    # Test del modulo
    print("=== Test GeneticAlgorithmEngine ===\n")
    
    if not DEAP_AVAILABLE:
        print("❌ DEAP not installed. Install with: pip install deap")
        exit(1)
    
    # Mock fitness function
    def mock_fitness(params: StrategyParams) -> float:
        """Mock fitness - premia alta confidenza e basso SL"""
        return (
            params.min_confidence_buy * 100 +
            (0.10 - params.sl_percentage) * 50 +
            params.min_risk_reward * 10
        )
    
    # Test GA
    print("Testing GA with mock fitness function...")
    ga = GeneticAlgorithmEngine(
        population_size=10,
        n_generations=5,
    )
    
    best_params, _ = ga.optimize(
        fitness_function=mock_fitness,
        verbose=True
    )
    
    print(f"\n✅ Best parameters found:")
    print(f"   Confidence: {best_params.min_confidence_buy:.2%}")
    print(f"   SL: {best_params.sl_percentage:.2%}")
    print(f"   R/R: {best_params.min_risk_reward:.2f}")
    
    print("\n✅ GeneticAlgorithmEngine test complete")
