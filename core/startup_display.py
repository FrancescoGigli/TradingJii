#!/usr/bin/env python3
"""
📊 STARTUP DISPLAY SYSTEM - Minimal Version
Clean, essential startup display
"""

import logging
from termcolor import colored
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class StartupData:
    """Container for all startup information"""
    # Core systems
    position_manager_mode: str = ""
    signal_processor_linked: bool = False
    trade_manager_linked: bool = False
    trade_logger_db: str = ""
    session_stats_ready: bool = False
    
    # Configuration
    excluded_symbols_count: int = 0
    excluded_symbols_list: List[str] = field(default_factory=list)
    mode: str = ""
    timeframes: List[str] = field(default_factory=list)
    model_type: str = ""
    
    # Exchange connection
    exchange_name: str = "Bybit"
    time_sync_offset: int = 0
    markets_loaded: bool = False
    authenticated: bool = False
    
    # Modules
    orchestrator_ready: bool = False
    dashboard_type: str = ""
    subsystems: List[str] = field(default_factory=list)
    
    # Market analysis
    total_symbols_processed: int = 0
    active_symbols_count: int = 0


class StartupCollector:
    """Collects startup information and displays minimal formatted output"""
    
    def __init__(self):
        self.data = StartupData()
    
    def set_core_system(self, component: str, status: str):
        """Register core system initialization"""
        if component == "position_manager":
            self.data.position_manager_mode = status
        elif component == "signal_processor":
            self.data.signal_processor_linked = True
        elif component == "trade_manager":
            self.data.trade_manager_linked = True
        elif component == "trade_logger":
            self.data.trade_logger_db = status
        elif component == "session_stats":
            self.data.session_stats_ready = True
    
    def set_configuration(self, excluded_count: int, excluded_list: List[str], 
                         mode: str, timeframes: List[str], model_type: str):
        """Register configuration data"""
        self.data.excluded_symbols_count = excluded_count
        self.data.excluded_symbols_list = excluded_list
        self.data.mode = mode
        self.data.timeframes = timeframes
        self.data.model_type = model_type
    
    def set_exchange_connection(self, time_offset: int, markets: bool, auth: bool):
        """Register exchange connection status"""
        self.data.time_sync_offset = time_offset
        self.data.markets_loaded = markets
        self.data.authenticated = auth
    
    def set_modules(self, orchestrator: bool, dashboard: str, subsystems: List[str]):
        """Register modules initialization"""
        self.data.orchestrator_ready = orchestrator
        self.data.dashboard_type = dashboard
        self.data.subsystems = subsystems
    
    def set_market_analysis(self, total_symbols: int, active_symbols: int):
        """Register market analysis data"""
        self.data.total_symbols_processed = total_symbols
        self.data.active_symbols_count = active_symbols
    
    def display_startup_summary(self):
        """Display minimal startup summary - only essentials"""
        print()
        print(colored("=" * 80, "cyan"))
        print(colored("🚀 SYSTEM STARTUP", "cyan", attrs=["bold"]))
        print(colored("=" * 80, "cyan"))
        
        # Mode indicator
        mode_emoji = "🔴" if "LIVE" in self.data.mode.upper() else "🟡"
        mode_text = colored(f"{mode_emoji} {self.data.mode}", "green" if "LIVE" in self.data.mode.upper() else "yellow", attrs=["bold"])
        
        # Single line summary
        timeframes_str = "/".join(self.data.timeframes) if self.data.timeframes else "N/A"
        
        print(f"Mode: {mode_text} | Model: {self.data.model_type} | Timeframes: {timeframes_str}")
        
        # Exchange status
        auth_status = colored("✅ Connected", "green") if self.data.authenticated else colored("❌ Failed", "red")
        print(f"Bybit: {auth_status} | Sync: {self.data.time_sync_offset:+d}ms | Symbols: {self.data.active_symbols_count}")
        
        # Final status
        print()
        print(colored("✅ READY - Trading loop active", "green", attrs=["bold"]))
        print(colored("=" * 80, "cyan"))
        print()


# Global instance
global_startup_collector = StartupCollector()
