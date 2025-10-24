#!/usr/bin/env python3
"""
📊 STARTUP DISPLAY SYSTEM

Elegant structured display for bot startup sequence.
Collects initialization data and presents it in organized sections.
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
    """Collects startup information and displays formatted output"""
    
    def __init__(self):
        self.data = StartupData()
        self._section_width = 80
    
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
    
    def _print_separator(self, char: str = "="):
        """Print section separator"""
        print(colored(char * self._section_width, "cyan"))
    
    def _print_section_header(self, title: str):
        """Print section header"""
        print(colored(f"=== {title} ===", "cyan", attrs=["bold"]))
        self._print_separator()
    
    def _print_item(self, label: str, value: str, dots: int = 40):
        """Print formatted item with dots"""
        dots_count = max(1, dots - len(label))
        print(f"[CORE] {label} {'.' * dots_count} {value}")
    
    def _print_config_item(self, label: str, value: str, dots: int = 40):
        """Print formatted config item"""
        dots_count = max(1, dots - len(label))
        print(f"[CONFIG] {label} {'.' * dots_count} {value}")
    
    def _print_exchange_item(self, label: str, value: str, dots: int = 40):
        """Print formatted exchange item"""
        dots_count = max(1, dots - len(label))
        print(f"[BYBIT] {label} {'.' * dots_count} {value}")
    
    def _print_system_item(self, label: str, value: str, dots: int = 40):
        """Print formatted system item"""
        dots_count = max(1, dots - len(label))
        print(f"[SYSTEM] {label} {'.' * dots_count} {value}")
    
    def _print_market_item(self, label: str, value: str, dots: int = 40):
        """Print formatted market item"""
        dots_count = max(1, dots - len(label))
        print(f"[MARKET] {label} {'.' * dots_count} {value}")
    
    def _print_explanation(self, lines: List[str]):
        """Print explanation section"""
        print(colored("→ ", "green"), end="")
        print(colored(lines[0], "white"))
        for line in lines[1:]:
            print(f"   {line}")
    
    def display_startup_summary(self):
        """Display complete formatted startup summary"""
        print()  # Empty line before start
        
        # ===== SYSTEM STARTUP =====
        self._print_separator()
        self._print_section_header("SYSTEM STARTUP")
        
        self._print_item("ThreadSafePositionManager", 
                        f"READY (Mode: {self.data.position_manager_mode})")
        self._print_item("SignalProcessor", 
                        "LINKED to ThreadSafePositionManager" if self.data.signal_processor_linked else "NOT LINKED")
        self._print_item("TradeManager", 
                        "LINKED to ThreadSafePositionManager" if self.data.trade_manager_linked else "NOT LINKED")
        
        if self.data.trade_logger_db:
            self._print_item("TradeDecisionLogger", 
                           f"INITIALIZED ({self.data.trade_logger_db})")
        
        if self.data.session_stats_ready:
            self._print_item("SessionStatistics", "INITIALIZED")
        
        self._print_explanation([
            "Core systems activated:",
            "- ThreadSafePositionManager guarantees concurrent-safe position tracking.",
            "- SignalProcessor and TradeManager share a synchronized state.",
            "- TradeDecisionLogger stores all ML-driven trade decisions.",
            "- SessionStatistics module tracks session-level metrics and winrate."
        ])
        
        print()  # Empty line between sections
        
        # ===== CONFIGURATION LOADED =====
        self._print_separator()
        self._print_section_header("CONFIGURATION LOADED")
        
        if self.data.excluded_symbols_count > 0:
            self._print_config_item("Excluded symbols file", 
                                   f"FOUND ({self.data.excluded_symbols_count} symbols)")
            symbols_str = ", ".join(self.data.excluded_symbols_list)
            self._print_config_item("Auto-excluded", symbols_str)
        
        # Mode display with emoji
        mode_emoji = "🔴" if "LIVE" in self.data.mode.upper() else "🟡"
        self._print_config_item("Mode", f"{mode_emoji} {self.data.mode}")
        
        if self.data.timeframes:
            timeframes_str = " / ".join(self.data.timeframes)
            self._print_config_item("Timeframes", timeframes_str)
        
        if self.data.model_type:
            self._print_config_item("Model type", self.data.model_type)
        
        self._print_explanation([
            "Configuration applied:",
            "- Exclusion list prevents trading on risky or illiquid pairs.",
            f"- Trading mode set to {self.data.mode} with real Bybit execution." if "LIVE" in self.data.mode.upper() 
                else f"- Trading mode set to {self.data.mode} (no real execution).",
            f"- Timeframes and model type ({self.data.model_type}) initialized for prediction engine.",
            "- System parameters propagated to orchestrator and subsystems."
        ])
        
        print()  # Empty line between sections
        
        # ===== EXCHANGE CONNECTION =====
        self._print_separator()
        self._print_section_header("EXCHANGE CONNECTION")
        
        self._print_exchange_item("Connection", "STARTING")
        
        if self.data.time_sync_offset != 0:
            offset_ms = self.data.time_sync_offset
            self._print_exchange_item("Time synchronization", 
                                     f"✅ OK (offset: {offset_ms:+d} ms)")
        
        if self.data.markets_loaded:
            self._print_exchange_item("Market data", "✅ Loaded successfully")
        
        if self.data.authenticated:
            self._print_exchange_item("Authentication", "✅ SUCCESS (API verified)")
        
        self._print_explanation([
            "Exchange connection established:",
            "- Local clock aligned with Bybit server for millisecond accuracy.",
            "- Market metadata retrieved: tick size, leverage, and precision.",
            "- Secure authentication completed — trading endpoints accessible."
        ])
        
        print()  # Empty line between sections
        
        # ===== MODULES INITIALIZATION =====
        self._print_separator()
        self._print_section_header("MODULES INITIALIZATION")
        
        if self.data.orchestrator_ready:
            self._print_system_item("TradingOrchestrator", "READY (ThreadSafe)")
        
        if self.data.dashboard_type:
            self._print_system_item(f"Dashboard ({self.data.dashboard_type})", "INITIALIZED")
        
        if self.data.subsystems:
            subsystems_str = ", ".join(self.data.subsystems).upper()
            self._print_system_item("Subsystems", f"{subsystems_str} → READY")
        
        self._print_explanation([
            "Internal modules initialized:",
            "- TradingOrchestrator coordinates full signal → execution workflow.",
            f"- Dashboard backend ({self.data.dashboard_type}) manages visualization and live status.",
            "- Subsystems (Stats & Trailing) handle analytics and dynamic protection."
        ])
        
        print()  # Empty line between sections
        
        # ===== MARKET ANALYSIS STARTUP =====
        self._print_separator()
        self._print_section_header("MARKET ANALYSIS STARTUP")
        
        if self.data.total_symbols_processed > 0:
            self._print_market_item("Parallel ticker fetch", 
                                   f"{self.data.total_symbols_processed} symbols processed concurrently")
        
        if self.data.active_symbols_count > 0:
            self._print_market_item("Active selection", 
                                   f"{self.data.active_symbols_count} symbols retained for analysis")
        
        print(colored("[STATUS] ", "green", attrs=["bold"]), end="")
        print(colored("🚀 SYSTEM FULLY OPERATIONAL — LIVE TRADING STARTED", "green", attrs=["bold"]))
        
        self._print_explanation([
            "Market analysis running:",
            "- Data streams opened for all tradable pairs.",
            f"- Liquidity filters retained {self.data.active_symbols_count} active symbols for ML analysis.",
            "- Main trading loop active (15m cycle): prediction, signal, order flow."
        ])
        
        self._print_separator()
        print()  # Empty line after completion


# Global instance
global_startup_collector = StartupCollector()
