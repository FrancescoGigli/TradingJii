#!/usr/bin/env python3
"""
🎯 TRAILING STOP MANAGER

SINGLE RESPONSIBILITY: Gestione trailing stops dinamici
- Stop catastrofico su exchange (backup ampio)
- Trailing stop interno gestito dal bot
- Attivazione condizionale sopra breakeven
- Monotonia: lo stop non arretra mai
- Nessun Take Profit su exchange

GARANTISCE: Risk management sofisticato senza conflitti API
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from config import (
    LEVERAGE,
    INITIAL_SL_PRICE_PCT,
    TRAILING_DISTANCE_LOW_VOL,
    TRAILING_DISTANCE_MED_VOL,
    TRAILING_DISTANCE_HIGH_VOL,
    VOLATILITY_LOW_THRESHOLD,
    VOLATILITY_HIGH_THRESHOLD,
)


class PositionState(Enum):
    """Stati delle posizioni per trailing stop"""
    FIXED_SL = "fixed_sl"       # Stop loss fisso al 6% (catastrofico) attivo
    MONITORING = "monitoring"   # Monitoraggio per trigger trailing
    TRAILING = "trailing"       # Trailing stop attivo


@dataclass
class TrailingData:
    """Dati trailing per ogni posizione (serializzabile)"""
    entry_price: float                          # Prezzo di entrata
    side: str                                   # 'buy' / 'sell'
    trailing_trigger_price: Optional[float] = None  # Prezzo trigger trailing
    trailing_attivo: bool = False               # Stato trailing attivo
    best_price: Optional[float] = None          # Miglior prezzo favorevole
    sl_corrente: Optional[float] = None         # Stop interno gestito dal bot
    fixed_sl_price: Optional[float] = None      # Stop loss fisso (catastrofico)
    state: PositionState = PositionState.FIXED_SL
    last_update: Optional[datetime] = None      # Ultimo aggiornamento

    # --- Serializzazione sicura (Enum -> stringa, datetime -> iso) ---
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_price": self.entry_price,
            "side": self.side,
            "trailing_trigger_price": self.trailing_trigger_price,
            "trailing_attivo": self.trailing_attivo,
            "best_price": self.best_price,
            "sl_corrente": self.sl_corrente,
            "fixed_sl_price": self.fixed_sl_price,
            "state": self.state.value,
            "last_update": self.last_update.isoformat() if self.last_update else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrailingData":
        # Ricostruisci lo stato Enum e il datetime
        state_str = data.get("state", PositionState.FIXED_SL.value)
        state = PositionState(state_str) if isinstance(state_str, str) else state_str

        last_update = data.get("last_update")
        if isinstance(last_update, str):
            try:
                last_update = datetime.fromisoformat(last_update)
            except ValueError:
                last_update = None

        return cls(
            entry_price=float(data["entry_price"]),
            side=str(data["side"]).lower(),
            trailing_trigger_price=data.get("trailing_trigger_price"),
            trailing_attivo=bool(data.get("trailing_attivo", False)),
            best_price=data.get("best_price"),
            sl_corrente=data.get("sl_corrente"),
            fixed_sl_price=data.get("fixed_sl_price"),
            state=state,
            last_update=last_update,
        )


class TrailingStopManager:
    """
    Gestione avanzata trailing stops

    PHILOSOPHY:
    - Exchange API solo per stop catastrofico
    - Trailing logic completamente interna
    - Attivazione condizionale sopra breakeven
    - Monotonia: stop mai arretrati
    """

    def __init__(
        self,
        order_manager,
        position_manager,
        *,
        commission_rate: float = 0.0006,        # 0.06% commissioni totali (entry+exit)
        buffer_extra_profit_pct: float = 0.002, # +0.2% sopra distanza trailing per garantire profitto minimo
        min_trail_distance_pct: float = 0.01,   # Non usato con le distanze ATR, ma disponibile per override
        max_trail_distance_pct: float = 0.05,   # Non usato con le distanze ATR, ma disponibile per override
    ):
        self.order_manager = order_manager
        self.position_manager = position_manager

        # Parametri interni (overrideabili)
        self.commission_rate = commission_rate
        self.buffer_extra_profit_pct = buffer_extra_profit_pct
        self.min_trail_distance_pct = min_trail_distance_pct
        self.max_trail_distance_pct = max_trail_distance_pct

    # ---------------------------- CALCOLI BASE ----------------------------

    @staticmethod
    def _normalize_side(side: str) -> str:
        s = (side or "").lower()
        if s not in ("buy", "sell"):
            raise ValueError(f"Invalid side '{side}', expected 'buy' or 'sell'")
        return s

    def calculate_liquidation_price(self, entry_price: float, side: str) -> float:
        """
        Stima prezzo di liquidazione (approssimata) per leva 10x.
        Nota: Bybit calcola il liq price in base a margin mode, fees, ecc.
        Usare l'API ufficiale per valore esatto quando possibile.
        """
        try:
            s = self._normalize_side(side)
            liquidation_pct = 0.095  # ~9.5% per leva 10x (stima)
            if s == "buy":
                liquidation = entry_price * (1 - liquidation_pct)
            else:
                liquidation = entry_price * (1 + liquidation_pct)
            logging.debug(
                f"💀 Liquidation calc: Entry {entry_price:.6f} | Liq {liquidation:.6f} "
                f"({liquidation_pct*100:.1f}%)"
            )
            return float(liquidation)
        except Exception as e:
            logging.error(f"Error calculating liquidation price: {e}")
            # Fallback coerente con SL iniziale ±6%
            return float(entry_price * (0.94 if str(side).lower() == "buy" else 1.06))

    def calculate_breakeven_price(self, entry_price: float, side: str) -> float:
        """
        Prezzo di pareggio = entry ± commissioni.
        """
        try:
            s = self._normalize_side(side)
            commission_cost = entry_price * self.commission_rate
            if s == "buy":
                return float(entry_price + commission_cost)
            return float(entry_price - commission_cost)
        except Exception as e:
            logging.error(f"Error calculating breakeven: {e}")
            return float(entry_price)

    def _trailing_distance_pct_from_atr(self, atr_pct: float) -> float:
        """
        Mappa ATR% -> distanza trailing percentuale.
        Coerenza con config:
          - Bassa volatilità  => 1.0%  (TRAILING_DISTANCE_LOW_VOL)
          - Media volatilità  => 0.8%  (TRAILING_DISTANCE_MED_VOL)
          - Alta volatilità   => 0.7%  (TRAILING_DISTANCE_HIGH_VOL)
        """
        if atr_pct < VOLATILITY_LOW_THRESHOLD:
            return float(TRAILING_DISTANCE_LOW_VOL)
        if atr_pct > VOLATILITY_HIGH_THRESHOLD:
            return float(TRAILING_DISTANCE_HIGH_VOL)
        return float(TRAILING_DISTANCE_MED_VOL)

    def calculate_dynamic_trigger(self, entry_price: float, side: str, atr: float) -> float:
        """
        Trigger dinamico basato su: breakeven + (distanza_trailing + extra buffer).
        L'idea è garantire un minimo profitto prima di attivare il trailing.
        """
        try:
            s = self._normalize_side(side)
            breakeven = self.calculate_breakeven_price(entry_price, s)

            atr_pct = (atr / entry_price) if entry_price > 0 else 0.0
            base_trail_pct = self._trailing_distance_pct_from_atr(atr_pct)

            # Buffer extra per garantire profitto minimo oltre la distanza di trailing
            buffer_pct = base_trail_pct + self.buffer_extra_profit_pct

            if s == "buy":
                trigger_price = breakeven * (1 + buffer_pct)
            else:
                trigger_price = breakeven * (1 - buffer_pct)

            logging.debug(
                "🎯 Breakeven-based trigger: Breakeven=%.6f, Trail=%.3f%%, Buffer=%.3f%%, "
                "Leverage=%dx → Trigger=%.6f",
                breakeven,
                base_trail_pct * 100,
                self.buffer_extra_profit_pct * 100,
                LEVERAGE,
                trigger_price,
            )
            return float(trigger_price)
        except Exception as e:
            logging.error(f"Error calculating dynamic trigger: {e}")
            breakeven = self.calculate_breakeven_price(entry_price, side)
            fallback_pct = 0.008  # 0.8% sopra/sotto breakeven
            return float(breakeven * (1 + fallback_pct if str(side).lower() == "buy" else 1 - fallback_pct))

    # ------------------------ INIZIALIZZAZIONE DATI ------------------------

    def initialize_trailing_data(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        atr: float,
    ) -> TrailingData:
        """
        Inizializza dati trailing per una nuova posizione.
        - Calcola SL catastrofico (±6% da entry)
        - Calcola trigger dinamico
        - Stato iniziale: FIXED_SL
        """
        try:
            s = self._normalize_side(side)

            # Stop loss fisso catastrofico ±6%
            if s == "buy":
                fixed_sl = entry_price * (1 - INITIAL_SL_PRICE_PCT)
            else:
                fixed_sl = entry_price * (1 + INITIAL_SL_PRICE_PCT)

            trigger_price = self.calculate_dynamic_trigger(entry_price, s, atr)

            td = TrailingData(
                entry_price=float(entry_price),
                side=s,
                trailing_trigger_price=float(trigger_price),
                trailing_attivo=False,
                best_price=None,
                sl_corrente=None,
                fixed_sl_price=float(fixed_sl),
                state=PositionState.FIXED_SL,
                last_update=datetime.now(),
            )
            logging.debug(
                "🔧 TRAILING INIT: %s %s | Entry=%.6f | Fixed SL=%.6f | Trigger=%.6f",
                symbol,
                s.upper(),
                entry_price,
                fixed_sl,
                trigger_price,
            )
            return td
        except Exception as e:
            logging.error(f"Error initializing trailing data: {e}")
            return TrailingData(
                entry_price=float(entry_price),
                side=str(side).lower(),
                state=PositionState.FIXED_SL,
                last_update=datetime.now(),
            )

    # ------------------------- ATTIVAZIONE TRAILING -------------------------

    def check_activation_conditions(self, trailing_data: TrailingData, current_price: float) -> bool:
        """
        Controlla se si è raggiunto il trigger dinamico (sopra/sotto breakeven).
        Se sì, porta lo stato a MONITORING (il chiamante potrà poi attivare il trailing).
        """
        try:
            if trailing_data.trailing_trigger_price is None:
                logging.warning("Trailing trigger price not set")
                return False

            s = self._normalize_side(trailing_data.side)
            cp = float(current_price)
            trig = float(trailing_data.trailing_trigger_price)

            trigger_reached = (cp >= trig) if s == "buy" else (cp <= trig)

            if trigger_reached:
                if trailing_data.state == PositionState.FIXED_SL:
                    trailing_data.state = PositionState.MONITORING

                profit_pct = abs(cp - trailing_data.entry_price) / trailing_data.entry_price * 100.0
                logging.info(
                    "🎯 TRIGGER REACHED: Price=%.6f, Profit=%.1f%%, State=%s",
                    cp,
                    profit_pct,
                    trailing_data.state.value,
                )
                return True

            return False
        except Exception as e:
            logging.error(f"Error checking activation conditions: {e}")
            return False

    def activate_trailing(self, trailing_data: TrailingData, current_price: float, side: str, atr: float) -> None:
        """
        Attiva il trailing stop (porta lo stato a TRAILING e imposta il primo SL interno).
        """
        try:
            s = self._normalize_side(side)
            cp = float(current_price)

            trailing_data.trailing_attivo = True
            trailing_data.best_price = cp
            trailing_data.state = PositionState.TRAILING

            # Calcola prima distanza e SL
            trail_distance = self.calculate_trailing_distance(cp, atr)
            if s == "buy":
                trailing_data.sl_corrente = cp - trail_distance
            else:
                trailing_data.sl_corrente = cp + trail_distance

            trailing_data.last_update = datetime.now()

            logging.info(
                "🎯 TRAILING ACTIVATED: Best=%.6f | SL=%.6f | State=%s",
                cp,
                trailing_data.sl_corrente,
                trailing_data.state.value,
            )
        except Exception as e:
            logging.error(f"Error activating trailing: {e}")

    # ---------------------- DISTANZA TRAILING DINAMICA ----------------------

    def calculate_trailing_distance(self, price: float, atr: float) -> float:
        """
        Distanza trailing dinamica in funzione della volatilità (ATR%).
        - Bassa vol:  ~1.0% del prezzo
        - Media vol:  ~0.8% del prezzo
        - Alta vol:   ~0.7% del prezzo
        """
        try:
            if price <= 0:
                return 0.0

            atr_pct = (atr / price) if price > 0 else 0.0
            distance_pct = self._trailing_distance_pct_from_atr(atr_pct)
            distance = float(price * distance_pct)

            logging.debug(
                "📏 Trailing distance: ATR%%=%.2f%%, Distance=%.2f%%, Value=%.6f",
                atr_pct * 100.0,
                distance_pct * 100.0,
                distance,
            )
            return distance
        except Exception as e:
            logging.error(f"Error calculating trailing distance: {e}")
            return float(price * TRAILING_DISTANCE_MED_VOL)  # fallback ~0.8%

    # ---------------------- AGGIORNAMENTO MONOTONO ----------------------

    def update_trailing(self, trailing_data: TrailingData, current_price: float, side: str, atr: float) -> None:
        """
        Aggiorna trailing stop attivo (monotono): lo SL si muove solo a favore.
        """
        try:
            if not trailing_data.trailing_attivo or trailing_data.best_price is None:
                return

            s = self._normalize_side(side)
            cp = float(current_price)

            # Aggiorna best price in modo monotono
            if s == "buy":
                new_best = max(trailing_data.best_price, cp)
            else:
                new_best = min(trailing_data.best_price, cp)

            if new_best != trailing_data.best_price:
                trailing_data.best_price = new_best

                trail_distance = self.calculate_trailing_distance(new_best, atr)
                if s == "buy":
                    new_sl = new_best - trail_distance
                    trailing_data.sl_corrente = max(trailing_data.sl_corrente or new_sl, new_sl)
                else:
                    new_sl = new_best + trail_distance
                    trailing_data.sl_corrente = min(trailing_data.sl_corrente or new_sl, new_sl)

                logging.debug("🔄 TRAILING UPDATE: Best=%.6f | SL=%.6f", new_best, trailing_data.sl_corrente)

            trailing_data.last_update = datetime.now()
        except Exception as e:
            logging.error(f"Error updating trailing: {e}")

    # --------------------------- HIT & EXIT ---------------------------

    def is_trailing_hit(self, trailing_data: TrailingData, current_price: float, side: str) -> bool:
        """
        True se il prezzo ha colpito lo stop interno corrente.
        """
        try:
            if not trailing_data.trailing_attivo or trailing_data.sl_corrente is None:
                return False

            s = self._normalize_side(side)
            cp = float(current_price)
            sl = float(trailing_data.sl_corrente)

            hit = (cp <= sl) if s == "buy" else (cp >= sl)
            if hit:
                logging.info("🎯 TRAILING HIT: Price=%.6f vs SL=%.6f", cp, sl)
            return hit
        except Exception as e:
            logging.error(f"Error checking trailing hit: {e}")
            return False

    async def execute_trailing_exit(
        self,
        exchange,
        symbol: str,
        side: str,
        position_size: float,
        current_price: float,
    ) -> bool:
        """
        Esegue uscita a mercato quando il trailing è colpito.
        """
        try:
            s = self._normalize_side(side)
            exit_side = "sell" if s == "buy" else "buy"

            logging.info("🎯 EXECUTING TRAILING EXIT: %s %s %s", symbol, exit_side.upper(), position_size)

            result = await self.order_manager.place_market_order(
                exchange, symbol, exit_side, position_size
            )

            if getattr(result, "success", False):
                logging.info("✅ Trailing exit successful: %s", getattr(result, "order_id", "N/A"))
                return True

            logging.error("❌ Trailing exit failed: %s", getattr(result, "error", "unknown error"))
            return False

        except Exception as e:
            logging.error(f"Error executing trailing exit: {e}")
            return False

    # --------------------------- SUMMARY ---------------------------

    def get_trailing_summary(self, trailing_data: TrailingData, symbol: str, side: str) -> Dict[str, Any]:
        """
        Riepilogo dello stato di trailing corrente.
        """
        try:
            return {
                "symbol": symbol,
                "side": self._normalize_side(side),
                "state": trailing_data.state.value,
                "entry_price": trailing_data.entry_price,
                "fixed_sl_price": trailing_data.fixed_sl_price,
                "trailing_trigger_price": trailing_data.trailing_trigger_price,
                "trailing_active": trailing_data.trailing_attivo,
                "best_price": trailing_data.best_price,
                "sl_corrente": trailing_data.sl_corrente,
                "last_update": trailing_data.last_update.isoformat() if trailing_data.last_update else None,
            }
        except Exception as e:
            logging.error(f"Error getting trailing summary: {e}")
            return {"error": str(e)}


# Istanza globale (inizializzata dal wiring dell'app)
global_trailing_manager = None
