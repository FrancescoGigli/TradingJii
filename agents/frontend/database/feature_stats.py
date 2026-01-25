"""
📊 Feature Statistics Module

Provides functions to get feature counts from database tables and views
for display in the ML training pipeline UI.
"""

from typing import Dict, List, Tuple, Optional
from .connection import get_connection


# Expected feature columns for XGBoost training
EXPECTED_FEATURES = [
    # OHLCV (5)
    'open', 'high', 'low', 'close', 'volume',
    # Moving Averages (4)
    'sma_20', 'sma_50', 'ema_12', 'ema_26',
    # Bollinger Bands (3)
    'bb_upper', 'bb_middle', 'bb_lower',
    # Momentum (4)
    'rsi', 'macd', 'macd_signal', 'macd_hist',
    # Stochastic (2)
    'stoch_k', 'stoch_d',
    # Other (3)
    'atr', 'volume_sma', 'obv'
]

EXPECTED_FEATURE_COUNT = len(EXPECTED_FEATURES)  # 21


def get_table_columns(table_name: str) -> List[str]:
    """Get column names from a table or view."""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def get_training_data_stats() -> Dict:
    """
    Get statistics from training_data table (Phase 1).
    Returns feature count and list of available features.
    """
    conn = get_connection()
    if not conn:
        return {'exists': False, 'error': 'No connection'}
    
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_data'")
        if not cur.fetchone():
            return {'exists': False, 'error': 'Table training_data not found'}
        
        # Get columns
        cur.execute("PRAGMA table_info(training_data)")
        all_cols = [row[1] for row in cur.fetchall()]
        
        # Exclude metadata columns
        exclude = {'id', 'symbol', 'timeframe', 'timestamp', 'fetched_at', 'interpolated'}
        feature_cols = [c for c in all_cols if c not in exclude]
        
        # Count rows
        cur.execute("SELECT COUNT(*) FROM training_data")
        row_count = cur.fetchone()[0]
        
        # Count symbols
        cur.execute("SELECT COUNT(DISTINCT symbol) FROM training_data")
        symbol_count = cur.fetchone()[0]
        
        return {
            'exists': True,
            'table_name': 'training_data',
            'total_columns': len(all_cols),
            'feature_count': len(feature_cols),
            'feature_columns': feature_cols,
            'row_count': row_count,
            'symbol_count': symbol_count,
            'expected_features': EXPECTED_FEATURE_COUNT,
            'is_complete': len(feature_cols) >= EXPECTED_FEATURE_COUNT - 5  # Allow some margin
        }
    except Exception as e:
        return {'exists': False, 'error': str(e)}
    finally:
        conn.close()


def get_training_labels_stats() -> Dict:
    """
    Get statistics from training_labels table (Phase 2).
    Labels table doesn't have features, only label columns.
    """
    conn = get_connection()
    if not conn:
        return {'exists': False, 'error': 'No connection'}
    
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_labels'")
        if not cur.fetchone():
            return {'exists': False, 'error': 'Table training_labels not found'}
        
        # Get columns
        cur.execute("PRAGMA table_info(training_labels)")
        all_cols = [row[1] for row in cur.fetchall()]
        
        # Label columns
        label_cols = [c for c in all_cols if 'score' in c or 'return' in c or 
                     'mfe' in c or 'mae' in c or 'bars_held' in c or 'exit_type' in c]
        
        # Count rows
        cur.execute("SELECT COUNT(*) FROM training_labels")
        row_count = cur.fetchone()[0]
        
        # Count symbols
        cur.execute("SELECT COUNT(DISTINCT symbol) FROM training_labels")
        symbol_count = cur.fetchone()[0]
        
        return {
            'exists': True,
            'table_name': 'training_labels',
            'total_columns': len(all_cols),
            'label_columns': label_cols,
            'label_count': len(label_cols),
            'row_count': row_count,
            'symbol_count': symbol_count
        }
    except Exception as e:
        return {'exists': False, 'error': str(e)}
    finally:
        conn.close()


def get_xgb_view_stats() -> Dict:
    """
    Get statistics from v_xgb_training view (Phase 3).
    This view joins training_data + training_labels.
    """
    conn = get_connection()
    if not conn:
        return {'exists': False, 'error': 'No connection'}
    
    try:
        cur = conn.cursor()
        
        # Check if view exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='v_xgb_training'")
        if not cur.fetchone():
            return {'exists': False, 'error': 'View v_xgb_training not found'}
        
        # Get columns
        cur.execute("PRAGMA table_info(v_xgb_training)")
        all_cols = [row[1] for row in cur.fetchall()]
        
        # Separate features vs labels vs metadata
        metadata = {'symbol', 'timeframe', 'timestamp'}
        label_cols = {c for c in all_cols if 'score' in c or 'return' in c or 
                     'mfe' in c or 'mae' in c or 'bars_held' in c or 'exit_type' in c or 'atr_pct' in c}
        
        feature_cols = [c for c in all_cols if c not in metadata and c not in label_cols]
        
        # Check which expected features are available
        available_features = []
        missing_features = []
        for f in EXPECTED_FEATURES:
            if f in feature_cols:
                available_features.append(f)
            else:
                missing_features.append(f)
        
        # Count rows (might be slow for large views)
        try:
            cur.execute("SELECT COUNT(*) FROM v_xgb_training LIMIT 1")
            row_count = cur.fetchone()[0]
        except Exception:
            row_count = -1
        
        return {
            'exists': True,
            'view_name': 'v_xgb_training',
            'total_columns': len(all_cols),
            'feature_count': len(feature_cols),
            'feature_columns': feature_cols,
            'label_columns': list(label_cols),
            'row_count': row_count,
            'expected_features': EXPECTED_FEATURE_COUNT,
            'available_features': available_features,
            'missing_features': missing_features,
            'is_complete': len(missing_features) == 0
        }
    except Exception as e:
        return {'exists': False, 'error': str(e)}
    finally:
        conn.close()


def get_pipeline_feature_summary() -> Dict:
    """
    Get a complete summary of feature availability across all pipeline stages.
    Useful for debugging and UI display.
    """
    training_data = get_training_data_stats()
    training_labels = get_training_labels_stats()
    xgb_view = get_xgb_view_stats()
    
    return {
        'phase1_data': training_data,
        'phase2_labels': training_labels,
        'phase3_view': xgb_view,
        'ready_for_training': (
            training_data.get('exists', False) and 
            training_labels.get('exists', False) and 
            xgb_view.get('exists', False) and
            xgb_view.get('feature_count', 0) >= 15  # At least 15 features
        )
    }


def format_feature_reminder(stats: Dict, phase: str) -> str:
    """Format a feature reminder message for UI display."""
    if not stats.get('exists', False):
        return f"⚠️ {phase}: Not available - {stats.get('error', 'Unknown error')}"
    
    if 'feature_count' in stats:
        count = stats['feature_count']
        expected = stats.get('expected_features', EXPECTED_FEATURE_COUNT)
        status = "✅" if count >= expected - 5 else "⚠️"
        return f"{status} {phase}: **{count}** features ({stats.get('table_name', stats.get('view_name', 'unknown'))})"
    elif 'label_count' in stats:
        return f"✅ {phase}: **{stats['label_count']}** label columns ({stats.get('table_name', 'unknown')})"
    
    return f"ℹ️ {phase}: Available"


__all__ = [
    'EXPECTED_FEATURES',
    'EXPECTED_FEATURE_COUNT',
    'get_table_columns',
    'get_training_data_stats',
    'get_training_labels_stats',
    'get_xgb_view_stats',
    'get_pipeline_feature_summary',
    'format_feature_reminder'
]
