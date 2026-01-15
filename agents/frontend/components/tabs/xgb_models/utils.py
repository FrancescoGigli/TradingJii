"""
🔧 XGBoost Models - Utility Functions

Path configuration and helper functions for model management.
"""

import os
import json
from pathlib import Path
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
# PATH CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

def get_models_dir() -> Path:
    """Get models directory path (works in Docker and locally)"""
    shared_path = os.environ.get('SHARED_DATA_PATH')
    if shared_path:
        return Path(shared_path) / "models"
    else:
        return Path(__file__).parent.parent.parent.parent.parent.parent / "shared" / "models"


MODELS_DIR = get_models_dir()


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_metadata(model_version: str = "latest") -> dict:
    """Load model metadata from JSON file"""
    metadata_path = MODELS_DIR / f"metadata_{model_version}.json"
    
    if not metadata_path.exists():
        return None
    
    with open(metadata_path, 'r') as f:
        return json.load(f)


def get_available_models() -> list:
    """Get list of available model versions"""
    if not MODELS_DIR.exists():
        return []
    
    versions = []
    for f in MODELS_DIR.glob("metadata_*.json"):
        version = f.stem.replace("metadata_", "")
        versions.append(version)
    
    # Sort by date (most recent first), keep 'latest' at top
    versions = sorted([v for v in versions if v != 'latest'], reverse=True)
    if (MODELS_DIR / "metadata_latest.json").exists():
        versions.insert(0, "latest")
    
    return versions


# ═══════════════════════════════════════════════════════════════════════════════
# QUALITY ASSESSMENT
# ═══════════════════════════════════════════════════════════════════════════════

def get_signal_quality(spearman: float) -> tuple:
    """
    Get signal quality label and color based on Spearman correlation
    
    Returns:
        tuple: (quality_label, color)
    """
    if spearman > 0.10:
        return "🟢 EXCELLENT", "green"
    elif spearman > 0.05:
        return "🟡 GOOD", "yellow"
    elif spearman > 0.02:
        return "🟠 WEAK", "orange"
    else:
        return "🔴 NO SIGNAL", "red"


def format_date(date_string: str) -> str:
    """Format ISO date string for display"""
    if date_string == 'N/A':
        return 'N/A'
    try:
        dt = datetime.fromisoformat(date_string)
        return dt.strftime("%Y-%m-%d")
    except:
        return date_string[:10] if len(date_string) > 10 else date_string


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL VERSION FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════

def format_version(version: str) -> str:
    """Format version string for display"""
    if version == "latest":
        return "🕐 Latest"
    elif "_optuna" in version:
        return f"🎯 Optuna {version[:8]}_{version[9:15]}"
    else:
        return f"📅 {version[:8]}_{version[9:]}"


def is_optuna_model(metadata: dict) -> bool:
    """Check if model was trained with Optuna"""
    return metadata.get('tuning_method') == 'optuna_tpe' or \
           metadata.get('version', '').endswith('_optuna')


__all__ = [
    'MODELS_DIR',
    'get_models_dir',
    'load_metadata',
    'get_available_models',
    'get_signal_quality',
    'format_date',
    'format_version',
    'is_optuna_model'
]
