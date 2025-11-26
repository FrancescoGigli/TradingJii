from indicators import analyze_multiple_tickers
from news_feed import fetch_latest_news
from trading_agent import previsione_trading_agent
from whalealert import format_whale_alerts_to_string
from sentiment import get_sentiment
from forecaster import get_crypto_forecasts
from hyperliquid_trader import HyperLiquidTrader
from stop_loss_manager import StopLossManager
import os
import json
import time
import logging
import db_utils
from dotenv import load_dotenv

# Silencing cmdstanpy (Prophet) logs
logging.getLogger("cmdstanpy").disabled = True

load_dotenv()

# Collegamento ad Hyperliquid
TESTNET = True   # True = testnet, False = mainnet (occhio!)
VERBOSE = True    # stampa informazioni extra
LOOP_INTERVAL = 3600 # 1 ora in secondi
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")

if not PRIVATE_KEY or not WALLET_ADDRESS:
    raise RuntimeError("PRIVATE_KEY o WALLET_ADDRESS mancanti nel .env")

# Initializing variables to avoid NameError in except block
system_prompt = "N/A"
indicators_json = {}
news_txt = "N/A"
sentiment_json = {}
forecasts_json = {}
account_status = {}
# Session trades history (in-memory)
session_trades = []

def run_bot_cycle():
    global system_prompt, indicators_json, news_txt, sentiment_json, forecasts_json, account_status, session_trades
    
    print(f"\n{'='*50}")
    print(f"🔄 Inizio ciclo di trading: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    try:
        bot = HyperLiquidTrader(
            secret_key=PRIVATE_KEY,
            account_address=WALLET_ADDRESS,
            testnet=TESTNET
        )

        # STOP LOSS MANAGER: Controlla posizioni esistenti
        print("🛡️ Inizializzazione Stop Loss Manager...")
        sl_manager = StopLossManager(bot, db_utils)
        
        # Controlla e esegui stop loss per posizioni aperte
        closed_by_stop = sl_manager.check_and_execute_stops()
        
        # Logga le chiusure per stop loss
        if closed_by_stop:
            db_utils.log_stop_loss_closures(closed_by_stop)
            print(f"✅ Loggate {len(closed_by_stop)} chiusure per stop loss")
            
            # Aggiungi alle operazioni della sessione
            for closure in closed_by_stop:
                trade_info = {
                    "time": time.strftime('%H:%M:%S'),
                    "symbol": closure['symbol'],
                    "op": "STOP_CLOSE",
                    "dir": closure['side'].upper(),
                    "pnl_pct": f"{closure['profit_pct']:.2f}%"
                }
                session_trades.append(trade_info)

        # 1. Fetch TOP 50 coins by liquidity
        print("📊 Fetching top 50 coins per liquidità...")
        tickers = bot.get_top_liquid_coins(limit=50)
        # Coin list is already printed by get_top_liquid_coins

        # 2. Calcolo indicatori per TUTTE le coin
        print("📈 Analisi indicatori tecnici...")
        indicators_txt, indicators_json  = analyze_multiple_tickers(tickers)
        
        # 3. News (General/Major coins)
        print("📰 Scaricando news...")
        news_txt = fetch_latest_news()

        # 4. Whale Alerts
        print("🐋 Scaricando Whale Alerts...")
        whale_alerts_txt = format_whale_alerts_to_string()
        
        # 5. Sentiment (Global)
        print("😨 Analisi sentiment...")
        sentiment_txt, sentiment_json  = get_sentiment()
        
        # 6. Forecast (Solo per major coins per risparmiare tempo/risorse, o top 3 della lista)
        print("🔮 Generando previsioni AI...")
        forecasts_txt, forecasts_json = get_crypto_forecasts()

        # 7. Performance History
        print("📜 Scaricando storico performance...")
        # Sleep before heavy history fetch to avoid 429
        time.sleep(2)
        performance_txt = bot.get_recent_performance()

        # Sleep to ensure rate limits are reset before fetching account status
        # Increased to 10s to be safe after heavy load
        print("⏳ Cooldown prima di scaricare stato account...")
        time.sleep(10)

        msg_info=f"""<indicatori>\n{indicators_txt}\n</indicatori>\n\n
        <news>\n{news_txt}</news>\n\n
        <whale_alerts>\n{whale_alerts_txt}</whale_alerts>\n\n
        <sentiment>\n{sentiment_txt}\n</sentiment>\n\n
        <forecast>\n{forecasts_txt}\n</forecast>\n\n
        <performance_history>\n{performance_txt}\n</performance_history>\n\n"""

        # Retry logic for account status (critical op)
        account_status = {}
        for attempt in range(3):
            try:
                account_status = bot.get_account_status()
                break
            except Exception as acc_err:
                print(f"⚠️ Errore recupero account (tentativo {attempt+1}/3): {acc_err}")
                time.sleep(5)
        
        if not account_status:
             raise RuntimeError("Impossibile recuperare stato account dopo 3 tentativi")

        portfolio_data = f"{json.dumps(account_status)}"

        # Print Balance Summary
        balance = account_status.get('balance_usd', 0)
        positions = account_status.get('open_positions', [])
        total_pnl = sum(p.get('pnl_usd', 0) for p in positions)
        equity = balance + total_pnl
        print(f"\n💰 WALLET (PRE-TRADE): ${balance:,.2f} | Equity: ${equity:,.2f} | PnL Open: ${total_pnl:+,.2f}")
        print(f"📊 Posizioni Aperte: {len(positions)}")
        for p in positions:
            print(f"   - {p['symbol']} ({p['side'].upper()}): Size {p['size']} | PnL: ${p['pnl_usd']:+.2f}")
        
        # Log account status
        snapshot_id = db_utils.log_account_status(account_status)
        print(f"[db_utils] Snapshot account salvato id={snapshot_id}")

        # Creating System prompt
        with open('system_prompt.txt', 'r') as f:
            system_prompt_template = f.read()
        
        system_prompt = system_prompt_template.format(portfolio_data, msg_info)
            
        print("🤖 L'agente sta analizzando i dati per prendere decisioni...")
        decisions, usage_stats = previsione_trading_agent(system_prompt)
        
        print(f"💰 AI Usage Cost: ${usage_stats.get('cost_usd', 0):.4f} (Tokens: {usage_stats.get('total_tokens', 0)})")
        if 'raw_response_excerpt' in usage_stats:
             print(f"🤖 AI Response (excerpt): {usage_stats['raw_response_excerpt'][:100]}...")

        print(f"💡 L'AI ha generato {len(decisions)} decisioni.")
        
        for decision in decisions:
            symbol = decision.get('symbol')
            operation = decision.get('operation')
            reason = decision.get('reason', 'N/A')
            print(f"👉 [{symbol}] {operation.upper()} | Reason: {reason}")
            
            # Retry logic for trade execution
            max_retries = 3
            for i in range(max_retries):
                try:
                    # execute_signal returns parsed result from exchange
                    res = bot.execute_signal(decision)
                    
                    # Track in session history if it's a trade
                    if operation in ['open', 'close']:
                        trade_info = {
                            "time": time.strftime('%H:%M:%S'),
                            "symbol": symbol,
                            "op": operation.upper(),
                            "dir": decision.get('direction', '').upper(),
                            # Try to get filled price/size from result if possible, 
                            # but Hyperliquid market open result structure varies.
                            # We'll keep it simple.
                        }
                        session_trades.append(trade_info)
                    
                    break # Success
                except Exception as exec_err:
                    if i == max_retries - 1:
                        print(f"❌ Errore definitivo eseguendo ordine per {symbol}: {exec_err}")
                    else:
                        print(f"⚠️ Errore temporaneo ordine {symbol} ({i+1}/{max_retries}): {exec_err} - Riprovo...")
                        time.sleep(2)

        # Log operation (summary)
        op_id = db_utils.log_bot_operation(
            {"decisions": decisions}, # Wrap list in dict for JSON logging
            system_prompt=system_prompt, 
            indicators=indicators_json, 
            news_text=news_txt, 
            sentiment=sentiment_json, 
            forecasts=forecasts_json
        )
        print(f"[db_utils] Operazione salvata con id={op_id}")

        # Post-trade status update
        print("\n🔄 Aggiornamento stato post-trade...")
        time.sleep(5) # Wait for execution to settle
        try:
            new_status = bot.get_account_status()
            new_bal = new_status.get('balance_usd', 0)
            new_pos = new_status.get('open_positions', [])
            new_pnl = sum(p.get('pnl_usd', 0) for p in new_pos)
            new_equity = new_bal + new_pnl
            print(f"💰 WALLET (POST-TRADE): ${new_bal:,.2f} | Equity: ${new_equity:,.2f} | PnL Open: ${new_pnl:+,.2f}")
            print(f"📊 Posizioni Aperte: {len(new_pos)}")
        except Exception as e:
            print("⚠️ Impossibile recuperare stato post-trade.")

        # Print Session Summary
        if session_trades:
            print(f"\n📝 RIEPILOGO OPERAZIONI SESSIONE ({len(session_trades)}):")
            for t in session_trades:
                if 'pnl_pct' in t:
                    print(f"   [{t['time']}] {t['symbol']} {t['op']} {t['dir']} - PnL: {t['pnl_pct']}")
                else:
                    print(f"   [{t['time']}] {t['symbol']} {t['op']} {t['dir']}")
        else:
            print("\n📝 Nessuna operazione eseguita in questa sessione.")

    except Exception as e:
        db_utils.log_error(e, context={
            "tickers": tickers if 'tickers' in locals() else "N/A",
            "balance": account_status
        }, source="trading_agent_loop")
        print(f"❌ An error occurred in cycle: {e}")

if __name__ == "__main__":
    print(f"🚀 Bot avviato. Esecuzione continua ogni {LOOP_INTERVAL} secondi.")
    while True:
        run_bot_cycle()
        print(f"\n💤 Dormo per {LOOP_INTERVAL} secondi...")
        time.sleep(LOOP_INTERVAL)
