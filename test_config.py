"""
Test Script: Verifica nuove configurazioni Global Model
"""

import config

print("=" * 70)
print("🧪 TEST CONFIGURAZIONI GLOBAL MODEL")
print("=" * 70)

# Test 1: Global Model
print("\n1️⃣ GLOBAL MODEL CONFIG:")
print(f"   GLOBAL_MODEL_ENABLED: {config.GLOBAL_MODEL_ENABLED}")
assert hasattr(config, 'GLOBAL_MODEL_ENABLED'), "❌ GLOBAL_MODEL_ENABLED mancante!"
assert config.GLOBAL_MODEL_ENABLED == True, "❌ GLOBAL_MODEL_ENABLED dovrebbe essere True!"
print("   ✅ Global Model configurato correttamente")

# Test 2: Triple Barrier
print("\n2️⃣ TRIPLE BARRIER CONFIG:")
print(f"   TRIPLE_BARRIER_ENABLED: {config.TRIPLE_BARRIER_ENABLED}")
print(f"   TRIPLE_BARRIER_TP_PCT: {config.TRIPLE_BARRIER_TP_PCT}")
print(f"   TRIPLE_BARRIER_SL_PCT: {config.TRIPLE_BARRIER_SL_PCT}")
print(f"   TRIPLE_BARRIER_LOOKFORWARD: {config.TRIPLE_BARRIER_LOOKFORWARD}")
assert hasattr(config, 'TRIPLE_BARRIER_ENABLED'), "❌ TRIPLE_BARRIER_ENABLED mancante!"
assert config.TRIPLE_BARRIER_ENABLED == True, "❌ TRIPLE_BARRIER_ENABLED dovrebbe essere True!"
assert config.TRIPLE_BARRIER_TP_PCT == 0.09, f"❌ TP dovrebbe essere 0.09, è {config.TRIPLE_BARRIER_TP_PCT}"
assert config.TRIPLE_BARRIER_SL_PCT == 0.06, f"❌ SL dovrebbe essere 0.06, è {config.TRIPLE_BARRIER_SL_PCT}"
assert config.TRIPLE_BARRIER_LOOKFORWARD == 8, f"❌ Lookforward dovrebbe essere 8, è {config.TRIPLE_BARRIER_LOOKFORWARD}"
print("   ✅ Triple Barrier configurato correttamente")

# Test 3: Z-Score Normalization
print("\n3️⃣ Z-SCORE NORMALIZATION CONFIG:")
print(f"   Z_SCORE_NORMALIZATION: {config.Z_SCORE_NORMALIZATION}")
print(f"   Z_SCORE_WINDOW: {config.Z_SCORE_WINDOW}")
assert hasattr(config, 'Z_SCORE_NORMALIZATION'), "❌ Z_SCORE_NORMALIZATION mancante!"
assert config.Z_SCORE_NORMALIZATION == True, "❌ Z_SCORE_NORMALIZATION dovrebbe essere True!"
assert config.Z_SCORE_WINDOW == 96, f"❌ Window dovrebbe essere 96, è {config.Z_SCORE_WINDOW}"
print("   ✅ Z-Score Normalization configurato correttamente")

# Test 4: Advanced Class Weighting
print("\n4️⃣ ADVANCED CLASS WEIGHTING CONFIG:")
print(f"   ADVANCED_CLASS_WEIGHTING: {config.ADVANCED_CLASS_WEIGHTING}")
assert hasattr(config, 'ADVANCED_CLASS_WEIGHTING'), "❌ ADVANCED_CLASS_WEIGHTING mancante!"
assert config.ADVANCED_CLASS_WEIGHTING == True, "❌ ADVANCED_CLASS_WEIGHTING dovrebbe essere True!"
print("   ✅ Advanced Class Weighting configurato correttamente")

# Test 5: Backward Compatibility (vecchie config ancora presenti)
print("\n5️⃣ BACKWARD COMPATIBILITY:")
print(f"   SL_AWARENESS_ENABLED: {config.SL_AWARENESS_ENABLED}")
print(f"   USE_CLASS_WEIGHTS: {config.USE_CLASS_WEIGHTS}")
print(f"   STOP_LOSS_PCT: {config.STOP_LOSS_PCT}")
assert hasattr(config, 'SL_AWARENESS_ENABLED'), "❌ SL_AWARENESS_ENABLED mancante!"
assert hasattr(config, 'USE_CLASS_WEIGHTS'), "❌ USE_CLASS_WEIGHTS mancante!"
assert hasattr(config, 'STOP_LOSS_PCT'), "❌ STOP_LOSS_PCT mancante!"
print("   ✅ Backward compatibility mantenuta")

# Test 6: Alignment Triple Barrier con trading
print("\n6️⃣ ALIGNMENT VERIFICATION:")
print(f"   TRIPLE_BARRIER_SL_PCT: {config.TRIPLE_BARRIER_SL_PCT}")
print(f"   STOP_LOSS_PCT (runtime): {config.STOP_LOSS_PCT}")
assert config.TRIPLE_BARRIER_SL_PCT == config.STOP_LOSS_PCT, \
    f"❌ SL training ({config.TRIPLE_BARRIER_SL_PCT}) != SL runtime ({config.STOP_LOSS_PCT})"
print("   ✅ Training SL allineato con runtime SL")

# Summary
print("\n" + "=" * 70)
print("✅ TUTTI I TEST PASSATI!")
print("=" * 70)
print("\n📊 CONFIGURAZIONE SUMMARY:")
print(f"   • Global Model: ENABLED")
print(f"   • Triple Barrier: ENABLED (TP=9%, SL=6%, lookforward=8)")
print(f"   • Z-Score Normalization: ENABLED (window=96)")
print(f"   • Advanced Class Weighting: ENABLED")
print(f"   • Backward Compatible: YES")
print("\n🚀 Step 1 completato! Pronto per Step 2 (Z-Score implementation)\n")
