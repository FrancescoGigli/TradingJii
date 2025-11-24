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
    def __init__(self, position_manager=None):
        self.position_manager = position_manager

        # Stato corrente
        self._cur_open_map: Dict[str, Dict] = {}
        self._session_closed: List[Dict] = []
        self._verified_closed_ids = set()  # Track positions with verified PnL from Bybit

        logging.info("⚡ REAL-TIME DISPLAY: Initialized in static snapshot mode")

    # ── Aggiornamento dati ───────────────────────────────────────────────────

    async def update_snapshot(self, exchange):
        """
        Recupera da Bybit:
        - posizioni aperte
        - rileva eventuali chiusure e aggiorna self._session_closed
        - VERIFICA PnL reale per posizioni chiuse
        """
        try:
            raw_positions = await exchange.fetch_positions(None, {"limit": 100, "type": "swap"})
            open_list, bybit_side, bybit_sl = self._normalize_open_positions(raw_positions)

            await self._detect_and_record_closures(exchange, open_list)
            await self._enrich_open_with_pnl(exchange, open_list)
            
            # Verify PnL for closed positions
            if self.position_manager:
                await self._verify_closed_positions_pnl(exchange)

            # aggiorna stato corrente
            self._cur_open_map = {row["symbol"]: row for row in open_list}
            self._last_side_map = bybit_side
            self._last_sl_map = bybit_sl

        except Exception as e:
            logging.error(f"⚡ Error updating snapshot: {e}")
            
    async def _verify_closed_positions_pnl(self, exchange):
        """Verify and update PnL for closed positions using Bybit data"""
        try:
            closed_positions = self.position_manager.safe_get_closed_positions()
            
            for pos in closed_positions:
                # Skip if already verified
                if pos.position_id in self._verified_closed_ids:
                    continue
                    
                # Skip if position is too old or missing ID
                if not pos.position_id or not pos.symbol:
                    continue
                
                # Fetch closed PnL from Bybit
                try:
                    if hasattr(exchange, 'privateGetV5PositionClosedPnl'):
                        closed_pnl_data = await exchange.privateGetV5PositionClosedPnl({
                            'category': 'linear',
                            'symbol': pos.symbol.replace('/USDT:USDT', '').replace('/', ''),
                            'limit': 5  # Check last 5 closed trades
                        })
                        
                        if closed_pnl_data and 'result' in closed_pnl_data:
                            result_list = closed_pnl_data['result'].get('list', [])
                            
                            # Find matching trade based on close time or just take most recent if close in time
                            matched_data = None
                            pos_close_time_ms = 0
                            
                            if pos.close_time:
                                try:
                                    dt = datetime.fromisoformat(pos.close_time)
                                    pos_close_time_ms = int(dt.timestamp() * 1000)
                                except:
                                    pass
                            
                            for item in result_list:
                                # Simple match: symbol matches and createdTime is close to our close_time
                                item_time = int(item.get('createdTime', 0))
                                # Allow 2 minute tolerance
                                if abs(item_time - pos_close_time_ms) < 120000:  
                                    matched_data = item
                                    break
                            
                            # If no time match but only one recent trade, assume it's that one
                            if not matched_data and len(result_list) == 1:
                                matched_data = result_list[0]
                                
                            if matched_data:
                                real_pnl = float(matched_data.get('closedPnl', 0.0))
                                exit_price = float(matched_data.get('avgExitPrice', 0.0))
                                
                                # Check if correction needed
                                current_pnl = pos.unrealized_pnl_usd
                                diff = abs(real_pnl - current_pnl)
                                
                                # If difference > $0.10, update
                                if diff > 0.10:
                                    updates = {
                                        'unrealized_pnl_usd': real_pnl,
                                        'pnl_usd': real_pnl,  # Alias
                                        'exit_price': exit_price,
                                        'current_price': exit_price,
                                        'close_reason': f"{pos.close_reason or 'MANUAL'} (VERIFIED)"
                                    }
                                    
                                    # Recalculate % based on real PnL and Margin
                                    if pos.position_size > 0:
                                        im = pos.position_size / pos.leverage
                                        new_pnl_pct = (real_pnl / im) * 100
                                        updates['unrealized_pnl_pct'] = new_pnl_pct
                                        updates['pnl_pct'] = new_pnl_pct
                                        
                                    # Atomic update
                                    self.position_manager.atomic_update_position(pos.position_id, updates)
                                    logging.info(colored(f"✅ Synced Real PnL for {pos.symbol}: ${current_pnl:.2f} -> ${real_pnl:.2f}", "green"))
                                
                                self._verified_closed_ids.add(pos.position_id)
                                
                except Exception as e:
                    logging.debug(f"Failed to verify PnL for {pos.symbol}: {e}")
                    
        except Exception as e:
            logging.error(f"Error in verify_closed_positions_pnl: {e}")

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
            
            # CRITICAL FIX: Use REAL initial margin from Bybit if available
            real_im = row.get("real_initial_margin")
            if real_im and real_im > 0:
                initial_margin = real_im
                logging.debug(f"✅ {sym}: Using REAL IM from Bybit: ${initial_margin:.2f}")
            else:
                # Fallback: calculate from position size
                initial_margin = (row["position_usd"] / row["leverage"]) if row["leverage"] else 0.0
                logging.debug(f"⚠️ {sym}: Real IM not available, calculated: ${initial_margin:.2f}")
            
            # WARNING for positions with dangerously low IM
            if initial_margin < 20.0 and initial_margin > 0.0:
                logging.warning(f"⚠️ DANGEROUS: {sym} has only ${initial_margin:.2f} IM - HIGH RISK!")
                
            total_im += initial_margin

            sl_price = bybit_sl_map.get(row["symbol"])
            if sl_price and sl_price > 0:
                # Calculate SL as PRICE percentage
                if side == "long":
                    # LONG: SL è sotto entry, quindi negativo
                    sl_price_pct = ((sl_price - row["entry_price"]) / row["entry_price"]) * 100.0
                else:
                    # SHORT: SL è sopra entry, quindi negativo per noi
                    # Se prezzo sale (SL > entry), perdiamo
                    sl_price_pct = -((sl_price - row["entry_price"]) / row["entry_price"]) * 100.0
                
                # Calculate ROE impact (price% × leverage) - questo è il vero rischio sul margine
                sl_roe = sl_price_pct * row["leverage"]
                delta_usd = (sl_roe / 100.0) * initial_margin
                
                # Display ROE% (impact on margin) with USD value
                sl_txt = f"{sl_roe:+.2f}% ({fmt_money(delta_usd)})"
                sl_col = "red" if delta_usd < 0 else "green"
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
        enhanced_logger.display_table("🔒 CLOSED POSITIONS (SESSION, Individual Trades)", "magenta", attrs=["bold"])
        
        # ✅ FIX: Get individual closed positions from position_manager instead of aggregated data
        closed_positions = []
        if self.position_manager:
            try:
                # Get all closed positions from position_manager (each with unique ID)
                closed_positions = self.position_manager.safe_get_closed_positions()
            except Exception as e:
                logging.debug(f"Could not get closed positions from manager: {e}")
                # Fallback to aggregated data
                closed_positions = []
        
        # Fallback to old aggregated data if no position_manager
        if not closed_positions:
            closed_positions = self._session_closed
        
        if not closed_positions:
            enhanced_logger.display_table("— nessuna posizione chiusa nella sessione corrente —", "yellow")
            return

        # Closed positions table structure with ID, timestamps, and more details
        # Width increased for REASON column (+22 chars)
        enhanced_logger.display_table("┌─────┬────────┬──────────┬──────┬──────┬─────────────┬─────────────┬──────────┬───────────┬──────────┬──────────┬──────────────────────┐", "cyan")
        enhanced_logger.display_table("│  #  │ SYMBOL │    ID    │ SIDE │ LEV  │   ENTRY     │    EXIT     │  PNL %   │   PNL $   │ OPENED   │  CLOSED  │        REASON        │", "white", attrs=["bold"])
        enhanced_logger.display_table("├─────┼────────┼──────────┼──────┼──────┼─────────────┼─────────────┼──────────┼───────────┼──────────┼──────────┼──────────────────────┤", "cyan")

        for i, pos in enumerate(closed_positions, 1):
            # Handle both dict and object formats
            if hasattr(pos, 'symbol'):
                # ThreadSafePosition object
                sym = pos.symbol.replace("/USDT:USDT", "")[:8]
                side = pos.side
                lev = int(pos.leverage) if pos.leverage else 0
                entry_price = pos.entry_price
                exit_price = pos.current_price
                pnl_pct = pos.unrealized_pnl_pct
                pnl_usd = pos.unrealized_pnl_usd
                reason = getattr(pos, 'close_reason', None)
                
                # Fallback: extract from status if reason missing (for old positions)
                if not reason or reason == "N/A":
                    status = getattr(pos, 'status', '')
                    if status and status.startswith("CLOSED_"):
                        reason = status.replace("CLOSED_", "")
                
                # Final check
                if not reason:
                    reason = "N/A"
                
                # Clean up reason
                reason = str(reason).replace("EARLY_EXIT_", "EARLY_")[:20]
                
                # Extract position ID
                pos_id = getattr(pos, 'position_id', '')
                if pos_id and '_' in pos_id:
                    # Extract timestamp from ID (e.g., "BTC_20241016_093445_123456" -> "0934")
                    parts = pos_id.split('_')
                    if len(parts) >= 3:
                        time_part = parts[-2]  # "093445"
                        id_display = time_part[:4]  # "0934" (HH:MM)
                    else:
                        id_display = pos_id[-8:]
                else:
                    id_display = "N/A"
                
                # Extract timestamps
                entry_time = getattr(pos, 'entry_time', '')
                close_time = getattr(pos, 'close_time', '')
                
                if entry_time:
                    try:
                        entry_dt = datetime.fromisoformat(entry_time)
                        opened_str = entry_dt.strftime("%H:%M:%S")
                    except:
                        opened_str = "N/A"
                else:
                    opened_str = "N/A"
                
                if close_time:
                    try:
                        close_dt = datetime.fromisoformat(close_time)
                        closed_str = close_dt.strftime("%H:%M:%S")
                    except:
                        closed_str = "N/A"
                else:
                    closed_str = "N/A"
                
            else:
                # Dict format (fallback)
                sym = pos["symbol"].replace("/USDT:USDT", "")[:8]
                side = pos["side"]
                lev = int(pos.get("leverage") or 0)
                entry_price = pos["entry_price"]
                exit_price = pos["exit_price"]
                pnl_pct = float(pos.get("pnl_pct") or 0.0)
                pnl_usd = float(pos.get("pnl_usd") or 0.0)
                reason = str(pos.get("close_reason") or "N/A")[:20]
                id_display = "N/A"
                opened_str = "N/A"
                closed_str = "N/A"

            # Determine reason color
            reason_col = "white"
            if "STOP" in reason or "LOSS" in reason or "LIQ" in reason:
                reason_col = "red"
            elif "EARLY" in reason:
                reason_col = "yellow"
            elif "TAKE" in reason or "TRAIL" in reason or "WIN" in reason:
                reason_col = "green"

            line = (
                colored(f"│{i:^5}│", "white") +
                colored(f"{sym:^8}", "cyan") + colored("│", "white") +
                colored(f"{id_display:^10}", "yellow") + colored("│", "white") +
                colored(f"{('LONG' if side in ['long', 'buy'] else 'SHORT'):^6}", "green" if side in ['long', 'buy'] else "red") + colored("│", "white") +
                colored(f"{lev:^6}", "yellow") + colored("│", "white") +
                colored(f"${entry_price:.6f}".center(13), "white") + colored("│", "white") +
                colored(f"${exit_price:.6f}".center(13), "cyan") + colored("│", "white") +
                colored(f"{pnl_pct:+.1f}%".center(10), pct_color(pnl_pct)) + colored("│", "white") +
                colored(f"{fmt_money(pnl_usd):>11}", pct_color(pnl_usd)) + colored("│", "white") +
                colored(f"{opened_str:^10}", "white") + colored("│", "white") +
                colored(f"{closed_str:^10}", "white") + colored("│", "white") +
                colored(f"{reason:^22}", reason_col) + colored("│", "white")
            )
            # Use enhanced logging
            logging.info(line)

        # Closed positions table bottom
        enhanced_logger.display_table("└─────┴────────┴──────────┴──────┴──────┴─────────────┴─────────────┴──────────┴───────────┴──────────┴──────────┴──────────────────────┘", "cyan")
        
        # 📊 SESSION SUMMARY for closed positions
        self._render_session_summary_individual(closed_positions)

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
            
            # Get REAL Initial Margin from Bybit
            real_im_val = p.get('initialMargin') or p.get('margin')
            real_initial_margin = safe_float(real_im_val) if real_im_val else None

            # Extracts PnL if available (None if missing to distinguish from 0.0)
            raw_pnl = p.get("unrealizedPnl")
            u_pnl = safe_float(raw_pnl) if raw_pnl is not None else None

            open_rows.append({
                "symbol": symbol,
                "side": side,
                "contracts": contracts,
                "entry_price": entry_price,
                "leverage": leverage,
                "position_usd": position_usd,
                "sl_price": bybit_sl_map.get(symbol),
                "unrealized_pnl_usd": u_pnl,
                "real_initial_margin": real_initial_margin  # ADD: Real IM from Bybit
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
            initial_margin = position_usd / leverage if leverage else 0
            sl_price = snap.get("sl_price")  # Get SL if was set

            # Default values (fallback)
            exit_price = entry
            pnl_pct = 0.0
            pnl_usd = 0.0
            close_reason = "UNKNOWN"
            
            # Attempt to fetch REAL closed PnL from Bybit
            # This ensures accuracy matching Bybit's history
            data_found = False
            try:
                # Only works for Bybit V5 (which we are using)
                if hasattr(exchange, 'privateGetV5PositionClosedPnl') and initial_margin > 0:
                    closed_pnl_data = await exchange.privateGetV5PositionClosedPnl({
                        'category': 'linear',
                        'symbol': sym.replace('/', '').replace(':', ''),
                        'limit': 1
                    })
                    
                    if closed_pnl_data and 'result' in closed_pnl_data:
                        result_list = closed_pnl_data['result'].get('list', [])
                        if result_list:
                            closed_pos = result_list[0]
                            
                            # Get real values
                            pnl_usd_real = float(closed_pos.get('closedPnl', 0.0))
                            exit_price_real = float(closed_pos.get('avgExitPrice', entry))
                            
                            # Update calculation
                            pnl_usd = pnl_usd_real
                            pnl_pct = (pnl_usd / initial_margin * 100.0) if initial_margin > 0 else 0.0
                            exit_price = exit_price_real
                            data_found = True
                            logging.info(f"✅ Display: Fetched REAL PnL for {sym}: ${pnl_usd:.2f} ({pnl_pct:.2f}%)")
            except Exception as e:
                logging.debug(f"Could not fetch real PnL for display {sym}: {e}")
            
            # Fallback if real data not found
            if not data_found and initial_margin > 0:
                try:
                    ticker = await exchange.fetch_ticker(sym)
                    exit_price = safe_float(ticker.get("last"), entry)
                    if side == "long":
                        price_chg_pct = ((exit_price - entry) / entry) * 100.0
                    else:
                        price_chg_pct = ((entry - exit_price) / entry) * 100.0
                    pnl_pct = price_chg_pct * leverage
                    pnl_usd = (pnl_pct / 100.0) * initial_margin
                except Exception as e:
                    logging.debug(f"Ticker fallback failed for {sym}: {e}")
            
            # 🔍 INFER CLOSE REASON from exit price, SL, and trailing status
            # First, check if position had trailing stop active
            had_trailing = False
            if self.position_manager:
                try:
                    open_positions = self.position_manager.safe_get_all_active_positions()
                    for pos in open_positions:
                        if pos.symbol == sym:
                            # Check if trailing was enabled
                            if pos.trailing_data and pos.trailing_data.enabled:
                                had_trailing = True
                                logging.debug(f"🔍 {sym}: Had trailing stop active")
                            break
                except Exception as e:
                    logging.debug(f"Could not check trailing status for {sym}: {e}")
            
            # Determine close reason based on available data
            if sl_price and exit_price > 0:
                price_diff_pct = abs((exit_price - sl_price) / sl_price) * 100.0
                
                # If exit price is within 0.5% of SL, assume SL was hit
                if price_diff_pct < 0.5:
                    close_reason = "STOP_LOSS_HIT"
                    logging.debug(f"🔍 {sym}: Detected STOP_LOSS (exit ${exit_price:.6f} ≈ SL ${sl_price:.6f})")
                # If profitable close with trailing active → TRAILING_STOP
                elif pnl_usd > 1.0 and had_trailing:  # Profitable with trailing
                    close_reason = "TRAILING_STOP_HIT"
                    logging.debug(f"🔍 {sym}: Detected TRAILING_STOP (profit ${pnl_usd:.2f} with trailing active)")
                # If profitable close without trailing → MANUAL or TP
                elif pnl_usd > 1.0:  # Profitable without trailing
                    close_reason = "MANUAL_CLOSE"  # Or could be TP if we had TP set
                    logging.debug(f"🔍 {sym}: Detected MANUAL_CLOSE (profitable exit)")
                # Negative but not at SL
                elif pnl_usd < -1.0:
                    close_reason = "EARLY_EXIT_LOSS"
                    logging.debug(f"🔍 {sym}: Detected EARLY_EXIT_LOSS (cut loss manually)")
                else:
                    close_reason = "BREAKEVEN"
                    logging.debug(f"🔍 {sym}: Detected BREAKEVEN close")
            else:
                # No SL data, infer from PnL and trailing status
                if pnl_usd < -5.0:  # Significant loss
                    close_reason = "STOP_LOSS_HIT"  # Likely SL even if we don't have SL price
                elif pnl_usd > 5.0 and had_trailing:  # Significant profit with trailing
                    close_reason = "TRAILING_STOP_HIT"
                elif pnl_usd > 5.0:  # Significant profit without trailing
                    close_reason = "MANUAL_CLOSE"
                else:
                    close_reason = "MANUAL_CLOSE"
            
            # If position is in position_manager, update it and move to closed
            if self.position_manager:
                try:
                    # Check if position exists in manager
                    open_positions = self.position_manager.safe_get_all_active_positions()
                    matching_pos = None
                    for pos in open_positions:
                        if pos.symbol == sym:
                            matching_pos = pos
                            break
                    
                    if matching_pos:
                        # Close position in manager with inferred reason
                        self.position_manager.close_position(
                            matching_pos.position_id,
                            exit_price,
                            close_reason
                        )
                        logging.info(f"✅ {sym}: Moved to closed positions with reason: {close_reason}")
                except Exception as e:
                    logging.debug(f"Could not update position manager for {sym}: {e}")

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
                "close_reason": close_reason,
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

            # Use Bybit PnL if available (even if 0.0), otherwise calculate
            if row.get("unrealized_pnl_usd") is not None:
                pnl_usd = row["unrealized_pnl_usd"]
                pnl_pct = (pnl_usd / initial_margin * 100.0) if initial_margin else 0.0
                
                # Estimate current price from PnL for display consistency
                # PnL = (Price - Entry) * Contracts -> Price = (PnL / Contracts) + Entry
                if row.get("contracts"):
                    if row["side"] == "long":
                        row["current_price"] = (pnl_usd / row["contracts"]) + row["entry_price"]
                    else:
                        row["current_price"] = row["entry_price"] - (pnl_usd / row["contracts"])
                else:
                     # Fallback to ticker if contracts 0/missing or can't calc
                     row["current_price"] = tickers.get(row["symbol"], row["entry_price"])
            else:
                # Fallback calculation using Last Price
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
    
    def _render_session_summary_individual(self, closed_positions):
        """
        📊 Renders session summary for individual closed positions with total PnL
        
        Args:
            closed_positions: List of closed positions (individual trades, not aggregated)
        """
        if not closed_positions:
            return
        
        try:
            # Calculate session metrics from individual positions
            total_trades = len(closed_positions)
            
            # Handle both object and dict formats
            def get_pnl(pos):
                if hasattr(pos, 'unrealized_pnl_usd'):
                    return pos.unrealized_pnl_usd
                return pos.get('pnl_usd', 0.0)
            
            def get_symbol(pos):
                if hasattr(pos, 'symbol'):
                    return pos.symbol.replace('/USDT:USDT', '')
                return pos.get('symbol', 'UNKNOWN').replace('/USDT:USDT', '')
            
            def get_size(pos):
                if hasattr(pos, 'position_size'):
                    return pos.position_size
                return pos.get('position_size', 0.0)
            
            # Calculate PnL (Gross)
            total_gross_pnl_usd = sum(get_pnl(pos) for pos in closed_positions)
            
            # Calculate Est. Fees (Taker 0.055% * 2 for entry/exit)
            total_fees_usd = sum(get_size(pos) * 0.0011 for pos in closed_positions)
            
            # Calculate Net PnL (Gross - Fees)
            total_net_pnl_usd = total_gross_pnl_usd - total_fees_usd
            
            winning_trades = sum(1 for pos in closed_positions if get_pnl(pos) > 0)
            losing_trades = total_trades - winning_trades
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            # Calculate best and worst trades
            if closed_positions:
                best_trade = max(closed_positions, key=lambda x: get_pnl(x))
                worst_trade = min(closed_positions, key=lambda x: get_pnl(x))
                
                best_pnl = get_pnl(best_trade)
                worst_pnl = get_pnl(worst_trade)
                avg_pnl = total_gross_pnl_usd / total_trades if total_trades > 0 else 0.0
                
                best_symbol = get_symbol(best_trade)[:8]
                worst_symbol = get_symbol(worst_trade)[:8]
            else:
                best_pnl = worst_pnl = avg_pnl = 0.0
                best_symbol = worst_symbol = 'N/A'
            
            # Render session summary using enhanced logging
            enhanced_logger.display_table("")  # Empty line
            enhanced_logger.display_table("📊 SESSION SUMMARY (Individual Trades)", "cyan", attrs=['bold'])
            enhanced_logger.display_table("┌" + "─" * 78 + "┐", "cyan")
            
            # Total PnL line with appropriate coloring
            # P&L: red if negative, green if positive
            pnl_color = pct_color(total_net_pnl_usd)
            
            # WIN RATE: green if good (≥60%), yellow if ok (40-60%), red if bad (<40%)
            if win_rate >= 60:
                wr_color = "green"
            elif win_rate >= 40:
                wr_color = "yellow"
            else:
                wr_color = "red"
            
            # 🆕 Wallet Balance Info
            start_bal = 0.0
            curr_bal = 0.0
            net_chg = 0.0
            net_chg_pct = 0.0
            
            if self.position_manager and hasattr(self.position_manager, 'get_session_summary'):
                summary = self.position_manager.get_session_summary()
                start_bal = summary.get('start_balance', 0.0)
                curr_bal = summary.get('balance', 0.0)
                net_chg = curr_bal - start_bal
                if start_bal > 0:
                    net_chg_pct = (net_chg / start_bal) * 100
            
            # Build colored line with separate colors for P&L and WIN RATE
            # CHANGED: Show NET PnL to match wallet balance better
            pnl_line = (
                colored("│ 💰 TOTAL SESSION P&L (Net): ", "white") +
                colored(f"{fmt_money(total_net_pnl_usd):>8}", pnl_color, attrs=['bold']) +
                colored(f" │ TRADES: {total_trades:>2} │ WIN RATE: ", "white") +
                colored(f"{win_rate:>5.1f}%", wr_color, attrs=['bold']) +
                colored(" │", "white")
            )
            # Use logging.info for proper handling through enhanced logging
            logging.info(pnl_line)
            
            # Add Est. Fees line
            fees_line = (
                colored(f"│ 📉 Est. Fees: -${total_fees_usd:.2f} (approx) ", "yellow") +
                colored(" " * (76 - len(f"📉 Est. Fees: -${total_fees_usd:.2f} (approx) ")) + "│", "white")
            )
            logging.info(fees_line)
            
            # 🆕 Add Balance Line (Always show if manager available)
            if self.position_manager:
                bal_col = "green" if net_chg >= 0 else "red"
                
                # Handle zero start balance gracefully
                if start_bal > 0:
                    pct_txt = f"{net_chg_pct:+.1f}%"
                else:
                    pct_txt = "N/A"
                    
                bal_str = f" SESSION BALANCE:   ${start_bal:.0f} ➜ ${curr_bal:.0f} ({fmt_money(net_chg)} / {pct_txt})"
                
                bal_line = (
                    colored("│ 🏦 SESSION BALANCE:   ", "white") +
                    colored(f"${start_bal:.0f}", "cyan") +
                    colored(" ➜ ", "white") +
                    colored(f"${curr_bal:.0f}", "cyan") +
                    colored(f" ({fmt_money(net_chg)} / {pct_txt})", bal_col)
                )
                
                # Add padding to match width
                padding_len = 78 - len(bal_str)
                if padding_len > 0:
                    bal_line += colored(" " * padding_len + "│", "white")
                else:
                    bal_line += colored("│", "white")
                    
                logging.info(bal_line)
            
            # Performance breakdown
            if total_trades > 0:
                performance_line = f"│ 📈 Winners: {winning_trades:>2} │ 📉 Losers: {losing_trades:>2} │ Avg P&L: {fmt_money(avg_pnl):>8} │"
                enhanced_logger.display_table(performance_line.ljust(79) + "│", "white")
                
                # Best/Worst trades
                highlights_line = f"│ 🥇 Best: {best_symbol} {fmt_money(best_pnl):>8} │ 🥉 Worst: {worst_symbol} {fmt_money(worst_pnl):>8} │"
                enhanced_logger.display_table(highlights_line.ljust(79) + "│", "white")
            
            enhanced_logger.display_table("└" + "─" * 78 + "┘", "cyan")
            
        except Exception as e:
            logging.error(f"Error rendering session summary: {e}")
            import traceback
            logging.error(traceback.format_exc())
            # Fallback simple summary using enhanced logging
            try:
                total_pnl = sum(get_pnl(pos) for pos in closed_positions)
                enhanced_logger.display_table(f"📊 SESSION TOTAL: {len(closed_positions)} trades | P&L: {fmt_money(total_pnl)}", 
                             pct_color(total_pnl), attrs=['bold'])
            except:
                enhanced_logger.display_table(f"📊 SESSION TOTAL: {len(closed_positions)} trades", "white")


# Global instance
global_realtime_display = None

def initialize_global_realtime_display(position_manager=None):
    global global_realtime_display
    global_realtime_display = RealTimePositionDisplay(position_manager)
    return global_realtime_display
