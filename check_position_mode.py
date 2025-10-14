#!/usr/bin/env python3
"""
🔍 CHECK BYBIT POSITION MODE

Script per verificare se il tuo account è in One-Way Mode o Hedge Mode
"""

import asyncio
import ccxt.async_support as ccxt
from config import API_KEY, API_SECRET

async def check_position_mode():
    """Verifica la modalità delle posizioni su Bybit"""
    
    exchange = ccxt.bybit({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
        }
    })
    
    try:
        print("=" * 80)
        print("🔍 CHECKING BYBIT POSITION MODE")
        print("=" * 80)
        
        # Metodo 1: Query delle impostazioni account
        try:
            # Bybit API v5 endpoint per position mode
            response = await exchange.private_get_v5_position_list({
                'category': 'linear',
                'limit': 1
            })
            
            # Estrai info dalle posizioni
            if response.get('result') and response['result'].get('list'):
                positions = response['result']['list']
                if positions:
                    pos = positions[0]
                    position_idx = pos.get('positionIdx', 0)
                    
                    print(f"\n📊 ACCOUNT MODE DETECTED:")
                    print(f"   positionIdx found in response: {position_idx}")
                    
                    if position_idx == 0:
                        print("\n✅ MODE: ONE-WAY MODE")
                        print("   - Puoi avere SOLO Long OPPURE Short per simbolo")
                        print("   - Non puoi Long e Short contemporaneamente")
                        print("   - position_idx deve essere SEMPRE 0")
                        print("   - Più semplice da gestire")
                    else:
                        print("\n✅ MODE: HEDGE MODE") 
                        print("   - Puoi avere Long E Short per simbolo contemporaneamente")
                        print("   - position_idx=1 per LONG, position_idx=2 per SHORT")
                        print("   - Più complesso ma più flessibile")
                    
        except Exception as e:
            print(f"\n⚠️  Could not query positions: {e}")
        
        # Metodo 2: Dall'errore precedente
        print("\n" + "=" * 80)
        print("📝 DIAGNOSIS FROM YOUR ERROR:")
        print("=" * 80)
        print("""
L'errore che hai ricevuto era:
"position idx(2) not match position mode(0)"
                  ^^^                      ^^^
                  |                        |
           Codice provava           Account è in
           ad usare idx=2           mode(0)

POSITION MODE(0) = ONE-WAY MODE ✅

Questo significa che il tuo account è configurato in ONE-WAY MODE.
In questo modo:
- Puoi avere SOLO Long OPPURE Short per simbolo
- Devi SEMPRE usare position_idx=0 nelle API calls
- È la configurazione più comune e più semplice
""")
        
        # Metodo 3: Come verificare su Bybit Web
        print("=" * 80)
        print("🌐 COME VERIFICARE SU BYBIT WEB:")
        print("=" * 80)
        print("""
1. Vai su https://www.bybit.com
2. Login al tuo account
3. Clicca su "Derivatives" → "USDT Perpetual"
4. Clicca sull'icona ⚙️ (Settings) in alto a destra
5. Cerca "Position Mode":
   
   📍 ONE-WAY MODE:
      - Vedi toggle "One-Way Mode" ATTIVO
      - Descrizione: "Only Long or Short positions"
   
   📍 HEDGE MODE:
      - Vedi toggle "Hedge Mode" ATTIVO
      - Descrizione: "Both Long and Short positions"

NOTA: Cambiare mode richiede chiusura di tutte le posizioni!
""")
        
        print("=" * 80)
        print("✅ CHECK COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(check_position_mode())
