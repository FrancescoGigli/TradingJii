#!/usr/bin/env python3
"""
Quick config verification script
"""

def check_config():
    print("🔍 VERIFYING CONFIG VALUES")
    print("=" * 50)
    
    # Check config.py directly
    try:
        from config import exchange_config
        recv_window = exchange_config['options']['recvWindow']
        adjust_time = exchange_config['options']['adjustForTimeDifference']
        
        print(f"✅ recv_window: {recv_window}ms")
        print(f"✅ adjustForTimeDifference: {adjust_time}")
        
        if recv_window == 120000:
            print("🎉 CONFIG FIX APPLIED SUCCESSFULLY!")
        else:
            print("❌ Config fix NOT applied - still showing old value")
            
    except Exception as e:
        print(f"❌ Error reading config: {e}")
    
    # Check API keys (safely)
    try:
        import os
        api_key = os.getenv("BYBIT_API_KEY", "")
        api_secret = os.getenv("BYBIT_API_SECRET", "")
        
        if api_key and api_secret:
            print(f"✅ API Key: {api_key[:8]}... (length: {len(api_key)})")
            print(f"✅ API Secret: {api_secret[:8]}... (length: {len(api_secret)})")
        else:
            print("❌ API keys not found in environment")
            
    except Exception as e:
        print(f"❌ Error checking API keys: {e}")

if __name__ == "__main__":
    check_config()
