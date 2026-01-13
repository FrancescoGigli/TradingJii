"""
🤖 ML Inference Agent - Configuration
"""

import os

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

SHARED_DATA_PATH = os.environ.get('SHARED_DATA_PATH', '/app/shared')
DATABASE_PATH = f"{SHARED_DATA_PATH}/data_cache/trading_data.db"
MODELS_PATH = f"{SHARED_DATA_PATH}/models"

# ═══════════════════════════════════════════════════════════════════════════════
# INFERENCE SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

# How often to run inference (in seconds)
INFERENCE_INTERVAL = int(os.environ.get('INFERENCE_INTERVAL', 300))  # 5 minutes

# Timeframe to use for inference
INFERENCE_TIMEFRAME = os.environ.get('INFERENCE_TIMEFRAME', '15m')

# Number of candles needed for feature calculation (warmup)
CANDLES_FOR_FEATURES = 200

# ═══════════════════════════════════════════════════════════════════════════════
# NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

# Based on training data distribution:
# top 1% ~ 0.015 → maps to +100
# Multiplier to normalize score to -100..+100 range
SCORE_MULTIPLIER = 6666.67  # 0.015 * 6666.67 ≈ 100

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
