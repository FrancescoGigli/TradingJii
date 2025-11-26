from openai import OpenAI
from dotenv import load_dotenv
import os
import json 

load_dotenv()
# read api key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)

def previsione_trading_agent(prompt):
    """
    Esegue una chiamata a OpenAI per ottenere una decisione di trading
    in formato JSON strutturato.
    Ritorna una tupla:
      - decisions: lista di decisioni (una per ogni coin analizzata).
      - metadata: dict con usage tokens, cost, modello ecc.
    """
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",  # GPT-4o supports structured outputs (json_schema)
            messages=[
                {"role": "system", "content": "You are a professional crypto trading assistant. always output valid JSON array of decisions."},
                {"role": "user", "content": prompt}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "trade_decisions",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "decisions": {
                                "type": "array",
                                "description": "List of trading decisions for analyzed coins",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "operation": {
                                            "type": "string",
                                            "description": "Type of trading operation to perform",
                                            "enum": ["open", "close", "hold"]
                                        },
                                        "symbol": {
                                            "type": "string",
                                            "description": "The cryptocurrency symbol (e.g. BTC, ETH, SOL, etc.)"
                                        },
                                        "direction": {
                                            "type": "string",
                                            "description": "Trade direction: long or short. Must be empty string for hold.",
                                            "enum": ["long", "short", ""]
                                        },
                                        "target_portion_of_balance": {
                                            "type": "number",
                                            "description": "Fraction of balance to use (max 0.1 or 10% per position recommended).",
                                            "minimum": 0,
                                            "maximum": 1
                                        },
                                        "leverage": {
                                            "type": "number",
                                            "description": "Leverage multiplier. User requested FIXED 10x.",
                                            "enum": [10]
                                        },
                                        "reason": {
                                            "type": "string",
                                            "description": "Brief explanation of the trading decision",
                                        }
                                    },
                                    "required": [
                                        "operation",
                                        "symbol",
                                        "direction",
                                        "target_portion_of_balance",
                                        "leverage",
                                        "reason"
                                    ],
                                    "additionalProperties": False
                                }
                            }
                        },
                        "required": ["decisions"],
                        "additionalProperties": False
                    }
                }
            }
        )
        
        # Parsa e restituisce il JSON dalla risposta
        content_str = completion.choices[0].message.content
        content = json.loads(content_str)
        decisions = content.get("decisions", [])
        
        # Usage stats
        usage = completion.usage
        prompt_tokens = usage.prompt_tokens
        completion_tokens = usage.completion_tokens
        
        # Cost calculator for GPT-4o (approx as of late 2024)
        # Input: $2.50 / 1M tokens
        # Output: $10.00 / 1M tokens
        cost = (prompt_tokens / 1_000_000 * 2.5) + (completion_tokens / 1_000_000 * 10.0)
        
        metadata = {
            "model": "gpt-4o",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": usage.total_tokens,
            "cost_usd": round(cost, 6),
            "raw_response_excerpt": content_str[:200] + "..." if len(content_str) > 200 else content_str
        }
        
        return decisions, metadata

    except Exception as e:
        print(f"Errore durante la chiamata a OpenAI: {e}")
        # Ritorna lista vuota o un hold safe e metadata vuoto
        return [{
            "operation": "hold",
            "symbol": "BTC",
            "direction": "",
            "target_portion_of_balance": 0,
            "leverage": 10,
            "reason": f"Error calling AI: {str(e)}"
        }], {"error": str(e)}
