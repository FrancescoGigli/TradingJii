"""
📦 Services Package

External API integrations for the trading bot:
- BybitService: Exchange operations (balance, positions, orders)
- OpenAIService: AI analysis (validator, analyst)
- MarketIntelligence: News and sentiment (RSS, CMC)

All services include:
- Timeout protection (10s default)
- Retry with exponential backoff
- Response caching to reduce API calls
- Automatic reconnection on failures
"""

from .bybit_service import BybitService, get_bybit_service, reset_bybit_service
from .openai_service import OpenAIService, get_openai_service
from .market_intelligence import MarketIntelligence, get_market_intelligence

__all__ = [
    'BybitService',
    'get_bybit_service',
    'reset_bybit_service',
    'OpenAIService', 
    'get_openai_service',
    'MarketIntelligence',
    'get_market_intelligence'
]
