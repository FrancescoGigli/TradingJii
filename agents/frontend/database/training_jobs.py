"""
📊 Training Jobs Database Module

CRUD operations for the training_jobs table.
Used by frontend to submit and monitor training requests.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from database.connection import get_connection


@dataclass
class TrainingJob:
    """Training job data container."""
    id: int
    timeframe: str
    n_trials: int
    train_ratio: float
    status: str
    progress_pct: float
    current_trial: int
    total_trials: int
    current_model: Optional[str]
    best_score_long: Optional[float]
    best_score_short: Optional[float]
    trial_log: Optional[List[Dict]]
    error: Optional[str]
    model_version: Optional[str]
    requested_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


def ensure_training_jobs_table():
    """Create training_jobs table if it doesn't exist."""
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS training_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timeframe TEXT NOT NULL,
                n_trials INTEGER DEFAULT 30,
                train_ratio REAL DEFAULT 0.8,
                status TEXT DEFAULT 'pending',
                progress_pct REAL DEFAULT 0,
                current_trial INTEGER DEFAULT 0,
                total_trials INTEGER DEFAULT 0,
                current_model TEXT,
                best_score_long REAL,
                best_score_short REAL,
                trial_log TEXT,
                error TEXT,
                model_version TEXT,
                requested_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            )
        ''')
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating training_jobs table: {e}")
        return False
    finally:
        conn.close()


def submit_training_job(
    timeframe: str,
    n_trials: int = 30,
    train_ratio: float = 0.8
) -> Optional[int]:
    """
    Submit a new training job request.
    
    Args:
        timeframe: '15m' or '1h'
        n_trials: Number of Optuna trials
        train_ratio: Train/test split ratio
    
    Returns:
        Job ID if successful, None otherwise
    """
    ensure_training_jobs_table()
    
    conn = get_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        
        # Check if there's already a pending/running job for this timeframe
        cur.execute('''
            SELECT id FROM training_jobs 
            WHERE timeframe = ? AND status IN ('pending', 'running')
        ''', (timeframe,))
        
        existing = cur.fetchone()
        if existing:
            print(f"Job already pending/running for {timeframe}: ID {existing[0]}")
            return existing[0]
        
        # Insert new job
        now = datetime.now().isoformat()
        cur.execute('''
            INSERT INTO training_jobs 
            (timeframe, n_trials, train_ratio, status, progress_pct, 
             current_trial, total_trials, requested_at)
            VALUES (?, ?, ?, 'pending', 0, 0, ?, ?)
        ''', (timeframe, n_trials, train_ratio, n_trials * 2, now))
        
        conn.commit()
        job_id = cur.lastrowid
        print(f"Submitted training job {job_id} for {timeframe}")
        return job_id
        
    except Exception as e:
        print(f"Error submitting training job: {e}")
        return None
    finally:
        conn.close()


def get_job_status(job_id: int) -> Optional[TrainingJob]:
    """
    Get current status of a training job.
    
    Args:
        job_id: Job ID to check
    
    Returns:
        TrainingJob object or None if not found
    """
    conn = get_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT id, timeframe, n_trials, train_ratio, status, progress_pct,
                   current_trial, total_trials, current_model, 
                   best_score_long, best_score_short, trial_log,
                   error, model_version, requested_at, started_at, completed_at
            FROM training_jobs WHERE id = ?
        ''', (job_id,))
        
        row = cur.fetchone()
        if not row:
            return None
        
        # Parse trial_log JSON
        trial_log = None
        if row[11]:
            try:
                trial_log = json.loads(row[11])
            except:
                trial_log = []
        
        return TrainingJob(
            id=row[0],
            timeframe=row[1],
            n_trials=row[2],
            train_ratio=row[3],
            status=row[4],
            progress_pct=row[5] or 0,
            current_trial=row[6] or 0,
            total_trials=row[7] or 0,
            current_model=row[8],
            best_score_long=row[9],
            best_score_short=row[10],
            trial_log=trial_log,
            error=row[12],
            model_version=row[13],
            requested_at=row[14],
            started_at=row[15],
            completed_at=row[16]
        )
        
    except Exception as e:
        print(f"Error getting job status: {e}")
        return None
    finally:
        conn.close()


def get_active_job(timeframe: str = None) -> Optional[TrainingJob]:
    """
    Get active (pending or running) job for a timeframe.
    
    Args:
        timeframe: Filter by timeframe, or None for any
    
    Returns:
        TrainingJob object or None
    """
    conn = get_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        
        if timeframe:
            cur.execute('''
                SELECT id FROM training_jobs 
                WHERE timeframe = ? AND status IN ('pending', 'running')
                ORDER BY requested_at DESC LIMIT 1
            ''', (timeframe,))
        else:
            cur.execute('''
                SELECT id FROM training_jobs 
                WHERE status IN ('pending', 'running')
                ORDER BY requested_at DESC LIMIT 1
            ''')
        
        row = cur.fetchone()
        if row:
            return get_job_status(row[0])
        return None
        
    except Exception as e:
        print(f"Error getting active job: {e}")
        return None
    finally:
        conn.close()


def get_recent_jobs(limit: int = 10) -> List[TrainingJob]:
    """
    Get recent training jobs.
    
    Args:
        limit: Maximum number of jobs to return
    
    Returns:
        List of TrainingJob objects
    """
    conn = get_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT id FROM training_jobs 
            ORDER BY requested_at DESC LIMIT ?
        ''', (limit,))
        
        jobs = []
        for row in cur.fetchall():
            job = get_job_status(row[0])
            if job:
                jobs.append(job)
        
        return jobs
        
    except Exception as e:
        print(f"Error getting recent jobs: {e}")
        return []
    finally:
        conn.close()


def cancel_job(job_id: int) -> bool:
    """
    Request cancellation of a training job.
    
    Args:
        job_id: Job ID to cancel
    
    Returns:
        True if cancellation requested, False otherwise
    """
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE training_jobs 
            SET status = 'cancelled', completed_at = ?
            WHERE id = ? AND status IN ('pending', 'running')
        ''', (datetime.now().isoformat(), job_id))
        
        conn.commit()
        return cur.rowcount > 0
        
    except Exception as e:
        print(f"Error cancelling job: {e}")
        return False
    finally:
        conn.close()


def get_latest_completed_job(timeframe: str) -> Optional[TrainingJob]:
    """
    Get the most recent completed job for a timeframe.
    
    Args:
        timeframe: '15m' or '1h'
    
    Returns:
        TrainingJob object or None
    """
    conn = get_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT id FROM training_jobs 
            WHERE timeframe = ? AND status = 'completed'
            ORDER BY completed_at DESC LIMIT 1
        ''', (timeframe,))
        
        row = cur.fetchone()
        if row:
            return get_job_status(row[0])
        return None
        
    except Exception as e:
        print(f"Error getting latest completed job: {e}")
        return None
    finally:
        conn.close()


__all__ = [
    'TrainingJob',
    'ensure_training_jobs_table',
    'submit_training_job',
    'get_job_status',
    'get_active_job',
    'get_recent_jobs',
    'cancel_job',
    'get_latest_completed_job'
]
