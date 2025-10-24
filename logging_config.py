import logging
import sys
from pathlib import Path
from termcolor import colored


class EmojiFormatter(logging.Formatter):
    """
    Formatter console con emoji + colori
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
        record.msg = f"{colored(emoji, color)} {record.getMessage()}"
        record.args = ()
        return super().format(record)




# ==============================
# HANDLER
# ==============================
# Console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(EmojiFormatter("%(asctime)s %(levelname)s %(message)s"))





# ==============================
# ROOT LOGGER
# ==============================
logging.basicConfig(
    level=logging.INFO,  # base rimane INFO
    handlers=[console_handler],
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

# ==============================
# QUIET MODE FILTER
# ==============================
import config

class QuietModeFilter(logging.Filter):
    """Filter che blocca log dettagliati in QUIET_MODE"""
    
    # Parole chiave da bloccare in QUIET_MODE
    BLOCK_KEYWORDS = [
        "Added to execution queue",
        "Using PORTFOLIO SIZING",
        "CALCULATED LEVELS",
        "Position size normalized",
        "PLACING MARKET",
        "normalized:",
        "leverage/margin setup failed",
        "leverage not modified",
        "Distance from current",
        "Profit protected from entry",
        "Thread-safe position created",
        "Decision logged:",
        "Trailing updated:",
        "[Trailing]",
        "Sync: NEW position",
        "Sync: CLOSED position",
        "unrealizedPnl missing",
        "Calculated PnL",
        "Processing prediction results"
    ]
    
    def filter(self, record):
        if not config.QUIET_MODE:
            return True  # Passa tutti i log se non in quiet mode
        
        # Blocca log dettagliati
        for keyword in self.BLOCK_KEYWORDS:
            if keyword.lower() in record.getMessage().lower():
                return False
        
        return True  # Passa i log importanti

# Applica filtro a console handler
if config.QUIET_MODE:
    console_handler.addFilter(QuietModeFilter())


# ==============================
# RIDUZIONE VERBOSITÀ SOLO MODULI "CHIACCHIERONI"
# ==============================
noisy_modules = [
    # Core systems (only show warnings/errors)
    "core.thread_safe_position_manager",
    "core.smart_api_manager",
    "core.order_manager",
    "trade_manager",
    
    # Adaptive Learning System (silent initialization)
    "core.trade_decision_logger",
    "core.feedback_logger",
    "core.penalty_calculator",
    "core.threshold_controller",
    "core.confidence_calibrator",
    "core.drift_detector",
    "core.risk_optimizer",
    "core.adaptation_core",
    
    # Session & Display
    "core.session_statistics",
    "core.trading_dashboard",
    "core.symbol_exclusion_manager",
    
    # Signal processing
    "trading.signal_processor",
    
    # Orchestrator
    "core.trading_orchestrator",
    
    # Trading execution (silent details)
    "core.risk_calculator",
    "core.integrated_trailing_monitor",
    "trading.market_analyzer",
    
    # Realtime display
    "core.realtime_display"
]

for module in noisy_modules:
    logging.getLogger(module).setLevel(logging.WARNING)
