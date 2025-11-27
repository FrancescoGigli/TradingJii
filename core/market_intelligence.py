"""
Market Intelligence Hub - Integration from Rizzo project
Collects news, sentiment, forecasts, and whale alerts for enhanced trading context
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import feedparser
import requests
import pandas as pd
from prophet import Prophet
import warnings

# Suppress Prophet logging
logging.getLogger("cmdstanpy").disabled = True
warnings.filterwarnings("ignore", category=FutureWarning, module="prophet")


@dataclass
class MarketIntelligence:
    """Container for all market intelligence data"""
    news: str
    sentiment: Dict
    forecasts: Dict
    whale_alerts: str
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging"""
        return {
            "news": self.news,
            "sentiment": self.sentiment,
            "forecasts": self.forecasts,
            "whale_alerts": self.whale_alerts,
            "timestamp": self.timestamp.isoformat()
        }


class NewsCollector:
    """Collects crypto news from RSS feeds"""
    
    RSS_FEED_URL = "https://coinjournal.net/feed/"
    
    @staticmethod
    def _strip_html_tags(text: str) -> str:
        """Remove HTML tags and normalize whitespace"""
        import re
        text = re.sub(r'<[^>]+>', '', text)
        text = ' '.join(text.split())
        return text
    
    @staticmethod
    async def fetch_latest_news(max_chars: int = 4000) -> str:
        """
        Fetch latest crypto news from RSS feed
        Returns formatted string with timestamp and titles
        """
        try:
            # Run in thread pool to avoid blocking
            feed = await asyncio.to_thread(feedparser.parse, NewsCollector.RSS_FEED_URL)
            
            if not feed.entries:
                return "No news available"
            
            news_lines = []
            total_chars = 0
            
            for entry in feed.entries:
                # Parse published date
                pub_date = entry.get('published', 'N/A')
                title = NewsCollector._strip_html_tags(entry.get('title', 'No title'))
                description = NewsCollector._strip_html_tags(entry.get('description', ''))
                
                news_line = f"{pub_date} | {title}: {description}"
                
                # Check length limit
                if total_chars + len(news_line) > max_chars:
                    # Truncate last entry if needed
                    remaining = max_chars - total_chars
                    if remaining > 100:  # Only add if meaningful space left
                        news_line = news_line[:remaining] + "..."
                        news_lines.append(news_line)
                    break
                
                news_lines.append(news_line)
                total_chars += len(news_line)
            
            return "\n".join(news_lines) if news_lines else "No news available"
            
        except Exception as e:
            logging.error(f"❌ Error fetching news: {e}")
            return f"Error fetching news: {str(e)}"


class SentimentAnalyzer:
    """Analyzes market sentiment using Fear & Greed Index"""
    
    CMC_API_URL = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
    
    async def get_sentiment(self) -> Tuple[str, Dict]:
        """
        Get Fear & Greed Index from CoinMarketCap
        Returns (formatted_text, sentiment_dict)
        """
        if not self.api_key:
            return "Sentiment analysis disabled (no CMC API key)", {}
        
        try:
            headers = {
                "X-CMC_PRO_API_KEY": self.api_key,
                "Accept": "application/json"
            }
            params = {"limit": 1}
            
            # Run in thread pool
            response = await asyncio.to_thread(
                requests.get, 
                self.CMC_API_URL, 
                headers=headers, 
                params=params,
                timeout=10
            )
            
            if response.status_code != 200:
                return f"Sentiment API error: {response.status_code}", {}
            
            data = response.json()
            
            if "data" not in data or not data["data"]:
                return "No sentiment data available", {}
            
            latest = data["data"][0]
            value = latest.get("value", 0)
            timestamp = latest.get("timestamp", "N/A")
            
            # Classify sentiment
            if value <= 25:
                classification = "EXTREME FEAR"
            elif value <= 45:
                classification = "FEAR"
            elif value <= 55:
                classification = "NEUTRAL"
            elif value <= 75:
                classification = "GREED"
            else:
                classification = "EXTREME GREED"
            
            sentiment_dict = {
                "value": value,
                "classification": classification,
                "timestamp": timestamp
            }
            
            sentiment_text = f"Fear & Greed Index: {value}/100 ({classification}) | Updated: {timestamp}"
            
            return sentiment_text, sentiment_dict
            
        except Exception as e:
            logging.error(f"❌ Error fetching sentiment: {e}")
            return f"Error fetching sentiment: {str(e)}", {}


class CryptoForecaster:
    """Generates price forecasts using Prophet"""
    
    def __init__(self, exchange):
        self.exchange = exchange
    
    async def _fetch_candles(self, symbol: str, timeframe: str = "15m", limit: int = 1000) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data and prepare for Prophet"""
        try:
            # Fetch from exchange
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            if not ohlcv:
                return None
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['ds'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['y'] = df['close']
            
            return df[['ds', 'y']]
            
        except Exception as e:
            logging.debug(f"Error fetching candles for {symbol}: {e}")
            return None
    
    async def forecast_symbol(self, symbol: str, timeframe: str = "15m") -> Optional[Dict]:
        """Generate forecast for a single symbol"""
        try:
            df = await self._fetch_candles(symbol, timeframe)
            
            if df is None or len(df) < 100:  # Need enough data
                return None
            
            last_price = df['y'].iloc[-1]
            
            # Train Prophet model (in thread pool)
            def train_predict():
                model = Prophet(
                    daily_seasonality=False,
                    weekly_seasonality=False,
                    yearly_seasonality=False,
                    changepoint_prior_scale=0.05
                )
                model.fit(df)
                
                # Predict next period
                future = model.make_future_dataframe(periods=1, freq='15min' if timeframe == '15m' else '1H')
                forecast = model.predict(future)
                
                return forecast.iloc[-1]
            
            prediction = await asyncio.to_thread(train_predict)
            
            predicted_price = prediction['yhat']
            lower_bound = prediction['yhat_lower']
            upper_bound = prediction['yhat_upper']
            change_pct = ((predicted_price - last_price) / last_price) * 100
            
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "last_price": float(last_price),
                "predicted_price": float(predicted_price),
                "lower_bound": float(lower_bound),
                "upper_bound": float(upper_bound),
                "change_pct": float(change_pct),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.debug(f"Error forecasting {symbol}: {e}")
            return None
    
    async def forecast_multiple(self, symbols: List[str], timeframe: str = "15m") -> Tuple[str, Dict]:
        """
        Generate forecasts for multiple symbols
        Returns (formatted_text, forecasts_dict)
        """
        try:
            # Limit to top symbols to avoid timeout
            symbols_to_forecast = symbols[:5]  # Top 5 only
            
            forecasts = []
            for symbol in symbols_to_forecast:
                forecast = await self.forecast_symbol(symbol, timeframe)
                if forecast:
                    forecasts.append(forecast)
            
            if not forecasts:
                return "No forecasts available", {}
            
            # Format as table
            lines = ["Prophet Forecasts (15m):"]
            lines.append("Symbol | Last Price | Predicted | Change % | Range")
            lines.append("-" * 60)
            
            for f in forecasts:
                symbol_short = f['symbol'].replace('/USDT:USDT', '')
                lines.append(
                    f"{symbol_short:6} | ${f['last_price']:8.2f} | ${f['predicted_price']:8.2f} | "
                    f"{f['change_pct']:+6.2f}% | ${f['lower_bound']:.2f}-${f['upper_bound']:.2f}"
                )
            
            forecasts_text = "\n".join(lines)
            forecasts_dict = {"forecasts": forecasts, "timestamp": datetime.now().isoformat()}
            
            return forecasts_text, forecasts_dict
            
        except Exception as e:
            logging.error(f"❌ Error generating forecasts: {e}")
            return f"Error generating forecasts: {str(e)}", {}


class WhaleAlertCollector:
    """Collects whale alert data"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
    
    async def get_alerts(self) -> str:
        """Get recent whale alerts (placeholder - requires API subscription)"""
        if not self.api_key:
            return "Whale alerts disabled (no API key)"
        
        # Placeholder - would integrate with whale-alert.io API
        return "Whale alerts: Feature available with API subscription"


class MarketIntelligenceHub:
    """Main hub for collecting all market intelligence"""
    
    def __init__(self, exchange, cmc_api_key: Optional[str] = None, whale_api_key: Optional[str] = None):
        self.exchange = exchange
        self.news_collector = NewsCollector()
        self.sentiment_analyzer = SentimentAnalyzer(cmc_api_key)
        self.forecaster = CryptoForecaster(exchange)
        self.whale_collector = WhaleAlertCollector(whale_api_key)
    
    async def collect_intelligence(self, symbols: List[str]) -> MarketIntelligence:
        """
        Collect all market intelligence data
        Returns MarketIntelligence object with all data
        """
        logging.info("📊 Collecting market intelligence...")
        
        # Collect all data in parallel
        results = await asyncio.gather(
            self.news_collector.fetch_latest_news(),
            self.sentiment_analyzer.get_sentiment(),
            self.forecaster.forecast_multiple(symbols),
            self.whale_collector.get_alerts(),
            return_exceptions=True
        )
        
        # Unpack results (handle exceptions)
        news = results[0] if not isinstance(results[0], Exception) else "Error fetching news"
        sentiment_data = results[1] if not isinstance(results[1], Exception) else ("Error", {})
        forecast_data = results[2] if not isinstance(results[2], Exception) else ("Error", {})
        whale_alerts = results[3] if not isinstance(results[3], Exception) else "Error fetching whale alerts"
        
        # Unpack tuples
        sentiment_text, sentiment_dict = sentiment_data if isinstance(sentiment_data, tuple) else (str(sentiment_data), {})
        forecast_text, forecast_dict = forecast_data if isinstance(forecast_data, tuple) else (str(forecast_data), {})
        
        intelligence = MarketIntelligence(
            news=news,
            sentiment=sentiment_dict,
            forecasts=forecast_dict,
            whale_alerts=whale_alerts,
            timestamp=datetime.now()
        )
        
        logging.info("✅ Market intelligence collected")
        return intelligence
    
    def format_for_prompt(self, intelligence: MarketIntelligence) -> str:
        """Format intelligence data for AI prompt"""
        sentiment_text = "N/A"
        if intelligence.sentiment:
            s = intelligence.sentiment
            sentiment_text = f"{s.get('value', 'N/A')}/100 ({s.get('classification', 'N/A')})"
        
        # Format forecasts
        forecast_text = "No forecasts available"
        if intelligence.forecasts and 'forecasts' in intelligence.forecasts:
            lines = []
            for f in intelligence.forecasts['forecasts'][:3]:  # Top 3
                symbol = f['symbol'].replace('/USDT:USDT', '')
                lines.append(f"{symbol}: ${f['last_price']:.2f} → ${f['predicted_price']:.2f} ({f['change_pct']:+.2f}%)")
            forecast_text = "\n".join(lines)
        
        # Truncate news for prompt length
        news_truncated = intelligence.news[:2000]
        
        return f"""
<market_intelligence>
<news>
{news_truncated}
</news>

<sentiment>
Fear & Greed Index: {sentiment_text}
</sentiment>

<forecasts>
{forecast_text}
</forecasts>

<whale_alerts>
{intelligence.whale_alerts}
</whale_alerts>
</market_intelligence>
"""
