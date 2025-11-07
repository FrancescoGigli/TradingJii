#!/usr/bin/env python3
"""
🤖 AI ANALYSIS TAB

Tab nella dashboard per mostrare analisi ChatGPT dei trade.
Visualizza prediction vs reality analysis in formato leggibile.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QBrush

from .helpers import ColorHelper


class AIAnalysisTabPopulator:
    """Popola tab AI Analysis con analisi ChatGPT"""
    
    @staticmethod
    def populate(table: QTableWidget, max_rows: int = 50):
        """
        Popola tabella con ultime analisi ChatGPT
        
        Args:
            table: QTableWidget da popolare
            max_rows: Numero massimo analisi da mostrare
        """
        try:
            # Get analyses from database
            db_path = Path("trade_analysis.db")
            
            if not db_path.exists():
                # No database yet
                table.setRowCount(1)
                item = QTableWidgetItem("⏳ No AI analyses yet - waiting for first trade to close...")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(QFont("Segoe UI", 10))
                table.setItem(0, 0, item)
                table.setSpan(0, 0, 1, table.columnCount())
                return
            
            # Query database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    symbol, timestamp, outcome, pnl_roe, duration_minutes,
                    prediction_accuracy, analysis_category, explanation,
                    recommendations, confidence
                FROM trade_analyses
                ORDER BY timestamp DESC
                LIMIT ?
            """, (max_rows,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                # Database exists but empty
                table.setRowCount(1)
                item = QTableWidgetItem("📊 Database ready - waiting for trade analyses...")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(QFont("Segoe UI", 10))
                table.setItem(0, 0, item)
                table.setSpan(0, 0, 1, table.columnCount())
                return
            
            # Populate table
            table.setRowCount(len(rows))
            
            for row_idx, row_data in enumerate(rows):
                symbol, timestamp, outcome, pnl_roe, duration, accuracy, category, explanation, recs_json, confidence = row_data
                
                # Clean symbol
                symbol_short = symbol.replace('/USDT:USDT', '')
                
                # Format timestamp
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%d/%m %H:%M")
                except:
                    time_str = timestamp[:16] if timestamp else 'N/A'
                
                # Column 0: Time
                time_item = QTableWidgetItem(time_str)
                time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_idx, 0, time_item)
                
                # Column 1: Symbol
                symbol_item = QTableWidgetItem(symbol_short)
                symbol_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                symbol_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                table.setItem(row_idx, 1, symbol_item)
                
                # Column 2: Outcome (WIN/LOSS)
                outcome_item = QTableWidgetItem(f"{outcome} {pnl_roe:+.1f}%")
                outcome_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                outcome_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                
                if outcome == "WIN":
                    outcome_item.setForeground(QBrush(ColorHelper.POSITIVE))
                else:
                    outcome_item.setForeground(QBrush(ColorHelper.NEGATIVE))
                
                table.setItem(row_idx, 2, outcome_item)
                
                # Column 3: Accuracy
                accuracy_item = QTableWidgetItem(accuracy or 'N/A')
                accuracy_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                # Color based on accuracy
                if 'correct' in (accuracy or '').lower():
                    accuracy_item.setForeground(QBrush(ColorHelper.POSITIVE))
                elif 'overconfident' in (accuracy or '').lower():
                    accuracy_item.setForeground(QBrush(ColorHelper.WARNING))
                elif 'wrong' in (accuracy or '').lower():
                    accuracy_item.setForeground(QBrush(ColorHelper.NEGATIVE))
                
                table.setItem(row_idx, 3, accuracy_item)
                
                # Column 4: Category
                category_item = QTableWidgetItem(category or 'N/A')
                category_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_idx, 4, category_item)
                
                # Column 5: Explanation (truncated)
                explanation_text = explanation or 'No explanation'
                if len(explanation_text) > 100:
                    explanation_text = explanation_text[:97] + "..."
                
                explanation_item = QTableWidgetItem(explanation_text)
                explanation_item.setToolTip(explanation or 'No explanation available')
                table.setItem(row_idx, 5, explanation_item)
                
                # Column 6: Recommendations (count + preview)
                try:
                    import json
                    recs = json.loads(recs_json) if recs_json else []
                    rec_count = len(recs)
                    rec_preview = recs[0] if recs else "No recommendations"
                    
                    rec_text = f"({rec_count}) {rec_preview[:50]}..."
                    rec_item = QTableWidgetItem(rec_text)
                    
                    # Tooltip with all recommendations
                    if recs:
                        tooltip = "🎯 RECOMMENDATIONS:\n\n"
                        for i, rec in enumerate(recs, 1):
                            tooltip += f"{i}. {rec}\n"
                        rec_item.setToolTip(tooltip)
                    
                    table.setItem(row_idx, 6, rec_item)
                    
                except:
                    rec_item = QTableWidgetItem("Parse error")
                    table.setItem(row_idx, 6, rec_item)
                
                # Column 7: Confidence
                conf_item = QTableWidgetItem(f"{confidence*100:.0f}%" if confidence else 'N/A')
                conf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                if confidence and confidence >= 0.8:
                    conf_item.setForeground(QBrush(ColorHelper.POSITIVE))
                elif confidence and confidence < 0.5:
                    conf_item.setForeground(QBrush(ColorHelper.WARNING))
                
                table.setItem(row_idx, 7, conf_item)
            
            # Center align all cells
            for row in range(table.rowCount()):
                for col in [0, 1, 2, 3, 4, 7]:  # Only specific columns
                    item = table.item(row, col)
                    if item:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        except Exception as e:
            logging.error(f"Error populating AI analysis tab: {e}")
            # Show error in table
            table.setRowCount(1)
            item = QTableWidgetItem(f"❌ Error loading analyses: {str(e)}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(0, 0, item)
            table.setSpan(0, 0, 1, table.columnCount())


def create_ai_analysis_table() -> QTableWidget:
    """
    Crea tabella per AI analysis tab
    
    Returns:
        QTableWidget configurata
    """
    table = QTableWidget()
    table.setColumnCount(8)
    table.setHorizontalHeaderLabels([
        "Time",
        "Symbol", 
        "Outcome",
        "Accuracy",
        "Category",
        "Explanation",
        "Recommendations",
        "Conf%"
    ])
    
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    
    # Performance optimizations
    table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
    table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
    table.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
    
    # Column widths
    header = table.horizontalHeader()
    table.setColumnWidth(0, 90)   # Time
    table.setColumnWidth(1, 80)   # Symbol
    table.setColumnWidth(2, 110)  # Outcome
    table.setColumnWidth(3, 140)  # Accuracy
    table.setColumnWidth(4, 140)  # Category
    table.setColumnWidth(6, 80)   # Conf%
    
    # Explanation and Recommendations stretch
    header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
    
    # Enable sorting
    table.setSortingEnabled(True)
    header.setSortIndicatorShown(True)
    header.setSectionsClickable(True)
    
    return table
