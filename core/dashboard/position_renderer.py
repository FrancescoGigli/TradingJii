#!/usr/bin/env python3
"""
🎨 POSITION RENDERER

Rendering celle per tabelle posizioni attive.
Ogni metodo renderizza una specifica colonna della tabella.
"""

from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtCore import Qt
from datetime import datetime
import json
import logging

from .helpers import ColorHelper
from .stats_calculator import StatsCalculator
import config


class PositionCellRenderer:
    """Renderizza singole celle per posizioni attive"""
    
    @staticmethod
    def render_symbol(pos) -> QTableWidgetItem:
        """Colonna 0: Symbol (short format)"""
        symbol_short = pos.symbol.replace('/USDT:USDT', '')
        item = QTableWidgetItem(symbol_short)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_side(pos) -> QTableWidgetItem:
        """Colonna 1: Side with color and leverage"""
        item = QTableWidgetItem()
        
        if pos.side in ['buy', 'long']:
            item.setText(f"[↑] LONG {pos.leverage}x")
            item.setForeground(QBrush(ColorHelper.POSITIVE))
        else:
            item.setText(f"[↓] SHORT {pos.leverage}x")
            item.setForeground(QBrush(ColorHelper.NEGATIVE))
        
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_initial_margin(pos) -> QTableWidgetItem:
        """Colonna 2: Initial Margin (IM)"""
        margin, source = StatsCalculator.calculate_initial_margin(pos)
        
        item = QTableWidgetItem(f"${margin:.2f}")
        item.setToolTip(
            f"Initial Margin (IM) [{source}]\n\n"
            f"Margine bloccato per questa posizione\n"
            f"Capital allocato: ${margin:.2f}\n\n"
            f"Source: {source}\n"
            f"{'✅ Read from Bybit (exact value)' if source == 'Bybit' else '⚠️ Calculated (may differ slightly from Bybit)'}"
        )
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_entry_price(pos) -> QTableWidgetItem:
        """Colonna 3: Entry Price"""
        item = QTableWidgetItem(ColorHelper.format_price(pos.entry_price))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_current_price(pos) -> QTableWidgetItem:
        """Colonna 4: Current Price"""
        item = QTableWidgetItem(ColorHelper.format_price(pos.current_price))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_stop_loss(pos) -> QTableWidgetItem:
        """Colonna 5: Stop Loss Price"""
        # Use real SL from Bybit if available
        if hasattr(pos, 'real_stop_loss') and pos.real_stop_loss is not None:
            stop_loss_display = pos.real_stop_loss
            sl_source = "Bybit"
        else:
            stop_loss_display = pos.stop_loss
            sl_source = "Calculated"
        
        item = QTableWidgetItem(ColorHelper.format_price(stop_loss_display))
        item.setToolTip(
            f"Stop Loss Price [{sl_source}]\n"
            f"${stop_loss_display:.6f}\n\n"
            f"{'✅ Read from Bybit (exact value)' if sl_source == 'Bybit' else '⚠️ Calculated (may differ from Bybit)'}"
        )
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_type(pos, metrics: dict) -> QTableWidgetItem:
        """Colonna 6: Type (TRAILING or FIXED)"""
        item = QTableWidgetItem()
        
        # Calculate REAL SL percentage for tooltip
        real_sl_price_pct = abs((pos.stop_loss - pos.entry_price) / pos.entry_price) * 100
        real_sl_roe_pct = real_sl_price_pct * pos.leverage
        
        if metrics['is_trailing']:
            item.setText("TRAILING")
            item.setForeground(QBrush(ColorHelper.POSITIVE))
            item.setToolTip(
                f"Trailing Stop: Stop loss dinamico\n"
                f"Current SL: ${pos.stop_loss:.6f}\n"
                f"Risk: -{real_sl_price_pct:.2f}% price = -{real_sl_roe_pct:.1f}% ROE"
            )
        else:
            item.setText("FIXED")
            item.setForeground(QBrush(ColorHelper.INFO))
            item.setToolTip(
                f"Fixed Stop Loss\n"
                f"SL Price: ${pos.stop_loss:.6f}\n"
                f"Risk: -{real_sl_price_pct:.2f}% price × {pos.leverage}x lev = -{real_sl_roe_pct:.1f}% ROE"
            )
        
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_sl_percentage(pos, metrics: dict) -> QTableWidgetItem:
        """Colonna 7: SL % (sempre negativo, protezione)"""
        item = QTableWidgetItem()
        
        risk_pct = metrics['risk_pct']
        sl_roe_pct = metrics['sl_roe_pct']
        
        # Display value (always negative for protection)
        item.setText(ColorHelper.format_pct(risk_pct))
        
        # Build tooltip
        side_type = "LONG" if pos.side in ['buy', 'long'] else "SHORT"
        sl_price = metrics['sl_price']
        
        if metrics['is_trailing']:
            tooltip_text = (
                f"🎪 TRAILING STOP - {side_type}\n\n"
                f"Stop Loss: ${sl_price:.6f}\n"
                f"Entry: ${pos.entry_price:.6f}\n"
                f"Risk: {risk_pct:.2f}% price\n"
                f"Impact on Margin: {sl_roe_pct:.1f}% ROE\n\n"
                f"✅ Trailing attivo - protegge profitti"
            )
            item.setForeground(QBrush(ColorHelper.POSITIVE))
        else:
            tooltip_text = (
                f"🛡️ FIXED STOP LOSS - {side_type}\n\n"
                f"Stop Loss: ${sl_price:.6f}\n"
                f"Entry: ${pos.entry_price:.6f}\n"
                f"Risk: {risk_pct:.2f}% price\n"
                f"Impact on Margin: {sl_roe_pct:.1f}% ROE\n\n"
                f"⚠️ Protezione base attiva"
            )
            item.setForeground(QBrush(ColorHelper.NEGATIVE))
        
        item.setToolTip(tooltip_text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_pnl_percentage(pos) -> QTableWidgetItem:
        """Colonna 8: PnL %"""
        item = QTableWidgetItem(ColorHelper.format_pct(pos.unrealized_pnl_pct))
        ColorHelper.color_cell(item, pos.unrealized_pnl_usd)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_pnl_usd(pos) -> QTableWidgetItem:
        """Colonna 9: PnL $"""
        item = QTableWidgetItem(ColorHelper.format_usd(pos.unrealized_pnl_usd))
        ColorHelper.color_cell(item, pos.unrealized_pnl_usd)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_liquidation_price(pos, metrics: dict) -> QTableWidgetItem:
        """Colonna 10: Liquidation Price"""
        liq_price = metrics['liq_price']
        distance_pct = metrics['distance_to_liq_pct']
        
        item = QTableWidgetItem(ColorHelper.format_price(liq_price))
        
        # Color based on proximity to liquidation
        if distance_pct < 5:
            item.setForeground(QBrush(ColorHelper.NEGATIVE))
        elif distance_pct < 15:
            item.setForeground(QBrush(ColorHelper.WARNING))
        else:
            item.setForeground(QBrush(ColorHelper.INFO))
        
        item.setToolTip(
            f"Liquidation Price\n\n"
            f"Prezzo a cui la posizione viene liquidata\n"
            f"Distanza attuale: {distance_pct:.1f}%\n\n"
            f"🔴 <5%: Pericolo imminente\n"
            f"🟡 5-15%: Attenzione\n"
            f"🔵 >15%: Sicuro"
        )
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_time_in_position(pos, metrics: dict) -> QTableWidgetItem:
        """Colonna 11: Time in Position"""
        time_str = metrics['time_in_position']
        
        item = QTableWidgetItem(time_str)
        
        if pos.entry_time:
            try:
                entry_dt = datetime.fromisoformat(pos.entry_time)
                item.setToolTip(f"Opened at: {entry_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            except:
                pass
        
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_status(pos, metrics: dict) -> QTableWidgetItem:
        """Colonna 12: Status (ACTIVE, STUCK, WAIT, OK, LOSS)"""
        item = QTableWidgetItem()
        
        roe_pct = metrics['roe_pct']
        is_trailing = metrics['is_trailing']
        price_move_pct = metrics['price_move_pct']
        
        if is_trailing:
            item.setText(f"✓ ACTIVE\n+{roe_pct:.0f}%")
            item.setForeground(QBrush(ColorHelper.POSITIVE))
        elif roe_pct >= 10.0:
            item.setText(f"⚠️ STUCK\n+{roe_pct:.0f}%")
            item.setForeground(QBrush(ColorHelper.WARNING))
        elif price_move_pct >= 1.0:
            item.setText(f"⏳ WAIT\n+{roe_pct:.0f}%")
            item.setForeground(QBrush(ColorHelper.INFO))
        elif roe_pct >= 0:
            item.setText(f"📊 OK\n+{roe_pct:.0f}%")
            item.setForeground(QBrush(ColorHelper.INFO))
        else:
            item.setText(f"🔻 LOSS\n{roe_pct:.0f}%")
            item.setForeground(QBrush(ColorHelper.NEGATIVE))
        
        item.setToolTip(
            "✓ ACTIVE: Trailing attivo e funzionante\n"
            "⚠️ STUCK: Dovrebbe essere in trailing ma non è attivo (BUG!)\n"
            "⏳ WAIT: In attesa di attivazione trailing (+10% ROE)\n"
            "📊 OK: Profit positivo ma sotto soglia trailing\n"
            "🔻 LOSS: Posizione in perdita"
        )
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_confidence(pos) -> QTableWidgetItem:
        """Colonna 13: Confidence %"""
        confidence = getattr(pos, 'confidence', 0.0)
        
        item = QTableWidgetItem(f"{confidence:.0%}")
        
        if confidence >= 0.75:
            item.setForeground(QBrush(ColorHelper.POSITIVE))
        elif confidence >= 0.65:
            item.setForeground(QBrush(ColorHelper.INFO))
        else:
            item.setForeground(QBrush(ColorHelper.WARNING))
        
        item.setToolTip(f"ML Model Confidence: {confidence:.1%}\nHigher = More confident prediction")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_weight(pos) -> QTableWidgetItem:
        """Colonna 14: Weight (based on confidence)"""
        confidence = getattr(pos, 'confidence', 0.0)
        
        item = QTableWidgetItem(f"{confidence:.0%}")
        
        if confidence >= 0.75:
            item.setForeground(QBrush(ColorHelper.POSITIVE))
        elif confidence >= 0.65:
            item.setForeground(QBrush(ColorHelper.INFO))
        else:
            item.setForeground(QBrush(ColorHelper.WARNING))
        
        item.setToolTip(f"Position Weight (based on ML confidence): {confidence:.0%}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_adaptive_status(pos) -> QTableWidgetItem:
        """Colonna 15: Adaptive Status (BLOCKED, GROWING, STABLE, NEW)"""
        item = QTableWidgetItem()
        
        try:
            if not config.ADAPTIVE_SIZING_ENABLED:
                item.setText("N/A")
                item.setForeground(QBrush(ColorHelper.NEUTRAL))
                item.setToolTip("Adaptive sizing is disabled")
                return item
            
            from core.adaptive_position_sizing import global_adaptive_sizing
            
            if global_adaptive_sizing is None or pos.symbol not in global_adaptive_sizing.symbol_memory:
                item.setText("🆕 NEW")
                item.setForeground(QBrush(ColorHelper.NEUTRAL))
                item.setToolTip(
                    "New symbol - not yet in adaptive memory\n\n"
                    "Will be tracked after first close\n"
                    "Starting with base size"
                )
                return item
            
            memory = global_adaptive_sizing.symbol_memory[pos.symbol]
            
            # Check if blocked
            if memory.blocked_cycles_left > 0:
                item.setText(f"🚫 BLOCKED\n{memory.blocked_cycles_left} cycles")
                item.setForeground(QBrush(ColorHelper.NEGATIVE))
                item.setToolTip(
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
                    item.setText(f"📈 GROWING\n+{size_change_pct:.1f}%")
                    item.setForeground(QBrush(ColorHelper.POSITIVE))
                    item.setToolTip(
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
                    item.setText(f"📉 RESET\n{size_change_pct:.1f}%")
                    item.setForeground(QBrush(ColorHelper.WARNING))
                    item.setToolTip(
                        f"Symbol was RESET after a loss\n\n"
                        f"Current size: ${current_size:.2f}\n"
                        f"Base size: ${base_size:.2f}\n"
                        f"Change: {size_change_pct:.1f}%\n\n"
                        f"History: {memory.wins}W / {memory.losses}L"
                    )
                else:
                    # Stable (at base level)
                    item.setText(f"📊 STABLE\n${current_size:.2f}")
                    item.setForeground(QBrush(ColorHelper.INFO))
                    win_rate_text = f"{(memory.wins / memory.total_trades * 100):.0f}%" if memory.total_trades > 0 else "New"
                    item.setToolTip(
                        f"Symbol at BASE size level\n\n"
                        f"Current size: ${current_size:.2f}\n"
                        f"Base size: ${base_size:.2f}\n\n"
                        f"Last PnL: {memory.last_pnl_pct:+.1f}%" if memory.last_pnl_pct != 0 else "First trade\n\n"
                        f"History: {memory.wins}W / {memory.losses}L\n"
                        f"Win rate: {win_rate_text}"
                    )
        
        except Exception as e:
            item.setText("ERROR")
            item.setForeground(QBrush(ColorHelper.WARNING))
            item.setToolTip(f"Error getting adaptive status: {e}")
        
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
    
    @staticmethod
    def render_open_reason(pos) -> QTableWidgetItem:
        """Colonna 16: Open Reason (ML prediction or Already Open)"""
        item = QTableWidgetItem()
        
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
            item.setText("🔄 Already Open")
            item.setForeground(QBrush(ColorHelper.INFO))
            item.setToolTip(
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
                
                item.setText(f"🤖 ML {side_indicator} {conf_display}")
                item.setForeground(QBrush(ColorHelper.POSITIVE))
                
                # Detailed tooltip with full prediction info
                item.setToolTip(
                    f"ML Prediction Details:\n"
                    f"Side: {'LONG' if pos.side in ['buy', 'long'] else 'SHORT'}\n"
                    f"Confidence: {conf_display}\n"
                    f"Signal: {ml_signal if ml_signal else 'N/A'}\n"
                    f"Reason: {open_reason if open_reason else 'N/A'}\n"
                    f"Entry: ${pos.entry_price:.6f}\n\n{debug_info}"
                )
            else:
                # No ML data found
                item.setText("📊 Manual")
                item.setForeground(QBrush(ColorHelper.NEUTRAL))
                item.setToolTip(
                    f"Manually opened position (no ML prediction found)\n\n{debug_info}"
                )
        
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item


class PositionTablePopulator:
    """Popola tabelle posizioni usando i renderer"""
    
    @staticmethod
    def populate(table, positions: list, tab_name: str):
        """
        Popola una tabella con posizioni
        
        Args:
            table: QTableWidget da popolare
            positions: Lista posizioni
            tab_name: Nome tab per messaggio vuoto
        """
        from .table_factory import TableFactory
        
        # Disable sorting durante update (CRITICO per performance)
        TableFactory.disable_sorting_for_update(table)
        
        try:
            # Ottimizzazione: rebuild solo se count changed
            if table.rowCount() != len(positions):
                table.setRowCount(0)
            
            if not positions:
                table.setRowCount(1)
                item = QTableWidgetItem(f"No {tab_name.lower()} positions")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(0, 0, item)
                table.setSpan(0, 0, 1, 17)  # 17 columns total
                return
            
            table.setRowCount(len(positions))
            
            for row, pos in enumerate(positions):
                # Calcola metriche una volta per posizione
                metrics = StatsCalculator.calculate_position_metrics(pos)
                
                # Renderizza ogni colonna
                table.setItem(row, 0, PositionCellRenderer.render_symbol(pos))
                table.setItem(row, 1, PositionCellRenderer.render_side(pos))
                table.setItem(row, 2, PositionCellRenderer.render_initial_margin(pos))
                table.setItem(row, 3, PositionCellRenderer.render_entry_price(pos))
                table.setItem(row, 4, PositionCellRenderer.render_current_price(pos))
                table.setItem(row, 5, PositionCellRenderer.render_stop_loss(pos))
                table.setItem(row, 6, PositionCellRenderer.render_type(pos, metrics))
                table.setItem(row, 7, PositionCellRenderer.render_sl_percentage(pos, metrics))
                table.setItem(row, 8, PositionCellRenderer.render_pnl_percentage(pos))
                table.setItem(row, 9, PositionCellRenderer.render_pnl_usd(pos))
                table.setItem(row, 10, PositionCellRenderer.render_liquidation_price(pos, metrics))
                table.setItem(row, 11, PositionCellRenderer.render_time_in_position(pos, metrics))
                table.setItem(row, 12, PositionCellRenderer.render_status(pos, metrics))
                table.setItem(row, 13, PositionCellRenderer.render_confidence(pos))
                table.setItem(row, 14, PositionCellRenderer.render_weight(pos))
                table.setItem(row, 15, PositionCellRenderer.render_adaptive_status(pos))
                table.setItem(row, 16, PositionCellRenderer.render_open_reason(pos))
                
                # Row highlighting basato su ROE
                row_background = PositionTablePopulator._get_row_background(pos, metrics)
                if row_background:
                    for col in range(17):
                        item = table.item(row, col)
                        if item:
                            item.setBackground(QBrush(row_background))
        
        finally:
            # Riabilita sorting
            TableFactory.enable_sorting_after_update(table)
    
    @staticmethod
    def _get_row_background(pos, metrics: dict) -> QColor:
        """Determina colore background riga basato su stato"""
        roe_pct = metrics['roe_pct']
        is_trailing = metrics['is_trailing']
        
        if roe_pct < -40:
            return QColor("#3D0000")  # Red - heavy loss
        elif roe_pct >= 10.0 and not is_trailing:
            return QColor("#3D3D00")  # Yellow - stuck (should be trailing)
        elif is_trailing and roe_pct >= 10.0:
            return QColor("#003D00")  # Green - trailing active
        
        return None  # No special background
