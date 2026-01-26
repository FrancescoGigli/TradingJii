# 📦 Modularization Plan

This document tracks the modularization of large files (>400 lines) to comply with the project's coding standards.

## 🗑️ Dead Code Removed (2026-01-26)

### `components/tabs/xgb_models/` - DELETED
The entire `xgb_models/` directory was identified as **dead code** and removed:

| File | Lines | Reason |
|------|-------|--------|
| `__init__.py` | ~20 | Never imported in app.py |
| `main.py` | ~30 | Tab never registered |
| `training.py` | ~400 | Duplicate of train/training.py |
| `viewer.py` | ~400 | Duplicate of train/models.py |
| `utils.py` | ~50 | Unused utilities |

**Total removed**: ~900 lines of dead code

### `components/tabs/train/model_viewer.py` - DELETED
| File | Lines | Reason |
|------|-------|--------|
| `model_viewer.py` | ~400 | Never imported, duplicate of `models.py` |

**Total removed**: ~400 lines of dead code

---


## ✅ Completed Modularizations

### 1. labeling_analysis.py (1073 → ~250 lines each)
**Location:** `agents/frontend/components/tabs/train/labeling_analysis/`

| New File | Content | Lines |
|----------|---------|-------|
| `__init__.py` | Re-exports all functions | ~60 |
| `charts.py` | MAE, score, ATR chart functions | ~280 |
| `dashboard.py` | Main dashboard renderer | ~120 |
| `stability.py` | Stability report functions | ~150 |
| `quality.py` | Label quality analysis | ~350 |

### 2. ml_labels.py (1018 → ~150 lines each)
**Location:** `agents/frontend/database/ml_labels/`

| New File | Content | Lines |
|----------|---------|-------|
| `__init__.py` | Re-exports all functions | ~65 |
| `crud.py` | CRUD operations (get, clear) | ~200 |
| `save.py` | Save labels to database | ~160 |
| `stats.py` | Statistics and inventory | ~150 |
| `schema.py` | Table creation, dataset export | ~130 |

### 3. train.py (874 → ~100 lines each)
**Location:** `agents/ml-training/train/`

| New File | Content | Lines |
|----------|---------|-------|
| `__init__.py` | Re-exports all functions | ~55 |
| `config.py` | Feature columns, XGBoost params | ~55 |
| `data_loader.py` | Load and validate datasets | ~115 |
| `metrics.py` | Ranking metrics, temporal split | ~70 |
| `trainer.py` | Model training and saving | ~85 |
| `__main__.py` | CLI entry point | ~85 |

---

## 🔜 Pending Modularizations

### 4. ml_training.py (838 lines)
**Location:** `agents/frontend/services/ml_training.py`
**Suggested split:**

| New File | Functions | ~Lines |
|----------|-----------|--------|
| `ml_training/data.py` | `get_available_training_data`, `load_training_data`, `_align_training_data` | ~300 |
| `ml_training/features.py` | `prepare_features`, `calculate_ranking_metrics` | ~200 |
| `ml_training/training.py` | `train_xgb_model`, `run_optuna_optimization` | ~300 |

### 5. database.py (750 lines)
**Location:** `agents/historical-data/core/database.py`
**Suggested split:**

| New File | Functions | ~Lines |
|----------|-----------|--------|
| `database/backfill.py` | `BackfillStatus`, `BackfillInfo`, backfill methods | ~200 |
| `database/storage.py` | `save_training_data`, `clear_training_data`, `get_training_data` | ~250 |
| `database/stats.py` | `get_candle_count`, `get_symbols`, `get_stats`, etc. | ~200 |

### 6. backtest_charts.py (710 lines)
**Location:** `agents/frontend/ai/visualizations/backtest_charts.py`
**Suggested split:**

| New File | Functions | ~Lines |
|----------|-----------|--------|
| `backtest_charts/equity.py` | Equity curve charts | ~200 |
| `backtest_charts/trades.py` | Trade history charts | ~200 |
| `backtest_charts/performance.py` | Performance metrics charts | ~250 |

---

## 📋 Files Between 400-700 Lines (Lower Priority)

These files exceed 400 lines but are less critical:

| File | Lines | Notes |
|------|-------|-------|
| `agents/frontend/ai/backtest/engine.py` | ~550 | Backtest engine |
| `agents/frontend/components/tabs/train/labeling.py` | ~500 | Labeling UI |
| `agents/frontend/services/market_scanner.py` | ~450 | Market scanner |
| `agents/historical-data/core/validation.py` | ~420 | Data validation |

> **Note:** `ml_training_v2.py` was removed in a previous cleanup.

---

## 🔧 Implementation Notes

### Backward Compatibility
All modularized packages maintain backward compatibility through `__init__.py` files that re-export all public functions. Existing imports continue to work:

```python
# Both work:
from agents.frontend.database.ml_labels import get_ml_labels
from agents.frontend.database import get_ml_labels
```

### Testing After Modularization
After modularizing a file, test by:
1. Running the application: `streamlit run agents/frontend/app.py`
2. Verifying imports work in Python console
3. Running any related test files

### Naming Conventions
- Package folders use the same name as the original file (without `.py`)
- Sub-modules use descriptive names based on functionality
- All modules use `__all__` to explicitly define exports
