"""
Trading Simulator for Walk-Forward Testing

Simulates realistic trading on test data using production parameters:
- Leverage 5x
- Stop Loss -6%
- Trailing Stop (+12% ROE trigger, -8% ROE distance)
- Confidence threshold 65%

This allows us to test model performance with actual trading rules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal
import numpy as np
import pandas as pd

import config

_LOG = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """Result of a simulated trade"""
    symbol: str
    direction: Literal['BUY', 'SELL']
    entry_price: float
    exit_price: float
    entry_time: int  # Candle index
    exit_time: int   # Candle index
    profit_loss_pct: float  # Price change %
    profit_loss_roe: float  # ROE with leverage
    exit_reason: Literal['SL', 'TRAILING', 'END_OF_DATA']
    holding_time_candles: int
    confidence: float  # ML confidence at entry
    

class TradingSimulator:
    """
    Simulates trading using production parameters from config.py
    
    Features:
    - Stop Loss at -6% price (-30% ROE with 5x leverage)
    - Trailing Stop activation at +12% ROE
    - Trailing distance -8% ROE from peak
    - Realistic profit/loss calculation with leverage
    """
    
    def __init__(self):
        self.leverage = config.LEVERAGE
        self.stop_loss_pct = config.STOP_LOSS_PCT
        self.trailing_trigger_roe = config.TRAILING_TRIGGER_ROE
        self.trailing_distance_roe = config.TRAILING_DISTANCE_ROE_OPTIMAL
        self.min_confidence = config.MIN_CONFIDENCE
        
        _LOG.info(f"🎮 Trading Simulator initialized:")
        _LOG.info(f"   Leverage: {self.leverage}x")
        _LOG.info(f"   Stop Loss: {self.stop_loss_pct*100:.1f}%")
        _LOG.info(f"   Trailing Trigger: {self.trailing_trigger_roe*100:.1f}% ROE")
        _LOG.info(f"   Trailing Distance: {self.trailing_distance_roe*100:.1f}% ROE")
        
    def calculate_roe(self, entry_price: float, current_price: float, 
                      direction: Literal['BUY', 'SELL']) -> float:
        """
        Calculate ROE (Return on Equity) with leverage.
        
        Args:
            entry_price: Entry price
            current_price: Current price
            direction: 'BUY' or 'SELL'
            
        Returns:
            ROE as decimal (0.12 = +12% ROE)
        """
        price_change_pct = (current_price - entry_price) / entry_price
        
        if direction == 'SELL':
            price_change_pct = -price_change_pct  # Invert for short
            
        roe = price_change_pct * self.leverage
        return roe
    
    def simulate_trade(self, symbol: str, direction: Literal['BUY', 'SELL'], 
                       entry_idx: int, entry_price: float, 
                       future_data: pd.DataFrame, confidence: float) -> TradeResult:
        """
        Simulate a single trade with SL and trailing stop.
        
        Args:
            symbol: Symbol name
            direction: 'BUY' or 'SELL'
            entry_idx: Entry candle index in original data
            entry_price: Entry price
            future_data: DataFrame with future candles (high, low, close)
            confidence: ML confidence at entry
            
        Returns:
            TradeResult with profit/loss and exit reason
        """
        # Initialize tracking
        peak_roe = 0.0  # Best ROE seen so far
        trailing_active = False
        trailing_stop_price = None
        
        # Calculate SL price
        if direction == 'BUY':
            sl_price = entry_price * (1 - self.stop_loss_pct)
        else:  # SELL
            sl_price = entry_price * (1 + self.stop_loss_pct)
        
        # Simulate each candle
        for i, (idx, row) in enumerate(future_data.iterrows()):
            high = row['high']
            low = row['low']
            close = row['close']
            
            # Check SL hit (always active)
            if direction == 'BUY':
                if low <= sl_price:
                    # SL hit on this candle
                    exit_price = sl_price
                    exit_roe = self.calculate_roe(entry_price, exit_price, direction)
                    return TradeResult(
                        symbol=symbol,
                        direction=direction,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        entry_time=entry_idx,
                        exit_time=entry_idx + i + 1,
                        profit_loss_pct=(exit_price - entry_price) / entry_price,
                        profit_loss_roe=exit_roe,
                        exit_reason='SL',
                        holding_time_candles=i + 1,
                        confidence=confidence
                    )
            else:  # SELL
                if high >= sl_price:
                    # SL hit on this candle
                    exit_price = sl_price
                    exit_roe = self.calculate_roe(entry_price, exit_price, direction)
                    return TradeResult(
                        symbol=symbol,
                        direction=direction,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        entry_time=entry_idx,
                        exit_time=entry_idx + i + 1,
                        profit_loss_pct=(exit_price - entry_price) / entry_price,
                        profit_loss_roe=exit_roe,
                        exit_reason='SL',
                        holding_time_candles=i + 1,
                        confidence=confidence
                    )
            
            # Update peak ROE using current candle's high/low
            if direction == 'BUY':
                current_best_price = high
            else:
                current_best_price = low
                
            current_roe = self.calculate_roe(entry_price, current_best_price, direction)
            peak_roe = max(peak_roe, current_roe)
            
            # Check if trailing stop should activate
            if not trailing_active and peak_roe >= self.trailing_trigger_roe:
                trailing_active = True
                # Set initial trailing stop
                trailing_stop_roe = peak_roe - self.trailing_distance_roe
                
                # Convert ROE back to price
                price_change_for_trailing = (trailing_stop_roe / self.leverage)
                if direction == 'SELL':
                    price_change_for_trailing = -price_change_for_trailing
                    
                trailing_stop_price = entry_price * (1 + price_change_for_trailing)
            
            # Update trailing stop if active
            if trailing_active:
                # Calculate new trailing stop based on peak
                trailing_stop_roe = peak_roe - self.trailing_distance_roe
                
                # Convert ROE to price
                price_change_for_trailing = (trailing_stop_roe / self.leverage)
                if direction == 'SELL':
                    price_change_for_trailing = -price_change_for_trailing
                    
                new_trailing_price = entry_price * (1 + price_change_for_trailing)
                
                # Update only if it moves in favorable direction
                if direction == 'BUY':
                    if trailing_stop_price is None or new_trailing_price > trailing_stop_price:
                        trailing_stop_price = new_trailing_price
                else:  # SELL
                    if trailing_stop_price is None or new_trailing_price < trailing_stop_price:
                        trailing_stop_price = new_trailing_price
                
                # Check if trailing stop hit
                if direction == 'BUY':
                    if low <= trailing_stop_price:
                        exit_price = trailing_stop_price
                        exit_roe = self.calculate_roe(entry_price, exit_price, direction)
                        return TradeResult(
                            symbol=symbol,
                            direction=direction,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            entry_time=entry_idx,
                            exit_time=entry_idx + i + 1,
                            profit_loss_pct=(exit_price - entry_price) / entry_price,
                            profit_loss_roe=exit_roe,
                            exit_reason='TRAILING',
                            holding_time_candles=i + 1,
                            confidence=confidence
                        )
                else:  # SELL
                    if high >= trailing_stop_price:
                        exit_price = trailing_stop_price
                        exit_roe = self.calculate_roe(entry_price, exit_price, direction)
                        return TradeResult(
                            symbol=symbol,
                            direction=direction,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            entry_time=entry_idx,
                            exit_time=entry_idx + i + 1,
                            profit_loss_pct=(exit_price - entry_price) / entry_price,
                            profit_loss_roe=exit_roe,
                            exit_reason='TRAILING',
                            holding_time_candles=i + 1,
                            confidence=confidence
                        )
        
        # End of data - close at last price
        last_row = future_data.iloc[-1]
        exit_price = last_row['close']
        exit_roe = self.calculate_roe(entry_price, exit_price, direction)
        
        return TradeResult(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            entry_time=entry_idx,
            exit_time=entry_idx + len(future_data),
            profit_loss_pct=(exit_price - entry_price) / entry_price,
            profit_loss_roe=exit_roe,
            exit_reason='END_OF_DATA',
            holding_time_candles=len(future_data),
            confidence=confidence
        )
    
    def simulate_test_period(self, model, scaler, X_test, y_test, 
                            df_test, test_start_idx: int) -> dict:
        """
        Simulate trading on entire test period.
        
        Args:
            model: Trained XGBoost model
            scaler: Fitted scaler
            X_test: Test features
            y_test: Test labels (not used, only for reference)
            df_test: DataFrame with OHLCV data for test period
            test_start_idx: Starting index in original data
            
        Returns:
            dict with trading results and statistics
        """
        _LOG.info(f"🎮 Simulating trading on test period...")
        _LOG.info(f"   Test samples: {len(X_test)}")
        _LOG.info(f"   Test candles: {len(df_test)}")
        
        simulator = self
        trades = []
        
        # Scale features
        X_test_scaled = scaler.transform(X_test)
        
        # Get predictions
        y_pred = model.predict(X_test_scaled)
        y_proba = model.predict_proba(X_test_scaled)
        
        # Simulate trades
        for i in range(len(X_test)):
            predicted_class = y_pred[i]
            confidence = np.max(y_proba[i])
            
            # Map Triple Barrier labels: 0=NEUTRAL, 1=BUY, 2=SELL
            if predicted_class == 1 and confidence >= self.min_confidence:
                direction = 'BUY'
            elif predicted_class == 2 and confidence >= self.min_confidence:
                direction = 'SELL'
            else:
                continue  # Skip NEUTRAL or low confidence
            
            # Entry point
            # Use relative index for df_test (which is already sliced)
            entry_idx_relative = i
            if entry_idx_relative >= len(df_test):
                continue
                
            entry_row = df_test.iloc[entry_idx_relative]
            entry_price = entry_row['close']
            
            # Extract symbol if available, otherwise use generic name
            if 'symbol' in df_test.columns:
                symbol = entry_row['symbol']
            else:
                symbol = 'MIXED_SYMBOLS'  # Multiple symbols aggregated
            
            # Absolute index for tracking
            entry_idx_absolute = test_start_idx + i
            
            # Get future data for this trade (remaining candles)
            future_data = df_test.iloc[entry_idx_relative+1:]
            
            if len(future_data) < 1:
                continue  # Not enough data to simulate
            
            # Simulate trade
            trade_result = simulator.simulate_trade(
                symbol=symbol,
                direction=direction,
                entry_idx=entry_idx_absolute,  # Use absolute index for tracking
                entry_price=entry_price,
                future_data=future_data,
                confidence=confidence
            )
            
            trades.append(trade_result)
        
        # Calculate statistics
        return self._calculate_statistics(trades)
    
    def _calculate_statistics_per_symbol(self, trades: list[TradeResult]) -> dict:
        """Calculate statistics grouped by symbol"""
        
        if not trades:
            return {}
        
        # Group trades by symbol
        from collections import defaultdict
        symbol_trades = defaultdict(list)
        
        for trade in trades:
            symbol_trades[trade.symbol].append(trade)
        
        # Calculate stats for each symbol
        symbol_stats = {}
        for symbol, sym_trades in symbol_trades.items():
            winning = [t for t in sym_trades if t.profit_loss_roe > 0]
            losing = [t for t in sym_trades if t.profit_loss_roe <= 0]
            
            total_profit = sum(t.profit_loss_roe for t in winning)
            total_loss = abs(sum(t.profit_loss_roe for t in losing))
            
            symbol_stats[symbol] = {
                'total_trades': len(sym_trades),
                'winning_trades': len(winning),
                'losing_trades': len(losing),
                'win_rate': (len(winning) / len(sym_trades) * 100) if sym_trades else 0,
                'total_profit': total_profit * 100,
                'total_loss': total_loss * 100,
                'net_profit': (total_profit - total_loss) * 100,
                'profit_factor': (total_profit / total_loss) if total_loss > 0 else float('inf'),
                'avg_holding_time': np.mean([t.holding_time_candles for t in sym_trades])
            }
        
        return symbol_stats
    
    def _calculate_statistics(self, trades: list[TradeResult]) -> dict:
        """Calculate aggregate statistics from trades"""
        
        if not trades:
            _LOG.warning("⚠️ No trades executed in test period!")
            return {
                'trades': [],
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_profit': 0.0,
                'total_loss': 0.0,
                'net_profit': 0.0,
                'avg_profit': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'best_trade_roe': 0.0,
                'worst_trade_roe': 0.0,
                'avg_holding_time': 0.0,
                'exit_reasons': {},
                'per_symbol': {}
            }
        
        # Separate winning and losing trades
        winning_trades = [t for t in trades if t.profit_loss_roe > 0]
        losing_trades = [t for t in trades if t.profit_loss_roe <= 0]
        
        # Calculate metrics
        total_profit = sum(t.profit_loss_roe for t in winning_trades)
        total_loss = abs(sum(t.profit_loss_roe for t in losing_trades))
        net_profit = total_profit - total_loss
        
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Exit reasons
        exit_reasons = {}
        for trade in trades:
            reason = trade.exit_reason
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        results = {
            'trades': trades,
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(trades) * 100 if trades else 0,
            'total_profit': total_profit * 100,  # Convert to %
            'total_loss': total_loss * 100,
            'net_profit': net_profit * 100,
            'avg_profit': (total_profit / len(winning_trades) * 100) if winning_trades else 0,
            'avg_loss': (total_loss / len(losing_trades) * 100) if losing_trades else 0,
            'profit_factor': profit_factor,
            'best_trade_roe': max(t.profit_loss_roe for t in trades) * 100,
            'worst_trade_roe': min(t.profit_loss_roe for t in trades) * 100,
            'avg_holding_time': np.mean([t.holding_time_candles for t in trades]),
            'exit_reasons': exit_reasons,
            # Additional breakdown
            'buy_trades': len([t for t in trades if t.direction == 'BUY']),
            'sell_trades': len([t for t in trades if t.direction == 'SELL']),
            'buy_win_rate': (len([t for t in winning_trades if t.direction == 'BUY']) / 
                           len([t for t in trades if t.direction == 'BUY']) * 100
                           if [t for t in trades if t.direction == 'BUY'] else 0),
            'sell_win_rate': (len([t for t in winning_trades if t.direction == 'SELL']) / 
                            len([t for t in trades if t.direction == 'SELL']) * 100
                            if [t for t in trades if t.direction == 'SELL'] else 0),
            # ✅ Per-symbol breakdown (Opzione A)
            'per_symbol': self._calculate_statistics_per_symbol(trades)
        }
        
        # Log summary
        _LOG.info(f"📊 Trading Simulation Results:")
        _LOG.info(f"   Total Trades: {results['total_trades']}")
        _LOG.info(f"   Win Rate: {results['win_rate']:.1f}%")
        _LOG.info(f"   Net Profit: {results['net_profit']:.2f}% ROE")
        _LOG.info(f"   Profit Factor: {results['profit_factor']:.2f}")
        
        return results
