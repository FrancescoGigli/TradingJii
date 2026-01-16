"""
🎓 Train Tab - Unified ML Training Pipeline

Combines Data Fetching, Labeling, Training and Model Management
into a single streamlined workflow.

Steps:
1. Data - Fetch and clean historical data
2. Labeling - Generate trailing stop labels
3. Training - Train XGBoost models
4. Models - View and manage trained models
"""

from .main import render_train_tab

__all__ = ['render_train_tab']
