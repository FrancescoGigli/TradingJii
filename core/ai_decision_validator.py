"""
AI Decision Validator - Integration from Rizzo project
Uses GPT-4o to validate and prioritize XGBoost trading signals
"""

import logging
import json
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI library not available - AI validation disabled")


@dataclass
class ValidatedSignal:
    """Container for AI-validated trading signal"""
    symbol: str
    original_signal: Dict
    action: str  # "approve", "reject", "defer"
    priority: int  # 1-10
    reasoning: str
    risk_assessment: str  # "low", "medium", "high"
    confidence_boost: float  # -20 to +20
    ai_timestamp: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "action": self.action,
            "priority": self.priority,
            "reasoning": self.reasoning,
            "risk_assessment": self.risk_assessment,
            "confidence_boost": self.confidence_boost,
            "original_confidence": self.original_signal.get("confidence", 0),
            "final_confidence": self.original_signal.get("confidence", 0) + self.confidence_boost,
            "ai_timestamp": self.ai_timestamp.isoformat()
        }


class AIDecisionValidator:
    """
    AI-powered validator for trading signals
    Uses GPT-4o to analyze XGBoost signals with market intelligence context
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        
        if not OPENAI_AVAILABLE:
            logging.warning("⚠️ OpenAI not available - AI validation will be disabled")
            self.client = None
        elif not self.api_key:
            logging.warning("⚠️ No OpenAI API key - AI validation will be disabled")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)
            logging.info(f"✅ AI Decision Validator initialized with {model}")
    
    def is_available(self) -> bool:
        """Check if AI validation is available"""
        return self.client is not None
    
    async def validate_signals(
        self,
        signals: List[Dict],
        market_intelligence: 'MarketIntelligence',
        portfolio_state: Dict,
        max_signals: int = 10
    ) -> Tuple[List[ValidatedSignal], Dict]:
        """
        Validate trading signals using GPT-4o
        
        Args:
            signals: List of XGBoost signals to validate
            market_intelligence: Market intelligence data (news, sentiment, forecasts, whale alerts)
            portfolio_state: Current portfolio state (balance, positions, etc.)
            max_signals: Maximum number of signals to validate
        
        Returns:
            Tuple of (validated_signals, metadata)
        """
        if not self.is_available():
            logging.warning("⚠️ AI validation not available - returning original signals")
            # Return original signals as "approved" with no reasoning
            validated = [
                ValidatedSignal(
                    symbol=s["symbol"],
                    original_signal=s,
                    action="approve",
                    priority=5,
                    reasoning="AI validation disabled",
                    risk_assessment="medium",
                    confidence_boost=0,
                    ai_timestamp=datetime.now()
                )
                for s in signals[:max_signals]
            ]
            return validated, {"error": "AI validation not available"}
        
        try:
            # Limit signals to validate
            signals_to_validate = signals[:max_signals]
            
            # Build the prompt
            prompt = self._build_prompt(signals_to_validate, market_intelligence, portfolio_state)
            
            # DEBUG: Log the FULL prompt sent to GPT-4o
            logging.info("=" * 80)
            logging.info("📝 PROMPT SENT TO GPT-4o:")
            logging.info("=" * 80)
            logging.info(prompt)
            logging.info("=" * 80)
            
            logging.info(f"🤖 Calling GPT-4o to validate {len(signals_to_validate)} signals...")
            
            # Call OpenAI API with structured output
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert crypto trading AI validator. Analyze ML signals with market context and provide structured decisions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "signal_validation",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "validated_signals": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "symbol": {"type": "string"},
                                            "action": {
                                                "type": "string",
                                                "enum": ["approve", "reject", "defer"]
                                            },
                                            "priority": {
                                                "type": "integer",
                                                "minimum": 1,
                                                "maximum": 10
                                            },
                                            "reasoning": {"type": "string"},
                                            "risk_assessment": {
                                                "type": "string",
                                                "enum": ["low", "medium", "high"]
                                            },
                                            "confidence_boost": {
                                                "type": "number",
                                                "minimum": -20,
                                                "maximum": 20
                                            }
                                        },
                                        "required": ["symbol", "action", "priority", "reasoning", "risk_assessment", "confidence_boost"],
                                        "additionalProperties": False
                                    }
                                },
                                "market_outlook": {
                                    "type": "string",
                                    "enum": ["bullish", "neutral", "bearish"]
                                },
                                "overall_risk_level": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high"]
                                }
                            },
                            "required": ["validated_signals", "market_outlook", "overall_risk_level"],
                            "additionalProperties": False
                        }
                    }
                },
                temperature=0.3  # Lower temperature for more consistent decisions
            )
            
            # Parse response
            raw_response = completion.choices[0].message.content
            
            # DEBUG: Log raw response to see what GPT-4o actually returns
            logging.info("=" * 80)
            logging.info("🔍 RAW GPT-4o RESPONSE:")
            logging.info(raw_response[:1000] if len(raw_response) > 1000 else raw_response)
            logging.info("=" * 80)
            
            # Try to parse JSON - clean response first
            try:
                # Remove BOM, leading/trailing whitespace, and any markdown code blocks
                clean_response = raw_response.strip()
                if clean_response.startswith("```json"):
                    clean_response = clean_response[7:]
                if clean_response.startswith("```"):
                    clean_response = clean_response[3:]
                if clean_response.endswith("```"):
                    clean_response = clean_response[:-3]
                clean_response = clean_response.strip()
                
                # Remove BOM if present
                if clean_response.startswith('\ufeff'):
                    clean_response = clean_response[1:]
                
                content = json.loads(clean_response)
            except json.JSONDecodeError as json_err:
                logging.error(f"❌ JSON Parse Error: {json_err}")
                logging.error(f"❌ Raw response (first 500 chars): {repr(raw_response[:500])}")
                logging.error(f"❌ Clean response (first 500 chars): {repr(clean_response[:500])}")
                raise
            
            # DEBUG: Log parsed structure
            logging.info(f"📊 Parsed validated_signals count: {len(content.get('validated_signals', []))}")
            
            # Calculate usage stats
            usage = completion.usage
            cost = (usage.prompt_tokens / 1_000_000 * 2.5) + (usage.completion_tokens / 1_000_000 * 10.0)
            
            metadata = {
                "model": self.model,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cost_usd": round(cost, 6),
                "market_outlook": content.get("market_outlook", "neutral"),
                "overall_risk_level": content.get("overall_risk_level", "medium"),
                "timestamp": datetime.now().isoformat(),
                "raw_response": raw_response  # CRITICAL: Save for debugging
            }
            
            # Convert to ValidatedSignal objects
            validated_signals = []
            for ai_decision in content.get("validated_signals", []):
                # Find original signal - try exact match first, then partial match
                ai_symbol = ai_decision["symbol"]
                original = next(
                    (s for s in signals_to_validate if s["symbol"] == ai_symbol),
                    None
                )
                
                # If no exact match, try partial match (e.g., "PAXG" matches "PAXG/USDT:USDT")
                if not original:
                    original = next(
                        (s for s in signals_to_validate if ai_symbol in s["symbol"] or s["symbol"].startswith(ai_symbol)),
                        None
                    )
                
                if original:
                    validated = ValidatedSignal(
                        symbol=ai_decision["symbol"],
                        original_signal=original,
                        action=ai_decision["action"],
                        priority=ai_decision["priority"],
                        reasoning=ai_decision["reasoning"],
                        risk_assessment=ai_decision["risk_assessment"],
                        confidence_boost=ai_decision["confidence_boost"],
                        ai_timestamp=datetime.now()
                    )
                    validated_signals.append(validated)
            
            # Sort by priority (highest first)
            validated_signals.sort(key=lambda x: x.priority, reverse=True)
            
            # Log results
            approved = sum(1 for v in validated_signals if v.action == "approve")
            rejected = sum(1 for v in validated_signals if v.action == "reject")
            deferred = sum(1 for v in validated_signals if v.action == "defer")
            
            logging.info(
                f"✅ AI Validation complete: {approved} approved, {rejected} rejected, {deferred} deferred | "
                f"Cost: ${cost:.4f} | Outlook: {metadata['market_outlook']}"
            )
            
            return validated_signals, metadata
            
        except Exception as e:
            logging.error(f"❌ AI validation error: {e}")
            # Fallback: return original signals as approved
            validated = [
                ValidatedSignal(
                    symbol=s["symbol"],
                    original_signal=s,
                    action="approve",
                    priority=5,
                    reasoning=f"AI error: {str(e)}",
                    risk_assessment="medium",
                    confidence_boost=0,
                    ai_timestamp=datetime.now()
                )
                for s in signals[:max_signals]
            ]
            return validated, {"error": str(e)}
    
    def _build_prompt(
        self,
        signals: List[Dict],
        market_intelligence: 'MarketIntelligence',
        portfolio_state: Dict
    ) -> str:
        """Build the validation prompt for GPT-4o from template file"""
        
        # Load prompt template from file
        template_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'ai_validation_base.txt')
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
        except FileNotFoundError:
            logging.error(f"❌ Prompt template not found at {template_path}")
            # Fallback to minimal hardcoded version
            prompt_template = "Analyze these signals: {signals_list}\n{market_intelligence}"
        
        # Format portfolio
        balance = portfolio_state.get("balance", 0)
        available = portfolio_state.get("available_balance", 0)
        positions = portfolio_state.get("active_positions", 0)
        
        # Get market intelligence formatted string
        from core.market_intelligence import MarketIntelligenceHub
        hub = MarketIntelligenceHub(None)  # Just for formatting
        intel_text = hub.format_for_prompt(market_intelligence)
        
        # Format signals with clear LONG/SHORT indication
        signals_detailed = []
        for i, sig in enumerate(signals, 1):
            symbol_short = sig["symbol"].replace("/USDT:USDT", "")
            direction = "🟢 LONG" if sig['signal_name'] == 'BUY' else "🔴 SHORT"
            signals_detailed.append(
                f"{i}. {symbol_short} - {direction} | "
                f"ML Confidence: {sig['confidence']*100:.1f}% | "
                f"Signal: {sig['signal_name']}"
            )
        
        # Replace placeholders in template
        prompt = prompt_template.format(
            balance=f"{balance:.2f}",
            available_balance=f"{available:.2f}",
            active_positions=positions,
            signals_list=chr(10).join(signals_detailed),
            market_intelligence=intel_text
        )

        
        return prompt
    
    def filter_approved_signals(self, validated_signals: List[ValidatedSignal]) -> List[Dict]:
        """
        Filter and return only approved signals, sorted by priority
        Returns original signal dicts with boosted confidence
        """
        approved = [
            v for v in validated_signals
            if v.action == "approve"
        ]
        
        # Sort by priority
        approved.sort(key=lambda x: x.priority, reverse=True)
        
        # Return modified original signals
        result = []
        for v in approved:
            signal = v.original_signal.copy()
            # Boost confidence based on AI analysis
            signal["confidence"] = min(100, max(0, signal["confidence"] + v.confidence_boost))
            signal["ai_priority"] = v.priority
            signal["ai_reasoning"] = v.reasoning
            signal["ai_risk"] = v.risk_assessment
            result.append(signal)
        
        return result
