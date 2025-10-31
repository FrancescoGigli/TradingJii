#!/usr/bin/env python3
"""
📋 CLOSED POSITIONS RENDERER

Rendering celle per tabelle posizioni chiuse.
Gestisce formattazione e tooltips per trade history.
"""

from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtGui import QBrush
from PyQt6.QtCore import Qt
from datetime import datetime
import json
import logging

from .helpers import ColorHelper
from .stats_calculator import StatsCalculator


class ClosedCellRenderer:
    """Renderizza singole celle per posizioni chiuse"""
    
    @staticmethod
    def render_symbol(trade) -> QTableWidgetItem:
        """Colonna 0: Symbol"""
        symbol = trade.symbol.replace('/USDT:USDT', '') if hasattr(trade, 'symbol') else str(trade.symbol)
        item = QTableWidgetItem(symbol)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_id(trade) -> QTableWidgetItem:
        """Colonna 1: ID (time-based short ID)"""
        if hasattr(trade, 'close_time') and trade.close_time:
            try:
                close_dt = datetime.fromisoformat(trade.close_time)
                id_display = close_dt.strftime("%H%M")  # "1550" format
            except:
                id_display = "N/A"
        elif hasattr(trade, 'position_id') and trade.position_id:
            # Fallback: extract from position_id
            pos_id = trade.position_id
            if '_' in pos_id:
                parts = pos_id.split('_')
                if len(parts) >= 3:
                    time_part = parts[-2]  # "093445"
                    id_display = time_part[:4]  # "0934"
                else:
                    id_display = pos_id[-8:]
            else:
                id_display = pos_id[-8:] if len(pos_id) > 8 else pos_id
        else:
            id_display = "N/A"
        
        item = QTableWidgetItem(id_display)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_initial_margin(trade) -> QTableWidgetItem:
        """Colonna 2: Initial Margin (IM)"""
        # Best effort: calculate from trade data
        if hasattr(trade, 'real_initial_margin') and trade.real_initial_margin is not None:
            initial_margin = trade.real_initial_margin
            im_source = "Bybit"
        elif hasattr(trade, 'leverage') and trade.leverage > 0:
            # Estimate IM from entry price assuming standard position size
            initial_margin = (trade.entry_price * 10) / trade.leverage
            im_source = "Estimated"
        else:
            initial_margin = 0
            im_source = "Unknown"
        
        item = QTableWidgetItem(f"${initial_margin:.2f}")
        item.setToolTip(f"Initial Margin (IM) [{im_source}]: ${initial_margin:.2f}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_entry_exit(trade) -> QTableWidgetItem:
        """Colonna 3: Entry→Exit"""
        # Use exit_price if available, otherwise fallback to current_price
        exit_price = getattr(trade, 'exit_price', None) or trade.current_price
        entry_exit = f"${trade.entry_price:,.4f} → ${exit_price:,.4f}"
        item = QTableWidgetItem(entry_exit)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_pnl(trade) -> QTableWidgetItem:
        """Colonna 4: PnL (ROE% e $)"""
        # Get PnL values with fallback to unrealized_pnl_* for backward compatibility
        pnl_pct = getattr(trade, 'pnl_pct', None) or getattr(trade, 'unrealized_pnl_pct', 0.0)
        pnl_usd = getattr(trade, 'pnl_usd', None) or getattr(trade, 'unrealized_pnl_usd', 0.0)
        
        # Calculate price change % (without leverage)
        leverage = getattr(trade, 'leverage', 10)
        price_change_pct = pnl_pct / leverage if leverage > 0 else pnl_pct
        
        pnl_text = f"ROE {ColorHelper.format_pct(pnl_pct)} | {ColorHelper.format_usd(pnl_usd)}"
        item = QTableWidgetItem(pnl_text)
        ColorHelper.color_cell(item, pnl_usd)
        
        # Tooltip explaining the difference
        item.setToolTip(
            f"💰 PnL Breakdown:\n\n"
            f"ROE% (Return on Equity): {pnl_pct:+.2f}%\n"
            f"  = Profit/Loss on your margin (with leverage)\n\n"
            f"Price Change: {price_change_pct:+.2f}%\n"
            f"  = Actual {trade.symbol} price movement\n\n"
            f"Leverage: {leverage}x\n"
            f"Formula: ROE% = Price% × Leverage"
        )
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_hold_time(trade) -> QTableWidgetItem:
        """Colonna 5: Hold Time"""
        hold_str = StatsCalculator.calculate_hold_time(
            getattr(trade, 'entry_time', None),
            getattr(trade, 'close_time', None)
        )
        
        item = QTableWidgetItem(hold_str)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_close_reason(trade) -> QTableWidgetItem:
        """Colonna 6: Close Reason (con PnL indicator e tooltip)"""
        # Get PnL values with fallback to unrealized_pnl_* for backward compatibility
        pnl_pct = getattr(trade, 'pnl_pct', None) or getattr(trade, 'unrealized_pnl_pct', 0.0)
        pnl_usd = getattr(trade, 'pnl_usd', None) or getattr(trade, 'unrealized_pnl_usd', 0.0)
        
        is_profit = pnl_usd > 0
        pnl_sign = "+" if is_profit else ""
        
        # Map reason to descriptive text
        close_reason = getattr(trade, 'close_reason', getattr(trade, 'status', 'UNKNOWN'))
        
        if "STOP_LOSS" in close_reason or "MANUAL" in close_reason:
            if is_profit:
                reason_str = f"✅ Trailing Stop Hit with Gain {pnl_sign}{pnl_pct:.1f}%"
            else:
                reason_str = f"❌ SL Hit {pnl_sign}{pnl_pct:.1f}%"
        elif "TRAILING" in close_reason:
            if is_profit:
                reason_str = f"✅ Trailing Stop Hit with Gain {pnl_sign}{pnl_pct:.1f}%"
            else:
                reason_str = f"🎪 Trailing {pnl_sign}{pnl_pct:.1f}%"
        elif "TAKE_PROFIT" in close_reason:
            reason_str = f"🎯 TP Hit {pnl_sign}{pnl_pct:.1f}%"
        else:
            reason_str = f"❓ {close_reason} {pnl_sign}{pnl_pct:.1f}%"
        
        item = QTableWidgetItem(reason_str)
        
        # Color based on profit/loss
        if is_profit:
            item.setForeground(QBrush(ColorHelper.POSITIVE))
        else:
            item.setForeground(QBrush(ColorHelper.NEGATIVE))
        
        # Build detailed tooltip with snapshot if available
        tooltip = ClosedCellRenderer._build_close_tooltip(trade, close_reason)
        item.setToolTip(tooltip)
        
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_opened_time(trade) -> QTableWidgetItem:
        """Colonna 7: Opened timestamp"""
        if hasattr(trade, 'entry_time') and trade.entry_time:
            try:
                entry_dt = datetime.fromisoformat(trade.entry_time)
                opened_str = entry_dt.strftime("%d/%m %H:%M:%S")
            except:
                opened_str = "N/A"
        else:
            opened_str = "N/A"
        
        item = QTableWidgetItem(opened_str)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_closed_time(trade) -> QTableWidgetItem:
        """Colonna 8: Closed timestamp"""
        if hasattr(trade, 'close_time') and trade.close_time:
            try:
                close_dt = datetime.fromisoformat(trade.close_time)
                closed_str = close_dt.strftime("%d/%m %H:%M:%S")
            except:
                closed_str = "N/A"
        else:
            closed_str = "N/A"
        
        item = QTableWidgetItem(closed_str)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def _build_close_tooltip(trade, close_reason: str) -> str:
        """Costruisce tooltip dettagliato con snapshot data"""
        tooltip_parts = [f"Close Reason: {close_reason}"]
        
        # Try to get close_snapshot
        if hasattr(trade, 'close_snapshot') and trade.close_snapshot:
            try:
                snapshot = json.loads(trade.close_snapshot)
                
                tooltip_parts.extend([
                    "",
                    "📸 CLOSE SNAPSHOT:",
                    "",
                    f"Exit Price: ${snapshot.get('exit_price', 0):.6f}",
                    f"Entry Price: ${snapshot.get('entry_price', 0):.6f}",
                    f"Price Change: {snapshot.get('price_change_pct', 0):+.2f}%",
                    "",
                    f"⏱️ Duration: {snapshot.get('hold_duration_str', 'N/A')}",
                ])
                
                # Add extreme prices if available
                if 'max_price_seen' in snapshot:
                    tooltip_parts.extend([
                        "",
                        "📊 PRICE EXTREMES:",
                        f"Max Seen: ${snapshot.get('max_price_seen', 0):.6f}",
                        f"Min Seen: ${snapshot.get('min_price_seen', 0):.6f}",
                    ])
                    
                    if 'distance_from_peak_pct' in snapshot:
                        tooltip_parts.append(f"Distance from Peak: {snapshot.get('distance_from_peak_pct', 0):.2f}%")
                    if 'distance_from_bottom_pct' in snapshot:
                        tooltip_parts.append(f"Distance from Bottom: {snapshot.get('distance_from_bottom_pct', 0):.2f}%")
                
                # Add recent candles summary
                if snapshot.get('recent_candles'):
                    tooltip_parts.extend(["", "🕯️ RECENT CANDLES (last 5):"])
                    for candle in snapshot['recent_candles']:
                        tooltip_parts.append(
                            f"  {candle['time']}: O${candle['open']:.4f} "
                            f"H${candle['high']:.4f} L${candle['low']:.4f} "
                            f"C${candle['close']:.4f}"
                        )
                
                # Add stop loss info
                if 'stop_loss_price' in snapshot:
                    tooltip_parts.extend([
                        "",
                        "🛡️ STOP LOSS:",
                        f"SL Price: ${snapshot.get('stop_loss_price', 0):.6f}",
                        f"SL Distance from Entry: {snapshot.get('sl_distance_from_entry_pct', 0):+.2f}%",
                    ])
                
                # Add trailing info
                if snapshot.get('trailing_was_active'):
                    tooltip_parts.extend([
                        "",
                        "🎪 TRAILING: Was Active",
                    ])
                    if snapshot.get('trailing_activation_time'):
                        tooltip_parts.append(f"Activated: {snapshot.get('trailing_activation_time', '')}")
                
            except Exception as e:
                tooltip_parts.append(f"\nError parsing snapshot: {e}")
        else:
            tooltip_parts.append("\nNo snapshot available")
        
        return "\n".join(tooltip_parts)


class ClosedTablePopulator:
    """Popola tabelle closed positions usando i renderer"""
    
    @staticmethod
    def populate(table, trades: list):
        """
        Popola tabella closed positions
        
        Args:
            table: QTableWidget da popolare
            trades: Lista trade chiusi
        """
        from .table_factory import TableFactory
        
        # Disable sorting durante update
        TableFactory.disable_sorting_for_update(table)
        
        try:
            table.setRowCount(0)
            
            if not trades:
                table.setRowCount(1)
                item = QTableWidgetItem("No closed trades yet")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(0, 0, item)
                table.setSpan(0, 0, 1, 9)  # 9 columns total
                return
            
            table.setRowCount(len(trades))
            
            for row, trade in enumerate(trades):
                # Renderizza ogni colonna
                table.setItem(row, 0, ClosedCellRenderer.render_symbol(trade))
                table.setItem(row, 1, ClosedCellRenderer.render_id(trade))
                table.setItem(row, 2, ClosedCellRenderer.render_initial_margin(trade))
                table.setItem(row, 3, ClosedCellRenderer.render_entry_exit(trade))
                table.setItem(row, 4, ClosedCellRenderer.render_pnl(trade))
                table.setItem(row, 5, ClosedCellRenderer.render_hold_time(trade))
                table.setItem(row, 6, ClosedCellRenderer.render_close_reason(trade))
                table.setItem(row, 7, ClosedCellRenderer.render_opened_time(trade))
                table.setItem(row, 8, ClosedCellRenderer.render_closed_time(trade))
        
        finally:
            # Riabilita sorting
            TableFactory.enable_sorting_after_update(table)
