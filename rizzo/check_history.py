from hyperliquid_trader import HyperLiquidTrader
import os
from dotenv import load_dotenv
import json

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")

bot = HyperLiquidTrader(secret_key=PRIVATE_KEY, account_address=WALLET_ADDRESS, testnet=True)

print("Fetching user fills...")
try:
    # user_fills returns a list of fills
    fills = bot.info.user_fills(WALLET_ADDRESS)
    print(f"Found {len(fills)} fills.")
    
    if fills:
        print("Example fill:")
        print(json.dumps(fills[0], indent=2))
        
        # Check if we can deduce PnL
        # Fills usually have: coin, px, sz, side, time
        # They might NOT have 'pnl'.
        
    # Try to fetch funding history or pnl history if available
    # Some SDKs expose user_funding_history
    
except Exception as e:
    print(f"Error fetching fills: {e}")
