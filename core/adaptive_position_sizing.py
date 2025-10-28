#!/usr/bin/env python3
"""
🎯 ADAPTIVE POSITION SIZING SYSTEM

Sistema adattivo che impara dalle performance reali per simbolo:
- Premia le monete vincenti aumentando la size
- Punisce le monete perdenti bloccandole per 3 cicli
- Si auto-adatta dinamicamente al wallet growth

FILOSOFIA:
"Premia chi ti fa guadagnare, congela chi ti fa perdere, e ricomincia da capo quando sbagli."
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, asdict
from datetime import datetime
from termcolor import colored


@dataclass
class SymbolMemory:
    """Memoria persistente per simbolo"""
    symbol: str
    base_size: float              # Size base (ricalcolata ogni ciclo da wallet)
    current_size: float           # Size attuale (dopo premi/reset)
    blocked_cycles_left: int      # Cicli di blocco rimanenti (0 = sbloccato)
    last_pnl_pct: float          # Ultimo PnL% per audit
    last_cycle_updated: int       # Numero ciclo ultimo update
    total_trades: int             # Totale trade eseguiti
    wins: int                     # Trade vincenti
    losses: int                   # Trade perdenti
    last_updated: str             # Timestamp ultimo update


class AdaptivePositionSizing:
    """
    Sistema adattivo di position sizing
    
    REGOLE OPERATIVE:
    1. Wallet diviso in 5 blocchi
    2. Base size = blocco × 0.5 (primo ciclo prudente)
    3. Win → size aumenta proporzionalmente al gain
    4. Loss → reset + blocco 3 cicli
    5. Cap massimo = slot_value
    """
    
    def __init__(self, config):
        """
        Inizializza adaptive sizing
        
        Args:
            config: Config module con parametri
        """
        self.config = config
        
        # Parametri da config
        self.wallet_blocks = config.ADAPTIVE_WALLET_BLOCKS
        self.first_cycle_factor = config.ADAPTIVE_FIRST_CYCLE_FACTOR
        self.block_cycles = config.ADAPTIVE_BLOCK_CYCLES
        self.cap_multiplier = config.ADAPTIVE_CAP_MULTIPLIER
        self.risk_max_pct = config.ADAPTIVE_RISK_MAX_PCT
        self.loss_multiplier = config.ADAPTIVE_LOSS_MULTIPLIER
        self.fresh_start = config.ADAPTIVE_FRESH_START  # NEW: Flag fresh start
        
        # Memoria simboli
        self.symbol_memory: Dict[str, SymbolMemory] = {}
        
        # Contatore cicli
        self.current_cycle = 0
        
        # File persistenza
        self.memory_file = Path("adaptive_sizing_memory.json")
        
        # Carica memoria esistente (o reset se fresh start)
        self._load_memory()
        
        # Log mode
        mode_msg = "FRESH START MODE" if self.fresh_start else "HISTORICAL MODE"
        mode_color = "yellow" if self.fresh_start else "green"
        
        logging.info(colored(
            f"🎯 Adaptive Position Sizing initialized | "
            f"Mode: {mode_msg} | "
            f"Blocks: {self.wallet_blocks} | "
            f"Block cycles: {self.block_cycles}",
            mode_color, attrs=['bold']
        ))
    
    def _load_memory(self):
        """Carica memoria da file JSON (o reset se fresh start)"""
        try:
            # CHECK: Fresh Start Mode
            if self.fresh_start:
                # Reset complete: cancella memoria e riparti da zero
                self.symbol_memory = {}
                self.current_cycle = 0
                
                # Cancella file se esiste
                if self.memory_file.exists():
                    self.memory_file.unlink()
                    logging.warning(colored(
                        "🔄 FRESH START: Previous memory deleted - Starting from scratch",
                        "yellow", attrs=['bold']
                    ))
                else:
                    logging.info(colored(
                        "🆕 FRESH START: No previous memory - Starting fresh session",
                        "yellow"
                    ))
                
                # Salva memoria vuota
                self._save_memory()
                return
            
            # HISTORICAL MODE: Carica memoria esistente
            if self.memory_file.exists():
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    
                    # Ricostruisci SymbolMemory objects
                    for symbol, mem_dict in data.get('symbols', {}).items():
                        self.symbol_memory[symbol] = SymbolMemory(**mem_dict)
                    
                    # Carica cycle counter
                    self.current_cycle = data.get('current_cycle', 0)
                    
                    # Calcola stats
                    total_trades = sum(m.total_trades for m in self.symbol_memory.values())
                    total_wins = sum(m.wins for m in self.symbol_memory.values())
                    total_losses = sum(m.losses for m in self.symbol_memory.values())
                    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
                    
                    logging.info(colored(
                        f"📂 HISTORICAL MODE: Loaded {len(self.symbol_memory)} symbols | "
                        f"Cycle {self.current_cycle} | "
                        f"Stats: {total_wins}W/{total_losses}L ({win_rate:.1f}% WR)",
                        "green", attrs=['bold']
                    ))
            else:
                logging.info(colored(
                    "🆕 HISTORICAL MODE: No existing memory - starting new history",
                    "yellow"
                ))
                
        except Exception as e:
            logging.error(f"❌ Error loading memory: {e}")
            self.symbol_memory = {}
            self.current_cycle = 0
    
    def _save_memory(self):
        """Salva memoria su file JSON"""
        try:
            data = {
                'current_cycle': self.current_cycle,
                'symbols': {
                    symbol: asdict(memory) 
                    for symbol, memory in self.symbol_memory.items()
                },
                'last_saved': datetime.now().isoformat()
            }
            
            with open(self.memory_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logging.debug(f"💾 Memory saved: {len(self.symbol_memory)} symbols")
            
        except Exception as e:
            logging.error(f"❌ Error saving memory: {e}")
    
    def calculate_slot_value(self, wallet_equity: float) -> float:
        """
        Calcola valore singolo blocco (dinamico)
        
        Args:
            wallet_equity: Equity totale wallet
            
        Returns:
            float: Valore slot (wallet / blocks)
        """
        slot_value = wallet_equity / self.wallet_blocks
        logging.debug(f"💰 Slot value: ${wallet_equity:.2f} / {self.wallet_blocks} = ${slot_value:.2f}")
        return slot_value
    
    def calculate_base_size(self, slot_value: float) -> float:
        """
        Calcola base size (dinamica)
        
        Args:
            slot_value: Valore slot corrente
            
        Returns:
            float: Base size (slot × factor)
        """
        base_size = slot_value * self.first_cycle_factor
        logging.debug(f"📏 Base size: ${slot_value:.2f} × {self.first_cycle_factor} = ${base_size:.2f}")
        return base_size
    
    def get_symbol_size(self, symbol: str, wallet_equity: float) -> Tuple[float, bool, str]:
        """
        Ottieni size per simbolo (con memoria)
        
        Args:
            symbol: Simbolo trading
            wallet_equity: Equity totale wallet
            
        Returns:
            Tuple[float, bool, str]: (size, is_blocked, reason)
        """
        # Calcola dinamiche correnti
        slot_value = self.calculate_slot_value(wallet_equity)
        base_size = self.calculate_base_size(slot_value)
        
        # Controlla memoria simbolo
        if symbol not in self.symbol_memory:
            # Simbolo nuovo → usa base size
            logging.debug(f"🆕 {symbol}: New symbol, using base size ${base_size:.2f}")
            return base_size, False, "new_symbol"
        
        memory = self.symbol_memory[symbol]
        
        # Controlla se bloccato
        if memory.blocked_cycles_left > 0:
            logging.debug(f"🚫 {symbol}: BLOCKED ({memory.blocked_cycles_left} cycles left)")
            return 0.0, True, f"blocked_{memory.blocked_cycles_left}_cycles"
        
        # Aggiorna base_size nella memoria (dinamica)
        memory.base_size = base_size
        
        # Usa current_size con cap
        size = min(memory.current_size, slot_value * self.cap_multiplier)
        
        # Log se cappato
        if memory.current_size > size:
            logging.debug(
                f"⚠️ {symbol}: Size capped ${memory.current_size:.2f} → ${size:.2f} "
                f"(max: ${slot_value * self.cap_multiplier:.2f})"
            )
        
        logging.debug(f"💎 {symbol}: Using memory size ${size:.2f} (W:{memory.wins} L:{memory.losses})")
        return size, False, "from_memory"
    
    def register_opening(self, symbol: str, margin_used: float, wallet_equity: float):
        """
        Registra apertura posizione nella memoria
        
        IMPORTANTE: Chiamare quando posizione viene aperta con successo
        
        Args:
            symbol: Simbolo aperto
            margin_used: Margin effettivamente usato
            wallet_equity: Equity corrente wallet
        """
        try:
            # Calcola dinamiche correnti
            slot_value = self.calculate_slot_value(wallet_equity)
            base_size = self.calculate_base_size(slot_value)
            
            # Se simbolo non in memoria, crealo
            if symbol not in self.symbol_memory:
                memory = SymbolMemory(
                    symbol=symbol,
                    base_size=base_size,
                    current_size=margin_used,  # Usa margin effettivo
                    blocked_cycles_left=0,
                    last_pnl_pct=0.0,
                    last_cycle_updated=self.current_cycle,
                    total_trades=0,
                    wins=0,
                    losses=0,
                    last_updated=datetime.now().isoformat()
                )
                self.symbol_memory[symbol] = memory
                
                logging.debug(colored(
                    f"📝 {symbol}: Registered opening with ${margin_used:.2f}",
                    "cyan"
                ))
            else:
                # Simbolo già in memoria - aggiorna solo timestamp
                memory = self.symbol_memory[symbol]
                memory.last_cycle_updated = self.current_cycle
                memory.last_updated = datetime.now().isoformat()
                
                logging.debug(colored(
                    f"📝 {symbol}: Updated last cycle to {self.current_cycle}",
                    "cyan"
                ))
            
            # Salva memoria
            self._save_memory()
            
        except Exception as e:
            logging.error(f"❌ Error registering opening for {symbol}: {e}")
    
    def update_after_trade(self, symbol: str, pnl_pct: float, wallet_equity: float):
        """
        Aggiorna memoria dopo chiusura trade
        
        Args:
            symbol: Simbolo tradato
            pnl_pct: PnL percentuale del trade
            wallet_equity: Equity corrente wallet
        """
        try:
            # Calcola dinamiche correnti
            slot_value = self.calculate_slot_value(wallet_equity)
            base_size = self.calculate_base_size(slot_value)
            
            # Ottieni/crea memoria
            if symbol not in self.symbol_memory:
                memory = SymbolMemory(
                    symbol=symbol,
                    base_size=base_size,
                    current_size=base_size,
                    blocked_cycles_left=0,
                    last_pnl_pct=0.0,
                    last_cycle_updated=self.current_cycle,
                    total_trades=0,
                    wins=0,
                    losses=0,
                    last_updated=datetime.now().isoformat()
                )
                self.symbol_memory[symbol] = memory
            else:
                memory = self.symbol_memory[symbol]
            
            # Update stats
            memory.total_trades += 1
            memory.last_pnl_pct = pnl_pct
            memory.last_cycle_updated = self.current_cycle
            memory.last_updated = datetime.now().isoformat()
            
            if pnl_pct > 0:
                # ✅ PREMIA: size aumenta proporzionalmente
                memory.wins += 1
                old_size = memory.current_size
                growth_factor = 1 + (pnl_pct / 100.0)
                new_size = old_size * growth_factor
                
                # Applica cap
                cap = slot_value * self.cap_multiplier
                new_size = min(new_size, cap)
                
                memory.current_size = new_size
                
                logging.info(colored(
                    f"✅ {symbol} WIN +{pnl_pct:.1f}% | "
                    f"Size: ${old_size:.2f} → ${new_size:.2f} "
                    f"(+{((new_size/old_size)-1)*100:.1f}%)",
                    "green", attrs=['bold']
                ))
                
            else:
                # ❌ PUNISCI: reset + blocco
                memory.losses += 1
                old_size = memory.current_size
                memory.current_size = base_size  # Reset a base
                memory.blocked_cycles_left = self.block_cycles  # Blocco N cicli
                
                logging.info(colored(
                    f"❌ {symbol} LOSS {pnl_pct:.1f}% | "
                    f"Size: ${old_size:.2f} → ${base_size:.2f} (RESET) | "
                    f"BLOCKED for {self.block_cycles} cycles",
                    "red", attrs=['bold']
                ))
            
            # Salva memoria
            self._save_memory()
            
        except Exception as e:
            logging.error(f"❌ Error updating {symbol}: {e}")
    
    def calculate_adaptive_margins(
        self, 
        signals: List[dict], 
        wallet_equity: float,
        max_positions: int = 5
    ) -> Tuple[List[float], List[str], Dict]:
        """
        Calcola margins adattive per segnali
        
        Args:
            signals: Lista segnali con symbol, confidence, etc
            wallet_equity: Equity totale wallet
            max_positions: Max posizioni contemporanee
            
        Returns:
            Tuple[List[float], List[str], Dict]: (margins, symbols, stats)
        """
        try:
            margins = []
            symbols_to_trade = []
            blocked_symbols = []
            
            # Calcola slot value per logging
            slot_value = self.calculate_slot_value(wallet_equity)
            base_size = self.calculate_base_size(slot_value)
            
            logging.info(colored(
                f"🎯 ADAPTIVE SIZING | Wallet: ${wallet_equity:.2f} | "
                f"Slot: ${slot_value:.2f} | Base: ${base_size:.2f}",
                "cyan", attrs=['bold']
            ))
            
            # Filtra e assegna size ai segnali
            for i, signal in enumerate(signals):
                if len(margins) >= max_positions:
                    break  # Raggiunto limite posizioni
                
                symbol = signal.get('symbol', f'UNKNOWN_{i}')
                
                # Ottieni size per simbolo
                size, is_blocked, reason = self.get_symbol_size(symbol, wallet_equity)
                
                if is_blocked:
                    blocked_symbols.append(symbol)
                    logging.debug(f"⏭️ Skipping {symbol}: {reason}")
                    continue
                
                margins.append(size)
                symbols_to_trade.append(symbol)
                
                # Log dettagliato
                symbol_short = symbol.replace('/USDT:USDT', '')
                confidence = signal.get('confidence', 0)
                logging.info(
                    f"  #{len(margins)} {symbol_short}: ${size:.2f} | "
                    f"Conf: {confidence:.0%} | Reason: {reason}"
                )
            
            # Validazione rischio totale
            total_margin = sum(margins)
            max_loss = total_margin * self.loss_multiplier
            risk_limit = wallet_equity * self.risk_max_pct
            
            logging.info(colored(
                f"🛡️ RISK CHECK | Total margin: ${total_margin:.2f} | "
                f"Max loss: ${max_loss:.2f} | Limit: ${risk_limit:.2f}",
                "yellow"
            ))
            
            # Se supera limite, scala proporzionalmente
            if max_loss > risk_limit:
                scale_factor = risk_limit / max_loss
                margins = [m * scale_factor for m in margins]
                total_margin = sum(margins)
                max_loss = total_margin * self.loss_multiplier
                
                logging.warning(colored(
                    f"⚠️ RISK SCALED | Scale: {scale_factor:.2%} | "
                    f"New total: ${total_margin:.2f} | Max loss: ${max_loss:.2f}",
                    "yellow", attrs=['bold']
                ))
            else:
                logging.info(colored(f"✅ Risk within limits", "green"))
            
            # Stats summary
            stats = {
                'total_signals': len(signals),
                'positions_opened': len(margins),
                'symbols_blocked': len(blocked_symbols),
                'total_margin': total_margin,
                'max_loss': max_loss,
                'risk_pct': (max_loss / wallet_equity * 100) if wallet_equity > 0 else 0,
                'slot_value': slot_value,
                'base_size': base_size,
                'blocked_list': blocked_symbols
            }
            
            logging.info(colored(
                f"📊 SUMMARY | Opened: {len(margins)}/{max_positions} | "
                f"Blocked: {len(blocked_symbols)} | "
                f"Total: ${total_margin:.2f} ({stats['risk_pct']:.1f}% risk)",
                "cyan"
            ))
            
            return margins, symbols_to_trade, stats
            
        except Exception as e:
            logging.error(f"❌ Error calculating adaptive margins: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return [], [], {}
    
    def increment_cycle(self):
        """
        Incrementa contatore ciclo e decrementa blocchi
        
        Chiamare all'inizio di ogni ciclo trading
        """
        self.current_cycle += 1
        
        # Decrementa blocchi
        unblocked = []
        for symbol, memory in self.symbol_memory.items():
            if memory.blocked_cycles_left > 0:
                memory.blocked_cycles_left -= 1
                
                if memory.blocked_cycles_left == 0:
                    unblocked.append(symbol)
                    logging.info(colored(
                        f"🔓 {symbol} UNBLOCKED | Returning with base size",
                        "green"
                    ))
        
        if unblocked:
            self._save_memory()
        
        logging.info(colored(
            f"🔄 Cycle {self.current_cycle} | "
            f"Active symbols: {len(self.symbol_memory)} | "
            f"Unblocked: {len(unblocked)}",
            "cyan"
        ))
        
        # Print detailed evolution report
        self.print_evolution_report()
    
    def print_evolution_report(self):
        """Stampa report dettagliato evoluzione simboli nel terminale"""
        try:
            if not self.symbol_memory:
                logging.info(colored("📊 No symbols in memory yet", "yellow"))
                return
            
            # Header
            logging.info("=" * 100)
            logging.info(colored(f"📊 ADAPTIVE SIZING EVOLUTION REPORT - CYCLE #{self.current_cycle}", "cyan", attrs=['bold']))
            logging.info("=" * 100)
            
            # Sort symbols by status (active first, then by current_size descending)
            sorted_symbols = sorted(
                self.symbol_memory.items(),
                key=lambda x: (x[1].blocked_cycles_left > 0, -x[1].current_size)
            )
            
            # Active symbols
            active_symbols = [(s, m) for s, m in sorted_symbols if m.blocked_cycles_left == 0]
            blocked_symbols = [(s, m) for s, m in sorted_symbols if m.blocked_cycles_left > 0]
            
            # Active symbols section
            if active_symbols:
                logging.info(colored(f"\n✅ ACTIVE SYMBOLS ({len(active_symbols)}):", "green", attrs=['bold']))
                logging.info("-" * 100)
                
                for symbol, memory in active_symbols:
                    symbol_short = symbol.replace('/USDT:USDT', '')
                    
                    # Calculate size evolution
                    size_change_pct = ((memory.current_size - memory.base_size) / memory.base_size * 100) if memory.base_size > 0 else 0
                    
                    # Determine status icon
                    if size_change_pct > 5:
                        status_icon = "📈 GROWING"
                        color = "green"
                    elif size_change_pct < -5:
                        status_icon = "📉 SHRINKING"
                        color = "yellow"
                    else:
                        status_icon = "📊 STABLE"
                        color = "white"
                    
                    # Win rate
                    win_rate = (memory.wins / memory.total_trades * 100) if memory.total_trades > 0 else 0
                    
                    # Build info line
                    info = (
                        f"  {symbol_short:8s} | "
                        f"{status_icon:12s} | "
                        f"Size: ${memory.current_size:6.2f} ({size_change_pct:+5.1f}%) | "
                        f"Base: ${memory.base_size:6.2f} | "
                        f"Record: {memory.wins}W-{memory.losses}L ({win_rate:4.0f}%) | "
                        f"Last: {memory.last_pnl_pct:+6.1f}%"
                    )
                    
                    logging.info(colored(info, color))
            
            # Blocked symbols section
            if blocked_symbols:
                logging.info(colored(f"\n🚫 BLOCKED SYMBOLS ({len(blocked_symbols)}):", "red", attrs=['bold']))
                logging.info("-" * 100)
                
                for symbol, memory in blocked_symbols:
                    symbol_short = symbol.replace('/USDT:USDT', '')
                    
                    # Win rate
                    win_rate = (memory.wins / memory.total_trades * 100) if memory.total_trades > 0 else 0
                    
                    # Build info line
                    info = (
                        f"  {symbol_short:8s} | "
                        f"🔒 BLOCKED {memory.blocked_cycles_left} cycles left | "
                        f"Will return with: ${memory.base_size:6.2f} | "
                        f"Record: {memory.wins}W-{memory.losses}L ({win_rate:4.0f}%) | "
                        f"Last: {memory.last_pnl_pct:+6.1f}% (LOSS)"
                    )
                    
                    logging.info(colored(info, "red"))
            
            # Summary statistics
            total_trades = sum(m.total_trades for m in self.symbol_memory.values())
            total_wins = sum(m.wins for m in self.symbol_memory.values())
            total_losses = sum(m.losses for m in self.symbol_memory.values())
            overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
            
            logging.info("")
            logging.info("-" * 100)
            logging.info(colored(
                f"📈 OVERALL: {total_wins}W / {total_losses}L | "
                f"Win Rate: {overall_win_rate:.1f}% | "
                f"Total Trades: {total_trades} | "
                f"Active: {len(active_symbols)} | Blocked: {len(blocked_symbols)}",
                "cyan", attrs=['bold']
            ))
            logging.info("=" * 100)
            
        except Exception as e:
            logging.error(f"Error printing evolution report: {e}")
    
    def get_memory_stats(self) -> Dict:
        """Ottieni statistiche memoria per audit"""
        try:
            total_symbols = len(self.symbol_memory)
            active_symbols = sum(1 for m in self.symbol_memory.values() if m.blocked_cycles_left == 0)
            blocked_symbols = total_symbols - active_symbols
            
            total_trades = sum(m.total_trades for m in self.symbol_memory.values())
            total_wins = sum(m.wins for m in self.symbol_memory.values())
            total_losses = sum(m.losses for m in self.symbol_memory.values())
            
            win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
            
            return {
                'cycle': self.current_cycle,
                'total_symbols': total_symbols,
                'active_symbols': active_symbols,
                'blocked_symbols': blocked_symbols,
                'total_trades': total_trades,
                'wins': total_wins,
                'losses': total_losses,
                'win_rate': win_rate
            }
        except Exception as e:
            logging.error(f"Error getting memory stats: {e}")
            return {}


# Global instance (sarà inizializzato da trading engine)
global_adaptive_sizing: Optional[AdaptivePositionSizing] = None


def initialize_adaptive_sizing(config):
    """Inizializza global adaptive sizing instance"""
    global global_adaptive_sizing
    global_adaptive_sizing = AdaptivePositionSizing(config)
    return global_adaptive_sizing
