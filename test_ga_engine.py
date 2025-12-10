"""
Test completo del GA Engine - Fresh Start Test

Questo script testa l'intero flusso del BLOCCO 3 - Strategy Optimizer:
1. Carica un modello XGBoost esistente
2. Prepara dati di test
3. Esegue ottimizzazione GA
4. Confronta risultati baseline vs ottimizzato
5. Salva parametri ottimali

IMPORTANTE: Eseguire dalla root del progetto
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    print("="*80)
    print("🧬 GA ENGINE - FRESH START TEST")
    print("="*80)
    print()
    
    # Step 1: Check dependencies
    print("📋 STEP 1: Checking dependencies...")
    try:
        import numpy as np
        import pandas as pd
        import joblib
        from deap import base, creator, tools
        print("✅ All dependencies installed")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("   Run: pip install deap numpy pandas joblib xgboost")
        return
    
    # Step 2: Check if models exist
    print("\n📋 STEP 2: Checking for trained models...")
    model_dir = Path("trained_models")
    if not model_dir.exists():
        print(f"❌ Model directory not found: {model_dir}")
        print("   Please train models first with: python trainer_new.py")
        return
    
    model_file = model_dir / "xgb_model_15m.pkl"
    scaler_file = model_dir / "xgb_scaler_15m.pkl"
    
    if not model_file.exists():
        print(f"❌ Model not found: {model_file}")
        print("   Please train XGBoost model for 15m timeframe first")
        return
    
    print(f"✅ Found model: {model_file}")
    print(f"✅ Found scaler: {scaler_file}")
    
    # Step 3: Load model and scaler
    print("\n📋 STEP 3: Loading model and scaler...")
    try:
        model = joblib.load(model_file)
        scaler = joblib.load(scaler_file)
        print("✅ Model and scaler loaded successfully")
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        return
    
    # Step 4: Create mock test data
    print("\n📋 STEP 4: Creating mock test data...")
    print("   (In production, use real historical data)")
    
    # Mock data for testing (in production, load real data)
    n_samples = 100
    n_features = 66  # Must match training features
    
    X_test = np.random.randn(n_samples, n_features)
    
    # Create mock dataframe with required columns
    df_test = pd.DataFrame({
        'close': np.random.uniform(40000, 45000, n_samples),
        'high': np.random.uniform(40000, 45000, n_samples),
        'low': np.random.uniform(40000, 45000, n_samples),
        'atr': np.random.uniform(500, 1000, n_samples),
        'volatility': np.random.uniform(0.03, 0.08, n_samples),
    })
    
    print(f"✅ Created mock data: {n_samples} samples")
    print(f"   X_test shape: {X_test.shape}")
    print(f"   df_test shape: {df_test.shape}")
    
    # Step 5: Test baseline evaluation
    print("\n📋 STEP 5: Testing baseline evaluation...")
    try:
        from strategy_optimizer.strategy_params import StrategyParams
        from strategy_optimizer.backtest_simulator import BacktestSimulator
        
        baseline_params = StrategyParams.from_config()
        print(f"✅ Baseline params created:")
        print(f"   Confidence: {baseline_params.min_confidence_buy:.2%}")
        print(f"   SL: {baseline_params.sl_percentage:.2%}")
        print(f"   Leverage: {baseline_params.leverage_base}")
        
        # Quick backtest
        simulator = BacktestSimulator(initial_capital=1000.0)
        trades, metrics = simulator.backtest_with_signals_from_model(
            model=model,
            scaler=scaler,
            X_test=X_test,
            df_test=df_test,
            params=baseline_params,
            duration_days=90
        )
        
        print(f"\n✅ Baseline backtest complete:")
        print(f"   Trades: {metrics.total_trades}")
        print(f"   Win Rate: {metrics.win_rate:.1%}")
        print(f"   Fitness: {metrics.fitness_score:.2f}")
        
    except Exception as e:
        print(f"❌ Error in baseline evaluation: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 6: Test GA optimization (quick version)
    print("\n📋 STEP 6: Testing GA optimization (quick version)...")
    print("   Population: 10, Generations: 5 (fast test)")
    
    try:
        from strategy_optimizer.ga_orchestrator import GAOrchestrator
        
        orchestrator = GAOrchestrator(
            initial_capital=1000.0,
            duration_days=90,
            output_dir="test_ga_results"
        )
        
        best_params, best_metrics = orchestrator.run_optimization(
            model=model,
            scaler=scaler,
            X_test=X_test,
            df_test=df_test,
            population_size=10,  # Small for quick test
            n_generations=5,     # Few generations for quick test
            save_results=True,
            compare_with_baseline=True
        )
        
        print(f"\n✅ GA optimization complete!")
        print(f"\n📊 RESULTS COMPARISON:")
        print(f"   Baseline fitness:  {metrics.fitness_score:.2f}")
        print(f"   Optimized fitness: {best_metrics.fitness_score:.2f}")
        print(f"   Improvement: {((best_metrics.fitness_score - metrics.fitness_score) / metrics.fitness_score * 100):+.1f}%")
        
        print(f"\n📊 OPTIMIZED PARAMETERS:")
        print(f"   Confidence: {baseline_params.min_confidence_buy:.2%} → {best_params.min_confidence_buy:.2%}")
        print(f"   SL: {baseline_params.sl_percentage:.2%} → {best_params.sl_percentage:.2%}")
        print(f"   Leverage: {baseline_params.leverage_base} → {best_params.leverage_base}")
        
        print(f"\n💾 Results saved to: test_ga_results/")
        print(f"   Check the directory for detailed reports and plots")
        
    except Exception as e:
        print(f"❌ Error in GA optimization: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 7: Summary
    print("\n" + "="*80)
    print("✅ GA ENGINE TEST COMPLETED SUCCESSFULLY!")
    print("="*80)
    print()
    print("📌 NEXT STEPS:")
    print("   1. Review results in test_ga_results/")
    print("   2. For production: Use larger population (50+) and more generations (30+)")
    print("   3. Use real historical data instead of mock data")
    print("   4. Validate optimized params with walk-forward testing")
    print()
    print("🚀 GA Engine is ready for use!")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⛔ Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
