"""
⚙️ Training Configuration

Feature columns, XGBoost parameters, and paths.
"""

from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DB_PATH = PROJECT_ROOT / "shared" / "data_cache" / "trading_data.db"
MODEL_OUTPUT_DIR = PROJECT_ROOT / "shared" / "models"

TRAIN_RATIO = 0.8
TARGET_LONG = 'score_long'
TARGET_SHORT = 'score_short'

FEATURE_COLUMNS = [
    'open', 'high', 'low', 'close', 'volume',
    'sma_20', 'sma_50', 'ema_12', 'ema_26',
    'bb_upper', 'bb_mid', 'bb_lower', 'bb_width', 'bb_position',
    'rsi', 'macd', 'macd_signal', 'macd_hist', 'stoch_k', 'stoch_d',
    'atr', 'atr_pct', 'obv', 'volume_sma', 'adx_14', 'adx_14_norm',
    'ret_5', 'ret_10', 'ret_20',
    'ema_20_dist', 'ema_50_dist', 'ema_200_dist',
    'ema_20_50_cross', 'ema_50_200_cross',
    'rsi_14_norm', 'macd_hist_norm',
    'trend_direction', 'momentum_10', 'momentum_20',
    'vol_5', 'vol_10', 'vol_20',
    'range_pct_5', 'range_pct_10', 'range_pct_20',
    'vol_percentile', 'vol_ratio', 'vol_change', 'obv_slope',
    'vwap_dist', 'vol_stability',
    'body_pct', 'candle_direction', 'upper_shadow_pct', 'lower_shadow_pct',
    'gap_pct', 'consecutive_up', 'consecutive_down',
    'speed_5', 'speed_20', 'accel_5', 'accel_20',
    'ret_percentile_50', 'ret_percentile_100',
    'price_position_20', 'price_position_50', 'price_position_100',
    'dist_from_high_20', 'dist_from_low_20',
]

EXCLUDE_COLUMNS = [
    'score_long', 'score_short', 'realized_return_long', 'realized_return_short',
    'mfe_long', 'mae_long', 'mfe_short', 'mae_short',
    'bars_held_long', 'bars_held_short', 'exit_type_long', 'exit_type_short',
    'trailing_stop_pct', 'max_bars', 'time_penalty_lambda', 'trading_cost',
    'generated_at', 'id', 'timestamp', 'symbol', 'timeframe',
]

XGBOOST_PARAMS = {
    'objective': 'reg:squarederror', 'eval_metric': 'rmse', 'tree_method': 'hist',
    'max_depth': 6, 'learning_rate': 0.05, 'colsample_bytree': 0.8,
    'subsample': 0.8, 'min_child_weight': 10, 'n_estimators': 500,
    'early_stopping_rounds': 50, 'verbosity': 1, 'random_state': 42,
}
