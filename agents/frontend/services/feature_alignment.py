"""agents.frontend.services.feature_alignment

Purpose
-------
Provide small utilities to align feature matrices for scikit-learn pipelines.

Why this exists
--------------
When a scikit-learn transformer (e.g., StandardScaler) is fitted on a pandas
DataFrame, it stores the feature names. If we later call `.transform()` with a
NumPy array, scikit-learn emits warnings like:

    "X does not have valid feature names, but StandardScaler was fitted with
    feature names"

To avoid noisy logs (and ensure consistent feature ordering), we always rebuild
an aligned DataFrame with the exact expected columns.

Responsibilities
----------------
- Align an input DataFrame to a given `feature_names` list.
- Build a 1-row DataFrame from a Series/dict aligned to `feature_names`.

Inputs / Outputs
----------------
- Input: pandas DataFrame / Series, and a sequence of expected feature names.
- Output: pandas DataFrame with columns exactly matching `feature_names`.

Dependencies
------------
- pandas

Limitations
-----------
- Missing features are filled with `fill_value` (default: 0.0).
- This module does not attempt to compute indicators; it only aligns columns.
"""

from __future__ import annotations

from typing import Mapping, Sequence, Union

import pandas as pd


def align_features_dataframe(
    df: pd.DataFrame,
    feature_names: Sequence[str],
    *,
    fill_value: float = 0.0,
    forward_fill: bool = False,
) -> pd.DataFrame:
    """Return a DataFrame with columns aligned to `feature_names`.

    Args:
        df: Input DataFrame.
        feature_names: Target columns (order matters).
        fill_value: Value used for missing features / remaining NaNs.
        forward_fill: If True, forward-fill NaNs before final fill_value.

    Returns:
        A DataFrame with columns exactly `feature_names` in the same order.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=list(feature_names))

    aligned = df.reindex(columns=list(feature_names))
    if forward_fill:
        aligned = aligned.ffill()
    return aligned.fillna(fill_value)


def align_features_row(
    row: Union[pd.Series, Mapping[str, object]],
    feature_names: Sequence[str],
    *,
    fill_value: float = 0.0,
) -> pd.DataFrame:
    """Build a 1-row DataFrame aligned to `feature_names`.

    Args:
        row: Input row (Series or dict-like).
        feature_names: Target columns (order matters).
        fill_value: Value used for missing features / NaNs.

    Returns:
        A 1-row DataFrame with columns exactly `feature_names`.
    """

    values = []
    for feat in feature_names:
        if isinstance(row, pd.Series):
            val = row.get(feat, fill_value)
        else:
            val = row.get(feat, fill_value)

        if pd.isna(val):
            values.append(fill_value)
        else:
            try:
                values.append(float(val))
            except (TypeError, ValueError):
                values.append(fill_value)

    return pd.DataFrame([values], columns=list(feature_names))


__all__ = [
    "align_features_dataframe",
    "align_features_row",
]
