# BTC Inference Scoring (0-100 / -100..100)

## Purpose
This module documents how the **BTC live inference** feature converts raw model
predictions into stable, user-friendly scores and trading signals.

It applies to the Streamlit UI section:
- **ML → Train → Training → Bitcoin Live Inference**

## Responsibilities
- Convert raw predictions from the **LONG** and **SHORT** XGBoost models into a
  comparable scale per candle.
- Compute a combined directional score (**net**) in a symmetric range.
- Compute a confidence metric.
- Derive a final discrete trading signal.
- Surface **strict diagnostics** when no real-time data exists for the requested
  symbol/timeframe.

## Inputs / Outputs

### Inputs
- `timeframe`: `15m` or `1h`
- `symbol`: default `BTCUSDT` (converted internally to CCXT format)
- `n_candles`: number of candles to fetch from the real-time DB

### Outputs
`services/local_models.run_inference()` returns a DataFrame with:
- OHLCV (`timestamp`, `open`, `high`, `low`, `close`, `volume`)
- Raw predictions:
  - `score_long_raw`
  - `score_short_raw`
- Normalized per-model scores (**higher = better**) in `[0, 100]`:
  - `score_long_0_100`
  - `score_short_0_100`
- Combined score in `[-100, +100]`:
  - `net_score_-100_100 = score_long_0_100 - score_short_0_100`
- Confidence in `[0, 100]`:
  - `confidence_0_100 = abs(net_score_-100_100)`
- Diagnostics:
  - `short_inverted` (bool)
- Discrete signal:
  - `signal` in `{STRONG BUY, BUY, HOLD, SELL, STRONG SELL}`

## Normalization Details

### Why percentile rank
Raw model predictions are typically **small** values (e.g. `-0.004`) because they
are trained to predict a score derived from a trailing-stop simulation. The raw
scale is not stable across symbols/timeframes/market regimes.

To make scores comparable candle-by-candle, we compute a **percentile rank**
within the inference window (e.g. last 200 candles).

### Percentile implementation
For a vector of scores `x`:
- `pct = rank(x) / len(x)` using `pandas.Series.rank(pct=True)`
- `score_0_100 = pct * 100`

This guarantees:
- `0` = weakest relative opportunity in the window
- `100` = strongest relative opportunity in the window

### Short score orientation
Some pipelines encode the short label such that a “better short entry” may
correspond to **more negative** raw values.

We apply a heuristic:
- If `>=90%` of short raw values are negative (and `<=10%` positive), we invert:
  - `short_oriented = -score_short_raw`
- Otherwise:
  - `short_oriented = score_short_raw`

The chosen behavior is exposed as `short_inverted`.

## Combined Score
The combined score is defined as:

```text
net_score_-100_100 = score_long_0_100 - score_short_0_100
confidence_0_100   = abs(net_score_-100_100)
```

This is a standard approach to combine two directional scores:
- `net > 0` biases LONG
- `net < 0` biases SHORT
- `abs(net)` represents how “decided” the model is (confidence)

## Signal Logic
Signals are derived from net + confidence:

- If `confidence < 10` → `HOLD`
- Else:
  - `net >= 60` → `STRONG BUY`
  - `net >= 30` → `BUY`
  - `net <= -60` → `STRONG SELL`
  - `net <= -30` → `SELL`
  - otherwise → `HOLD`

## Dependencies
- Real-time OHLCV DB: `shared/data_cache/trading_data.db`
- Table: `realtime_ohlcv`
- Model artifacts: `shared/models/*_latest.pkl` and `metadata_*_latest.json`

## Limitations
- Scores are **relative to the selected window** (e.g. last 200 candles).
  Changing the window size changes the percentile ranking.
- The short inversion heuristic is a best-effort rule; for full correctness the
  short label convention should be explicitly documented during labeling.
- Strict mode raises an explicit error if the real-time DB has no rows for
  `(symbol, timeframe)`.
