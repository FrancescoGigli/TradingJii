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
# CARTELLA LOG
# ==============================
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)


# ==============================
# HANDLER
# ==============================
# Console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(EmojiFormatter("%(asctime)s %(levelname)s %(message)s"))

# File unico con tutto
file_handler = logging.FileHandler(
    logs_dir / "trading_bot.log", mode="w", encoding="utf-8"
)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
)

# File errori
error_handler = logging.FileHandler(
    logs_dir / "trading_bot_errors.log", mode="w", encoding="utf-8"
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s %(funcName)s:%(lineno)d %(message)s")
)


# ==============================
# ROOT LOGGER
# ==============================
logging.basicConfig(
    level=logging.INFO,  # base rimane INFO
    handlers=[console_handler, file_handler, error_handler],
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)


# ==============================
# RIDUZIONE VERBOSITÀ SOLO MODULI "CHIACCHIERONI"
# ==============================
noisy_modules = [
    "core.thread_safe_position_manager",   # altrimenti logga ogni init/load
    "core.smart_api_manager",              # logga ogni setup
    "core.unified_stop_loss_calculator",   # log debug ridondanti
    "core.trailing_monitor",               # troppo verboso se lasciato a INFO
    "core.order_manager",                  # stampa ogni chiamata API
    "trade_manager"                        # log molto frequenti
]

for module in noisy_modules:
    logging.getLogger(module).setLevel(logging.WARNING)


# ==============================
# STARTUP LOG
# ==============================
logging.info("🚀 LOGGING SYSTEM INITIALIZED (balanced)")
logging.info(f"📁 Log files location: {logs_dir.absolute()}")
