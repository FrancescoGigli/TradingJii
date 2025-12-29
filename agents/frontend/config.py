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
REFRESH_SIGNAL_FILE = f"{SHARED_PATH}/refresh_signal.txt"

# Page config
PAGE_TITLE = "Crypto Dashboard Pro"
PAGE_ICON = "📈"
