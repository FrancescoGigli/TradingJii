"""agents.frontend.services.xgb_normalization

Purpose
-------
Provide a single, shared normalization strategy for XGBoost predictions.

This repository previously had multiple normalization approaches:
- Z-score based mapping for single-row inference (MLInferenceService.predict)
- Percentile ranking for batch backtest charts
- A dedicated percentile + short-orientation heuristic in local BTC inference

This module standardizes the behavior everywhere:
- LONG and SHORT are normalized independently to a stable 0..100 scale using
  percentile ranking within the selected window.
- SHORT scores can be automatically inverted when the raw model outputs are
  mostly negative (best short entries = more negative values).
- A net score is computed for easy comparison with technical signals:
  net = long_0_100 - short_0_100  => range [-100, +100]

Inputs / Outputs
----------------
Inputs:
- raw_long: numpy array of raw LONG model outputs
- raw_short: numpy array of raw SHORT model outputs

Outputs:
- long_0_100: numpy array of normalized LONG scores in [0, 100]
- short_0_100: numpy array of normalized SHORT scores in [0, 100]
- net_score_minus_100_100: numpy array of combined scores in [-100, +100]
- short_inverted: bool flag showing if the short series was inverted

Dependencies
------------
- numpy
- pandas

Limitations
-----------
- Percentile scores are relative to the selected window.
- The short inversion heuristic is best-effort.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class XGBNormalizedScores:
    """Normalized score bundle for LONG/SHORT and net score."""

    long_0_100: np.ndarray
    short_0_100: np.ndarray
    net_score_minus_100_100: np.ndarray
    short_inverted: bool


def percentile_rank_0_100(values: np.ndarray) -> np.ndarray:
    """Convert values to percentile rank in range [0, 100]."""

    s = pd.Series(values)
    s = s.replace([np.inf, -np.inf], np.nan)
    if s.isna().all():
        return np.full(shape=len(s), fill_value=50.0)

    fill_value = float(s.dropna().median())
    s = s.fillna(fill_value)
    pct = s.rank(pct=True, method="average")
    return (pct * 100.0).astype(float).to_numpy()


def should_invert_short_scores(raw_short: np.ndarray) -> bool:
    """Heuristic to decide whether short raw scores should be inverted."""

    s = pd.Series(raw_short).replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return False

    pct_positive = float((s > 0).mean())
    pct_negative = float((s < 0).mean())

    # If almost all values are negative, it is likely that "better" short entries
    # correspond to more negative raw values.
    return pct_negative >= 0.90 and pct_positive <= 0.10


def normalize_long_short_scores(
    raw_long: np.ndarray,
    raw_short: np.ndarray,
    *,
    invert_short: bool | None = None,
) -> XGBNormalizedScores:
    """Normalize raw LONG/SHORT model outputs into stable scores.

    Args:
        raw_long: Raw LONG model outputs.
        raw_short: Raw SHORT model outputs.
        invert_short: Optional override. If None, uses heuristic.

    Returns:
        XGBNormalizedScores with LONG/SHORT in 0..100 and NET in -100..100.
    """

    if invert_short is None:
        invert_short = should_invert_short_scores(raw_short)

    short_oriented = -raw_short if invert_short else raw_short

    long_0_100 = percentile_rank_0_100(raw_long)
    short_0_100 = percentile_rank_0_100(short_oriented)
    net = long_0_100 - short_0_100

    return XGBNormalizedScores(
        long_0_100=long_0_100,
        short_0_100=short_0_100,
        net_score_minus_100_100=net,
        short_inverted=bool(invert_short),
    )
