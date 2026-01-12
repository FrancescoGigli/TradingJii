"""
Bybit Service - Singleton management
"""

import threading
import logging
from typing import Optional

from .service import BybitService

logger = logging.getLogger(__name__)

# Module-level singleton
_bybit_service_instance: Optional[BybitService] = None
_singleton_lock = threading.Lock()


def get_bybit_service() -> BybitService:
    """
    Get singleton instance of BybitService.
    
    Thread-safe lazy initialization.
    
    Returns:
        BybitService singleton instance
    """
    global _bybit_service_instance
    
    if _bybit_service_instance is None:
        with _singleton_lock:
            if _bybit_service_instance is None:
                logger.info("🚀 Creating BybitService singleton...")
                _bybit_service_instance = BybitService()
    
    return _bybit_service_instance


def reset_bybit_service():
    """
    Reset the singleton instance.
    Useful for testing or credential changes.
    """
    global _bybit_service_instance
    
    with _singleton_lock:
        if _bybit_service_instance is not None:
            logger.info("🔄 Resetting BybitService singleton...")
            _bybit_service_instance.clear_cache()
            _bybit_service_instance = None
