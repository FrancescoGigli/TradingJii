#!/usr/bin/env python3
"""
📊 TRADING DASHBOARD - LIVE UI (TKINTER VERSION)

Complete dashboard with tkinter GUI for real-time monitoring:
- Session statistics (Win/Loss, PnL, Win Rate)
- Active positions with trailing status
- Last closed trades
- Portfolio summary

Modern GUI with professional dark theme
"""

import logging
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import List, Optional
import threading


class TradingDashboard:
    """
    Live trading dashboard with tkinter GUI
    
    Features:
    - Auto-refreshing UI (every 30s)
    - Session statistics
    - Active positions monitoring
    - Closed trades history
    - Professional dark theme
    - Zebra-striped tables
    - Clean, readable layout
    """
    
    def __init__(self, position_manager, session_stats):
        self.position_manager = position_manager
        self.session_stats = session_stats
        self.last_update_time = datetime.now()
        self.root = None
        self.update_interval = 30000  # 30 seconds in milliseconds
        self.is_running = False
        
        logging.info("📊 TradingDashboard initialized (tkinter version)")
    
    def create_window(self):
        """Create main dashboard window with professional dark theme"""
        self.root = tk.Tk()
        self.root.title("🎪 TRADING BOT - LIVE DASHBOARD")
        self.root.geometry("1400x900")
        self.root.configure(bg='#0B0F14')
        
        # Configure ttk Style with consistent dark theme
        style = ttk.Style()
        style.theme_use('clam')
        
        # Base style for all widgets
        style.configure('.',
                       background='#0B0F14',
                       foreground='#E6EEF8',
                       fieldbackground='#121822')
        
        # Treeview style (tables) with dark theme
        style.configure('Treeview',
                       background='#121822',
                       fieldbackground='#121822',
                       foreground='#E6EEF8',
                       bordercolor='#2F3A4D',
                       borderwidth=1,
                       rowheight=25,
                       font=('Segoe UI', 9))
        
        style.configure('Treeview.Heading',
                       background='#1F2A37',
                       foreground='#E6EEF8',
                       bordercolor='#2F3A4D',
                       relief='flat',
                       font=('Segoe UI', 10, 'bold'))
        
        style.map('Treeview',
                 background=[('selected', '#1B2430')],
                 foreground=[('selected', '#E6EEF8')])
        
        # Label styles
        style.configure('Title.TLabel', 
                       font=('Segoe UI', 16, 'bold'),
                       foreground='#06B6D4',
                       background='#0B0F14')
        
        # Create main container
        main_frame = tk.Frame(self.root, bg='#0B0F14')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header section
        self.header_frame = self._create_header_section(main_frame)
        self.header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Statistics section
        self.stats_frame = self._create_statistics_section(main_frame)
        self.stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Active positions section
        self.positions_frame = self._create_positions_section(main_frame)
        self.positions_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Closed trades section
        self.closed_frame = self._create_closed_trades_section(main_frame)
        self.closed_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Footer section
        self.footer_frame = self._create_footer_section(main_frame)
        self.footer_frame.pack(fill=tk.X)
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        
        logging.info("📊 Dashboard window created")
    
    def _create_header_section(self, parent):
        """Create header section with session info"""
        frame = tk.LabelFrame(parent, text="📊 DASHBOARD HEADER", 
                             bg='#1B2430', fg='#06B6D4',
                             font=('Segoe UI', 10, 'bold'),
                             borderwidth=1, relief=tk.SOLID)
        
        self.header_label = tk.Label(frame, text="", 
                                     font=('Segoe UI', 10),
                                     fg='#A9B4C0', bg='#1B2430',
                                     justify=tk.LEFT)
        self.header_label.pack(pady=10, padx=10, anchor=tk.W)
        
        return frame
    
    def _create_statistics_section(self, parent):
        """Create statistics section"""
        frame = tk.LabelFrame(parent, text="📈 SESSION STATISTICS",
                             bg='#121822', fg='#06B6D4',
                             font=('Segoe UI', 10, 'bold'),
                             borderwidth=1, relief=tk.SOLID)
        
        # Create grid for statistics
        stats_grid = tk.Frame(frame, bg='#121822')
        stats_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # Configure columns
        for i in range(5):
            stats_grid.columnconfigure(i, weight=1, uniform="column")
        
        # Create labels for each stat category
        categories = ["Balance", "Trades", "Win Rate", "Total PnL", "Best/Worst"]
        self.stat_labels = {}
        
        for i, category in enumerate(categories):
            # Category header
            header = tk.Label(stats_grid, text=category,
                            font=('Segoe UI', 10, 'bold'),
                            fg='#7E8A99', bg='#121822')
            header.grid(row=0, column=i, sticky='ew', padx=5, pady=(0, 5))
            
            # Value label
            value = tk.Label(stats_grid, text="",
                           font=('Segoe UI', 9),
                           fg='#E6EEF8', bg='#121822',
                           justify=tk.LEFT)
            value.grid(row=1, column=i, sticky='ew', padx=5)
            
            self.stat_labels[category] = value
        
        return frame
    
    def _create_positions_section(self, parent):
        """Create active positions section with treeview"""
        frame = tk.LabelFrame(parent, text="🎯 ACTIVE POSITIONS",
                             bg='#121822', fg='#06B6D4',
                             font=('Segoe UI', 10, 'bold'),
                             borderwidth=1, relief=tk.SOLID)
        
        # Create treeview
        columns = ("Symbol", "Side", "Entry", "Current", "Stop Loss", "PnL", "Trailing")
        self.positions_tree = ttk.Treeview(frame, columns=columns, show='headings', height=8)
        
        # Configure columns
        column_widths = [100, 140, 120, 120, 160, 170, 100]
        for col, width in zip(columns, column_widths):
            self.positions_tree.heading(col, text=col)
            self.positions_tree.column(col, width=width, anchor=tk.CENTER)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.positions_tree.yview)
        self.positions_tree.configure(yscroll=scrollbar.set)
        
        # Pack widgets
        self.positions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10, padx=(0, 10))
        
        # Configure tags for colors and zebra striping
        self.positions_tree.tag_configure('positive', foreground='#22C55E')
        self.positions_tree.tag_configure('negative', foreground='#EF4444')
        self.positions_tree.tag_configure('evenrow', background='#0F141B')
        self.positions_tree.tag_configure('oddrow', background='#131B24')
        
        return frame
    
    def _create_closed_trades_section(self, parent):
        """Create closed trades section with treeview"""
        frame = tk.LabelFrame(parent, text="📋 LAST 5 CLOSED POSITIONS",
                             bg='#121822', fg='#06B6D4',
                             font=('Segoe UI', 10, 'bold'),
                             borderwidth=1, relief=tk.SOLID)
        
        # Create treeview
        columns = ("Symbol", "Entry→Exit", "PnL", "Hold", "Close Reason", "Time")
        self.closed_tree = ttk.Treeview(frame, columns=columns, show='headings', height=5)
        
        # Configure columns
        column_widths = [100, 200, 150, 100, 200, 100]
        for col, width in zip(columns, column_widths):
            self.closed_tree.heading(col, text=col)
            self.closed_tree.column(col, width=width, anchor=tk.CENTER)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.closed_tree.yview)
        self.closed_tree.configure(yscroll=scrollbar.set)
        
        # Pack widgets
        self.closed_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10, padx=(0, 10))
        
        # Configure tags for colors and zebra striping
        self.closed_tree.tag_configure('positive', foreground='#22C55E')
        self.closed_tree.tag_configure('negative', foreground='#EF4444')
        self.closed_tree.tag_configure('evenrow', background='#0F141B')
        self.closed_tree.tag_configure('oddrow', background='#131B24')
        
        return frame
    
    def _create_footer_section(self, parent):
        """Create footer section with portfolio summary"""
        frame = tk.LabelFrame(parent, text="💡 PORTFOLIO SUMMARY",
                             bg='#121822', fg='#06B6D4',
                             font=('Segoe UI', 10, 'bold'),
                             borderwidth=1, relief=tk.SOLID)
        
        self.footer_label = tk.Label(frame, text="",
                                    font=('Segoe UI', 10),
                                    fg='#A9B4C0', bg='#121822',
                                    justify=tk.LEFT)
        self.footer_label.pack(pady=10, padx=10, anchor=tk.W)
        
        return frame
    
    def update_dashboard(self, current_balance: float):
        """Update all dashboard sections"""
        try:
            # Update header
            self._update_header()
            
            # Update statistics
            self._update_statistics(current_balance)
            
            # Update active positions
            self._update_positions()
            
            # Update closed trades
            self._update_closed_trades()
            
            # Update footer
            self._update_footer()
            
            self.last_update_time = datetime.now()
            
        except Exception as e:
            logging.error(f"Dashboard update error: {e}")
    
    def _update_header(self):
        """Update header information"""
        session_duration = self.session_stats.get_session_duration()
        current_time = datetime.now().strftime("%H:%M:%S")
        next_seconds = self.update_interval // 1000
        
        header_text = f"Session Duration: {session_duration} | Last Update: {current_time} | Next Update: {next_seconds}s"
        self.header_label.config(text=header_text)
    
    def _update_statistics(self, current_balance: float):
        """Update statistics section"""
        # Get statistics
        total_trades = self.session_stats.get_total_trades()
        win_rate = self.session_stats.get_win_rate()
        win_rate_emoji = self.session_stats.get_win_rate_emoji()
        pnl_usd, pnl_pct = self.session_stats.get_pnl_vs_start()
        
        # Update Balance
        balance_text = f"${current_balance:.2f}\nStart: ${self.session_stats.session_start_balance:.2f}"
        self.stat_labels["Balance"].config(text=balance_text)
        
        # Update Trades
        trades_text = f"{total_trades} ({self.session_stats.trades_won}W / {self.session_stats.trades_lost}L)\nOpen: {self.position_manager.safe_get_position_count()}"
        self.stat_labels["Trades"].config(text=trades_text)
        
        # Update Win Rate
        winrate_text = f"{win_rate:.1f}% {win_rate_emoji}\nAvg Win: +{self.session_stats.get_average_win_pct():.1f}%"
        self.stat_labels["Win Rate"].config(text=winrate_text)
        
        # Update Total PnL (semantic colors)
        pnl_color = '#22C55E' if pnl_usd >= 0 else '#EF4444'
        pnl_text = f"{'+' if pnl_usd >= 0 else ''}{pnl_usd:.2f} USD\n({'+' if pnl_pct >= 0 else ''}{pnl_pct:.2f}%)"
        self.stat_labels["Total PnL"].config(text=pnl_text, fg=pnl_color)
        
        # Update Best/Worst
        best_str = f"+${self.session_stats.best_trade_pnl:.2f}" if self.session_stats.best_trade_pnl > 0 else "$0.00"
        worst_str = f"-${abs(self.session_stats.worst_trade_pnl):.2f}" if self.session_stats.worst_trade_pnl < 0 else "$0.00"
        best_worst_text = f"{best_str} / {worst_str}\nAvg Hold: {self.session_stats.get_average_hold_time()}"
        self.stat_labels["Best/Worst"].config(text=best_worst_text)
    
    def _update_positions(self):
        """Update active positions table with clean values (no ROE/Dist/Max)"""
        # Clear existing items
        for item in self.positions_tree.get_children():
            self.positions_tree.delete(item)
        
        # Get active positions
        active_positions = self.position_manager.safe_get_all_active_positions()
        
        # Update frame title
        self.positions_frame.config(text=f"🎯 ACTIVE POSITIONS ({len(active_positions)})")
        
        if not active_positions:
            self.positions_tree.insert('', 'end', values=("No active positions", "", "", "", "", "", ""))
            return
        
        # Add positions with clean formatting and color-coded columns
        for idx, pos in enumerate(active_positions):
            # Symbol (neutral)
            symbol_short = pos.symbol.replace('/USDT:USDT', '')
            
            # Side (text indicators instead of emoji)
            if pos.side in ['buy', 'long']:
                side_text = f"[↑] LONG {pos.leverage}x"
            else:
                side_text = f"[↓] SHORT {pos.leverage}x"
            
            # Entry & Current (neutral)
            entry_str = f"${pos.entry_price:,.6f}"
            current_str = f"${pos.current_price:,.6f}"
            
            # Stop Loss (clean text without emoji)
            sl_pct = ((pos.stop_loss - pos.entry_price) / pos.entry_price * 100) if pos.stop_loss > 0 else 0
            sl_str = f"${pos.stop_loss:,.6f} ({sl_pct:+.2f}%)"
            
            # PnL (use +/- prefix for clarity)
            pnl_str = f"{pos.unrealized_pnl_pct:+.2f}% | ${pos.unrealized_pnl_usd:+.2f}"
            
            # Trailing (text indicators)
            if hasattr(pos, 'trailing_data') and pos.trailing_data and pos.trailing_data.enabled:
                trailing_str = "[√] ACTIVE"
            else:
                trailing_str = "[ ] WAITING"
            
            # Use ONLY zebra striping (no color tags that affect entire row)
            zebra_tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            
            # Insert row with only zebra tag
            self.positions_tree.insert('', 'end', 
                                      values=(symbol_short, side_text, entry_str, current_str, 
                                             sl_str, pnl_str, trailing_str),
                                      tags=(zebra_tag,))
    
    def _update_closed_trades(self):
        """Update closed trades table with clean formatting"""
        # Clear existing items
        for item in self.closed_tree.get_children():
            self.closed_tree.delete(item)
        
        # Get last trades
        last_trades = self.session_stats.get_last_n_trades(5)
        
        if not last_trades:
            self.closed_tree.insert('', 'end', values=("No closed trades yet", "", "", "", "", ""))
            return
        
        # Emoji mapping for close reasons
        reason_emoji = {
            "STOP_LOSS_HIT": "❌",
            "TRAILING_STOP_HIT": "🎪",
            "TAKE_PROFIT_HIT": "🎯",
            "MANUAL_CLOSE": "👤",
            "UNKNOWN": "❓"
        }
        
        # Add trades with clean formatting
        for idx, trade in enumerate(last_trades):
            # Symbol
            symbol_short = trade.symbol
            
            # Entry→Exit
            entry_exit_str = f"${trade.entry_price:,.4f} → ${trade.exit_price:,.4f}"
            
            # PnL (clean, on single line)
            pnl_str = f"{trade.pnl_pct:+.2f}% | ${trade.pnl_usd:+.2f}"
            
            # Hold time
            if trade.hold_time_minutes < 60:
                hold_str = f"{trade.hold_time_minutes}m"
            else:
                hours = trade.hold_time_minutes // 60
                minutes = trade.hold_time_minutes % 60
                hold_str = f"{hours}h {minutes}m"
            
            # Close reason
            emoji = reason_emoji.get(trade.close_reason, "❓")
            reason_display = trade.close_reason.replace("_", " ").title()
            reason_str = f"{emoji} {reason_display}"
            
            # Time
            close_time = datetime.fromisoformat(trade.close_time)
            time_str = close_time.strftime("%H:%M")
            
            # Determine tags: color + zebra striping
            color_tag = 'positive' if trade.pnl_usd >= 0 else 'negative'
            zebra_tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            
            # Insert row with both tags
            self.closed_tree.insert('', 'end',
                                   values=(symbol_short, entry_exit_str, pnl_str, 
                                          hold_str, reason_str, time_str),
                                   tags=(color_tag, zebra_tag))
    
    def _update_footer(self):
        """Update footer with portfolio summary"""
        summary = self.position_manager.safe_get_session_summary()
        
        active_count = summary.get('active_positions', 0)
        used_margin = summary.get('used_margin', 0)
        available = summary.get('available_balance', 0)
        unrealized_pnl = summary.get('unrealized_pnl', 0)
        
        # Count trailing active
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
        
        self.footer_label.config(text=footer_text)
    
    def _schedule_update(self):
        """Schedule next dashboard update"""
        if self.is_running and self.root:
            try:
                # Get current balance
                balance_summary = self.position_manager.safe_get_session_summary()
                current_balance = balance_summary.get('balance', 0)
                
                # Update dashboard
                self.update_dashboard(current_balance)
                
                # Schedule next update
                self.root.after(self.update_interval, self._schedule_update)
                
            except Exception as e:
                logging.error(f"Dashboard scheduled update error: {e}")
                if self.is_running:
                    self.root.after(self.update_interval, self._schedule_update)
    
    def start(self):
        """Start the dashboard"""
        if not self.root:
            self.create_window()
        
        self.is_running = True
        
        # Initial update
        balance_summary = self.position_manager.safe_get_session_summary()
        current_balance = balance_summary.get('balance', 0)
        self.update_dashboard(current_balance)
        
        # Schedule updates
        self.root.after(self.update_interval, self._schedule_update)
        
        logging.info(f"📊 Dashboard started (update every {self.update_interval/1000}s)")
        
        # Run main loop
        self.root.mainloop()
    
    def stop(self):
        """Stop the dashboard"""
        self.is_running = False
        if self.root:
            self.root.quit()
            self.root.destroy()
            self.root = None
        logging.info("📊 Dashboard stopped")
    
    async def run_live_dashboard(self, exchange, update_interval: int = 30):
        """
        Run live dashboard in separate thread (for compatibility with async code)
        
        Args:
            exchange: Bybit exchange instance (not used in tkinter version)
            update_interval: Update interval in seconds (default 30s)
        """
        self.update_interval = update_interval * 1000  # Convert to milliseconds
        
        # Run dashboard in separate thread
        dashboard_thread = threading.Thread(target=self.start, daemon=True)
        dashboard_thread.start()
        
        logging.info(f"📊 Dashboard thread started (update every {update_interval}s)")
