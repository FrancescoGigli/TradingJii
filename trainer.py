"""
Utility di training modelli (LSTM, RF, XGBoost).

Correzioni:
1. Re-introdotta la funzione pubblica `ensure_trained_models_dir`
   usata da main.py; ora è solo un wrapper del helper interno.
2. Resto del file invariato rispetto alla versione precedente.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from pathlib import Path
from typing import Any, Tuple

import joblib
import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
from tensorflow.keras.callbacks import EarlyStopping, TensorBoard, Callback
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.utils import class_weight
from tqdm import tqdm

import config
from data_utils import prepare_data
from models import create_lstm_model, create_rf_model

_LOG = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Directory modelli
# ----------------------------------------------------------------------
def _trained_dir() -> Path:
    return Path(config.get_lstm_model_file("tmp")).parent

def _ensure_trained_models_dir() -> None:
    _trained_dir().mkdir(exist_ok=True)

# --- wrapper di compatibilità richiesto da main.py --------------------
def ensure_trained_models_dir() -> str:
    """Mantiene la compatibilità con main.py: crea la cartella e ne restituisce il path."""
    _ensure_trained_models_dir()
    return str(_trained_dir())
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# Utility plotting
# ----------------------------------------------------------------------
def _save_training_plot(history, timeframe: str) -> None:
    out_dir = Path("logs/plots")
    out_dir.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(12, 5))

    plt.subplot(1, 2, 1)
    plt.plot(history.history["loss"],     label="Train")
    plt.plot(history.history["val_loss"], label="Val")
    plt.title("Loss")
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.plot(history.history["accuracy"],     label="Train")
    plt.plot(history.history["val_accuracy"], label="Val")
    plt.title("Accuracy")
    plt.legend()

    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    plt.savefig(out_dir / f"training_history_{timeframe}_{ts}.png")
    plt.close()

def _augment_jitter(x: np.ndarray, sigma: float = 0.03) -> np.ndarray:
    return x + np.random.normal(0.0, sigma, size=x.shape)

# ----------------------------------------------------------------------
# LSTM
# ----------------------------------------------------------------------
async def train_lstm_model_for_timeframe(
    exchange,
    symbols: list[str],
    timeframe: str,
    timestep: int,
) -> Tuple[Any, StandardScaler, dict[str, Any]] | Tuple[None, None, None]:

    from fetcher import get_data_async  # import locale per evitare loop

    X_list, y_list = [], []
    for sym in symbols:
        df = await get_data_async(exchange, sym, timeframe)
        if df is None:
            continue
        data = prepare_data(df)
        if not np.isfinite(data).all() or len(data) < timestep + 1:
            continue

        data_scaled = StandardScaler().fit_transform(data)
        for i in range(timestep, len(data_scaled) - 1):
            X_list.append(data_scaled[i - timestep : i])
            
            # Parameters
            future_window = 3  # Number of future candles to consider
            profit_threshold = 0.005  # e.g., +0.5% gain
            loss_threshold = -0.005   # e.g., -0.5% loss

            # Compute future returns
            future_returns = (df["close"].iloc[i+1:i+1+future_window].values - df["close"].iloc[i]) / df["close"].iloc[i]

            # Class assignment
            if np.any(future_returns >= profit_threshold):
                label = 1  # BUY
            elif np.any(future_returns <= loss_threshold):
                label = 0  # SELL
            else:
                label = 2  # NEUTRAL

            y_list.append(label)

    if not X_list:
        _LOG.error("No data collected for %s", timeframe)
        return None, None, None

    X_all = np.array(X_list)
    y_all = np.array(y_list)
    
    # Convert labels to one-hot encoding for LSTM
    from tensorflow.keras.utils import to_categorical
    y_all = to_categorical(y_all, num_classes=3)

    tscv = TimeSeriesSplit(n_splits=4)
    train_idx, val_idx = list(tscv.split(X_all))[-1]
    X_tr, X_val = X_all[train_idx], X_all[val_idx]
    y_tr, y_val = y_all[train_idx], y_all[val_idx]

    # Converti one-hot encoding in singoli indici per il bilanciamento delle classi
    y_tr_labels = np.argmax(y_tr, axis=1)
    
    # bilanciamento classi con jitter
    unique, counts = np.unique(y_tr_labels, return_counts=True)
    if len(unique) >= 2 and counts.min() != counts.max():
        minority = unique[counts.argmin()]
        aug_X, aug_y = [], []
        for i in np.where(y_tr_labels == minority)[0]:
            aug_X.append(_augment_jitter(X_tr[i]))
            aug_y.append(y_tr[i])
        if aug_X:
            X_tr = np.concatenate([X_tr, np.array(aug_X)], axis=0)
            y_tr = np.concatenate([y_tr, np.array(aug_y)], axis=0)
            _LOG.info("Augmentazione jitter applicata (%s)", timeframe)
    
    # Calcola pesi delle classi usando gli indici non one-hot
    y_tr_labels = np.argmax(y_tr, axis=1)
    class_w = class_weight.compute_class_weight("balanced", classes=np.unique(y_tr_labels), y=y_tr_labels)
    class_w = {i: v for i, v in enumerate(class_w)}

    num_feat = len(config.EXPECTED_COLUMNS)
    model = create_lstm_model((timestep, num_feat))
    model.compile(
        optimizer="adam",
        loss=model.loss,
        metrics=["accuracy", tf.keras.metrics.Precision(), tf.keras.metrics.Recall(), tf.keras.metrics.AUC()],
    )

    cb_early = EarlyStopping(monitor="val_loss", patience=3, restore_best_weights=True)
    log_dir = Path("logs/fit") / _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    cb_tb = TensorBoard(log_dir=str(log_dir), histogram_freq=1)

    class _Bar(Callback):
        def __init__(self, total: int) -> None:
            super().__init__()
            self._pbar = tqdm(total=total, desc=f"LSTM {timeframe}", ncols=80, leave=False)
        def on_epoch_end(self, epoch, logs=None):
            self._pbar.update(1)
            self._pbar.set_postfix(loss=f"{logs['loss']:.4f}", acc=f"{logs['accuracy']:.4f}")
        def on_train_end(self, logs=None):
            self._pbar.close()

    history = model.fit(
        X_tr, y_tr,
        epochs=40,
        batch_size=32,
        validation_data=(X_val, y_val),
        class_weight=class_w,
        callbacks=[cb_early, cb_tb, _Bar(40)],
        verbose=0,
    )

    _save_training_plot(history, timeframe)

    # ------------------------------------------------------------------
    # Salvataggio
    # ------------------------------------------------------------------
    _ensure_trained_models_dir()
    model_path   = Path(config.get_lstm_model_file(timeframe))
    scaler_path  = Path(config.get_lstm_scaler_file(timeframe))
    metrics_path = model_path.with_suffix(".json")

    model.save(model_path)

    scaler_final = StandardScaler().fit(X_tr.reshape(-1, num_feat))
    joblib.dump(scaler_final, scaler_path)

    metrics_dict = {
        "train": dict(zip(model.metrics_names, model.evaluate(X_tr, y_tr, verbose=0))),
        "val":   dict(zip(model.metrics_names, model.evaluate(X_val, y_val, verbose=0))),
    }
    metrics_path.write_text(json.dumps(metrics_dict, indent=4))

    _LOG.info("LSTM salvato in %s", model_path)
    return model, scaler_final, metrics_dict

# ----------------------------------------------------------------------
# RANDOM-FOREST
# ----------------------------------------------------------------------
from sklearn.ensemble import RandomForestClassifier

def _train_rf_sync(X: np.ndarray, y: np.ndarray):
    scaler = StandardScaler().fit(X)
    X_scaled = scaler.transform(X)

    tscv = TimeSeriesSplit(n_splits=4)
    tr_idx, val_idx = list(tscv.split(X_scaled))[-1]
    X_tr, X_val = X_scaled[tr_idx], X_scaled[val_idx]
    y_tr, y_val = y[tr_idx], y[val_idx]

    rf = create_rf_model()
    _LOG.info("Training Random-Forest…")
    rf.fit(X_tr, y_tr)

    y_pred = rf.predict(X_val)
    m = {
        "val_accuracy":  accuracy_score(y_val, y_pred),
        "val_precision": precision_score(y_val, y_pred, average="weighted"),
        "val_recall":    recall_score(y_val, y_pred, average="weighted"),
        "val_f1":        f1_score(y_val, y_pred, average="weighted"),
    }
    return rf, scaler, m

async def train_random_forest_model_wrapper(top_symbols, exchange, timestep, timeframe):
    from fetcher import get_data_async

    X_all, y_all = [], []
    for sym in top_symbols:
        df = await get_data_async(exchange, sym, timeframe)
        if df is None:
            continue
        data = prepare_data(df)
        if not np.isfinite(data).all() or len(data) < timestep + 1:
            continue
        # Non scaliamo i dati qui, ma li raccogliamo non scalati
        for i in range(timestep, len(data) - 1):
            X_all.append(data[i - timestep : i].flatten())
            
            # Parameters
            future_window = 3  # Number of future candles to consider
            profit_threshold = 0.005  # e.g., +0.5% gain
            loss_threshold = -0.005   # e.g., -0.5% loss

            # Compute future returns
            future_returns = (df["close"].iloc[i+1:i+1+future_window].values - df["close"].iloc[i]) / df["close"].iloc[i]

            # Class assignment
            if np.any(future_returns >= profit_threshold):
                label = 1  # BUY
            elif np.any(future_returns <= loss_threshold):
                label = 0  # SELL
            else:
                label = 2  # NEUTRAL
                
            y_all.append(label)

    if not X_all:
        _LOG.error("No data RF %s", timeframe)
        return None, None, None

    rf, scaler, metrics = _train_rf_sync(np.array(X_all), np.array(y_all))

    _ensure_trained_models_dir()
    joblib.dump(rf,     config.get_rf_model_file(timeframe))
    joblib.dump(scaler, config.get_rf_scaler_file(timeframe))
    Path(config.get_rf_model_file(timeframe)).with_suffix(".json").write_text(json.dumps(metrics, indent=4))
    return rf, scaler, metrics

# ----------------------------------------------------------------------
# XGBOOST
# ----------------------------------------------------------------------
import xgboost as xgb
def _train_xgb_sync(X, y):
    scaler = StandardScaler().fit(X)
    X_scaled = scaler.transform(X)

    tscv = TimeSeriesSplit(n_splits=4)
    tr_idx, val_idx = list(tscv.split(X_scaled))[-1]
    X_tr, X_val = X_scaled[tr_idx], X_scaled[val_idx]
    y_tr, y_val = y[tr_idx], y[val_idx]

    model = xgb.XGBClassifier(
        n_estimators=100, max_depth=6, learning_rate=0.1,
        num_class=3,
        objective='multi:softprob',
        eval_metric='mlogloss'
        # Parametro 'use_label_encoder' rimosso perché deprecato
    )
    _LOG.info("Training XGBoost…")
    model.fit(X_tr, y_tr)

    y_pred = model.predict(X_val)
    m = {
        "val_accuracy":  accuracy_score(y_val, y_pred),
        "val_precision": precision_score(y_val, y_pred, average="weighted"),
        "val_recall":    recall_score(y_val, y_pred, average="weighted"),
        "val_f1":        f1_score(y_val, y_pred, average="weighted"),
    }
    return model, scaler, m

async def train_xgboost_model_wrapper(top_symbols, exchange, timestep, timeframe):
    from fetcher import get_data_async

    X_all, y_all = [], []
    for sym in top_symbols:
        df = await get_data_async(exchange, sym, timeframe)
        if df is None:
            continue
        data = prepare_data(df)
        if not np.isfinite(data).all() or len(data) < timestep + 1:
            continue
        # I dati sono già non scalati, come richiesto
        for i in range(timestep, len(data) - 1):
            X_all.append(data[i - timestep : i].flatten())
            
            # Parameters
            future_window = 3  # Number of future candles to consider
            profit_threshold = 0.005  # e.g., +0.5% gain
            loss_threshold = -0.005   # e.g., -0.5% loss

            # Compute future returns
            future_returns = (df["close"].iloc[i+1:i+1+future_window].values - df["close"].iloc[i]) / df["close"].iloc[i]

            # Class assignment
            if np.any(future_returns >= profit_threshold):
                label = 1  # BUY
            elif np.any(future_returns <= loss_threshold):
                label = 0  # SELL
            else:
                label = 2  # NEUTRAL
                
            y_all.append(label)

    if not X_all:
        _LOG.error("No data XGB %s", timeframe)
        return None, None, None

    model, scaler, metrics = _train_xgb_sync(np.array(X_all), np.array(y_all))

    _ensure_trained_models_dir()
    joblib.dump(model,  config.get_xgb_model_file(timeframe))
    joblib.dump(scaler, config.get_xgb_scaler_file(timeframe))
    Path(config.get_xgb_model_file(timeframe)).with_suffix(".json").write_text(json.dumps(metrics, indent=4))
    return model, scaler, metrics
