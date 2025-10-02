#!/usr/bin/env python3
"""
🧹 FRESH START MANAGER

Gestisce fresh start mode: chiusura posizioni esistenti + cleanup file
per garantire riavvio pulito del bot con codice aggiornato.

FEATURES:
- Chiusura market di tutte le posizioni Bybit
- Cleanup selettivo file (positions, learning, RL model, etc)
- Log dettagliato operazioni
- Error handling robusto
- Backup automatico prima di cancellare

USAGE:
    from core.fresh_start_manager import execute_fresh_start
    await execute_fresh_start(exchange, config_options)
"""

import os
import json
import shutil
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
from termcolor import colored


class FreshStartManager:
    """
    Manager per fresh start mode
    """
    
    def __init__(self, options: Dict):
        """
        Initialize fresh start manager
        
        Args:
            options: Dict con opzioni fresh start da config
        """
        self.options = options
        self.backup_dir = Path("fresh_start_backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        # Statistics
        self.stats = {
            'positions_closed': 0,
            'files_deleted': 0,
            'files_backed_up': 0,
            'errors': 0
        }
    
    async def execute(self, exchange=None) -> bool:
        """
        Execute fresh start sequence
        
        Args:
            exchange: ccxt exchange instance (None if DEMO_MODE)
            
        Returns:
            bool: True se fresh start completato con successo
        """
        try:
            self._log_header()
            
            # Step 1: Close all Bybit positions
            if self.options.get('close_all_positions', True) and exchange:
                await self._close_all_positions(exchange)
            elif self.options.get('close_all_positions', True) and not exchange:
                logging.info(colored("⚠️ DEMO MODE: Skipping position closure", "yellow"))
            
            # Step 2: Cleanup files
            if self.options.get('clear_position_json', True):
                self._clear_position_json()
            
            if self.options.get('clear_learning_state', False):
                self._clear_learning_state()
            
            if self.options.get('clear_rl_model', False):
                self._clear_rl_model()
            
            if self.options.get('clear_decisions', False):
                self._clear_decisions()
            
            if self.options.get('clear_postmortem', False):
                self._clear_postmortem()
            
            # Step 3: Summary
            self._log_summary()
            
            return self.stats['errors'] == 0
            
        except Exception as e:
            logging.error(colored(f"❌ Fresh start failed: {e}", "red"))
            return False
    
    async def _close_all_positions(self, exchange):
        """Close all open positions on Bybit"""
        try:
            logging.info(colored("📊 Checking Bybit positions...", "cyan"))
            
            # Fetch all positions
            positions = await exchange.fetch_positions(None, {'limit': 100, 'type': 'swap'})
            active_positions = [p for p in positions if float(p.get('contracts', 0)) != 0]
            
            if not active_positions:
                logging.info(colored("✅ No positions to close", "green"))
                return
            
            logging.info(colored(f"⚠️ Found {len(active_positions)} positions to close", "yellow"))
            
            # Log positions to close
            for pos in active_positions:
                symbol = pos.get('symbol', 'Unknown')
                contracts = float(pos.get('contracts', 0))
                side = "LONG" if contracts > 0 else "SHORT"
                entry_price = float(pos.get('entryPrice', 0))
                unrealized_pnl = float(pos.get('unrealizedPnl', 0))
                
                symbol_short = symbol.replace('/USDT:USDT', '')
                pnl_color = 'green' if unrealized_pnl >= 0 else 'red'
                logging.info(colored(
                    f"  • {symbol_short} {side} @ ${entry_price:.6f} | "
                    f"PnL: ${unrealized_pnl:+.2f}",
                    pnl_color
                ))
            
            # Close all positions
            logging.info(colored("🔄 Closing all positions at market...", "yellow"))
            
            for pos in active_positions:
                try:
                    symbol = pos.get('symbol')
                    contracts = float(pos.get('contracts', 0))
                    
                    if abs(contracts) == 0:
                        continue
                    
                    # Determine side to close
                    close_side = 'sell' if contracts > 0 else 'buy'
                    
                    # Close position at market
                    await exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side=close_side,
                        amount=abs(contracts),
                        params={
                            'reduceOnly': True,
                            'positionIdx': 0  # One-way mode
                        }
                    )
                    
                    symbol_short = symbol.replace('/USDT:USDT', '')
                    logging.info(colored(f"  ✅ {symbol_short} closed", "green"))
                    self.stats['positions_closed'] += 1
                    
                    # Wait a bit to avoid rate limits
                    await asyncio.sleep(0.2)
                    
                except Exception as close_error:
                    symbol_short = pos.get('symbol', 'Unknown').replace('/USDT:USDT', '')
                    logging.error(colored(f"  ❌ Failed to close {symbol_short}: {close_error}", "red"))
                    self.stats['errors'] += 1
            
            logging.info(colored(f"✅ Closed {self.stats['positions_closed']} positions", "green"))
            
        except Exception as e:
            logging.error(colored(f"❌ Error closing positions: {e}", "red"))
            self.stats['errors'] += 1
    
    def _clear_position_json(self):
        """Clear position JSON file"""
        try:
            file_path = Path("thread_safe_positions.json")
            
            if file_path.exists():
                # Backup first
                if self.options.get('log_detailed_cleanup', True):
                    self._backup_file(file_path)
                
                # Delete
                file_path.unlink()
                logging.info(colored("  ✅ thread_safe_positions.json deleted", "green"))
                self.stats['files_deleted'] += 1
            else:
                logging.info(colored("  ⏭️ thread_safe_positions.json not found (already clean)", "cyan"))
                
        except Exception as e:
            logging.error(colored(f"  ❌ Failed to delete positions file: {e}", "red"))
            self.stats['errors'] += 1
    
    def _clear_learning_state(self):
        """Clear learning database"""
        try:
            file_path = Path("learning_db/online_learning_state.json")
            
            if file_path.exists():
                # Backup first
                if self.options.get('log_detailed_cleanup', True):
                    self._backup_file(file_path)
                
                # Delete
                file_path.unlink()
                logging.info(colored("  ✅ online_learning_state.json deleted", "green"))
                self.stats['files_deleted'] += 1
            else:
                logging.info(colored("  ⏭️ learning_db not found (already clean)", "cyan"))
                
        except Exception as e:
            logging.error(colored(f"  ❌ Failed to delete learning state: {e}", "red"))
            self.stats['errors'] += 1
    
    def _clear_rl_model(self):
        """Clear RL agent model"""
        try:
            file_path = Path("trained_models/rl_agent.pth")
            
            if file_path.exists():
                # Backup first
                if self.options.get('log_detailed_cleanup', True):
                    self._backup_file(file_path)
                
                # Delete
                file_path.unlink()
                logging.info(colored("  ✅ rl_agent.pth deleted (will use fresh threshold)", "green"))
                self.stats['files_deleted'] += 1
            else:
                logging.info(colored("  ⏭️ rl_agent.pth not found (already clean)", "cyan"))
                
        except Exception as e:
            logging.error(colored(f"  ❌ Failed to delete RL model: {e}", "red"))
            self.stats['errors'] += 1
    
    def _clear_decisions(self):
        """Clear decision files"""
        try:
            dir_path = Path("trade_decisions")
            
            if dir_path.exists():
                files = list(dir_path.glob("*.json"))
                
                if files:
                    # Backup directory
                    if self.options.get('log_detailed_cleanup', True):
                        self._backup_directory(dir_path)
                    
                    # Delete files
                    for file in files:
                        file.unlink()
                        self.stats['files_deleted'] += 1
                    
                    logging.info(colored(f"  ✅ {len(files)} decision files deleted", "green"))
                else:
                    logging.info(colored("  ⏭️ trade_decisions empty (already clean)", "cyan"))
            else:
                logging.info(colored("  ⏭️ trade_decisions not found (already clean)", "cyan"))
                
        except Exception as e:
            logging.error(colored(f"  ❌ Failed to delete decisions: {e}", "red"))
            self.stats['errors'] += 1
    
    def _clear_postmortem(self):
        """Clear post-mortem files"""
        try:
            dir_path = Path("trade_postmortem")
            
            if dir_path.exists():
                files = list(dir_path.glob("*.json"))
                
                if files:
                    # Backup directory
                    if self.options.get('log_detailed_cleanup', True):
                        self._backup_directory(dir_path)
                    
                    # Delete files
                    for file in files:
                        file.unlink()
                        self.stats['files_deleted'] += 1
                    
                    logging.info(colored(f"  ✅ {len(files)} post-mortem files deleted", "green"))
                else:
                    logging.info(colored("  ⏭️ trade_postmortem empty (already clean)", "cyan"))
            else:
                logging.info(colored("  ⏭️ trade_postmortem not found (already clean)", "cyan"))
                
        except Exception as e:
            logging.error(colored(f"  ❌ Failed to delete post-mortem: {e}", "red"))
            self.stats['errors'] += 1
    
    def _backup_file(self, file_path: Path):
        """Backup a file before deletion"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
            backup_path = self.backup_dir / backup_name
            
            shutil.copy2(file_path, backup_path)
            self.stats['files_backed_up'] += 1
            
            if self.options.get('log_detailed_cleanup', True):
                logging.debug(f"  📦 Backed up: {file_path.name} → {backup_name}")
                
        except Exception as e:
            logging.warning(f"  ⚠️ Backup failed for {file_path.name}: {e}")
    
    def _backup_directory(self, dir_path: Path):
        """Backup a directory before deletion"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{dir_path.name}_{timestamp}"
            backup_path = self.backup_dir / backup_name
            
            shutil.copytree(dir_path, backup_path)
            self.stats['files_backed_up'] += len(list(dir_path.glob("*")))
            
            if self.options.get('log_detailed_cleanup', True):
                logging.debug(f"  📦 Backed up directory: {dir_path.name} → {backup_name}")
                
        except Exception as e:
            logging.warning(f"  ⚠️ Directory backup failed for {dir_path.name}: {e}")
    
    def _log_header(self):
        """Log fresh start header"""
        logging.info("\n" + "=" * 80)
        logging.info(colored("🧹 FRESH START MODE ENABLED", "cyan", attrs=['bold']))
        logging.info("=" * 80)
        
        logging.info(colored("\n📋 Fresh Start Options:", "cyan"))
        for key, value in self.options.items():
            status = "✅ ENABLED" if value else "⏭️ DISABLED"
            color = "green" if value else "yellow"
            logging.info(colored(f"  • {key}: {status}", color))
        
        logging.info("\n" + "-" * 80)
    
    def _log_summary(self):
        """Log fresh start summary"""
        logging.info("\n" + "-" * 80)
        logging.info(colored("📊 FRESH START SUMMARY", "cyan", attrs=['bold']))
        logging.info("-" * 80)
        
        logging.info(f"  Positions closed:  {self.stats['positions_closed']}")
        logging.info(f"  Files deleted:     {self.stats['files_deleted']}")
        logging.info(f"  Files backed up:   {self.stats['files_backed_up']}")
        logging.info(colored(f"  Errors:            {self.stats['errors']}", 
                           "red" if self.stats['errors'] > 0 else "green"))
        
        if self.stats['files_backed_up'] > 0:
            logging.info(colored(f"\n📦 Backups saved in: {self.backup_dir}/", "cyan"))
        
        logging.info("\n" + "=" * 80)
        
        if self.stats['errors'] == 0:
            logging.info(colored("✅ FRESH START COMPLETE", "green", attrs=['bold']))
        else:
            logging.warning(colored("⚠️ FRESH START COMPLETED WITH ERRORS", "yellow", attrs=['bold']))
        
        logging.info("=" * 80)
        logging.info(colored("Starting fresh session...\n", "cyan"))


async def execute_fresh_start(exchange=None, options: Dict = None) -> bool:
    """
    Execute fresh start sequence
    
    Args:
        exchange: ccxt exchange instance (None if DEMO_MODE)
        options: Fresh start options dict
        
    Returns:
        bool: True if successful
    """
    if options is None:
        options = {
            'close_all_positions': True,
            'clear_position_json': True,
            'clear_learning_state': False,
            'clear_rl_model': False,
            'clear_decisions': False,
            'clear_postmortem': False,
            'log_detailed_cleanup': True
        }
    
    manager = FreshStartManager(options)
    return await manager.execute(exchange)
