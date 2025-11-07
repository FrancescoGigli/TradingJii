"""
Market Regime Detector - Filters unfavorable market conditions

FIX #2: Critical filter to avoid trading in bear markets and high volatility periods

Checks:
1. Trend (BTC EMA 200 on 4h)
2. Volatility (Max 6% daily)
3. Volume (Min 70% of average)
4. Correlation (Max 85% between symbols)
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta


class MarketRegimeDetector:
    """Detect market regime to avoid trading in unfavorable conditions"""
    
    def __init__(self):
        self.last_check = None
        self.current_regime = None
        self.last_volatility = 0.0
        self.cache_duration = timedelta(minutes=5)  # Cache 5 min
        
    async def is_market_tradeable(
        self,
        exchange,
        symbols_data: Dict = None
    ) -> Tuple[bool, str]:
        """
        Check if market conditions are favorable for trading
        
        Args:
            exchange: CCXT exchange instance
            symbols_data: Dict of symbol data (optional, for correlation check)
            
        Returns:
            (tradeable: bool, reason: str)
        """
        import config
        
        # Check if filter is enabled
        if not getattr(config, 'MARKET_FILTER_ENABLED', False):
            return True, "Filter disabled"
        
        # Use cache if recent
        if self.last_check and (datetime.now() - self.last_check) < self.cache_duration:
            if self.current_regime is not None:
                return self.current_regime
        
        try:
            benchmark = getattr(config, 'MARKET_FILTER_BENCHMARK', 'BTC/USDT:USDT')
            
            # Fetch benchmark data
            benchmark_data = await self._fetch_benchmark_data(
                exchange,
                benchmark,
                getattr(config, 'MARKET_FILTER_EMA_TIMEFRAME', '4h'),
                limit=250
            )
            
            if benchmark_data is None or len(benchmark_data) < 50:
                logging.warning("⚠️ Insufficient benchmark data for market filter")
                return False, "Insufficient data"
            
            # CHECK 1: Trend Filter (EMA)
            ema_period = getattr(config, 'MARKET_FILTER_EMA_PERIOD', 200)
            
            if len(benchmark_data) >= ema_period:
                ema = benchmark_data['close'].ewm(span=ema_period, adjust=False).mean()
                current_price = benchmark_data['close'].iloc[-1]
                ema_value = ema.iloc[-1]
                
                if current_price < ema_value:
                    reason = f"Bear: {benchmark.split('/')[0]} ${current_price:.0f} < EMA{ema_period} ${ema_value:.0f}"
                    logging.warning(f"🔴 {reason}")
                    self._cache_result(False, reason)
                    return False, reason
                
                logging.debug(f"✅ Trend: {benchmark.split('/')[0]} ${current_price:.0f} > EMA{ema_period} ${ema_value:.0f}")
            
            # CHECK 2: Volatility Filter
            returns = benchmark_data['close'].pct_change().dropna()
            
            # Calculate daily volatility
            periods_per_day = 24 / 4  # 4h timeframe = 6 periods per day
            volatility = returns.std() * np.sqrt(periods_per_day)
            self.last_volatility = volatility
            
            max_vol = getattr(config, 'MARKET_FILTER_MAX_VOLATILITY', 0.06)
            
            if volatility > max_vol:
                reason = f"High volatility: {volatility:.1%} > {max_vol:.1%}"
                logging.warning(f"⚠️ {reason}")
                self._cache_result(False, reason)
                return False, reason
            
            logging.debug(f"✅ Volatility: {volatility:.1%} (acceptable)")
            
            # CHECK 3: Volume Filter
            if 'volume' in benchmark_data.columns:
                avg_volume = benchmark_data['volume'].rolling(20).mean().iloc[-1]
                current_volume = benchmark_data['volume'].iloc[-1]
                
                if avg_volume > 0:
                    volume_ratio = current_volume / avg_volume
                    min_ratio = getattr(config, 'MARKET_FILTER_MIN_VOLUME_RATIO', 0.7)
                    
                    if volume_ratio < min_ratio:
                        reason = f"Low volume: {volume_ratio:.0%} < {min_ratio:.0%}"
                        logging.warning(f"⚠️ {reason}")
                        self._cache_result(False, reason)
                        return False, reason
                    
                    logging.debug(f"✅ Volume: {volume_ratio:.0%} (acceptable)")
            
            # CHECK 4: Correlation Filter (optional)
            if symbols_data and len(symbols_data) >= 5:
                try:
                    avg_corr = self._calculate_average_correlation(symbols_data)
                    max_corr = getattr(config, 'MARKET_FILTER_MAX_CORRELATION', 0.85)
                    
                    if avg_corr > max_corr:
                        reason = f"High correlation: {avg_corr:.0%} > {max_corr:.0%}"
                        logging.warning(f"⚠️ {reason}")
                        self._cache_result(False, reason)
                        return False, reason
                    
                    logging.debug(f"✅ Correlation: {avg_corr:.0%} (diversified)")
                except Exception as e:
                    logging.debug(f"Correlation check failed: {e}")
            
            # All checks passed
            reason = "Market conditions favorable"
            logging.info(f"✅ {reason}")
            self._cache_result(True, reason)
            return True, reason
            
        except Exception as e:
            reason = f"Filter error: {str(e)}"
            logging.error(f"❌ Market filter error: {e}", exc_info=True)
            self._cache_result(False, reason)
            return False, reason
    
    async def _fetch_benchmark_data(
        self,
        exchange,
        symbol: str,
        timeframe: str,
        limit: int = 250
    ) -> Optional[pd.DataFrame]:
        """Fetch benchmark symbol data"""
        try:
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            return df
            
        except Exception as e:
            logging.error(f"Failed to fetch benchmark data for {symbol}: {e}")
            return None
    
    def _calculate_average_correlation(self, symbols_data: Dict) -> float:
        """Calculate average correlation between symbols"""
        try:
            # Extract close prices for top symbols
            closes = {}
            
            for symbol, data in list(symbols_data.items())[:10]:
                if '15m' in data and len(data['15m']) >= 50:
                    closes[symbol] = data['15m']['close'].values[-50:]
            
            if len(closes) < 3:
                return 0.5  # Neutral if insufficient data
            
            # Calculate correlation matrix
            df = pd.DataFrame(closes)
            corr_matrix = df.corr()
            
            # Get upper triangle (avoid diagonal)
            mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
            correlations = corr_matrix.where(mask).values.flatten()
            correlations = correlations[~np.isnan(correlations)]
            
            if len(correlations) == 0:
                return 0.5
            
            avg_correlation = np.mean(correlations)
            return avg_correlation
            
        except Exception as e:
            logging.debug(f"Correlation calculation failed: {e}")
            return 0.5  # Neutral on error
    
    def _cache_result(self, tradeable: bool, reason: str):
        """Cache the result"""
        self.last_check = datetime.now()
        self.current_regime = (tradeable, reason)


# Global instance
global_market_filter = MarketRegimeDetector()
