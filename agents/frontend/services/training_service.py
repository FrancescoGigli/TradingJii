"""
🚂 Training Service - Job Submission & Monitoring

Simplified service for frontend - NO training logic here.
Training is handled by the ml-training container.

Provides:
- submit_training_job(): Submit a training request to the queue
- get_job_status(): Get current status of a training job
- get_active_jobs(): Get all running/pending jobs
- load_model_metadata(): Load completed model info
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from database.training_jobs import (
    TrainingJob,
    submit_training_job as db_submit_job,
    get_job_status as db_get_job_status,
    get_active_job,
    get_recent_jobs,
    cancel_job,
    get_latest_completed_job,
    ensure_training_jobs_table
)


@dataclass
class TrainingResult:
    """Container for training result display."""
    success: bool
    timeframe: str
    version: str
    metrics_long: Dict[str, Any]
    metrics_short: Dict[str, Any]
    n_features: int
    n_train: int
    n_test: int
    best_params_long: Dict[str, Any]
    best_params_short: Dict[str, Any]
    error: str = ""


def get_model_dir() -> Path:
    """Get model directory path."""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    return Path(shared_path) / "models"


def submit_training_request(
    timeframe: str,
    n_trials: int = 30,
    train_ratio: float = 0.8
) -> Optional[int]:
    """
    Submit a training job request.
    
    The ml-training container will pick this up and execute it.
    
    Args:
        timeframe: '15m' or '1h'
        n_trials: Number of Optuna trials
        train_ratio: Train/test split ratio
    
    Returns:
        Job ID if successful, None otherwise
    """
    ensure_training_jobs_table()
    return db_submit_job(timeframe, n_trials, train_ratio)


def get_training_job_status(job_id: int) -> Optional[TrainingJob]:
    """
    Get current status of a training job.
    
    Args:
        job_id: Job ID
    
    Returns:
        TrainingJob object with progress info
    """
    return db_get_job_status(job_id)


def get_active_training_job(timeframe: str = None) -> Optional[TrainingJob]:
    """
    Get active (pending or running) job.
    
    Args:
        timeframe: Filter by timeframe, or None for any
    
    Returns:
        TrainingJob or None
    """
    return get_active_job(timeframe)


def get_training_history(limit: int = 10) -> List[TrainingJob]:
    """
    Get recent training jobs.
    
    Args:
        limit: Max jobs to return
    
    Returns:
        List of TrainingJob objects
    """
    return get_recent_jobs(limit)


def cancel_training_job(job_id: int) -> bool:
    """
    Request cancellation of a training job.
    
    Args:
        job_id: Job ID
    
    Returns:
        True if cancellation requested
    """
    return cancel_job(job_id)


def load_model_metadata(timeframe: str) -> Optional[Dict[str, Any]]:
    """
    Load metadata from the latest trained model.
    
    Args:
        timeframe: '15m' or '1h'
    
    Returns:
        Metadata dict or None
    """
    model_dir = get_model_dir()
    metadata_file = model_dir / f"metadata_{timeframe}_latest.json"
    
    if not metadata_file.exists():
        return None
    
    try:
        with open(metadata_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading metadata for {timeframe}: {e}")
        return None


def get_training_result_from_metadata(timeframe: str) -> Optional[TrainingResult]:
    """
    Convert metadata to TrainingResult for display.
    
    Args:
        timeframe: '15m' or '1h'
    
    Returns:
        TrainingResult or None
    """
    metadata = load_model_metadata(timeframe)
    if not metadata:
        return None
    
    return TrainingResult(
        success=True,
        timeframe=timeframe,
        version=metadata.get('version', 'Unknown'),
        metrics_long=metadata.get('metrics_long', {}),
        metrics_short=metadata.get('metrics_short', {}),
        n_features=metadata.get('n_features', 0),
        n_train=metadata.get('n_train_samples', 0),
        n_test=metadata.get('n_test_samples', 0),
        best_params_long=metadata.get('best_params_long', {}),
        best_params_short=metadata.get('best_params_short', {}),
        error=''
    )


def model_exists(timeframe: str) -> bool:
    """
    Check if a trained model exists for a timeframe.
    
    Args:
        timeframe: '15m' or '1h'
    
    Returns:
        True if model files exist
    """
    model_dir = get_model_dir()
    model_file = model_dir / f"model_long_{timeframe}_latest.pkl"
    return model_file.exists()


def get_training_labels_count(timeframe: str) -> int:
    """
    Get count of training labels for a timeframe.
    
    Args:
        timeframe: '15m' or '1h'
    
    Returns:
        Count of labels
    """
    from database import get_connection
    
    conn = get_connection()
    if not conn:
        return 0
    
    try:
        cur = conn.cursor()
        
        # Try v_xgb_training view first
        try:
            cur.execute('SELECT COUNT(*) FROM v_xgb_training WHERE timeframe=?', (timeframe,))
            return cur.fetchone()[0]
        except:
            pass
        
        # Fallback to ml_training_labels
        cur.execute('SELECT COUNT(*) FROM ml_training_labels WHERE timeframe=?', (timeframe,))
        return cur.fetchone()[0]
    except:
        return 0
    finally:
        conn.close()


# Singleton service (for compatibility)
class TrainingService:
    """
    Simplified training service for frontend.
    Just submits jobs and monitors progress.
    """
    
    def submit_job(
        self,
        timeframe: str,
        n_trials: int = 30,
        train_ratio: float = 0.8
    ) -> Optional[int]:
        """Submit a training job request."""
        return submit_training_request(timeframe, n_trials, train_ratio)
    
    def get_status(self, job_id: int) -> Optional[TrainingJob]:
        """Get job status."""
        return get_training_job_status(job_id)
    
    def get_active(self, timeframe: str = None) -> Optional[TrainingJob]:
        """Get active job."""
        return get_active_training_job(timeframe)
    
    def cancel(self, job_id: int) -> bool:
        """Cancel a job."""
        return cancel_training_job(job_id)
    
    def load_metadata(self, timeframe: str) -> Optional[Dict[str, Any]]:
        """Load model metadata."""
        return load_model_metadata(timeframe)


_training_service: Optional[TrainingService] = None


def get_training_service() -> TrainingService:
    """Get singleton training service."""
    global _training_service
    if _training_service is None:
        _training_service = TrainingService()
    return _training_service


__all__ = [
    'TrainingResult',
    'TrainingService',
    'get_training_service',
    'submit_training_request',
    'get_training_job_status',
    'get_active_training_job',
    'get_training_history',
    'cancel_training_job',
    'load_model_metadata',
    'get_training_result_from_metadata',
    'model_exists',
    'get_training_labels_count'
]
