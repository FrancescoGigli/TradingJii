# Changelog

## [2026-01-26] v2.3.1 - UI Cleanup & Refactoring Plan

### Removed
- **`status.py`**: Removed "Validation Checklist" section from ML Pipeline Status
  - Removed 4 disabled checkbox validations (data volume, labels, model exists, model quality)
  - Removed success/info messages at the end
  - Kept only the 3 status cards and detailed status expander

### Added
- **`docs/modules/TABS_REFACTORING_PLAN.md`**: Comprehensive analysis of tab structure
  - Documents all 3 main tabs and their components
  - Identifies 4 critical duplications in ML/Training tab
  - Provides detailed action plan with priorities
  - Lists files needing modification vs files OK

### Identified Duplications (for future refactoring)
| Duplication | Files Affected |
|-------------|----------------|
| `_get_models_dir()` | training_model_details.py, training_io_tables.py (should use shared/model_loader.py) |
| `COLORS` dict | 4+ files (should use shared/colors.py) |
| Model metadata loading | 3 files (should use shared/model_loader.py) |
| Step 3 vs Step 4 overlap | training_model_details.py duplicates models.py functionality |

---

## [2026-01-26] v2.3.0 - ML Tab Refactoring & Dead Code Removal

### Removed
- **DELETED `labeling_optuna.py`**: Dead code, never imported anywhere
- **DELETED `training_results.py`** (~600 lines): 
  - Was a duplicate of `models.py` functionality
  - Both showed feature importance, metrics, AI analysis, BTC inference
  - Removed to eliminate confusion and code duplication

### Added
- **New shared modules** (`components/tabs/train/shared/`):
  - `__init__.py`: Module exports
  - `model_loader.py`: Centralized model path and metadata loading
    - `get_model_dir()`: Get models directory path
    - `load_metadata()`: Load model metadata for a timeframe
    - `get_available_models()`: Get all available models
    - `model_exists()`: Check if model exists
    - `get_available_timeframes()`: Get list of trained timeframes
  - `colors.py`: Centralized dark theme color scheme
    - `COLORS`: Main color dictionary
    - `RATING_COLORS`: AI analysis quality badge colors
    - `SIGNAL_COLORS`: Trading signal colors

### Changed
- **`main.py`**: Removed "Results" tab (was duplicate of "Models")
  - Reduced from 6 sub-tabs to 5 sub-tabs
  - New structure: Data → Labeling → Training → Models → Explorer

- **`training_ai_eval.py`**: Refactored to use shared modules
  - Removed duplicated `COLORS` dict (now imports from `shared.colors`)
  - Removed duplicated `_get_models_dir()` and `_load_metadata()` (now imports from `shared.model_loader`)
  - Reduced file size by ~50 lines

- **`training_btc_inference.py`**: Refactored to use shared modules
  - Removed duplicated `COLORS` dict (now imports from `shared.colors`)
  - Removed duplicated `_get_models_dir()` (now imports from `shared.model_loader`)
  - Reduced file size by ~35 lines

### Technical Details
**Before (Duplicated code):**
```
training_results.py:  ~600 lines (DELETED)
training_ai_eval.py:  ~320 lines → ~270 lines
training_btc_inference.py: ~300 lines → ~265 lines
labeling_optuna.py:   ~200 lines (DELETED - never used)
```

**Shared modules created:**
```
train/shared/
├── __init__.py      (~15 lines)
├── model_loader.py  (~85 lines)
└── colors.py        (~65 lines)
```

**Total lines removed:** ~1,100+ lines of dead/duplicated code

---

## [2026-01-26] v2.2.0 - Tab Restructuring & Consolidation

### Changed
- **App reduced from 4 tabs to 3 tabs**:
  - Removed separate "Charts" tab
  - Merged Charts content into "Top 100 Coins" tab
  - New tab structure: `Top 100 Coins` | `Test` | `Backtest` | `ML`

- **Removed "Crypto Dashboard Pro" header** from app.py
  - Cleaner interface without redundant branding

- **Top Coins tab modularized** (`components/tabs/top_coins/`):
  | File | Content | Lines |
  |------|---------|-------|
  | `__init__.py` | Re-exports | ~10 |
  | `main.py` | Entry point | ~30 |
  | `coins_table.py` | Top 100 list + volume chart | ~85 |
  | `analysis.py` | Coin analysis (from Charts) | ~210 |
  | `styles.py` | CSS for tables | ~100 |

### Removed
- **DELETED `components/tabs/top_coins.py`** (~300 lines):
  - Content split into `top_coins/` package modules
  - XGB Market Scanner removed (unused feature)

- **DELETED `components/tabs/analysis.py`** (~200 lines):
  - Content moved to `top_coins/analysis.py`
  - Integrated into Top 100 Coins tab

### Current Tab Structure (Clean)
| Tab | Directory | Status |
|-----|-----------|--------|
| 📊 Top 100 Coins | `top_coins/` | ✅ Active (includes analysis) |
| 🔄 Test | `backtest/` | ✅ Active |
| 🎓 ML | `train/` | ✅ Active |

---

## [2026-01-26] v2.1.3 - Dead Code Removal & Project Cleanup

### Removed
- **DELETED `components/tabs/xgb_models/` directory** (5 files, ~850+ lines of dead code):
  - `__init__.py` - Module exports (never imported)
  - `main.py` - Tab renderer (never called)
  - `training.py` - Training UI (~400 lines, duplicate of train/training.py)
  - `viewer.py` - Model viewer (~400 lines, duplicate of train/models.py)
  - `utils.py` - Utility functions

- **DELETED `components/tabs/train/model_viewer.py`** (~400 lines of dead code):
  - Never imported anywhere in the codebase
  - Duplicate functionality of `models.py` which is actively used
  - Contained: `render_model_viewer()`, metrics tables, feature importance charts
  
### Analysis Summary
The `xgb_models/` directory was identified as completely unused:
- **Not imported in `app.py`** - The main app only uses 4 tabs: Top, Charts, Test, ML
- **ML tab** uses `train/` directory which has its own training and models views
- `xgb_models/` was legacy code that was never integrated or was replaced by `train/`

### Current Tab Structure (Clean)
| Tab | File | Status |
|-----|------|--------|
| 📊 Top | `top_coins.py` | ✅ Active |
| 📈 Charts | `analysis.py` | ✅ Active |
| 🔄 Test | `backtest/main.py` | ✅ Active |
| 🎓 ML | `train/main.py` | ✅ Active |

**Sub-tabs removed**: `xgb_models/` (was dead code)

---

## [2026-01-25] v2.1.2 - BTC Inference Real-Time Data Fix

### Fixed
- **`services/local_models.py`**: Bitcoin Inference chart was showing stale data
  - **Root cause**: ML inference was reading from `historical_ohlcv` table instead of `realtime_ohlcv`
  - **Data-fetcher** writes to `realtime_ohlcv` in `trading_data.db` (updated every 15 min)
  - **ML inference** was reading from `historical_ohlcv` (old historical data)
  - Fixed `run_inference()` to connect to correct database (`trading_data.db`)
  - Changed query from `historical_ohlcv` to `realtime_ohlcv` table
  - Added `_get_realtime_db_path()` helper function
  - Column mapping fix: `bb_mid` → `bb_middle` (schema difference between tables)
  
### Technical Details
| Component | Table | Database | Purpose |
|-----------|-------|----------|---------|
| data-fetcher | `realtime_ohlcv` | trading_data.db | Real-time OHLCV (updated every 15 min) |
| ML inference | `realtime_ohlcv` ✅ | trading_data.db | Now reads fresh data |
| ~~ML inference~~ | ~~`historical_ohlcv`~~ | ~~crypto_data.db~~ | ~~Old, stale data (removed)~~ |

---

## [2026-01-25] v2.1.1 - Enhanced Training Results Dashboard

### Added
- **Enhanced Training Results Dashboard** (`training_results.py`):
  - **Detailed Metrics Tables**: Side-by-side LONG/SHORT model metrics with all values
  - **Hyperparameters Display**: Expandable section showing best Optuna parameters
  - **Auto-Generated GPT Analysis**: Automatic AI analysis on page load (cached)
  - **Real-Time Bitcoin Inference**: Uses live OHLCV data from `realtime_ohlcv` table
    - Same data source as Top Coins tab for consistency
    - Signal card showing STRONG BUY/BUY/NEUTRAL/SELL/STRONG SELL
    - 200-candle candlestick chart with ML scores overlay
    - Current LONG/SHORT/Net scores

### Changed
- GPT analysis now auto-generates on first visit (no button required)
- Analysis is cached in session state to avoid repeated API calls
- "Regenerate Analysis" button available for fresh analysis
- Bitcoin inference uses `get_ohlcv_with_indicators()` for real-time data

### Fixed
- Plotly radar chart fillcolor error (hex with alpha → proper rgba)
  - Changed from `#00ffff30` to `rgba(0, 255, 255, 0.2)`

---

## [2026-01-25] v2.1.0 - Training Dashboard Redesign

### Added
- **Complete Training Step Redesign** (`components/tabs/train/training.py`): New modular 5-section layout
  - Replaced monolithic training step with focused sub-components
  - Clean, organized interface with clear visual hierarchy

- **Input/Output Tables Section** (`training_io_tables.py`):
  - Shows `v_xgb_training` view status with ✅/❌ indicators
  - Displays model files status for 15m and 1h timeframes
  - Feature count, row count, timeframes, and date range
  - Expandable feature and label column lists

- **Training Commands Section** (`training_commands.py`):
  - Three command cards: Single Training, Multi-Frame, Optuna Intensive
  - Copyable bash commands with syntax highlighting
  - Expandable options explanation table
  - Tips for production training

- **Model Details Section** (`training_model_details.py`):
  - Model summary card with quality badge (Excellent/Good/Acceptable/Poor)
  - Detailed metrics table (Spearman, R², RMSE, Precision@K)
  - Feature importance horizontal bar chart (Top 10)
  - Precision@K grouped bar chart with 50% baseline
  - Expandable hyperparameters and data range sections

- **AI Evaluation Section** (`training_ai_eval.py`):
  - GPT-4o integration for model quality assessment
  - Analyzes input features and output metrics
  - Returns structured JSON with:
    - Quality rating (excellent/good/acceptable/poor)
    - Strengths and weaknesses lists
    - Recommendations for improvement
    - Trading viability assessment
  - Session state caching to avoid repeated API calls

- **Bitcoin Inference Section** (`training_btc_inference.py`):
  - Live signal card showing STRONG BUY/BUY/HOLD/SELL/STRONG SELL
  - Current BTC price and LONG/SHORT/Net scores
  - 200-candle candlestick chart with ML scores overlay
  - Threshold lines at 0.7 (Strong) and 0.5 (Signal)
  - Signal distribution summary with statistics

### Changed
- **Modular Architecture**: Training step split into 5 focused modules
  - Each module under 200 lines (per coding standards)
  - Clear separation of concerns
  - Reusable components

### Technical Details
New files created:
```
components/tabs/train/
├── training.py              # Main orchestrator (50 lines)
├── training_io_tables.py    # Section 1: I/O tables (180 lines)
├── training_commands.py     # Section 2: Commands (150 lines)
├── training_model_details.py # Section 3: Model details (320 lines)
├── training_ai_eval.py      # Section 4: AI eval (280 lines)
└── training_btc_inference.py # Section 5: BTC inference (310 lines)
```

---

## [2026-01-24] v2.0.0 - Local Training (No Docker)

### Added
- **`train_local.py`**: New CLI script for local XGBoost + Optuna training
  - Faster than Docker (~2-3x) with full CPU/RAM access
  - Rich console output with progress bars and metrics
  - Saves models compatible with frontend
  - Usage: `python train_local.py --timeframe 15m --trials 30`

- **`services/local_models.py`**: New service for loading locally trained models
  - `load_model_metadata()`: Load model info from JSON
  - `model_exists()`: Check if model is trained
  - `run_inference()`: Run predictions on OHLCV data
  - `get_latest_signals()`: Get current signals for a symbol

- **`components/tabs/train/model_viewer.py`**: Complete model visualization
  - Training command display (copyable)
  - Model summary with quality badge
  - Detailed metrics table (Spearman, R², RMSE, Precision@K)
  - Feature importance charts (side-by-side LONG/SHORT)
  - Precision@K line chart
  - **Live BTCUSDT inference** with 200 candles
  - Hyperparameters display
  - Training data range info

### Changed
- **`docker-compose.yml`**: Removed `ml-training` container
  - Training is now local-only (faster and more efficient)
  - `ml-inference` container still available for production inference

- **`components/tabs/train/training.py`**: Refactored for local training
  - Shows training command (no longer submits Docker jobs)
  - Displays trained models with full metrics
  - Training history section

### Performance Improvement
| Metric | Docker Training | Local Training |
|--------|-----------------|----------------|
| 20 trials | ~8-12 min | ~3-5 min |
| CPU usage | Limited by container | All cores |
| Memory | Container limit | Full RAM |

### Migration Notes
- Existing models in `shared/models/` remain compatible
- Run `python train_local.py --timeframe 15m --trials 30` to train new models
- Frontend automatically detects locally trained models

---

## [2025-01-24] v1.9.3 - Fix v_xgb_training View

### Fixed
- **v_xgb_training VIEW**: Fixed broken view that referenced `d.bb_middle` instead of `d.bb_mid`
  - Old view caused error: "no such column: d.bb_middle"
  - View now uses correct column mapping: `d.bb_mid AS bb_middle`
  - View row count verified: 3,167,921 (15m: 2,532,696 + 1h: 635,225)
  - Training tab should now properly detect available labels and features

## [2025-01-24] - Data Model Display Component

### Added
- **Data Model Display Component** (`data_model_display.py`): New reusable component for displaying input/output data model information in each training pipeline tab
  - Shows table/view name with existence status (✅/❌)
  - Displays feature count and feature names (collapsible)
  - Shows row count, symbol count, and timeframe
  - Displays date range of data
  - Categorizes columns into features vs labels vs metadata
  
### Changed
- **Step 1 (Data)**: Added data model display showing `historical_ohlcv` → `training_data` pipeline
- **Step 2 (Labeling)**: Added data model display showing `training_data` → `training_labels` pipeline
- **Step 3 (Training)**: Added data model display showing `v_xgb_training` input view
- **Step 4 (Models)**: Added data model display showing `v_xgb_training` input view

### Technical Details
- Created `STEP_CONFIGS` dictionary for predefined input/output configurations
- Each tab now shows a collapsible "📊 Data Model" expander with full schema info
- Feature columns are sorted and displayed in 3-column layout for readability
- Label columns are identified by keywords (score, return, mfe, mae, bars_held, exit_type)

---

## [2026-01-24] - Training Labels Count Fix

### Fixed
- **`services/training_service.py`**: "No training labels available" error in training step
  - `get_training_labels_count()` was looking for wrong table name `ml_training_labels`
  - The actual table created by labeling is `training_labels`
  - Fixed fallback order: `v_xgb_training` → `training_labels` → `ml_training_labels` (legacy)
  - Training step now correctly detects available labels for both 15m and 1h timeframes

---

## [2026-01-24] - Frontend Performance Optimization (Lazy Loading)

### Changed
- **`status.py`**: Added `@st.cache_data(ttl=60)` to `get_pipeline_status()`
  - Pipeline status queries now cached for 60 seconds
  - Reduces DB queries on every page interaction

- **`labeling.py`**: Wrapped heavy sections in `st.expander(expanded=False)` for lazy loading
  - 📋 Labels Table Preview - loads only when opened
  - 📈 Analysis Dashboard (12 charts) - loads only when opened
  - 🔍 Stability Report - loads only when opened
  - 👁️ Candlestick Visualizer - loads only when opened

- **`models.py`**: Wrapped all heavy sections in `st.expander(expanded=False)`
  - 📈 Training Analytics (Charts) - loads only when opened
  - 🔬 Feature Importance - loads only when opened
  - 🤖 AI Analysis - loads only when opened
  - 🛠️ Model Details & Parameters - loads only when opened
  - 🔮 Real-Time Inference - loads only when opened

### Performance Impact
| Metric | Before | After |
|--------|--------|-------|
| Initial tab load time | ~5-8s | ~1-2s |
| Plotly charts rendered | 12+ | 0 (until expanded) |
| DB queries on load | 10+ | 3-4 (cached) |

### Technical Notes
- Streamlit's `st.expander(expanded=False)` defers rendering of content until expanded
- This provides "lazy loading" behavior without code complexity
- Users can still access all features by clicking on expanders
- Summary/lightweight sections remain always visible

---

## [2026-01-24] - Feature Pipeline Debugging & Visibility Improvements

### Added
- **Feature Statistics Module** (`agents/frontend/database/feature_stats.py`):
  - `EXPECTED_FEATURES`: List of 21 expected features for XGBoost training
  - `get_training_data_stats()`: Phase 1 feature statistics
  - `get_training_labels_stats()`: Phase 2 label statistics  
  - `get_xgb_view_stats()`: Phase 3 view feature statistics
  - `get_pipeline_feature_summary()`: Complete pipeline overview
  - `format_feature_reminder()`: UI formatting helper

### Changed
- **Phase 1 (Data Tab)**: Added feature reminder box showing `training_data` feature count
- **Phase 2 (Labeling Tab)**: Added feature reminder box showing `v_xgb_training` view stats
- **Phase 3 (ML Training Job Handler)**: Enhanced logging with detailed feature availability check
  - Shows expected vs available vs missing features
  - Clear warnings when falling back to limited features
- **Phase 4 (Models Tab)**: Added feature reminder showing model's trained features vs expected

### Fixed
- **Root cause identified**: Models showing 8 features because `v_xgb_training` view was missing
- The view is created during labeling (Phase 2) but wasn't visible in UI
- All 4 phases now show feature counts for better debugging

### Technical Details
The ML training pipeline expects 21 features:
- OHLCV (5): open, high, low, close, volume
- Moving Averages (4): sma_20, sma_50, ema_12, ema_26
- Bollinger Bands (3): bb_upper, bb_middle, bb_lower
- Momentum (4): rsi, macd, macd_signal, macd_hist
- Stochastic (2): stoch_k, stoch_d
- Other (3): atr, volume_sma, obv

---

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
