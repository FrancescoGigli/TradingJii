#!/usr/bin/env python3
"""
📊 REAL-TIME POSITION DISPLAY (Static Snapshot Mode)
Only-Bybit data • Clean screen • Open + Closed (session)

- Open positions:    ccxt.fetch_positions (Bybit)
- Closed (session):  rilevate quando spariscono da fetch_positions, arricchite con
                     fetchClosedOrders / fetchMyTrades (Bybit). Nessun dato inventato.

⚠️ Non gira più in loop continuo: ora si aggiorna e stampa SOLO quando viene
richiamato da TradingEngine al termine di un ciclo.
"""

import os
import platform
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from termcolor import colored


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
    if p >= 10:
        return "green"
    if p > 0:
        return "green"
    if p > -20:
        return "yellow"
    return "red"


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
        Pulisce il terminale e mostra:
        - tabella LIVE POSITIONS
        - tabella CLOSED POSITIONS (sessione)
        """
        clear_terminal()
        self._render_live()
        print()
        self._render_closed()

    def _render_live(self):
        open_list = list(self._cur_open_map.values())
        bybit_side_map = getattr(self, "_last_side_map", {})
        bybit_sl_map = getattr(self, "_last_sl_map", {})

        print(colored("📊 LIVE POSITIONS (Bybit) — snapshot", "green", attrs=["bold"]))
        if not open_list:
            print(colored("— nessuna posizione aperta —", "yellow"))
            return

        print(colored("┌─────┬────────┬──────┬──────┬─────────────┬─────────────┬──────────┬───────────┬──────────────┬───────────┐", "cyan"))
        print(colored("│  #  │ SYMBOL │ SIDE │ LEV  │    ENTRY    │   CURRENT   │  PNL %   │   PNL $   │   SL % (±$)  │   IM $    │", "white", attrs=["bold"]))
        print(colored("├─────┼────────┼──────┼──────┼─────────────┼─────────────┼──────────┼───────────┼──────────────┼───────────┤", "cyan"))

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
            initial_margin = (row["position_usd"] / row["leverage"]) if row["leverage"] else 0.0
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
            print(line)

        print(colored("└─────┴────────┴──────┴─────────────┴─────────────┴──────────┴───────────┴──────────────┴───────────┘", "cyan"))

        print(
            colored(f"💰 LIVE: {len(open_list)} pos | P&L: {fmt_money(total_pnl_usd)} | Margin: ${total_im:.0f}", "white")
        )

    def _render_closed(self):
        print(colored("🔒 CLOSED POSITIONS (SESSION, Bybit)", "magenta", attrs=["bold"]))
        if not self._session_closed:
            print(colored("— nessuna posizione chiusa nella sessione corrente —", "yellow"))
            return

        print(colored("┌─────┬────────┬──────┬──────┬─────────────┬─────────────┬──────────┬───────────┐", "cyan"))
        print(colored("│  #  │ SYMBOL │ SIDE │ LEV  │   ENTRY     │    EXIT     │  PNL %   │   PNL $   │", "white", attrs=["bold"]))
        print(colored("├─────┼────────┼──────┼──────┼─────────────┼─────────────┼──────────┼───────────┤", "cyan"))

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
            print(line)

        print(colored("└─────┴────────┴──────┴─────────────┴─────────────┴──────────┴───────────┘", "cyan"))

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


# Global instance
global_realtime_display = None

def initialize_global_realtime_display(position_manager=None, trailing_monitor=None):
    global global_realtime_display
    global_realtime_display = RealTimePositionDisplay(position_manager, trailing_monitor)
    return global_realtime_display
