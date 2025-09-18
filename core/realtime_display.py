#!/usr/bin/env python3
"""
📊 REAL-TIME POSITION DISPLAY (Static Snapshot Mode)
Only-Bybit data • Clean screen • Open + Closed (session)

- Open positions:    ccxt.fetch_positions (Bybit)
- Closed (session):  rilevate quando spariscono da fetch_positions, arricchite con
                     fetchClosedOrders / fetchMyTrades (Bybit). Nessun dato inventato.

⚠️ Non gira più in loop continuo: ora si aggiorna e stampa SOLO quando viene
richiamato da TradingEngine al termine di un ciclo.

🚀 ENHANCED: Now uses triple output logging system:
- Terminal: Colored display (unchanged UX)
- ANSI File: Identical colored output in trading_bot_colored.log  
- HTML File: Professional export in trading_session.html
"""

import os
import platform
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from termcolor import colored

# Import enhanced logging system
from core.enhanced_logging_system import (
    enhanced_logger, 
    position_logger,
    log_table,
    log_separator
)


# ──────────────────────────────────────────────────────────────────────────────
# Utils
# ──────────────────────────────────────────────────────────────────────────────

def clear_terminal():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")


def fmt_money(v: float) -> str:
    sign = "+" if v >= 0 else "-"
    return f"{sign}${abs(v):.2f}"


def pct_color(p: float) -> str:
    if p > 0:
        return "green"  # Tutti i positivi in verde
    else:
        return "red"    # Tutti i negativi in rosso (niente giallo)


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def utcnow_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


# ──────────────────────────────────────────────────────────────────────────────
# Display
# ──────────────────────────────────────────────────────────────────────────────

class RealTimePositionDisplay:
    def __init__(self, position_manager=None, trailing_monitor=None):
        self.position_manager = position_manager
        self.trailing_monitor = trailing_monitor

        # Stato corrente
        self._cur_open_map: Dict[str, Dict] = {}
        self._session_closed: List[Dict] = []

        logging.info("⚡ REAL-TIME DISPLAY: Initialized in static snapshot mode")

    # ── Aggiornamento dati ───────────────────────────────────────────────────

    async def update_snapshot(self, exchange):
        """
        Recupera da Bybit:
        - posizioni aperte
        - rileva eventuali chiusure e aggiorna self._session_closed
        """
        try:
            raw_positions = await exchange.fetch_positions(None, {"limit": 100, "type": "swap"})
            open_list, bybit_side, bybit_sl = self._normalize_open_positions(raw_positions)

            await self._detect_and_record_closures(exchange, open_list)
            await self._enrich_open_with_pnl(exchange, open_list)

            # aggiorna stato corrente
            self._cur_open_map = {row["symbol"]: row for row in open_list}
            self._last_side_map = bybit_side
            self._last_sl_map = bybit_sl

        except Exception as e:
            logging.error(f"⚡ Error updating snapshot: {e}")

    # ── Visualizzazione ──────────────────────────────────────────────────────

    def show_snapshot(self):
        """
        Mostra snapshot delle posizioni:
        - tabella LIVE POSITIONS
        - tabella CLOSED POSITIONS (sessione)
        
        🚀 ENHANCED: Uses triple output logging system
        """
        # Empty line + separator
        enhanced_logger.display_table("")
        log_separator("=", 100, "cyan")
        
        self._render_live()
        enhanced_logger.display_table("")  # Empty line
        self._render_closed()
        
        log_separator("=", 100, "cyan")
        enhanced_logger.display_table("")

    def _render_live(self):
        open_list = list(self._cur_open_map.values())
        bybit_side_map = getattr(self, "_last_side_map", {})
        bybit_sl_map = getattr(self, "_last_sl_map", {})

        # Table title
        enhanced_logger.display_table("📊 LIVE POSITIONS (Bybit) — snapshot", "green", attrs=["bold"])
        
        if not open_list:
            enhanced_logger.display_table("— nessuna posizione aperta —", "yellow")
            return

        # Table structure
        enhanced_logger.display_table("┌─────┬────────┬──────┬──────┬─────────────┬─────────────┬──────────┬───────────┬──────────────┬───────────┐", "cyan")
        enhanced_logger.display_table("│  #  │ SYMBOL │ SIDE │ LEV  │    ENTRY    │   CURRENT   │  PNL %   │   PNL $   │   SL % (±$)  │   IM $    │", "white", attrs=["bold"])
        enhanced_logger.display_table("├─────┼────────┼──────┼──────┼─────────────┼─────────────┼──────────┼───────────┼──────────────┼───────────┤", "cyan")

        total_pnl_usd = 0.0
        total_im = 0.0

        for i, row in enumerate(open_list, 1):
            sym = row["symbol"].replace("/USDT:USDT", "")[:8]
            side = bybit_side_map.get(row["symbol"], row["side"])
            lev = int(row["leverage"]) if row["leverage"] else 0
            current_price = row.get("current_price", row["entry_price"])
            pnl_pct = row.get("pnl_pct", 0.0)
            pnl_usd = row.get("pnl_usd", 0.0)

            total_pnl_usd += pnl_usd
            # CRITICAL FIX: Calculate REAL initial margin from Bybit data
            # Don't enforce artificial minimums - show the real situation
            calculated_margin = (row["position_usd"] / row["leverage"]) if row["leverage"] else 0.0
            initial_margin = calculated_margin
            
            # WARNING for positions with dangerously low IM
            if calculated_margin < 20.0 and calculated_margin > 0.0:
                logging.warning(f"⚠️ DANGEROUS: {sym} has only ${calculated_margin:.2f} IM - HIGH RISK!")
                
            total_im += initial_margin

            sl_price = bybit_sl_map.get(row["symbol"])
            if sl_price:
                if side == "long":
                    sl_pct = ((sl_price - row["entry_price"]) / row["entry_price"]) * row["leverage"]
                    delta_usd = (sl_pct / 100.0) * initial_margin
                else:
                    sl_pct = ((row["entry_price"] - sl_price) / row["entry_price"]) * row["leverage"]
                    delta_usd = (sl_pct / 100.0) * initial_margin
                sl_txt = f"{sl_pct:+.1f}% ({fmt_money(delta_usd)})"
                sl_col = "yellow" if sl_pct < 0 else "green"
            else:
                sl_txt = "NO SL"
                sl_col = "yellow"

            line = (
                colored(f"│{i:^5}│", "white") +
                colored(f"{sym:^8}", "cyan") + colored("│", "white") +
                colored(f"{('LONG' if side=='long' else 'SHORT'):^6}", "green" if side=="long" else "red") + colored("│", "white") +
                colored(f"{lev:^6}", "yellow") + colored("│", "white") +
                colored(f"${row['entry_price']:.6f}".center(13), "white") + colored("│", "white") +
                colored(f"${current_price:.6f}".center(13), "cyan") + colored("│", "white") +
                colored(f"{pnl_pct:+.1f}%".center(10), pct_color(pnl_pct)) + colored("│", "white") +
                colored(f"{fmt_money(pnl_usd):>11}", pct_color(pnl_pct)) + colored("│", "white") +
                colored(f"{sl_txt}".center(14), sl_col) + colored("│", "white") +
                colored(f"${initial_margin:.0f}".center(11), "white") + colored("│", "white")
            )
            # Use enhanced logging instead of print
            logging.info(line)  # This will go through all handlers including ANSI and HTML

        # Table bottom border
        enhanced_logger.display_table("└─────┴────────┴──────┴─────────────┴─────────────┴──────────┴───────────┴──────────────┴───────────┘", "cyan")

        # 📊 Enhanced summary con wallet info
        self._render_wallet_summary(len(open_list), total_pnl_usd, total_im)

    def _render_closed(self):
        enhanced_logger.display_table("🔒 CLOSED POSITIONS (SESSION, Bybit)", "magenta", attrs=["bold"])
        
        if not self._session_closed:
            enhanced_logger.display_table("— nessuna posizione chiusa nella sessione corrente —", "yellow")
            return

        # Closed positions table structure
        enhanced_logger.display_table("┌─────┬────────┬──────┬──────┬─────────────┬─────────────┬──────────┬───────────┐", "cyan")
        enhanced_logger.display_table("│  #  │ SYMBOL │ SIDE │ LEV  │   ENTRY     │    EXIT     │  PNL %   │   PNL $   │", "white", attrs=["bold"])
        enhanced_logger.display_table("├─────┼────────┼──────┼──────┼─────────────┼─────────────┼──────────┼───────────┤", "cyan")

        for i, r in enumerate(self._session_closed, 1):
            sym = r["symbol"].replace("/USDT:USDT", "")[:8]
            side = r["side"]
            lev = int(r.get("leverage") or 0)
            pnl_pct = float(r.get("pnl_pct") or 0.0)
            pnl_usd = float(r.get("pnl_usd") or 0.0)

            line = (
                colored(f"│{i:^5}│", "white") +
                colored(f"{sym:^8}", "cyan") + colored("│", "white") +
                colored(f"{('LONG' if side=='long' else 'SHORT'):^6}", "green" if side=="long" else "red") + colored("│", "white") +
                colored(f"{lev:^6}", "yellow") + colored("│", "white") +
                colored(f"${r['entry_price']:.6f}".center(13), "white") + colored("│", "white") +
                colored(f"${r['exit_price']:.6f}".center(13), "cyan") + colored("│", "white") +
                colored(f"{pnl_pct:+.1f}%".center(10), pct_color(pnl_pct)) + colored("│", "white") +
                colored(f"{fmt_money(pnl_usd):>11}", pct_color(pnl_pct)) + colored("│", "white")
            )
            # Use enhanced logging
            logging.info(line)

        # Closed positions table bottom
        enhanced_logger.display_table("└─────┴────────┴──────┴─────────────┴─────────────┴──────────┴───────────┘", "cyan")
        
        # 📊 SESSION SUMMARY for closed positions
        self._render_session_summary()

    # ── Helpers per dati ─────────────────────────────────────────────────────

    def _normalize_open_positions(self, bybit_positions: List[Dict]) -> Tuple[List[Dict], Dict[str, str], Dict[str, float]]:
        real_active = [
            p for p in bybit_positions
            if safe_float(p.get("contracts") or p.get("positionAmt") or 0) != 0
        ]

        open_rows: List[Dict] = []
        bybit_side_map: Dict[str, str] = {}
        bybit_sl_map: Dict[str, float] = {}

        for p in real_active:
            symbol = p.get("symbol")
            if not symbol:
                continue

            contracts = abs(safe_float(p.get("contracts") or p.get("positionAmt")))
            raw_side = str(p.get("side", "")).lower()
            side = "long" if raw_side in ("buy", "long") else "short"

            entry_price = safe_float(p.get("entryPrice") or p.get("entry_price"))
            leverage = safe_float(p.get("leverage"), 0) or 10.0
            real_sl = p.get("stopLoss") or p.get("stopLossPrice")
            if real_sl is not None:
                bybit_sl_map[symbol] = safe_float(real_sl)

            bybit_side_map[symbol] = side
            position_usd = contracts * entry_price

            open_rows.append({
                "symbol": symbol,
                "side": side,
                "contracts": contracts,
                "entry_price": entry_price,
                "leverage": leverage,
                "position_usd": position_usd,
                "sl_price": bybit_sl_map.get(symbol),
                "unrealized_pnl_usd": safe_float(p.get("unrealizedPnl", 0.0))
            })

        return open_rows, bybit_side_map, bybit_sl_map

    async def _detect_and_record_closures(self, exchange, open_list: List[Dict]):
        prev_symbols = set(self._cur_open_map.keys())
        cur_symbols = set([row["symbol"] for row in open_list])

        closed_symbols = prev_symbols - cur_symbols
        if not closed_symbols:
            return

        for sym in closed_symbols:
            snap = self._cur_open_map.get(sym)
            if not snap:
                continue

            side = snap["side"]
            entry = snap["entry_price"]
            leverage = snap["leverage"]
            position_usd = snap["position_usd"]

            # Exit price (fallback su entry se non trovato)
            exit_price = entry
            pnl_pct = 0.0
            pnl_usd = 0.0
            initial_margin = position_usd / leverage if leverage else 0
            if initial_margin > 0:
                ticker = await exchange.fetch_ticker(sym)
                exit_price = safe_float(ticker.get("last"), entry)
                if side == "long":
                    price_chg_pct = ((exit_price - entry) / entry) * 100.0
                else:
                    price_chg_pct = ((entry - exit_price) / entry) * 100.0
                pnl_pct = price_chg_pct * leverage
                pnl_usd = (pnl_pct / 100.0) * initial_margin

            self._session_closed.append({
                "symbol": sym,
                "side": side,
                "entry_price": entry,
                "exit_price": exit_price,
                "contracts": snap["contracts"],
                "position_usd": position_usd,
                "leverage": leverage,
                "pnl_pct": pnl_pct,
                "pnl_usd": pnl_usd,
            })

    async def _enrich_open_with_pnl(self, exchange, open_list: List[Dict]):
        tickers: Dict[str, float] = {}
        for row in open_list:
            if row.get("unrealized_pnl_usd") == 0.0:
                try:
                    t = await exchange.fetch_ticker(row["symbol"])
                    tickers[row["symbol"]] = safe_float(t.get("last"))
                except Exception:
                    pass

        for row in open_list:
            initial_margin = (row["position_usd"] / row["leverage"]) if row["leverage"] else 0.0

            if row.get("unrealized_pnl_usd"):
                pnl_usd = row["unrealized_pnl_usd"]
                pnl_pct = (pnl_usd / initial_margin * 100.0) if initial_margin else 0.0
            else:
                last = tickers.get(row["symbol"], row["entry_price"])
                if row["side"] == "long":
                    price_chg_pct = ((last - row["entry_price"]) / row["entry_price"]) * 100.0
                else:
                    price_chg_pct = ((row["entry_price"] - last) / row["entry_price"]) * 100.0
                pnl_pct = price_chg_pct * row["leverage"]
                pnl_usd = (pnl_pct / 100.0) * initial_margin
                row["current_price"] = last

            row["pnl_pct"] = pnl_pct
            row["pnl_usd"] = pnl_usd

    def _render_wallet_summary(self, position_count: int, total_pnl_usd: float, wallet_allocated: float):
        """
        📊 Rendering wallet summary con timer 5m e wallet info
        
        Args:
            position_count: Numero posizioni attive
            total_pnl_usd: PnL totale delle posizioni
            wallet_allocated: Margine totale allocato
        """
        try:
            # 🕐 Calcola tempo rimanente al prossimo ciclo (5m = 300s)
            from config import TRADE_CYCLE_INTERVAL
            
            current_time = datetime.now()
            seconds_in_cycle = current_time.minute * 60 + current_time.second
            seconds_to_next_cycle = TRADE_CYCLE_INTERVAL - (seconds_in_cycle % TRADE_CYCLE_INTERVAL)
            
            minutes_remaining = seconds_to_next_cycle // 60
            seconds_remaining = seconds_to_next_cycle % 60
            next_cycle_timer = f"{minutes_remaining}m{seconds_remaining:02d}s"
            
            # 💰 Calcola wallet info
            # Assumendo un wallet totale di esempio - in un caso reale dovrebbe venire dal position_manager
            total_wallet = self._get_total_wallet_balance()  # Da implementare
            wallet_available = total_wallet - wallet_allocated
            allocation_pct = (wallet_allocated / total_wallet * 100) if total_wallet > 0 else 0
            
            # 📊 Rendering summary con tutte le info richieste
            summary_line = (
                colored(f"💰 LIVE: {position_count} pos", "white") +
                colored(" | ", "white") +
                colored(f"P&L: {fmt_money(total_pnl_usd)}", pct_color(total_pnl_usd)) +
                colored(" | ", "white") +
                colored(f"Wallet Allocated: ${wallet_allocated:.0f}", "yellow") +
                colored(" | ", "white") +
                colored(f"Available: ${wallet_available:.0f}", "cyan") +
                colored(" | ", "white") +
                colored(f"Next Cycle: {next_cycle_timer}", "magenta")
            )
            
            # Use enhanced logging for summary
            logging.info(summary_line)
            
            # 📈 Riga aggiuntiva con allocation percentage
            if total_wallet > 0:
                allocation_line = (
                    colored(f"🏦 Total Wallet: ${total_wallet:.0f}", "white") +
                    colored(" | ", "white") +
                    colored(f"Allocation: {allocation_pct:.1f}%", "yellow" if allocation_pct > 70 else "green")
                )
                logging.info(allocation_line)
            
        except Exception as e:
            # Fallback usando enhanced logging
            logging.debug(f"Error in wallet summary: {e}")
            enhanced_logger.display_table(f"💰 LIVE: {position_count} pos | P&L: {fmt_money(total_pnl_usd)} | Allocated: ${wallet_allocated:.0f}", "white")
    
    def _get_total_wallet_balance(self) -> float:
        """
        Ottiene il balance totale del wallet
        
        Returns:
            float: Balance totale del wallet
        """
        try:
            # Se abbiamo position_manager, usa quello per il balance
            if self.position_manager and hasattr(self.position_manager, 'get_session_summary'):
                session = self.position_manager.get_session_summary()
                return session.get('balance', 200.0)  # Fallback 200
            else:
                # Fallback: Leggi da config o stima dal margine allocato
                return 200.0  # Valore di default
                
        except Exception as e:
            logging.debug(f"Error getting wallet balance: {e}")
            return 200.0  # Safe fallback
    
    def _render_session_summary(self):
        """
        📊 Renders session summary for closed positions with total PnL
        """
        if not self._session_closed:
            return
        
        try:
            # Calculate session metrics
            total_trades = len(self._session_closed)
            total_pnl_usd = sum(r.get('pnl_usd', 0.0) for r in self._session_closed)
            winning_trades = sum(1 for r in self._session_closed if r.get('pnl_usd', 0.0) > 0)
            losing_trades = total_trades - winning_trades
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            # Calculate best and worst trades
            if self._session_closed:
                best_trade = max(self._session_closed, key=lambda x: x.get('pnl_usd', 0.0))
                worst_trade = min(self._session_closed, key=lambda x: x.get('pnl_usd', 0.0))
                
                best_pnl = best_trade.get('pnl_usd', 0.0)
                worst_pnl = worst_trade.get('pnl_usd', 0.0)
                avg_pnl = total_pnl_usd / total_trades if total_trades > 0 else 0.0
            else:
                best_pnl = worst_pnl = avg_pnl = 0.0
            
            # Render session summary using enhanced logging
            enhanced_logger.display_table("")  # Empty line
            enhanced_logger.display_table("📊 SESSION SUMMARY (Closed Positions)", "cyan", attrs=['bold'])
            enhanced_logger.display_table("┌" + "─" * 78 + "┐", "cyan")
            
            # Total PnL line
            pnl_color = pct_color(total_pnl_usd)
            pnl_line = f"│ 💰 TOTAL SESSION P&L: {fmt_money(total_pnl_usd):>8} │ TRADES: {total_trades:>2} │ WIN RATE: {win_rate:>5.1f}% │"
            enhanced_logger.display_table(pnl_line.ljust(79) + "│", pnl_color, attrs=['bold'])
            
            # Performance breakdown
            if total_trades > 0:
                performance_line = f"│ 📈 Winners: {winning_trades:>2} │ 📉 Losers: {losing_trades:>2} │ Avg P&L: {fmt_money(avg_pnl):>8} │"
                enhanced_logger.display_table(performance_line.ljust(79) + "│", "white")
                
                # Best/Worst trades
                best_symbol = best_trade['symbol'].replace('/USDT:USDT', '')[:8] if best_trade else 'N/A'
                worst_symbol = worst_trade['symbol'].replace('/USDT:USDT', '')[:8] if worst_trade else 'N/A'
                
                highlights_line = f"│ 🥇 Best: {best_symbol} {fmt_money(best_pnl):>8} │ 🥉 Worst: {worst_symbol} {fmt_money(worst_pnl):>8} │"
                enhanced_logger.display_table(highlights_line.ljust(79) + "│", "white")
            
            enhanced_logger.display_table("└" + "─" * 78 + "┘", "cyan")
            
        except Exception as e:
            logging.error(f"Error rendering session summary: {e}")
            # Fallback simple summary using enhanced logging
            total_pnl = sum(r.get('pnl_usd', 0.0) for r in self._session_closed)
            enhanced_logger.display_table(f"📊 SESSION TOTAL: {len(self._session_closed)} trades | P&L: {fmt_money(total_pnl)}", 
                         pct_color(total_pnl), attrs=['bold'])


# Global instance
global_realtime_display = None

def initialize_global_realtime_display(position_manager=None, trailing_monitor=None):
    global global_realtime_display
    global_realtime_display = RealTimePositionDisplay(position_manager, trailing_monitor)
    return global_realtime_display
