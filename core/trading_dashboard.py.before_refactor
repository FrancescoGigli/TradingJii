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
import config

# Import dashboard modules
from core.dashboard import ColorHelper, create_adaptive_memory_table, populate_adaptive_memory_table


class TradingDashboard(QMainWindow):
    """Live trading dashboard with PyQt6 GUI + qasync integration"""
    
    def __init__(self, position_manager, session_stats, exchange=None):
        super().__init__()
        
        self.position_manager = position_manager
        self.session_stats = session_stats
        self.exchange = exchange  # Store exchange for direct balance fetching
        self.last_update_time = datetime.now()
        self.update_interval = 30000  # 30 seconds - less lag
        self.update_timer = None
        self.is_running = False
        self.api_call_count = 0
        self._last_fetched_balance = 0.0  # Cache for balance
        
        # Cache per ridurre operazioni - SEPARATE per ogni tab
        self._cached_synced = []
        self._cached_session = []
        self._cached_closed = []
        self._cached_stats = {}
        self._cache_time_tabs = 0
        self._cache_ttl = 15  # seconds - OPTIMIZED: Less aggressive refresh (was 5s)
        
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
        
        # Add adaptive sizing section if enabled
        if config.ADAPTIVE_SIZING_ENABLED:
            self.adaptive_group = self._create_adaptive_sizing_section()
            main_layout.addWidget(self.adaptive_group)
        
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
    
    def _create_adaptive_sizing_section(self) -> QGroupBox:
        """Create adaptive position sizing status section"""
        group = QGroupBox("🎯 ADAPTIVE POSITION SIZING")
        layout = QGridLayout()
        layout.setSpacing(15)
        
        self.adaptive_labels = {}
        categories = ["Cycle", "Active Symbols", "Blocked", "Win Rate", "Avg Size"]
        
        for i, category in enumerate(categories):
            header = QLabel(category)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            layout.addWidget(header, 0, i)
            
            value = QLabel()
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value.setFont(QFont("Segoe UI", 9))
            layout.addWidget(value, 1, i)
            
            self.adaptive_labels[category] = value
        
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
        
        # TAB 4: ADAPTIVE MEMORY - Adaptive sizing performance tracking
        if config.ADAPTIVE_SIZING_ENABLED:
            self.adaptive_memory_table = create_adaptive_memory_table()
            self.tabs.addTab(self.adaptive_memory_table, "ADAPTIVE MEMORY (0)")
        
        layout.addWidget(self.tabs)
        group.setLayout(layout)
        return group
    
    def _create_position_table(self) -> QTableWidget:
        """Create a position table with standard columns"""
        table = QTableWidget()
        table.setColumnCount(17)  # Removed Vol% and ADX columns
        table.setHorizontalHeaderLabels([
            "Symbol", "Side", "IM", "Entry", "Current", "Stop Loss", "Type", "SL %", "PnL %", "PnL $", 
            "Liq. Price", "Time", "Status", "Conf%", "Weight", "Adaptive Status", "Open Reason"
        ])
        
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        
        # Performance optimizations for smoother scrolling and resizing
        table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        
        # PERFORMANCE FIX: Use Fixed sizes instead of ResizeToContents (MUCH FASTER!)
        header = table.horizontalHeader()
        # Fixed column widths for better performance
        table.setColumnWidth(0, 80)   # Symbol
        table.setColumnWidth(1, 110)  # Side
        table.setColumnWidth(2, 80)   # IM
        table.setColumnWidth(3, 90)   # Entry
        table.setColumnWidth(4, 90)   # Current
        table.setColumnWidth(5, 90)   # Stop Loss
        table.setColumnWidth(6, 80)   # Type
        table.setColumnWidth(7, 70)   # SL %
        table.setColumnWidth(8, 70)   # PnL %
        table.setColumnWidth(9, 90)   # PnL $
        table.setColumnWidth(10, 90)  # Liq. Price
        table.setColumnWidth(11, 70)  # Time
        table.setColumnWidth(12, 80)  # Status
        table.setColumnWidth(13, 60)  # Conf%
        table.setColumnWidth(14, 60)  # Weight
        table.setColumnWidth(15, 120) # Adaptive Status
        header.setSectionResizeMode(16, QHeaderView.ResizeMode.Stretch)  # Open Reason stretches
        
        # INTERACTIVE: Enable column sorting by clicking headers
        table.setSortingEnabled(True)
        header.setSortIndicatorShown(True)
        header.setSectionsClickable(True)
        
        return table
    
    def _create_closed_table(self) -> QTableWidget:
        """Create a closed positions table"""
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels([
            "Symbol", "ID", "IM", "Entry→Exit", "PnL", "Hold", "Close Reason", "Opened", "Closed"
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
        # Close Reason column (index 6) stretches to fill remaining space
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # Close Reason column
        
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
        self.closed_table.setColumnCount(9)
        self.closed_table.setHorizontalHeaderLabels([
            "Symbol", "ID", "IM", "Entry→Exit", "PnL", "Hold", "Close Reason", "Opened", "Closed"
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
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        
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
        
        # ✅ CORRECT FIX: Total PnL = Current Balance - Start Balance
        # This is the ONLY correct way to calculate total session PnL because:
        # 1. Current balance already includes all realized P&L
        # 2. It accounts for exchange fees automatically
        # 3. No double counting or accumulation errors
        pnl_usd = current_balance - self.session_stats.session_start_balance
        pnl_pct = (pnl_usd / self.session_stats.session_start_balance * 100) if self.session_stats.session_start_balance > 0 else 0.0
        
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
        
        # Update adaptive sizing section if enabled
        if config.ADAPTIVE_SIZING_ENABLED:
            self._update_adaptive_sizing()
    
    def _update_adaptive_sizing(self):
        """Update adaptive position sizing statistics"""
        try:
            from core.adaptive_position_sizing import global_adaptive_sizing
            
            if global_adaptive_sizing is None:
                return
            
            # Get stats from adaptive sizing
            stats = global_adaptive_sizing.get_memory_stats()
            
            # Cycle
            cycle_text = f"#{stats.get('cycle', 0)}"
            self.adaptive_labels["Cycle"].setText(cycle_text)
            
            # Active Symbols - Show REAL open positions (max 5)
            import config
            max_positions = config.MAX_CONCURRENT_POSITIONS
            current_open = self.position_manager.safe_get_position_count()
            
            active_text = f"{current_open}/{max_positions}"
            active_label = self.adaptive_labels["Active Symbols"]
            active_label.setText(active_text)
            
            # Color based on capacity
            if current_open >= max_positions:
                active_label.setStyleSheet("color: #F59E0B;")  # Orange when full
            elif current_open > 0:
                active_label.setStyleSheet("color: #22C55E;")  # Green when active
            else:
                active_label.setStyleSheet("color: #E6EEF8;")  # White when empty
            
            # Blocked
            blocked = stats.get('blocked_symbols', 0)
            blocked_text = f"{blocked}"
            blocked_label = self.adaptive_labels["Blocked"]
            blocked_label.setText(blocked_text)
            if blocked > 0:
                blocked_label.setStyleSheet("color: #EF4444;")
            else:
                blocked_label.setStyleSheet("color: #E6EEF8;")
            
            # Win Rate
            win_rate = stats.get('win_rate', 0)
            win_rate_text = f"{win_rate:.1f}%"
            win_rate_label = self.adaptive_labels["Win Rate"]
            win_rate_label.setText(win_rate_text)
            if win_rate >= 50:
                win_rate_label.setStyleSheet("color: #22C55E;")
            elif win_rate >= 40:
                win_rate_label.setStyleSheet("color: #F59E0B;")
            else:
                win_rate_label.setStyleSheet("color: #EF4444;")
            
            # Average Size
            if total > 0:
                # Calculate average current size from memory
                total_size = sum(m.current_size for m in global_adaptive_sizing.symbol_memory.values())
                avg_size = total_size / total if total > 0 else 0
                avg_size_text = f"${avg_size:.2f}"
            else:
                avg_size_text = "$0.00"
            self.adaptive_labels["Avg Size"].setText(avg_size_text)
            
        except Exception as e:
            logging.debug(f"Error updating adaptive sizing stats: {e}")
    
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
        
        # Update adaptive memory tab count if enabled
        if config.ADAPTIVE_SIZING_ENABLED:
            try:
                from core.adaptive_position_sizing import global_adaptive_sizing
                memory_count = len(global_adaptive_sizing.symbol_memory) if global_adaptive_sizing else 0
                self.tabs.setTabText(3, f"ADAPTIVE MEMORY ({memory_count})")
            except:
                self.tabs.setTabText(3, "ADAPTIVE MEMORY (0)")
        
        # Update group title
        total_active = len(all_active_positions)
        self.positions_group.setTitle(f"🎯 POSITIONS (Active: {total_active}, Closed: {len(self._cached_closed)})")
        
        # Populate each tab
        self._populate_position_table(self.all_active_table, all_active_positions, "ALL ACTIVE")
        self._populate_position_table(self.session_table, self._cached_session, "OPENED THIS SESSION")
        self._populate_closed_tab(self.closed_tab_table, self._cached_closed)
        
        # Populate adaptive memory tab if enabled
        if config.ADAPTIVE_SIZING_ENABLED:
            try:
                from core.adaptive_position_sizing import global_adaptive_sizing
                populate_adaptive_memory_table(self.adaptive_memory_table, global_adaptive_sizing)
            except Exception as e:
                logging.debug(f"Error populating adaptive memory tab: {e}")
    
    def _populate_position_table(self, table: QTableWidget, positions: list, tab_name: str):
        """Populate a position table with position data"""
        
        # PERFORMANCE FIX: Disable ALL expensive operations during populate
        table.setUpdatesEnabled(False)
        table.setSortingEnabled(False)  # CRITICAL: Disable sorting during updates
        
        try:
            # OPTIMIZATION: Only rebuild table if count changed
            if table.rowCount() != len(positions):
                table.setRowCount(0)
            
            if not positions:
                table.setRowCount(1)
                item = QTableWidgetItem(f"No {tab_name.lower()} positions")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(0, 0, item)
                table.setSpan(0, 0, 1, 18)  # BUG FIX: 18 columns, not 9
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
                # 🔧 FIX: Use REAL IM from Bybit if available
                if hasattr(pos, 'real_initial_margin') and pos.real_initial_margin is not None:
                    # Use real IM from Bybit
                    initial_margin = pos.real_initial_margin
                    im_source = "Bybit"
                else:
                    # Fallback: calculate from position size
                    initial_margin = pos.position_size / pos.leverage if pos.position_size > 0 else 0
                    im_source = "Calculated"
                
                im_item = QTableWidgetItem(f"${initial_margin:.2f}")
                im_item.setToolTip(
                    f"Initial Margin (IM) [{im_source}]\n\n"
                    f"Margine bloccato per questa posizione\n"
                    f"Capital allocato: ${initial_margin:.2f}\n\n"
                    f"Source: {im_source}\n"
                    f"{'✅ Read from Bybit (exact value)' if im_source == 'Bybit' else '⚠️ Calculated (may differ slightly from Bybit)'}"
                )
                im_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 2, im_item)
            
                # Entry & Current (IMPROVEMENT 3 - smart formatting)
                table.setItem(row, 3, QTableWidgetItem(ColorHelper.format_price(pos.entry_price)))
                table.setItem(row, 4, QTableWidgetItem(ColorHelper.format_price(pos.current_price)))
                
                # Stop Loss - Column 5 - Use REAL SL from Bybit if available
                if hasattr(pos, 'real_stop_loss') and pos.real_stop_loss is not None:
                    # Use real SL from Bybit (most accurate)
                    stop_loss_display = pos.real_stop_loss
                    sl_source = "Bybit"
                else:
                    # Fallback to calculated SL
                    stop_loss_display = pos.stop_loss
                    sl_source = "Calculated"
                
                sl_item = QTableWidgetItem(ColorHelper.format_price(stop_loss_display))
                sl_item.setToolTip(
                    f"Stop Loss Price [{sl_source}]\n"
                    f"${stop_loss_display:.6f}\n\n"
                    f"{'✅ Read from Bybit (exact value)' if sl_source == 'Bybit' else '⚠️ Calculated (may differ from Bybit)'}"
                )
                sl_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 5, sl_item)
            
                # Calculate ROE
                roe_pct = pos.unrealized_pnl_pct
                
                # Check trailing
                is_trailing_active = (hasattr(pos, 'trailing_data') and 
                                     pos.trailing_data and 
                                     pos.trailing_data.enabled)
                
                # Type - Column 6 (IMPROVEMENT 4)
                type_item = QTableWidgetItem()
                
                # Calculate REAL SL percentage for tooltip
                real_sl_price_pct = abs((pos.stop_loss - pos.entry_price) / pos.entry_price) * 100
                real_sl_roe_pct = real_sl_price_pct * pos.leverage
                
                if is_trailing_active:
                    type_item.setText("TRAILING")
                    type_item.setForeground(QBrush(ColorHelper.POSITIVE))
                    type_item.setToolTip(
                        f"Trailing Stop: Stop loss dinamico\n"
                        f"Current SL: ${pos.stop_loss:.6f}\n"
                        f"Risk: -{real_sl_price_pct:.2f}% price = -{real_sl_roe_pct:.1f}% ROE"
                    )
                else:
                    type_item.setText("FIXED")
                    type_item.setForeground(QBrush(ColorHelper.INFO))
                    type_item.setToolTip(
                        f"Fixed Stop Loss\n"
                        f"SL Price: ${pos.stop_loss:.6f}\n"
                        f"Risk: -{real_sl_price_pct:.2f}% price × {pos.leverage}x lev = -{real_sl_roe_pct:.1f}% ROE"
                    )
                type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 6, type_item)
            
                # SL % - Column 7 - ALWAYS show as NEGATIVE protection (intuitive)
                sl_pct_item = QTableWidgetItem()
                
                # Use REAL stop loss from Bybit if available
                sl_price = pos.real_stop_loss if (hasattr(pos, 'real_stop_loss') and pos.real_stop_loss) else pos.stop_loss
                
                # Calculate RISK percentage (always shown as negative for protection)
                # For LONG: SL is below entry → negative %
                # For SHORT: SL is above entry → but we show it as negative % for consistency
                if pos.side in ['buy', 'long']:
                    # LONG: (SL - Entry) / Entry × 100 = negative value
                    risk_pct = ((sl_price - pos.entry_price) / pos.entry_price) * 100
                else:
                    # SHORT: (Entry - SL) / Entry × 100 = show as negative for consistency
                    # If SL is above entry (correct for SHORT), this gives negative value
                    risk_pct = ((pos.entry_price - sl_price) / pos.entry_price) * 100
                
                # Check if trailing is active
                is_trailing_active = (hasattr(pos, 'trailing_data') and 
                                     pos.trailing_data and 
                                     pos.trailing_data.enabled)
                
                # Display the value (should always be negative or near zero for protection)
                sl_pct_item.setText(ColorHelper.format_pct(risk_pct))
                
                # Build tooltip
                side_type = "LONG" if pos.side in ['buy', 'long'] else "SHORT"
                sl_roe_pct = risk_pct * pos.leverage
                
                if is_trailing_active:
                    tooltip_text = (
                        f"🎪 TRAILING STOP - {side_type}\n\n"
                        f"Stop Loss: ${sl_price:.6f}\n"
                        f"Entry: ${pos.entry_price:.6f}\n"
                        f"Risk: {risk_pct:.2f}% price\n"
                        f"Impact on Margin: {sl_roe_pct:.1f}% ROE\n\n"
                        f"✅ Trailing attivo - protegge profitti"
                    )
                else:
                    tooltip_text = (
                        f"🛡️ FIXED STOP LOSS - {side_type}\n\n"
                        f"Stop Loss: ${sl_price:.6f}\n"
                        f"Entry: ${pos.entry_price:.6f}\n"
                        f"Risk: {risk_pct:.2f}% price\n"
                        f"Impact on Margin: {sl_roe_pct:.1f}% ROE\n\n"
                        f"⚠️ Protezione base attiva"
                    )
                
                sl_pct_item.setToolTip(tooltip_text)
                
                # Color based on trailing status
                if is_trailing_active:
                    sl_pct_item.setForeground(QBrush(ColorHelper.POSITIVE))  # Verde se trailing
                else:
                    sl_pct_item.setForeground(QBrush(ColorHelper.NEGATIVE))  # Rosso se fixed
                
                sl_pct_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 7, sl_pct_item)
                
                # PnL % - Column 8 (IMPROVEMENT 3)
                pnl_pct_item = QTableWidgetItem(ColorHelper.format_pct(pos.unrealized_pnl_pct))
                ColorHelper.color_cell(pnl_pct_item, pos.unrealized_pnl_usd)
                pnl_pct_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 8, pnl_pct_item)
                
                # PnL $ - Column 9 (IMPROVEMENT 3)
                pnl_usd_item = QTableWidgetItem(ColorHelper.format_usd(pos.unrealized_pnl_usd))
                ColorHelper.color_cell(pnl_usd_item, pos.unrealized_pnl_usd)
                pnl_usd_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 9, pnl_usd_item)
                
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
                table.setItem(row, 10, liq_item)
                
                # Time in Position - Column 11
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
                
                # NEW: Risk Parameters (Conf%, Vol%, ADX, Weight) - Columns 13-16
                # Column 13: Confidence %
                confidence = getattr(pos, 'confidence', 0.0)
                conf_item = QTableWidgetItem(f"{confidence:.0%}")
                if confidence >= 0.75:
                    conf_item.setForeground(QBrush(ColorHelper.POSITIVE))  # Green for high conf
                elif confidence >= 0.65:
                    conf_item.setForeground(QBrush(ColorHelper.INFO))  # Blue for medium
                else:
                    conf_item.setForeground(QBrush(ColorHelper.WARNING))  # Orange for low
                conf_item.setToolTip(f"ML Model Confidence: {confidence:.1%}\nHigher = More confident prediction")
                conf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 13, conf_item)
                
                # Column 14: Weight - Simplified (just show confidence as weight proxy)
                weight_item = QTableWidgetItem(f"{confidence:.0%}")
                if confidence >= 0.75:
                    weight_item.setForeground(QBrush(ColorHelper.POSITIVE))
                elif confidence >= 0.65:
                    weight_item.setForeground(QBrush(ColorHelper.INFO))
                else:
                    weight_item.setForeground(QBrush(ColorHelper.WARNING))
                weight_item.setToolTip(f"Position Weight (based on ML confidence): {confidence:.0%}")
                weight_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 14, weight_item)
                
                # Column 15: Adaptive Status - Shows if position size is improving/declining
                adaptive_item = QTableWidgetItem()
                
                # Try to get adaptive sizing memory for this symbol
                try:
                    if config.ADAPTIVE_SIZING_ENABLED:
                        from core.adaptive_position_sizing import global_adaptive_sizing
                        
                        if global_adaptive_sizing and pos.symbol in global_adaptive_sizing.symbol_memory:
                            memory = global_adaptive_sizing.symbol_memory[pos.symbol]
                            
                            # Check if blocked
                            if memory.blocked_cycles_left > 0:
                                adaptive_item.setText(f"🚫 BLOCKED\n{memory.blocked_cycles_left} cycles")
                                adaptive_item.setForeground(QBrush(ColorHelper.NEGATIVE))
                                adaptive_item.setToolTip(
                                    f"Symbol is BLOCKED for {memory.blocked_cycles_left} more cycles\n\n"
                                    f"Reason: Last trade was a loss ({memory.last_pnl_pct:+.1f}%)\n"
                                    f"Size reset to base: ${memory.base_size:.2f}\n"
                                    f"Will be unblocked after {memory.blocked_cycles_left} cycles\n\n"
                                    f"History: {memory.wins}W / {memory.losses}L"
                                )
                            else:
                                # Calculate size evolution
                                base_size = memory.base_size
                                current_size = memory.current_size
                                size_change_pct = ((current_size - base_size) / base_size * 100) if base_size > 0 else 0
                                
                                # Determine status based on size evolution
                                if size_change_pct > 5:
                                    # Growing (winning)
                                    adaptive_item.setText(f"📈 GROWING\n+{size_change_pct:.1f}%")
                                    adaptive_item.setForeground(QBrush(ColorHelper.POSITIVE))
                                    adaptive_item.setToolTip(
                                        f"Symbol size is GROWING (performing well)\n\n"
                                        f"Current size: ${current_size:.2f}\n"
                                        f"Base size: ${base_size:.2f}\n"
                                        f"Growth: +{size_change_pct:.1f}%\n\n"
                                        f"Last PnL: {memory.last_pnl_pct:+.1f}%\n"
                                        f"History: {memory.wins}W / {memory.losses}L\n"
                                        f"Win rate: {(memory.wins / memory.total_trades * 100):.0f}%" if memory.total_trades > 0 else "No trades yet"
                                    )
                                elif size_change_pct < -5:
                                    # Shrinking (not expected, but handle it)
                                    adaptive_item.setText(f"📉 RESET\n{size_change_pct:.1f}%")
                                    adaptive_item.setForeground(QBrush(ColorHelper.WARNING))
                                    adaptive_item.setToolTip(
                                        f"Symbol was RESET after a loss\n\n"
                                        f"Current size: ${current_size:.2f}\n"
                                        f"Base size: ${base_size:.2f}\n"
                                        f"Change: {size_change_pct:.1f}%\n\n"
                                        f"History: {memory.wins}W / {memory.losses}L"
                                    )
                                else:
                                    # Stable (at base level)
                                    adaptive_item.setText(f"📊 STABLE\n${current_size:.2f}")
                                    adaptive_item.setForeground(QBrush(ColorHelper.INFO))
                                    win_rate_text = f"{(memory.wins / memory.total_trades * 100):.0f}%" if memory.total_trades > 0 else "New"
                                    adaptive_item.setToolTip(
                                        f"Symbol at BASE size level\n\n"
                                        f"Current size: ${current_size:.2f}\n"
                                        f"Base size: ${base_size:.2f}\n\n"
                                        f"Last PnL: {memory.last_pnl_pct:+.1f}%" if memory.last_pnl_pct != 0 else "First trade\n\n"
                                        f"History: {memory.wins}W / {memory.losses}L\n"
                                        f"Win rate: {win_rate_text}"
                                    )
                        else:
                            # Symbol not in memory yet (new position)
                            adaptive_item.setText("🆕 NEW")
                            adaptive_item.setForeground(QBrush(ColorHelper.NEUTRAL))
                            adaptive_item.setToolTip(
                                "New symbol - not yet in adaptive memory\n\n"
                                "Will be tracked after first close\n"
                                "Starting with base size"
                            )
                    else:
                        # Adaptive sizing disabled
                        adaptive_item.setText("N/A")
                        adaptive_item.setForeground(QBrush(ColorHelper.NEUTRAL))
                        adaptive_item.setToolTip("Adaptive sizing is disabled")
                        
                except Exception as e:
                    adaptive_item.setText("ERROR")
                    adaptive_item.setForeground(QBrush(ColorHelper.WARNING))
                    adaptive_item.setToolTip(f"Error getting adaptive status: {e}")
                
                adaptive_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 15, adaptive_item)
                
                # Column 16: Open Reason - Shows ML prediction results for SESSION positions or "Already Open" for SYNCED
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
                table.setItem(row, 16, reason_item)  # Column 16 (last column)
                
                # Row highlighting (IMPROVEMENT 2)
                row_background = None
                if roe_pct < -40:
                    row_background = QColor("#3D0000")  # Red
                elif roe_pct >= 10.0 and not is_trailing_active:
                    row_background = QColor("#3D3D00")  # Yellow
                elif is_trailing_active and roe_pct >= 10.0:
                    row_background = QColor("#003D00")  # Green
                
                if row_background:
                    for col in range(17):  # 17 columns total (0-16)
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
            # Re-enable updates AND sorting
            table.setSortingEnabled(True)  # CRITICAL: Re-enable sorting AFTER populate
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
                table.setSpan(0, 0, 1, 9)
                return
            
            table.setRowCount(len(closed_positions))
        
        if not closed_positions:
            return
        
        for row, pos in enumerate(closed_positions):
            # Symbol
            symbol_short = pos.symbol.replace('/USDT:USDT', '')
            table.setItem(row, 0, QTableWidgetItem(symbol_short))
            
            # ID - Extract time from position_id
            pos_id = getattr(pos, 'position_id', '')
            if pos_id and '_' in pos_id:
                parts = pos_id.split('_')
                if len(parts) >= 3:
                    time_part = parts[-2]  # "093445"
                    id_display = time_part[:4]  # "0934" (HH:MM)
                else:
                    id_display = pos_id[-8:]
            else:
                id_display = "N/A"
            table.setItem(row, 1, QTableWidgetItem(id_display))
            
            # Initial Margin (IM)
            if hasattr(pos, 'real_initial_margin') and pos.real_initial_margin is not None:
                initial_margin = pos.real_initial_margin
                im_source = "Bybit"
            else:
                initial_margin = pos.position_size / pos.leverage if pos.position_size > 0 else 0
                im_source = "Calculated"
            
            im_item = QTableWidgetItem(f"${initial_margin:.2f}")
            im_item.setToolTip(
                f"Initial Margin (IM) [{im_source}]\n"
                f"Margine utilizzato per questa posizione\n"
                f"${initial_margin:.2f}"
            )
            im_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 2, im_item)
            
            # Entry → Exit
            entry_exit = f"${pos.entry_price:.4f} → ${pos.current_price:.4f}"
            table.setItem(row, 3, QTableWidgetItem(entry_exit))
            
            # PnL with ROE% clarification
            roe_pct = pos.unrealized_pnl_pct
            # Calculate price change % (without leverage)
            price_change_pct = roe_pct / pos.leverage if hasattr(pos, 'leverage') and pos.leverage > 0 else roe_pct
            
            pnl_text = f"ROE {ColorHelper.format_pct(roe_pct)} | {ColorHelper.format_usd(pos.unrealized_pnl_usd)}"
            pnl_item = QTableWidgetItem(pnl_text)
            ColorHelper.color_cell(pnl_item, pos.unrealized_pnl_usd)
            
            # Tooltip explaining the difference
            pnl_item.setToolTip(
                f"💰 PnL Breakdown:\n\n"
                f"ROE% (Return on Equity): {roe_pct:+.2f}%\n"
                f"  = Profit/Loss on your margin (with leverage)\n\n"
                f"Price Change: {price_change_pct:+.2f}%\n"
                f"  = Actual {pos.symbol} price movement\n\n"
                f"Leverage: {pos.leverage if hasattr(pos, 'leverage') else 10}x\n"
                f"Formula: ROE% = Price% × Leverage"
            )
            
            table.setItem(row, 4, pnl_item)
            
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
            table.setItem(row, 5, QTableWidgetItem(hold_str))
            
            # Close Reason with PnL indicator and detailed snapshot tooltip
            is_profit = pos.unrealized_pnl_usd > 0
            
            # Check if this was a stop loss hit
            if "STOP_LOSS" in pos.status or "MANUAL" in pos.status:
                # Se è positivo, era un trailing stop che ha protetto i guadagni
                if is_profit:
                    reason_str = f"✅ Trailing Stop Hit with Gain {pos.unrealized_pnl_pct:+.1f}%"
                else:
                    # Se è negativo, era uno stop loss fisso (circa -50% con leva)
                    reason_str = f"❌ SL Hit {pos.unrealized_pnl_pct:+.1f}%"
            elif "TRAILING" in pos.status:
                # Trailing stop esplicito
                if is_profit:
                    reason_str = f"✅ Trailing Stop Hit with Gain {pos.unrealized_pnl_pct:+.1f}%"
                else:
                    reason_str = f"🎪 Trailing {pos.unrealized_pnl_pct:+.1f}%"
            else:
                reason_str = f"❓ {pos.status} {pos.unrealized_pnl_pct:+.1f}%"
            
            reason_item = QTableWidgetItem(reason_str)
            reason_item.setForeground(QBrush(ColorHelper.POSITIVE if is_profit else ColorHelper.NEGATIVE))
            table.setItem(row, 6, reason_item)
            
            # Opened timestamp with date
            if pos.entry_time:
                try:
                    entry_dt = datetime.fromisoformat(pos.entry_time)
                    opened_str = entry_dt.strftime("%d/%m %H:%M:%S")
                except:
                    opened_str = "N/A"
            else:
                opened_str = "N/A"
            table.setItem(row, 7, QTableWidgetItem(opened_str))
            
            # Closed timestamp with date
            if pos.close_time:
                try:
                    close_dt = datetime.fromisoformat(pos.close_time)
                    closed_str = close_dt.strftime("%d/%m %H:%M:%S")
                except:
                    closed_str = "N/A"
            else:
                closed_str = "N/A"
            table.setItem(row, 8, QTableWidgetItem(closed_str))
            
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
        
        # CRITICAL FIX: Reverse order to show most recent trades FIRST
        all_trades = list(reversed(all_trades))
        
        # Update group title with count
        self.closed_group.setTitle(f"📋 CLOSED POSITIONS (SESSION) - {len(all_trades)} trades")
        
        self.closed_table.setRowCount(0)
        
        if not all_trades:
            self.closed_table.setRowCount(1)
            item = QTableWidgetItem("No closed trades yet")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.closed_table.setItem(0, 0, item)
            self.closed_table.setSpan(0, 0, 1, 8)  # BUG FIX: 8 columns, not 6
            return
        
        self.closed_table.setRowCount(len(all_trades))
        
        for row, trade in enumerate(all_trades):
            # Column 0: Symbol
            self.closed_table.setItem(row, 0, QTableWidgetItem(trade.symbol))
            
            # Column 1: ID - Extract from close_time as timestamp
            if trade.close_time:
                try:
                    close_dt = datetime.fromisoformat(trade.close_time)
                    id_display = close_dt.strftime("%H%M")  # "1550" format
                except:
                    id_display = "N/A"
            else:
                id_display = "N/A"
            self.closed_table.setItem(row, 1, QTableWidgetItem(id_display))
            
            # Column 2: IM (Initial Margin) - Calculate from trade data
            # Best effort: calculate from PnL and leverage
            if hasattr(trade, 'leverage') and trade.leverage > 0:
                # Estimate IM from entry price assuming standard position size
                initial_margin = (trade.entry_price * 10) / trade.leverage  # Rough estimate
            else:
                initial_margin = 0
            
            im_item = QTableWidgetItem(f"${initial_margin:.2f}")
            im_item.setToolTip(f"Initial Margin (Estimated): ${initial_margin:.2f}")
            im_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.closed_table.setItem(row, 2, im_item)
            
            # Column 3: Entry→Exit
            entry_exit = f"${trade.entry_price:,.4f} → ${trade.exit_price:,.4f}"
            self.closed_table.setItem(row, 3, QTableWidgetItem(entry_exit))
            
            # Column 4: PnL
            # Calculate price change % (without leverage)
            price_change_pct = trade.pnl_pct / trade.leverage if trade.leverage > 0 else trade.pnl_pct
            
            pnl_item = QTableWidgetItem(f"ROE {trade.pnl_pct:+.2f}% | ${trade.pnl_usd:+.2f}")
            ColorHelper.color_cell(pnl_item, trade.pnl_usd)
            
            # Tooltip explaining ROE vs Price Change
            pnl_item.setToolTip(
                f"💰 PnL Breakdown:\n\n"
                f"ROE% (Return on Equity): {trade.pnl_pct:+.2f}%\n"
                f"  = Your actual profit/loss on margin\n\n"
                f"Price Change: {price_change_pct:+.2f}%\n"
                f"  = {trade.symbol} price movement\n\n"
                f"Leverage: {trade.leverage}x\n\n"
                f"Example: 7% price × 10x lev = 70% ROE"
            )
            self.closed_table.setItem(row, 4, pnl_item)
            
            # Column 5: Hold Time
            if trade.hold_time_minutes < 60:
                hold_str = f"{trade.hold_time_minutes}m"
            else:
                hours = trade.hold_time_minutes // 60
                minutes = trade.hold_time_minutes % 60
                hold_str = f"{hours}h {minutes}m"
            self.closed_table.setItem(row, 5, QTableWidgetItem(hold_str))
            
            # Column 6: Close Reason
            is_profit = trade.pnl_usd > 0
            pnl_sign = "+" if is_profit else ""
            
            # Map reason to descriptive text with improved logic
            if "STOP_LOSS" in trade.close_reason or "MANUAL" in trade.close_reason:
                if is_profit:
                    reason_str = f"✅ Trailing Stop Hit with Gain {pnl_sign}{trade.pnl_pct:.1f}%"
                else:
                    reason_str = f"❌ SL Hit {pnl_sign}{trade.pnl_pct:.1f}%"
            elif "TRAILING" in trade.close_reason:
                if is_profit:
                    reason_str = f"✅ Trailing Stop Hit with Gain {pnl_sign}{trade.pnl_pct:.1f}%"
                else:
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
            
            self.closed_table.setItem(row, 6, reason_item)
            
            # Column 7: Opened timestamp with date
            if trade.entry_time:
                try:
                    entry_dt = datetime.fromisoformat(trade.entry_time)
                    opened_str = entry_dt.strftime("%d/%m %H:%M:%S")
                except:
                    opened_str = "N/A"
            else:
                opened_str = "N/A"
            self.closed_table.setItem(row, 7, QTableWidgetItem(opened_str))
            
            # Column 8: Closed timestamp with date
            if trade.close_time:
                try:
                    close_dt = datetime.fromisoformat(trade.close_time)
                    closed_str = close_dt.strftime("%d/%m %H:%M:%S")
                except:
                    closed_str = "N/A"
            else:
                closed_str = "N/A"
            self.closed_table.setItem(row, 8, QTableWidgetItem(closed_str))
        
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
        """Timer callback for periodic updates - NON-BLOCKING with real balance fetch"""
        try:
            # Schedule async update that will fetch fresh balance
            asyncio.ensure_future(self._async_timer_update())
            self.api_call_count += 1
        except Exception as e:
            logging.error(f"Error in timer update: {e}")
    
    async def _async_timer_update(self):
        """Async timer update - OPTIMIZED: Read from Position Manager only"""
        try:
            # OPTIMIZATION: Dashboard NO LONGER fetches balance directly from Bybit
            # Balance is kept up-to-date by Balance Sync Loop in trading_engine
            # Dashboard just reads the cached value from Position Manager
            
            balance_summary = self.position_manager.safe_get_session_summary()
            current_balance = balance_summary.get('balance', 0)
            
            # Update dashboard with cached balance (still REAL data from Bybit)
            await self.update_dashboard_async(current_balance)
            
            logging.debug(f"💰 Dashboard: Using cached balance ${current_balance:.2f} (synced by Balance Loop)")
            
        except Exception as e:
            logging.error(f"Error in async timer update: {e}")
    
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
    
    async def run_live_dashboard(self, exchange, update_interval: int = 60):
        """Run live dashboard with qasync integration (async)"""
        self.update_interval = update_interval * 1000
        self.is_running = True
        
        # Store exchange reference (not used for fetching anymore)
        self.exchange = exchange
        
        # OPTIMIZATION: Initial balance from Position Manager only
        # Balance is already synced by trading_engine's balance sync loop
        balance_summary = self.position_manager.safe_get_session_summary()
        current_balance = balance_summary.get('balance', 0)
        
        logging.info(f"💰 Dashboard initialized - Balance: ${current_balance:.2f} (from Position Manager)")
        
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
