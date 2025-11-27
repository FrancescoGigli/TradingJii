"""
Test standalone per AI Validation System
USA GLI STESSI IDENTICI SEGNALI del tuo bot reale
"""

import os
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import config
from core.ai_decision_validator import AIDecisionValidator
from core.market_intelligence import MarketIntelligenceHub

# Mock exchange per testing
class MockExchange:
    pass

async def test_ai_validation():
    """Test AI validation con segnali REALI dal tuo bot"""
    
    print("=" * 80)
    print("🧪 TEST AI VALIDATION SYSTEM - REAL SIGNALS FROM YOUR BOT")
    print("=" * 80)
    
    # 1. Initialize AI Validator
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not found in .env")
        return
    
    validator = AIDecisionValidator(api_key=api_key, model=config.OPENAI_MODEL)
    
    if not validator.is_available():
        print("❌ AI Validator not available")
        return
    
    print(f"✅ AI Validator initialized ({config.OPENAI_MODEL})")
    print()
    
    # 2. Collect Market Intelligence
    print("📊 Collecting Market Intelligence...")
    mock_exchange = MockExchange()
    intel_hub = MarketIntelligenceHub(
        mock_exchange,
        cmc_api_key=os.getenv("CMC_PRO_API_KEY"),
        whale_api_key=os.getenv("WHALE_ALERT_API_KEY")
    )
    
    symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
    market_intel = await intel_hub.collect_intelligence(symbols)
    
    print(f"✅ News: {len(market_intel.news[:100])}+ chars")
    if market_intel.sentiment:
        s = market_intel.sentiment
        print(f"✅ Sentiment: {s.get('value', 'N/A')}/100 ({s.get('classification', 'N/A')})")
        print(f"   📍 Source: https://coinmarketcap.com/charts/fear-and-greed-index/")
    print()
    
    # 3. REAL SIGNALS from your bot's last cycle (logged at 10:31:02)
    # These are the EXACT signals XGBoost generated
    real_signals = [
        # BUY signals (LONG)
        {'symbol': 'BTC/USDT:USDT', 'signal_name': 'BUY', 'confidence': 0.399},
        {'symbol': 'USUAL/USDT:USDT', 'signal_name': 'BUY', 'confidence': 0.660},
        {'symbol': 'ETH/USDT:USDT', 'signal_name': 'BUY', 'confidence': 0.672},
        {'symbol': 'TNSR/USDT:USDT', 'signal_name': 'BUY', 'confidence': 0.585},
        {'symbol': 'PLUME/USDT:USDT', 'signal_name': 'BUY', 'confidence': 0.561},
        {'symbol': 'RESOLV/USDT:USDT', 'signal_name': 'BUY', 'confidence': 0.699},
        {'symbol': 'PARTI/USDT:USDT', 'signal_name': 'BUY', 'confidence': 0.709},
        
        # SELL signals (SHORT)
        {'symbol': 'PIPPIN/USDT:USDT', 'signal_name': 'SELL', 'confidence': 0.689},
        {'symbol': 'KAITO/USDT:USDT', 'signal_name': 'SELL', 'confidence': 0.718},
        {'symbol': 'ARC/USDT:USDT', 'signal_name': 'SELL', 'confidence': 0.710},
        {'symbol': 'SOL/USDT:USDT', 'signal_name': 'SELL', 'confidence': 0.698},
        {'symbol': 'PAXG/USDT:USDT', 'signal_name': 'SELL', 'confidence': 1.000},
        {'symbol': 'XAUT/USDT:USDT', 'signal_name': 'SELL', 'confidence': 0.605},
        {'symbol': 'PIEVERSE/USDT:USDT', 'signal_name': 'SELL', 'confidence': 0.573},
        {'symbol': 'FIL/USDT:USDT', 'signal_name': 'SELL', 'confidence': 0.727},
        {'symbol': 'MERL/USDT:USDT', 'signal_name': 'SELL', 'confidence': 0.711},
    ]
    
    print(f"🎯 REAL Signals from Your Bot ({len(real_signals)} total):")
    print()
    
    # Count by direction
    longs = [s for s in real_signals if s['signal_name'] == 'BUY']
    shorts = [s for s in real_signals if s['signal_name'] == 'SELL']
    
    print(f"   🟢 LONG signals: {len(longs)}")
    for sig in longs:
        symbol_short = sig['symbol'].replace('/USDT:USDT', '')
        print(f"      • {symbol_short}: {sig['confidence']*100:.1f}% confidence")
    
    print()
    print(f"   🔴 SHORT signals: {len(shorts)}")
    for sig in shorts:
        symbol_short = sig['symbol'].replace('/USDT:USDT', '')
        print(f"      • {symbol_short}: {sig['confidence']*100:.1f}% confidence")
    
    print()
    
    # 4. Get portfolio state (your real balance)
    portfolio_state = {
        'balance': 577.11,
        'available_balance': 577.11,
        'active_positions': 0
    }
    
    # 5. Call AI Validation (limiting to top 10 by confidence)
    print("=" * 80)
    print("🤖 CALLING GPT-4o WITH YOUR REAL SIGNALS...")
    print("=" * 80)
    print()
    
    # Sort by confidence and take top 10
    sorted_signals = sorted(real_signals, key=lambda x: x['confidence'], reverse=True)[:10]
    
    print(f"📊 Top 10 signals by ML confidence:")
    for i, sig in enumerate(sorted_signals, 1):
        symbol_short = sig['symbol'].replace('/USDT:USDT', '')
        direction = "🟢 LONG" if sig['signal_name'] == 'BUY' else "🔴 SHORT"
        print(f"   {i}. {symbol_short} {direction} - {sig['confidence']*100:.1f}%")
    print()
    
    # Call AI Validation
    validated_signals, ai_metadata = await validator.validate_signals(
        sorted_signals,
        market_intel,
        portfolio_state,
        max_signals=10
    )
    
    # 6. Show RAW RESPONSE (CRITICAL DEBUG)
    print("\n" + "=" * 80)
    print("🔍 RAW GPT-4o RESPONSE (CRITICAL DEBUG):")
    print("=" * 80)
    
    # Extract raw response from metadata if available
    if 'raw_response' in ai_metadata:
        raw_resp = ai_metadata['raw_response']
        print(raw_resp[:1000] if len(raw_resp) > 1000 else raw_resp)
    else:
        print("⚠️ Raw response not available in metadata")
        print(f"Metadata keys: {list(ai_metadata.keys())}")
    
    print("=" * 80)
    print()
    
    # 7. Show results SEGNALE PER SEGNALE
    print("=" * 80)
    print("📊 AI VALIDATION RESULTS (SIGNAL BY SIGNAL):")
    print("=" * 80)
    
    # Initialize lists BEFORE use
    approved_list = []
    rejected_list = []
    
    if not validated_signals:
        print("\n⚠️ NO VALIDATED SIGNALS RETURNED BY AI!")
        print(f"   AI returned {len(validated_signals)} signals")
        print(f"   Expected: 10 signals")
        print("\n   This means GPT-4o response did NOT contain signal decisions.")
        print("\n💡 POSSIBLE CAUSES:")
        print("   1. GPT-4o is too conservative (rejects everything)")
        print("   2. JSON schema too strict (can't generate valid response)")
        print("   3. Prompt has contradictions (confuses the AI)")
    
    for sig in validated_signals:
        symbol = sig.symbol.replace('/USDT:USDT', '')
        original = sig.original_signal
        direction = "🟢 LONG" if original['signal_name'] == 'BUY' else "🔴 SHORT"
        status = sig.action
        status_icon = "✅" if status == "approve" else "❌" if status == "reject" else "⏸️"
        
        print(f"\n{status_icon} {symbol} {direction}")
        print(f"   ML Confidence: {original['confidence']*100:.0f}%")
        print(f"   AI Action: {status.upper()}")
        if sig.confidence_boost != 0:
            print(f"   AI Adjustment: {sig.confidence_boost:+.0f}%")
        print(f"   💬 AI Reasoning: {sig.reasoning}")
        print(f"   ⚠️ Risk: {sig.risk_assessment.upper()}")
        print(f"   🎯 Priority: {sig.priority}/10")
        
        if status == "approve":
            approved_list.append((symbol, direction, original['signal_name']))
        else:
            rejected_list.append((symbol, direction, original['signal_name']))
    
    print("\n" + "=" * 80)
    print("📈 OVERALL ASSESSMENT:")
    print(f"   Market Outlook: {ai_metadata.get('market_outlook', 'N/A').upper()}")
    print(f"   Risk Level: {ai_metadata.get('overall_risk_level', 'N/A').upper()}")
    print(f"   Cost: ${ai_metadata.get('cost_usd', 0):.4f}")
    print("=" * 80)
    
    # 7. CRITICAL ANALYSIS - Did AI understand SHORT logic?
    print("\n" + "=" * 80)
    print("🔍 CRITICAL LOGIC CHECK:")
    print("=" * 80)
    
    sentiment_value = market_intel.sentiment.get('value', 50) if market_intel.sentiment else 50
    
    print(f"\n📊 MARKET CONDITIONS:")
    print(f"   😨 Sentiment: {sentiment_value}/100 ({market_intel.sentiment.get('classification', 'N/A')})")
    print(f"   📍 Source: https://coinmarketcap.com/charts/fear-and-greed-index/")
    
    if sentiment_value < 30:
        print(f"\n⚠️ EXTREME FEAR DETECTED ({sentiment_value}/100)")
        print("   Theory: SHORTs should be approved, LONGs should be rejected")
    
    # Count approved by direction
    approved_longs = sum(1 for _, _, sig in approved_list if sig == 'BUY')
    approved_shorts = sum(1 for _, _, sig in approved_list if sig == 'SELL')
    rejected_longs = sum(1 for _, _, sig in rejected_list if sig == 'BUY')
    rejected_shorts = sum(1 for _, _, sig in rejected_list if sig == 'SELL')
    
    print(f"\n📊 AI DECISIONS:")
    print(f"   🟢 LONGs: {approved_longs} approved, {rejected_longs} rejected")
    print(f"   🔴 SHORTs: {approved_shorts} approved, {rejected_shorts} rejected")
    
    print(f"\n🎯 LOGIC EVALUATION:")
    
    if sentiment_value < 30:
        # Extreme fear - should prioritize SHORTs
        if approved_shorts > approved_longs:
            print("   ✅ CORRECT: AI is prioritizing SHORTs during extreme fear!")
        elif approved_shorts > 0 and approved_longs == 0:
            print("   ✅ GOOD: AI approved only SHORTs (no LONGs) during fear")
        elif approved_longs > 0:
            print(f"   ⚠️ WARNING: AI approved {approved_longs} LONGs during extreme fear (risky!)")
        else:
            print("   ⚠️ TOO CONSERVATIVE: AI rejected ALL signals")
            print("      (might be too cautious, could consider strong SHORT signals)")
    elif sentiment_value > 75:
        # Extreme greed - should prioritize SHORTs
        if approved_shorts > approved_longs:
            print("   ✅ CORRECT: AI is prioritizing SHORTs during extreme greed!")
        else:
            print("   ⚠️ AI should prioritize SHORTs during extreme greed")
    else:
        # Neutral - balance is expected
        print("   ✅ NEUTRAL SENTIMENT: AI evaluating on technical merit")
    
    print("\n" + "=" * 80)
    print("✅ Test completed!")
    print("=" * 80)
    
    if approved_list:
        print("\n🎯 APPROVED TRADES (would be executed):")
        for symbol, direction, _ in approved_list:
            print(f"   • {symbol} {direction}")
    else:
        print("\n😐 NO TRADES APPROVED")

if __name__ == "__main__":
    asyncio.run(test_ai_validation())
