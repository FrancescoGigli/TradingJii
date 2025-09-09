#!/usr/bin/env python3
"""
🔧 TEST CONNESSIONE BYBIT - Verifica fix timestamp

Questo script testa la connessione a Bybit e la sincronizzazione timestamp
senza avviare l'intero sistema di trading.

Utile per:
- Verificare che i fix timestamp funzionino
- Testare le credenziali API
- Diagnosticare problemi di connessione
"""

import asyncio
import logging
from datetime import datetime
import ccxt.async_support as ccxt_async
from termcolor import colored

# Setup logging semplice
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

async def test_bybit_connection():
    """Test completo della connessione Bybit con diagnostica avanzata"""
    
    print(colored("\n🔧 BYBIT CONNECTION TEST - Diagnostica Timestamp Fix", "cyan", attrs=['bold']))
    print(colored("=" * 80, "cyan"))
    
    # Import config
    try:
        from config import exchange_config
        print(colored("✅ Configurazione caricata", "green"))
    except Exception as e:
        print(colored(f"❌ Errore caricamento config: {e}", "red"))
        return False
    
    # Inizializza exchange
    print(colored("\n🚀 FASE 1: Inizializzazione Exchange", "yellow", attrs=['bold']))
    
    async_exchange = None
    try:
        async_exchange = ccxt_async.bybit(exchange_config)
        print(colored("✅ Exchange Bybit inizializzato", "green"))
        print(colored(f"📊 recv_window configurato: {exchange_config['options']['recvWindow']}ms", "cyan"))
    except Exception as e:
        print(colored(f"❌ Errore inizializzazione exchange: {e}", "red"))
        return False
    
    # Test sincronizzazione timestamp (identico al main.py)
    print(colored("\n🕐 FASE 2: Test Sincronizzazione Timestamp", "yellow", attrs=['bold']))
    
    max_sync_attempts = 3
    sync_success = False
    best_time_diff = float('inf')
    
    for attempt in range(max_sync_attempts):
        try:
            print(colored(f"   Tentativo {attempt + 1}/{max_sync_attempts}...", "cyan"))
            
            # Step 1: Load markets
            await async_exchange.load_markets()
            print(colored("   ✅ Markets caricati", "green"))
            
            # Step 2: Timestamp sync
            await async_exchange.load_time_difference()
            print(colored("   ✅ Timestamp sync eseguito", "green"))
            
            # Step 3: Verify sync quality  
            server_time = await async_exchange.fetch_time()
            local_time = async_exchange.milliseconds()
            time_diff = abs(server_time - local_time)
            
            print(colored(f"   📊 Server time: {server_time}", "cyan"))
            print(colored(f"   📊 Local time:  {local_time}", "cyan"))
            print(colored(f"   📊 Differenza:  {time_diff}ms", "yellow"))
            
            if time_diff < best_time_diff:
                best_time_diff = time_diff
            
            # Valuta qualità sync
            if time_diff <= 2000:  
                print(colored(f"   🎉 ECCELLENTE: Differenza {time_diff}ms ≤ 2000ms", "green"))
                sync_success = True
                break
            elif time_diff <= 5000:  
                print(colored(f"   ✅ BUONO: Differenza {time_diff}ms ≤ 5000ms", "green"))
                sync_success = True
                break
            elif time_diff <= 10000:
                print(colored(f"   ⚠️ ACCETTABILE: Differenza {time_diff}ms ≤ 10000ms", "yellow"))
                sync_success = True
                break
            else:
                print(colored(f"   ❌ PROBLEMATICO: Differenza {time_diff}ms > 10000ms", "red"))
                if attempt < max_sync_attempts - 1:
                    print(colored("   🔄 Ritentativo in 2 secondi...", "yellow"))
                    await asyncio.sleep(2)
                    
        except Exception as sync_error:
            print(colored(f"   ❌ Tentativo {attempt + 1} fallito: {sync_error}", "red"))
            if attempt < max_sync_attempts - 1:
                print(colored("   🔄 Ritentativo in 3 secondi...", "yellow"))
                await asyncio.sleep(3)
    
    print(colored(f"\n📊 RISULTATO SINCRONIZZAZIONE:", "white", attrs=['bold']))
    if sync_success:
        print(colored(f"✅ SUCCESSO - Miglior differenza: {best_time_diff}ms", "green", attrs=['bold']))
    else:
        print(colored(f"❌ FALLIMENTO - Miglior differenza: {best_time_diff}ms", "red", attrs=['bold']))
        print(colored("💡 SUGGERIMENTI:", "yellow"))
        print(colored("   1. Esegui: w32tm /resync /force (come Amministratore)", "yellow"))
        print(colored("   2. Verifica connessione internet stabile", "yellow"))
        print(colored("   3. Controlla timezone sistema", "yellow"))
    
    # Test API chiamate critiche
    print(colored("\n🎯 FASE 3: Test API Calls Critiche", "yellow", attrs=['bold']))
    
    api_tests = [
        ("Balance", "fetch_balance"),
        ("Positions", "fetch_positions"),  
        ("Tickers", "fetch_ticker"),
        ("Server Time", "fetch_time")
    ]
    
    api_success_count = 0
    
    for test_name, api_method in api_tests:
        try:
            print(colored(f"   Testing {test_name}...", "cyan"))
            
            if api_method == "fetch_balance":
                result = await async_exchange.fetch_balance()
                usdt_balance = result.get('USDT', {}).get('total', 0)
                print(colored(f"   ✅ {test_name}: Balance USDT = {usdt_balance:.2f}", "green"))
                
            elif api_method == "fetch_positions":
                result = await async_exchange.fetch_positions(None, {'limit': 5, 'type': 'swap'})
                positions_count = len([p for p in result if float(p.get('contracts', 0)) > 0])
                print(colored(f"   ✅ {test_name}: {positions_count} posizioni attive", "green"))
                
            elif api_method == "fetch_ticker":
                result = await async_exchange.fetch_ticker('BTC/USDT:USDT')
                btc_price = result.get('last', 0)
                print(colored(f"   ✅ {test_name}: BTC/USDT = ${btc_price:,.2f}", "green"))
                
            elif api_method == "fetch_time":
                result = await async_exchange.fetch_time()
                server_time_readable = datetime.fromtimestamp(result/1000).strftime('%H:%M:%S')
                print(colored(f"   ✅ {test_name}: Server time = {server_time_readable}", "green"))
            
            api_success_count += 1
            
        except Exception as api_error:
            error_str = str(api_error).lower()
            if "timestamp" in error_str or "recv_window" in error_str:
                print(colored(f"   ❌ {test_name}: TIMESTAMP ISSUE - {api_error}", "red"))
            elif "invalid api" in error_str or "signature" in error_str:
                print(colored(f"   ❌ {test_name}: API KEY ISSUE - {api_error}", "red"))  
            else:
                print(colored(f"   ⚠️ {test_name}: {api_error}", "yellow"))
    
    # Final Summary
    print(colored("\n🏆 RISULTATI FINALI", "cyan", attrs=['bold']))
    print(colored("=" * 80, "cyan"))
    
    print(colored(f"🕐 Timestamp Sync: {'✅ OK' if sync_success else '❌ FAIL'} (Diff: {best_time_diff}ms)", 
                  "green" if sync_success else "red"))
    print(colored(f"🎯 API Tests: {api_success_count}/{len(api_tests)} successo", 
                  "green" if api_success_count == len(api_tests) else "yellow" if api_success_count > 0 else "red"))
    
    overall_success = sync_success and api_success_count >= len(api_tests) // 2
    
    if overall_success:
        print(colored("\n🎉 CONNESSIONE BYBIT: TUTTO OK!", "green", attrs=['bold']))
        print(colored("✅ Il bot dovrebbe funzionare correttamente", "green"))
    else:
        print(colored("\n⚠️ CONNESSIONE BYBIT: PROBLEMI RILEVATI", "yellow", attrs=['bold']))
        if not sync_success:
            print(colored("🔧 PRIORITÀ: Risolvi problemi timestamp", "red"))
        if api_success_count == 0:
            print(colored("🔧 PRIORITÀ: Verifica credenziali API", "red"))
    
    try:
        await async_exchange.close()
        print(colored("\n🔒 Connessione chiusa correttamente", "cyan"))
    except:
        pass
    
    return overall_success

# Funzione main per eseguire il test
async def main():
    print(colored("Bybit Connection Test v1.0", "white", attrs=['bold']))
    print(colored("Diagnostica timestamp fix e connettività", "white"))
    
    success = await test_bybit_connection()
    
    if success:
        print(colored("\n🚀 PRONTO PER IL TRADING BOT!", "green", attrs=['bold']))
        return 0
    else:
        print(colored("\n❌ RISOLVI I PROBLEMI PRIMA DI AVVIARE IL BOT", "red", attrs=['bold']))
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
