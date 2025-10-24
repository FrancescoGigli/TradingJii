#!/usr/bin/env python3
"""
🚫 SYMBOL EXCLUSION MANAGER

SINGLE RESPONSIBILITY: Gestione automatica esclusione simboli
- Auto-exclude simboli con dati insufficienti
- Persiste la lista su file
- Evita re-processing di simboli problematici
- Report di simboli esclusi

GARANTISCE: Solo simboli con dati sufficienti vengono analizzati
"""

import logging
import os
from typing import Set, List
from datetime import datetime
from pathlib import Path

import config

class SymbolExclusionManager:
    """
    Gestisce automaticamente l'esclusione dei simboli con dati insufficienti
    
    PHILOSOPHY: 
    - Auto-escludi simboli che non hanno abbastanza dati storici
    - Persiste su file per evitare re-processing
    - Logging dettagliato per debugging
    - Reset periodico per ri-testare simboli
    """
    
    def __init__(self):
        self.excluded_file_path = Path(config.EXCLUDED_SYMBOLS_FILE)
        self.auto_excluded_symbols: Set[str] = set()
        self.manual_excluded_symbols: Set[str] = set(config.EXCLUDED_SYMBOLS)
        self.session_excluded: Set[str] = set()  # Esclusi in questa sessione
        
        self._load_excluded_symbols()
        
        # 📋 Mostra simboli esclusi con i nomi
        if self.auto_excluded_symbols:
            excluded_names = [sym.replace('/USDT:USDT', '') for sym in sorted(self.auto_excluded_symbols)]
            logging.debug(f"🚫 SymbolExclusionManager: {len(self.auto_excluded_symbols)} auto-excluded symbols loaded: {', '.join(excluded_names)}")
        else:
            logging.debug(f"🚫 SymbolExclusionManager: 0 auto-excluded symbols loaded")
    
    def _load_excluded_symbols(self):
        """Carica simboli esclusi dal file"""
        try:
            if self.excluded_file_path.exists():
                with open(self.excluded_file_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            symbol, reason = line.split('|', 1) if '|' in line else (line, 'Unknown')
                            self.auto_excluded_symbols.add(symbol)
                            
                logging.debug(f"📋 Loaded {len(self.auto_excluded_symbols)} excluded symbols from {self.excluded_file_path}")
            else:
                logging.debug(f"📋 No exclusion file found, starting fresh")
                
        except Exception as e:
            logging.error(f"Error loading excluded symbols: {e}")
    
    def _save_excluded_symbols(self):
        """Salva simboli esclusi su file"""
        try:
            with open(self.excluded_file_path, 'w') as f:
                f.write(f"# Auto-excluded symbols - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Format: SYMBOL|REASON\n\n")
                
                for symbol in sorted(self.auto_excluded_symbols):
                    f.write(f"{symbol}|insufficient_data\n")
            
            logging.debug(f"💾 Saved {len(self.auto_excluded_symbols)} excluded symbols")
            
        except Exception as e:
            logging.error(f"Error saving excluded symbols: {e}")
    
    def is_excluded(self, symbol: str) -> bool:
        """
        Controlla se un simbolo è escluso (manualmente o automaticamente)
        
        Args:
            symbol: Trading symbol da controllare
            
        Returns:
            bool: True se escluso
        """
        return (symbol in self.auto_excluded_symbols or 
                symbol in self.manual_excluded_symbols)
    
    def exclude_symbol_insufficient_data(self, symbol: str, missing_timeframes: List[str] = None,
                                       candle_count: int = 0):
        """
        Esclude automaticamente un simbolo per dati insufficienti
        
        Args:
            symbol: Trading symbol da escludere
            missing_timeframes: Lista di timeframes mancanti
            candle_count: Numero di candele trovate (se < MIN_REQUIRED_CANDLES)
        """
        if symbol not in self.auto_excluded_symbols:
            self.auto_excluded_symbols.add(symbol)
            self.session_excluded.add(symbol)
            
            # Dettagli per logging
            reason_details = []
            if missing_timeframes:
                reason_details.append(f"missing {len(missing_timeframes)} timeframes: {', '.join(missing_timeframes)}")
            if candle_count > 0:
                reason_details.append(f"only {candle_count} candles (< {config.MIN_REQUIRED_CANDLES} required)")
            
            reason = "; ".join(reason_details) if reason_details else "insufficient historical data"
            
            logging.warning(f"🚫 AUTO-EXCLUDED: {symbol} - {reason}")
            
            # Salva immediatamente
            self._save_excluded_symbols()
    
    def get_all_excluded(self) -> Set[str]:
        """Restituisce tutti i simboli esclusi (manuali + automatici)"""
        return self.auto_excluded_symbols.union(self.manual_excluded_symbols)
    
    def get_session_excluded_count(self) -> int:
        """Restituisce il numero di simboli esclusi in questa sessione"""
        return len(self.session_excluded)
    
    def filter_symbols(self, symbols: List[str]) -> List[str]:
        """
        Filtra una lista di simboli rimuovendo quelli esclusi
        
        Args:
            symbols: Lista di simboli da filtrare
            
        Returns:
            List[str]: Simboli non esclusi
        """
        excluded = self.get_all_excluded()
        filtered = [sym for sym in symbols if sym not in excluded]
        
        if len(filtered) < len(symbols):
            excluded_count = len(symbols) - len(filtered)
            logging.info(f"🚫 Filtered out {excluded_count} excluded symbols ({len(filtered)} remaining)")
        
        return filtered
    
    def reset_auto_excluded(self):
        """
        Reset dei simboli auto-esclusi (per ri-testare periodicamente)
        
        Utile per ri-testare simboli che potrebbero aver accumulato più dati storici
        """
        if self.auto_excluded_symbols:
            count = len(self.auto_excluded_symbols)
            self.auto_excluded_symbols.clear()
            self.session_excluded.clear()
            
            # Rimuovi file
            if self.excluded_file_path.exists():
                os.remove(self.excluded_file_path)
            
            logging.info(f"🔄 RESET: Cleared {count} auto-excluded symbols for re-testing")
        else:
            logging.info("🔄 No auto-excluded symbols to reset")
    
    def get_exclusion_summary(self) -> dict:
        """Restituisce summary delle esclusioni"""
        return {
            'auto_excluded_count': len(self.auto_excluded_symbols),
            'manual_excluded_count': len(self.manual_excluded_symbols), 
            'session_excluded_count': len(self.session_excluded),
            'total_excluded_count': len(self.get_all_excluded()),
            'auto_excluded_symbols': sorted(list(self.auto_excluded_symbols)),
            'session_excluded_symbols': sorted(list(self.session_excluded))
        }
    
    def print_exclusion_report(self):
        """Stampa un report delle esclusioni"""
        summary = self.get_exclusion_summary()
        
        if summary['total_excluded_count'] > 0:
            logging.info("🚫 SYMBOL EXCLUSION REPORT:")
            logging.info(f"   📊 Total excluded: {summary['total_excluded_count']}")
            logging.info(f"   🤖 Auto-excluded: {summary['auto_excluded_count']}")
            logging.info(f"   👤 Manual-excluded: {summary['manual_excluded_count']}")
            
            if summary['session_excluded_count'] > 0:
                logging.info(f"   🆕 New this session: {summary['session_excluded_count']}")
                for symbol in summary['session_excluded_symbols']:
                    logging.info(f"      - {symbol}")
        else:
            logging.info("✅ No symbols currently excluded")


# Global symbol exclusion manager instance  
global_symbol_exclusion_manager = SymbolExclusionManager()
