import logging
import logging.handlers
import sys
import os
from pathlib import Path
from termcolor import colored

class EmojiFormatter(logging.Formatter):
    """
    Custom formatter with emojis for console output.
    
    Fixes:
    - Safer message modification to avoid breaking external loggers
    - Preserves original message for proper log propagation
    """
    # Mappa dei livelli di log con emoji e colori
    LEVEL_EMOJI = {
        'DEBUG': '🐛',
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨'
    }
    LEVEL_COLOR = {
        'DEBUG': 'blue',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'magenta'
    }
    
    def format(self, record):
        # Create a copy to avoid modifying the original record
        record_copy = logging.makeLogRecord(record.__dict__)
        
        # Seleziona l'emoji e il colore in base al livello del log
        emoji = self.LEVEL_EMOJI.get(record_copy.levelname, '')
        color = self.LEVEL_COLOR.get(record_copy.levelname, 'white')
        
        # Safely modify only the copy for console display
        original_msg = record_copy.getMessage()
        record_copy.msg = f"{colored(emoji, color)} {original_msg}"
        record_copy.args = ()  # Clear args since we've already formatted the message
        
        return super().format(record_copy)

# Ensure logs directory exists
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Handler per la console con il formatter personalizzato
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(EmojiFormatter("%(asctime)s %(levelname)s %(message)s"))

# Handler per il file con rotazione (FIXED: now uses append mode)
# Uses RotatingFileHandler to manage log file size and keep history
file_handler = logging.handlers.RotatingFileHandler(
    logs_dir / "trading_bot_derivatives.log", 
    mode='a',  # CRITICAL FIX: Changed from 'w' to 'a' to preserve logs
    encoding="utf-8",
    maxBytes=10*1024*1024,  # 10MB per file
    backupCount=5  # Keep 5 historical files
)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

# Error-only file handler for critical issues
error_handler = logging.handlers.RotatingFileHandler(
    logs_dir / "trading_bot_errors.log",
    mode='a',
    encoding="utf-8", 
    maxBytes=5*1024*1024,  # 5MB per file
    backupCount=3
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(funcName)s:%(lineno)d %(message)s"))

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler, error_handler],
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

# Log startup information
logging.info(f"Logging system initialized. Log files location: {logs_dir.absolute()}")
logging.info("Log configuration: Main logs with rotation, separate error logs, console with emojis")
