#!/usr/bin/env python3
"""
Test script for Dual-Engine System (XGBoost vs GPT-4o)

Tests:
1. AI Technical Analyst module
2. Decision Comparator logic
3. Execution strategies
4. Statistics tracking
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from termcolor import colored

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

def test_imports():
    """Test all imports work correctly"""
    print(colored("\n" + "="*60, "cyan"))
    print(colored("TEST 1: IMPORT CHECK", "cyan", attrs=['bold']))
    print(colored("="*60, "cyan"))
    
    try:
        from core.ai_technical_analyst import AITechnicalAnalyst, AISignal, global_ai_technical_analyst
        print(colored("✅ AI Technical Analyst imported", "green"))
    except ImportError as e:
        print(colored(f"❌ Failed to import AI Technical Analyst: {e}", "red"))
        return False
    
    try:
        from core.decision_comparator import (
            DecisionComparator, 
            ExecutionStrategy, 
            ComparisonResult,
            DualEngineStats,
            global_decision_comparator
        )
        print(colored("✅ Decision Comparator imported", "green"))
    except ImportError as e:
        print(colored(f"❌ Failed to import Decision Comparator: {e}", "red"))
        return False
    
    try:
        import config
        print(colored("✅ Config imported", "green"))
        print(f"   DUAL_ENGINE_ENABLED = {getattr(config, 'DUAL_ENGINE_ENABLED', 'NOT SET')}")
        print(f"   DUAL_ENGINE_STRATEGY = {getattr(config, 'DUAL_ENGINE_STRATEGY', 'NOT SET')}")
        print(f"   AI_ANALYST_ENABLED = {getattr(config, 'AI_ANALYST_ENABLED', 'NOT SET')}")
    except ImportError as e:
        print(colored(f"❌ Failed to import config: {e}", "red"))
        return False
    
    return True


def test_decision_comparator():
    """Test Decision Comparator logic"""
    print(colored("\n" + "="*60, "cyan"))
    print(colored("TEST 2: DECISION COMPARATOR", "cyan", attrs=['bold']))
    print(colored("="*60, "cyan"))
    
    from core.decision_comparator import DecisionComparator, ExecutionStrategy
    from core.ai_technical_analyst import AISignal
    from datetime import datetime
    
    # Create comparator
    comparator = DecisionComparator(ExecutionStrategy.CONSENSUS)
    
    # Test Case 1: Agreement (both LONG)
    print(colored("\n📊 Test Case 1: XGB LONG + AI LONG (Agreement)", "yellow"))
    xgb_signal_1 = {
        'symbol': 'BTC/USDT:USDT',
        'signal': 1,  # LONG
        'confidence': 0.82,  # 82%
        'signal_name': 'BUY'
    }
    ai_signal_1 = AISignal(
        symbol='BTC/USDT:USDT',
        direction='LONG',
        confidence=78,
        reasoning='Strong bullish momentum with RSI oversold bounce',
        key_factors=['RSI oversold', 'MACD cross up', 'Volume surge'],
        risk_level='medium',
        entry_quality='good',
        technical_score=75,
        fundamental_score=72,
        timestamp=datetime.now()
    )
    
    result_1 = comparator.compare_signal(xgb_signal_1, ai_signal_1)
    print(f"   Agreement: {result_1.agreement}")
    print(f"   Consensus Confidence: {result_1.consensus_confidence:.1f}%")
    print(f"   Should Trade: {result_1.should_trade}")
    print(f"   Reason: {result_1.execution_reason}")
    
    assert result_1.agreement == True, "Should agree on LONG"
    print(colored("   ✅ PASSED", "green"))
    
    # Test Case 2: Disagreement (XGB LONG, AI SHORT)
    print(colored("\n📊 Test Case 2: XGB LONG + AI SHORT (Disagreement)", "yellow"))
    xgb_signal_2 = {
        'symbol': 'ETH/USDT:USDT',
        'signal': 1,  # LONG
        'confidence': 0.75,
        'signal_name': 'BUY'
    }
    ai_signal_2 = AISignal(
        symbol='ETH/USDT:USDT',
        direction='SHORT',
        confidence=72,
        reasoning='Bearish divergence detected, expecting pullback',
        key_factors=['MACD divergence', 'RSI overbought', 'Near resistance'],
        risk_level='high',
        entry_quality='fair',
        technical_score=68,
        fundamental_score=60,
        timestamp=datetime.now()
    )
    
    result_2 = comparator.compare_signal(xgb_signal_2, ai_signal_2)
    print(f"   Agreement: {result_2.agreement}")
    print(f"   Should Trade (consensus strategy): {result_2.should_trade}")
    print(f"   Reason: {result_2.execution_reason}")
    
    assert result_2.agreement == False, "Should disagree"
    assert result_2.should_trade == False, "Consensus strategy should NOT trade on disagreement"
    print(colored("   ✅ PASSED", "green"))
    
    # Test Case 3: AI NEUTRAL
    print(colored("\n📊 Test Case 3: XGB LONG + AI NEUTRAL", "yellow"))
    ai_signal_3 = AISignal(
        symbol='SOL/USDT:USDT',
        direction='NEUTRAL',
        confidence=55,
        reasoning='Mixed signals, ranging market with weak trend',
        key_factors=['ADX below 20', 'Mixed EMA', 'No clear direction'],
        risk_level='high',
        entry_quality='poor',
        technical_score=50,
        fundamental_score=52,
        timestamp=datetime.now()
    )
    xgb_signal_3 = {
        'symbol': 'SOL/USDT:USDT',
        'signal': 1,
        'confidence': 0.70,
        'signal_name': 'BUY'
    }
    
    result_3 = comparator.compare_signal(xgb_signal_3, ai_signal_3)
    print(f"   Agreement: {result_3.agreement}")
    print(f"   Should Trade: {result_3.should_trade}")
    print(f"   Reason: {result_3.execution_reason}")
    
    assert result_3.agreement == False, "NEUTRAL should not agree"
    print(colored("   ✅ PASSED", "green"))
    
    # Test statistics
    print(colored("\n📊 Statistics Summary:", "yellow"))
    stats = comparator.get_stats_summary()
    print(f"   XGB Signals: {stats['xgb']['signals']}")
    print(f"   AI Signals: {stats['ai']['signals']}")
    print(f"   Agreement Rate: {stats['consensus']['agreement_rate']:.1f}%")
    print(f"   Disagreements: {stats['disagreements_count']}")
    
    return True


def test_execution_strategies():
    """Test different execution strategies"""
    print(colored("\n" + "="*60, "cyan"))
    print(colored("TEST 3: EXECUTION STRATEGIES", "cyan", attrs=['bold']))
    print(colored("="*60, "cyan"))
    
    from core.decision_comparator import DecisionComparator, ExecutionStrategy
    from core.ai_technical_analyst import AISignal
    from datetime import datetime
    
    xgb_signal = {
        'symbol': 'TEST/USDT:USDT',
        'signal': 1,
        'confidence': 0.80,
        'signal_name': 'BUY'
    }
    ai_signal = AISignal(
        symbol='TEST/USDT:USDT',
        direction='LONG',
        confidence=75,
        reasoning='Test signal',
        key_factors=['Factor 1', 'Factor 2'],
        risk_level='medium',
        entry_quality='good',
        technical_score=75,
        fundamental_score=70,
        timestamp=datetime.now()
    )
    
    # Test each strategy
    strategies = [
        ExecutionStrategy.XGBOOST_ONLY,
        ExecutionStrategy.AI_ONLY,
        ExecutionStrategy.CONSENSUS,
        ExecutionStrategy.WEIGHTED,
    ]
    
    for strategy in strategies:
        print(colored(f"\n📊 Strategy: {strategy.value.upper()}", "yellow"))
        comparator = DecisionComparator(strategy)
        result = comparator.compare_signal(xgb_signal, ai_signal)
        print(f"   Should Trade: {result.should_trade}")
        print(f"   Reason: {result.execution_reason}")
    
    print(colored("\n   ✅ All strategies executed", "green"))
    return True


def test_ai_technical_analyst():
    """Test AI Technical Analyst (requires OpenAI API key)"""
    print(colored("\n" + "="*60, "cyan"))
    print(colored("TEST 4: AI TECHNICAL ANALYST", "cyan", attrs=['bold']))
    print(colored("="*60, "cyan"))
    
    from core.ai_technical_analyst import AITechnicalAnalyst
    
    analyst = AITechnicalAnalyst()
    
    if not analyst.is_available():
        print(colored("⚠️ AI Analyst not available (no OpenAI API key)", "yellow"))
        print("   Set OPENAI_API_KEY environment variable to test")
        return True  # Not a failure, just not configured
    
    print(colored("✅ AI Technical Analyst is available", "green"))
    
    # Test with sample data
    print(colored("\n🧠 Testing AI analysis with sample data...", "magenta"))
    
    sample_indicators = {
        'close': 45000.0,
        'open': 44800.0,
        'high': 45200.0,
        'low': 44500.0,
        'volume': 1000000,
        'ema5': 44900,
        'ema10': 44700,
        'ema20': 44500,
        'rsi_fast': 65.5,
        'stoch_rsi': 72.0,
        'macd': 150.0,
        'macd_signal': 120.0,
        'macd_histogram': 30.0,
        'atr': 500.0,
        'volatility': 0.025,
        'adx': 32.5,
        'bollinger_hband': 46000,
        'bollinger_lband': 44000,
        'vwap': 44850,
        'obv': 5000000,
        'resistance_dist_10': 0.02,
        'support_dist_10': -0.03,
        'volatility_squeeze': 0.3,
        'price_acceleration': 0.002,
        'vol_acceleration': 0.45
    }
    
    async def run_test():
        result = await analyst.analyze_symbol(
            symbol='BTC/USDT:USDT',
            indicators=sample_indicators,
            market_intel=None,
            current_price=45000.0
        )
        return result
    
    result = asyncio.run(run_test())
    
    if result:
        print(colored(f"\n✅ AI Analysis Result:", "green"))
        print(f"   Direction: {result.direction}")
        print(f"   Confidence: {result.confidence}%")
        print(f"   Risk Level: {result.risk_level}")
        print(f"   Entry Quality: {result.entry_quality}")
        print(f"   Reasoning: {result.reasoning[:100]}...")
        print(f"   Key Factors: {result.key_factors}")
    else:
        print(colored("❌ AI analysis returned None", "red"))
        return False
    
    return True


def test_statistics_dashboard():
    """Test statistics dashboard display"""
    print(colored("\n" + "="*60, "cyan"))
    print(colored("TEST 5: STATISTICS DASHBOARD", "cyan", attrs=['bold']))
    print(colored("="*60, "cyan"))
    
    from core.decision_comparator import DecisionComparator, ExecutionStrategy
    
    comparator = DecisionComparator()
    
    # Simulate some trade outcomes
    comparator.record_trade_outcome('BTC/USDT:USDT', 'consensus', 15.50, True)
    comparator.record_trade_outcome('ETH/USDT:USDT', 'consensus', -8.20, False)
    comparator.record_trade_outcome('SOL/USDT:USDT', 'xgb', 12.30, True)
    comparator.record_trade_outcome('DOGE/USDT:USDT', 'xgb', -5.40, False)
    comparator.record_trade_outcome('XRP/USDT:USDT', 'ai', 18.90, True)
    
    # Display dashboard
    print(colored("\n📊 Displaying Stats Dashboard:", "yellow"))
    comparator.display_stats_dashboard()
    
    print(colored("\n   ✅ Dashboard displayed successfully", "green"))
    return True


def main():
    """Run all tests"""
    print(colored("\n" + "="*70, "magenta", attrs=['bold']))
    print(colored("      DUAL-ENGINE SYSTEM TEST SUITE", "magenta", attrs=['bold']))
    print(colored("      XGBoost ML vs GPT-4o AI Parallel Analysis", "magenta"))
    print(colored("="*70 + "\n", "magenta", attrs=['bold']))
    
    tests = [
        ("Import Check", test_imports),
        ("Decision Comparator", test_decision_comparator),
        ("Execution Strategies", test_execution_strategies),
        ("AI Technical Analyst", test_ai_technical_analyst),
        ("Statistics Dashboard", test_statistics_dashboard),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(colored(f"\n❌ {name} FAILED with exception: {e}", "red"))
            results.append((name, False))
    
    # Summary
    print(colored("\n" + "="*70, "cyan", attrs=['bold']))
    print(colored("TEST SUMMARY", "cyan", attrs=['bold']))
    print(colored("="*70, "cyan"))
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = colored("✅ PASSED", "green") if passed else colored("❌ FAILED", "red")
        print(f"   {name}: {status}")
    
    print(colored("="*70, "cyan"))
    
    if passed_count == total_count:
        print(colored(f"\n🎉 ALL TESTS PASSED ({passed_count}/{total_count})", "green", attrs=['bold']))
    else:
        print(colored(f"\n⚠️ SOME TESTS FAILED ({passed_count}/{total_count} passed)", "yellow", attrs=['bold']))
    
    print(colored("\n" + "="*70 + "\n", "cyan"))
    
    return passed_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
