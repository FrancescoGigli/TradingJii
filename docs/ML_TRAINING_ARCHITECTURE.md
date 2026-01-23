# ML Training Architecture

## Overview

The ML training system has been refactored to separate concerns:
- **Frontend (Streamlit)**: UI only - submits jobs and displays progress
- **ML-Training Container**: Handles heavy computation (XGBoost + Optuna)

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       FRONTEND CONTAINER                         │
│  (Streamlit)                                                     │
│                                                                  │
│  ┌─────────────────┐    ┌────────────────────────────────────┐  │
│  │ "Start Training"│───►│ INSERT INTO training_jobs          │  │
│  │    Button       │    │ (status='pending')                 │  │
│  └─────────────────┘    └────────────────────────────────────┘  │
│                                       │                          │
│  ┌─────────────────┐                  │                          │
│  │ Progress Bar    │◄─────────────────┼──── Poll every 3s       │
│  │ Trial Log       │    SELECT * FROM training_jobs WHERE id=?  │
│  │ Best Scores     │                                             │
│  └─────────────────┘                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ SQLite DB (shared volume)
                              │
┌─────────────────────────────────────────────────────────────────┐
│                     ML-TRAINING CONTAINER                        │
│  (Python daemon)                                                 │
│                                                                  │
│  ┌─────────────────┐    ┌────────────────────────────────────┐  │
│  │ Poll every 30s  │───►│ SELECT * FROM training_jobs        │  │
│  │ for pending     │    │ WHERE status='pending' LIMIT 1     │  │
│  └─────────────────┘    └────────────────────────────────────┘  │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ XGBoost +       │    ┌────────────────────────────────────┐  │
│  │ Optuna Training │───►│ UPDATE training_jobs               │  │
│  │ (LONG + SHORT)  │    │ SET progress_pct=?, current_trial=?│  │
│  └─────────────────┘    └────────────────────────────────────┘  │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │ Save Models     │──► /shared/models/                         │
│  │ Save Metadata   │    - model_long_15m_latest.pkl             │
│  │ Mark Complete   │    - model_short_15m_latest.pkl            │
│  └─────────────────┘    - metadata_15m_latest.json              │
└─────────────────────────────────────────────────────────────────┘
```

## Database Schema

### training_jobs Table

```sql
CREATE TABLE training_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timeframe TEXT NOT NULL,          -- '15m' or '1h'
    n_trials INTEGER DEFAULT 30,      -- Optuna trials per model
    train_ratio REAL DEFAULT 0.8,     -- Train/test split
    status TEXT DEFAULT 'pending',    -- pending/running/completed/failed/cancelled
    progress_pct REAL DEFAULT 0,      -- 0-100
    current_trial INTEGER DEFAULT 0,  -- Current trial number
    total_trials INTEGER DEFAULT 0,   -- Total trials (n_trials * 2)
    current_model TEXT,               -- 'LONG' or 'SHORT'
    best_score_long REAL,             -- Best Spearman for LONG
    best_score_short REAL,            -- Best Spearman for SHORT
    trial_log TEXT,                   -- JSON array of trial results
    error TEXT,                       -- Error message if failed
    model_version TEXT,               -- Version string when completed
    requested_at TEXT NOT NULL,       -- ISO timestamp
    started_at TEXT,                  -- ISO timestamp
    completed_at TEXT                 -- ISO timestamp
);
```

## Data Flow

### 1. Job Submission (Frontend)

```python
# User clicks "Start Training" button
job_id = submit_training_request(
    timeframe='15m',
    n_trials=30,
    train_ratio=0.8
)
# Inserts row with status='pending'
```

### 2. Job Pickup (ML-Training Container)

```python
# Daemon polls every 30 seconds
job = get_pending_job()  
# SELECT ... WHERE status='pending' ORDER BY requested_at LIMIT 1

# Mark as running
mark_job_running(job_id, total_trials=60)  # 30 LONG + 30 SHORT
```

### 3. Training Execution

```python
# For each Optuna trial
def on_trial_complete(trial_num, model, spearman):
    update_job_progress(
        job_id=job_id,
        current_trial=trial_num,
        current_model=model,  # 'LONG' or 'SHORT'
        best_score_long=best_long,
        best_score_short=best_short,
        trial_result={
            'trial': trial_num,
            'model': model,
            'spearman': spearman,
            'params': {...}
        }
    )
```

### 4. Progress Monitoring (Frontend)

```python
# Streamlit polls every 3 seconds
job = get_training_job_status(job_id)
# Displays:
# - Progress bar (job.progress_pct)
# - Current trial (job.current_trial / job.total_trials)
# - Best scores (job.best_score_long, job.best_score_short)
# - Trial log (job.trial_log)
```

### 5. Completion

```python
# ML-Training saves models
save_models(model_long, model_short, scaler, metadata)
# Files saved to /shared/models/

# Mark job complete
mark_job_completed(job_id, version='15m_20260123_140000')
```

## File Structure

```
agents/
├── ml-training/
│   ├── Dockerfile
│   ├── main.py              # Daemon entry point
│   ├── requirements.txt
│   └── core/
│       ├── __init__.py
│       ├── database.py      # Job queue operations
│       ├── job_handler.py   # Training execution
│       ├── dataset.py       # (existing)
│       └── trainer.py       # (existing)
│
├── frontend/
│   ├── database/
│   │   └── training_jobs.py # Job CRUD operations
│   ├── services/
│   │   └── training_service.py  # Simplified (no XGBoost)
│   └── components/tabs/train/
│       └── training.py      # UI with progress monitoring
```

## Docker Services

### docker-compose.yml

```yaml
ml-training:
  build: ./agents/ml-training
  volumes:
    - shared-data:/app/shared
  environment:
    - SHARED_DATA_PATH=/app/shared
    - TRAINING_POLL_INTERVAL=30
    - LOG_LEVEL=INFO
  depends_on:
    - historical-data
```

## Key Benefits

1. **Separation of Concerns**: Frontend handles UI, ML-Training handles computation
2. **Non-Blocking UI**: Training runs in background, UI remains responsive
3. **Real-Time Progress**: Frontend polls for updates, shows live progress
4. **Cancellation Support**: Users can cancel running jobs
5. **Job History**: Track past training jobs and their status
6. **Scalability**: Can add more training containers if needed

## Usage

### Start Training

1. Go to ML Training tab in Streamlit
2. Select timeframe (15m or 1h)
3. Configure number of trials
4. Click "Start Training"
5. Watch progress bar update in real-time

### Monitor Training

- Progress bar shows overall completion
- Current trial number displayed
- Best Spearman scores shown for LONG and SHORT
- Trial log available in expandable section

### Cancel Training

- Click "Cancel" button to request cancellation
- Training will stop after current trial completes

## Troubleshooting

### Training Stuck at "Pending"

1. Check if ml-training container is running:
   ```bash
   docker-compose ps ml-training
   ```

2. Check ml-training logs:
   ```bash
   docker-compose logs -f ml-training
   ```

### No Training Data

Ensure labels have been generated in Step 2 (Labeling) before training.

### Database Locked

Both containers access the same SQLite database. WAL mode is enabled to allow concurrent reads. If issues persist, check for hung processes.
