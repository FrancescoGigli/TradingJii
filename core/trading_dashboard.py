#!/usr/bin/env python3
"""
📊 TRADING DASHBOARD - LIVE UI (PyQt6 + qasync VERSION)

Complete dashboard with PyQt6 GUI integrated with asyncio using qasync:
- Session statistics (Win/Loss, PnL, Win Rate)
- Active positions with trailing status  
- Last closed trades
- Portfolio summary

Modern GUI with professional dark theme and 6 UI improvements:
1. Side colors (LONG green, SHORT red)
2. Row highlighting (red/yellow/green for issues)
3. Improved number formatting (smart decimals, separators)
4. Informative tooltips
5. Expanded header info
6. Status bar info
"""

import logging
import sys
import asyncio
from datetime import datetime
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGroupBox, QTableWidget, QTableWidgetItem, QGridLayout,
    QHeaderView, QStatusBar
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QColor, QBrush
from qasync import QEventLoop


class ColorHelper:
    """Centralized color management"""
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


class TradingDashboard(QMainWindow):
    """Live trading dashboard with PyQt6 GUI + qasync integration"""
    
    def __init__(self, position_manager, session_stats):
        super().__init__()
        
        self.position_manager = position_manager
        self.session_stats = session_stats
        self.last_update_time = datetime.now()
        self.update_interval = 10000
        self.update_timer = None
        self.is_running = False
        self.api_call_count = 0
        
        self._setup_window()
        self._create_widgets()
        self._apply_stylesheet()
        
        logging.info("📊 TradingDashboard initialized (PyQt6 + qasync version)")
    
    def _setup_window(self):
        """Configure main window"""
        self.setWindowTitle("🎪 TRADING BOT - LIVE DASHBOARD")
        self.setGeometry(100, 100, 1400, 900)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Initializing dashboard...")
    
    def _create_widgets(self):
        """Create all UI widgets"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        central_widget.setLayout(main_layout)
        
        self.header_group = self._create_header_section()
        main_layout.addWidget(self.header_group)
        
        self.stats_group = self._create_statistics_section()
        main_layout.addWidget(self.stats_group)
        
        self.positions_group = self._create_positions_section()
        main_layout.addWidget(self.positions_group, stretch=2)
        
        self.closed_group = self._create_closed_trades_section()
        main_layout.addWidget(self.closed_group, stretch=1)
        
        self.footer_group = self._create_footer_section()
        main_layout.addWidget(self.footer_group)
    
    def _create_header_section(self) -> QGroupBox:
        """Create header section with session info"""
        group = QGroupBox("📊 DASHBOARD HEADER")
        layout = QVBoxLayout()
        
        self.protection_banner = QLabel()
        self.protection_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.protection_banner.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.protection_banner.setStyleSheet("""
            background-color: #22C55E;
            color: #0B0F14;
            padding: 10px;
            border-radius: 5px;
            margin: 5px;
        """)
        self.protection_banner.setText("🛡️ PROTEZIONE ATTIVA | Update: 10s")
        layout.addWidget(self.protection_banner)
        
        self.header_label = QLabel()
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.header_label)
        
        group.setLayout(layout)
        return group
    
    def _create_statistics_section(self) -> QGroupBox:
        """Create statistics section with 5 columns"""
        group = QGroupBox("📈 SESSION STATISTICS")
        layout = QGridLayout()
        layout.setSpacing(15)
        
        self.stat_labels = {}
        categories = ["Balance", "Trades", "Win Rate", "Total PnL", "Best/Worst"]
        
        for i, category in enumerate(categories):
            header = QLabel(category)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            layout.addWidget(header, 0, i)
            
            value = QLabel()
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value.setFont(QFont("Segoe UI", 9))
            layout.addWidget(value, 1, i)
            
            self.stat_labels[category] = value
        
        group.setLayout(layout)
        return group
    
    def _create_positions_section(self) -> QGroupBox:
        """Create active positions table"""
        group = QGroupBox("🎯 ACTIVE POSITIONS")
        layout = QVBoxLayout()
        
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(9)
        self.positions_table.setHorizontalHeaderLabels([
            "Symbol", "Side", "Entry", "Current", "Stop Loss", "Type", "SL %", "PnL", "Status"
        ])
        
        self.positions_table.setAlternatingRowColors(True)
        self.positions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.positions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.positions_table.horizontalHeader().setStretchLastSection(True)
        
        header = self.positions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.positions_table)
        group.setLayout(layout)
        return group
    
    def _create_closed_trades_section(self) -> QGroupBox:
        """Create closed trades table"""
        group = QGroupBox("📋 LAST 5 CLOSED POSITIONS")
        layout = QVBoxLayout()
        
        self.closed_table = QTableWidget()
        self.closed_table.setColumnCount(6)
        self.closed_table.setHorizontalHeaderLabels([
            "Symbol", "Entry→Exit", "PnL", "Hold", "Close Reason", "Time"
        ])
        
        self.closed_table.setAlternatingRowColors(True)
        self.closed_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.closed_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.closed_table.horizontalHeader().setStretchLastSection(True)
        
        header = self.closed_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.closed_table)
        group.setLayout(layout)
        return group
    
    def _create_footer_section(self) -> QGroupBox:
        """Create footer section with portfolio summary"""
        group = QGroupBox("💡 PORTFOLIO SUMMARY")
        layout = QVBoxLayout()
        
        self.footer_label = QLabel()
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.footer_label)
        
        group.setLayout(layout)
        return group
    
    def _apply_stylesheet(self):
        """Apply QSS dark theme"""
        stylesheet = """
            QMainWindow {
                background-color: #0B0F14;
            }
            
            QWidget {
                background-color: #0B0F14;
                color: #E6EEF8;
                font-family: 'Segoe UI';
            }
            
            QGroupBox {
                border: 1px solid #2F3A4D;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: #06B6D4;
                font-weight: bold;
                font-size: 10pt;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            
            QLabel {
                color: #E6EEF8;
                background-color: transparent;
            }
            
            QTableWidget {
                background-color: #121822;
                alternate-background-color: #0F141B;
                color: #E6EEF8;
                gridline-color: #2F3A4D;
                border: 1px solid #2F3A4D;
                border-radius: 3px;
                selection-background-color: #1B2430;
                selection-color: #E6EEF8;
            }
            
            QTableWidget::item {
                padding: 5px;
            }
            
            QHeaderView::section {
                background-color: #1F2A37;
                color: #E6EEF8;
                padding: 5px;
                border: none;
                border-right: 1px solid #2F3A4D;
                border-bottom: 1px solid #2F3A4D;
                font-weight: bold;
            }
            
            QScrollBar:vertical {
                background-color: #121822;
                width: 12px;
                border: none;
            }
            
            QScrollBar::handle:vertical {
                background-color: #2F3A4D;
                border-radius: 6px;
                min-height: 20px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #3F4A5D;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """
        self.setStyleSheet(stylesheet)
    
    def update_dashboard(self, current_balance: float):
        """Update all dashboard sections"""
        try:
            self._update_header()
            self._update_statistics(current_balance)
            self._update_positions()
            self._update_closed_trades()
            self._update_footer()
            self.last_update_time = datetime.now()
        except Exception as e:
            logging.error(f"Dashboard update error: {e}")
    
    def _update_header(self):
        """Update header with expanded info"""
        session_duration = self.session_stats.get_session_duration()
        current_time = datetime.now().strftime("%H:%M:%S")
        
        # Count trailing/stuck/fixed
        active_positions = self.position_manager.safe_get_all_active_positions()
        trailing_count = sum(1 for p in active_positions if hasattr(p, 'trailing_data') and p.trailing_data and p.trailing_data.enabled)
        stuck_count = sum(1 for p in active_positions if p.unrealized_pnl_pct >= 10 and not (hasattr(p, 'trailing_data') and p.trailing_data and p.trailing_data.enabled))
        fixed_count = len(active_positions) - trailing_count - stuck_count
        
        # Update banner with counts
        banner_text = f"🛡️ PROTEZIONE ATTIVA | ✓ {trailing_count} TRAILING | ⚠️ {stuck_count} STUCK | 🔒 {fixed_count} FIXED | Update: 10s"
        self.protection_banner.setText(banner_text)
        
        header_text = f"Session Duration: {session_duration} | Last Update: {current_time}"
        self.header_label.setText(header_text)
    
    def _update_statistics(self, current_balance: float):
        """Update statistics section"""
        total_trades = self.session_stats.get_total_trades()
        win_rate = self.session_stats.get_win_rate()
        win_rate_emoji = self.session_stats.get_win_rate_emoji()
        pnl_usd, pnl_pct = self.session_stats.get_pnl_vs_start()
        
        balance_text = f"${current_balance:.2f}\nStart: ${self.session_stats.session_start_balance:.2f}"
        self.stat_labels["Balance"].setText(balance_text)
        
        trades_text = f"{total_trades} ({self.session_stats.trades_won}W / {self.session_stats.trades_lost}L)\nOpen: {self.position_manager.safe_get_position_count()}"
        self.stat_labels["Trades"].setText(trades_text)
        
        winrate_text = f"{win_rate:.1f}% {win_rate_emoji}\nAvg Win: +{self.session_stats.get_average_win_pct():.1f}%"
        self.stat_labels["Win Rate"].setText(winrate_text)
        
        pnl_text = f"{'+' if pnl_usd >= 0 else ''}{pnl_usd:.2f} USD\n({'+' if pnl_pct >= 0 else ''}{pnl_pct:.2f}%)"
        pnl_label = self.stat_labels["Total PnL"]
        pnl_label.setText(pnl_text)
        
        if pnl_usd >= 0:
            pnl_label.setStyleSheet("color: #22C55E;")
        else:
            pnl_label.setStyleSheet("color: #EF4444;")
        
        best_str = f"+${self.session_stats.best_trade_pnl:.2f}" if self.session_stats.best_trade_pnl > 0 else "$0.00"
        worst_str = f"-${abs(self.session_stats.worst_trade_pnl):.2f}" if self.session_stats.worst_trade_pnl < 0 else "$0.00"
        best_worst_text = f"{best_str} / {worst_str}\nAvg Hold: {self.session_stats.get_average_hold_time()}"
        self.stat_labels["Best/Worst"].setText(best_worst_text)
    
    def _update_positions(self):
        """Update active positions table with all 6 improvements"""
        active_positions = self.position_manager.safe_get_all_active_positions()
        
        self.positions_group.setTitle(f"🎯 ACTIVE POSITIONS ({len(active_positions)})")
        
        self.positions_table.setRowCount(0)
        
        if not active_positions:
            self.positions_table.setRowCount(1)
            item = QTableWidgetItem("No active positions")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_table.setItem(0, 0, item)
            self.positions_table.setSpan(0, 0, 1, 9)
            return
        
        self.positions_table.setRowCount(len(active_positions))
        
        for row, pos in enumerate(active_positions):
            # Symbol
            symbol_short = pos.symbol.replace('/USDT:USDT', '')
            self.positions_table.setItem(row, 0, QTableWidgetItem(symbol_short))
            
            # Side with color (IMPROVEMENT 1)
            side_item = QTableWidgetItem()
            if pos.side in ['buy', 'long']:
                side_item.setText(f"[↑] LONG {pos.leverage}x")
                side_item.setForeground(QBrush(ColorHelper.POSITIVE))
            else:
                side_item.setText(f"[↓] SHORT {pos.leverage}x")
                side_item.setForeground(QBrush(ColorHelper.NEGATIVE))
            side_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_table.setItem(row, 1, side_item)
            
            # Entry & Current (IMPROVEMENT 3 - smart formatting)
            self.positions_table.setItem(row, 2, QTableWidgetItem(ColorHelper.format_price(pos.entry_price)))
            self.positions_table.setItem(row, 3, QTableWidgetItem(ColorHelper.format_price(pos.current_price)))
            
            # Stop Loss (IMPROVEMENT 3)
            sl_item = QTableWidgetItem(ColorHelper.format_price(pos.stop_loss))
            self.positions_table.setItem(row, 4, sl_item)
            
            # Calculate ROE
            roe_pct = pos.unrealized_pnl_pct
            
            # Check trailing
            is_trailing_active = (hasattr(pos, 'trailing_data') and 
                                 pos.trailing_data and 
                                 pos.trailing_data.enabled)
            
            # Type with tooltip (IMPROVEMENT 4)
            type_item = QTableWidgetItem()
            if is_trailing_active:
                type_item.setText("TRAILING")
                type_item.setForeground(QBrush(ColorHelper.POSITIVE))
                type_item.setToolTip("Trailing Stop: Stop loss dinamico a -8% dal prezzo corrente")
            else:
                type_item.setText("FIXED")
                type_item.setForeground(QBrush(ColorHelper.INFO))
                type_item.setToolTip("Fixed Stop Loss: Stop loss fisso a -50% ROE")
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_table.setItem(row, 5, type_item)
            
            # SL % with tooltip (IMPROVEMENT 4)
            sl_pct_item = QTableWidgetItem()
            if pos.side in ['buy', 'long']:
                sl_distance = ((pos.stop_loss - pos.current_price) / pos.current_price) * 100
            else:
                sl_distance = ((pos.stop_loss - pos.current_price) / pos.current_price) * 100
            
            sl_pct_item.setText(ColorHelper.format_pct(sl_distance))
            sl_pct_item.setToolTip(
                "Distanza percentuale dello Stop Loss dal prezzo corrente\n\n"
                "LONG: Negativo = SL sotto prezzo (corretto) ✓\n"
                "SHORT: Positivo = SL sopra prezzo (corretto) ✓"
            )
            
            if pos.side in ['buy', 'long']:
                if sl_distance < 0:
                    sl_pct_item.setForeground(QBrush(ColorHelper.POSITIVE))
                else:
                    sl_pct_item.setForeground(QBrush(ColorHelper.NEGATIVE))
            else:
                if sl_distance > 0:
                    sl_pct_item.setForeground(QBrush(ColorHelper.POSITIVE))
                else:
                    sl_pct_item.setForeground(QBrush(ColorHelper.NEGATIVE))
            sl_pct_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_table.setItem(row, 6, sl_pct_item)
            
            # PnL (IMPROVEMENT 3)
            pnl_text = f"{ColorHelper.format_pct(pos.unrealized_pnl_pct)}\n{ColorHelper.format_usd(pos.unrealized_pnl_usd)}"
            pnl_item = QTableWidgetItem(pnl_text)
            ColorHelper.color_cell(pnl_item, pos.unrealized_pnl_usd)
            self.positions_table.setItem(row, 7, pnl_item)
            
            # Status with tooltip (IMPROVEMENT 4)
            status_item = QTableWidgetItem()
            
            if pos.side in ['buy', 'long']:
                price_move_pct = ((pos.current_price - pos.entry_price) / pos.entry_price) * 100
            else:
                price_move_pct = ((pos.entry_price - pos.current_price) / pos.entry_price) * 100
            
            if is_trailing_active:
                status_item.setText(f"✓ ACTIVE\n+{roe_pct:.0f}%")
                status_item.setForeground(QBrush(ColorHelper.POSITIVE))
            elif roe_pct >= 10.0:
                status_item.setText(f"⚠️ STUCK\n+{roe_pct:.0f}%")
                status_item.setForeground(QBrush(ColorHelper.WARNING))
            elif price_move_pct >= 1.0:
                status_item.setText(f"⏳ WAIT\n+{roe_pct:.0f}%")
                status_item.setForeground(QBrush(ColorHelper.INFO))
            elif roe_pct >= 0:
                status_item.setText(f"📊 OK\n+{roe_pct:.0f}%")
                status_item.setForeground(QBrush(ColorHelper.INFO))
            else:
                status_item.setText(f"🔻 LOSS\n{roe_pct:.0f}%")
                status_item.setForeground(QBrush(ColorHelper.NEGATIVE))
            
            status_item.setToolTip(
                "✓ ACTIVE: Trailing attivo e funzionante\n"
                "⚠️ STUCK: Dovrebbe essere in trailing ma non è attivo (BUG!)\n"
                "⏳ WAIT: In attesa di attivazione trailing (+10% ROE)\n"
                "📊 OK: Profit positivo ma sotto soglia trailing\n"
                "🔻 LOSS: Posizione in perdita"
            )
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.positions_table.setItem(row, 8, status_item)
            
            # Row highlighting (IMPROVEMENT 2)
            row_background = None
            if roe_pct < -40:
                row_background = QColor("#3D0000")  # Red
            elif roe_pct >= 10.0 and not is_trailing_active:
                row_background = QColor("#3D3D00")  # Yellow
            elif is_trailing_active and roe_pct >= 10.0:
                row_background = QColor("#003D00")  # Green
            
            if row_background:
                for col in range(9):
                    item = self.positions_table.item(row, col)
                    if item:
                        item.setBackground(QBrush(row_background))
        
        # Center align
        for row in range(self.positions_table.rowCount()):
            for col in range(self.positions_table.columnCount()):
                item = self.positions_table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    
    def _update_closed_trades(self):
        """Update closed trades table"""
        last_trades = self.session_stats.get_last_n_trades(5)
        
        self.closed_table.setRowCount(0)
        
        if not last_trades:
            self.closed_table.setRowCount(1)
            item = QTableWidgetItem("No closed trades yet")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.closed_table.setItem(0, 0, item)
            self.closed_table.setSpan(0, 0, 1, 6)
            return
        
        reason_emoji = {
            "STOP_LOSS_HIT": "❌",
            "TRAILING_STOP_HIT": "🎪",
            "TAKE_PROFIT_HIT": "🎯",
            "MANUAL_CLOSE": "👤",
            "UNKNOWN": "❓"
        }
        
        self.closed_table.setRowCount(len(last_trades))
        
        for row, trade in enumerate(last_trades):
            self.closed_table.setItem(row, 0, QTableWidgetItem(trade.symbol))
            
            entry_exit = f"${trade.entry_price:,.4f} → ${trade.exit_price:,.4f}"
            self.closed_table.setItem(row, 1, QTableWidgetItem(entry_exit))
            
            pnl_item = QTableWidgetItem(f"{trade.pnl_pct:+.2f}% | ${trade.pnl_usd:+.2f}")
            ColorHelper.color_cell(pnl_item, trade.pnl_usd)
            self.closed_table.setItem(row, 2, pnl_item)
            
            if trade.hold_time_minutes < 60:
                hold_str = f"{trade.hold_time_minutes}m"
            else:
                hours = trade.hold_time_minutes // 60
                minutes = trade.hold_time_minutes % 60
                hold_str = f"{hours}h {minutes}m"
            self.closed_table.setItem(row, 3, QTableWidgetItem(hold_str))
            
            emoji = reason_emoji.get(trade.close_reason, "❓")
            reason_display = trade.close_reason.replace("_", " ").title()
            reason_str = f"{emoji} {reason_display}"
            self.closed_table.setItem(row, 4, QTableWidgetItem(reason_str))
            
            close_time = datetime.fromisoformat(trade.close_time)
            time_str = close_time.strftime("%H:%M")
            self.closed_table.setItem(row, 5, QTableWidgetItem(time_str))
        
        for row in range(self.closed_table.rowCount()):
            for col in range(self.closed_table.columnCount()):
                item = self.closed_table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    
    def _update_footer(self):
        """Update footer with portfolio summary and status bar (IMPROVEMENT 6)"""
        summary = self.position_manager.safe_get_session_summary()
        
        active_count = summary.get('active_positions', 0)
        used_margin = summary.get('used_margin', 0)
        available = summary.get('available_balance', 0)
        unrealized_pnl = summary.get('unrealized_pnl', 0)
        
        active_positions = self.position_manager.safe_get_all_active_positions()
        trailing_count = sum(
            1 for pos in active_positions 
            if hasattr(pos, 'trailing_data') and pos.trailing_data and pos.trailing_data.enabled
        )
        
        footer_text = (f"{active_count} active positions | "
                      f"${used_margin:.2f} margin used | "
                      f"${available:.2f} available | "
                      f"Unrealized PnL: ${unrealized_pnl:+.2f} | "
                      f"Trailing: {trailing_count}/{active_count}")
        
        self.footer_label.setText(footer_text)
        
        # Status bar (IMPROVEMENT 6)
        last_sync = (datetime.now() - self.last_update_time).seconds
        status_text = f"Last sync: {last_sync}s ago | API calls: ~{self.api_call_count}/min | Status: OK"
        self.statusBar().showMessage(status_text)
    
    def _on_timer_update(self):
        """Timer callback for periodic updates"""
        try:
            balance_summary = self.position_manager.safe_get_session_summary()
            current_balance = balance_summary.get('balance', 0)
            self.update_dashboard(current_balance)
            self.api_call_count += 1
        except Exception as e:
            logging.error(f"Error in timer update: {e}")
    
    def start(self):
        """Start the dashboard (non-async, for synchronous usage)"""
        pass
    
    def stop(self):
        """Stop the dashboard"""
        self.is_running = False
        
        if self.update_timer:
            self.update_timer.stop()
        
        self.close()
        
        logging.info("📊 Dashboard stopped")
    
    def closeEvent(self, event):
        """Handle window close event - clean shutdown"""
        self.is_running = False
        
        if self.update_timer:
            self.update_timer.stop()
        
        event.accept()
        logging.info("📊 Dashboard window closed")
    
    async def run_live_dashboard(self, exchange, update_interval: int = 30):
        """Run live dashboard with qasync integration (async)"""
        self.update_interval = update_interval * 1000
        self.is_running = True
        
        # Initial update
        balance_summary = self.position_manager.safe_get_session_summary()
        current_balance = balance_summary.get('balance', 0)
        self.update_dashboard(current_balance)
        
        # Setup QTimer for periodic updates
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._on_timer_update)
        self.update_timer.start(self.update_interval)
        
        # Log protection status
        active_positions = self.position_manager.safe_get_all_active_positions()
        logging.info("=" * 80)
        logging.info("🛡️  SISTEMA DI PROTEZIONE ATTIVO - PyQt6 VERSION")
        logging.info("=" * 80)
        logging.info(f"📊 Dashboard avviato (aggiornamento ogni {update_interval}s)")
        logging.info(f"🎯 {len(active_positions)} posizioni sotto monitoraggio")
        logging.info("🎨 6 UI Improvements attivi:")
        logging.info("  1. ✅ Side colors (LONG green, SHORT red)")
        logging.info("  2. ✅ Row highlighting (red/yellow/green)")
        logging.info("  3. ✅ Smart number formatting")
        logging.info("  4. ✅ Informative tooltips")
        logging.info("  5. ✅ Expanded header info")
        logging.info("  6. ✅ Status bar info")
        logging.info("=" * 80)
        
        # Show window (non-blocking with qasync)
        self.show()
        
        logging.info(f"📊 Dashboard running with qasync (update every {update_interval}s)")
