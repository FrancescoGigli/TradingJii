"""
Model Loader - Centralized model path and metadata loading.

This module consolidates the duplicated model loading logic that was
previously spread across:
- training_ai_eval.py
- training_btc_inference.py
- models.py

All model-related path and metadata operations should use this module.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


def get_model_dir() -> Path:
    """
    Get the models directory path.
    
    Uses SHARED_DATA_PATH environment variable if set,
    otherwise defaults to /app/shared.
    
    Returns:
        Path to the models directory
    """
    shared_path = os.environ.get('SHARED_DATA_PATH', '/app/shared')
    return Path(shared_path) / "models"


def load_metadata(timeframe: str) -> Optional[Dict[str, Any]]:
    """
    Load metadata for a specific timeframe model.
    
    Args:
        timeframe: Either '15m' or '1h'
        
    Returns:
        Dictionary with model metadata, or None if not found
    """
    model_dir = get_model_dir()
    metadata_path = model_dir / f"metadata_{timeframe}_latest.json"
    
    if not metadata_path.exists():
        return None
    
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def get_available_models() -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Get all available models grouped by timeframe.
    
    Returns:
        Dictionary with '15m' and '1h' keys, each containing
        metadata dict or None if model doesn't exist
    """
    return {
        '15m': load_metadata('15m'),
        '1h': load_metadata('1h')
    }


def model_exists(timeframe: str) -> bool:
    """
    Check if a model exists for a given timeframe.
    
    Args:
        timeframe: Either '15m' or '1h'
        
    Returns:
        True if model files exist, False otherwise
    """
    model_dir = get_model_dir()
    return (model_dir / f"model_long_{timeframe}_latest.pkl").exists()


def get_available_timeframes() -> list:
    """
    Get list of timeframes that have trained models.
    
    Returns:
        List of available timeframe strings (e.g., ['15m', '1h'])
    """
    available = []
    for tf in ['15m', '1h']:
        if load_metadata(tf) is not None:
            available.append(tf)
    return available


__all__ = [
    'get_model_dir',
    'load_metadata',
    'get_available_models',
    'model_exists',
    'get_available_timeframes'
]
