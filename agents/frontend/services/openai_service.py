"""
🤖 OpenAI Service - AI Analysis

Provides:
- validate_signal(): Validate a trading signal with GPT-4o
- analyze_trade(): Get AI analysis for a specific trade
- get_market_analysis(): General market analysis

Uses OpenAI API with structured JSON outputs.
All calls are made on-demand (when user clicks button).
"""

import os
import json
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AIValidationResult:
    """Container for AI validation result"""
    symbol: str
    action: str  # 'approve', 'reject', 'defer'
    direction: str  # 'LONG', 'SHORT', 'NEUTRAL'
    confidence: float  # 0-100
    confidence_boost: float  # -20 to +20
    risk_assessment: str  # 'low', 'medium', 'high'
    reasoning: str
    key_factors: List[str]
    timestamp: datetime
    cost_usd: float = 0.0
    
    @property
    def is_approved(self) -> bool:
        return self.action == 'approve'


@dataclass
class AIAnalysisResult:
    """Container for general AI analysis"""
    symbol: str
    direction: str  # 'LONG', 'SHORT', 'NEUTRAL'
    confidence: float
    reasoning: str
    key_factors: List[str]
    risk_level: str
    entry_quality: str  # 'excellent', 'good', 'fair', 'poor'
    technical_score: float
    fundamental_score: float
    timestamp: datetime
    cost_usd: float = 0.0


class OpenAIService:
    """
    Service class for OpenAI API operations.
    
    Usage:
        service = OpenAIService()
        result = service.analyze_trade(trade_data, indicators)
    """
    
    # GPT-4o pricing (as of 2024)
    COST_PER_1M_INPUT_TOKENS = 2.50
    COST_PER_1M_OUTPUT_TOKENS = 10.00
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        """
        Initialize OpenAI service.
        
        Args:
            api_key: OpenAI API key (defaults to env var)
            model: Model to use (default: gpt-4o)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = None
        
        # Check if credentials are available
        if not self.api_key:
            logger.warning("⚠️ OpenAI API key not configured")
            self._has_credentials = False
        else:
            self._has_credentials = True
    
    def _get_client(self) -> Optional['OpenAI']:
        """Get or create OpenAI client"""
        if OpenAI is None:
            logger.error("❌ OpenAI library not installed")
            return None
            
        if not self._has_credentials:
            return None
            
        if self._client is None:
            try:
                self._client = OpenAI(api_key=self.api_key)
                logger.info("✅ OpenAI client initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize OpenAI: {e}")
                return None
                
        return self._client
    
    @property
    def is_available(self) -> bool:
        """Check if service is available"""
        return self._has_credentials and OpenAI is not None
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate API call cost"""
        input_cost = (prompt_tokens / 1_000_000) * self.COST_PER_1M_INPUT_TOKENS
        output_cost = (completion_tokens / 1_000_000) * self.COST_PER_1M_OUTPUT_TOKENS
        return round(input_cost + output_cost, 6)
    
    def analyze_trade(
        self,
        symbol: str,
        trade_type: str,  # 'LONG' or 'SHORT'
        entry_price: float,
        indicators: Dict[str, float],
        sentiment: Optional[Dict] = None,
        news: Optional[str] = None
    ) -> Optional[AIValidationResult]:
        """
        Get AI analysis for a specific trade.
        
        Args:
            symbol: Trading pair (e.g., "BTC")
            trade_type: 'LONG' or 'SHORT'
            entry_price: Entry price
            indicators: Dict with RSI, MACD, BB scores
            sentiment: Optional sentiment data
            news: Optional recent news
        
        Returns:
            AIValidationResult with AI reasoning
        """
        if not self.is_available:
            logger.warning("⚠️ OpenAI service not available")
            return None
        
        try:
            client = self._get_client()
            if client is None:
                return None
            
            # ╔════════════════════════════════════════════════════════════════╗
            # ║  BUILD PROMPT                                                   ║
            # ╚════════════════════════════════════════════════════════════════╝
            prompt = self._build_trade_analysis_prompt(
                symbol=symbol,
                trade_type=trade_type,
                entry_price=entry_price,
                indicators=indicators,
                sentiment=sentiment,
                news=news
            )
            
            logger.info(f"🤖 Calling GPT-4o to analyze {symbol} {trade_type}...")
            
            # ╔════════════════════════════════════════════════════════════════╗
            # ║  OPENAI API CALL                                               ║
            # ║  POST https://api.openai.com/v1/chat/completions               ║
            # ║  Using JSON Schema for structured output                       ║
            # ╚════════════════════════════════════════════════════════════════╝
            completion = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert cryptocurrency trading AI analyst.
Your job is to analyze trading signals and provide validation decisions.

Analyze the technical indicators and market context provided.
Be decisive - only use NEUTRAL when indicators truly conflict.

Respond in the exact JSON format requested."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "trade_validation",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["approve", "reject", "defer"],
                                    "description": "approve=take the trade, reject=skip it, defer=wait for better entry"
                                },
                                "direction": {
                                    "type": "string",
                                    "enum": ["LONG", "SHORT", "NEUTRAL"],
                                    "description": "Recommended direction based on analysis"
                                },
                                "confidence": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 100,
                                    "description": "Confidence in the recommendation (0-100)"
                                },
                                "confidence_boost": {
                                    "type": "number",
                                    "minimum": -20,
                                    "maximum": 20,
                                    "description": "Adjustment to original signal confidence"
                                },
                                "risk_assessment": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high"],
                                    "description": "Risk level of the trade"
                                },
                                "reasoning": {
                                    "type": "string",
                                    "description": "Detailed explanation of the analysis"
                                },
                                "key_factors": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Top 3-5 factors that influenced the decision"
                                }
                            },
                            "required": ["action", "direction", "confidence", "confidence_boost", 
                                        "risk_assessment", "reasoning", "key_factors"],
                            "additionalProperties": False
                        }
                    }
                },
                temperature=0.3  # Low temperature for consistent decisions
            )
            
            # ╔════════════════════════════════════════════════════════════════╗
            # ║  PARSE RESPONSE                                                ║
            # ╚════════════════════════════════════════════════════════════════╝
            raw_response = completion.choices[0].message.content
            content = json.loads(raw_response)
            
            # Calculate cost
            usage = completion.usage
            cost = self._calculate_cost(usage.prompt_tokens, usage.completion_tokens)
            
            result = AIValidationResult(
                symbol=symbol,
                action=content["action"],
                direction=content["direction"],
                confidence=content["confidence"],
                confidence_boost=content["confidence_boost"],
                risk_assessment=content["risk_assessment"],
                reasoning=content["reasoning"],
                key_factors=content["key_factors"],
                timestamp=datetime.now(),
                cost_usd=cost
            )
            
            # Log result
            emoji = "✅" if result.is_approved else "❌" if result.action == "reject" else "⏸️"
            logger.info(
                f"🤖 AI Analysis: {emoji} {result.action.upper()} {symbol} {trade_type} "
                f"| Confidence: {result.confidence:.0f}% | Cost: ${cost:.4f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ AI analysis error: {e}")
            return None
    
    def _build_trade_analysis_prompt(
        self,
        symbol: str,
        trade_type: str,
        entry_price: float,
        indicators: Dict[str, float],
        sentiment: Optional[Dict] = None,
        news: Optional[str] = None
    ) -> str:
        """Build the prompt for trade analysis"""
        
        prompt = f"""ANALYZE THIS TRADE SIGNAL:

SYMBOL: {symbol}
SIGNAL: {trade_type}
ENTRY PRICE: ${entry_price:,.2f}

📊 TECHNICAL INDICATORS:

RSI Score: {indicators.get('rsi_score', 0):+.1f}
MACD Score: {indicators.get('macd_score', 0):+.1f}
Bollinger Score: {indicators.get('bb_score', 0):+.1f}
Total Confidence: {indicators.get('total_score', 0):+.1f}

"""
        
        if sentiment:
            prompt += f"""📈 MARKET SENTIMENT:
Fear & Greed Index: {sentiment.get('value', 'N/A')}/100 ({sentiment.get('classification', 'N/A')})

"""
        
        if news:
            prompt += f"""📰 RECENT NEWS:
{news[:500]}...

"""
        
        prompt += """Based on this data, should this trade be taken?

Consider:
1. Do the technical indicators support this direction?
2. Is the entry timing good?
3. What is the risk/reward profile?
4. Are there any red flags?

Provide your analysis in the requested JSON format."""
        
        return prompt
    
    def get_market_analysis(
        self,
        symbol: str,
        indicators: Dict[str, float],
        current_price: float,
        sentiment: Optional[Dict] = None,
        news: Optional[str] = None
    ) -> Optional[AIAnalysisResult]:
        """
        Get general market analysis (not validating a specific trade).
        
        Args:
            symbol: Trading pair
            indicators: Technical indicators
            current_price: Current price
            sentiment: Optional sentiment data
            news: Optional recent news
        
        Returns:
            AIAnalysisResult with market analysis
        """
        if not self.is_available:
            return None
        
        try:
            client = self._get_client()
            if client is None:
                return None
            
            prompt = f"""ANALYZE THIS MARKET:

SYMBOL: {symbol}
CURRENT PRICE: ${current_price:,.2f}

📊 TECHNICAL INDICATORS:
RSI Score: {indicators.get('rsi_score', 0):+.1f}
MACD Score: {indicators.get('macd_score', 0):+.1f}
Bollinger Score: {indicators.get('bb_score', 0):+.1f}
Total Signal Score: {indicators.get('total_score', 0):+.1f}

"""
            
            if sentiment:
                prompt += f"""📈 SENTIMENT: {sentiment.get('value', 'N/A')}/100 ({sentiment.get('classification', 'N/A')})
"""
            
            if news:
                prompt += f"""📰 NEWS: {news[:300]}...
"""
            
            prompt += """
What is your independent analysis? Should a trader go LONG, SHORT, or stay NEUTRAL?"""
            
            completion = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert crypto technical analyst. Provide independent market analysis."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "market_analysis",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "direction": {"type": "string", "enum": ["LONG", "SHORT", "NEUTRAL"]},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                                "reasoning": {"type": "string"},
                                "key_factors": {"type": "array", "items": {"type": "string"}},
                                "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                                "entry_quality": {"type": "string", "enum": ["excellent", "good", "fair", "poor"]},
                                "technical_score": {"type": "number"},
                                "fundamental_score": {"type": "number"}
                            },
                            "required": ["direction", "confidence", "reasoning", "key_factors",
                                        "risk_level", "entry_quality", "technical_score", "fundamental_score"],
                            "additionalProperties": False
                        }
                    }
                },
                temperature=0.2
            )
            
            content = json.loads(completion.choices[0].message.content)
            usage = completion.usage
            cost = self._calculate_cost(usage.prompt_tokens, usage.completion_tokens)
            
            return AIAnalysisResult(
                symbol=symbol,
                direction=content["direction"],
                confidence=content["confidence"],
                reasoning=content["reasoning"],
                key_factors=content["key_factors"],
                risk_level=content["risk_level"],
                entry_quality=content["entry_quality"],
                technical_score=content["technical_score"],
                fundamental_score=content["fundamental_score"],
                timestamp=datetime.now(),
                cost_usd=cost
            )
            
        except Exception as e:
            logger.error(f"❌ Market analysis error: {e}")
            return None


# ============================================================
# SINGLETON INSTANCE
# ============================================================
_openai_service: Optional[OpenAIService] = None


def get_openai_service() -> OpenAIService:
    """Get singleton OpenAI service instance"""
    global _openai_service
    if _openai_service is None:
        _openai_service = OpenAIService()
    return _openai_service
