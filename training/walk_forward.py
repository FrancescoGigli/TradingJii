"""
Walk-Forward Testing Module

Implements Walk-Forward Analysis with:
- 3 rounds of training and testing
- Trading simulation on each test period
- Comprehensive reporting
- Final model trained on all data
"""

from __future__ import annotations

import logging
import joblib
import numpy as np
from pathlib import Path

import config
from training.xgb_trainer import train_xgb_model, create_temporal_split
from training_simulator import TradingSimulator
from training_report import generate_walk_forward_report, save_detailed_trades

_LOG = logging.getLogger(__name__)


def walk_forward_training(all_data_X, all_data_y, all_data_df, timeframe: str):
    """
    Perform Walk-Forward Testing with 3 rounds.
    
    Args:
        all_data_X: All features (90 days)
        all_data_y: All labels (90 days)
        all_data_df: DataFrame with OHLCV (for simulation)
        timeframe: Timeframe string (e.g., '15m')
        
    Returns:
        tuple: (final_model, final_scaler, report)
    """
    if not config.WALK_FORWARD_ENABLED:
        _LOG.warning("Walk-Forward Testing is disabled in config!")
        return None, None, None
    
    _LOG.info("="*80)
    _LOG.info(f"🔄 WALK-FORWARD TESTING - {timeframe}")
    _LOG.info("="*80)
    _LOG.info(f"Total data: {len(all_data_X)} samples")
    _LOG.info(f"Configuration: {config.WALK_FORWARD_ROUNDS} rounds, {config.WF_TEST_DAYS_PER_ROUND} days test per round")
    
    # Calculate split points (in samples, not days)
    # Assume roughly uniform sample distribution across days
    total_samples = len(all_data_X)
    samples_per_day = total_samples / config.DATA_LIMIT_DAYS
    
    # Round 1: Train on 63 days, test on 9 days (days 64-72)
    round_1_train_samples = int(config.WF_TRAIN_DAYS_ROUND_1 * samples_per_day)
    round_1_test_samples = int(config.WF_TEST_DAYS_PER_ROUND * samples_per_day)
    
    # Round 2: Train on 72 days, test on 9 days (days 73-81)
    round_2_train_samples = round_1_train_samples + round_1_test_samples
    round_2_test_samples = int(config.WF_TEST_DAYS_PER_ROUND * samples_per_day)
    
    # Round 3: Train on 81 days, test on 9 days (days 82-90)
    round_3_train_samples = round_2_train_samples + round_2_test_samples
    round_3_test_samples = total_samples - round_3_train_samples
    
    rounds_config = [
        {
            'round': 1,
            'train_end': round_1_train_samples,
            'test_end': round_1_train_samples + round_1_test_samples
        },
        {
            'round': 2,
            'train_end': round_2_train_samples,
            'test_end': round_2_train_samples + round_2_test_samples
        },
        {
            'round': 3,
            'train_end': round_3_train_samples,
            'test_end': round_3_train_samples + round_3_test_samples
        }
    ]
    
    # Initialize simulator
    simulator = TradingSimulator()
    
    # Store results for each round
    rounds_results = []
    
    # Execute each round
    for round_cfg in rounds_config:
        round_num = round_cfg['round']
        train_end = round_cfg['train_end']
        test_end = round_cfg['test_end']
        
        _LOG.info("\n" + "="*80)
        _LOG.info(f"🔄 ROUND {round_num}/{config.WALK_FORWARD_ROUNDS}")
        _LOG.info("="*80)
        
        # Split data for this round
        X_train_full = all_data_X[:train_end]
        y_train_full = all_data_y[:train_end]
        X_test = all_data_X[train_end:test_end]
        y_test = all_data_y[train_end:test_end]
        df_test = all_data_df.iloc[train_end:test_end]
        
        _LOG.info(f"Train samples: 0 to {train_end}")
        _LOG.info(f"Test samples: {train_end} to {test_end}")
        
        # Internal validation split (90/10)
        X_train, y_train, X_val, y_val = create_temporal_split(
            X_train_full, y_train_full, 
            train_pct=1 - config.WF_VALIDATION_PCT
        )
        
        # Train model
        _LOG.info(f"\n📚 Training model for Round {round_num}...")
        model, scaler, ml_metrics = train_xgb_model(X_train, y_train, X_val, y_val)
        
        # Simulate trading on test set
        _LOG.info(f"\n🎮 Simulating trading on test period...")
        test_results = simulator.simulate_test_period(
            model=model,
            scaler=scaler,
            X_test=X_test,
            y_test=y_test,
            df_test=df_test,
            test_start_idx=train_end
        )
        
        # Save detailed trades if enabled
        if config.WF_SAVE_DETAILED_TRADES and test_results['trades']:
            save_detailed_trades(test_results['trades'], timeframe, round_num)
        
        # Store results (remove trades list to save memory)
        test_results_summary = {k: v for k, v in test_results.items() if k != 'trades'}
        rounds_results.append(test_results_summary)
        
        _LOG.info(f"\n✅ Round {round_num} completed!")
        _LOG.info(f"   Win Rate: {test_results['win_rate']:.1f}%")
        _LOG.info(f"   Net Profit: {test_results['net_profit']:.2f}% ROE")
        _LOG.info(f"   Profit Factor: {test_results['profit_factor']:.2f}")
    
    # Generate aggregate report
    _LOG.info("\n" + "="*80)
    _LOG.info("📊 GENERATING AGGREGATE REPORT")
    _LOG.info("="*80)
    
    # Use metrics from last round as representative
    ml_metrics_final = ml_metrics if 'ml_metrics' in locals() else {}
    
    report = generate_walk_forward_report(
        rounds_results=rounds_results,
        ml_metrics=ml_metrics_final,
        timeframe=timeframe
    )
    
    # Train final model on ALL 90 days for production
    _LOG.info("\n" + "="*80)
    _LOG.info("🏁 TRAINING FINAL MODEL (All 90 days)")
    _LOG.info("="*80)
    
    X_train_final, y_train_final, X_val_final, y_val_final = create_temporal_split(
        all_data_X, all_data_y,
        train_pct=0.90
    )
    
    final_model, final_scaler, final_metrics = train_xgb_model(
        X_train_final, y_train_final,
        X_val_final, y_val_final
    )
    
    # Save final model
    _LOG.info("\n💾 Saving final model...")
    trained_dir = Path(config.get_xgb_model_file(timeframe)).parent
    trained_dir.mkdir(exist_ok=True)
    
    joblib.dump(final_model, config.get_xgb_model_file(timeframe))
    joblib.dump(final_scaler, config.get_xgb_scaler_file(timeframe))
    
    _LOG.info(f"✅ Model saved: {config.get_xgb_model_file(timeframe)}")
    _LOG.info(f"✅ Scaler saved: {config.get_xgb_scaler_file(timeframe)}")
    
    _LOG.info("\n" + "="*80)
    _LOG.info("🎉 WALK-FORWARD TESTING COMPLETED!")
    _LOG.info("="*80)
    
    return final_model, final_scaler, report
