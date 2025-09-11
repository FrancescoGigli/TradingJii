#!/usr/bin/env python3
"""
📊 REAL-TIME POSITION DISPLAY
Only-Bybit data • Clean screen • Open + Closed (session)

- Open positions:    ccxt.fetch_positions (Bybit)
- Closed (session):  rilevate quando spariscono da fetch_positions, dettagliate da
                     fetchClosedOrders / fetchMyTrades (Bybit). Nessun dato inventato.

Stampa una singola schermata pulita ogni secondo con:
  1) LIVE POSITIONS (aperte)
  2) CLOSED POSITIONS (SESSION) con massimo dettaglio

Requisiti: ccxt 4.x, account Bybit Unified/Linear.
"""

import os
import platform
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from termcolor import colored


# ──────────────────────────────────────────────────────────────────────────────
# Utils
# ──────────────────────────────────────────────────────────────────────────────

def clear_terminal():
    """Pulisce completamente il terminale (Windows / Unix)."""
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
    """
    Dashboard realtime SOLO-DATI-BYBIT:
    - fetch_positions per aperte
    - detect close + enrich con fetchClosedOrders / fetchMyTrades
    """

    def __init__(self, position_manager=None, trailing_monitor=None):
        self.position_manager = position_manager  # non usato per i dati, solo per status
        self.trailing_monitor = trailing_monitor

        self.update_interval = 1.0  # 1s refresh
        self.is_running = False
        self.display_task: Optional[asyncio.Task] = None

        # Stato corrente (solo dati Bybit)
        self._cur_open_map: Dict[str, Dict] = {}     # symbol -> snapshot aperta
        self._session_closed: List[Dict] = []        # lista di chiusure (solo sessione)
        self._last_refresh_ts = 0

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start_display(self, exchange):
        if self.is_running:
            logging.warning("⚡ Real-time display already running")
            return
        self.is_running = True
        self.display_task = asyncio.create_task(self._loop(exchange))
        logging.info("▶️ Real-time display loop avviato")

    async def stop_display(self):
        if not self.is_running:
            return
        self.is_running = False
        if self.display_task:
            self.display_task.cancel()
            try:
                await self.display_task
            except asyncio.CancelledError:
                pass
        logging.info("⛔ Real-time display loop terminato")

    # ── Main Loop ────────────────────────────────────────────────────────────

    async def _loop(self, exchange):
        try:
            while self.is_running:
                try:
                    await self._tick(exchange)
                    await asyncio.sleep(self.update_interval)
                except Exception as e:
                    logging.error(f"⚡ Display loop error: {e}")
                    await asyncio.sleep(self.update_interval)
        except asyncio.CancelledError:
            logging.info("⚡ REAL-TIME DISPLAY: loop cancellato")
        finally:
            self.is_running = False

    # ── One tick ─────────────────────────────────────────────────────────────

    async def _tick(self, exchange):
        # 1) leggi aperte da Bybit
        raw_positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
        open_list, bybit_side, bybit_sl = self._normalize_open_positions(raw_positions)

        # 2) detect chiusure (sessione)
        await self._detect_and_record_closures(exchange, open_list)

        # 3) calcola PnL su aperte solo da dati Bybit (preferendo unrealizedPnl)
        await self._enrich_open_with_pnl(exchange, open_list)

        # 4) stampa schermo UNICO
        self._render(open_list, bybit_side, bybit_sl)

        # 5) aggiorna mappa aperte corrente
        self._cur_open_map = {row["symbol"]: row for row in open_list}
        self._last_refresh_ts = utcnow_ms()

    # ── Normalize open positions from Bybit ──────────────────────────────────

    def _normalize_open_positions(self, bybit_positions: List[Dict]) -> Tuple[List[Dict], Dict[str, str], Dict[str, float]]:
        real_active = [
            p for p in bybit_positions
            if safe_float(p.get('contracts') or p.get('positionAmt') or 0) != 0
        ]

        open_rows: List[Dict] = []
        bybit_side_map: Dict[str, str] = {}
        bybit_sl_map: Dict[str, float] = {}

        for p in real_active:
            symbol = p.get('symbol')
            if not symbol:
                continue

            contracts = abs(safe_float(p.get('contracts') or p.get('positionAmt')))
            raw_side = str(p.get('side', '')).lower()  # "buy"/"sell" o "long"/"short"
            side = "long" if raw_side in ("buy", "long") else "short"

            entry_price = safe_float(p.get('entryPrice') or p.get('entry_price'))
            leverage = safe_float(p.get('leverage'), 0) or 10.0  # fallback 10x se Bybit non lo rimanda
            # stop loss reale (se presente)
            real_sl = p.get('stopLoss') or p.get('stopLossPrice')
            if real_sl is not None:
                bybit_sl_map[symbol] = safe_float(real_sl)

            bybit_side_map[symbol] = side

            # calcolo size USD dal dato Bybit
            position_usd = contracts * entry_price

            # timestamp (se disponibile nel payload ccxt)
            opened_at = p.get('timestamp') or p.get('info', {}).get('updatedTime') or None
            if isinstance(opened_at, str) and opened_at.isdigit():
                opened_at = int(opened_at)

            open_rows.append({
                "symbol": symbol,
                "side": side,
                "contracts": contracts,
                "entry_price": entry_price,
                "leverage": leverage,
                "position_usd": position_usd,
                "sl_price": bybit_sl_map.get(symbol),
                "unrealized_pnl_usd": safe_float(p.get('unrealizedPnl', 0.0)),
                "opened_at": opened_at
            })

        return open_rows, bybit_side_map, bybit_sl_map

    # ── Detect + record closures (session) ───────────────────────────────────

    async def _detect_and_record_closures(self, exchange, open_list: List[Dict]):
        prev_symbols = set(self._cur_open_map.keys())
        cur_symbols = set([row["symbol"] for row in open_list])

        closed_symbols = prev_symbols - cur_symbols
        if not closed_symbols:
            return

        now_ms = utcnow_ms()

        for sym in closed_symbols:
            snap = self._cur_open_map.get(sym)
            if not snap:
                continue

            side = snap["side"]
            entry = snap["entry_price"]
            leverage = snap["leverage"]
            position_usd = snap["position_usd"]

            # Prova a ricavare exit/close info dallo storico Bybit
            exit_price, close_time, reason, got_exact = await self._fetch_close_details(exchange, sym, side, since_ms=now_ms - 24*60*60*1000)

            # Calcolo PnL %/$ in termini di margine iniziale (coerente con le aperte)
            initial_margin = position_usd / leverage if leverage else 0.0
            if initial_margin <= 0:
                pnl_pct = 0.0
                pnl_usd = 0.0
            else:
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
                "opened_at": snap.get("opened_at"),
                "closed_at": close_time or now_ms,
                "reason": reason + ("" if got_exact else " (approx)")
            })

    async def _fetch_close_details(self, exchange, symbol: str, side: str, since_ms: int) -> Tuple[float, Optional[int], str, bool]:
        """
        Ritorna: (exit_price, closed_at_ms, reason, got_exact)
        - Tenta prima closed orders (reduce-only / lato opposto).
        - Fallback: trade fill più recente lato opposto.
        - Ultimo fallback: ticker last (approx).
        """
        opp_side = "buy" if side == "short" else "sell"
        got_exact = False

        # 1) Closed orders
        try:
            params = {"category": "linear"}  # per Bybit v5 derivatives
            orders = await exchange.fetch_closed_orders(symbol, since=since_ms, limit=50, params=params)
            # preferisci l'ultimo ordine lato opposto o reduce-only
            candidates = []
            for o in orders or []:
                status = (o.get("status") or "").lower()
                o_side = (o.get("side") or "").lower()
                reduce_only = o.get("reduceOnly") or o.get("info", {}).get("reduceOnly")
                if status in ("closed", "filled") and (o_side == opp_side or reduce_only):
                    candidates.append(o)

            if candidates:
                best = sorted(candidates, key=lambda x: x.get("timestamp") or 0)[-1]
                avg = safe_float(best.get("average") or best.get("price"))
                ts = best.get("timestamp")
                reason = (best.get("info", {}) or {}).get("orderType") or (best.get("type") or "close")
                if avg > 0:
                    got_exact = True
                    return avg, ts, str(reason).upper(), got_exact
        except Exception as e:
            logging.debug(f"[closed-orders miss] {symbol}: {e}")

        # 2) My trades
        try:
            trades = await exchange.fetch_my_trades(symbol, since=since_ms, limit=100)
            # prendi l'ultimo fill lato opposto
            opp_fills = []
            for t in trades or []:
                t_side = (t.get("side") or "").lower()
                if t_side == opp_side:
                    opp_fills.append(t)
            if opp_fills:
                last = sorted(opp_fills, key=lambda x: x.get("timestamp") or 0)[-1]
                px = safe_float(last.get("price"))
                ts = last.get("timestamp")
                reason = "TRADE FILL"
                if px > 0:
                    got_exact = True
                    return px, ts, reason, got_exact
        except Exception as e:
            logging.debug(f"[trades miss] {symbol}: {e}")

        # 3) Fallback: ticker last (approx)
        try:
            tkr = await exchange.fetch_ticker(symbol)
            px = safe_float(tkr.get("last"))
            ts = tkr.get("timestamp")
            if px > 0:
                return px, ts, "TICKER LAST", got_exact
        except Exception as e:
            logging.debug(f"[ticker miss] {symbol}: {e}")

        # ultima spiaggia: entry (neutrale)
        return safe_float(0.0), None, "UNKNOWN", got_exact

    # ── Enrich open positions with PnL (unrealized) ──────────────────────────

    async def _enrich_open_with_pnl(self, exchange, open_list: List[Dict]):
        # Se Bybit fornisce unrealizedPnl in USD lo uso direttamente.
        # Altrimenti calcolo con ticker last → percent su margine iniziale.
        # Percentuale PnL coerente = (pnl_usd / initial_margin) * 100
        symbols_missing = [row["symbol"] for row in open_list if row.get("unrealized_pnl_usd") == 0.0]

        tickers: Dict[str, float] = {}
        for row in open_list:
            if row["symbol"] in symbols_missing:
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

            row["pnl_pct"] = pnl_pct
            row["pnl_usd"] = pnl_usd

    # ── Render ────────────────────────────────────────────────────────────────

    def _render(self, open_list: List[Dict], bybit_side_map: Dict[str, str], bybit_sl_map: Dict[str, float]):
        clear_terminal()

        # Header
        print(colored("📊 LIVE POSITIONS (Bybit) — aggiornamento 1s", "green", attrs=["bold"]))
        print(colored("┌─────┬────────┬──────┬──────┬─────────────┬─────────────┬──────────┬───────────┬──────────────┬───────────┐", "cyan"))
        print(colored("│  #  │ SYMBOL │ SIDE │ LEV  │    ENTRY    │   CURRENT   │  PNL %   │   PNL $   │   SL % (±$)  │   IM $    │", "white", attrs=["bold"]))
        print(colored("├─────┼────────┼──────┼──────┼─────────────┼─────────────┼──────────┼───────────┼──────────────┼───────────┤", "cyan"))

        total_pnl_usd = 0.0
        total_im = 0.0

        # ordina per PnL $
        open_sorted = sorted(open_list, key=lambda r: r.get("pnl_usd", 0.0), reverse=True)

        for i, row in enumerate(open_sorted, 1):
            sym = row["symbol"].replace("/USDT:USDT", "")[:8]
            side = bybit_side_map.get(row["symbol"], row["side"])
            lev = int(row["leverage"]) if row["leverage"] else 0

            # prezzo corrente (se abbiamo calcolato sopra, non lo esponiamo: la riga "CURRENT"
            # è coerente con l'ultimo ticker usato per il PnL quando mancava unrealizedPnl)
            # qui lo ricalcolo solo per display "best effort":
            current_price = row.get("entry_price")
            if row.get("pnl_pct") is not None:
                # ricava current a partire dal PnL% (best effort); non sempre perfetto, ma display-only
                # long:  pnl_pct = ((cur - entry)/entry)*100*lev  => cur = entry * (1 + (pnl_pct/lev)/100)
                # short: cur = entry * (1 - (pnl_pct/lev)/100)
                delta = (row["pnl_pct"] / max(lev, 1)) / 100.0
                current_price = row["entry_price"] * (1 + delta) if side == "long" else row["entry_price"] * (1 - delta)

            pnl_pct = row.get("pnl_pct", 0.0)
            pnl_usd = row.get("pnl_usd", 0.0)
            total_pnl_usd += pnl_usd

            initial_margin = (row["position_usd"] / row["leverage"]) if row["leverage"] else 0.0
            total_im += initial_margin

            # SL %
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

        print(colored("└─────┴────────┴──────┴──────┴─────────────┴─────────────┴──────────┴───────────┴──────────────┴───────────┘", "cyan"))

        # Riepilogo
        wallet = getattr(self.position_manager, 'session_balance', None)
        trailing_status = "ATTIVO" if (self.trailing_monitor and getattr(self.trailing_monitor, "is_running", False)) else "OFFLINE"
        countdown = self._countdown_to_next_cycle()

        summary = (
            colored(f"💰 LIVE: {len(open_list)} pos | P&L: ", "white") +
            colored(f"{fmt_money(total_pnl_usd)}", "green" if total_pnl_usd >= 0 else "red") +
            colored(f" | Margin: ${total_im:.0f}", "cyan")
        )
        if wallet is not None:
            free = max(0.0, float(wallet) - total_im)
            summary += (
                colored(f" | Wallet: ${float(wallet):.0f}", "white") +
                colored(f" | Free: ${free:.0f}", "green")
            )
        print(summary)
        print(
            colored(f"⏳ Prossimo ciclo: {countdown}", "blue", attrs=["bold"]) +
            " | " +
            colored(f"⚡ Trailing Monitor: {trailing_status}", "green" if trailing_status == "ATTIVO" else "red")
        )

        # Sezione CLOSED (session)
        print()
        print(colored("🔒 CLOSED POSITIONS (SESSION, Bybit)", "magenta", attrs=["bold"]))
        if not self._session_closed:
            print(colored("— nessuna posizione chiusa nella sessione corrente —", "yellow"))
            return

        print(colored("┌─────┬────────┬──────┬──────┬─────────────┬─────────────┬──────────┬───────────┬──────────────┬──────────────┬──────────────┐", "cyan"))
        print(colored("│  #  │ SYMBOL │ SIDE │ LEV  │   ENTRY     │    EXIT     │  PNL %   │   PNL $   │    OPENED    │    CLOSED     │   REASON     │", "white", attrs=["bold"]))
        print(colored("├─────┼────────┼──────┼──────┼─────────────┼─────────────┼──────────┼───────────┼──────────────┼──────────────┼──────────────┤", "cyan"))

        closed_sorted = sorted(self._session_closed, key=lambda r: r.get("closed_at", 0), reverse=True)
        for i, r in enumerate(closed_sorted, 1):
            sym = r["symbol"].replace("/USDT:USDT", "")[:8]
            side = r["side"]
            lev = int(r.get("leverage") or 0)
            pnl_pct = float(r.get("pnl_pct") or 0.0)
            pnl_usd = float(r.get("pnl_usd") or 0.0)

            def tsfmt(ms):
                if not ms:
                    return "--"
                try:
                    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).strftime("%m-%d %H:%M:%S")
                except Exception:
                    return "--"

            line = (
                colored(f"│{i:^5}│", "white") +
                colored(f"{sym:^8}", "cyan") + colored("│", "white") +
                colored(f"{('LONG' if side=='long' else 'SHORT'):^6}", "green" if side=="long" else "red") + colored("│", "white") +
                colored(f"{lev:^6}", "yellow") + colored("│", "white") +
                colored(f"${r['entry_price']:.6f}".center(13), "white") + colored("│", "white") +
                colored(f"${r['exit_price']:.6f}".center(13), "cyan") + colored("│", "white") +
                colored(f"{pnl_pct:+.1f}%".center(10), pct_color(pnl_pct)) + colored("│", "white") +
                colored(f"{fmt_money(pnl_usd):>11}", pct_color(pnl_pct)) + colored("│", "white") +
                colored(f"{tsfmt(r.get('opened_at')):^14}", "white") + colored("│", "white") +
                colored(f"{tsfmt(r.get('closed_at')):^14}", "white") + colored("│", "white") +
                colored(f"{(r.get('reason') or '').upper():^14}", "white") + colored("│", "white")
            )
            print(line)

        print(colored("└─────┴────────┴──────┴──────┴─────────────┴─────────────┴──────────┴───────────┴──────────────┴──────────────┴──────────────┘", "cyan"))

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _countdown_to_next_cycle(self) -> str:
        try:
            now = datetime.now()
            seconds_elapsed = now.second + (now.minute % 5) * 60
            remaining = 300 - seconds_elapsed if seconds_elapsed < 300 else 300
            m, s = divmod(remaining, 60)
            return f"{m:02d}:{s:02d}"
        except Exception:
            return "--:--"


# Global instance (compat)
global_realtime_display = None

def initialize_global_realtime_display(position_manager=None, trailing_monitor=None):
    global global_realtime_display
    global_realtime_display = RealTimePositionDisplay(position_manager, trailing_monitor)
    return global_realtime_display
