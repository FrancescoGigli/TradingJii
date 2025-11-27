#!/usr/bin/env python3
"""
📊 REAL-TIME POSITION DISPLAY - Simplified Version
100% Bybit Data • No Local Tracking • Clean & Efficient

Features:
- Live positions from ccxt.fetch_positions()
- Session statistics from Bybit closed positions
- Triple output: Terminal + ANSI File + HTML
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from termcolor import colored

from core.enhanced_logging_system import enhanced_logger, log_separator


# ═══════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def fmt_money(v: float) -> str:
    """Format money with +/- sign"""
    sign = "+" if v >= 0 else "-"
    return f"{sign}${abs(v):.2f}"


def pct_color(p: float) -> str:
    """Return color based on positive/negative"""
    return "green" if p > 0 else "red"


def safe_float(x, default: float = 0.0) -> float:
    """Safely convert to float"""
    try:
        return float(x)
    except:
        return default


# ═══════════════════════════════════════════════════════════════════════════
# MAIN DISPLAY CLASS
# ═══════════════════════════════════════════════════════════════════════════

class RealTimePositionDisplay:
    """Simplified real-time display using only Bybit data"""
    
    def __init__(self, position_manager=None):
        self.position_manager = position_manager
        self._last_open_positions = []
        self._last_closed_positions = []  # Closed from Bybit
        self._session_start_time = datetime.now()  # Session starts NOW
        logging.info(f"⚡ REAL-TIME DISPLAY: Initialized at {self._session_start_time.strftime('%H:%M:%S')}")
    
    # ───────────────────────────────────────────────────────────────────────
    # DATA FETCHING
    # ───────────────────────────────────────────────────────────────────────
    
    async def update_snapshot(self, exchange):
        """Fetch current data from Bybit"""
        try:
            # Fetch open positions
            raw_positions = await exchange.fetch_positions(None, {"limit": 100, "type": "swap"})
            self._last_open_positions = self._normalize_positions(raw_positions)
            
            # Fetch closed positions from Bybit (only from session start)
            self._last_closed_positions = await self._fetch_closed_positions(exchange)
            
        except Exception as e:
            logging.error(f"⚡ Error updating snapshot: {e}")
    
    def _normalize_positions(self, raw_positions: List[Dict]) -> List[Dict]:
        """Convert Bybit positions to normalized format"""
        normalized = []
        
        for p in raw_positions:
            contracts = abs(safe_float(p.get("contracts") or p.get("positionAmt")))
            if contracts == 0:
                continue
            
            symbol = p.get("symbol")
            side = "long" if str(p.get("side", "")).lower() in ("buy", "long") else "short"
            entry_price = safe_float(p.get("entryPrice"))
            leverage = safe_float(p.get("leverage")) or 10.0
            
            # Get unrealized PnL from Bybit
            unrealized_pnl = safe_float(p.get("unrealizedPnl"))
            
            # Calculate initial margin
            position_usd = contracts * entry_price
            initial_margin = safe_float(p.get("initialMargin")) or (position_usd / leverage)
            
            # Calculate PnL %
            pnl_pct = (unrealized_pnl / initial_margin * 100) if initial_margin > 0 else 0
            
            # Get current price (estimate from PnL if not available)
            current_price = safe_float(p.get("markPrice"))
            if not current_price and contracts > 0:
                if side == "long":
                    current_price = entry_price + (unrealized_pnl / contracts)
                else:
                    current_price = entry_price - (unrealized_pnl / contracts)
            
            # Get stop loss
            stop_loss = safe_float(p.get("stopLoss") or p.get("stopLossPrice"))
            
            normalized.append({
                "symbol": symbol,
                "side": side,
                "contracts": contracts,
                "entry_price": entry_price,
                "current_price": current_price,
                "leverage": leverage,
                "position_usd": position_usd,
                "initial_margin": initial_margin,
                "pnl_usd": unrealized_pnl,
                "pnl_pct": pnl_pct,
                "stop_loss": stop_loss,
            })
        
        return normalized
    
    async def _fetch_closed_positions(self, exchange) -> List[Dict]:
        """Fetch closed positions from Bybit (session only)"""
        try:
            start_time_ms = int(self._session_start_time.timestamp() * 1000)
            end_time_ms = int(datetime.now().timestamp() * 1000)
            
            response = await exchange.privateGetV5PositionClosedPnl({
                'category': 'linear',
                'startTime': start_time_ms,
                'endTime': end_time_ms,
                'limit': 100
            })
            
            if int(response.get('retCode', -1)) != 0:
                logging.warning(f"Bybit API error: {response.get('retMsg')}")
                return []
            
            trades = response.get('result', {}).get('list', [])
            
            # Normalize closed positions
            normalized = []
            for trade in trades:
                symbol = trade.get('symbol', 'UNKNOWN')
                side = trade.get('side', '').upper()
                entry_price = safe_float(trade.get('avgEntryPrice'))
                exit_price = safe_float(trade.get('avgExitPrice'))
                qty = safe_float(trade.get('qty'))
                leverage = int(safe_float(trade.get('leverage')))
                closed_pnl = safe_float(trade.get('closedPnl'))
                
                # Calculate margin and %
                notional = qty * entry_price
                margin = notional / leverage if leverage > 0 else notional
                pnl_pct = (closed_pnl / margin * 100) if margin > 0 else 0
                
                # Parse timestamps
                created_time = trade.get('createdTime')
                updated_time = trade.get('updatedTime')
                
                open_time = None
                close_time = None
                duration = None
                
                if created_time:
                    open_time = datetime.fromtimestamp(int(created_time) / 1000)
                if updated_time:
                    close_time = datetime.fromtimestamp(int(updated_time) / 1000)
                if open_time and close_time:
                    duration = close_time - open_time
                
                normalized.append({
                    "symbol": symbol,
                    "side": "long" if side == "BUY" else "short",
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "leverage": leverage,
                    "pnl_usd": closed_pnl,
                    "pnl_pct": pnl_pct,
                    "open_time": open_time,
                    "close_time": close_time,
                    "duration": duration,
                })
            
            return normalized
            
        except Exception as e:
            logging.error(f"Failed to fetch closed positions: {e}")
            return []
    
    
    # ───────────────────────────────────────────────────────────────────────
    # DISPLAY RENDERING
    # ───────────────────────────────────────────────────────────────────────
    
    def show_snapshot(self):
        """Display current snapshot with closed positions"""
        enhanced_logger.display_table("")
        log_separator("=", 100, "cyan")
        
        self._render_open_positions()
        enhanced_logger.display_table("")
        self._render_closed_positions()
        
        log_separator("=", 100, "cyan")
        enhanced_logger.display_table("")
    
    def _render_open_positions(self):
        """Render open positions table"""
        positions = self._last_open_positions
        
        enhanced_logger.display_table("📊 LIVE POSITIONS (Bybit)", "green", attrs=["bold"])
        
        if not positions:
            enhanced_logger.display_table("— no open positions —", "yellow")
            return
        
        # Table header
        enhanced_logger.display_table(
            "┌─────┬────────┬──────┬──────┬─────────────┬─────────────┬──────────┬───────────┬──────────────┬───────────┐",
            "cyan"
        )
        enhanced_logger.display_table(
            "│  #  │ SYMBOL │ SIDE │ LEV  │    ENTRY    │   CURRENT   │  PNL %   │   PNL $   │  SL (ROE%)   │   IM $    │",
            "white", attrs=["bold"]
        )
        enhanced_logger.display_table(
            "├─────┼────────┼──────┼──────┼─────────────┼─────────────┼──────────┼───────────┼──────────────┼───────────┤",
            "cyan"
        )
        
        total_pnl = 0.0
        total_im = 0.0
        
        for i, pos in enumerate(positions, 1):
            sym = pos["symbol"].replace("/USDT:USDT", "").replace("USDT", "")[:8]
            side_text = "LONG" if pos["side"] == "long" else "SHORT"
            side_color = "green" if pos["side"] == "long" else "red"
            
            total_pnl += pos["pnl_usd"]
            total_im += pos["initial_margin"]
            
            # Calculate SL ROE
            sl_text = "NO SL"
            sl_color = "yellow"
            if pos["stop_loss"] and pos["stop_loss"] > 0:
                if pos["side"] == "long":
                    sl_price_pct = ((pos["stop_loss"] - pos["entry_price"]) / pos["entry_price"]) * 100
                else:
                    sl_price_pct = -((pos["stop_loss"] - pos["entry_price"]) / pos["entry_price"]) * 100
                
                sl_roe = sl_price_pct * pos["leverage"]
                sl_text = f"{sl_roe:+.2f}%"
                sl_color = "red" if sl_roe < 0 else "green"
            
            line = (
                colored(f"│{i:^5}│", "white") +
                colored(f"{sym:^8}", "cyan") + colored("│", "white") +
                colored(f"{side_text:^6}", side_color) + colored("│", "white") +
                colored(f"{int(pos['leverage']):^6}", "yellow") + colored("│", "white") +
                colored(f"${pos['entry_price']:.6f}".center(13), "white") + colored("│", "white") +
                colored(f"${pos['current_price']:.6f}".center(13), "cyan") + colored("│", "white") +
                colored(f"{pos['pnl_pct']:+.1f}%".center(10), pct_color(pos['pnl_pct'])) + colored("│", "white") +
                colored(f"{fmt_money(pos['pnl_usd']):>11}", pct_color(pos['pnl_usd'])) + colored("│", "white") +
                colored(f"{sl_text}".center(14), sl_color) + colored("│", "white") +
                colored(f"${pos['initial_margin']:.0f}".center(11), "white") + colored("│", "white")
            )
            logging.info(line)
        
        # Table footer
        enhanced_logger.display_table(
            "└─────┴────────┴──────┴──────┴─────────────┴─────────────┴──────────┴───────────┴──────────────┴───────────┘",
            "cyan"
        )
        
        # Summary
        self._render_wallet_summary(len(positions), total_pnl, total_im)
    
    
    def _render_wallet_summary(self, pos_count: int, total_pnl: float, allocated: float):
        """Render wallet summary for open positions"""
        try:
            # Get wallet info from position manager
            total_wallet = 200.0  # Default
            if self.position_manager and hasattr(self.position_manager, 'get_session_summary'):
                summary = self.position_manager.get_session_summary()
                total_wallet = summary.get('balance', 200.0)
            
            available = total_wallet - allocated
            
            # Calculate next cycle timer
            from config import TRADE_CYCLE_INTERVAL
            current_time = datetime.now()
            seconds_in_cycle = current_time.minute * 60 + current_time.second
            seconds_to_next = TRADE_CYCLE_INTERVAL - (seconds_in_cycle % TRADE_CYCLE_INTERVAL)
            timer = f"{seconds_to_next // 60}m{seconds_to_next % 60:02d}s"
            
            summary_line = (
                colored(f"💰 LIVE: {pos_count} pos", "white") +
                colored(" | ", "white") +
                colored(f"P&L: {fmt_money(total_pnl)}", pct_color(total_pnl)) +
                colored(" | ", "white") +
                colored(f"Allocated: ${allocated:.0f}", "yellow") +
                colored(" | ", "white") +
                colored(f"Available: ${available:.0f}", "cyan") +
                colored(" | ", "white") +
                colored(f"Next: {timer}", "magenta")
            )
            logging.info(summary_line)
            
        except Exception as e:
            logging.debug(f"Error in wallet summary: {e}")
    
    def _render_closed_positions(self):
        """Render closed positions table (from Bybit session data)"""
        positions = self._last_closed_positions
        
        enhanced_logger.display_table("🔒 CLOSED POSITIONS (Bybit - Session)", "magenta", attrs=["bold"])
        
        if not positions:
            enhanced_logger.display_table("— no closed positions in this session —", "yellow")
            return
        
        # Table header
        enhanced_logger.display_table(
            "┌─────┬────────┬──────────┬──────┬──────┬─────────────┬─────────────┬──────────┬───────────┬──────────┬──────────┬──────────┐",
            "cyan"
        )
        enhanced_logger.display_table(
            "│  #  │ SYMBOL │    ID    │ SIDE │ LEV  │   ENTRY     │    EXIT     │  PNL %   │   PNL $   │ OPENED   │  CLOSED  │ DURATION │",
            "white", attrs=["bold"]
        )
        enhanced_logger.display_table(
            "├─────┼────────┼──────────┼──────┼──────┼─────────────┼─────────────┼──────────┼───────────┼──────────┼──────────┼──────────┤",
            "cyan"
        )
        
        total_pnl = 0.0
        winning = 0
        
        for i, pos in enumerate(positions, 1):
            sym = pos["symbol"].replace("USDT", "")[:8]
            side_text = "LONG" if pos["side"] == "long" else "SHORT"
            side_color = "green" if pos["side"] == "long" else "red"
            
            total_pnl += pos["pnl_usd"]
            if pos["pnl_usd"] > 0:
                winning += 1
            
            # Format ID (time-based)
            id_display = "N/A"
            if pos["open_time"]:
                id_display = pos["open_time"].strftime("%H%M")
            
            # Format timestamps
            open_str = pos["open_time"].strftime("%H:%M:%S") if pos["open_time"] else "N/A"
            close_str = pos["close_time"].strftime("%H:%M:%S") if pos["close_time"] else "N/A"
            
            # Format duration
            duration_str = "N/A"
            if pos["duration"]:
                total_seconds = int(pos["duration"].total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                duration_str = f"{hours}h{minutes:02d}m" if hours > 0 else f"{minutes}m"
            
            line = (
                colored(f"│{i:^5}│", "white") +
                colored(f"{sym:^8}", "cyan") + colored("│", "white") +
                colored(f"{id_display:^10}", "yellow") + colored("│", "white") +
                colored(f"{side_text:^6}", side_color) + colored("│", "white") +
                colored(f"{pos['leverage']:^6}", "yellow") + colored("│", "white") +
                colored(f"${pos['entry_price']:.6f}".center(13), "white") + colored("│", "white") +
                colored(f"${pos['exit_price']:.6f}".center(13), "cyan") + colored("│", "white") +
                colored(f"{pos['pnl_pct']:+.1f}%".center(10), pct_color(pos['pnl_pct'])) + colored("│", "white") +
                colored(f"{fmt_money(pos['pnl_usd']):>11}", pct_color(pos['pnl_usd'])) + colored("│", "white") +
                colored(f"{open_str:^10}", "white") + colored("│", "white") +
                colored(f"{close_str:^10}", "white") + colored("│", "white") +
                colored(f"{duration_str:^10}", "magenta") + colored("│", "white")
            )
            logging.info(line)
        
        # Table footer
        enhanced_logger.display_table(
            "└─────┴────────┴──────────┴──────┴──────┴─────────────┴─────────────┴──────────┴───────────┴──────────┴──────────┴──────────┘",
            "cyan"
        )
        
        # Session summary
        self._render_session_summary(len(positions), total_pnl, winning)
    
    def _render_session_summary(self, trade_count: int, total_pnl: float, winning: int):
        """Render compact session summary with duration"""
        if trade_count == 0:
            return
        
        try:
            win_rate = (winning / trade_count * 100) if trade_count > 0 else 0
            
            # Calculate session duration
            session_duration = datetime.now() - self._session_start_time
            total_seconds = int(session_duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            
            if hours > 0:
                duration_str = f"{hours}h{minutes:02d}m"
            else:
                duration_str = f"{minutes}m"
            
            # Get balance info
            start_bal = 200.0
            curr_bal = 200.0
            if self.position_manager and hasattr(self.position_manager, 'get_session_summary'):
                summary = self.position_manager.get_session_summary()
                start_bal = summary.get('start_balance', 200.0)
                curr_bal = summary.get('balance', 200.0)
            
            net_change = curr_bal - start_bal
            net_change_pct = (net_change / start_bal * 100) if start_bal > 0 else 0
            
            # Calculate average PnL per trade
            avg_pnl = total_pnl / trade_count if trade_count > 0 else 0
            
            # Calculate trades per hour
            hours_float = total_seconds / 3600 if total_seconds > 0 else 1
            trades_per_hour = trade_count / hours_float
            
            # Render compact session summary
            enhanced_logger.display_table("")
            
            # Line 1: Main stats with session duration
            stats_line = (
                colored("📊 SESSION (", "cyan", attrs=['bold']) +
                colored(f"⏱️{duration_str}", "magenta", attrs=['bold']) +
                colored("): ", "cyan", attrs=['bold']) +
                colored("P&L: ", "white") +
                colored(f"{fmt_money(total_pnl)}", pct_color(total_pnl), attrs=['bold']) +
                colored(" | ", "white") +
                colored(f"Trades: {trade_count} ({trades_per_hour:.1f}/hr)", "white") +
                colored(" | ", "white") +
                colored("WR: ", "white") +
                colored(f"{win_rate:.1f}%", "green" if win_rate >= 60 else "yellow" if win_rate >= 40 else "red", attrs=['bold']) +
                colored(" | ", "white") +
                colored(f"${start_bal:.0f}➜${curr_bal:.0f}", "cyan") +
                colored(f" ({net_change_pct:+.1f}%)", "green" if net_change >= 0 else "red")
            )
            logging.info(stats_line)
            
            # Line 2: Additional insights (if significant)
            if trade_count >= 3:
                avg_line = (
                    colored("   📈 Avg Trade: ", "white") +
                    colored(f"{fmt_money(avg_pnl)}", pct_color(avg_pnl)) +
                    colored(" | ", "white") +
                    colored("Winning: ", "white") +
                    colored(f"{winning}", "green") +
                    colored(" | ", "white") +
                    colored("Losing: ", "white") +
                    colored(f"{trade_count - winning}", "red")
                )
                logging.info(avg_line)
            
        except Exception as e:
            logging.error(f"Error in session summary: {e}")
    


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

global_realtime_display = None

def initialize_global_realtime_display(position_manager=None):
    """Initialize global display instance"""
    global global_realtime_display
    global_realtime_display = RealTimePositionDisplay(position_manager)
    return global_realtime_display
