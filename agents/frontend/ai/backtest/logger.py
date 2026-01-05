"""
📝 Backtest Logger - Salva i risultati del backtest in file di log

Crea file di log leggeri in formato CSV per:
- Ogni signal (LONG, SHORT, NEUTRAL)
- Confidence score
- Componenti del segnale (RSI, MACD, BB)
- Trade aperti/chiusi
"""

import os
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Union
import pandas as pd
import numpy as np

from .trades import Trade, TradeType


def safe_timestamp_str(ts) -> str:
    """
    Converte un timestamp (datetime o pandas Timestamp) in stringa ISO.
    Gestisce NaT e valori None in modo sicuro.
    """
    if ts is None:
        return ''
    # Check for pandas NaT
    if pd.isna(ts):
        return ''
    try:
        # Works for both datetime and pandas Timestamp
        if hasattr(ts, 'isoformat'):
            return ts.isoformat()
        return str(ts)
    except Exception:
        return ''


# Directory per i log
LOG_DIR = Path("/app/shared/backtest_logs")


def ensure_log_dir():
    """Crea la directory dei log se non esiste"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_signal_log_path(symbol: str, timeframe: str) -> Path:
    """Ottiene il path del file di log dei segnali"""
    ensure_log_dir()
    filename = f"signals_{symbol}_{timeframe}.csv"
    return LOG_DIR / filename


def get_trade_log_path(symbol: str, timeframe: str) -> Path:
    """Ottiene il path del file di log dei trade"""
    ensure_log_dir()
    filename = f"trades_{symbol}_{timeframe}.csv"
    return LOG_DIR / filename


def log_signal(
    symbol: str,
    timeframe: str,
    timestamp: datetime,
    confidence: float,
    signal_type: str,  # 'LONG', 'SHORT', 'NEUTRAL'
    rsi_score: float,
    macd_score: float,
    bb_score: float,
    price: float,
    rsi_value: Optional[float] = None,
    macd_value: Optional[float] = None
):
    """
    Logga un singolo segnale nel file CSV.
    
    Args:
        symbol: Simbolo della crypto (es. BTCUSDT)
        timeframe: Timeframe (es. 15m)
        timestamp: Timestamp del segnale
        confidence: Score di confidenza (-100 a +100)
        signal_type: Tipo di segnale (LONG, SHORT, NEUTRAL)
        rsi_score: Contributo RSI al confidence
        macd_score: Contributo MACD al confidence
        bb_score: Contributo Bollinger al confidence
        price: Prezzo corrente
        rsi_value: Valore RSI grezzo
        macd_value: Valore MACD grezzo
    """
    log_path = get_signal_log_path(symbol, timeframe)
    
    # Header per il CSV
    headers = [
        'timestamp', 'symbol', 'timeframe', 'price',
        'confidence', 'signal_type',
        'rsi_score', 'macd_score', 'bb_score',
        'rsi_value', 'macd_value',
        'logged_at'
    ]
    
    # Crea file con header se non esiste
    file_exists = log_path.exists()
    
    with open(log_path, 'a', newline='') as f:
        writer = csv.writer(f)
        
        if not file_exists:
            writer.writerow(headers)
        
        writer.writerow([
            safe_timestamp_str(timestamp),
            symbol,
            timeframe,
            f"{price:.2f}" if price is not None and not pd.isna(price) else '',
            f"{confidence:.2f}" if confidence is not None and not pd.isna(confidence) else '',
            signal_type,
            f"{rsi_score:.2f}" if rsi_score is not None and not pd.isna(rsi_score) else '',
            f"{macd_score:.2f}" if macd_score is not None and not pd.isna(macd_score) else '',
            f"{bb_score:.2f}" if bb_score is not None and not pd.isna(bb_score) else '',
            f"{rsi_value:.2f}" if rsi_value is not None and not pd.isna(rsi_value) else '',
            f"{macd_value:.4f}" if macd_value is not None and not pd.isna(macd_value) else '',
            datetime.now().isoformat()
        ])


def log_trade(
    symbol: str,
    timeframe: str,
    trade: Trade
):
    """
    Logga un trade completato nel file CSV.
    
    Args:
        symbol: Simbolo della crypto
        timeframe: Timeframe
        trade: Oggetto Trade da loggare
    """
    log_path = get_trade_log_path(symbol, timeframe)
    
    # Header per il CSV
    headers = [
        'entry_time', 'exit_time', 'symbol', 'timeframe',
        'trade_type', 'entry_price', 'exit_price',
        'pnl_pct', 'is_winner', 'entry_confidence',
        'logged_at'
    ]
    
    # Crea file con header se non esiste
    file_exists = log_path.exists()
    
    with open(log_path, 'a', newline='') as f:
        writer = csv.writer(f)
        
        if not file_exists:
            writer.writerow(headers)
        
        writer.writerow([
            safe_timestamp_str(trade.entry_time),
            safe_timestamp_str(trade.exit_time),
            symbol,
            timeframe,
            trade.trade_type.value if trade.trade_type else '',
            f"{trade.entry_price:.2f}" if trade.entry_price and not pd.isna(trade.entry_price) else '',
            f"{trade.exit_price:.2f}" if trade.exit_price and not pd.isna(trade.exit_price) else '',
            f"{trade.pnl_pct:.2f}" if trade.pnl_pct is not None and not pd.isna(trade.pnl_pct) else '',
            str(trade.is_winner) if trade.is_winner is not None else '',
            f"{trade.entry_confidence:.2f}" if trade.entry_confidence and not pd.isna(trade.entry_confidence) else '',
            datetime.now().isoformat()
        ])


def log_backtest_summary(
    symbol: str,
    timeframe: str,
    total_signals: int,
    long_signals: int,
    short_signals: int,
    neutral_signals: int,
    total_trades: int,
    winning_trades: int,
    losing_trades: int,
    total_return: float,
    win_rate: float,
    avg_win: float,
    avg_loss: float
):
    """
    Logga un riepilogo del backtest.
    """
    ensure_log_dir()
    summary_path = LOG_DIR / "backtest_summaries.csv"
    
    headers = [
        'timestamp', 'symbol', 'timeframe',
        'total_signals', 'long_signals', 'short_signals', 'neutral_signals',
        'total_trades', 'winning_trades', 'losing_trades',
        'total_return_pct', 'win_rate_pct',
        'avg_win_pct', 'avg_loss_pct'
    ]
    
    file_exists = summary_path.exists()
    
    with open(summary_path, 'a', newline='') as f:
        writer = csv.writer(f)
        
        if not file_exists:
            writer.writerow(headers)
        
        writer.writerow([
            datetime.now().isoformat(),
            symbol,
            timeframe,
            total_signals,
            long_signals,
            short_signals,
            neutral_signals,
            total_trades,
            winning_trades,
            losing_trades,
            f"{total_return:.2f}",
            f"{win_rate:.1f}",
            f"{avg_win:.2f}",
            f"{avg_loss:.2f}"
        ])


def get_recent_signals(symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
    """
    Legge gli ultimi N segnali dal log.
    
    Returns:
        DataFrame con gli ultimi segnali
    """
    log_path = get_signal_log_path(symbol, timeframe)
    
    if not log_path.exists():
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(log_path)
        return df.tail(limit)
    except Exception:
        return pd.DataFrame()


def get_trade_history(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Legge lo storico trade dal log.
    
    Returns:
        DataFrame con lo storico trade
    """
    log_path = get_trade_log_path(symbol, timeframe)
    
    if not log_path.exists():
        return pd.DataFrame()
    
    try:
        return pd.read_csv(log_path)
    except Exception:
        return pd.DataFrame()


def clear_logs(symbol: str = None, timeframe: str = None):
    """
    Cancella i file di log.
    
    Args:
        symbol: Se specificato, cancella solo per quel simbolo
        timeframe: Se specificato, cancella solo per quel timeframe
    """
    ensure_log_dir()
    
    if symbol and timeframe:
        # Cancella file specifici
        signal_log = get_signal_log_path(symbol, timeframe)
        trade_log = get_trade_log_path(symbol, timeframe)
        
        if signal_log.exists():
            signal_log.unlink()
        if trade_log.exists():
            trade_log.unlink()
    else:
        # Cancella tutti i log
        for f in LOG_DIR.glob("*.csv"):
            f.unlink()


def get_log_stats() -> Dict:
    """
    Ottiene statistiche sui file di log.
    
    Returns:
        Dizionario con statistiche
    """
    ensure_log_dir()
    
    stats = {
        'total_files': 0,
        'total_size_kb': 0,
        'signal_files': [],
        'trade_files': []
    }
    
    for f in LOG_DIR.glob("*.csv"):
        stats['total_files'] += 1
        stats['total_size_kb'] += f.stat().st_size / 1024
        
        if f.name.startswith('signals_'):
            stats['signal_files'].append(f.name)
        elif f.name.startswith('trades_'):
            stats['trade_files'].append(f.name)
    
    return stats
