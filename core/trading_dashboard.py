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
import json
from datetime import datetime
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGroupBox, QTableWidget, QTableWidgetItem, QGridLayout,
    QHeaderView, QStatusBar, QTabWidget
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QColor, QBrush
from qasync import QEventLoop
import sqlite3
from pathlib import Path


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
        self.update_interval = 30000  # 30 seconds - less lag
        self.update_timer = None
        self.is_running = False
        self.api_call_count = 0
        
        # Cache per ridurre operazioni - SEPARATE per ogni tab
        self._cached_synced = []
        self._cached_session = []
        self._cached_closed = []
        self._cached_stats = {}
        self._cache_time_tabs = 0
        self._cache_ttl = 10  # seconds - aumentato per ridurre lag
        
        # Track last data hash to avoid unnecessary updates
        self._last_data_hash = {
            'synced': 0,
            'session': 0,
            'closed': 0
        }
        
        self._setup_window()
        self._create_widgets()
        self._apply_stylesheet()
        
        logging.info("📊 TradingDashboard initialized (PyQt6 + qasync version)")
    
    def _setup_window(self):
        """Configure main window"""
        self.setWindowTitle("🎪 TRADING BOT - LIVE DASHBOARD")
        self.setGeometry(100, 100, 1600, 1000)  # Increased size for better visibility
        
        # Performance optimizations to reduce lag
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)  # Faster painting
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)  # Reduce redraws
        
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
        """Create positions section with 3 tabs: SYNCED, SESSION, CLOSED"""
        group = QGroupBox("🎯 POSITIONS")
        layout = QVBoxLayout()
        
        # Create QTabWidget with 3 tabs
        self.tabs = QTabWidget()
        
        # TAB 1: ALL ACTIVE - Tutte le posizioni attive (SYNCED + SESSION insieme)
        self.all_active_table = self._create_position_table()
        self.tabs.addTab(self.all_active_table, "ALL ACTIVE (0)")
        
        # TAB 2: OPENED THIS SESSION - Solo posizioni aperte in questa sessione
        self.session_table = self._create_position_table()
        self.tabs.addTab(self.session_table, "OPENED THIS SESSION (0)")
        
        # TAB 3: CLOSED - Posizioni chiuse in questa sessione
        self.closed_tab_table = self._create_closed_table()
        self.tabs.addTab(self.closed_tab_table, "CLOSED (0)")
        
        layout.addWidget(self.tabs)
        group.setLayout(layout)
        return group
    
    def _create_position_table(self) -> QTableWidget:
        """Create a position table with standard columns"""
        table = QTableWidget()
        table.setColumnCount(14)
        table.setHorizontalHeaderLabels([
            "Symbol", "Side", "IM", "Entry", "Current", "Stop Loss", "Type", "SL %", "PnL %", "PnL $", 
            "Liq. Price", "Time", "Status", "Open Reason"
        ])
        
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        
        # Performance optimizations for smoother scrolling and resizing
        table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        
        # RESPONSIVE LAYOUT: Auto-resize columns to content
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # Last column stretches to fill remaining space
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        
        # INTERACTIVE: Enable column sorting by clicking headers
        table.setSortingEnabled(True)
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)
        
        return table
    
    def _create_closed_table(self) -> QTableWidget:
        """Create a closed positions table"""
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Symbol", "Entry→Exit", "PnL", "Hold", "Close Reason", "Time"
        ])
        
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        
        # Performance optimizations
        table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        
        # RESPONSIVE LAYOUT: Auto-resize columns to content
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # Close Reason column stretches to fill remaining space
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        
        # INTERACTIVE: Enable column sorting by clicking headers
        table.setSortingEnabled(True)
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)
        
        return table
    
    def _create_closed_trades_section(self) -> QGroupBox:
        """Create closed trades table"""
        group = QGroupBox("📋 CLOSED POSITIONS (SESSION)")
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
        
        # Performance optimizations
        self.closed_table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.closed_table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.closed_table.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        
        # RESPONSIVE LAYOUT: Auto-resize columns to content
        header = self.closed_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # Close Reason column stretches to fill remaining space
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        
        # INTERACTIVE: Enable column sorting by clicking headers
        self.closed_table.setSortingEnabled(True)
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)
        
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
    
    async def update_dashboard_async(self, current_balance: float):
        """Update all dashboard sections - ASYNC non-blocking"""
        try:
            # Update in chunks to keep GUI responsive
            self._update_header()
            await asyncio.sleep(0)  # Yield to event loop
            
            self._update_statistics(current_balance)
            await asyncio.sleep(0)
            
            self._update_positions()
            await asyncio.sleep(0)
            
            self._update_closed_trades()
            await asyncio.sleep(0)
            
            self._update_footer()
            self.last_update_time = datetime.now()
        except Exception as e:
            logging.error(f"Dashboard update error: {e}")
    
    def update_dashboard(self, current_balance: float):
        """Update all dashboard sections - SYNC wrapper"""
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
        
        # Get max positions from config
        import config
        max_positions = config.MAX_CONCURRENT_POSITIONS
        current_open = self.position_manager.safe_get_position_count()
        
        trades_text = f"{total_trades} ({self.session_stats.trades_won}W / {self.session_stats.trades_lost}L)\nOpen: {current_open}/{max_positions}"
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
        """Update all 3 position tabs - OPTIMIZED with cache"""
        # Use cache to reduce lag
        import time
        current_time = time.time()
        
        # Check cache validity and refresh if needed
        if current_time - self._cache_time_tabs < self._cache_ttl:
            # Use cached data
            pass
        else:
            # Refresh all caches
            self._cached_synced = self.position_manager.safe_get_positions_by_origin("SYNCED")
            self._cached_session = self.position_manager.safe_get_positions_by_origin("SESSION")
            self._cached_closed = self.position_manager.safe_get_closed_positions()
            self._cache_time_tabs = current_time
        
        # Combine synced + session for "ALL ACTIVE" tab
        all_active_positions = self._cached_synced + self._cached_session
        
        # Update tab titles with counts
        self.tabs.setTabText(0, f"ALL ACTIVE ({len(all_active_positions)})")
        self.tabs.setTabText(1, f"OPENED THIS SESSION ({len(self._cached_session)})")
        self.tabs.setTabText(2, f"CLOSED ({len(self._cached_closed)})")
        
        # Update group title
        total_active = len(all_active_positions)
        self.positions_group.setTitle(f"🎯 POSITIONS (Active: {total_active}, Closed: {len(self._cached_closed)})")
        
        # Populate each tab
        self._populate_position_table(self.all_active_table, all_active_positions, "ALL ACTIVE")
        self._populate_position_table(self.session_table, self._cached_session, "OPENED THIS SESSION")
        self._populate_closed_tab(self.closed_tab_table, self._cached_closed)
    
    def _populate_position_table(self, table: QTableWidget, positions: list, tab_name: str):
        """Populate a position table with position data"""
        
        # ANTI-LAG: Disable updates during population
        table.setUpdatesEnabled(False)
        
        try:
            # OPTIMIZATION: Only rebuild table if count changed
            if table.rowCount() != len(positions):
                table.setRowCount(0)
            
            if not positions:
                table.setRowCount(1)
                item = QTableWidgetItem(f"No {tab_name.lower()} positions")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(0, 0, item)
                table.setSpan(0, 0, 1, 9)
                return
            
            table.setRowCount(len(positions))
            
            for row, pos in enumerate(positions):
                # Symbol
                symbol_short = pos.symbol.replace('/USDT:USDT', '')
                table.setItem(row, 0, QTableWidgetItem(symbol_short))
                
                # Side with color (IMPROVEMENT 1)
                side_item = QTableWidgetItem()
                if pos.side in ['buy', 'long']:
                    side_item.setText(f"[↑] LONG {pos.leverage}x")
                    side_item.setForeground(QBrush(ColorHelper.POSITIVE))
                else:
                    side_item.setText(f"[↓] SHORT {pos.leverage}x")
                    side_item.setForeground(QBrush(ColorHelper.NEGATIVE))
                side_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 1, side_item)
                
                # Initial Margin (IM) - RIGHT AFTER SIDE
                # Formula: IM = position_size (notional value) / leverage
                # position_size è già il notional value in USD
                initial_margin = pos.position_size / pos.leverage if pos.position_size > 0 else 0
                
                im_item = QTableWidgetItem(f"${initial_margin:.2f}")
                im_item.setToolTip(
                    f"Initial Margin (IM)\n\n"
                    f"Margine bloccato per questa posizione\n"
                    f"Capital allocato: ${initial_margin:.2f}\n\n"
                    f"Calcolo: position_size ${pos.position_size:.2f} ÷ leverage {pos.leverage}x"
                )
                im_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 2, im_item)
            
                # Entry & Current (IMPROVEMENT 3 - smart formatting)
                table.setItem(row, 3, QTableWidgetItem(ColorHelper.format_price(pos.entry_price)))
                table.setItem(row, 4, QTableWidgetItem(ColorHelper.format_price(pos.current_price)))
                
                # Stop Loss (IMPROVEMENT 3)
                sl_item = QTableWidgetItem(ColorHelper.format_price(pos.stop_loss))
                table.setItem(row, 5, sl_item)
            
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
                table.setItem(row, 5, type_item)
            
                # SL % with tooltip - NORMALIZED: Always show as ROE% (price% × leverage)
                sl_pct_item = QTableWidgetItem()
                
                # Calculate price distance (always shows protection direction)
                price_distance_pct = ((pos.stop_loss - pos.entry_price) / pos.entry_price) * 100
                
                # Convert to ROE% by multiplying with leverage
                sl_roe_pct = price_distance_pct * pos.leverage
                
                # VISUAL ADJUSTMENT: Invert sign for SHORT positions (GUI only)
                display_value = sl_roe_pct
                if pos.side in ['sell', 'short']:
                    display_value = -sl_roe_pct  # Inverte il segno solo visivamente
                
                # Display the adjusted value
                sl_pct_item.setText(ColorHelper.format_pct(display_value))
                
                # Build tooltip explaining the visual inversion for SHORT
                side_type = "LONG" if pos.side in ['buy', 'long'] else "SHORT"
                tooltip_text = (
                    f"Stop Loss Risk (ROE%) - {side_type}\n\n"
                    "🔴 Rosso (negativo): Fixed SL - Protezione base\n"
                    "   Protegge da perdite oltre questa percentuale del margine\n\n"
                    "🟢 Verde (positivo): Trailing attivo\n"
                    "   Protegge profitti già realizzati\n\n"
                    f"Calcolo interno: {price_distance_pct:+.1f}% (prezzo) × {pos.leverage}x (leva) = {sl_roe_pct:+.1f}% ROE\n"
                )
                
                if pos.side in ['sell', 'short']:
                    tooltip_text += (
                        f"Valore mostrato: {display_value:+.1f}% (segno invertito per SHORT)\n\n"
                        "📌 Nota: Per le posizioni SHORT, il segno è invertito visivamente\n"
                        "per rendere intuitivo il concetto: negativo = rischio, positivo = protezione profitti"
                    )
                else:
                    tooltip_text += (
                        f"Valore mostrato: {display_value:+.1f}%\n\n"
                        "Esempio: -5% prezzo × 10x leva = -50% ROE massimo rischio"
                    )
                
                sl_pct_item.setToolTip(tooltip_text)
                
                # Color based on displayed value
                if display_value < 0:
                    sl_pct_item.setForeground(QBrush(ColorHelper.NEGATIVE))  # Rosso
                else:
                    sl_pct_item.setForeground(QBrush(ColorHelper.POSITIVE))  # Verde
                sl_pct_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 6, sl_pct_item)
                
                # PnL % (IMPROVEMENT 3) - Separated column
                pnl_pct_item = QTableWidgetItem(ColorHelper.format_pct(pos.unrealized_pnl_pct))
                ColorHelper.color_cell(pnl_pct_item, pos.unrealized_pnl_usd)
                pnl_pct_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 7, pnl_pct_item)
                
                # PnL $ (IMPROVEMENT 3) - Separated column
                pnl_usd_item = QTableWidgetItem(ColorHelper.format_usd(pos.unrealized_pnl_usd))
                ColorHelper.color_cell(pnl_usd_item, pos.unrealized_pnl_usd)
                pnl_usd_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 8, pnl_usd_item)
                
                # Liquidation Price - Calcolo basato su leverage e direction
                # Formula: Liq = Entry ± (Entry / Leverage) per LONG/SHORT
                if pos.side in ['buy', 'long']:
                    # LONG: liquidation quando price scende troppo
                    liq_price = pos.entry_price * (1 - 1 / pos.leverage)
                else:
                    # SHORT: liquidation quando price sale troppo
                    liq_price = pos.entry_price * (1 + 1 / pos.leverage)
                
                liq_item = QTableWidgetItem(ColorHelper.format_price(liq_price))
                
                # Color based on proximity to liquidation
                distance_to_liq_pct = abs((pos.current_price - liq_price) / liq_price) * 100
                if distance_to_liq_pct < 5:  # <5% from liquidation
                    liq_item.setForeground(QBrush(ColorHelper.NEGATIVE))
                elif distance_to_liq_pct < 15:  # 5-15% from liquidation
                    liq_item.setForeground(QBrush(ColorHelper.WARNING))
                else:
                    liq_item.setForeground(QBrush(ColorHelper.INFO))
                
                liq_item.setToolTip(
                    f"Liquidation Price\n\n"
                    f"Prezzo a cui la posizione viene liquidata\n"
                    f"Distanza attuale: {distance_to_liq_pct:.1f}%\n\n"
                    f"🔴 <5%: Pericolo imminente\n"
                    f"🟡 5-15%: Attenzione\n"
                    f"🔵 >15%: Sicuro"
                )
                liq_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 9, liq_item)
                
                # Time in Position
                if pos.entry_time:
                    entry_dt = datetime.fromisoformat(pos.entry_time)
                    now = datetime.now()
                    delta = now - entry_dt
                    hours = int(delta.total_seconds() // 3600)
                    minutes = int((delta.total_seconds() % 3600) // 60)
                    
                    if hours > 0:
                        time_str = f"{hours}h {minutes}m"
                    else:
                        time_str = f"{minutes}m"
                    
                    time_item = QTableWidgetItem(time_str)
                    time_item.setToolTip(f"Opened at: {entry_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    time_item = QTableWidgetItem("N/A")
                
                time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 11, time_item)
                
                # Status with tooltip (IMPROVEMENT 4) - Column 12
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
                table.setItem(row, 12, status_item)
                
                # Open Reason - Shows ML prediction results for SESSION positions or "Already Open" for SYNCED
                reason_item = QTableWidgetItem()
                origin = getattr(pos, 'origin', 'SESSION')
                open_reason = getattr(pos, 'open_reason', None)
                confidence = getattr(pos, 'confidence', 0.0)
                
                # Try to extract ML data from different possible attributes
                ml_signal = getattr(pos, 'ml_signal', None)
                ml_confidence = getattr(pos, 'ml_confidence', confidence)
                prediction_data = getattr(pos, 'prediction_data', None)
                
                # Build debug info for tooltip
                debug_info = (
                    f"DEBUG INFO:\n"
                    f"origin: {origin}\n"
                    f"open_reason: {open_reason}\n"
                    f"confidence: {confidence}\n"
                    f"ml_signal: {ml_signal}\n"
                    f"ml_confidence: {ml_confidence}\n"
                    f"prediction_data: {prediction_data}\n"
                )
                
                # Check if position was synced from Bybit or opened in this session
                if origin == "SYNCED":
                    # Position was already open on Bybit when bot started
                    reason_item.setText("🔄 Already Open")
                    reason_item.setForeground(QBrush(ColorHelper.INFO))
                    reason_item.setToolTip(
                        f"Origin: Found on Bybit at bot startup\n"
                        f"This position was opened before this session started\n\n{debug_info}"
                    )
                else:
                    # Position opened during this session - show ML prediction details
                    # Check multiple sources for ML data
                    has_ml_data = (
                        ml_signal is not None or
                        (confidence > 0) or
                        (ml_confidence > 0) or
                        (open_reason and ("ML" in str(open_reason).upper() or "PREDICTION" in str(open_reason).upper()))
                    )
                    
                    if has_ml_data:
                        # ML prediction available
                        side_indicator = "🟢" if pos.side in ['buy', 'long'] else "🔴"
                        
                        # Use best available confidence value
                        best_confidence = ml_confidence if ml_confidence > 0 else confidence
                        conf_display = f"{best_confidence:.0%}" if best_confidence > 0 else "N/A"
                        
                        reason_item.setText(f"🤖 ML {side_indicator} {conf_display}")
                        reason_item.setForeground(QBrush(ColorHelper.POSITIVE))
                        
                        # Detailed tooltip with full prediction info
                        reason_item.setToolTip(
                            f"ML Prediction Details:\n"
                            f"Side: {'LONG' if pos.side in ['buy', 'long'] else 'SHORT'}\n"
                            f"Confidence: {conf_display}\n"
                            f"Signal: {ml_signal if ml_signal else 'N/A'}\n"
                            f"Reason: {open_reason if open_reason else 'N/A'}\n"
                            f"Entry: ${pos.entry_price:.6f}\n\n{debug_info}"
                        )
                    else:
                        # No ML data found
                        reason_item.setText("📊 Manual")
                        reason_item.setForeground(QBrush(ColorHelper.NEUTRAL))
                        reason_item.setToolTip(
                            f"Manually opened position (no ML prediction found)\n\n{debug_info}"
                        )
                
                reason_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 13, reason_item)
                
                # Row highlighting (IMPROVEMENT 2)
                row_background = None
                if roe_pct < -40:
                    row_background = QColor("#3D0000")  # Red
                elif roe_pct >= 10.0 and not is_trailing_active:
                    row_background = QColor("#3D3D00")  # Yellow
                elif is_trailing_active and roe_pct >= 10.0:
                    row_background = QColor("#003D00")  # Green
                
                if row_background:
                    for col in range(14):  # 14 columns total (0-13)
                        item = table.item(row, col)
                        if item:
                            item.setBackground(QBrush(row_background))
            
            # Center align
            for row in range(table.rowCount()):
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    if item:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        finally:
            # Re-enable updates
            table.setUpdatesEnabled(True)
    
    def _populate_closed_tab(self, table: QTableWidget, closed_positions: list):
        """Populate closed positions tab"""
        if table.rowCount() != len(closed_positions):
            table.setRowCount(0)
            
            if not closed_positions:
                table.setRowCount(1)
                item = QTableWidgetItem("No closed positions")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(0, 0, item)
                table.setSpan(0, 0, 1, 6)
                return
            
            table.setRowCount(len(closed_positions))
        
        if not closed_positions:
            return
        
        for row, pos in enumerate(closed_positions):
            # Symbol
            symbol_short = pos.symbol.replace('/USDT:USDT', '')
            table.setItem(row, 0, QTableWidgetItem(symbol_short))
            
            # Entry → Exit
            entry_exit = f"${pos.entry_price:.4f} → ${pos.current_price:.4f}"
            table.setItem(row, 1, QTableWidgetItem(entry_exit))
            
            # PnL
            pnl_text = f"{ColorHelper.format_pct(pos.unrealized_pnl_pct)} | {ColorHelper.format_usd(pos.unrealized_pnl_usd)}"
            pnl_item = QTableWidgetItem(pnl_text)
            ColorHelper.color_cell(pnl_item, pos.unrealized_pnl_usd)
            table.setItem(row, 2, pnl_item)
            
            # Hold Time
            if pos.entry_time and pos.close_time:
                entry_dt = datetime.fromisoformat(pos.entry_time)
                close_dt = datetime.fromisoformat(pos.close_time)
                hold_minutes = int((close_dt - entry_dt).total_seconds() / 60)
                if hold_minutes < 60:
                    hold_str = f"{hold_minutes}m"
                else:
                    hours = hold_minutes // 60
                    minutes = hold_minutes % 60
                    hold_str = f"{hours}h {minutes}m"
            else:
                hold_str = "N/A"
            table.setItem(row, 3, QTableWidgetItem(hold_str))
            
            # Close Reason with PnL indicator and detailed snapshot tooltip
            is_profit = pos.unrealized_pnl_usd > 0
            if "STOP_LOSS" in pos.status or "MANUAL" in pos.status:
                if is_profit:
                    reason_str = f"✅ SL Hit {pos.unrealized_pnl_pct:+.1f}%"
                else:
                    reason_str = f"❌ SL Hit {pos.unrealized_pnl_pct:+.1f}%"
            elif "TRAILING" in pos.status:
                reason_str = f"🎪 Trailing {pos.unrealized_pnl_pct:+.1f}%"
            else:
                reason_str = f"❓ {pos.status} {pos.unrealized_pnl_pct:+.1f}%"
            
            reason_item = QTableWidgetItem(reason_str)
            reason_item.setForeground(QBrush(ColorHelper.POSITIVE if is_profit else ColorHelper.NEGATIVE))
            
            # Build detailed tooltip with close snapshot data
            if pos.close_snapshot:
                try:
                    snapshot = json.loads(pos.close_snapshot)
                    
                    tooltip_parts = [
                        f"📸 CLOSE SNAPSHOT:",
                        f"",
                        f"Reason: {snapshot.get('close_reason', 'Unknown')}",
                        f"Exit Price: ${snapshot.get('exit_price', 0):.6f}",
                        f"Entry Price: ${snapshot.get('entry_price', 0):.6f}",
                        f"Price Change: {snapshot.get('price_change_pct', 0):+.2f}%",
                        f"",
                        f"⏱️ TIMING:",
                        f"Duration: {snapshot.get('hold_duration_str', 'N/A')}",
                    ]
                    
                    # Add extreme prices if available
                    if 'max_price_seen' in snapshot:
                        tooltip_parts.append(f"")
                        tooltip_parts.append(f"📊 PRICE EXTREMES:")
                        tooltip_parts.append(f"Max Seen: ${snapshot.get('max_price_seen', 0):.6f}")
                        tooltip_parts.append(f"Min Seen: ${snapshot.get('min_price_seen', 0):.6f}")
                        
                        if 'distance_from_peak_pct' in snapshot:
                            tooltip_parts.append(f"Distance from Peak: {snapshot.get('distance_from_peak_pct', 0):.2f}%")
                        if 'distance_from_bottom_pct' in snapshot:
                            tooltip_parts.append(f"Distance from Bottom: {snapshot.get('distance_from_bottom_pct', 0):.2f}%")
                    
                    # Add recent candles summary
                    if snapshot.get('recent_candles'):
                        tooltip_parts.append(f"")
                        tooltip_parts.append(f"🕯️ RECENT CANDLES (last 5):")
                        for candle in snapshot['recent_candles']:
                            tooltip_parts.append(
                                f"  {candle['time']}: O${candle['open']:.4f} "
                                f"H${candle['high']:.4f} L${candle['low']:.4f} "
                                f"C${candle['close']:.4f}"
                            )
                    
                    # Add stop loss info
                    if 'stop_loss_price' in snapshot:
                        tooltip_parts.append(f"")
                        tooltip_parts.append(f"🛡️ STOP LOSS:")
                        tooltip_parts.append(f"SL Price: ${snapshot.get('stop_loss_price', 0):.6f}")
                        tooltip_parts.append(f"SL Distance from Entry: {snapshot.get('sl_distance_from_entry_pct', 0):+.2f}%")
                    
                    # Add trailing info
                    if snapshot.get('trailing_was_active'):
                        tooltip_parts.append(f"")
                        tooltip_parts.append(f"🎪 TRAILING: Was Active")
                        if snapshot.get('trailing_activation_time'):
                            tooltip_parts.append(f"Activated: {snapshot.get('trailing_activation_time', '')}")
                    
                    reason_item.setToolTip("\n".join(tooltip_parts))
                    
                except Exception as e:
                    reason_item.setToolTip(f"Close snapshot error: {e}")
            else:
                reason_item.setToolTip(f"Status: {pos.status}\nNo snapshot available")
            
            table.setItem(row, 4, reason_item)
            
            # Close Time
            if pos.close_time:
                close_dt = datetime.fromisoformat(pos.close_time)
                time_str = close_dt.strftime("%H:%M")
            else:
                time_str = "N/A"
            table.setItem(row, 5, QTableWidgetItem(time_str))
        
        # Center align
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                item = table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    
    def _update_closed_trades(self):
        """Update closed trades table - show ALL session trades"""
        # Get ALL trades from session (not just last 5)
        all_trades = self.session_stats.closed_trades  # All closed positions from session
        
        # Update group title with count
        self.closed_group.setTitle(f"📋 CLOSED POSITIONS (SESSION) - {len(all_trades)} trades")
        
        self.closed_table.setRowCount(0)
        
        if not all_trades:
            self.closed_table.setRowCount(1)
            item = QTableWidgetItem("No closed trades yet")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.closed_table.setItem(0, 0, item)
            self.closed_table.setSpan(0, 0, 1, 6)
            return
        
        self.closed_table.setRowCount(len(all_trades))
        
        for row, trade in enumerate(all_trades):
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
            
            # Build reason with profit/loss info
            is_profit = trade.pnl_usd > 0
            pnl_sign = "+" if is_profit else ""
            
            # Map reason to descriptive text
            if "STOP_LOSS" in trade.close_reason or "MANUAL" in trade.close_reason:
                if is_profit:
                    reason_str = f"✅ SL Hit {pnl_sign}{trade.pnl_pct:.1f}%"
                else:
                    reason_str = f"❌ SL Hit {pnl_sign}{trade.pnl_pct:.1f}%"
            elif "TRAILING" in trade.close_reason:
                reason_str = f"🎪 Trailing {pnl_sign}{trade.pnl_pct:.1f}%"
            elif "TAKE_PROFIT" in trade.close_reason:
                reason_str = f"🎯 TP Hit {pnl_sign}{trade.pnl_pct:.1f}%"
            else:
                reason_str = f"❓ Unknown {pnl_sign}{trade.pnl_pct:.1f}%"
            
            reason_item = QTableWidgetItem(reason_str)
            
            # Color based on profit/loss
            if is_profit:
                reason_item.setForeground(QBrush(ColorHelper.POSITIVE))
            else:
                reason_item.setForeground(QBrush(ColorHelper.NEGATIVE))
            
            self.closed_table.setItem(row, 4, reason_item)
            
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
        """Timer callback for periodic updates - NON-BLOCKING"""
        try:
            balance_summary = self.position_manager.safe_get_session_summary()
            current_balance = balance_summary.get('balance', 0)
            
            # Schedule async update without blocking GUI
            asyncio.ensure_future(self.update_dashboard_async(current_balance))
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
        
        # Log protection status (minimal)
        active_positions = self.position_manager.safe_get_all_active_positions()
        logging.info("=" * 80)
        logging.info(f"🛡️ SISTEMA DI PROTEZIONE ATTIVO - {len(active_positions)} posizioni monitorate")
        logging.info("=" * 80)
        
        # Show window (non-blocking with qasync)
        self.show()
        
        logging.info(f"📊 Dashboard running with qasync (update every {update_interval}s)")
