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

# Import dashboard modules (REFACTORED)
from core.dashboard import (
    ColorHelper,
    PositionTablePopulator,
    ClosedTablePopulator,
    create_adaptive_memory_table,
    populate_adaptive_memory_table,
    create_ai_analysis_table,
    AIAnalysisTabPopulator
)


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
        
        # TAB 5: AI ANALYSIS - ChatGPT trade analysis
        self.ai_analysis_table = create_ai_analysis_table()
        self.tabs.addTab(self.ai_analysis_table, "🤖 AI ANALYSIS (0)")
        
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
        
        # Populate AI Analysis tab
        try:
            AIAnalysisTabPopulator.populate(self.ai_analysis_table, max_rows=50)
            
            # Update tab title with count from database
            try:
                db_path = Path("trade_analysis.db")
                if db_path.exists():
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM trade_analyses")
                    count = cursor.fetchone()[0]
                    conn.close()
                    tab_index = 4 if config.ADAPTIVE_SIZING_ENABLED else 3
                    self.tabs.setTabText(tab_index, f"🤖 AI ANALYSIS ({count})")
            except:
                pass
        except Exception as e:
            logging.debug(f"Error populating AI analysis tab: {e}")
    
    def _populate_position_table(self, table: QTableWidget, positions: list, tab_name: str):
        """Populate a position table with position data - REFACTORED"""
        # Delegate to dedicated populator module
        PositionTablePopulator.populate(table, positions, tab_name)

    def _populate_closed_tab(self, table: QTableWidget, closed_positions: list):
        """Populate closed positions tab - REFACTORED"""
        # Delegate to dedicated populator module
        ClosedTablePopulator.populate(table, closed_positions)

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
