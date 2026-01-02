"""
Configuration settings for the Crypto Dashboard
"""

import os
import pytz

# Timezone
ROME_TZ = pytz.timezone('Europe/Rome')

# Update interval
UPDATE_INTERVAL_MINUTES = 15

# Paths
SHARED_PATH = os.getenv("SHARED_DATA_PATH", "/app/shared")
DB_PATH = f"{SHARED_PATH}/data_cache/trading_data.db"

# Signal files
REFRESH_SIGNAL_FILE = f"{SHARED_PATH}/refresh_signal.txt"  # Refresh OHLCV data only
UPDATE_LIST_SIGNAL_FILE = f"{SHARED_PATH}/update_list_signal.txt"  # Update top 100 list + refresh data

# Candles configuration
CANDLES_LIMIT = 300  # Candele da visualizzare (include warmup per indicatori)

# Page config
PAGE_TITLE = "Crypto Dashboard Pro"
PAGE_ICON = "📈"
