#!/usr/bin/env python3
"""
🧪 TEST DASHBOARD TKINTER

Script di test per verificare il funzionamento del nuovo dashboard tkinter
"""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional
import random

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Mock classes per testare il dashboard senza dipendenze reali
@dataclass
class MockTrailingData:
    enabled: bool = False
    activation_profit_pct: float = 0.0
    trailing_distance_pct: float = 0.0

@dataclass
class MockPosition:
    symbol: str
    side: str
    entry_price: float
    current_price: float
    stop_loss: float
    unrealized_pnl_pct: float
    unrealized_pnl_usd: float
    leverage: int
    max_favorable_pnl: float
    trailing_data: Optional[MockTrailingData] = None

@dataclass
class MockClosedTrade:
    symbol: str
    entry_price: float
    exit_price: float
    pnl_usd: float
    pnl_pct: float
    hold_time_minutes: int
    close_reason: str
    close_time: str

class MockPositionManager:
    """Mock Position Manager per testing"""
    
    def __init__(self):
        self.positions = []
        self.closed_trades = []
        
    def safe_get_position_count(self):
        return len(self.positions)
    
    def safe_get_all_active_positions(self):
        return self.positions
    
    def safe_get_session_summary(self):
        total_unrealized = sum(pos.unrealized_pnl_usd for pos in self.positions)
        used_margin = sum(pos.current_price * 0.1 for pos in self.positions)  # Mock
        
        return {
            'balance': 10000.0 + total_unrealized,
            'active_positions': len(self.positions),
            'used_margin': used_margin,
            'available_balance': 10000.0 - used_margin,
            'unrealized_pnl': total_unrealized
        }
    
    def add_mock_position(self, symbol: str, side: str, entry: float, 
                         current: float, sl: float, leverage: int = 10):
        """Aggiungi una posizione mock per testing"""
        pnl_pct = ((current - entry) / entry * 100) if side == 'long' else ((entry - current) / entry * 100)
        pnl_usd = pnl_pct * 10  # Mock
        
        trailing_data = MockTrailingData(enabled=random.choice([True, False]))
        
        pos = MockPosition(
            symbol=symbol,
            side=side,
            entry_price=entry,
            current_price=current,
            stop_loss=sl,
            unrealized_pnl_pct=pnl_pct,
            unrealized_pnl_usd=pnl_usd,
            leverage=leverage,
            max_favorable_pnl=abs(pnl_pct) * 1.2 if pnl_pct > 0 else 0,
            trailing_data=trailing_data
        )
        self.positions.append(pos)
        logging.info(f"✅ Added mock position: {symbol} {side.upper()} @ ${entry}")

class MockSessionStatistics:
    """Mock Session Statistics per testing"""
    
    def __init__(self):
        self.session_start_time = datetime.now() - timedelta(hours=2, minutes=30)
        self.session_start_balance = 10000.0
        self.trades_won = 15
        self.trades_lost = 5
        self.best_trade_pnl = 250.0
        self.worst_trade_pnl = -80.0
        self.closed_trades = []
        
    def get_session_duration(self):
        duration = datetime.now() - self.session_start_time
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}m"
    
    def get_total_trades(self):
        return self.trades_won + self.trades_lost
    
    def get_win_rate(self):
        total = self.get_total_trades()
        return (self.trades_won / total * 100) if total > 0 else 0
    
    def get_win_rate_emoji(self):
        win_rate = self.get_win_rate()
        if win_rate >= 70:
            return "🔥"
        elif win_rate >= 60:
            return "😊"
        elif win_rate >= 50:
            return "😐"
        else:
            return "😞"
    
    def get_pnl_vs_start(self):
        current_balance = 10450.0  # Mock balance with profit
        pnl_usd = current_balance - self.session_start_balance
        pnl_pct = (pnl_usd / self.session_start_balance) * 100
        return pnl_usd, pnl_pct
    
    def get_average_win_pct(self):
        return 2.5  # Mock
    
    def get_average_hold_time(self):
        return "1h 23m"  # Mock
    
    def get_last_n_trades(self, n: int):
        return self.closed_trades[-n:]
    
    def add_mock_closed_trade(self, symbol: str, entry: float, exit: float,
                             pnl_usd: float, pnl_pct: float, hold_min: int,
                             reason: str):
        """Aggiungi una trade chiusa mock"""
        trade = MockClosedTrade(
            symbol=symbol.replace('/USDT:USDT', ''),
            entry_price=entry,
            exit_price=exit,
            pnl_usd=pnl_usd,
            pnl_pct=pnl_pct,
            hold_time_minutes=hold_min,
            close_reason=reason,
            close_time=datetime.now().isoformat()
        )
        self.closed_trades.append(trade)
        logging.info(f"✅ Added mock closed trade: {symbol} PnL: ${pnl_usd:+.2f}")

def create_mock_data(position_manager, session_stats):
    """Crea dati mock per testing"""
    
    logging.info("📊 Creating mock data for dashboard testing...")
    
    # Aggiungi posizioni attive mock
    position_manager.add_mock_position("BTC/USDT:USDT", "long", 67500.0, 68200.0, 66800.0, 10)
    position_manager.add_mock_position("ETH/USDT:USDT", "long", 3800.0, 3850.0, 3750.0, 15)
    position_manager.add_mock_position("SOL/USDT:USDT", "short", 145.0, 143.5, 147.0, 20)
    position_manager.add_mock_position("BNB/USDT:USDT", "long", 580.0, 585.0, 575.0, 10)
    position_manager.add_mock_position("ADA/USDT:USDT", "long", 0.45, 0.46, 0.44, 25)
    
    # Aggiungi trade chiuse mock
    session_stats.add_mock_closed_trade("BTC/USDT:USDT", 67000.0, 67800.0, 120.0, 1.19, 45, "TRAILING_STOP_HIT")
    session_stats.add_mock_closed_trade("ETH/USDT:USDT", 3750.0, 3820.0, 93.33, 1.87, 92, "TRAILING_STOP_HIT")
    session_stats.add_mock_closed_trade("DOGE/USDT:USDT", 0.15, 0.149, -20.0, -0.67, 30, "STOP_LOSS_HIT")
    session_stats.add_mock_closed_trade("XRP/USDT:USDT", 0.62, 0.635, 48.39, 2.42, 180, "TAKE_PROFIT_HIT")
    session_stats.add_mock_closed_trade("LINK/USDT:USDT", 14.5, 14.8, 68.97, 2.07, 65, "TRAILING_STOP_HIT")
    
    logging.info("✅ Mock data created successfully!")

def main():
    """Main test function"""
    
    print("\n" + "="*60)
    print("🧪 TKINTER DASHBOARD TEST")
    print("="*60 + "\n")
    
    print("Questo script testa il nuovo dashboard tkinter con dati mock.")
    print("Il dashboard si aprirà in una finestra separata.\n")
    
    input("Premi INVIO per avviare il dashboard...")
    
    # Crea mock managers
    position_manager = MockPositionManager()
    session_stats = MockSessionStatistics()
    
    # Popola con dati mock
    create_mock_data(position_manager, session_stats)
    
    # Importa e avvia dashboard
    try:
        from core.trading_dashboard import TradingDashboard
        
        logging.info("📊 Starting dashboard...")
        dashboard = TradingDashboard(position_manager, session_stats)
        
        print("\n✅ Dashboard window opening...")
        print("📝 Features to test:")
        print("   - Header con session info")
        print("   - Statistics section (5 colonne)")
        print("   - Active positions table (5 posizioni)")
        print("   - Closed trades table (5 trades)")
        print("   - Footer con portfolio summary")
        print("   - Auto-refresh ogni 30 secondi")
        print("\n⚠️  Chiudi la finestra per terminare il test\n")
        
        # Avvia dashboard (bloccante per il test)
        dashboard.start()
        
        print("\n✅ Test completato!")
        
    except ImportError as e:
        logging.error(f"❌ Import error: {e}")
        print("\n❌ Errore: Impossibile importare TradingDashboard")
        print("   Assicurati che core/trading_dashboard.py sia presente")
    except Exception as e:
        logging.error(f"❌ Error during test: {e}")
        print(f"\n❌ Errore durante il test: {e}")

if __name__ == "__main__":
    main()
