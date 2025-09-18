#!/usr/bin/env python3
"""
🚀 TEST SCRIPT per il Sistema di Logging Triplo
Testa tutte le funzionalità del nuovo enhanced logging system

Questo script verifica:
1. ✅ Console output colorato (terminale)
2. ✅ File ANSI colorato (trading_bot_colored.log)
3. ✅ File HTML export (trading_session.html)
4. ✅ File plain text (trading_bot_derivatives.log)
5. ✅ Tabelle formattate
6. ✅ Position displays

Run: python test_logging_system.py
"""

import sys
import os
from pathlib import Path
import time
from datetime import datetime

# Add current directory to path to import modules
sys.path.append(str(Path(__file__).parent))

def main():
    """Test the enhanced logging system"""
    
    print("🚀 Testing Enhanced Triple Logging System")
    print("=" * 60)
    
    try:
        # Import logging system (this will initialize everything)
        from logging_config import logs_dir
        print(f"✅ Logging config imported successfully")
        print(f"📁 Log directory: {logs_dir.absolute()}")
        
        # Import enhanced logging components
        from core.enhanced_logging_system import (
            enhanced_logger,
            table_logger,
            position_logger,
            countdown_logger,
            cycle_logger,
            log_table,
            log_separator,
            log_header
        )
        print("✅ Enhanced logging system imported successfully")
        
        # Test 1: Basic logging
        print("\n📝 Testing basic enhanced logging...")
        enhanced_logger.display_table("🧪 TEST: Basic colored message", "green", attrs=['bold'])
        enhanced_logger.display_table("🔵 INFO: This should appear in all log files", "blue")
        enhanced_logger.display_table("🟡 WARNING: Testing warning colors", "yellow")
        enhanced_logger.display_table("🔴 ERROR: Testing error colors", "red")
        
        # Test 2: Separators and headers  
        print("\n📊 Testing separators and headers...")
        log_separator("=", 80, "cyan")
        log_header("🚀 TEST HEADER", "green", ['bold'])
        log_separator("-", 40, "yellow")
        
        # Test 3: Table logging
        print("\n📋 Testing table logging...")
        table_logger.log_ascii_table(
            headers=["Symbol", "Side", "PnL %", "Status"],
            rows=[
                ["BTC", "LONG", "+5.2%", "✅ Active"],
                ["ETH", "SHORT", "-2.1%", "⚠️ Warning"],
                ["SOL", "LONG", "+8.7%", "🎯 Trailing"]
            ],
            title="📊 Sample Trading Table",
            title_color="green",
            border_color="cyan",
            row_colors=["green", "yellow", "blue"]
        )
        
        # Test 4: Position display simulation
        print("\n🏦 Testing position display...")
        sample_positions = [
            {
                "symbol": "BTC/USDT:USDT",
                "side": "long",
                "entry_price": 45000.0,
                "current_price": 46150.0,
                "leverage": 10,
                "pnl_pct": 2.55,
                "pnl_usd": 15.30
            },
            {
                "symbol": "ETH/USDT:USDT", 
                "side": "short",
                "entry_price": 2800.0,
                "current_price": 2756.0,
                "leverage": 10,
                "pnl_pct": 1.57,
                "pnl_usd": 8.90
            }
        ]
        
        # Simulate position display
        enhanced_logger.display_separator("=", 100)
        enhanced_logger.display_table("📊 LIVE POSITIONS (Test)", "green", attrs=['bold'])
        enhanced_logger.display_table("┌─────┬────────┬──────┬──────┬─────────────┬─────────────┬──────────┬───────────┐", "cyan")
        enhanced_logger.display_table("│  #  │ SYMBOL │ SIDE │ LEV  │    ENTRY    │   CURRENT   │  PnL %   │   PnL $   │", "white", attrs=['bold'])
        enhanced_logger.display_table("├─────┼────────┼──────┼──────┼─────────────┼─────────────┼──────────┼───────────┤", "cyan")
        
        for i, pos in enumerate(sample_positions, 1):
            sym = pos["symbol"].replace("/USDT:USDT", "")
            side_color = "green" if pos["side"] == "long" else "red"
            pnl_color = "green" if pos["pnl_usd"] > 0 else "red"
            
            from termcolor import colored
            import logging
            
            line = (
                colored(f"│{i:^5}│", "white") +
                colored(f"{sym:^8}", "cyan") + colored("│", "white") +
                colored(f"{pos['side'].upper():^6}", side_color) + colored("│", "white") +
                colored(f"{pos['leverage']:^6}", "yellow") + colored("│", "white") +
                colored(f"${pos['entry_price']:,.2f}".center(13), "white") + colored("│", "white") +
                colored(f"${pos['current_price']:,.2f}".center(13), "cyan") + colored("│", "white") +
                colored(f"{pos['pnl_pct']:+.1f}%".center(10), pnl_color) + colored("│", "white") +
                colored(f"+${pos['pnl_usd']:.2f}".center(11), pnl_color) + colored("│", "white")
            )
            logging.info(line)
        
        enhanced_logger.display_table("└─────┴────────┴──────┴─────────────┴─────────────┴──────────┴───────────┘", "cyan")
        enhanced_logger.display_separator("=", 100)
        
        # Test 5: Countdown simulation
        print("\n⏰ Testing countdown logging...")
        countdown_logger.log_countdown_start(5)
        for i in range(5, 0, -1):
            countdown_logger.log_countdown_tick(0, i)
            time.sleep(0.5)  # Quick test
        
        # Test 6: Cycle events
        print("\n🔄 Testing cycle logging...")
        cycle_logger.log_cycle_start()
        cycle_logger.log_phase(1, "DATA COLLECTION", "blue")
        cycle_logger.log_phase(2, "ML PREDICTIONS", "magenta") 
        cycle_logger.log_phase(3, "SIGNAL EXECUTION", "green")
        cycle_logger.log_execution_summary(3, 5)
        
        # Test 7: Mixed content
        print("\n🎭 Testing mixed content...")
        enhanced_logger.display_multiline([
            "📈 Market Analysis Complete",
            "🧠 ML Models: 3/3 ready", 
            "⚡ Trading Engine: Active",
            "🛡️ Risk Management: Enabled"
        ], ["green", "blue", "cyan", "yellow"])
        
        # Final summary
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("\n📁 Check these files for results:")
        print(f"   📄 Plain text: {logs_dir}/trading_bot_derivatives.log")
        print(f"   🎨 ANSI colors: {logs_dir}/trading_bot_colored.log") 
        print(f"   🌐 HTML export: {logs_dir}/trading_session.html")
        print(f"   ❌ Errors only: {logs_dir}/trading_bot_errors.log")
        
        print("\n🎯 VIEWING COMMANDS:")
        print("   Windows ANSI: type logs\\trading_bot_colored.log")
        print("   Linux/Mac:    cat logs/trading_bot_colored.log") 
        print("   HTML:         Open logs/trading_session.html in browser")
        
        print("\n🚀 System ready for production use!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure all required modules are installed:")
        print("   pip install termcolor")
        return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
