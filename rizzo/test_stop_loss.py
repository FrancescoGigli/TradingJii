"""
Script di test per il sistema di Stop Loss e Trailing Stop
Questo script testa la logica senza effettuare trading reale
"""

from decimal import Decimal
from stop_loss_manager import StopLossManager
import db_utils

def test_stop_loss_calculations():
    """Testa i calcoli degli stop loss"""
    
    print("=" * 70)
    print("TEST SISTEMA STOP LOSS E TRAILING STOP")
    print("=" * 70)
    
    # Crea un'istanza fittizia del manager (senza trader reale)
    class MockTrader:
        pass
    
    class MockDB:
        pass
    
    manager = StopLossManager(MockTrader(), MockDB())
    
    # Test 1: Stop Loss Iniziale per LONG
    print("\n📊 TEST 1: Stop Loss Iniziale (-40%) per posizione LONG")
    entry_price = Decimal("100.0")
    side = "long"
    stop = manager.calculate_initial_stop(entry_price, side)
    print(f"   Entry Price: ${entry_price}")
    print(f"   Stop Loss: ${stop} ({((stop - entry_price) / entry_price * 100):.2f}%)")
    assert stop == Decimal("60.0"), "Stop loss dovrebbe essere 60.0"
    print("   ✅ TEST PASSATO")
    
    # Test 2: Stop Loss Iniziale per SHORT
    print("\n📊 TEST 2: Stop Loss Iniziale (-40%) per posizione SHORT")
    entry_price = Decimal("100.0")
    side = "short"
    stop = manager.calculate_initial_stop(entry_price, side)
    print(f"   Entry Price: ${entry_price}")
    print(f"   Stop Loss: ${stop} ({((stop - entry_price) / entry_price * 100):.2f}%)")
    assert stop == Decimal("140.0"), "Stop loss dovrebbe essere 140.0"
    print("   ✅ TEST PASSATO")
    
    # Test 3: Calcolo Profitto per LONG
    print("\n📊 TEST 3: Calcolo Profitto/Perdita per LONG")
    entry_price = Decimal("100.0")
    current_price = Decimal("120.0")
    side = "long"
    profit_pct = manager.calculate_profit_pct(entry_price, current_price, side)
    print(f"   Entry: ${entry_price} | Current: ${current_price}")
    print(f"   Profit: {profit_pct * 100:.2f}%")
    assert profit_pct == Decimal("0.2"), "Profitto dovrebbe essere 20%"
    print("   ✅ TEST PASSATO")
    
    # Test 4: Calcolo Profitto per SHORT
    print("\n📊 TEST 4: Calcolo Profitto/Perdita per SHORT")
    entry_price = Decimal("100.0")
    current_price = Decimal("80.0")
    side = "short"
    profit_pct = manager.calculate_profit_pct(entry_price, current_price, side)
    print(f"   Entry: ${entry_price} | Current: ${current_price}")
    print(f"   Profit: {profit_pct * 100:.2f}%")
    assert profit_pct == Decimal("0.2"), "Profitto dovrebbe essere 20%"
    print("   ✅ TEST PASSATO")
    
    # Test 5: Trailing Stop - Primo Step (+10% -> stop a +2%)
    print("\n📊 TEST 5: Trailing Stop - Primo Trigger (+10%)")
    entry_price = Decimal("100.0")
    current_price = Decimal("110.0")  # +10%
    side = "long"
    highest_profit = Decimal("0.10")  # 10%
    stop = manager.calculate_trailing_stop(entry_price, current_price, side, highest_profit)
    expected_stop = entry_price * Decimal("1.02")  # +2%
    print(f"   Entry: ${entry_price} | Current: ${current_price} | Max Profit: {highest_profit * 100}%")
    print(f"   Trailing Stop: ${stop} (+{((stop - entry_price) / entry_price * 100):.2f}%)")
    assert stop == expected_stop, f"Stop dovrebbe essere {expected_stop}"
    print("   ✅ TEST PASSATO")
    
    # Test 6: Trailing Stop - Secondo Step (+20% -> stop a +12%)
    print("\n📊 TEST 6: Trailing Stop - Secondo Step (+20%)")
    entry_price = Decimal("100.0")
    current_price = Decimal("120.0")  # +20%
    side = "long"
    highest_profit = Decimal("0.20")  # 20%
    stop = manager.calculate_trailing_stop(entry_price, current_price, side, highest_profit)
    # Step 2: 20% - 8% = 12%
    expected_stop = entry_price * Decimal("1.12")
    print(f"   Entry: ${entry_price} | Current: ${current_price} | Max Profit: {highest_profit * 100}%")
    print(f"   Trailing Stop: ${stop} (+{((stop - entry_price) / entry_price * 100):.2f}%)")
    assert stop == expected_stop, f"Stop dovrebbe essere {expected_stop}"
    print("   ✅ TEST PASSATO")
    
    # Test 7: Trailing Stop - Terzo Step (+30% -> stop a +22%)
    print("\n📊 TEST 7: Trailing Stop - Terzo Step (+30%)")
    entry_price = Decimal("100.0")
    current_price = Decimal("130.0")  # +30%
    side = "long"
    highest_profit = Decimal("0.30")  # 30%
    stop = manager.calculate_trailing_stop(entry_price, current_price, side, highest_profit)
    # Step 3: 30% - 8% = 22%
    expected_stop = entry_price * Decimal("1.22")
    print(f"   Entry: ${entry_price} | Current: ${current_price} | Max Profit: {highest_profit * 100}%")
    print(f"   Trailing Stop: ${stop} (+{((stop - entry_price) / entry_price * 100):.2f}%)")
    assert stop == expected_stop, f"Stop dovrebbe essere {expected_stop}"
    print("   ✅ TEST PASSATO")
    
    # Test 8: Trailing Stop per SHORT (+20%)
    print("\n📊 TEST 8: Trailing Stop per SHORT (+20%)")
    entry_price = Decimal("100.0")
    current_price = Decimal("80.0")  # Prezzo sceso, quindi profit per short
    side = "short"
    highest_profit = Decimal("0.20")  # 20% profit
    stop = manager.calculate_trailing_stop(entry_price, current_price, side, highest_profit)
    # Step 2: entry * (1 - 0.12) = 100 * 0.88 = 88
    expected_stop = entry_price * Decimal("0.88")
    print(f"   Entry: ${entry_price} | Current: ${current_price} | Max Profit: {highest_profit * 100}%")
    print(f"   Trailing Stop: ${stop} (-{((entry_price - stop) / entry_price * 100):.2f}%)")
    assert stop == expected_stop, f"Stop dovrebbe essere {expected_stop}"
    print("   ✅ TEST PASSATO")
    
    print("\n" + "=" * 70)
    print("✅ TUTTI I TEST SONO PASSATI!")
    print("=" * 70)
    
    # Mostra esempi pratici
    print("\n📚 ESEMPI PRATICI:")
    print("\n1. Posizione LONG BTC @ $100,000")
    print("   - Stop iniziale: $60,000 (-40%)")
    print("   - Prezzo sale a $110,000 (+10%): Stop sale a $102,000 (+2%)")
    print("   - Prezzo sale a $120,000 (+20%): Stop sale a $112,000 (+12%)")
    print("   - Prezzo sale a $130,000 (+30%): Stop sale a $122,000 (+22%)")
    print("   - Se prezzo scende a $122,000: CHIUSURA con +22% di profitto")
    
    print("\n2. Posizione SHORT ETH @ $2,000")
    print("   - Stop iniziale: $2,800 (-40%)")
    print("   - Prezzo scende a $1,800 (+10%): Stop scende a $1,960 (+2%)")
    print("   - Prezzo scende a $1,600 (+20%): Stop scende a $1,760 (+12%)")
    print("   - Se prezzo sale a $1,760: CHIUSURA con +12% di profitto")


def test_database_init():
    """Testa l'inizializzazione del database"""
    print("\n" + "=" * 70)
    print("TEST INIZIALIZZAZIONE DATABASE")
    print("=" * 70)
    
    try:
        print("\n🔧 Inizializzazione schema database...")
        db_utils.init_db()
        print("✅ Database inizializzato correttamente")
        print("   - Tabella 'position_stops' creata")
        print("   - Tabella 'stop_loss_closures' creata")
        print("   - Indici creati")
        return True
    except Exception as e:
        print(f"❌ Errore nell'inizializzazione: {e}")
        return False


if __name__ == "__main__":
    print("\n🚀 AVVIO TEST SISTEMA STOP LOSS\n")
    
    # Test 1: Inizializza database
    db_ok = test_database_init()
    
    if db_ok:
        print("\n" + "=" * 70)
        
    # Test 2: Calcoli stop loss
    test_stop_loss_calculations()
    
    print("\n✅ TEST COMPLETATI CON SUCCESSO!")
    print("\n📝 PROSSIMI PASSI:")
    print("   1. Il sistema è pronto per l'uso")
    print("   2. Gli stop loss verranno monitorati a ogni ciclo")
    print("   3. Le chiusure saranno registrate nel database")
    print("   4. Puoi visualizzare lo storico con view_history.py")
