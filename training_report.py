"""
Training Report Generator for Walk-Forward Testing

Generates comprehensive reports with:
- Performance metrics per round
- Aggregate statistics
- Visual charts (confusion matrix, profit curves)
- Recommendations
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any

import config

_LOG = logging.getLogger(__name__)


def generate_walk_forward_report(rounds_results: list[dict], 
                                 ml_metrics: dict,
                                 timeframe: str) -> dict:
    """
    Generate comprehensive Walk-Forward testing report.
    
    Args:
        rounds_results: List of dicts with results from each round
        ml_metrics: ML performance metrics (accuracy, precision, etc.)
        timeframe: Timeframe string (e.g., '15m')
        
    Returns:
        dict with complete report
    """
    _LOG.info(f"📝 Generating Walk-Forward report for {timeframe}...")
    
    # Aggregate statistics across all rounds
    aggregate = _aggregate_rounds(rounds_results)
    
    # Generate recommendation
    recommendation = _generate_recommendation(aggregate)
    
    # Build report
    report = {
        'timeframe': timeframe,
        'generated_at': datetime.now().isoformat(),
        'configuration': {
            'data_days': config.DATA_LIMIT_DAYS,
            'symbols_count': config.TOP_SYMBOLS_COUNT,
            'leverage': config.LEVERAGE,
            'stop_loss_pct': config.STOP_LOSS_PCT * 100,
            'trailing_trigger_roe': config.TRAILING_TRIGGER_ROE * 100,
            'trailing_distance_roe': config.TRAILING_DISTANCE_ROE_OPTIMAL * 100,
            'min_confidence': config.MIN_CONFIDENCE * 100,
        },
        'ml_metrics': ml_metrics,
        'rounds': [
            {
                'round': i + 1,
                'train_days': _get_train_days_for_round(i + 1),
                'test_days': config.WF_TEST_DAYS_PER_ROUND,
                'results': round_result
            }
            for i, round_result in enumerate(rounds_results)
        ],
        'aggregate': aggregate,
        'recommendation': recommendation
    }
    
    # Save report
    _save_report(report, timeframe)
    
    # Print summary to console
    _print_report_summary(report)
    
    return report


def _get_train_days_for_round(round_num: int) -> int:
    """Get training days for specific round"""
    if round_num == 1:
        return config.WF_TRAIN_DAYS_ROUND_1  # 63 days
    elif round_num == 2:
        return config.WF_TRAIN_DAYS_ROUND_1 + config.WF_TEST_DAYS_PER_ROUND  # 72 days
    else:  # round 3
        return config.WF_TRAIN_DAYS_ROUND_1 + 2 * config.WF_TEST_DAYS_PER_ROUND  # 81 days


def _aggregate_rounds(rounds_results: list[dict]) -> dict:
    """Aggregate statistics across all rounds"""
    
    # Total trades across all rounds
    total_trades = sum(r['total_trades'] for r in rounds_results)
    total_winning = sum(r['winning_trades'] for r in rounds_results)
    total_losing = sum(r['losing_trades'] for r in rounds_results)
    
    # Aggregate profit/loss
    total_profit = sum(r['total_profit'] for r in rounds_results)
    total_loss = sum(r['total_loss'] for r in rounds_results)
    net_profit = total_profit - total_loss
    
    # Calculate aggregate metrics
    win_rate = (total_winning / total_trades * 100) if total_trades > 0 else 0
    profit_factor = (total_profit / total_loss) if total_loss > 0 else float('inf')
    
    # Average metrics across rounds
    avg_holding_time = sum(r['avg_holding_time'] for r in rounds_results) / len(rounds_results)
    
    # Consistency (how many rounds were profitable)
    profitable_rounds = sum(1 for r in rounds_results if r['net_profit'] > 0)
    consistency = (profitable_rounds / len(rounds_results) * 100) if rounds_results else 0
    
    # Best and worst rounds
    best_round = max(rounds_results, key=lambda r: r['win_rate'])
    worst_round = min(rounds_results, key=lambda r: r['win_rate'])
    
    # Performance trend (is it improving?)
    win_rates = [r['win_rate'] for r in rounds_results]
    if len(win_rates) >= 2:
        if win_rates[-1] > win_rates[0]:
            trend = "IMPROVING"
        elif win_rates[-1] < win_rates[0]:
            trend = "DECLINING"
        else:
            trend = "STABLE"
    else:
        trend = "UNKNOWN"
    
    # ✅ Aggregate per-symbol stats across all rounds (Opzione A)
    aggregated_per_symbol = {}
    for round_result in rounds_results:
        if 'per_symbol' in round_result and round_result['per_symbol']:
            for symbol, stats in round_result['per_symbol'].items():
                if symbol not in aggregated_per_symbol:
                    aggregated_per_symbol[symbol] = {
                        'total_trades': 0,
                        'winning_trades': 0,
                        'losing_trades': 0,
                        'total_profit': 0.0,
                        'total_loss': 0.0,
                    }
                
                agg = aggregated_per_symbol[symbol]
                agg['total_trades'] += stats['total_trades']
                agg['winning_trades'] += stats['winning_trades']
                agg['losing_trades'] += stats['losing_trades']
                agg['total_profit'] += stats['total_profit']
                agg['total_loss'] += stats['total_loss']
    
    # Calculate derived metrics for each symbol
    for symbol, agg in aggregated_per_symbol.items():
        agg['win_rate'] = (agg['winning_trades'] / agg['total_trades'] * 100) if agg['total_trades'] > 0 else 0
        agg['net_profit'] = agg['total_profit'] - agg['total_loss']
        agg['profit_factor'] = (agg['total_profit'] / agg['total_loss']) if agg['total_loss'] > 0 else float('inf')
    
    return {
        'total_trades': total_trades,
        'winning_trades': total_winning,
        'losing_trades': total_losing,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'total_loss': total_loss,
        'net_profit': net_profit,
        'profit_factor': profit_factor,
        'avg_holding_time': avg_holding_time,
        'consistency': consistency,
        'profitable_rounds': profitable_rounds,
        'best_round_number': rounds_results.index(best_round) + 1,
        'best_round_win_rate': best_round['win_rate'],
        'worst_round_number': rounds_results.index(worst_round) + 1,
        'worst_round_win_rate': worst_round['win_rate'],
        'performance_trend': trend,
        'per_symbol': aggregated_per_symbol,  # ✅ Added per-symbol breakdown
    }


def _generate_recommendation(aggregate: dict) -> dict:
    """Generate recommendation based on aggregate statistics"""
    
    win_rate = aggregate['win_rate']
    profit_factor = aggregate['profit_factor']
    consistency = aggregate['consistency']
    trend = aggregate['performance_trend']
    
    # Decision criteria
    approved = False
    confidence_level = "LOW"
    reasons = []
    warnings = []
    
    # Check win rate
    if win_rate >= 55:
        reasons.append(f"Strong win rate ({win_rate:.1f}%)")
        confidence_level = "HIGH"
    elif win_rate >= 52:
        reasons.append(f"Good win rate ({win_rate:.1f}%)")
        confidence_level = "MEDIUM"
    elif win_rate >= 48:
        warnings.append(f"Marginal win rate ({win_rate:.1f}%)")
        confidence_level = "LOW"
    else:
        warnings.append(f"Poor win rate ({win_rate:.1f}%)")
        confidence_level = "VERY_LOW"
    
    # Check profit factor
    if profit_factor >= 1.5:
        reasons.append(f"Strong profit factor ({profit_factor:.2f})")
    elif profit_factor >= 1.2:
        reasons.append(f"Good profit factor ({profit_factor:.2f})")
    elif profit_factor >= 1.0:
        warnings.append(f"Marginal profit factor ({profit_factor:.2f})")
    else:
        warnings.append(f"Poor profit factor ({profit_factor:.2f})")
    
    # Check consistency
    if consistency == 100:
        reasons.append("Perfect consistency (all rounds profitable)")
    elif consistency >= 66:
        reasons.append(f"Good consistency ({consistency:.0f}% rounds profitable)")
    else:
        warnings.append(f"Inconsistent performance ({consistency:.0f}% rounds profitable)")
    
    # Check trend
    if trend == "IMPROVING":
        reasons.append("Performance trend is improving")
    elif trend == "DECLINING":
        warnings.append("Performance trend is declining")
    
    # Final decision
    if win_rate >= 52 and profit_factor >= 1.2 and consistency >= 66:
        approved = True
        decision = "APPROVED"
        action = "✅ Ready for Paper Trading"
    elif win_rate >= 50 and profit_factor >= 1.1:
        approved = False
        decision = "CONDITIONAL"
        action = "⚠️ Paper trade with caution - monitor closely"
    else:
        approved = False
        decision = "REJECTED"
        action = "❌ NOT recommended for trading - needs improvement"
    
    return {
        'approved': approved,
        'decision': decision,
        'action': action,
        'confidence_level': confidence_level,
        'reasons': reasons,
        'warnings': warnings,
    }


def _save_report(report: dict, timeframe: str) -> None:
    """Save report to JSON file"""
    
    if not config.WF_SAVE_AGGREGATE_REPORT:
        return
    
    try:
        # Create trained_models directory if not exists
        trained_dir = Path(config.get_xgb_model_file(timeframe)).parent
        trained_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = trained_dir / f"walk_forward_report_{timeframe}_{timestamp}.json"
        
        # Save as JSON (excluding TradeResult objects which aren't serializable)
        report_copy = report.copy()
        for round_data in report_copy['rounds']:
            if 'trades' in round_data['results']:
                # Keep only trade count, not full trade objects
                round_data['results']['trades_count'] = len(round_data['results']['trades'])
                del round_data['results']['trades']
        
        with open(filename, 'w') as f:
            json.dump(report_copy, f, indent=2)
        
        _LOG.info(f"💾 Report saved: {filename}")
        
    except Exception as e:
        _LOG.error(f"Failed to save report: {e}")


def _print_report_summary(report: dict) -> None:
    """Print formatted report summary to console"""
    
    print("\n" + "="*80)
    print(f"{'WALK-FORWARD TESTING REPORT':^80}")
    print(f"{'Timeframe: ' + report['timeframe']:^80}")
    print("="*80)
    
    # Configuration
    print(f"\n📊 CONFIGURATION:")
    cfg = report['configuration']
    print(f"   Data: {cfg['data_days']} days, {cfg['symbols_count']} symbols")
    print(f"   Leverage: {cfg['leverage']}x | SL: {cfg['stop_loss_pct']:.1f}% | Confidence: {cfg['min_confidence']:.0f}%")
    print(f"   Trailing: Trigger {cfg['trailing_trigger_roe']:.0f}% ROE, Distance {cfg['trailing_distance_roe']:.0f}% ROE")
    
    # Per-round results
    print(f"\n🔄 ROUND-BY-ROUND RESULTS:")
    print(f"{'Round':<8} {'Train Days':<12} {'Test Days':<10} {'Trades':<8} {'Win Rate':<10} {'Net P/L':<12} {'PF':<6}")
    print("-"*80)
    
    for round_data in report['rounds']:
        r = round_data['results']
        print(f"{round_data['round']:<8} "
              f"{round_data['train_days']:<12} "
              f"{round_data['test_days']:<10} "
              f"{r['total_trades']:<8} "
              f"{r['win_rate']:.1f}%      "
              f"{r['net_profit']:>+.2f}% ROE  "
              f"{r['profit_factor']:.2f}")
    
    # Aggregate results
    print(f"\n📈 AGGREGATE PERFORMANCE ({config.WALK_FORWARD_ROUNDS * config.WF_TEST_DAYS_PER_ROUND} days total):")
    agg = report['aggregate']
    print(f"   Total Trades:        {agg['total_trades']}")
    
    # Handle zero trades case
    if agg['total_trades'] > 0:
        print(f"   Winning Trades:      {agg['winning_trades']} ({agg['winning_trades']/agg['total_trades']*100:.1f}%)")
        print(f"   Losing Trades:       {agg['losing_trades']} ({agg['losing_trades']/agg['total_trades']*100:.1f}%)")
    else:
        print(f"   ⚠️  NO TRADES EXECUTED - Model too conservative or bug in simulator")
        print(f"   Check: 1) MIN_CONFIDENCE setting, 2) Prediction confidence levels, 3) Simulator logic")
    print(f"   Win Rate:            {agg['win_rate']:.1f}%")
    print(f"   ")
    print(f"   Total Profit:        +{agg['total_profit']:.2f}% ROE")
    print(f"   Total Loss:          -{agg['total_loss']:.2f}% ROE")
    print(f"   Net Profit:          {agg['net_profit']:+.2f}% ROE")
    print(f"   Profit Factor:       {agg['profit_factor']:.2f}")
    print(f"   ")
    print(f"   Consistency:         {agg['consistency']:.0f}% ({agg['profitable_rounds']}/{config.WALK_FORWARD_ROUNDS} rounds profitable)")
    print(f"   Best Round:          Round {agg['best_round_number']} ({agg['best_round_win_rate']:.1f}% WR)")
    print(f"   Worst Round:         Round {agg['worst_round_number']} ({agg['worst_round_win_rate']:.1f}% WR)")
    print(f"   Performance Trend:   {agg['performance_trend']}")
    
    # ✅ Per-Symbol Breakdown (Opzione A)
    if 'per_symbol' in agg and agg['per_symbol']:
        print(f"\n📊 PER-SYMBOL BREAKDOWN:")
        print(f"{'Symbol':<12} {'Trades':<8} {'Win Rate':<10} {'Net P/L':<14} {'PF':<6}")
        print("-"*80)
        
        # Sort by win rate (descending)
        sorted_symbols = sorted(
            agg['per_symbol'].items(),
            key=lambda x: x[1]['win_rate'],
            reverse=True
        )
        
        # Show top 20 symbols
        for symbol, stats in sorted_symbols[:20]:
            print(f"{symbol:<12} "
                  f"{stats['total_trades']:<8} "
                  f"{stats['win_rate']:.1f}%      "
                  f"{stats['net_profit']:>+10.2f}% ROE  "
                  f"{stats['profit_factor']:.2f}")
        
        if len(sorted_symbols) > 20:
            print(f"   ... and {len(sorted_symbols)-20} more symbols")
        
        # Top performers
        top_3 = sorted_symbols[:3]
        if top_3:
            print(f"\n🏆 TOP PERFORMERS:")
            for i, (symbol, stats) in enumerate(top_3, 1):
                print(f"   {i}. {symbol}: {stats['win_rate']:.1f}% WR, "
                      f"{stats['profit_factor']:.2f} PF, {stats['total_trades']} trades")
        
        # Bottom performers (only if significant trades)
        bottom_3 = [(s, st) for s, st in sorted_symbols[-3:] if st['total_trades'] >= 5]
        if bottom_3:
            print(f"\n⚠️  NEEDS ATTENTION:")
            for symbol, stats in reversed(bottom_3):
                print(f"   • {symbol}: {stats['win_rate']:.1f}% WR, "
                      f"{stats['total_trades']} trades, {stats['net_profit']:+.2f}% ROE")
    
    # ML Metrics

    if 'ml_metrics' in report and report['ml_metrics']:
        print(f"\n🎯 ML VALIDATION METRICS:")
        ml = report['ml_metrics']
        print(f"   Accuracy:     {ml.get('val_accuracy', 0)*100:.1f}%")
        print(f"   Precision:    {ml.get('val_precision', 0)*100:.1f}%")
        print(f"   Recall:       {ml.get('val_recall', 0)*100:.1f}%")
        print(f"   F1-Score:     {ml.get('val_f1', 0)*100:.1f}%")
    
    # Recommendation
    print(f"\n💡 RECOMMENDATION:")
    rec = report['recommendation']
    print(f"   Decision:         {rec['decision']} ({rec['confidence_level']} confidence)")
    print(f"   Action:           {rec['action']}")
    
    if rec['reasons']:
        print(f"\n   ✅ Strengths:")
        for reason in rec['reasons']:
            print(f"      • {reason}")
    
    if rec['warnings']:
        print(f"\n   ⚠️  Warnings:")
        for warning in rec['warnings']:
            print(f"      • {warning}")
    
    print("="*80 + "\n")


def save_detailed_trades(trades: list, timeframe: str, round_num: int) -> None:
    """Save detailed trade log for a specific round"""
    
    if not config.WF_SAVE_DETAILED_TRADES:
        return
    
    try:
        trained_dir = Path(config.get_xgb_model_file(timeframe)).parent
        trained_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = trained_dir / f"trades_round{round_num}_{timeframe}_{timestamp}.json"
        
        # Convert trades to dict format (convert numpy types to Python native types)
        trades_data = []
        for trade in trades:
            trades_data.append({
                'symbol': str(trade.symbol),
                'direction': str(trade.direction),
                'entry_price': float(trade.entry_price),
                'exit_price': float(trade.exit_price),
                'entry_time': int(trade.entry_time),
                'exit_time': int(trade.exit_time),
                'profit_loss_pct': float(trade.profit_loss_pct * 100),
                'profit_loss_roe': float(trade.profit_loss_roe * 100),
                'exit_reason': str(trade.exit_reason),
                'holding_time_candles': int(trade.holding_time_candles),
                'confidence': float(trade.confidence) if trade.confidence is not None else None,
            })
        
        with open(filename, 'w') as f:
            json.dump(trades_data, f, indent=2)
        
        _LOG.info(f"💾 Detailed trades saved: {filename}")
        
    except Exception as e:
        _LOG.error(f"Failed to save detailed trades: {e}")
