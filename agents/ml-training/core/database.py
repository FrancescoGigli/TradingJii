"""
📊 ML Training - Database Module

Database operations for the ml-training daemon.
Handles job queue and progress updates.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path


def get_db_path() -> str:
    """Get database path from environment."""
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    return f"{shared_path}/data_cache/trading_data.db"


def get_connection() -> Optional[sqlite3.Connection]:
    """Get database connection with proper settings."""
    db_path = get_db_path()
    
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}")
        return None
    
    try:
        conn = sqlite3.connect(db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None


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


def get_pending_job() -> Optional[Dict[str, Any]]:
    """
    Get the oldest pending job from the queue.
    
    Returns:
        Job dict or None if no pending jobs
    """
    conn = get_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT id, timeframe, n_trials, train_ratio
            FROM training_jobs 
            WHERE status = 'pending'
            ORDER BY requested_at ASC
            LIMIT 1
        ''')
        
        row = cur.fetchone()
        if not row:
            return None
        
        return {
            'id': row[0],
            'timeframe': row[1],
            'n_trials': row[2],
            'train_ratio': row[3]
        }
        
    except Exception as e:
        print(f"Error getting pending job: {e}")
        return None
    finally:
        conn.close()


def mark_job_running(job_id: int, total_trials: int) -> bool:
    """
    Mark a job as running.
    
    Args:
        job_id: Job ID
        total_trials: Total number of trials (LONG + SHORT)
    
    Returns:
        True if successful
    """
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE training_jobs 
            SET status = 'running', 
                started_at = ?,
                total_trials = ?,
                progress_pct = 0,
                current_trial = 0
            WHERE id = ?
        ''', (datetime.now().isoformat(), total_trials, job_id))
        
        conn.commit()
        return cur.rowcount > 0
        
    except Exception as e:
        print(f"Error marking job running: {e}")
        return False
    finally:
        conn.close()


def update_job_progress(
    job_id: int,
    current_trial: int,
    current_model: str,
    best_score_long: Optional[float] = None,
    best_score_short: Optional[float] = None,
    trial_result: Optional[Dict] = None
) -> bool:
    """
    Update job progress after a trial completes.
    
    Args:
        job_id: Job ID
        current_trial: Current trial number (1-indexed)
        current_model: 'LONG' or 'SHORT'
        best_score_long: Best Spearman for LONG model
        best_score_short: Best Spearman for SHORT model
        trial_result: Trial result dict to append to log
    
    Returns:
        True if successful
    """
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        # Get current trial log
        cur.execute('SELECT trial_log, total_trials FROM training_jobs WHERE id = ?', (job_id,))
        row = cur.fetchone()
        if not row:
            return False
        
        # Parse existing log
        trial_log = []
        if row[0]:
            try:
                trial_log = json.loads(row[0])
            except:
                trial_log = []
        
        total_trials = row[1] or 1
        
        # Append new trial result
        if trial_result:
            trial_log.append(trial_result)
        
        # Calculate progress percentage
        progress_pct = (current_trial / total_trials) * 100
        
        # Update job
        cur.execute('''
            UPDATE training_jobs 
            SET current_trial = ?,
                current_model = ?,
                progress_pct = ?,
                best_score_long = COALESCE(?, best_score_long),
                best_score_short = COALESCE(?, best_score_short),
                trial_log = ?
            WHERE id = ?
        ''', (
            current_trial, 
            current_model, 
            progress_pct,
            best_score_long,
            best_score_short,
            json.dumps(trial_log),
            job_id
        ))
        
        conn.commit()
        return cur.rowcount > 0
        
    except Exception as e:
        print(f"Error updating job progress: {e}")
        return False
    finally:
        conn.close()


def mark_job_completed(job_id: int, model_version: str) -> bool:
    """
    Mark a job as completed.
    
    Args:
        job_id: Job ID
        model_version: Version string of saved model
    
    Returns:
        True if successful
    """
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE training_jobs 
            SET status = 'completed',
                completed_at = ?,
                progress_pct = 100,
                model_version = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), model_version, job_id))
        
        conn.commit()
        return cur.rowcount > 0
        
    except Exception as e:
        print(f"Error marking job completed: {e}")
        return False
    finally:
        conn.close()


def mark_job_failed(job_id: int, error: str) -> bool:
    """
    Mark a job as failed.
    
    Args:
        job_id: Job ID
        error: Error message
    
    Returns:
        True if successful
    """
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE training_jobs 
            SET status = 'failed',
                completed_at = ?,
                error = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), error, job_id))
        
        conn.commit()
        return cur.rowcount > 0
        
    except Exception as e:
        print(f"Error marking job failed: {e}")
        return False
    finally:
        conn.close()


def is_job_cancelled(job_id: int) -> bool:
    """
    Check if a job has been cancelled.
    
    Args:
        job_id: Job ID
    
    Returns:
        True if cancelled
    """
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute('SELECT status FROM training_jobs WHERE id = ?', (job_id,))
        row = cur.fetchone()
        return row and row[0] == 'cancelled'
        
    except Exception as e:
        print(f"Error checking job status: {e}")
        return False
    finally:
        conn.close()


def get_training_data(timeframe: str) -> Optional[int]:
    """
    Get count of training labels for a timeframe.
    
    Args:
        timeframe: '15m' or '1h'
    
    Returns:
        Count of labels or None on error
    """
    conn = get_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        
        # Try v_xgb_training view first
        try:
            cur.execute('''
                SELECT COUNT(*) FROM v_xgb_training WHERE timeframe = ?
            ''', (timeframe,))
            return cur.fetchone()[0]
        except:
            pass
        
        # Fallback to ml_training_labels table
        cur.execute('''
            SELECT COUNT(*) FROM ml_training_labels WHERE timeframe = ?
        ''', (timeframe,))
        return cur.fetchone()[0]
        
    except Exception as e:
        print(f"Error getting training data count: {e}")
        return None
    finally:
        conn.close()


__all__ = [
    'get_db_path',
    'get_connection',
    'ensure_training_jobs_table',
    'get_pending_job',
    'mark_job_running',
    'update_job_progress',
    'mark_job_completed',
    'mark_job_failed',
    'is_job_cancelled',
    'get_training_data'
]
