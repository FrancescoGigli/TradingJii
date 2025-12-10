"""
Strategy Optimizer Module - BLOCCO 3

Questo modulo implementa l'Algoritmo Genetico (GA) per ottimizzare i parametri
della strategia di trading basandosi su dati storici.

Componenti:
- strategy_params.py: Cromosoma (StrategyParams)
- backtest_simulator.py: Simulazione trade su storico
- fitness_evaluator.py: Calcolo metriche (CAGR, Sharpe, MaxDD)
- genetic_algorithm.py: GA engine (DEAP library)
- ga_orchestrator.py: Orchestratore del processo di ottimizzazione
"""

__version__ = "1.0.0"
