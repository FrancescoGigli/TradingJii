"""
AI Technical Analyst - Parallel AI Analysis of Technical Indicators
Analyzes the same 66 features as XGBoost but with reasoning capabilities

This is NOT a validator - it's an independent analyst that provides its own signal
"""

import logging
import json
import os
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI library not available - AI Technical Analyst disabled")


@dataclass
class AISignal:
    """AI-generated trading signal with full reasoning"""
    symbol: str
    direction: str  # "LONG", "SHORT", "NEUTRAL"
    confidence: float  # 0-100
    reasoning: str  # 2-3 sentence explanation
    key_factors: List[str]  # Top 3-5 decisive factors
    risk_level: str  # "low", "medium", "high"
    entry_quality: str  # "excellent", "good", "fair", "poor"
    timestamp: datetime
    
    # Raw technical assessment
    technical_score: float  # 0-100 based on indicators
    fundamental_score: float  # 0-100 based on news/sentiment
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat()
        }


class AITechnicalAnalyst:
    """
    Parallel AI analyst that analyzes same data as XGBoost
    Returns independent signal with reasoning
    
    Key difference from AIDecisionValidator:
    - Validator: Takes XGBoost signals and approves/rejects
    - Analyst: Generates its OWN independent signal from raw data
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        
        if not OPENAI_AVAILABLE:
            logging.warning("⚠️ OpenAI not available - AI Technical Analyst disabled")
            self.client = None
        elif not self.api_key:
            logging.warning("⚠️ No OpenAI API key - AI Technical Analyst disabled")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)
            logging.info(f"🧠 AI Technical Analyst initialized with {model}")
    
    def is_available(self) -> bool:
        """Check if AI analyst is available"""
        return self.client is not None
    
    async def analyze_symbol(
        self,
        symbol: str,
        indicators: Dict,
        market_intel: Optional[Dict] = None,
        current_price: float = 0.0
    ) -> Optional[AISignal]:
        """
        Analyze a symbol using GPT-4o with full technical context
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT:USDT")
            indicators: Dict with technical indicators from dataframe
            market_intel: Optional market intelligence (news, sentiment, forecasts)
            current_price: Current price of the asset
            
        Returns:
            AISignal with independent analysis
        """
        if not self.is_available():
            return None
        
        try:
            # Build the technical analysis prompt
            prompt = self._build_technical_prompt(symbol, indicators, market_intel, current_price)
            
            logging.debug(f"🧠 AI Analyst analyzing {symbol}...")
            
            # Call OpenAI API with structured output
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "ai_signal",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "direction": {
                                    "type": "string",
                                    "enum": ["LONG", "SHORT", "NEUTRAL"]
                                },
                                "confidence": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 100
                                },
                                "reasoning": {
                                    "type": "string"
                                },
                                "key_factors": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "risk_level": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high"]
                                },
                                "entry_quality": {
                                    "type": "string",
                                    "enum": ["excellent", "good", "fair", "poor"]
                                },
                                "technical_score": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 100
                                },
                                "fundamental_score": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 100
                                }
                            },
                            "required": [
                                "direction", "confidence", "reasoning", "key_factors",
                                "risk_level", "entry_quality", "technical_score", "fundamental_score"
                            ],
                            "additionalProperties": False
                        }
                    }
                },
                temperature=0.2  # Low temperature for consistent analysis
            )
            
            # Parse response
            raw_response = completion.choices[0].message.content
            content = json.loads(raw_response)
            
            # Create AISignal
            ai_signal = AISignal(
                symbol=symbol,
                direction=content["direction"],
                confidence=content["confidence"],
                reasoning=content["reasoning"],
                key_factors=content["key_factors"],
                risk_level=content["risk_level"],
                entry_quality=content["entry_quality"],
                technical_score=content["technical_score"],
                fundamental_score=content["fundamental_score"],
                timestamp=datetime.now()
            )
            
            # Log result
            symbol_short = symbol.replace('/USDT:USDT', '')
            direction_emoji = "🟢" if ai_signal.direction == "LONG" else "🔴" if ai_signal.direction == "SHORT" else "⚪"
            logging.info(
                f"🧠 AI Analysis {symbol_short}: {direction_emoji} {ai_signal.direction} "
                f"({ai_signal.confidence:.0f}%) - {ai_signal.entry_quality} entry"
            )
            
            return ai_signal
            
        except Exception as e:
            logging.error(f"❌ AI Technical Analyst error for {symbol}: {e}")
            return None
    
    async def analyze_batch(
        self,
        signals_data: List[Dict],
        market_intel: Optional[Dict] = None
    ) -> Dict[str, AISignal]:
        """
        Analyze multiple symbols in batch
        
        Args:
            signals_data: List of signal dicts with symbol, dataframes, etc.
            market_intel: Optional market intelligence
            
        Returns:
            Dict mapping symbol to AISignal
        """
        results = {}
        
        for signal in signals_data:
            symbol = signal['symbol']
            
            # Extract indicators from dataframe
            indicators = self._extract_indicators_from_signal(signal)
            
            # Get current price
            current_price = signal.get('price', 0)
            if current_price == 0:
                # Try to get from dataframe
                df = signal.get('dataframes', {}).get('15m')
                if df is not None and len(df) > 0:
                    current_price = df.iloc[-1].get('close', 0)
            
            # Analyze
            ai_signal = await self.analyze_symbol(symbol, indicators, market_intel, current_price)
            
            if ai_signal:
                results[symbol] = ai_signal
        
        return results
    
    def _extract_indicators_from_signal(self, signal: Dict) -> Dict:
        """
        Extract key indicators from signal dataframe
        
        This extracts the same indicators XGBoost uses for analysis
        """
        indicators = {}
        
        # Get default timeframe dataframe (15m or 5m)
        df = None
        for tf in ['15m', '5m', '30m', '1h']:
            if tf in signal.get('dataframes', {}) and signal['dataframes'][tf] is not None:
                df = signal['dataframes'][tf]
                break
        
        if df is None or len(df) == 0:
            return indicators
        
        # Get latest candle
        latest = df.iloc[-1]
        
        # Core indicators
        indicators['close'] = latest.get('close', 0)
        indicators['open'] = latest.get('open', 0)
        indicators['high'] = latest.get('high', 0)
        indicators['low'] = latest.get('low', 0)
        indicators['volume'] = latest.get('volume', 0)
        
        # Moving Averages
        indicators['ema5'] = latest.get('ema5', 0)
        indicators['ema10'] = latest.get('ema10', 0)
        indicators['ema20'] = latest.get('ema20', 0)
        
        # Momentum Indicators
        indicators['rsi_fast'] = latest.get('rsi_fast', 50)
        indicators['stoch_rsi'] = latest.get('stoch_rsi', 50)
        indicators['macd'] = latest.get('macd', 0)
        indicators['macd_signal'] = latest.get('macd_signal', 0)
        indicators['macd_histogram'] = latest.get('macd_histogram', 0)
        
        # Volatility
        indicators['atr'] = latest.get('atr', 0)
        indicators['volatility'] = latest.get('volatility', 0)
        indicators['bollinger_hband'] = latest.get('bollinger_hband', 0)
        indicators['bollinger_lband'] = latest.get('bollinger_lband', 0)
        
        # Trend
        indicators['adx'] = latest.get('adx', 25)
        indicators['vwap'] = latest.get('vwap', 0)
        indicators['obv'] = latest.get('obv', 0)
        
        # Advanced Features
        indicators['price_pos_5'] = latest.get('price_pos_5', 0)
        indicators['price_pos_10'] = latest.get('price_pos_10', 0)
        indicators['price_pos_20'] = latest.get('price_pos_20', 0)
        indicators['vol_acceleration'] = latest.get('vol_acceleration', 0)
        indicators['momentum_divergence'] = latest.get('momentum_divergence', 0)
        indicators['volatility_squeeze'] = latest.get('volatility_squeeze', 0)
        indicators['resistance_dist_10'] = latest.get('resistance_dist_10', 0)
        indicators['support_dist_10'] = latest.get('support_dist_10', 0)
        indicators['price_acceleration'] = latest.get('price_acceleration', 0)
        
        return indicators
    
    def _get_system_prompt(self) -> str:
        """System prompt for AI Technical Analyst"""
        return """You are a professional cryptocurrency technical analyst with 10+ years of experience.

Your job is to analyze technical indicators and provide an independent trading signal.

You must analyze:
1. MOMENTUM: RSI, MACD, Stochastic
2. TREND: EMA alignment, ADX strength
3. VOLATILITY: ATR, Bollinger Bands, Volatility Squeeze
4. VOLUME: OBV, Volume Acceleration
5. STRUCTURE: Support/Resistance distances

Your analysis MUST be objective and based solely on the data provided.
You are NOT validating someone else's signal - you are providing YOUR OWN analysis.

Key principles:
- RSI >70 = overbought (potential SHORT), <30 = oversold (potential LONG)
- ADX >20 = tradeable trend, <15 = too weak (avoid)
- MACD histogram direction shows momentum
- Volume confirmation strengthens signals
- Bollinger squeeze indicates potential breakout
- Always consider risk/reward ratio

IMPORTANT: Be DECISIVE. Only use NEUTRAL when:
- ADX < 15 (extremely weak trend)
- Conflicting signals from ALL indicators
- Extreme volatility (>6%) without clear direction
Otherwise, pick LONG or SHORT based on the dominant indicators."""
    
    def _build_technical_prompt(
        self,
        symbol: str,
        indicators: Dict,
        market_intel: Optional[Dict],
        current_price: float
    ) -> str:
        """Build the technical analysis prompt for GPT-4o"""
        
        symbol_short = symbol.replace('/USDT:USDT', '')
        
        # Calculate derived values
        price = indicators.get('close', current_price) or current_price
        rsi = indicators.get('rsi_fast', 50)
        adx = indicators.get('adx', 25)
        macd_hist = indicators.get('macd_histogram', 0)
        volatility = indicators.get('volatility', 0) * 100  # Convert to %
        vol_accel = indicators.get('vol_acceleration', 0) * 100  # Convert to %
        
        # EMA trend detection
        ema5 = indicators.get('ema5', price)
        ema10 = indicators.get('ema10', price)
        ema20 = indicators.get('ema20', price)
        
        if ema5 > ema10 > ema20:
            ema_trend = "BULLISH (5>10>20)"
        elif ema5 < ema10 < ema20:
            ema_trend = "BEARISH (5<10<20)"
        else:
            ema_trend = "MIXED (choppy)"
        
        # RSI interpretation
        if rsi > 80:
            rsi_status = "EXTREME OVERBOUGHT ⚠️"
        elif rsi > 70:
            rsi_status = "Overbought"
        elif rsi < 20:
            rsi_status = "EXTREME OVERSOLD ⚠️"
        elif rsi < 30:
            rsi_status = "Oversold"
        else:
            rsi_status = "Neutral zone"
        
        # ADX interpretation
        if adx > 40:
            adx_status = "Very Strong Trend 💪"
        elif adx > 25:
            adx_status = "Strong Trend"
        elif adx > 20:
            adx_status = "Moderate Trend"
        else:
            adx_status = "Weak/Ranging Market ⚠️"
        
        # MACD interpretation
        if macd_hist > 0.5:
            macd_status = "Strong Bullish Momentum 📈"
        elif macd_hist > 0:
            macd_status = "Bullish Momentum"
        elif macd_hist < -0.5:
            macd_status = "Strong Bearish Momentum 📉"
        elif macd_hist < 0:
            macd_status = "Bearish Momentum"
        else:
            macd_status = "Neutral"
        
        # Bollinger position
        bb_upper = indicators.get('bollinger_hband', price * 1.02)
        bb_lower = indicators.get('bollinger_lband', price * 0.98)
        bb_width = (bb_upper - bb_lower) / price * 100 if price > 0 else 0
        
        if price > bb_upper * 0.99:
            bb_position = "Near upper band (potential resistance)"
        elif price < bb_lower * 1.01:
            bb_position = "Near lower band (potential support)"
        else:
            bb_position = "Mid-range"
        
        # Volume status
        if vol_accel > 100:
            vol_status = "SURGE 🚀 (+{:.0f}%)".format(vol_accel)
        elif vol_accel > 50:
            vol_status = "Strong increase (+{:.0f}%)".format(vol_accel)
        elif vol_accel < -50:
            vol_status = "Declining (-{:.0f}%)".format(abs(vol_accel))
        else:
            vol_status = "Normal"
        
        # Support/Resistance distances
        res_dist = indicators.get('resistance_dist_10', 0) * 100
        sup_dist = indicators.get('support_dist_10', 0) * 100
        
        # Build prompt
        prompt = f"""ANALYZE THIS SYMBOL AND PROVIDE YOUR INDEPENDENT TRADING SIGNAL:

═══════════════════════════════════════════════════════════
SYMBOL: {symbol_short}
CURRENT PRICE: ${price:.4f}
═══════════════════════════════════════════════════════════

📊 TECHNICAL INDICATORS:

MOMENTUM:
• RSI (14): {rsi:.1f} - {rsi_status}
• MACD Histogram: {macd_hist:.4f} - {macd_status}
• Stochastic RSI: {indicators.get('stoch_rsi', 50):.1f}

TREND:
• ADX: {adx:.1f} - {adx_status}
• EMA Alignment: {ema_trend}
  - EMA5: ${ema5:.4f}
  - EMA10: ${ema10:.4f}
  - EMA20: ${ema20:.4f}

VOLATILITY:
• Current Volatility: {volatility:.2f}% {'(HIGH ⚠️)' if volatility > 4 else '(Normal)'}
• ATR: ${indicators.get('atr', 0):.4f}
• Bollinger Width: {bb_width:.2f}%
• Bollinger Position: {bb_position}
• Squeeze Active: {'YES 🔔' if indicators.get('volatility_squeeze', 0) > 0.5 else 'No'}

VOLUME:
• Volume Acceleration: {vol_status}
• OBV Trend: {'Positive' if indicators.get('obv', 0) > 0 else 'Negative'}

STRUCTURE:
• Distance to Resistance (10): {res_dist:.2f}%
• Distance to Support (10): {sup_dist:.2f}%
• Price Acceleration: {indicators.get('price_acceleration', 0)*100:.2f}%
"""

        # Add market intelligence if available
        if market_intel:
            prompt += "\n═══════════════════════════════════════════════════════════\n"
            prompt += "📰 FUNDAMENTAL CONTEXT:\n\n"
            
            if hasattr(market_intel, 'news') and market_intel.news:
                news_preview = market_intel.news[:500] if len(market_intel.news) > 500 else market_intel.news
                prompt += f"NEWS: {news_preview}...\n\n"
            
            if hasattr(market_intel, 'sentiment') and market_intel.sentiment:
                sent = market_intel.sentiment
                value = sent.get('value', 50)
                classification = sent.get('classification', 'neutral')
                
                if value < 25:
                    sent_status = f"EXTREME FEAR ({value}/100) ⚠️"
                elif value < 45:
                    sent_status = f"Fear ({value}/100)"
                elif value > 75:
                    sent_status = f"EXTREME GREED ({value}/100) ⚠️"
                elif value > 55:
                    sent_status = f"Greed ({value}/100)"
                else:
                    sent_status = f"Neutral ({value}/100)"
                
                prompt += f"SENTIMENT: {sent_status}\n\n"
            
            if hasattr(market_intel, 'forecasts') and market_intel.forecasts:
                forecasts = market_intel.forecasts.get('forecasts', {})
                if symbol_short in forecasts or f"{symbol_short}/USDT" in forecasts:
                    fc = forecasts.get(symbol_short) or forecasts.get(f"{symbol_short}/USDT")
                    if fc:
                        fc_direction = "BULLISH 📈" if fc > 0 else "BEARISH 📉" if fc < 0 else "FLAT"
                        prompt += f"PROPHET FORECAST: {fc_direction} ({fc:+.2f}%)\n"

        prompt += """
═══════════════════════════════════════════════════════════
YOUR TASK:

Based on the technical and fundamental data above, provide:
1. Direction: LONG, SHORT, or NEUTRAL
2. Confidence: 0-100% (how sure are you?)
3. Reasoning: 2-3 sentences explaining your decision
4. Key Factors: List 3-5 decisive indicators
5. Risk Level: low, medium, high
6. Entry Quality: excellent, good, fair, poor

═══════════════════════════════════════════════════════════
ANALYSIS RULES:

• Weight technical indicators 70%, fundamentals 30%
• High confidence (>75%) requires multiple confirming factors
• NEUTRAL ONLY if ADX < 15 OR all indicators conflict
• Consider risk/reward: don't go LONG near resistance, SHORT near support
• Volume confirmation strengthens signals
• Trending market (ADX >20) = pick a direction based on indicators
• Strong MACD + aligned EMAs = go with the trend
• Extreme RSI (>75 or <25) = potential reversal, moderate confidence

CONFIDENCE GUIDELINES:
• 80-100%: All indicators align, strong trend (ADX >30)
• 65-80%: Most indicators align, decent trend (ADX >20)
• 50-65%: Mixed signals but one side dominant
• <50%: Use NEUTRAL (extremely rare)

BE DECISIVE - In crypto trading, sitting out costs opportunities.

Provide your analysis in JSON format."""

        return prompt


# Global instance
global_ai_technical_analyst = AITechnicalAnalyst()
