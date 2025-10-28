#!/usr/bin/env python3
"""
🎯 ADAPTIVE MEMORY TAB

Creates and populates the Adaptive Memory tab showing:
- Symbol performance tracking
- Size evolution (GROWING/STABLE/SHRINKING/BLOCKED)
- Win/Loss records
- Historical performance
"""

import logging
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush
from .helpers import ColorHelper
import config


def create_adaptive_memory_table() -> QTableWidget:
    """
    Create Adaptive Memory table
    
    Columns:
    - Symbol
    - Status (GROWING/STABLE/BLOCKED)
    - Current Size
    - Base Size
    - Change %
    - Record (W-L)
    - Win Rate
    - Last PnL
    - Last Updated
    
    Returns:
        QTableWidget: Configured table
    """
    table = QTableWidget()
    table.setColumnCount(9)
    table.setHorizontalHeaderLabels([
        "Symbol", "Status", "Current Size", "Base Size", "Change %", 
        "Record", "Win Rate", "Last PnL", "Last Updated"
    ])
    
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.horizontalHeader().setStretchLastSection(True)
    
    # Performance optimizations
    table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
    table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
    table.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
    
    # Column widths
    table.setColumnWidth(0, 80)   # Symbol
    table.setColumnWidth(1, 120)  # Status
    table.setColumnWidth(2, 100)  # Current Size
    table.setColumnWidth(3, 100)  # Base Size
    table.setColumnWidth(4, 80)   # Change %
    table.setColumnWidth(5, 80)   # Record
    table.setColumnWidth(6, 80)   # Win Rate
    table.setColumnWidth(7, 80)   # Last PnL
    # Last Updated stretches
    
    # Enable sorting
    table.setSortingEnabled(True)
    header = table.horizontalHeader()
    header.setSortIndicatorShown(True)
    header.setSectionsClickable(True)
    
    return table


def populate_adaptive_memory_table(table: QTableWidget, adaptive_sizing=None):
    """
    Populate Adaptive Memory table with data from adaptive sizing
    
    Args:
        table: QTableWidget to populate
        adaptive_sizing: AdaptivePositionSizing instance (or None if disabled)
    """
    # Disable updates during populate
    table.setUpdatesEnabled(False)
    table.setSortingEnabled(False)
    
    try:
        # Check if adaptive sizing is enabled
        if not config.ADAPTIVE_SIZING_ENABLED or adaptive_sizing is None:
            table.setRowCount(1)
            item = QTableWidgetItem("Adaptive Sizing is disabled")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(0, 0, item)
            table.setSpan(0, 0, 1, 9)
            return
        
        # Get memory from adaptive sizing
        symbol_memory = adaptive_sizing.symbol_memory
        
        if not symbol_memory:
            table.setRowCount(1)
            item = QTableWidgetItem("No symbols in memory yet")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(0, 0, item)
            table.setSpan(0, 0, 1, 9)
            return
        
        # Sort symbols: active first (by size desc), then blocked (by cycles left)
        sorted_symbols = sorted(
            symbol_memory.items(),
            key=lambda x: (x[1].blocked_cycles_left > 0, -x[1].current_size)
        )
        
        table.setRowCount(len(sorted_symbols))
        
        for row, (symbol, memory) in enumerate(sorted_symbols):
            # Column 0: Symbol
            symbol_short = symbol.replace('/USDT:USDT', '')
            table.setItem(row, 0, QTableWidgetItem(symbol_short))
            
            # Column 1: Status
            status_item = QTableWidgetItem()
            
            if memory.blocked_cycles_left > 0:
                # BLOCKED
                status_item.setText(f"🚫 BLOCKED ({memory.blocked_cycles_left} left)")
                status_item.setForeground(QBrush(ColorHelper.NEGATIVE))
                status_item.setToolTip(
                    f"Symbol is BLOCKED for {memory.blocked_cycles_left} more cycles\n"
                    f"Reason: Last trade was a loss ({memory.last_pnl_pct:+.1f}%)\n"
                    f"Will return with base size: ${memory.base_size:.2f}"
                )
            else:
                # Calculate size change
                size_change_pct = ((memory.current_size - memory.base_size) / memory.base_size * 100) if memory.base_size > 0 else 0
                
                if size_change_pct > 5:
                    status_item.setText("📈 GROWING")
                    status_item.setForeground(QBrush(ColorHelper.POSITIVE))
                    status_item.setToolTip(
                        f"Symbol is GROWING (performing well)\n"
                        f"Size increased by {size_change_pct:+.1f}%\n"
                        f"Current: ${memory.current_size:.2f} | Base: ${memory.base_size:.2f}"
                    )
                elif size_change_pct < -5:
                    status_item.setText("📉 SHRINKING")
                    status_item.setForeground(QBrush(ColorHelper.WARNING))
                    status_item.setToolTip(
                        f"Symbol was RESET after a loss\n"
                        f"Size decreased by {size_change_pct:.1f}%\n"
                        f"Current: ${memory.current_size:.2f} | Base: ${memory.base_size:.2f}"
                    )
                else:
                    status_item.setText("📊 STABLE")
                    status_item.setForeground(QBrush(ColorHelper.INFO))
                    status_item.setToolTip(
                        f"Symbol at BASE size level\n"
                        f"Size change: {size_change_pct:+.1f}%\n"
                        f"Current: ${memory.current_size:.2f} | Base: ${memory.base_size:.2f}"
                    )
            
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 1, status_item)
            
            # Column 2: Current Size
            current_size_item = QTableWidgetItem(f"${memory.current_size:.2f}")
            current_size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 2, current_size_item)
            
            # Column 3: Base Size
            base_size_item = QTableWidgetItem(f"${memory.base_size:.2f}")
            base_size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 3, base_size_item)
            
            # Column 4: Change %
            size_change_pct = ((memory.current_size - memory.base_size) / memory.base_size * 100) if memory.base_size > 0 else 0
            change_item = QTableWidgetItem(ColorHelper.format_pct(size_change_pct))
            
            # Color based on change
            if size_change_pct > 5:
                change_item.setForeground(QBrush(ColorHelper.POSITIVE))
            elif size_change_pct < -5:
                change_item.setForeground(QBrush(ColorHelper.WARNING))
            else:
                change_item.setForeground(QBrush(ColorHelper.INFO))
            
            change_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 4, change_item)
            
            # Column 5: Record (W-L)
            record_text = f"{memory.wins}W-{memory.losses}L"
            record_item = QTableWidgetItem(record_text)
            record_item.setToolTip(
                f"Total Trades: {memory.total_trades}\n"
                f"Wins: {memory.wins}\n"
                f"Losses: {memory.losses}"
            )
            record_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 5, record_item)
            
            # Column 6: Win Rate
            win_rate = (memory.wins / memory.total_trades * 100) if memory.total_trades > 0 else 0
            win_rate_item = QTableWidgetItem(f"{win_rate:.0f}%")
            
            # Color based on win rate
            if win_rate >= 60:
                win_rate_item.setForeground(QBrush(ColorHelper.POSITIVE))
            elif win_rate >= 40:
                win_rate_item.setForeground(QBrush(ColorHelper.WARNING))
            else:
                win_rate_item.setForeground(QBrush(ColorHelper.NEGATIVE))
            
            win_rate_item.setToolTip(
                f"Win Rate: {win_rate:.1f}%\n"
                f"{memory.wins} wins out of {memory.total_trades} trades"
            )
            win_rate_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 6, win_rate_item)
            
            # Column 7: Last PnL
            last_pnl_item = QTableWidgetItem(ColorHelper.format_pct(memory.last_pnl_pct))
            
            # Color based on last PnL
            if memory.last_pnl_pct > 0:
                last_pnl_item.setForeground(QBrush(ColorHelper.POSITIVE))
            elif memory.last_pnl_pct < 0:
                last_pnl_item.setForeground(QBrush(ColorHelper.NEGATIVE))
            else:
                last_pnl_item.setForeground(QBrush(ColorHelper.NEUTRAL))
            
            last_pnl_item.setToolTip(f"Last trade PnL: {memory.last_pnl_pct:+.2f}%")
            last_pnl_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 7, last_pnl_item)
            
            # Column 8: Last Updated
            from datetime import datetime
            try:
                last_updated_dt = datetime.fromisoformat(memory.last_updated)
                last_updated_str = last_updated_dt.strftime("%d/%m %H:%M")
            except:
                last_updated_str = "N/A"
            
            last_updated_item = QTableWidgetItem(last_updated_str)
            last_updated_item.setToolTip(f"Last cycle updated: {memory.last_cycle_updated}")
            last_updated_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 8, last_updated_item)
            
            # Row background color for blocked symbols
            if memory.blocked_cycles_left > 0:
                from PyQt6.QtGui import QColor
                row_background = QColor("#3D0000")  # Dark red
                for col in range(9):
                    item = table.item(row, col)
                    if item:
                        item.setBackground(QBrush(row_background))
        
        # Overall summary in status/tooltip
        total_symbols = len(symbol_memory)
        active_symbols = sum(1 for m in symbol_memory.values() if m.blocked_cycles_left == 0)
        blocked_symbols = total_symbols - active_symbols
        total_trades = sum(m.total_trades for m in symbol_memory.values())
        total_wins = sum(m.wins for m in symbol_memory.values())
        total_losses = sum(m.losses for m in symbol_memory.values())
        overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        logging.debug(
            f"Adaptive Memory: {active_symbols} active, {blocked_symbols} blocked | "
            f"{total_wins}W/{total_losses}L ({overall_win_rate:.1f}% WR)"
        )
        
    except Exception as e:
        logging.error(f"Error populating adaptive memory table: {e}")
        table.setRowCount(1)
        item = QTableWidgetItem(f"Error: {e}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(0, 0, item)
        table.setSpan(0, 0, 1, 9)
    
    finally:
        # Re-enable updates and sorting
        table.setSortingEnabled(True)
        table.setUpdatesEnabled(True)
