# 🚀 Local Training Guide

This guide explains how to train XGBoost models locally without Docker.

## Overview

Local training provides significant performance benefits:
- **2-3x faster** than Docker-based training
- **Full CPU/RAM access** - no container limits
- **Rich console output** - real-time progress and metrics
- **Compatible** with the Streamlit frontend

## Prerequisites

1. Python 3.10+ with required packages:
   ```bash
   pip install xgboost optuna scikit-learn pandas numpy tqdm scipy
   ```

2. Training data available in `shared/crypto_data.db`:
   - Complete Step 1 (Data) to load OHLCV data
   - Complete Step 2 (Labeling) to generate training labels

## Usage

### Basic Training

```bash
# Train 15m model with 30 Optuna trials
python train_local.py --timeframe 15m --trials 30

# Train 1h model with 20 trials
python train_local.py --timeframe 1h --trials 20
```

### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--timeframe` | `-t` | Required | `15m` or `1h` |
| `--trials` | `-n` | 20 | Number of Optuna trials (10-50 recommended) |
| `--train-ratio` | | 0.8 | Train/test split ratio |
| `--output-dir` | `-o` | `shared/models` | Custom output directory |
| `--verbose` | `-v` | False | Show detailed feature info |

### Examples

```bash
# Verbose mode with custom trials
python train_local.py -t 15m -n 25 --verbose

# Custom output directory
python train_local.py -t 1h -n 30 -o ./my_models

# Quick test with few trials
python train_local.py -t 15m -n 10
```

## Output

### Console Output

The script provides rich console output:

```
╔══════════════════════════════════════════════════════════════════╗
║              🚀 LOCAL ML TRAINING (No Docker)                    ║
╚══════════════════════════════════════════════════════════════════╝

⚙️  Configuration:
   Timeframe: 15m
   Trials: 30
   Train ratio: 0.8

📊 Loading 15m data...
✅ Loaded 2,532,696 samples with 21 features

📈 Data Summary:
   Total samples: 2,532,696
   Features: 21
   Date range: 2024-01-01 → 2025-01-24
   Symbols: 100

==================================================
📈 Training LONG Model (30 trials)
==================================================
LONG: 100%|████████████████████████| 30/30 [04:23<00:00, spearman=0.1823, best=0.1892]

✅ LONG Model Results:
   Spearman: 0.1892
   R²: 0.0342
   Top1% Positive: 78.5%

==================================================
📉 Training SHORT Model (30 trials)
==================================================
SHORT: 100%|███████████████████████| 30/30 [04:18<00:00, spearman=0.1756, best=0.1801]

✅ SHORT Model Results:
   Spearman: 0.1801
   R²: 0.0298
   Top1% Positive: 75.2%

💾 Saving Models
==================================================
   ✅ model_long_15m_latest.pkl
   ✅ model_short_15m_latest.pkl
   ✅ scaler_15m_latest.pkl
   ✅ metadata_15m_latest.json

🎉 TRAINING COMPLETE!
==================================================

📊 Final Results:
   ┌─────────────┬──────────┬──────────┐
   │ Metric      │   LONG   │  SHORT   │
   ├─────────────┼──────────┼──────────┤
   │ Spearman    │  0.1892  │  0.1801  │
   │ R²          │  0.0342  │  0.0298  │
   │ Top1% Pos   │  78.5%   │  75.2%   │
   │ Top5% Pos   │  68.3%   │  65.1%   │
   └─────────────┴──────────┴──────────┘

⏱️  Duration: 8.7 minutes

🔝 Top 5 Features (LONG):
   1. close           █████████████████████ 0.142
   2. rsi             ████████████████ 0.108
   3. volume          ██████████████ 0.095
   4. macd_hist       ████████████ 0.082
   5. bb_middle       ██████████ 0.071
```

### Output Files

Models are saved to `shared/models/`:

```
shared/models/
├── model_long_15m_latest.pkl       # Latest LONG model
├── model_short_15m_latest.pkl      # Latest SHORT model
├── scaler_15m_latest.pkl           # Feature scaler
├── metadata_15m_latest.json        # Complete metadata
├── model_long_15m_20260124_*.pkl   # Versioned backup
└── ...
```

### Metadata JSON

The metadata file contains all training details:

```json
{
  "version": "15m_20260124_130000",
  "created_at": "2026-01-24T13:00:00",
  "timeframe": "15m",
  "training_mode": "local",
  "n_features": 21,
  "n_train_samples": 2026156,
  "n_test_samples": 506540,
  "training_duration_seconds": 523.4,
  "feature_names": ["open", "high", "low", "close", ...],
  "metrics_long": {
    "test_r2": 0.0342,
    "test_rmse": 0.0891,
    "test_mae": 0.0654,
    "ranking": {
      "spearman_corr": 0.1892,
      "top1pct_positive": 78.5,
      "top5pct_positive": 68.3,
      "top10pct_positive": 62.1,
      "top20pct_positive": 57.8
    }
  },
  "metrics_short": {...},
  "feature_importance_long": {"close": 0.142, "rsi": 0.108, ...},
  "feature_importance_short": {...},
  "best_params_long": {...},
  "best_params_short": {...},
  "data_range": {
    "train_start": "2024-01-01 00:00:00",
    "train_end": "2025-10-18 12:00:00",
    "test_start": "2025-10-18 12:15:00",
    "test_end": "2026-01-24 12:00:00"
  }
}
```

## Frontend Integration

After training, the frontend automatically detects the new model:

1. **Start the frontend:**
   ```bash
   docker-compose up -d frontend
   ```

2. **Open the dashboard:**
   ```
   http://localhost:8501
   ```

3. **Go to Train tab:**
   - Model details displayed automatically
   - Metrics, feature importance, precision@K charts
   - Live inference on BTCUSDT

## Features Used

The model uses 21 features:

| Category | Features |
|----------|----------|
| **OHLCV** (5) | open, high, low, close, volume |
| **Moving Averages** (4) | sma_20, sma_50, ema_12, ema_26 |
| **Bollinger Bands** (3) | bb_upper, bb_middle, bb_lower |
| **Momentum** (4) | rsi, macd, macd_signal, macd_hist |
| **Stochastic** (2) | stoch_k, stoch_d |
| **Other** (3) | atr, volume_sma, obv |

## Troubleshooting

### "Database not found"

Ensure the database exists at `shared/crypto_data.db`:
```bash
# Check if database exists
ls -la shared/crypto_data.db

# If missing, run data fetch first
docker-compose up -d data-fetcher historical-data
```

### "No training data found"

Complete the labeling step first:
1. Go to frontend → Train tab → Step 2 (Labeling)
2. Generate training labels
3. Re-run training

### "Not enough samples"

Need at least 100 samples for training. Check:
```bash
python -c "import sqlite3; conn = sqlite3.connect('shared/crypto_data.db'); print(conn.execute('SELECT timeframe, COUNT(*) FROM ml_training_labels GROUP BY timeframe').fetchall())"
```

### Memory Issues

For large datasets, consider:
- Reduce `--trials` to 10-15
- Train one timeframe at a time
- Close other applications

## Performance Comparison

| Metric | Docker Training | Local Training |
|--------|-----------------|----------------|
| 20 trials | ~8-12 min | ~3-5 min |
| 30 trials | ~12-18 min | ~5-8 min |
| CPU utilization | ~50% (limited) | 100% (all cores) |
| Memory usage | Container limit | Full RAM |

## Best Practices

1. **Start with fewer trials** (10-15) for testing
2. **Use 30 trials** for production models
3. **Train both timeframes** for complete coverage:
   ```bash
   python train_local.py -t 15m -n 30
   python train_local.py -t 1h -n 30
   ```
4. **Check Spearman correlation** - aim for > 0.15
5. **Monitor Top1% Positive** - aim for > 65%
