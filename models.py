# models.py - Cleaned up to only contain XGBoost-related functionality
# All LSTM, RandomForest, and FocalLoss code removed as they're no longer used

import logging
from config import TIME_STEPS, EXPECTED_COLUMNS

# Note: This file now only contains documentation and constants since the system
# only uses XGBoost models. All model creation is handled directly in trainer.py
# to avoid redundant code and maintain clear separation of concerns.

# Keeping this file for potential future model additions and configuration consistency
