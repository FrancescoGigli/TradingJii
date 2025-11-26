from hyperliquid_trader import HyperLiquidTrader
import os
from dotenv import load_dotenv
import json

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")

if not PRIVATE_KEY or not WALLET_ADDRESS:
    print("Missing keys")
    exit()

bot = HyperLiquidTrader(secret_key=PRIVATE_KEY, account_address=WALLET_ADDRESS, testnet=True)

print("Fetching meta and asset contexts...")
# info.meta_and_asset_ctxs() is the standard way to get volume/stats in HL SDK
# But let's see what methods 'bot.info' has.
try:
    # Type hint might be missing, but usually it's meta_and_asset_ctxs
    meta_ctx = bot.info.meta_and_asset_ctxs()
    print("Successfully fetched meta_and_asset_ctxs")
    
    universe = meta_ctx[0]['universe']
    asset_ctxs = meta_ctx[1]
    
    # Create a list of (symbol, volume/notional)
    # AssetCtx usually contains 'dayNtlVlm' (day notional volume)
    
    stats = []
    for i, asset in enumerate(universe):
        symbol = asset['name']
        # asset_ctxs is usually a list matching universe index
        ctx = asset_ctxs[i]
        day_volume = float(ctx.get('dayNtlVlm', 0))
        stats.append((symbol, day_volume))
        
    # Sort by volume desc
    stats.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\nTop 20 Coins by Volume:")
    for sym, vol in stats[:20]:
        print(f"{sym}: ${vol:,.2f}")

except Exception as e:
    print(f"Error: {e}")
    # Fallback check attributes
    print(dir(bot.info))
