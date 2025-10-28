#!/usr/bin/env python3
"""
🎨 DASHBOARD HELPERS

Helper utilities for dashboard:
- ColorHelper: Color management and formatting
- Utility functions for formatting
"""

from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtGui import QColor, QBrush


class ColorHelper:
    """Centralized color management and formatting"""
    
    # Color palette
    POSITIVE = QColor("#22C55E")
    NEGATIVE = QColor("#EF4444")
    NEUTRAL = QColor("#E6EEF8")
    WARNING = QColor("#F59E0B")
    INFO = QColor("#06B6D4")
    BACKGROUND_DARK = QColor("#0B0F14")
    BACKGROUND_MEDIUM = QColor("#121822")
    
    @staticmethod
    def color_cell(item: QTableWidgetItem, value: float, neutral_threshold: float = 0):
        """Apply color based on value"""
        if value > neutral_threshold:
            color = ColorHelper.POSITIVE
        elif value < neutral_threshold:
            color = ColorHelper.NEGATIVE
        else:
            color = ColorHelper.NEUTRAL
        item.setForeground(QBrush(color))
    
    @staticmethod
    def format_price(price: float) -> str:
        """Format price with intelligent decimals"""
        if price < 0.01:
            return f"${price:.6f}"
        elif price < 1:
            return f"${price:.4f}"
        else:
            return f"${price:,.2f}"
    
    @staticmethod
    def format_usd(value: float) -> str:
        """Format USD value with thousands separator"""
        return f"${value:+,.2f}" if value != 0 else "$0.00"
    
    @staticmethod
    def format_pct(value: float) -> str:
        """Format percentage with max 1 decimal"""
        return f"{value:+.1f}%"
