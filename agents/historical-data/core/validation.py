"""
🔍 Data Validation Module

Validates historical OHLCV data integrity:
- Gap detection
- Small gap interpolation
- Data quality reporting
- Anomaly detection
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import pandas as pd
import numpy as np
from termcolor import colored

import config

logger = logging.getLogger(__name__)


class GapStatus(Enum):
    """Status of a detected gap"""
    DETECTED = "DETECTED"
    FILLED = "FILLED"
    TOO_LARGE = "TOO_LARGE"


@dataclass
class GapInfo:
    """Information about a detected gap in the data"""
    start_time: datetime
    end_time: datetime
    expected_candles: int
    status: GapStatus
    
    @property
    def duration_minutes(self) -> int:
        """Get gap duration in minutes"""
        return int((self.end_time - self.start_time).total_seconds() / 60)


@dataclass
class ValidationResult:
    """Result of data validation"""
    is_valid: bool
    total_candles: int
    expected_candles: int
    missing_candles: int
    completeness_pct: float
    gaps: List[GapInfo]
    gap_count: int
    anomalies: List[Dict]
    anomaly_count: int
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    message: str


@dataclass
class QualityReport:
    """Comprehensive data quality report for a symbol/timeframe"""
    symbol: str
    timeframe: str
    validation: ValidationResult
    monthly_completeness: Dict[str, float]
    volume_stats: Dict
    ohlc_stats: Dict
    interpolated_count: int


def get_timeframe_minutes(timeframe: str) -> int:
    """Convert timeframe string to minutes"""
    if timeframe.endswith('m'):
        return int(timeframe[:-1])
    elif timeframe.endswith('h'):
        return int(timeframe[:-1]) * 60
    elif timeframe.endswith('d'):
        return int(timeframe[:-1]) * 60 * 24
    else:
        # Default to 15m
        return 15


class DataValidator:
    """
    Validates data integrity and fills small gaps.
    
    Key functions:
    - validate_no_gaps: Check for missing candles
    - fill_small_gaps: Interpolate gaps <= MAX_GAP_TO_FILL
    - get_quality_report: Comprehensive quality analysis
    """
    
    def __init__(self, max_gap_to_fill: int = None):
        self.max_gap_to_fill = max_gap_to_fill or config.MAX_GAP_TO_FILL
    
    def validate_no_gaps(
        self, 
        df: pd.DataFrame, 
        timeframe: str,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> ValidationResult:
        """
        Validate that there are no gaps in the data.
        
        Args:
            df: DataFrame with OHLCV data (datetime index)
            timeframe: Candle timeframe (e.g., '15m')
            start_date: Expected start date (optional)
            end_date: Expected end date (optional)
            
        Returns:
            ValidationResult with completeness and gap information
        """
        if df is None or df.empty:
            return ValidationResult(
                is_valid=False,
                total_candles=0,
                expected_candles=0,
                missing_candles=0,
                completeness_pct=0.0,
                gaps=[],
                gap_count=0,
                anomalies=[],
                anomaly_count=0,
                start_date=None,
                end_date=None,
                message="Empty or None DataFrame"
            )
        
        # Get timeframe interval
        interval_minutes = get_timeframe_minutes(timeframe)
        interval = timedelta(minutes=interval_minutes)
        
        # Ensure datetime index and sort
        if not isinstance(df.index, pd.DatetimeIndex):
            df = df.copy()
            df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        
        # Determine date range
        actual_start = df.index.min()
        actual_end = df.index.max()
        
        expected_start = start_date or actual_start
        expected_end = end_date or actual_end
        
        # Calculate expected number of candles
        total_duration = expected_end - expected_start
        expected_candles = int(total_duration.total_seconds() / (interval_minutes * 60)) + 1
        actual_candles = len(df)
        missing_candles = expected_candles - actual_candles
        
        # Find gaps
        gaps = self._find_gaps(df, interval)
        
        # Calculate completeness
        completeness = (actual_candles / expected_candles * 100) if expected_candles > 0 else 0.0
        
        # Find anomalies
        anomalies = self._find_anomalies(df)
        
        # Determine validity
        is_valid = completeness >= config.COMPLETENESS_THRESHOLD and len(anomalies) == 0
        
        if is_valid:
            message = f"Data valid: {completeness:.2f}% complete"
        else:
            issues = []
            if completeness < config.COMPLETENESS_THRESHOLD:
                issues.append(f"completeness {completeness:.2f}% < {config.COMPLETENESS_THRESHOLD}%")
            if len(anomalies) > 0:
                issues.append(f"{len(anomalies)} anomalies detected")
            message = f"Validation failed: {', '.join(issues)}"
        
        return ValidationResult(
            is_valid=is_valid,
            total_candles=actual_candles,
            expected_candles=expected_candles,
            missing_candles=max(0, missing_candles),
            completeness_pct=round(completeness, 2),
            gaps=gaps,
            gap_count=len(gaps),
            anomalies=anomalies,
            anomaly_count=len(anomalies),
            start_date=actual_start,
            end_date=actual_end,
            message=message
        )
    
    def _find_gaps(self, df: pd.DataFrame, interval: timedelta) -> List[GapInfo]:
        """Find all gaps in the data"""
        gaps = []
        
        if len(df) < 2:
            return gaps
        
        prev_time = df.index[0]
        for curr_time in df.index[1:]:
            # Check if gap exists
            time_diff = curr_time - prev_time
            expected_diff = interval
            
            if time_diff > expected_diff:
                # Gap detected
                gap_candles = int(time_diff / interval) - 1
                
                if gap_candles <= self.max_gap_to_fill:
                    status = GapStatus.DETECTED
                else:
                    status = GapStatus.TOO_LARGE
                
                gaps.append(GapInfo(
                    start_time=prev_time,
                    end_time=curr_time,
                    expected_candles=gap_candles,
                    status=status
                ))
            
            prev_time = curr_time
        
        return gaps
    
    def _find_anomalies(self, df: pd.DataFrame) -> List[Dict]:
        """Find anomalies in OHLCV data"""
        anomalies = []
        
        for idx, row in df.iterrows():
            # Check OHLC validity (high >= low, etc.)
            if row['high'] < row['low']:
                anomalies.append({
                    'timestamp': idx,
                    'type': 'INVALID_OHLC',
                    'message': f"High ({row['high']}) < Low ({row['low']})"
                })
            
            if row['open'] < 0 or row['close'] < 0:
                anomalies.append({
                    'timestamp': idx,
                    'type': 'NEGATIVE_PRICE',
                    'message': f"Negative price detected"
                })
            
            # Check for zero/negative volume (warning, not error)
            # Volume = 0 can be valid during low activity
            if row['volume'] < 0:
                anomalies.append({
                    'timestamp': idx,
                    'type': 'NEGATIVE_VOLUME',
                    'message': f"Negative volume: {row['volume']}"
                })
        
        return anomalies
    
    def fill_small_gaps(
        self, 
        df: pd.DataFrame, 
        timeframe: str
    ) -> Tuple[pd.DataFrame, List[GapInfo]]:
        """
        Fill small gaps (≤ max_gap_to_fill) using linear interpolation.
        
        Args:
            df: DataFrame with OHLCV data (datetime index)
            timeframe: Candle timeframe
            
        Returns:
            Tuple of (filled DataFrame, list of filled gaps)
        """
        if df is None or df.empty:
            return df, []
        
        # Ensure datetime index and sort
        if not isinstance(df.index, pd.DatetimeIndex):
            df = df.copy()
            df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        
        interval_minutes = get_timeframe_minutes(timeframe)
        interval = timedelta(minutes=interval_minutes)
        
        # Find gaps first
        gaps = self._find_gaps(df, interval)
        
        filled_gaps = []
        new_rows = []
        
        for gap in gaps:
            if gap.expected_candles <= self.max_gap_to_fill:
                # Get surrounding candles for interpolation
                try:
                    before = df.loc[gap.start_time]
                    after = df.loc[gap.end_time]
                except KeyError:
                    continue
                
                # Generate interpolated candles
                for i in range(1, gap.expected_candles + 1):
                    new_time = gap.start_time + interval * i
                    
                    # Linear interpolation factor
                    factor = i / (gap.expected_candles + 1)
                    
                    new_row = {
                        'open': before['open'] + (after['open'] - before['open']) * factor,
                        'high': before['high'] + (after['high'] - before['high']) * factor,
                        'low': before['low'] + (after['low'] - before['low']) * factor,
                        'close': before['close'] + (after['close'] - before['close']) * factor,
                        'volume': (before['volume'] + after['volume']) / 2,  # Average volume
                        'interpolated': 1 if 'interpolated' in df.columns else True
                    }
                    
                    new_rows.append((new_time, new_row))
                
                gap.status = GapStatus.FILLED
                filled_gaps.append(gap)
        
        # Add interpolated rows to dataframe
        if new_rows:
            df = df.copy()
            for timestamp, row_data in new_rows:
                for col, val in row_data.items():
                    if col in df.columns or col == 'interpolated':
                        if col not in df.columns:
                            df['interpolated'] = 0
                        df.loc[timestamp, col] = val
            
            df = df.sort_index()
        
        return df, filled_gaps
    
    def get_monthly_completeness(
        self, 
        df: pd.DataFrame, 
        timeframe: str
    ) -> Dict[str, float]:
        """
        Calculate completeness percentage for each month.
        
        Args:
            df: DataFrame with OHLCV data (datetime index)
            timeframe: Candle timeframe
            
        Returns:
            Dict mapping 'YYYY-MM' to completeness percentage
        """
        if df is None or df.empty:
            return {}
        
        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            df = df.copy()
            df.index = pd.to_datetime(df.index)
        
        interval_minutes = get_timeframe_minutes(timeframe)
        candles_per_day = 24 * 60 / interval_minutes
        
        result = {}
        
        # Group by month
        df['month'] = df.index.to_period('M')
        monthly_counts = df.groupby('month').size()
        
        for month, count in monthly_counts.items():
            # Expected candles for this month
            days_in_month = month.days_in_month
            expected = int(days_in_month * candles_per_day)
            
            # Handle partial months at start/end
            month_start = df[df['month'] == month].index.min()
            month_end = df[df['month'] == month].index.max()
            
            actual_duration = (month_end - month_start).total_seconds() / (interval_minutes * 60) + 1
            expected = min(expected, int(actual_duration))
            
            completeness = (count / expected * 100) if expected > 0 else 0
            result[str(month)] = round(min(completeness, 100), 2)
        
        # Remove helper column
        df.drop('month', axis=1, inplace=True, errors='ignore')
        
        return result
    
    def get_quality_report(
        self, 
        symbol: str,
        timeframe: str,
        df: pd.DataFrame
    ) -> QualityReport:
        """
        Generate comprehensive data quality report.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe
            df: DataFrame with OHLCV data
            
        Returns:
            QualityReport with all quality metrics
        """
        # Validate data
        validation = self.validate_no_gaps(df, timeframe)
        
        # Monthly completeness
        monthly = self.get_monthly_completeness(df, timeframe)
        
        # Volume stats
        volume_stats = {}
        if df is not None and not df.empty and 'volume' in df.columns:
            volume_stats = {
                'min': float(df['volume'].min()),
                'max': float(df['volume'].max()),
                'mean': float(df['volume'].mean()),
                'std': float(df['volume'].std()),
                'zero_count': int((df['volume'] == 0).sum()),
                'zero_pct': round((df['volume'] == 0).mean() * 100, 2)
            }
        
        # OHLC stats
        ohlc_stats = {}
        if df is not None and not df.empty:
            ohlc_stats = {
                'price_min': float(df['low'].min()),
                'price_max': float(df['high'].max()),
                'price_mean': float(df['close'].mean()),
                'price_std': float(df['close'].std()),
                'avg_range_pct': float(((df['high'] - df['low']) / df['close']).mean() * 100)
            }
        
        # Count interpolated candles
        interpolated_count = 0
        if df is not None and 'interpolated' in df.columns:
            interpolated_count = int(df['interpolated'].sum())
        
        return QualityReport(
            symbol=symbol,
            timeframe=timeframe,
            validation=validation,
            monthly_completeness=monthly,
            volume_stats=volume_stats,
            ohlc_stats=ohlc_stats,
            interpolated_count=interpolated_count
        )
    
    def print_quality_report(self, report: QualityReport):
        """Print a formatted quality report"""
        v = report.validation
        
        print(colored(f"\n{'='*60}", "cyan"))
        print(colored(f"📊 QUALITY REPORT: {report.symbol} [{report.timeframe}]", "cyan", attrs=['bold']))
        print(colored(f"{'='*60}", "cyan"))
        
        # Validation status
        status_icon = "✅" if v.is_valid else "❌"
        status_color = "green" if v.is_valid else "red"
        print(colored(f"\n  {status_icon} Status: {v.message}", status_color))
        
        # Basic stats
        print(colored(f"\n  📈 Candle Statistics:", "white", attrs=['bold']))
        print(colored(f"     Total candles: {v.total_candles:,}", "white"))
        print(colored(f"     Expected: {v.expected_candles:,}", "white"))
        print(colored(f"     Missing: {v.missing_candles:,}", "yellow" if v.missing_candles > 0 else "white"))
        print(colored(f"     Completeness: {v.completeness_pct}%", "green" if v.completeness_pct >= 99 else "yellow"))
        print(colored(f"     Interpolated: {report.interpolated_count:,}", "yellow" if report.interpolated_count > 0 else "white"))
        
        # Date range
        if v.start_date and v.end_date:
            print(colored(f"\n  📅 Date Range:", "white", attrs=['bold']))
            print(colored(f"     {v.start_date.strftime('%Y-%m-%d')} → {v.end_date.strftime('%Y-%m-%d')}", "white"))
        
        # Gaps
        if v.gaps:
            print(colored(f"\n  ⚠️ Gaps Detected: {len(v.gaps)}", "yellow", attrs=['bold']))
            for i, gap in enumerate(v.gaps[:5]):  # Show first 5
                status_str = "✅ Filled" if gap.status == GapStatus.FILLED else "❌ Too Large"
                print(colored(f"     {i+1}. {gap.start_time} → {gap.end_time} ({gap.expected_candles} candles) {status_str}", "yellow"))
            if len(v.gaps) > 5:
                print(colored(f"     ... and {len(v.gaps) - 5} more", "yellow"))
        
        # Volume stats
        if report.volume_stats:
            print(colored(f"\n  📊 Volume Statistics:", "white", attrs=['bold']))
            print(colored(f"     Mean: {report.volume_stats['mean']:,.0f}", "white"))
            print(colored(f"     Zero volume: {report.volume_stats['zero_pct']}% of candles", 
                         "yellow" if report.volume_stats['zero_pct'] > 10 else "white"))
        
        # Monthly completeness (sample)
        if report.monthly_completeness:
            print(colored(f"\n  📅 Monthly Completeness (sample):", "white", attrs=['bold']))
            months = list(report.monthly_completeness.items())
            for month, pct in months[:3] + months[-3:]:
                icon = "🟢" if pct >= 99 else "🟡" if pct >= 95 else "🔴"
                print(colored(f"     {icon} {month}: {pct}%", "white"))
        
        print(colored(f"\n{'='*60}\n", "cyan"))


def validate_and_fill_gaps(
    df: pd.DataFrame, 
    timeframe: str,
    max_gap: int = None
) -> Tuple[pd.DataFrame, ValidationResult]:
    """
    Convenience function to validate data and fill small gaps.
    
    Args:
        df: DataFrame with OHLCV data
        timeframe: Candle timeframe
        max_gap: Maximum gap size to fill (default from config)
        
    Returns:
        Tuple of (filled DataFrame, ValidationResult)
    """
    validator = DataValidator(max_gap_to_fill=max_gap)
    
    # Fill small gaps
    filled_df, filled_gaps = validator.fill_small_gaps(df, timeframe)
    
    # Validate the filled data
    result = validator.validate_no_gaps(filled_df, timeframe)
    
    return filled_df, result
