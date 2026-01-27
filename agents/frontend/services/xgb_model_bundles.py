"""\
🤖 XGB Model Bundles (Per-Timeframe)
==================================

Purpose
-------
Load XGBoost LONG/SHORT models for multiple timeframes (e.g. 15m, 1h) from
`shared/models/` and run batch inference.

This module exists because the UI may need to show predictions for **both** 15m
and 1h models in the Test/Backtest tab, while keeping the heavy feature
calculation shared.

Responsibilities
----------------
- Discover available model timeframes.
- Load a model bundle (long model, short model, scaler, metadata).
- Run batch predictions with feature alignment.

Inputs / Outputs
----------------
- Input: a feature DataFrame (output of `services.ml_inference.compute_ml_features`).
- Output: a DataFrame with `pred_score_long` and `pred_score_short`.

Dependencies
------------
- `services.feature_alignment.align_features_dataframe_with_report`

Limitations
-----------
- This module does not compute features; it expects the caller to do that.
"""

from __future__ import annotations

import json
import os
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from services.feature_alignment import FeatureAlignmentReport, align_features_dataframe_with_report


DEFAULT_TIMEFRAMES = ("15m", "1h")


@dataclass
class XGBModelBundle:
    timeframe: str
    version: str
    feature_names: list[str]
    model_long: Any
    model_short: Any
    scaler: Any
    metadata: Dict[str, Any]
    last_alignment_report: Optional[FeatureAlignmentReport] = None


def get_models_dir() -> Path:
    shared_path = os.environ.get("SHARED_DATA_PATH", "/app/shared")
    model_dir = Path(shared_path) / "models"

    # Local dev fallback
    if not model_dir.exists():
        model_dir = Path(__file__).parent.parent.parent.parent / "shared" / "models"

    return model_dir


def load_bundle(timeframe: str) -> Optional[XGBModelBundle]:
    model_dir = get_models_dir()

    model_long_path = model_dir / f"model_long_{timeframe}_latest.pkl"
    model_short_path = model_dir / f"model_short_{timeframe}_latest.pkl"
    scaler_path = model_dir / f"scaler_{timeframe}_latest.pkl"
    metadata_path = model_dir / f"metadata_{timeframe}_latest.json"

    if not (model_long_path.exists() and model_short_path.exists() and scaler_path.exists() and metadata_path.exists()):
        return None

    with open(model_long_path, "rb") as f:
        model_long = pickle.load(f)
    with open(model_short_path, "rb") as f:
        model_short = pickle.load(f)
    with open(scaler_path, "rb") as f:
        scaler = pickle.load(f)
    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    feature_names = metadata.get("feature_names", [])
    version = metadata.get("version", f"{timeframe}_unknown")

    return XGBModelBundle(
        timeframe=timeframe,
        version=version,
        feature_names=feature_names,
        model_long=model_long,
        model_short=model_short,
        scaler=scaler,
        metadata=metadata,
    )


def list_available_timeframes(allowed: Tuple[str, ...] = DEFAULT_TIMEFRAMES) -> list[str]:
    model_dir = get_models_dir()
    out: list[str] = []
    for tf in allowed:
        if (model_dir / f"metadata_{tf}_latest.json").exists():
            out.append(tf)
    return out


def predict_batch(bundle: XGBModelBundle, df_features: pd.DataFrame) -> pd.DataFrame:
    """Run batch inference and return df with pred_score_long/pred_score_short."""
    if not bundle.feature_names:
        raise ValueError(f"Empty feature_names in metadata for timeframe={bundle.timeframe}")

    X_df, report = align_features_dataframe_with_report(
        df_features,
        bundle.feature_names,
        fill_value=0.0,
        forward_fill=True,
    )
    bundle.last_alignment_report = report

    X_scaled = bundle.scaler.transform(X_df)

    out = df_features.copy()
    out["pred_score_long"] = bundle.model_long.predict(X_scaled)
    out["pred_score_short"] = bundle.model_short.predict(X_scaled)
    return out
