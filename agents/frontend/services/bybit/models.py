"""
Bybit Service - Data Models
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# Configuration constants
API_TIMEOUT_MS = 10000  # 10 seconds timeout for API calls
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0  # Base delay in seconds (exponential backoff)
CACHE_TTL_SECONDS = 15  # Cache balance/positions for 15 seconds
EXCHANGE_RECONNECT_INTERVAL = 300  # Force reconnect every 5 minutes


@dataclass
class BalanceInfo:
    """Container for balance information"""
    total_usdt: float
    available_usdt: float
    used_usdt: float
    timestamp: datetime
    is_real: bool = True  # False if demo/error


@dataclass
class PositionInfo:
    """Container for position information"""
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    leverage: int
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    liquidation_price: Optional[float] = None


@dataclass
class OrderResult:
    """Container for order execution result"""
    success: bool
    order_id: Optional[str]
    symbol: str
    side: str
    amount: float
    price: Optional[float]
    error: Optional[str] = None


@dataclass
class CachedData:
    """Generic cached data container"""
    data: any
    timestamp: datetime
    ttl_seconds: int = CACHE_TTL_SECONDS
    
    @property
    def is_valid(self) -> bool:
        """Check if cache is still valid"""
        if self.data is None:
            return False
        age = (datetime.now() - self.timestamp).total_seconds()
        return age < self.ttl_seconds
