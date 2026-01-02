"""
Configurazione Data Fetcher Agent

Configurazioni per il download dati OHLCV da Bybit
"""

from __future__ import annotations

import os
from pathlib import Path

# ----------------------------------------------------------------------
# Carica il file .env se presente
# ----------------------------------------------------------------------
try:
    from dotenv import load_dotenv, find_dotenv

    _env_file = find_dotenv()
    if _env_file:
        load_dotenv(_env_file, override=False)
except ModuleNotFoundError:
    pass

# ----------------------------------------------------------------------
# Credenziali Bybit
# ----------------------------------------------------------------------
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")

if not API_KEY or not API_SECRET:
    raise RuntimeError(
        "Chiavi API mancanti: definisci BYBIT_API_KEY e BYBIT_API_SECRET "
        "nel file .env o tra le variabili d'ambiente."
    )

# ----------------------------------------------------------------------
# Configurazione Exchange
# ----------------------------------------------------------------------
exchange_config = {
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "enableRateLimit": True,
    "options": {
        "adjustForTimeDifference": True,
        "recvWindow": 300000,
    },
}

# ----------------------------------------------------------------------
# Configurazione Download Dati
# ----------------------------------------------------------------------
# Timeframes disponibili
ENABLED_TIMEFRAMES: list[str] = ["15m", "1h", "4h", "1d"]
TIMEFRAME_DEFAULT: str = "15m"

# Numero di candele da salvare per ogni simbolo
CANDLES_LIMIT = 200

# Candele extra per il warmup degli indicatori tecnici
# (EMA 50 = 50, MACD = 35, RSI = 14, Bollinger = 20)
# Consigliato: almeno 100 candele per copertura completa su tutti i timeframe
WARMUP_CANDLES = 100

# Candele totali da scaricare (CANDLES_LIMIT + WARMUP_CANDLES)
TOTAL_CANDLES_TO_FETCH = CANDLES_LIMIT + WARMUP_CANDLES

# Numero di simboli da analizzare (top per volume)
TOP_SYMBOLS_COUNT = 100

# Giorni di dati massimi da mantenere nel database
DATA_RETENTION_DAYS = 90

# Intervallo di aggiornamento candele (minuti)
UPDATE_INTERVAL_MINUTES = 15

# File di segnale per refresh manuale
REFRESH_SIGNAL_FILE = "refresh_signal.txt"

# ----------------------------------------------------------------------
# Configurazione Cache (shared volume)
# ----------------------------------------------------------------------
# Path al volume condiviso Docker
SHARED_DATA_PATH = os.getenv("SHARED_DATA_PATH", "/app/shared")
CACHE_DIR = f"{SHARED_DATA_PATH}/data_cache"
DB_FILE = "trading_data.db"

# Cache freshness (in minuti)
CACHE_MAX_AGE_MINUTES = 5
