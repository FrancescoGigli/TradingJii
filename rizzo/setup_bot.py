#!/usr/bin/env python3
"""
Script di Setup Rapido per Trading Bot
Verifica prerequisiti e guida l'utente nella configurazione
"""

import os
import sys
from dotenv import load_dotenv

def print_header(text):
    """Stampa un header formattato"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")

def check_env_file():
    """Verifica esistenza file .env"""
    print_header("1. Verifica File .env")
    
    if not os.path.exists('.env'):
        print("❌ File .env NON TROVATO!")
        print("\n💡 Soluzione:")
        print("   1. Copia .env.example in .env")
        print("   2. Compila con le tue chiavi")
        print("\nComando: copy .env.example .env  (Windows)")
        print("         cp .env.example .env     (Linux/Mac)")
        return False
    
    print("✅ File .env trovato!")
    return True

def check_env_variables():
    """Verifica variabili d'ambiente"""
    print_header("2. Verifica Chiavi API")
    
    load_dotenv()
    
    checks = {
        'PRIVATE_KEY': os.getenv('PRIVATE_KEY'),
        'WALLET_ADDRESS': os.getenv('WALLET_ADDRESS'),
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'CMC_PRO_API_KEY': os.getenv('CMC_PRO_API_KEY'),
        'DATABASE_URL': os.getenv('DATABASE_URL')
    }
    
    all_ok = True
    for key, value in checks.items():
        if not value or value == "":
            print(f"❌ {key}: MANCANTE")
            all_ok = False
        else:
            # Mostra solo i primi e ultimi caratteri per sicurezza
            if len(value) > 20:
                masked = value[:8] + "..." + value[-4:]
            else:
                masked = value[:4] + "..." if len(value) > 4 else "****"
            print(f"✅ {key}: {masked}")
    
    if not all_ok:
        print("\n💡 Compila il file .env con le chiavi mancanti!")
        print("   Vedi .env.example per riferimento")
    
    return all_ok

def check_dependencies():
    """Verifica dipendenze Python"""
    print_header("3. Verifica Dipendenze Python")
    
    required = [
        'hyperliquid',
        'openai',
        'pandas',
        'psycopg2',
        'ta',
        'prophet',
        'dotenv'
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing.append(package)
    
    if missing:
        print(f"\n💡 Installa dipendenze mancanti:")
        print("   pip install -r requirements.txt")
        return False
    
    return True

def check_database():
    """Verifica connessione database"""
    print_header("4. Verifica Database")
    
    try:
        import db_utils
        
        # Tenta connessione
        db_utils.get_db_config()
        print("✅ DATABASE_URL configurata")
        
        # Verifica se tabelle esistono
        try:
            with db_utils.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM account_snapshots")
                    print("✅ Tabelle database esistono")
                    return True
        except Exception as e:
            print("⚠️  Database connesso ma tabelle non inizializzate")
            print("\n💡 Inizializza database:")
            print('   python -c "import db_utils; db_utils.init_db()"')
            return False
            
    except Exception as e:
        print(f"❌ Errore database: {str(e)[:100]}")
        print("\n💡 Verifica DATABASE_URL nel .env")
        print("   Suggerimento: Usa Supabase (https://supabase.com/)")
        return False

def test_hyperliquid():
    """Testa connessione Hyperliquid"""
    print_header("5. Test Hyperliquid")
    
    try:
        from hyperliquid_trader import HyperLiquidTrader
        load_dotenv()
        
        private_key = os.getenv('PRIVATE_KEY')
        wallet_address = os.getenv('WALLET_ADDRESS')
        
        if not private_key or not wallet_address:
            print("❌ PRIVATE_KEY o WALLET_ADDRESS mancanti")
            return False
        
        bot = HyperLiquidTrader(
            secret_key=private_key,
            account_address=wallet_address,
            testnet=True
        )
        
        status = bot.get_account_status()
        balance = status.get('balance_usd', 0)
        
        print(f"✅ Connesso a Hyperliquid testnet!")
        print(f"   Balance: ${balance:.2f}")
        print(f"   Posizioni aperte: {len(status.get('open_positions', []))}")
        
        if balance == 0:
            print("\n⚠️  Balance = $0!")
            print("💡 Richiedi fondi testnet:")
            print("   - Discord: https://discord.gg/hyperliquid")
            print("   - Canale: #testnet-faucet")
            print("   - Comando: /faucet <your_address>")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore Hyperliquid: {str(e)[:200]}")
        return False

def main():
    """Main setup check"""
    print("\n" + "🤖 TRADING BOT - SETUP CHECKER".center(60))
    print("Verifica che tutto sia configurato correttamente\n")
    
    checks = [
        ("File .env", check_env_file),
        ("Chiavi API", check_env_variables),
        ("Dipendenze", check_dependencies),
        ("Database", check_database),
        ("Hyperliquid", test_hyperliquid)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Errore durante verifica {name}: {e}")
            results.append((name, False))
    
    # Riepilogo finale
    print_header("RIEPILOGO SETUP")
    
    all_passed = True
    for name, passed in results:
        status = "✅ OK" if passed else "❌ ERRORE"
        print(f"{status:12} {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    
    if all_passed:
        print("\n🎉 TUTTO OK! Sei pronto per lanciare il bot!")
        print("\n📝 Prossimi comandi:")
        print("   python test_trading.py  # Test rapido")
        print("   python main.py          # Avvia bot")
    else:
        print("\n⚠️  Ci sono ancora problemi da risolvere.")
        print("   Segui le istruzioni sopra per fixare gli errori.")
    
    print("\n📖 Per aiuto dettagliato:")
    print("   - Leggi SETUP_GUIDE.md")
    print("   - Leggi TECHNICAL_OVERVIEW.md\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✋ Setup interrotto dall'utente")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Errore inaspettato: {e}")
        sys.exit(1)
