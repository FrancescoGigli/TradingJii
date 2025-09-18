import logging
import logging.handlers
import sys
import os
import re
import html
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

class ANSIPreservingFormatter(logging.Formatter):
    """
    Formatter that preserves ANSI color codes in the output.
    Used for colored file logging.
    """
    
    def format(self, record):
        # Don't modify the message - keep ANSI codes intact
        return super().format(record)

class HTMLFormatter(logging.Formatter):
    """
    Formatter that converts ANSI color codes to HTML with CSS.
    """
    
    # ANSI to CSS color mapping
    ANSI_TO_CSS = {
        '\033[30m': '<span style="color: black;">',      # Black
        '\033[31m': '<span style="color: red;">',        # Red  
        '\033[32m': '<span style="color: green;">',      # Green
        '\033[33m': '<span style="color: yellow;">',     # Yellow
        '\033[34m': '<span style="color: blue;">',       # Blue
        '\033[35m': '<span style="color: magenta;">',    # Magenta
        '\033[36m': '<span style="color: cyan;">',       # Cyan
        '\033[37m': '<span style="color: white;">',      # White
        '\033[90m': '<span style="color: gray;">',       # Bright Black
        '\033[91m': '<span style="color: lightcoral;">',  # Bright Red
        '\033[92m': '<span style="color: lightgreen;">',  # Bright Green
        '\033[93m': '<span style="color: lightyellow;">', # Bright Yellow
        '\033[94m': '<span style="color: lightblue;">',   # Bright Blue
        '\033[95m': '<span style="color: violet;">',      # Bright Magenta
        '\033[96m': '<span style="color: lightcyan;">',   # Bright Cyan
        '\033[97m': '<span style="color: white;">',       # Bright White
        '\033[0m': '</span>',                             # Reset
        '\033[1m': '<strong>',                            # Bold
        '\033[22m': '</strong>',                          # Bold off
    }
    
    def format(self, record):
        # Get the formatted message
        formatted = super().format(record)
        
        # Convert ANSI codes to HTML
        html_message = self._ansi_to_html(formatted)
        
        return html_message
    
    def _ansi_to_html(self, text):
        """Convert ANSI color codes to HTML with CSS"""
        # Escape HTML entities first
        text = html.escape(text)
        
        # Replace ANSI codes with HTML spans
        for ansi_code, html_tag in self.ANSI_TO_CSS.items():
            text = text.replace(ansi_code, html_tag)
        
        # Handle any remaining ANSI codes by removing them
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        text = ansi_escape.sub('', text)
        
        return text

# Ensure logs directory exists
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# 1. Handler per la console con il formatter personalizzato (ESISTENTE)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(EmojiFormatter("%(asctime)s %(levelname)s %(message)s"))

# 2. Handler per il file PLAIN TEXT - OVERWRITE MODE
file_handler = logging.FileHandler(
    logs_dir / "trading_bot_derivatives.log", 
    mode='w',  # OVERWRITE: Fresh file every run
    encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

# 3. Handler per il file ANSI COLORATO - OVERWRITE MODE
ansi_file_handler = logging.FileHandler(
    logs_dir / "trading_bot_colored.log",
    mode='w',  # OVERWRITE: Fresh file every run
    encoding="utf-8"
)
ansi_file_handler.setFormatter(ANSIPreservingFormatter("%(asctime)s %(levelname)s %(message)s"))

# 4. Handler HTML per export - OVERWRITE MODE
html_file_handler = logging.FileHandler(
    logs_dir / "trading_session.html",
    mode='w',  # OVERWRITE: Fresh file every run
    encoding="utf-8"
)
html_file_handler.setFormatter(HTMLFormatter('<div class="log-entry"><span class="timestamp">%(asctime)s</span> <span class="level">%(levelname)s</span> <pre class="message">%(message)s</pre></div>'))

# 5. Handler per errori - OVERWRITE MODE
error_handler = logging.FileHandler(
    logs_dir / "trading_bot_errors.log",
    mode='w',  # OVERWRITE: Fresh file every run
    encoding="utf-8"
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(funcName)s:%(lineno)d %(message)s"))

# Configure root logger with ALL handlers
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler, ansi_file_handler, html_file_handler, error_handler],
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

# Initialize HTML file with CSS
def initialize_html_log():
    """Initialize HTML log file with CSS styling - ALWAYS RECREATE"""
    from datetime import datetime
    
    html_file_path = logs_dir / "trading_session.html"
    
    # Get current timestamp for fresh run indicator
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # ALWAYS recreate HTML file with fresh CSS
    css_style = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Bot Session Log - Fresh Run</title>
    <style>
        body {{ 
            font-family: 'Consolas', 'Courier New', monospace; 
            background: #1a1a1a; 
            color: #ffffff; 
            margin: 0; 
            padding: 20px;
            line-height: 1.4;
        }}
        .log-entry {{ 
            margin-bottom: 5px; 
            border-left: 3px solid #333;
            padding-left: 10px;
        }}
        .timestamp {{ 
            color: #888; 
            font-size: 0.9em; 
        }}
        .level {{ 
            font-weight: bold; 
            padding: 2px 6px; 
            border-radius: 3px;
            font-size: 0.8em;
        }}
        .message {{ 
            margin: 5px 0; 
            white-space: pre-wrap; 
            font-family: inherit;
        }}
        pre {{ margin: 0; }}
        
        /* Table styling for position displays */
        .message:contains('┌') {{
            background: #2d2d2d;
            padding: 10px;
            border-radius: 5px;
            border: 1px solid #444;
        }}
        
        /* Color overrides for better visibility */
        span[style*="lightgreen"] {{ color: #4CAF50 !important; }}
        span[style*="lightcoral"] {{ color: #f44336 !important; }}
        span[style*="lightyellow"] {{ color: #FFEB3B !important; }}
        span[style*="lightcyan"] {{ color: #00BCD4 !important; }}
        span[style*="violet"] {{ color: #9C27B0 !important; }}
        
        /* Fresh run indicator */
        .run-info {{
            background: #2d4a2d;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            border-left: 4px solid #4CAF50;
        }}
    </style>
</head>
<body>
<h1>🚀 Trading Bot Session Log</h1>
<div class="run-info">
    <strong>Fresh Run Started:</strong> {current_time}<br>
    <strong>Mode:</strong> Overwrite logs each run
</div>
<div id="log-container">
"""
    
    with open(html_file_path, 'w', encoding='utf-8') as f:
        f.write(css_style)

# Initialize HTML log
initialize_html_log()

# Log startup information
logging.info(f"🚀 TRIPLE LOGGING SYSTEM INITIALIZED")
logging.info(f"📁 Log files location: {logs_dir.absolute()}")
logging.info("📊 Log configuration:")
logging.info("   ✅ Console: Colored with emojis")
logging.info("   ✅ Plain text: trading_bot_derivatives.log") 
logging.info("   ✅ ANSI colored: trading_bot_colored.log")
logging.info("   ✅ HTML export: trading_session.html")
logging.info("   ✅ Error only: trading_bot_errors.log")
