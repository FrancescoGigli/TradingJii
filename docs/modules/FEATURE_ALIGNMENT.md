# Feature Alignment Utilities

## Purpose
This module provides small helpers to align feature matrices passed into scikit-learn transformers.

It exists to prevent warnings such as:

> "X does not have valid feature names, but StandardScaler was fitted with feature names"

and to guarantee consistent feature ordering between training and inference.

## Location
- Code: `agents/frontend/services/feature_alignment.py`

## Responsibilities
- Build an aligned **DataFrame** for batch inference (`align_features_dataframe`).
- Build an aligned **1-row DataFrame** for single-row inference (`align_features_row`).
- Provide diagnostics to detect heavy auto-filling (`align_features_dataframe_with_report`).

## Inputs / Outputs
### `align_features_dataframe(df, feature_names, fill_value=0.0, forward_fill=False)`
- **Input**: `df` (pandas DataFrame), `feature_names` (ordered list of strings)
- **Output**: DataFrame with **exactly** `feature_names` as columns, in the same order.

### `align_features_row(row, feature_names, fill_value=0.0)`
- **Input**: `row` (pandas Series or dict-like), `feature_names` (ordered list of strings)
- **Output**: 1-row DataFrame with **exactly** `feature_names` as columns.

### `align_features_dataframe_with_report(df, feature_names, fill_value=0.0, forward_fill=False)`
- **Input**: `df` (pandas DataFrame), `feature_names` (ordered list of strings)
- **Output**: `(aligned_df, report)` where `report` is a `FeatureAlignmentReport` containing:
  - `expected_count`, `input_count`
  - `missing_features` (auto-filled)
  - `extra_features` (dropped)
  - `filled_ratio`

## Dependencies
- `pandas`

## Limitations
- Missing features are filled with `fill_value` (default: `0.0`).
- This module does **not** compute indicators; it only aligns columns.

## Usage in the codebase
Current users:
- `agents/frontend/services/ml_inference.py`
- `agents/frontend/services/local_models.py`
- `agents/frontend/components/tabs/train/models_inference.py`

UI diagnostics:
- `agents/frontend/components/tabs/backtest/xgb_section.py` (Feature Alignment Diagnostics expander)
  - Note: the Backtest UI renders this expander **after** running batch inference so the
    report is tied to the current backtest run (prevents showing stale diagnostics from
    other tabs).
