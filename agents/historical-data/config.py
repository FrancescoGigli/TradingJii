"""
📊 Historical Data Agent Configuration

Configuration for downloading and managing historical OHLCV data
for ML training (12+ months of data with warmup period).
"""

from __future__ import annotations

import os
from pathlib import Path

# ----------------------------------------------------------------------
# Load .env file if present
# ----------------------------------------------------------------------
try:
    from dotenv import load_dotenv, find_dotenv

    _env_file = find_dotenv()
    if _env_file:
        load_dotenv(_env_file, override=False)
except ModuleNotFoundError:
    pass

# ----------------------------------------------------------------------
# Bybit Credentials
# ----------------------------------------------------------------------
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

if not API_KEY or not API_SECRET:
    raise RuntimeError(
        "Missing API keys: define BYBIT_API_KEY and BYBIT_API_SECRET "
        "in the .env file or environment variables."
    )

# ----------------------------------------------------------------------
# Exchange Configuration
# ----------------------------------------------------------------------
EXCHANGE_CONFIG = {
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "enableRateLimit": True,
    "options": {
        "adjustForTimeDifference": True,
        "recvWindow": 300000,
    },
}

# ----------------------------------------------------------------------
# Historical Data Configuration
# ----------------------------------------------------------------------

# Target historical period for TRAINING
HISTORICAL_MONTHS = 12  # 12 months of usable data for training

# Warmup candles for indicators (EMA 200 + safety margin)
# These extra candles ensure indicators are calculable from day 1 of training
WARMUP_CANDLES = 250

# Timeframes to download (only those useful for ML)
# - 15m: primary operational timeframe
# - 1h: context timeframe
HISTORICAL_TIMEFRAMES: list[str] = ["15m", "1h"]

# Number of symbols to track (top by volume)
TOP_SYMBOLS_COUNT = 100

# ----------------------------------------------------------------------
# Bybit API Limits
# ----------------------------------------------------------------------
MAX_CANDLES_PER_REQUEST = 1000  # Bybit maximum per request
REQUEST_DELAY_MS = 100  # Rate limiting delay between requests
MAX_CONCURRENT_REQUESTS = 10  # Concurrent symbol downloads

# ----------------------------------------------------------------------
# Update Configuration
# ----------------------------------------------------------------------
UPDATE_INTERVAL_MINUTES = 15  # Sync with 15m candles
BATCH_SIZE = 10  # Symbols to process in parallel

# ----------------------------------------------------------------------
# Validation Configuration
# ----------------------------------------------------------------------
VALIDATE_INTEGRITY = True  # Check for gaps after download
MAX_GAP_TO_FILL = 3  # Interpolate gaps <= 3 candles
COMPLETENESS_THRESHOLD = 99.0  # Minimum % completeness required

# ----------------------------------------------------------------------
# Storage Configuration (shared volume)
# ----------------------------------------------------------------------
SHARED_DATA_PATH = os.getenv("SHARED_DATA_PATH", "/app/shared")
CACHE_DIR = f"{SHARED_DATA_PATH}/data_cache"
DB_FILE = "trading_data.db"
DB_PATH = f"{CACHE_DIR}/{DB_FILE}"

# ----------------------------------------------------------------------
# Logging Configuration
# ----------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# ----------------------------------------------------------------------
# Calculated Constants
# ----------------------------------------------------------------------
# Candles per timeframe for 12 months
CANDLES_15M_PER_DAY = 24 * 4  # 96 candles/day
CANDLES_15M_PER_MONTH = CANDLES_15M_PER_DAY * 30  # ~2,880 candles/month
CANDLES_15M_TOTAL = CANDLES_15M_PER_MONTH * HISTORICAL_MONTHS + WARMUP_CANDLES  # ~34,810 + 250

CANDLES_1H_PER_DAY = 24  # 24 candles/day
CANDLES_1H_PER_MONTH = CANDLES_1H_PER_DAY * 30  # ~720 candles/month
CANDLES_1H_TOTAL = CANDLES_1H_PER_MONTH * HISTORICAL_MONTHS + WARMUP_CANDLES  # ~8,890


def get_target_candles(timeframe: str) -> int:
    """Get target number of candles for a timeframe"""
    if timeframe == "15m":
        return CANDLES_15M_TOTAL
    elif timeframe == "1h":
        return CANDLES_1H_TOTAL
    else:
        # Default: estimate based on timeframe
        return CANDLES_15M_PER_MONTH * HISTORICAL_MONTHS


def print_config():
    """Print current configuration"""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           HISTORICAL DATA AGENT CONFIGURATION                ║
╠══════════════════════════════════════════════════════════════╣
║  Historical Period:    {HISTORICAL_MONTHS} months                              ║
║  Warmup Candles:       {WARMUP_CANDLES}                                   ║
║  Timeframes:           {', '.join(HISTORICAL_TIMEFRAMES)}                              ║
║  Symbols Count:        {TOP_SYMBOLS_COUNT}                                   ║
║  Update Interval:      {UPDATE_INTERVAL_MINUTES} minutes                           ║
╠══════════════════════════════════════════════════════════════╣
║  Target Candles (15m): ~{CANDLES_15M_TOTAL:,}                           ║
║  Target Candles (1h):  ~{CANDLES_1H_TOTAL:,}                            ║
║  Max Gap to Fill:      {MAX_GAP_TO_FILL} candles                             ║
║  Completeness Target:  {COMPLETENESS_THRESHOLD}%                              ║
╠══════════════════════════════════════════════════════════════╣
║  Database Path:        {DB_PATH[:40]}...  ║
╚══════════════════════════════════════════════════════════════╝
""")
