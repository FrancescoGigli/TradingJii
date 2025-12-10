"""
Test Walk-Forward Training System

Verifica che tutti i moduli funzionino correttamente con dati sintetici.
"""

import numpy as np
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)

print("="*80)
print("🧪 TESTING WALK-FORWARD TRAINING SYSTEM")
print("="*80)

# Test 1: Importazione moduli
print("\n1️⃣ Test: Importazione moduli...")
try:
    from training.labeling import label_with_triple_barrier, label_with_sl_awareness_v2
    from training.features import create_temporal_features
    from training.xgb_trainer import train_xgb_model, create_temporal_split
    from training.walk_forward import walk_forward_training
    from training_simulator import TradingSimulator
    from training_report import generate_walk_forward_report
    print("✅ Tutti i moduli importati correttamente")
except Exception as e:
    print(f"❌ Errore importazione: {e}")
    exit(1)

# Test 2: Triple Barrier Labeling
print("\n2️⃣ Test: Triple Barrier Labeling...")
try:
    # Crea dati sintetici
    np.random.seed(42)
    n_candles = 100
    df_test = pd.DataFrame({
        'open': np.random.randn(n_candles).cumsum() + 100,
        'high': np.random.randn(n_candles).cumsum() + 102,
        'low': np.random.randn(n_candles).cumsum() + 98,
        'close': np.random.randn(n_candles).cumsum() + 100,
        'volume': np.random.rand(n_candles) * 1000
    })
    
    labels = label_with_triple_barrier(df_test, lookforward=5, tp_pct=0.04, sl_pct=0.07)
    
    assert len(labels) == len(df_test), "Labels length mismatch"
    assert set(np.unique(labels)).issubset({0, 1, 2}), "Invalid label values"
    
    print(f"✅ Triple Barrier: {len(labels)} labels, distribuzione: {np.bincount(labels)}")
except Exception as e:
    print(f"❌ Errore Triple Barrier: {e}")
    exit(1)

# Test 3: Feature Engineering
print("\n3️⃣ Test: Temporal Feature Engineering...")
try:
    # Crea sequenza di features (timesteps=5, features=33)
    sequence = np.random.randn(5, 33)
    features = create_temporal_features(sequence)
    
    assert len(features) == 66, f"Expected 66 features, got {len(features)}"
    assert np.isfinite(features).all(), "Features contain NaN or Inf"
    
    print(f"✅ Features: {len(features)} features create correttamente")
except Exception as e:
    print(f"❌ Errore Feature Engineering: {e}")
    exit(1)

# Test 4: Temporal Split
print("\n4️⃣ Test: Temporal Split...")
try:
    X_dummy = np.random.randn(1000, 66)
    y_dummy = np.random.randint(0, 3, 1000)
    
    X_train, y_train, X_val, y_val = create_temporal_split(X_dummy, y_dummy, train_pct=0.80)
    
    assert len(X_train) == 800, f"Expected 800 train samples, got {len(X_train)}"
    assert len(X_val) == 200, f"Expected 200 val samples, got {len(X_val)}"
    
    print(f"✅ Split: Train={len(X_train)}, Val={len(X_val)}")
except Exception as e:
    print(f"❌ Errore Temporal Split: {e}")
    exit(1)

# Test 5: Trading Simulator
print("\n5️⃣ Test: Trading Simulator...")
try:
    simulator = TradingSimulator()
    
    # Crea dati di test per una simulazione
    df_sim = pd.DataFrame({
        'high': [101, 102, 103, 102, 101],
        'low': [99, 100, 101, 100, 99],
        'close': [100, 101, 102, 101, 100]
    })
    
    trade_result = simulator.simulate_trade(
        symbol='TEST',
        direction='BUY',
        entry_idx=0,
        entry_price=100,
        future_data=df_sim,
        confidence=0.75
    )
    
    assert trade_result.symbol == 'TEST'
    assert trade_result.direction == 'BUY'
    assert trade_result.exit_reason in ['SL', 'TRAILING', 'END_OF_DATA']
    
    print(f"✅ Simulator: Trade simulato, exit reason={trade_result.exit_reason}")
except Exception as e:
    print(f"❌ Errore Trading Simulator: {e}")
    exit(1)

# Test 6: XGBoost Training (piccolo dataset)
print("\n6️⃣ Test: XGBoost Training...")
try:
    # Dataset piccolo per test veloce
    X_train_test = np.random.randn(100, 66)
    y_train_test = np.random.randint(0, 3, 100)
    X_val_test = np.random.randn(30, 66)
    y_val_test = np.random.randint(0, 3, 30)
    
    model, scaler, metrics = train_xgb_model(X_train_test, y_train_test, X_val_test, y_val_test)
    
    assert model is not None, "Model is None"
    assert scaler is not None, "Scaler is None"
    assert 'val_accuracy' in metrics, "Missing val_accuracy in metrics"
    
    print(f"✅ XGBoost: Model trained, accuracy={metrics['val_accuracy']:.2f}")
except Exception as e:
    print(f"❌ Errore XGBoost Training: {e}")
    exit(1)

# Test 7: Report Generation
print("\n7️⃣ Test: Report Generation...")
try:
    # Dati mock per report
    rounds_results = [
        {'total_trades': 10, 'winning_trades': 6, 'losing_trades': 4, 'win_rate': 60.0,
         'total_profit': 15.0, 'total_loss': 8.0, 'net_profit': 7.0, 'profit_factor': 1.875,
         'avg_holding_time': 3.5, 'exit_reasons': {'SL': 4, 'TRAILING': 6}},
        {'total_trades': 12, 'winning_trades': 7, 'losing_trades': 5, 'win_rate': 58.3,
         'total_profit': 18.0, 'total_loss': 10.0, 'net_profit': 8.0, 'profit_factor': 1.8,
         'avg_holding_time': 4.0, 'exit_reasons': {'SL': 5, 'TRAILING': 7}},
        {'total_trades': 11, 'winning_trades': 7, 'losing_trades': 4, 'win_rate': 63.6,
         'total_profit': 20.0, 'total_loss': 9.0, 'net_profit': 11.0, 'profit_factor': 2.22,
         'avg_holding_time': 3.8, 'exit_reasons': {'SL': 4, 'TRAILING': 7}}
    ]
    
    ml_metrics = {'val_accuracy': 0.72, 'val_precision': 0.70, 'val_recall': 0.68, 'val_f1': 0.69}
    
    report = generate_walk_forward_report(rounds_results, ml_metrics, 'TEST')
    
    assert 'aggregate' in report, "Missing aggregate in report"
    assert 'recommendation' in report, "Missing recommendation in report"
    assert report['aggregate']['win_rate'] > 0, "Win rate is 0"
    
    print(f"✅ Report: Generato correttamente, Win Rate={report['aggregate']['win_rate']:.1f}%")
    print(f"   Recommendation: {report['recommendation']['decision']}")
except Exception as e:
    print(f"❌ Errore Report Generation: {e}")
    exit(1)

print("\n" + "="*80)
print("✅ TUTTI I TEST COMPLETATI CON SUCCESSO!")
print("="*80)
print("\n📝 SUMMARY:")
print("   ✅ Moduli importati")
print("   ✅ Triple Barrier labeling")
print("   ✅ Feature engineering")
print("   ✅ Temporal split")
print("   ✅ Trading simulator")
print("   ✅ XGBoost training")
print("   ✅ Report generation")
print("\n🎉 Il sistema Walk-Forward è pronto per l'uso!")
print("\n💡 Per training completo: python trainer_new.py")
print("="*80)
