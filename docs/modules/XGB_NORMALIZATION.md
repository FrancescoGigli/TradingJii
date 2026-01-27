# XGB Normalization (Canonical 0..100 / -100..100)

## Purpose
Provide a **single, shared normalization strategy** for XGBoost model outputs so
that Train and Test/Backtest UI show consistent scores.

This module complements:
- `docs/modules/BTC_INFERENCE_SCORING.md`

## Responsibilities
- Normalize raw LONG and SHORT predictions into stable, window-relative scores.
- Optionally invert the SHORT raw series when the model encoding is oriented as
  "more negative = stronger short".
- Produce a NET score in `[-100, +100]` suitable for direct comparison with the
  Signal Calculator confidence score.

## Inputs / Outputs

### Inputs
- `raw_long`: numpy array of raw LONG model outputs.
- `raw_short`: numpy array of raw SHORT model outputs.

### Outputs
`services/xgb_normalization.normalize_long_short_scores()` returns:
- `long_0_100`: LONG percentile rank in `[0, 100]`
- `short_0_100`: SHORT percentile rank in `[0, 100]`
- `net_score_minus_100_100`: `long_0_100 - short_0_100` in `[-100, +100]`
- `short_inverted`: bool flag indicating if SHORT was inverted before ranking

`services/ml_inference.build_normalized_xgb_frame()` builds a DataFrame with:
- `score_long_raw`, `score_short_raw`
- `score_long_0_100`, `score_short_0_100`
- `net_score_-100_100`

## Dependencies
- `numpy`
- `pandas`

## Limitations
- Percentile scores are **relative** to the selected window.
- The short inversion heuristic is best-effort.

## UI Notes (Test/Backtest "Current Signals Comparison")
The Test/Backtest tab shows three related values:
- **LONG (0..100)**: percentile rank of the LONG model output within the selected window
- **SHORT (0..100)**: percentile rank of the (optionally inverted) SHORT model output within the selected window
- **NET (-100..+100)**: `LONG - SHORT`

Because LONG and SHORT are percentile ranks, it is normal to occasionally see
**100** (top-ranked value) or **0** (bottom-ranked value) in the current candle.
This does **not** mean the model is "100% sure"; it means the last candle is the
extreme (best/worst) score in the current window.

### Multiple timeframes
If multiple model bundles are present under `shared/models/` (e.g. `15m` and `1h`),
the UI may show **side-by-side** NET/LONG/SHORT values per timeframe.
This helps explain cases where the 15m model and 1h model disagree on the same
latest candle.
