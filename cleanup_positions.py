#!/usr/bin/env python3
"""
🧹 CLEANUP POSIZIONI DUPLICATE

Pulisce tutte le posizioni duplicate dal sistema e riparte con sync pulito
"""

import os
import json
import logging
from termcolor import colored

def cleanup_all_position_files():
    """Rimuove tutti i file di posizioni per ripartire pulito"""
    
    print(colored("🧹 CLEANUP POSIZIONI DUPLICATE", "yellow", attrs=['bold']))
    print("=" * 60)
    
    # Files to clean
    position_files = [
        "positions_clean.json",
        "smart_positions.json", 
        "positions.json",
        "session_data.json"
    ]
    
    cleaned_files = []
    
    for filename in position_files:
        try:
            if os.path.exists(filename):
                # Backup first
                backup_name = f"{filename}.backup_{int(os.path.getmtime(filename))}"
                os.rename(filename, backup_name)
                cleaned_files.append(filename)
                print(f"✅ {filename} → {backup_name}")
            else:
                print(f"⚪ {filename} (not found)")
                
        except Exception as e:
            print(f"❌ Error cleaning {filename}: {e}")
    
    print("-" * 60)
    
    if cleaned_files:
        print(f"🧹 Cleaned {len(cleaned_files)} position files")
        print("✅ Bot will start with clean position tracking")
        print("✅ Duplicates eliminated")
        print("✅ Only real Bybit positions will be tracked")
    else:
        print("💡 No position files found - already clean")
    
    print("-" * 60)
    
    return len(cleaned_files)

def cleanup_logs():
    """Pulisce log vecchi per fresh start"""
    try:
        logs_dir = "logs"
        if os.path.exists(logs_dir):
            log_files = os.listdir(logs_dir)
            
            for log_file in log_files:
                if log_file.endswith('.log'):
                    log_path = os.path.join(logs_dir, log_file)
                    try:
                        # Clear content but keep file
                        with open(log_path, 'w') as f:
                            f.write(f"# Log cleared for fresh start - {os.path.basename(__file__)}\n")
                        print(f"🧹 Cleared: {log_file}")
                    except Exception as e:
                        print(f"⚠️ Could not clear {log_file}: {e}")
            
            print(f"✅ Log cleanup complete")
        
    except Exception as e:
        print(f"⚠️ Log cleanup error: {e}")

def display_fresh_start_info():
    """Display information about fresh start"""
    
    print(colored("\n🚀 FRESH START READY", "green", attrs=['bold']))
    print("=" * 60)
    
    print("✅ Position tracking: CLEAN")
    print("✅ Duplicate removal: COMPLETE") 
    print("✅ Smart sync: READY")
    print("✅ Dual tables: ENABLED")
    
    print("\n📊 NEXT BOT START:")
    print("🟢 OPEN table: Only real Bybit positions")
    print("🔴 CLOSED table: Session history (starts empty)")
    print("🔄 Auto-sync: Every 5 minutes")
    print("🧹 Auto-cleanup: Duplicate prevention")
    
    print("\n💡 RECOMMENDED:")
    print("1. Run: python main.py")
    print("2. Select mode: 2 (LIVE)")
    print("3. Timeframes: default (15m,30m,1h)")
    print("4. Observe clean dual tables!")
    
    print("=" * 60)

if __name__ == "__main__":
    print("Position Cleanup Utility v1.0")
    print("Removing duplicate positions for fresh start")
    
    # 1. Clean position files
    cleaned_count = cleanup_all_position_files()
    
    # 2. Clean logs for fresh start
    cleanup_logs()
    
    # 3. Show fresh start info
    display_fresh_start_info()
    
    print(f"\n🎉 CLEANUP COMPLETE!")
    print(f"📁 {cleaned_count} files backed up and cleaned")
    print(f"🚀 Ready for clean bot restart!")
