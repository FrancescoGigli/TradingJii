"""
Database Explorer functions
"""

import pandas as pd
from .connection import get_connection


def execute_custom_query(query: str, limit: int = 1000):
    """
    Execute a custom SQL query on the database.
    
    Args:
        query: SQL query string (SELECT only for safety)
        limit: Maximum rows to return (default 1000)
    
    Returns:
        Tuple of (DataFrame with results, error_message or None)
    """
    conn = get_connection()
    if not conn:
        return pd.DataFrame(), "Database connection failed"
    
    try:
        # Security check: only allow SELECT queries
        query_lower = query.strip().lower()
        if not query_lower.startswith('select'):
            return pd.DataFrame(), "Only SELECT queries are allowed for security"
        
        # Check for dangerous keywords
        dangerous_keywords = ['delete', 'drop', 'insert', 'update', 'alter', 'create', 'truncate']
        for keyword in dangerous_keywords:
            if keyword in query_lower:
                return pd.DataFrame(), f"Query contains forbidden keyword: {keyword.upper()}"
        
        # Add LIMIT if not present
        if 'limit' not in query_lower:
            query = f"{query.rstrip(';')} LIMIT {limit}"
        
        # Execute query
        df = pd.read_sql_query(query, conn)
        return df, None
        
    except Exception as e:
        return pd.DataFrame(), str(e)
    finally:
        conn.close()


# Predefined SQL queries for Database Explorer
ML_LABELS_EXAMPLE_QUERIES = {
    "📊 All Labels Summary": """
SELECT 
    symbol,
    timeframe,
    COUNT(*) as total_labels,
    ROUND(AVG(score_long), 5) as avg_score_long,
    ROUND(AVG(score_short), 5) as avg_score_short,
    ROUND(SUM(CASE WHEN score_long > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as pct_positive_long,
    MIN(timestamp) as from_date,
    MAX(timestamp) as to_date
FROM ml_training_labels
GROUP BY symbol, timeframe
ORDER BY symbol, timeframe
""",
    
    "🏆 Top 20 LONG Scores": """
SELECT 
    timestamp, 
    symbol, 
    timeframe,
    ROUND(score_long * 100, 3) as score_pct,
    ROUND(realized_return_long * 100, 3) as return_pct,
    ROUND(mfe_long * 100, 3) as mfe_pct,
    bars_held_long,
    exit_type_long
FROM ml_training_labels
WHERE score_long IS NOT NULL
ORDER BY score_long DESC
LIMIT 20
""",
    
    "📉 Top 20 SHORT Scores": """
SELECT 
    timestamp, 
    symbol, 
    timeframe,
    ROUND(score_short * 100, 3) as score_pct,
    ROUND(realized_return_short * 100, 3) as return_pct,
    ROUND(mfe_short * 100, 3) as mfe_pct,
    bars_held_short,
    exit_type_short
FROM ml_training_labels
WHERE score_short IS NOT NULL
ORDER BY score_short DESC
LIMIT 20
""",
    
    "🚪 Exit Type Distribution": """
SELECT 
    symbol,
    timeframe,
    exit_type_long,
    COUNT(*) as count,
    ROUND(AVG(realized_return_long) * 100, 3) as avg_return_pct,
    ROUND(AVG(score_long) * 100, 3) as avg_score_pct
FROM ml_training_labels
WHERE exit_type_long IS NOT NULL
GROUP BY symbol, timeframe, exit_type_long
ORDER BY symbol, timeframe, exit_type_long
""",
    
    "⚠️ High MFE but Low Score (Missed Opportunities)": """
SELECT 
    timestamp,
    symbol,
    timeframe,
    ROUND(mfe_long * 100, 3) as mfe_pct,
    ROUND(mae_long * 100, 3) as mae_pct,
    ROUND(realized_return_long * 100, 3) as return_pct,
    ROUND(score_long * 100, 3) as score_pct,
    bars_held_long,
    exit_type_long
FROM ml_training_labels
WHERE mfe_long > 0.02
  AND score_long < 0.005
ORDER BY mfe_long DESC
LIMIT 50
""",
    
    "📅 Daily Score Average": """
SELECT 
    DATE(timestamp) as date,
    symbol,
    COUNT(*) as labels,
    ROUND(AVG(score_long) * 100, 4) as avg_score_long_pct,
    ROUND(AVG(score_short) * 100, 4) as avg_score_short_pct
FROM ml_training_labels
GROUP BY DATE(timestamp), symbol
ORDER BY date DESC, symbol
LIMIT 100
""",
    
    "🔍 Recent Labels (Last 100)": """
SELECT 
    timestamp,
    symbol,
    timeframe,
    ROUND(close, 2) as close,
    ROUND(score_long * 100, 4) as score_long_pct,
    ROUND(score_short * 100, 4) as score_short_pct,
    exit_type_long,
    exit_type_short
FROM ml_training_labels
ORDER BY timestamp DESC
LIMIT 100
"""
}
