# Changelog

## [2026-01-23] - Training Summary Card HTML Rendering Fix

### Fixed
- **`ai/visualizations/training_charts.py`**: Raw HTML displayed as text instead of rendered
  - Streamlit's markdown renderer has issues with complex `<table>` elements
  - Replaced HTML `<table>` with CSS Grid-based `<div>` layout
  - Added helper function `_build_metrics_grid()` for Streamlit-compatible grid rendering
  - Metrics (Spearman, Top1% Positive, R²) now display properly in styled card
  - Header/data rows use `display: grid; grid-template-columns: 1fr 1fr 1fr`

---

## [2026-01-23] - ML Training Architecture Refactoring

### Added
- **ML Training Container (`agents/ml-training/`)**: New Docker container for training execution
  - `main.py`: Daemon that polls for training jobs every 30s
  - `core/database.py`: Database operations for job queue
  - `core/job_handler.py`: XGBoost + Optuna training execution with progress updates
  - `Dockerfile`: Container configuration

- **Training Jobs System**: Database-backed job queue for training
  - `training_jobs` table: Tracks job status, progress, trial log
  - Real-time progress updates from ml-training to frontend
  - Job cancellation support

- **Frontend Database Module (`database/training_jobs.py`)**: 
  - `TrainingJob` dataclass for job data
  - CRUD operations: submit, get status, cancel, get history

- **Documentation (`docs/ML_TRAINING_ARCHITECTURE.md`)**: 
  - Complete architecture documentation
  - Database schema
  - Data flow diagrams
  - Troubleshooting guide

### Changed
- **`docker-compose.yml`**: 
  - Added `ml-training` service
  - Removed resource limits from frontend (training no longer runs there)

- **`services/training_service.py`**: Simplified to job submission only
  - Removed all XGBoost/Optuna training logic
  - Now only submits jobs and polls for status
  - Training execution moved to ml-training container

- **`components/tabs/train/training.py`**: Refactored for job monitoring
  - Submit training request (not execute)
  - Real-time progress bar with polling
  - Display current trial, best scores, trial log
  - Cancel button for active jobs
  - Training history section

### Architecture
```
Frontend (Streamlit)         ML-Training Container
       │                            │
 Click "Start"                      │
       │                            │
 INSERT training_jobs ──────────► Poll every 30s
       │                            │
 Poll for progress ◄──────────── UPDATE progress
       │                            │
 Show progress bar                  │
       │                       XGBoost + Optuna
       │                            │
 Show results ◄────────────── Save models + metadata
```

### Benefits
- **Separation of Concerns**: Frontend handles UI only
- **Non-Blocking UI**: Training runs in background
- **Real-Time Progress**: Live updates via polling
- **Cancellation Support**: Users can stop training
- **Job History**: Track past training jobs

---

## [2026-01-23] - Training Summary Card Dark Theme Fix

### Fixed
- **`ai/visualizations/training_charts.py`**: White background in metrics table
  - Added explicit dark background (`#0d1117`) to `<table>` element
  - Added explicit background to all `<tr>`, `<th>`, `<td>` elements
  - Header row uses `#161b26` background for visual separation
  - Data rows use `#0d1117` background for consistency
  - Fixed the Metric/LONG/SHORT comparison table in training summary card

---

## [2026-01-23] - ML Models Dashboard & Extended Features

### Added
- **21 Features for Training**: Extended from 8 to 21 features including all technical indicators
  - OHLCV (5): open, high, low, close, volume
  - Moving Averages (4): sma_20, sma_50, ema_12, ema_26
  - Bollinger Bands (3): bb_upper, bb_middle, bb_lower
  - Momentum (4): rsi, macd, macd_signal, macd_hist
  - Other (5): atr, adx, cci, willr, obv

- **Feature Importance Charts**: Bar charts showing top 15 features for LONG/SHORT models
- **Saved AI Analysis**: GPT-4o analysis saved to metadata during training, displayed without API calls
- **Optimization History Trials**: Full trial history saved for post-training visualization
- **Enhanced Step 4 (Models)**: Complete dashboard with:
  - Model summary cards with quality badges
  - Training analytics (metrics comparison, precision@K)
  - Feature importance visualization
  - Saved AI analysis display
  - Model parameters & data range
  - Real-time inference section

### Changed
- **labeling_db.py**: `v_xgb_training` VIEW now includes all 21 features
- **training_service.py**: 
  - `FEATURE_COLUMNS` expanded to 21
  - `load_training_data()` fetches all features
  - Metadata includes trials, feature importance, AI analysis placeholder
- **training.py**: Saves AI analysis to metadata after training

### Migration Notes
After updating, you need to:
1. **Re-generate labels** (Step 2) to update the VIEW
2. **Re-train models** (Step 3) to use all 21 features


## [2026-01-23] - Training Tab: Persistent Model Status Display

### Added
- **`components/tabs/train/training.py`**: Current trained models status display
  - New function `load_latest_model_metadata()` - loads metadata from saved models
  - New function `_render_current_models_status()` - renders model status section
  - New function `_render_model_details()` - renders detailed model info with charts
  - Displays 📦 **Current Trained Models** section at the top of the tab
  - Shows summary cards with metrics for each timeframe (15m, 1h)
  - Uses tabs when both models exist for clean navigation
  - Displays Model Comparison and Precision@K charts from saved metadata
  - Shows training date and data range info

### Fixed
- **`components/tabs/train/training.py`**: HTML rendering issue in training results
  - Replaced `st.markdown(..., unsafe_allow_html=True)` with `st.html()` for Summary Card
  - Replaced `st.markdown(..., unsafe_allow_html=True)` with `st.html()` for AI Analysis
  - HTML was being displayed as raw text instead of rendered; now properly renders styled cards

### Changed
- **`components/tabs/train/training.py`**: Reorganized layout
  - Model status shown at top (always visible)
  - Training data samples moved to collapsible expander
  - Training config section more compact

---

## [2026-01-22] - Interactive Training UI + LLM Analysis

### Added
- **`services/training_service.py`**: New training service with real-time Optuna callbacks
  - `TrialResult` and `TrainingResult` dataclasses for structured results
  - `train_with_optuna()` with `on_trial_complete` and `on_progress` callbacks
  - Sequential training support for multiple timeframes (15m → 1h)

- **`ai/visualizations/training_charts.py`**: Plotly charts for training visualization
  - `create_optimization_curve()`: Spearman by trial with best-so-far line
  - `create_dual_optimization_chart()`: Side-by-side LONG/SHORT comparison
  - `create_metrics_comparison()`: Bar chart comparing model metrics
  - `create_precision_at_k_chart()`: Precision@K line chart
  - `create_trial_log_html()`: Colored trial log with 🏆 for new best

- **`services/training_analysis.py`**: LLM-powered result analysis (GPT-4o)
  - `analyze_training_results()`: Get AI insights on training quality
  - `format_analysis_html()`: Beautiful HTML card with strengths/weaknesses
  - Supports timeframe comparison when training both 15m and 1h

### Changed
- **`components/tabs/train/training.py`**: Complete rewrite for interactive experience
  - Checkbox to "Train Both Timeframes (15m → 1h)"
  - Real-time progress bar with status updates
  - Live-updating optimization charts during training
  - Trial-by-trial log with colors (green=improved, red=worse)
  - Final summary cards with quality assessment
  - Optional GPT-4o analysis at completion

### Training Results
- **15m Model**: Trained with 15 Optuna trials on 2.5M samples
- **1h Model**: Trained with 15 Optuna trials on 635K samples
- Models saved to `/app/shared/models/` with timeframe-specific versions


## [2026-01-22] - Tables Dark Theme Fix

### Added
- **`styles/tables.py`**: New reusable module for HTML-styled tables
  - `render_html_table()`: Dark theme compatible table rendering
  - `render_metrics_table()`: For metrics comparison tables
  - `render_ranking_table()`: For ranking tables with medals

### Changed
- **`xgb_models/viewer.py`**: Replaced 6 `st.table()` with `render_html_table()`
  - Regression Metrics, Precision@K, Complete Summary
  - Features List, Model Files, Parameters

- **`backtest/optimization.py`**: Replaced 2 `st.table()` with `render_html_table()`
  - Ranking Table, Detailed Results

- **`train/training.py`**: Replaced `st.dataframe()` with `render_html_table()`
  - Precision@K results

- **`train/labeling_visualizer.py`**: Replaced `st.dataframe()` with `render_html_table()`
  - Raw Data table

- **`train/labeling_analysis/quality.py`**: Replaced `st.dataframe()` with `render_html_table()`
  - Score Ranges table

### Fixed
- All tables now have proper dark theme visibility with:
  - Cyan headers (`#00ffff`)
  - Light text (`#e0e0ff`)
  - Semantic coloring (green for positive, red for negative)
  - Sticky headers for scrolling
  - Hover effects


All notable changes to this project are documented in this file.

The format follows a simplified semantic structure:
- Added
- Changed
- Fixed
- Removed

---

## [2026-01-22]

### Changed
- **MODULARIZATION**: Split `labeling_analysis.py` (1073 lines) into modular package:
  - `labeling_analysis/charts.py` - Chart creation functions
  - `labeling_analysis/dashboard.py` - Dashboard renderer
  - `labeling_analysis/stability.py` - Stability report
  - `labeling_analysis/quality.py` - Quality analysis
- **MODULARIZATION**: Split `ml_labels.py` (1018 lines) into modular package:
  - `ml_labels/crud.py` - CRUD operations
  - `ml_labels/save.py` - Save functions
  - `ml_labels/stats.py` - Statistics
  - `ml_labels/schema.py` - Table schema and dataset export
- **MODULARIZATION**: Split `train.py` (874 lines) into modular package:
  - `train/config.py` - Feature columns, XGBoost parameters
  - `train/data_loader.py` - Dataset loading and validation
  - `train/metrics.py` - Ranking metrics
  - `train/trainer.py` - Model training and saving
  - `train/__main__.py` - CLI entry point

### Added
- `docs/modules/MODULARIZATION_PLAN.md` - Plan for remaining large files
- Backward-compatible `__init__.py` files for all modularized packages

---

## [Unreleased]

### Added
- Custom HTML-based table renderer for Streamlit
- Dark theme optimized table styling
- Semantic value coloring (positive / negative)
- Sticky table headers
- Horizontal and vertical scrolling support
- Modular frontend architecture

### Changed
- Replaced Streamlit `st.dataframe()` with HTML rendering
- Separated rendering, styling, and integration logic

### Fixed
- Text visibility issues in dark themes
- Column truncation in wide tables

---

## [2026-01-21]

### Added
- Initial documentation for frontend table system
- Module-level documentation
- Architecture overview

---

## Notes

- Documentation must be updated whenever public behavior changes
- Any new module must include corresponding documentation
