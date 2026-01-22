"""
🎯 Optuna Label Optimizer

Ottimizza i parametri del Trailing Stop Labeler usando Optuna.
Obiettivi disponibili: Win Rate, Sharpe, Profit Factor, Expected Value, etc.
"""

import optuna
from optuna.trial import Trial
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import logging
import time

# Import del labeler
try:
    from ai.core.labels import TrailingStopLabeler, TrailingLabelConfig
    LABELER_AVAILABLE = True
except ImportError:
    LABELER_AVAILABLE = False

logger = logging.getLogger(__name__)


class OptimizationObjective(Enum):
    """Obiettivi di ottimizzazione disponibili"""
    WIN_RATE = "win_rate"
    SHARPE_RATIO = "sharpe_ratio"
    PROFIT_FACTOR = "profit_factor"
    EXPECTED_VALUE = "expected_value"
    TOTAL_RETURN = "total_return"
    COMBO_WR_PF = "combo_wr_pf"


@dataclass
class OptimizationResult:
    """Risultato dell'ottimizzazione Optuna"""
    best_params: Dict
    best_value: float
    study: optuna.Study
    optimization_history: List[Dict]
    param_importances: Optional[Dict] = None
    elapsed_time: float = 0.0
    n_trials: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# PARAMETRI DI RICERCA OPTUNA
# ═══════════════════════════════════════════════════════════════════════════════

PARAM_SEARCH_SPACE = {
    # Trailing Stop (diverso per timeframe)
    "trailing_stop_pct_15m": {"low": 0.005, "high": 0.03, "step": 0.001},  # 0.5% - 3.0%
    "trailing_stop_pct_1h": {"low": 0.01, "high": 0.05, "step": 0.001},    # 1.0% - 5.0%
    
    # Max bars (diverso per timeframe)
    "max_bars_15m": {"low": 12, "high": 96, "step": 6},
    "max_bars_1h": {"low": 6, "high": 48, "step": 6},
    
    # Time penalty (log scale)
    "time_penalty_lambda": {"low": 0.0001, "high": 0.01, "log": True},
    
    # Trading cost
    "trading_cost": {"low": 0.0005, "high": 0.003, "step": 0.0005},
}


def _calculate_objective(
    labels_df: pd.DataFrame,
    timeframe: str,
    objective: OptimizationObjective
) -> float:
    """
    Calcola il valore dell'obiettivo per un set di labels.
    
    Args:
        labels_df: DataFrame con le labels generate
        timeframe: '15m' o '1h'
        objective: Tipo di obiettivo da calcolare
    
    Returns:
        Valore dell'obiettivo (maggiore è meglio)
    """
    tf = timeframe
    
    # Filtra solo righe valide
    exit_col = f'exit_type_long_{tf}'
    if exit_col not in labels_df.columns:
        return float('-inf')
    
    valid_mask = labels_df[exit_col] != 'invalid'
    valid_labels = labels_df[valid_mask]
    
    if len(valid_labels) < 100:  # Minimo 100 labels per valutazione significativa
        return float('-inf')
    
    # Estrai score e return
    score_long = valid_labels[f'score_long_{tf}'].values
    score_short = valid_labels[f'score_short_{tf}'].values
    return_long = valid_labels[f'realized_return_long_{tf}'].values
    return_short = valid_labels[f'realized_return_short_{tf}'].values
    
    # Combina LONG e SHORT per valutazione complessiva
    all_scores = np.concatenate([score_long, score_short])
    all_returns = np.concatenate([return_long, return_short])
    
    # Filtra NaN
    valid_mask = ~np.isnan(all_scores) & ~np.isnan(all_returns)
    all_scores = all_scores[valid_mask]
    all_returns = all_returns[valid_mask]
    
    if len(all_scores) == 0:
        return float('-inf')
    
    # Calcola l'obiettivo richiesto
    if objective == OptimizationObjective.WIN_RATE:
        # Percentuale di score positivi
        win_rate = np.sum(all_scores > 0) / len(all_scores)
        return win_rate
    
    elif objective == OptimizationObjective.SHARPE_RATIO:
        # Sharpe = mean / std (annualizzato non necessario per confronto)
        if np.std(all_returns) < 1e-8:
            return 0.0
        sharpe = np.mean(all_returns) / np.std(all_returns)
        return sharpe
    
    elif objective == OptimizationObjective.PROFIT_FACTOR:
        # Profit Factor = somma profitti / |somma perdite|
        profits = all_returns[all_returns > 0].sum()
        losses = abs(all_returns[all_returns < 0].sum())
        if losses < 1e-8:
            return 10.0 if profits > 0 else 0.0  # Cap at 10
        pf = profits / losses
        return min(pf, 10.0)  # Cap per evitare valori estremi
    
    elif objective == OptimizationObjective.EXPECTED_VALUE:
        # EV = (win_rate * avg_win) - (loss_rate * avg_loss)
        wins = all_returns[all_returns > 0]
        losses = all_returns[all_returns < 0]
        
        if len(wins) == 0 or len(losses) == 0:
            return np.mean(all_returns)
        
        win_rate = len(wins) / len(all_returns)
        loss_rate = 1 - win_rate
        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))
        
        ev = (win_rate * avg_win) - (loss_rate * avg_loss)
        return ev
    
    elif objective == OptimizationObjective.TOTAL_RETURN:
        # Somma dei rendimenti
        return np.sum(all_returns)
    
    elif objective == OptimizationObjective.COMBO_WR_PF:
        # Win Rate * Profit Factor
        win_rate = np.sum(all_scores > 0) / len(all_scores)
        
        profits = all_returns[all_returns > 0].sum()
        losses = abs(all_returns[all_returns < 0].sum())
        pf = profits / losses if losses > 1e-8 else 1.0
        pf = min(pf, 10.0)
        
        return win_rate * pf
    
    else:
        return float('-inf')


class LabelOptimizer:
    """
    Ottimizzatore Optuna per i parametri del labeling.
    """
    
    def __init__(
        self,
        ohlcv_df: pd.DataFrame,
        timeframe: str = '15m',
        objective: OptimizationObjective = OptimizationObjective.WIN_RATE,
        n_trials: int = 50,
        timeout: Optional[int] = 300,  # 5 minuti default
        progress_callback: Optional[Callable] = None
    ):
        """
        Inizializza l'ottimizzatore.
        
        Args:
            ohlcv_df: DataFrame con dati OHLCV
            timeframe: '15m' o '1h'
            objective: Obiettivo di ottimizzazione
            n_trials: Numero massimo di trial Optuna
            timeout: Timeout in secondi (None = no timeout)
            progress_callback: Callback per aggiornare il progresso
        """
        self.ohlcv_df = ohlcv_df
        self.timeframe = timeframe
        self.objective = objective
        self.n_trials = n_trials
        self.timeout = timeout
        self.progress_callback = progress_callback
        
        # Contatori per progress
        self._trial_count = 0
        self._best_value = float('-inf')
    
    def _create_objective_function(self) -> Callable[[Trial], float]:
        """Crea la funzione obiettivo per Optuna"""
        
        def objective_fn(trial: Trial) -> float:
            # Suggerisci parametri
            params = self._suggest_params(trial)
            
            # Crea config
            config = TrailingLabelConfig(
                trailing_stop_pct_15m=params['trailing_stop_pct_15m'],
                trailing_stop_pct_1h=params['trailing_stop_pct_1h'],
                max_bars_15m=params['max_bars_15m'],
                max_bars_1h=params['max_bars_1h'],
                time_penalty_lambda=params['time_penalty_lambda'],
                trading_cost=params['trading_cost']
            )
            
            # Genera labels
            labeler = TrailingStopLabeler(config)
            labels_df = labeler.generate_labels_for_timeframe(
                self.ohlcv_df, 
                self.timeframe
            )
            
            # Calcola obiettivo
            value = _calculate_objective(labels_df, self.timeframe, self.objective)
            
            # Aggiorna contatori
            self._trial_count += 1
            if value > self._best_value:
                self._best_value = value
            
            # Callback progress
            if self.progress_callback:
                self.progress_callback(
                    trial_num=self._trial_count,
                    total_trials=self.n_trials,
                    current_value=value,
                    best_value=self._best_value,
                    params=params
                )
            
            return value
        
        return objective_fn
    
    def _suggest_params(self, trial: Trial) -> Dict:
        """Suggerisci parametri per un trial"""
        params = {}
        
        for param_name, space in PARAM_SEARCH_SPACE.items():
            if 'log' in space and space['log']:
                params[param_name] = trial.suggest_float(
                    param_name,
                    space['low'],
                    space['high'],
                    log=True
                )
            elif 'step' in space:
                if isinstance(space['low'], float):
                    params[param_name] = trial.suggest_float(
                        param_name,
                        space['low'],
                        space['high'],
                        step=space['step']
                    )
                else:
                    params[param_name] = trial.suggest_int(
                        param_name,
                        space['low'],
                        space['high'],
                        step=space['step']
                    )
            else:
                params[param_name] = trial.suggest_float(
                    param_name,
                    space['low'],
                    space['high']
                )
        
        return params
    
    def optimize(self) -> OptimizationResult:
        """
        Esegui l'ottimizzazione Optuna.
        
        Returns:
            OptimizationResult con best params, study, e statistiche
        """
        if not LABELER_AVAILABLE:
            raise ImportError("TrailingStopLabeler not available")
        
        start_time = time.time()
        
        # Reset contatori
        self._trial_count = 0
        self._best_value = float('-inf')
        
        # Crea lo studio Optuna
        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=42),
            study_name=f"label_optimization_{self.timeframe}"
        )
        
        # Ottimizza
        objective_fn = self._create_objective_function()
        
        study.optimize(
            objective_fn,
            n_trials=self.n_trials,
            timeout=self.timeout,
            show_progress_bar=False,  # Usiamo il nostro progress callback
            catch=(Exception,)  # Cattura eccezioni per non fermare l'ottimizzazione
        )
        
        elapsed_time = time.time() - start_time
        
        # Estrai risultati
        best_params = study.best_params
        best_value = study.best_value
        
        # Calcola importanza parametri
        try:
            param_importances = optuna.importance.get_param_importances(study)
        except Exception:
            param_importances = None
        
        # Costruisci history
        optimization_history = []
        for trial in study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETE:
                optimization_history.append({
                    'trial': trial.number,
                    'value': trial.value,
                    'params': trial.params
                })
        
        return OptimizationResult(
            best_params=best_params,
            best_value=best_value,
            study=study,
            optimization_history=optimization_history,
            param_importances=param_importances,
            elapsed_time=elapsed_time,
            n_trials=len(study.trials)
        )


def optimize_labels_with_optuna(
    ohlcv_df: pd.DataFrame,
    timeframe: str = '15m',
    objective: str = 'win_rate',
    n_trials: int = 50,
    timeout: int = 300,
    progress_callback: Optional[Callable] = None
) -> OptimizationResult:
    """
    Funzione di convenienza per ottimizzare i parametri delle labels.
    
    Args:
        ohlcv_df: DataFrame OHLCV
        timeframe: '15m' o '1h'
        objective: 'win_rate', 'sharpe_ratio', 'profit_factor', 
                   'expected_value', 'total_return', 'combo_wr_pf'
        n_trials: Numero di trials
        timeout: Timeout in secondi
        progress_callback: Callback per progress updates
    
    Returns:
        OptimizationResult
    """
    # Converti stringa a enum
    obj_enum = OptimizationObjective(objective)
    
    optimizer = LabelOptimizer(
        ohlcv_df=ohlcv_df,
        timeframe=timeframe,
        objective=obj_enum,
        n_trials=n_trials,
        timeout=timeout,
        progress_callback=progress_callback
    )
    
    return optimizer.optimize()


def get_default_params(timeframe: str = '15m') -> Dict:
    """Restituisce i parametri default per un timeframe"""
    if timeframe == '15m':
        return {
            'trailing_stop_pct_15m': 0.015,
            'trailing_stop_pct_1h': 0.025,
            'max_bars_15m': 48,
            'max_bars_1h': 24,
            'time_penalty_lambda': 0.001,
            'trading_cost': 0.001
        }
    else:
        return {
            'trailing_stop_pct_15m': 0.015,
            'trailing_stop_pct_1h': 0.025,
            'max_bars_15m': 48,
            'max_bars_1h': 24,
            'time_penalty_lambda': 0.001,
            'trading_cost': 0.001
        }


# Esporta
__all__ = [
    'LabelOptimizer',
    'OptimizationObjective',
    'OptimizationResult',
    'optimize_labels_with_optuna',
    'get_default_params',
    'PARAM_SEARCH_SPACE'
]
