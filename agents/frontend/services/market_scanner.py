"""
📡 Market Scanner Service
==========================

Scans all Top 100 cryptocurrencies and generates XGBoost signals.
Uses data from the database (no new API calls needed).

Features:
- Loads latest candle + indicators from historical_ohlcv
- Runs XGBoost inference for LONG/SHORT scores
- Calculates combined signal (BUY/SELL/NEUTRAL)
- Returns ranked list by volume
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import pandas as pd
import numpy as np

from services.ml_inference import get_ml_inference_service, compute_ml_features, normalize_xgb_score_batch


# ═══════════════════════════════════════════════════════════════════════════════
# PATH CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SHARED_PATH = os.environ.get('SHARED_DATA_PATH', '/app/shared')
DB_PATH = Path(SHARED_PATH) / 'data_cache' / 'trading_data.db'

# Fallback for local dev
if not DB_PATH.exists():
    DB_PATH = Path(__file__).parent.parent.parent.parent / 'shared' / 'data_cache' / 'trading_data.db'


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MarketSignal:
    """Market signal for a single symbol"""
    symbol: str
    coin: str  # Without /USDT:USDT
    rank: int
    volume_24h: float
    
    # Price info
    price: float
    change_24h: float  # % change
    
    # Technical indicators (raw values)
    rsi: float
    macd_signal: str  # "BULLISH", "BEARISH", "NEUTRAL"
    
    # Technical indicator SCORES (scaled -33.33 to +33.33 each)
    rsi_score: float      # RSI contribution to signal
    macd_score: float     # MACD contribution to signal
    bb_score: float       # Bollinger Bands contribution to signal
    tech_signal: float    # Total technical signal (-100 to +100)
    
    # XGBoost scores (normalized -100 to +100)
    xgb_long: float
    xgb_short: float
    
    # Combined signal
    signal: str  # "BUY", "SELL", "NEUTRAL"
    confidence: float  # 0-100
    
    # Timestamp
    last_update: str


# ═══════════════════════════════════════════════════════════════════════════════
# MARKET SCANNER SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class MarketScannerService:
    """
    Scans market and generates trading signals.
    """
    
    def __init__(self):
        self.ml_service = get_ml_inference_service()
        self._cache = None
        self._cache_time = None
        self._cache_ttl = 60  # Cache for 60 seconds
        self._last_candle_timestamp = None  # Track latest candle from DB
    
    def scan_market(self, timeframe: str = '15m', top_n: int = 100) -> List[MarketSignal]:
        """
        Scan all symbols and generate signals.
        
        Uses PERCENTILE normalization for XGB scores across all symbols.
        This means top 10% get +60, bottom 10% get -60, etc.
        
        Args:
            timeframe: Timeframe to analyze (default 15m)
            top_n: Number of top symbols by volume
            
        Returns:
            List of MarketSignal objects sorted by volume
        """
        # Check cache
        if self._cache and self._cache_time:
            elapsed = (datetime.now() - self._cache_time).total_seconds()
            if elapsed < self._cache_ttl:
                return self._cache
        
        signals = []
        raw_data = []  # Collect raw data first for batch normalization
        
        if not DB_PATH.exists():
            return signals
        
        # Connect with timeout and WAL mode for better concurrency
        conn = sqlite3.connect(str(DB_PATH), timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        
        try:
            # Get top symbols by volume
            top_symbols = pd.read_sql_query("""
                SELECT symbol, volume_24h, rank
                FROM top_symbols
                ORDER BY rank ASC
                LIMIT ?
            """, conn, params=(top_n,))
            
            if top_symbols.empty:
                return signals
            
            # Phase 1: Collect raw XGB scores for all symbols
            for _, row in top_symbols.iterrows():
                symbol = row['symbol']
                volume_24h = row['volume_24h']
                rank = row['rank']
                
                data = self._get_symbol_data(conn, symbol, timeframe, rank, volume_24h)
                if data:
                    raw_data.append(data)
            
            if not raw_data:
                return signals
            
            # Phase 2: Normalize XGB scores using percentile ranking
            df_raw = pd.DataFrame(raw_data)
            
            # Percentile normalize - top gets +100, bottom gets -100
            df_raw['xgb_long_norm'] = normalize_xgb_score_batch(df_raw['xgb_long_raw'], 'long')
            df_raw['xgb_short_norm'] = normalize_xgb_score_batch(df_raw['xgb_short_raw'], 'short')
            
            # Phase 3: Create MarketSignal objects with normalized scores
            for _, row in df_raw.iterrows():
                xgb_long = float(row['xgb_long_norm'])
                xgb_short = float(row['xgb_short_norm'])
                
                # Calculate signal with normalized scores
                signal, confidence = self._calculate_signal(
                    row['rsi'], row['macd_signal'], xgb_long, xgb_short
                )
                
                signals.append(MarketSignal(
                    symbol=row['symbol'],
                    coin=row['coin'],
                    rank=row['rank'],
                    volume_24h=row['volume_24h'],
                    price=row['price'],
                    change_24h=row['change_24h'],
                    rsi=row['rsi'],
                    macd_signal=row['macd_signal'],
                    rsi_score=float(row['rsi_score']),
                    macd_score=float(row['macd_score']),
                    bb_score=float(row['bb_score']),
                    tech_signal=float(row['tech_signal']),
                    xgb_long=xgb_long,
                    xgb_short=xgb_short,
                    signal=signal,
                    confidence=confidence,
                    last_update=row['last_update']
                ))
            
            # Sort by volume
            signals.sort(key=lambda x: x.volume_24h, reverse=True)
            
            # Update cache
            self._cache = signals
            self._cache_time = datetime.now()
            
            return signals
            
        except Exception as e:
            print(f"Error scanning market: {e}")
            import traceback
            traceback.print_exc()
            return signals
        finally:
            conn.close()
    
    def _get_symbol_data(
        self,
        conn: sqlite3.Connection,
        symbol: str,
        timeframe: str,
        rank: int,
        volume_24h: float
    ) -> Optional[Dict[str, Any]]:
        """Get raw data for a symbol (before normalization)"""
        
        try:
            # Get latest candles (need ~200 for feature calculation)
            df = pd.read_sql_query(f"""
                SELECT *
                FROM historical_ohlcv
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC
                LIMIT 250
            """, conn, params=(symbol, timeframe))
            
            if len(df) < 50:
                return None
            
            # Reverse to chronological order
            df = df.iloc[::-1].reset_index(drop=True)
            
            # Get latest row
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            
            # Calculate indicators if not present
            if 'rsi' not in df.columns or pd.isna(latest.get('rsi')):
                df = compute_ml_features(df)
                latest = df.iloc[-1]
            
            # Get price info
            price = float(latest['close'])
            open_price = float(df.iloc[0]['close']) if len(df) > 24 else float(latest['open'])
            change_24h = ((price - open_price) / open_price) * 100 if open_price > 0 else 0
            
            # ALWAYS compute ML features (69 features needed by XGBoost)
            # The database only has basic indicators, not all 69 features
            df = compute_ml_features(df)
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            
            # Get RSI
            rsi = float(latest.get('rsi', 50))
            
            # Get MACD signal
            macd_hist = float(latest.get('macd_hist', 0))
            prev_macd_hist = float(prev.get('macd_hist', 0)) if 'macd_hist' in prev else 0
            
            if macd_hist > 0 and macd_hist > prev_macd_hist:
                macd_signal = "BULLISH"
            elif macd_hist < 0 and macd_hist < prev_macd_hist:
                macd_signal = "BEARISH"
            else:
                macd_signal = "NEUTRAL"
            
            # ═══════════════════════════════════════════════════════════════════
            # CALCULATE TECHNICAL INDICATOR SCORES (same logic as Signal Calculator)
            # Each score ranges from -33.33 to +33.33
            # ═══════════════════════════════════════════════════════════════════
            
            # RSI SCORE: oversold (<30) = +33.33, overbought (>70) = -33.33
            if rsi < 30:
                rsi_score = 33.33 * (1 - rsi / 30)  # RSI=0 → +33.33, RSI=30 → 0
            elif rsi > 70:
                rsi_score = -33.33 * (rsi - 70) / 30  # RSI=70 → 0, RSI=100 → -33.33
            else:
                # Neutral zone: RSI=50 → 0, RSI=30 → +8.3, RSI=70 → -8.3
                rsi_score = -33.33 * (rsi - 50) / 40
            
            # MACD SCORE: based on histogram as % of price
            macd_diff = float(latest.get('macd', 0)) - float(latest.get('macd_signal', 0))
            macd_diff_pct = (macd_diff / price) * 100 if price > 0 else 0
            max_diff_pct = 0.5  # Same as config
            macd_score = (macd_diff_pct / max_diff_pct) * 33.33
            macd_score = max(-33.33, min(33.33, macd_score))
            
            # BB SCORE: position within bands (0=lower, 1=upper)
            bb_upper = float(latest.get('bb_upper', price * 1.02))
            bb_lower = float(latest.get('bb_lower', price * 0.98))
            bb_width = bb_upper - bb_lower
            if bb_width > 0:
                bb_position = (price - bb_lower) / bb_width  # 0-1
                bb_score = 33.33 * (0.5 - bb_position) * 2  # 0 → +33.33, 1 → -33.33
            else:
                bb_score = 0
            bb_score = max(-33.33, min(33.33, bb_score))
            
            # TECH SIGNAL: sum of all scores (range -100 to +100)
            tech_signal = rsi_score + macd_score + bb_score
            tech_signal = max(-100, min(100, tech_signal))
            
            # Get RAW XGBoost scores (not normalized)
            xgb_long_raw = 0.0
            xgb_short_raw = 0.0
            
            if self.ml_service.is_available:
                pred = self.ml_service.predict(latest)
                if pred.is_valid:
                    xgb_long_raw = pred.score_long  # RAW score
                    xgb_short_raw = pred.score_short  # RAW score
            
            # Clean coin name
            coin = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            
            return {
                'symbol': symbol,
                'coin': coin,
                'rank': rank,
                'volume_24h': volume_24h,
                'price': price,
                'change_24h': change_24h,
                'rsi': rsi,
                'macd_signal': macd_signal,
                'rsi_score': rsi_score,
                'macd_score': macd_score,
                'bb_score': bb_score,
                'tech_signal': tech_signal,
                'xgb_long_raw': xgb_long_raw,
                'xgb_short_raw': xgb_short_raw,
                'last_update': str(latest.get('timestamp', datetime.now()))
            }
            
        except Exception as e:
            print(f"Error getting data for {symbol}: {e}")
            return None
    
    def _analyze_symbol(
        self, 
        conn: sqlite3.Connection, 
        symbol: str, 
        timeframe: str,
        rank: int,
        volume_24h: float
    ) -> Optional[MarketSignal]:
        """Analyze a single symbol"""
        
        try:
            # Get latest candles (need ~200 for feature calculation)
            df = pd.read_sql_query(f"""
                SELECT *
                FROM historical_ohlcv
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC
                LIMIT 250
            """, conn, params=(symbol, timeframe))
            
            if len(df) < 50:
                return None
            
            # Reverse to chronological order
            df = df.iloc[::-1].reset_index(drop=True)
            
            # Get latest row
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            
            # Calculate indicators if not present
            if 'rsi' not in df.columns or pd.isna(latest.get('rsi')):
                df = compute_ml_features(df)
                latest = df.iloc[-1]
            
            # Get price info
            price = float(latest['close'])
            open_price = float(df.iloc[0]['close']) if len(df) > 24 else float(latest['open'])
            change_24h = ((price - open_price) / open_price) * 100 if open_price > 0 else 0
            
            # Get RSI
            rsi = float(latest.get('rsi', 50))
            
            # Get MACD signal
            macd_hist = float(latest.get('macd_hist', 0))
            prev_macd_hist = float(prev.get('macd_hist', 0)) if 'macd_hist' in prev else 0
            
            if macd_hist > 0 and macd_hist > prev_macd_hist:
                macd_signal = "BULLISH"
            elif macd_hist < 0 and macd_hist < prev_macd_hist:
                macd_signal = "BEARISH"
            else:
                macd_signal = "NEUTRAL"
            
            # Run XGBoost prediction
            xgb_long = 0.0
            xgb_short = 0.0
            
            if self.ml_service.is_available:
                pred = self.ml_service.predict(latest)
                if pred.is_valid:
                    xgb_long = pred.score_long_normalized
                    xgb_short = pred.score_short_normalized
            
            # Calculate combined signal
            signal, confidence = self._calculate_signal(rsi, macd_signal, xgb_long, xgb_short)
            
            # Clean coin name
            coin = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            
            return MarketSignal(
                symbol=symbol,
                coin=coin,
                rank=rank,
                volume_24h=volume_24h,
                price=price,
                change_24h=change_24h,
                rsi=rsi,
                macd_signal=macd_signal,
                xgb_long=xgb_long,
                xgb_short=xgb_short,
                signal=signal,
                confidence=confidence,
                last_update=str(latest.get('timestamp', datetime.now()))
            )
            
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
            return None
    
    def _calculate_signal(
        self, 
        rsi: float, 
        macd_signal: str, 
        xgb_long: float, 
        xgb_short: float
    ) -> tuple[str, float]:
        """
        Calculate combined trading signal.
        
        Uses NET XGB SIGNAL (LONG - SHORT):
        - If LONG >> SHORT → BUY
        - If SHORT >> LONG → SELL
        - Otherwise → NEUTRAL
        
        RSI and MACD provide additional confirmation.
        
        Returns:
            (signal, confidence)
        """
        score = 0.0
        
        # XGBoost NET contribution (80% weight)
        # Net signal = LONG - SHORT
        # Range: -200 to +200 (if LONG=100, SHORT=-100 → net=200)
        # Scale to -80 to +80
        xgb_net = (xgb_long - xgb_short) * 0.4
        score += xgb_net
        
        # RSI contribution (10%)
        # RSI < 30 = oversold = bullish (+10)
        # RSI > 70 = overbought = bearish (-10)
        if rsi < 30:
            score += 10 * (30 - rsi) / 30  # Up to +10
        elif rsi > 70:
            score -= 10 * (rsi - 70) / 30  # Up to -10
        
        # MACD contribution (10%)
        if macd_signal == "BULLISH":
            score += 10
        elif macd_signal == "BEARISH":
            score -= 10
        
        # Determine signal with wider thresholds for NET approach
        if score > 40:
            signal = "BUY"
        elif score < -40:
            signal = "SELL"
        else:
            signal = "NEUTRAL"
        
        # Confidence is absolute value of score, capped at 100
        confidence = min(abs(score), 100)
        
        return signal, confidence
    
    def get_top_opportunities(self, direction: str = 'LONG', top_n: int = 10) -> List[MarketSignal]:
        """
        Get top trading opportunities.
        
        Args:
            direction: 'LONG' or 'SHORT'
            top_n: Number of results
            
        Returns:
            List of top opportunities
        """
        signals = self.scan_market()
        
        if direction == 'LONG':
            # Sort by xgb_long descending, filter BUY signals
            filtered = [s for s in signals if s.signal == 'BUY']
            filtered.sort(key=lambda x: x.xgb_long, reverse=True)
        else:
            # Sort by xgb_short descending, filter SELL signals
            filtered = [s for s in signals if s.signal == 'SELL']
            filtered.sort(key=lambda x: x.xgb_short, reverse=True)
        
        return filtered[:top_n]
    
    def clear_cache(self):
        """Clear the scan cache"""
        self._cache = None
        self._cache_time = None


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_scanner_service = None


def get_market_scanner_service() -> MarketScannerService:
    """Get singleton instance of market scanner service"""
    global _scanner_service
    if _scanner_service is None:
        _scanner_service = MarketScannerService()
    return _scanner_service
