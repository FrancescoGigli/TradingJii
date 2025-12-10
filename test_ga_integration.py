"""
Test GA Integration with config.py
Verifies that GA-optimized parameters are correctly loaded and applied
"""

import sys
from pathlib import Path

def test_ga_integration():
    """Test that GA parameters are loaded correctly"""
    
    print("=" * 80)
    print("🧬 GA INTEGRATION TEST")
    print("=" * 80)
    print()
    
    # Step 1: Check if optimized params file exists
    print("📋 STEP 1: Checking for GA-optimized parameters file...")
    ga_params_file = Path(__file__).parent / "strategy_optimizer" / "optimized_params.json"
    
    if not ga_params_file.exists():
        print(f"❌ ERROR: {ga_params_file} not found!")
        print("   Run test_ga_engine.py first to generate optimized parameters.")
        return False
    
    print(f"✅ Found: {ga_params_file}")
    print()
    
    # Step 2: Import config and check parameters
    print("📋 STEP 2: Importing config and checking parameters...")
    try:
        import config
    except Exception as e:
        print(f"❌ ERROR importing config: {e}")
        return False
    
    print("✅ Config imported successfully")
    print()
    
    # Step 3: Verify GA parameters were loaded
    print("📋 STEP 3: Verifying GA parameters loaded...")
    
    if not hasattr(config, '_GA_PARAMS_LOADED'):
        print("❌ ERROR: _GA_PARAMS_LOADED flag not found in config")
        return False
    
    if not config._GA_PARAMS_LOADED:
        print("⚠️  WARNING: GA parameters file exists but was not loaded")
        print("   Check config.py for loading errors")
        return False
    
    print("✅ GA parameters loaded successfully")
    print()
    
    # Step 4: Check specific parameters
    print("📋 STEP 4: Checking parameter values...")
    print()
    
    # Default values (what would be used without GA)
    defaults = {
        "LEVERAGE": 5,
        "STOP_LOSS_PCT": 0.06,
        "MIN_CONFIDENCE": 0.65
    }
    
    # Current values (potentially GA-optimized)
    current = {
        "LEVERAGE": config.LEVERAGE,
        "STOP_LOSS_PCT": config.STOP_LOSS_PCT,
        "MIN_CONFIDENCE": config.MIN_CONFIDENCE
    }
    
    # GA optimized values (from file)
    import json
    with open(ga_params_file, 'r') as f:
        ga_params = json.load(f)
    
    optimized = {
        "LEVERAGE": ga_params.get("leverage_base", defaults["LEVERAGE"]),
        "STOP_LOSS_PCT": ga_params.get("sl_percentage", defaults["STOP_LOSS_PCT"]),
        "MIN_CONFIDENCE": ga_params.get("min_confidence_buy", defaults["MIN_CONFIDENCE"])
    }
    
    print("┌─────────────────────┬─────────────┬─────────────┬─────────────┐")
    print("│ Parameter           │   Default   │  Optimized  │   Loaded    │")
    print("├─────────────────────┼─────────────┼─────────────┼─────────────┤")
    
    all_match = True
    for param in defaults.keys():
        default_val = defaults[param]
        optimized_val = optimized[param]
        current_val = current[param]
        
        # Check if current matches optimized (not default)
        matches = abs(current_val - optimized_val) < 0.0001
        status = "✅" if matches else "❌"
        
        if not matches:
            all_match = False
        
        # Format values
        if isinstance(default_val, float):
            default_str = f"{default_val:.4f}"
            optimized_str = f"{optimized_val:.4f}"
            current_str = f"{current_val:.4f}"
        else:
            default_str = f"{default_val}"
            optimized_str = f"{optimized_val}"
            current_str = f"{current_val}"
        
        print(f"│ {param:19} │ {default_str:>11} │ {optimized_str:>11} │ {current_str:>9} {status} │")
    
    print("└─────────────────────┴─────────────┴─────────────┴─────────────┘")
    print()
    
    if all_match:
        print("✅ All parameters match GA-optimized values!")
    else:
        print("❌ Some parameters don't match GA-optimized values")
        print("   This could indicate a loading issue in config.py")
        return False
    
    print()
    
    # Step 5: Summary
    print("=" * 80)
    print("📊 INTEGRATION TEST SUMMARY")
    print("=" * 80)
    print()
    print("✅ GA-optimized parameters file exists")
    print("✅ Parameters loaded successfully into config.py")
    print("✅ All key parameters match GA-optimized values")
    print()
    print("🎯 RESULT: Integration is working correctly!")
    print()
    print("When you run main.py, the bot will automatically use these optimized parameters.")
    print()
    
    # Show additional info
    print("📋 ADDITIONAL GA PARAMETERS AVAILABLE:")
    print()
    interesting_params = [
        ("min_confidence_sell", "Min confidence for SELL signals"),
        ("min_risk_reward", "Minimum risk/reward ratio"),
        ("max_positions", "Maximum concurrent positions"),
        ("fixed_size_usd", "Fixed position size in USD")
    ]
    
    for param_name, description in interesting_params:
        if param_name in ga_params:
            value = ga_params[param_name]
            if isinstance(value, float):
                print(f"   • {description:40} : {value:.4f}")
            else:
                print(f"   • {description:40} : {value}")
    
    print()
    print("💡 TIP: To update parameters, run test_ga_engine.py with new data")
    print("         and the latest results will be automatically picked up.")
    print()
    
    return True

if __name__ == "__main__":
    success = test_ga_integration()
    sys.exit(0 if success else 1)
