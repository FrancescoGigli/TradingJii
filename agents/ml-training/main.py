#!/usr/bin/env python3
"""
🚀 ML Training Daemon

Polls the training_jobs table for pending jobs and executes them.
Updates progress in real-time for frontend monitoring.

Usage:
    python main.py              # Run as daemon (polls every 30s)
    python main.py --once       # Process one job and exit
"""

import os
import sys
import time
import signal
import argparse
from datetime import datetime

from core.database import (
    ensure_training_jobs_table,
    get_pending_job,
    get_training_data
)
from core.job_handler import run_training_job


# Configuration
POLL_INTERVAL = int(os.environ.get('TRAINING_POLL_INTERVAL', 30))
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

# Graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    print("\n⚠️ Shutdown signal received. Will stop after current job completes...")
    shutdown_requested = True


def print_banner():
    """Print startup banner."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                    🚂 ML TRAINING DAEMON                         ║
║                                                                  ║
║  Polls for training jobs and executes XGBoost + Optuna training  ║
║  Progress updates sent to database for frontend monitoring       ║
╚══════════════════════════════════════════════════════════════════╝
    """)


def check_database_ready() -> bool:
    """Check if database is ready for training."""
    # Ensure table exists
    if not ensure_training_jobs_table():
        print("❌ Could not create/verify training_jobs table")
        return False
    
    # Check for training data
    count_15m = get_training_data('15m')
    count_1h = get_training_data('1h')
    
    print(f"📊 Training data available:")
    print(f"   15m: {count_15m or 0:,} samples")
    print(f"   1h:  {count_1h or 0:,} samples")
    
    if (count_15m or 0) == 0 and (count_1h or 0) == 0:
        print("⚠️ No training data available yet")
    
    return True


def run_daemon():
    """Run the training daemon loop."""
    print_banner()
    
    print(f"⚙️ Configuration:")
    print(f"   Poll interval: {POLL_INTERVAL}s")
    print(f"   Log level: {LOG_LEVEL}")
    print(f"   Shared path: {os.environ.get('SHARED_DATA_PATH', '/app/shared')}")
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check database
    print("\n🔍 Checking database...")
    if not check_database_ready():
        print("❌ Database not ready. Exiting.")
        sys.exit(1)
    
    print(f"\n🚀 Starting daemon loop (polling every {POLL_INTERVAL}s)...")
    print("   Press Ctrl+C to stop gracefully\n")
    
    jobs_processed = 0
    
    while not shutdown_requested:
        try:
            # Check for pending job
            job = get_pending_job()
            
            if job:
                print(f"\n📬 Found pending job: {job}")
                
                # Execute training
                success = run_training_job(job)
                
                if success:
                    jobs_processed += 1
                    print(f"✅ Job completed. Total processed: {jobs_processed}")
                else:
                    print(f"❌ Job failed or was cancelled")
                
                # Small delay before checking for next job
                time.sleep(2)
            else:
                # No pending jobs, wait before polling again
                if LOG_LEVEL == 'DEBUG':
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No pending jobs, sleeping {POLL_INTERVAL}s...")
                
                # Sleep in small increments to allow for graceful shutdown
                for _ in range(POLL_INTERVAL):
                    if shutdown_requested:
                        break
                    time.sleep(1)
                    
        except Exception as e:
            print(f"❌ Error in daemon loop: {e}")
            time.sleep(10)  # Wait before retrying
    
    print(f"\n👋 Daemon stopped. Processed {jobs_processed} jobs total.")


def run_once():
    """Process one pending job and exit."""
    print_banner()
    
    print("🔍 Running in single-job mode...")
    
    if not check_database_ready():
        print("❌ Database not ready. Exiting.")
        sys.exit(1)
    
    job = get_pending_job()
    
    if not job:
        print("ℹ️ No pending jobs found.")
        return
    
    print(f"\n📬 Processing job: {job}")
    success = run_training_job(job)
    
    if success:
        print("✅ Job completed successfully!")
    else:
        print("❌ Job failed!")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='ML Training Daemon')
    parser.add_argument('--once', action='store_true', 
                       help='Process one job and exit')
    args = parser.parse_args()
    
    if args.once:
        run_once()
    else:
        run_daemon()


if __name__ == '__main__':
    main()
