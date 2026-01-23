"""
📈 Ranking Metrics

Metrics for evaluating trading model performance.
"""

import numpy as np
from scipy.stats import spearmanr


def temporal_split(X, y, timestamps, train_ratio=0.8):
    """Split data temporally (NO shuffle!)."""
    split_idx = int(len(X) * train_ratio)
    return (
        X.iloc[:split_idx], X.iloc[split_idx:],
        y.iloc[:split_idx], y.iloc[split_idx:],
        timestamps.iloc[:split_idx], timestamps.iloc[split_idx:]
    )


def calculate_ranking_metrics(y_true: np.ndarray, y_pred: np.ndarray, realized_returns: np.ndarray = None) -> dict:
    """
    Calculate ranking metrics for trading.
    
    Returns dict with:
    - spearman_corr: Rank correlation
    - topK metrics: Performance of top predictions
    """
    spearman_corr, spearman_pval = spearmanr(y_pred, y_true)
    
    precision_metrics = {}
    for k_pct in [1, 5, 10, 20]:
        k = max(1, int(len(y_pred) * k_pct / 100))
        top_k_idx = np.argsort(y_pred)[-k:]
        top_k_true = y_true.iloc[top_k_idx] if hasattr(y_true, 'iloc') else y_true[top_k_idx]
        
        precision_metrics[f'top{k_pct}pct_avg_score'] = np.mean(top_k_true)
        precision_metrics[f'top{k_pct}pct_positive'] = (top_k_true > 0).mean() * 100
        
        if realized_returns is not None:
            top_k_ret = realized_returns.iloc[top_k_idx] if hasattr(realized_returns, 'iloc') else realized_returns[top_k_idx]
            precision_metrics[f'top{k_pct}pct_avg_return'] = np.mean(top_k_ret) * 100
    
    return {'spearman_corr': spearman_corr, 'spearman_pval': spearman_pval, **precision_metrics}


def print_ranking_metrics(metrics: dict, model_name: str):
    """Print ranking metrics nicely."""
    print(f"\n   🎯 RANKING METRICS ({model_name}):")
    print(f"   ╔══════════════════════════════════════════════════╗")
    print(f"   ║  Spearman Correlation: {metrics['spearman_corr']:>8.4f}  (p={metrics['spearman_pval']:.2e})")
    
    quality = "🟢 EXCELLENT" if metrics['spearman_corr'] > 0.10 else \
              "🟡 GOOD" if metrics['spearman_corr'] > 0.05 else \
              "🟠 WEAK" if metrics['spearman_corr'] > 0.02 else "🔴 NO SIGNAL"
    
    print(f"   ║  Signal Quality:       {quality}")
    print(f"   ╠══════════════════════════════════════════════════╣")
    print(f"   ║  Precision@K:")
    print(f"   ║  ┌────────┬────────────┬──────────────┐")
    print(f"   ║  │ Top K% │ Avg Score  │ % Positive   │")
    print(f"   ║  ├────────┼────────────┼──────────────┤")
    
    for k_pct in [1, 5, 10, 20]:
        avg = metrics.get(f'top{k_pct}pct_avg_score', 0)
        pos = metrics.get(f'top{k_pct}pct_positive', 0)
        print(f"   ║  │  {k_pct:>3}% │ {avg:>10.6f} │ {pos:>10.1f}%  │")
    
    print(f"   ║  └────────┴────────────┴──────────────┘")
    print(f"   ╚══════════════════════════════════════════════════╝")
