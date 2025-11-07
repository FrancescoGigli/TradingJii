import logging
import sys
from pathlib import Path
from termcolor import colored


class CleanFormatter(logging.Formatter):
    """
    Enhanced formatter with emoji, colors, and clean output
    Adapts verbosity based on LOG_VERBOSITY setting
    """
    LEVEL_EMOJI = {
        "DEBUG": "🐛",
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨"
    }
    LEVEL_COLOR = {
        "DEBUG": "blue",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "magenta"
    }

    def format(self, record):
        emoji = self.LEVEL_EMOJI.get(record.levelname, "")
        color = self.LEVEL_COLOR.get(record.levelname, "white")
        
        # Clean message without timestamp in MINIMAL mode
        if hasattr(self, 'minimal') and self.minimal:
            record.msg = f"{colored(emoji, color)} {record.getMessage()}"
        else:
            record.msg = f"{colored(emoji, color)} {record.getMessage()}"
        
        record.args = ()
        return super().format(record)


class VerbosityFilter(logging.Filter):
    """
    Smart filter based on LOG_VERBOSITY level
    
    MINIMAL: Only critical events (trades, P&L, errors)
    NORMAL: Standard operations (signals, risk checks, trailing)
    DETAILED: Everything (debug info, API calls, calculations)
    """
    
    # Keywords for each verbosity level
    CRITICAL_EVENTS = [
        "TRADE #",
        "Position opened",
        "Position closed",
        "CYCLE COMPLETED",
        "EXECUTION SUMMARY",
        "P&L:",
        "Balance synced",
        "FINAL DECISION",
        "❌",  # Errors
        "🚨",  # Critical issues
    ]
    
    STANDARD_OPERATIONS = [
        "Consensus:",
        "ML Confidence:",
        "RL Filter:",
        "Risk Manager:",
        "TRAILING ACTIVATED",
        "Stop Loss",
        "Dynamic confidence",
        "Signals Ready:",
        "ADAPTIVE SIZING",
    ]
    
    VERBOSE_DEBUG = [
        "Pre-flight",
        "normalized:",
        "DEBUG",
        "Using PORTFOLIO",
        "CALCULATED LEVELS",
        "Distance from",
        "Thread-safe",
        "Cache",
        "API call",
        "Fetching",
        "Processing prediction",
    ]
    
    ALWAYS_BLOCK = [
        "Added to execution queue",
        "leverage not modified",
        "Decision logged:",
        "unrealizedPnl missing",
        "Calculated PnL",
        "Processing prediction results",
        "🔍 DEBUG PRE-SET",
        "🔍 DEBUG POST-SET",
        "🔍 DEBUG VERIFY",
        "🔧 AUTO-FIX: Corrected",
        "Checking stop losses for correctness",
    ]
    
    def __init__(self, verbosity_level="MINIMAL"):
        super().__init__()
        self.verbosity = verbosity_level.upper()
    
    def filter(self, record):
        msg = record.getMessage()
        
        # Always block these annoying logs
        for keyword in self.ALWAYS_BLOCK:
            if keyword in msg:
                return False
        
        # MINIMAL: Only critical events
        if self.verbosity == "MINIMAL":
            # Allow errors and warnings always
            if record.levelno >= logging.WARNING:
                return True
            
            # Allow critical trading events
            for keyword in self.CRITICAL_EVENTS:
                if keyword in msg:
                    return True
            
            # Block everything else
            return False
        
        # NORMAL: Standard + Critical
        elif self.verbosity == "NORMAL":
            # Block verbose debug
            for keyword in self.VERBOSE_DEBUG:
                if keyword in msg:
                    return False
            
            return True  # Allow everything except verbose debug
        
        # DETAILED: Everything
        else:
            return True


# ==============================
# HANDLER SETUP
# ==============================
import config

# Determine verbosity level
verbosity = config.LOG_VERBOSITY.upper() if hasattr(config, 'LOG_VERBOSITY') else "MINIMAL"

# Console handler with clean formatter
console_handler = logging.StreamHandler(sys.stdout)

if verbosity == "MINIMAL":
    # Minimal mode: no timestamp, just clean messages
    formatter = CleanFormatter("%(message)s")
    formatter.minimal = True
else:
    # Normal/Detailed: include timestamp
    formatter = CleanFormatter("%(asctime)s %(message)s", datefmt="%H:%M:%S")

console_handler.setFormatter(formatter)

# Apply verbosity filter
console_handler.addFilter(VerbosityFilter(verbosity))

# ==============================
# ROOT LOGGER
# ==============================
logging.basicConfig(
    level=logging.INFO,  # Base level INFO
    handlers=[console_handler],
    format="%(message)s"
)

# ==============================
# MODULE-SPECIFIC SETTINGS
# ==============================
# These modules are extra noisy, silence them in MINIMAL/NORMAL mode
noisy_modules = [
    "core.thread_safe_position_manager",
    "core.smart_api_manager",
    "core.order_manager",
    "trade_manager",
    "core.trade_decision_logger",
    "core.session_statistics",
    "core.trading_dashboard",
    "core.symbol_exclusion_manager",
    "trading.signal_processor",
    "core.risk_calculator",
    "core.integrated_trailing_monitor",
    "trading.market_analyzer",
    "core.realtime_display",
    "core.position_management.position_sync",
    "core.position_management.position_trailing",
    "core.position_management.position_safety",
]

# Set appropriate level based on verbosity
if verbosity == "MINIMAL":
    # In MINIMAL mode, these modules should only show warnings/errors
    for module in noisy_modules:
        logging.getLogger(module).setLevel(logging.WARNING)
elif verbosity == "NORMAL":
    # In NORMAL mode, allow INFO but not DEBUG
    for module in noisy_modules:
        logging.getLogger(module).setLevel(logging.INFO)
else:
    # DETAILED: Show everything
    for module in noisy_modules:
        logging.getLogger(module).setLevel(logging.DEBUG)

# ==============================
# STARTUP MESSAGE
# ==============================
if verbosity == "MINIMAL":
    logging.info(f"📊 Logging: MINIMAL mode (only trades & P&L)")
elif verbosity == "NORMAL":
    logging.info(f"📊 Logging: NORMAL mode (standard operations)")
else:
    logging.info(f"📊 Logging: DETAILED mode (full debug)")
