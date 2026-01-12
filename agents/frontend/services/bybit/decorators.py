"""
Bybit Service - Decorators
"""

import time
import logging
from functools import wraps

from .models import MAX_RETRIES, RETRY_DELAY_BASE

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries: int = MAX_RETRIES, base_delay: float = RETRY_DELAY_BASE):
    """
    Decorator that retries a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries (increases exponentially)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if it's a rate limit error
                    error_str = str(e).lower()
                    is_rate_limit = 'rate' in error_str or 'limit' in error_str or '429' in error_str
                    
                    # Don't retry on authentication errors
                    if 'auth' in error_str or 'key' in error_str or '401' in error_str or '403' in error_str:
                        logger.error(f"❌ Authentication error in {func.__name__}: {e}")
                        raise
                    
                    if attempt < max_retries:
                        # Exponential backoff with jitter
                        delay = base_delay * (2 ** attempt) + (time.time() % 1) * 0.5
                        
                        # Longer delay for rate limits
                        if is_rate_limit:
                            delay = max(delay, 5.0)
                        
                        logger.warning(
                            f"⚠️ Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"❌ All {max_retries + 1} attempts failed for {func.__name__}: {e}")
            
            raise last_exception
        return wrapper
    return decorator
