"""
📊 Market Intelligence Service - News & Sentiment

Provides:
- get_news(): Fetch latest crypto news from RSS feeds
- get_sentiment(): Get Fear & Greed Index from CoinMarketCap

Non-blocking operations with caching to minimize API calls.
"""

import os
import re
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    import requests
except ImportError:
    requests = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """Container for a single news item"""
    title: str
    description: str
    published: str
    link: str
    source: str


@dataclass
class SentimentData:
    """Container for sentiment data"""
    value: int  # 0-100
    classification: str  # 'Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed'
    timestamp: str
    is_real: bool = True  # False if error/demo


class MarketIntelligence:
    """
    Service class for market intelligence operations.
    
    Usage:
        service = MarketIntelligence()
        news = service.get_news()
        sentiment = service.get_sentiment()
    """
    
    # RSS Feed sources
    RSS_FEEDS = [
        ("CoinJournal", "https://coinjournal.net/feed/"),
        # Can add more sources here
    ]
    
    # CoinMarketCap API endpoint
    CMC_FEAR_GREED_URL = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical"
    
    # Cache duration
    NEWS_CACHE_MINUTES = 15
    SENTIMENT_CACHE_MINUTES = 30
    
    def __init__(self, cmc_api_key: str = None):
        """
        Initialize Market Intelligence service.
        
        Args:
            cmc_api_key: CoinMarketCap API key (defaults to env var)
        """
        self.cmc_api_key = cmc_api_key or os.getenv("CMC_PRO_API_KEY")
        
        # Check if CMC credentials are available
        if not self.cmc_api_key:
            logger.warning("⚠️ CMC API key not configured - sentiment disabled")
            self._has_cmc_credentials = False
        else:
            self._has_cmc_credentials = True
        
        # Cache storage
        self._news_cache: List[NewsItem] = []
        self._news_cache_time: Optional[datetime] = None
        
        self._sentiment_cache: Optional[SentimentData] = None
        self._sentiment_cache_time: Optional[datetime] = None
    
    @property
    def is_sentiment_available(self) -> bool:
        """Check if sentiment service is available"""
        return self._has_cmc_credentials and requests is not None
    
    @property
    def is_news_available(self) -> bool:
        """Check if news service is available"""
        return feedparser is not None
    
    def _is_cache_valid(self, cache_time: Optional[datetime], max_age_minutes: int) -> bool:
        """Check if cache is still valid"""
        if cache_time is None:
            return False
        age = datetime.now() - cache_time
        return age.total_seconds() < max_age_minutes * 60
    
    @staticmethod
    def _strip_html_tags(text: str) -> str:
        """Remove HTML tags and normalize whitespace"""
        text = re.sub(r'<[^>]+>', '', text)
        text = ' '.join(text.split())
        return text
    
    def get_news(self, max_items: int = 5, max_chars: int = 4000, use_cache: bool = True) -> List[NewsItem]:
        """
        Fetch latest crypto news from RSS feeds.
        
        Args:
            max_items: Maximum number of news items
            max_chars: Maximum total characters
            use_cache: Whether to use cached data
        
        Returns:
            List of NewsItem objects
        """
        # Check cache
        if use_cache and self._is_cache_valid(self._news_cache_time, self.NEWS_CACHE_MINUTES):
            return self._news_cache[:max_items]
        
        if not self.is_news_available:
            logger.warning("⚠️ feedparser not installed")
            return []
        
        news_items = []
        total_chars = 0
        
        try:
            for source_name, feed_url in self.RSS_FEEDS:
                # ╔════════════════════════════════════════════════════════════════╗
                # ║  RSS FEED FETCH                                                ║
                # ║  Public feed - no API key required                             ║
                # ╚════════════════════════════════════════════════════════════════╝
                feed = feedparser.parse(feed_url)
                
                if not feed.entries:
                    continue
                
                for entry in feed.entries:
                    if len(news_items) >= max_items:
                        break
                    
                    title = self._strip_html_tags(entry.get('title', 'No title'))
                    description = self._strip_html_tags(entry.get('description', ''))[:200]
                    published = entry.get('published', 'N/A')
                    link = entry.get('link', '')
                    
                    item = NewsItem(
                        title=title,
                        description=description,
                        published=published,
                        link=link,
                        source=source_name
                    )
                    
                    item_chars = len(title) + len(description)
                    if total_chars + item_chars > max_chars:
                        break
                    
                    news_items.append(item)
                    total_chars += item_chars
            
            # Update cache
            self._news_cache = news_items
            self._news_cache_time = datetime.now()
            
            logger.info(f"📰 Fetched {len(news_items)} news items")
            return news_items
            
        except Exception as e:
            logger.error(f"❌ Error fetching news: {e}")
            return self._news_cache[:max_items] if self._news_cache else []
    
    def get_news_text(self, max_items: int = 3) -> str:
        """Get news as formatted text string for AI prompts"""
        news = self.get_news(max_items=max_items)
        if not news:
            return "No news available"
        
        lines = []
        for item in news:
            lines.append(f"• {item.title}")
            if item.description:
                lines.append(f"  {item.description[:100]}...")
        
        return "\n".join(lines)
    
    def get_sentiment(self, use_cache: bool = True) -> SentimentData:
        """
        Get Fear & Greed Index from CoinMarketCap.
        
        Args:
            use_cache: Whether to use cached data
        
        Returns:
            SentimentData with current sentiment
        """
        # Check cache
        if use_cache and self._is_cache_valid(self._sentiment_cache_time, self.SENTIMENT_CACHE_MINUTES):
            return self._sentiment_cache
        
        if not self.is_sentiment_available:
            return SentimentData(
                value=50,
                classification="Neutral",
                timestamp=datetime.now().isoformat(),
                is_real=False
            )
        
        try:
            # ╔════════════════════════════════════════════════════════════════╗
            # ║  COINMARKETCAP API CALL                                        ║
            # ║  GET /v3/fear-and-greed/historical                            ║
            # ║  Header: X-CMC_PRO_API_KEY                                     ║
            # ╚════════════════════════════════════════════════════════════════╝
            headers = {
                "X-CMC_PRO_API_KEY": self.cmc_api_key,
                "Accept": "application/json"
            }
            params = {"limit": 1}  # Only get latest value
            
            response = requests.get(
                self.CMC_FEAR_GREED_URL,
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"❌ CMC API error: {response.status_code}")
                return self._get_fallback_sentiment()
            
            data = response.json()
            
            if "data" not in data or not data["data"]:
                logger.warning("⚠️ No sentiment data in response")
                return self._get_fallback_sentiment()
            
            # ╔════════════════════════════════════════════════════════════════╗
            # ║  PARSE RESPONSE                                                ║
            # ╚════════════════════════════════════════════════════════════════╝
            latest = data["data"][0]
            value = int(latest.get("value", 50))
            timestamp = latest.get("timestamp", datetime.now().isoformat())
            
            # Classify sentiment based on value
            if value <= 25:
                classification = "Extreme Fear"
            elif value <= 45:
                classification = "Fear"
            elif value <= 55:
                classification = "Neutral"
            elif value <= 75:
                classification = "Greed"
            else:
                classification = "Extreme Greed"
            
            sentiment = SentimentData(
                value=value,
                classification=classification,
                timestamp=timestamp,
                is_real=True
            )
            
            # Update cache
            self._sentiment_cache = sentiment
            self._sentiment_cache_time = datetime.now()
            
            logger.info(f"📊 Sentiment: {value}/100 ({classification})")
            return sentiment
            
        except Exception as e:
            logger.error(f"❌ Error fetching sentiment: {e}")
            return self._get_fallback_sentiment()
    
    def _get_fallback_sentiment(self) -> SentimentData:
        """Return cached or default sentiment on error"""
        if self._sentiment_cache:
            return self._sentiment_cache
        
        return SentimentData(
            value=50,
            classification="Neutral",
            timestamp=datetime.now().isoformat(),
            is_real=False
        )
    
    def get_sentiment_dict(self) -> Dict:
        """Get sentiment as dictionary for AI prompts"""
        sentiment = self.get_sentiment()
        return {
            "value": sentiment.value,
            "classification": sentiment.classification,
            "timestamp": sentiment.timestamp
        }
    
    def get_sentiment_emoji(self) -> str:
        """Get emoji representation of sentiment"""
        sentiment = self.get_sentiment()
        value = sentiment.value
        
        if value <= 25:
            return "😱"  # Extreme Fear
        elif value <= 45:
            return "😰"  # Fear
        elif value <= 55:
            return "😐"  # Neutral
        elif value <= 75:
            return "😊"  # Greed
        else:
            return "🤑"  # Extreme Greed
    
    def get_full_context(self, max_news: int = 3) -> Dict:
        """
        Get full market context for AI analysis.
        
        Returns:
            Dict with news and sentiment data
        """
        return {
            "news": self.get_news_text(max_items=max_news),
            "sentiment": self.get_sentiment_dict()
        }


# ============================================================
# SINGLETON INSTANCE
# ============================================================
_market_intelligence: Optional[MarketIntelligence] = None


def get_market_intelligence() -> MarketIntelligence:
    """Get singleton Market Intelligence service instance"""
    global _market_intelligence
    if _market_intelligence is None:
        _market_intelligence = MarketIntelligence()
    return _market_intelligence
