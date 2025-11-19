#!/usr/bin/env python3
"""
📝 TRADE HISTORY LOGGER

Sistema di logging completo per tutti i trade aperti e chiusi.
Registra in formato JSON tutti i dettagli recuperati da Bybit:
- Timestamp apertura/chiusura
- Prezzi entry/exit
- Leva utilizzata
- Fee pagate
- PnL realizzato
- Margin utilizzato
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional, List
from threading import Lock
from pathlib import Path

import config


class TradeHistoryLogger:
    """Logger per storia completa dei trade con dati da Bybit"""
    
    def __init__(self, json_file: str = "data_cache/trade_history.json"):
        self.json_file = json_file
        self.lock = Lock()
        self._ensure_file_exists()
        
        # Statistiche in memoria per performance
        self._stats = {
            'total_trades_opened': 0,
            'total_trades_closed': 0,
            'last_update': None
        }
        
        logging.info(f"📝 Trade History Logger initialized: {self.json_file}")
    
    def _ensure_file_exists(self):
        """Crea il file JSON se non esiste"""
        try:
            # Crea directory se necessaria
            Path(self.json_file).parent.mkdir(parents=True, exist_ok=True)
            
            # Crea file vuoto se non esiste
            if not os.path.exists(self.json_file):
                with open(self.json_file, 'w', encoding='utf-8') as f:
                    json.dump({'trades': [], 'metadata': {'created': datetime.now().isoformat()}}, f, indent=2)
                logging.info(f"✅ Created new trade history file: {self.json_file}")
        except Exception as e:
            logging.error(f"❌ Error creating trade history file: {e}")
    
    def log_trade_opened(self, position_data: Dict, bybit_data: Optional[Dict] = None) -> bool:
        """
        Registra l'apertura di un nuovo trade con dati da Bybit
        
        Args:
            position_data: Dati della posizione locale
            bybit_data: Dati raw da Bybit (opzionale, per fee e dettagli extra)
        
        Returns:
            bool: True se registrato con successo
        """
        try:
            with self.lock:
                # Carica dati esistenti
                trades_data = self._load_trades()
                
                # Crea record del trade
                trade_record = {
                    'trade_id': position_data.get('position_id', f"UNKNOWN_{datetime.now().timestamp()}"),
                    'symbol': position_data.get('symbol', 'UNKNOWN'),
                    'symbol_short': position_data.get('symbol', '').replace('/USDT:USDT', ''),
                    'status': 'OPEN',
                    
                    # Timestamp apertura
                    'open_time': position_data.get('entry_time', datetime.now().isoformat()),
                    'open_timestamp': self._parse_timestamp(position_data.get('entry_time')),
                    
                    # Dettagli posizione
                    'side': position_data.get('side', 'UNKNOWN').upper(),
                    'entry_price': float(position_data.get('entry_price', 0)),
                    'position_size': float(position_data.get('position_size', 0)),
                    'contracts': float(position_data.get('position_size', 0)) / float(position_data.get('entry_price', 1)),
                    
                    # Leva e margine
                    'leverage': float(position_data.get('leverage', config.LEVERAGE)),
                    'initial_margin': float(position_data.get('real_initial_margin', 0)) or (
                        float(position_data.get('position_size', 0)) / float(position_data.get('leverage', config.LEVERAGE))
                    ),
                    
                    # Risk management
                    'stop_loss': float(position_data.get('stop_loss', 0)) if position_data.get('stop_loss') else None,
                    'take_profit': float(position_data.get('take_profit', 0)) if position_data.get('take_profit') else None,
                    
                    # Trading info
                    'confidence': float(position_data.get('confidence', 0.0)),
                    'origin': position_data.get('origin', 'UNKNOWN'),
                    
                    # Fee (se disponibile da Bybit)
                    'open_fee': self._extract_fee(bybit_data) if bybit_data else None,
                    
                    # Dati di chiusura (null per ora)
                    'close_time': None,
                    'close_timestamp': None,
                    'exit_price': None,
                    'close_fee': None,
                    'realized_pnl_usd': None,
                    'realized_pnl_pct': None,
                    'close_reason': None,
                    
                    # Metadata
                    'logged_at': datetime.now().isoformat(),
                    'bybit_raw_open': bybit_data if bybit_data else None
                }
                
                # Aggiungi alla lista
                trades_data['trades'].append(trade_record)
                
                # Salva su file
                self._save_trades(trades_data)
                
                # Aggiorna statistiche
                self._stats['total_trades_opened'] += 1
                self._stats['last_update'] = datetime.now().isoformat()
                
                symbol_short = trade_record['symbol_short']
                side_emoji = "🟢" if trade_record['side'] == 'BUY' else "🔴"
                
                logging.info(
                    f"📝 TRADE OPENED logged: {symbol_short} {side_emoji} "
                    f"Entry: ${trade_record['entry_price']:.6f} | "
                    f"Margin: ${trade_record['initial_margin']:.2f} | "
                    f"Lev: {trade_record['leverage']}x"
                )
                
                return True
                
        except Exception as e:
            logging.error(f"❌ Error logging trade open: {e}", exc_info=True)
            return False
    
    def log_trade_closed(
        self, 
        position_data: Dict, 
        exit_price: float,
        close_reason: str,
        bybit_trade_data: Optional[Dict] = None
    ) -> bool:
        """
        Aggiorna il record di un trade con i dati di chiusura da Bybit
        
        Args:
            position_data: Dati della posizione locale
            exit_price: Prezzo di uscita
            close_reason: Motivo della chiusura
            bybit_trade_data: Dati del trade da Bybit (include fee e PnL reali)
        
        Returns:
            bool: True se aggiornato con successo
        """
        try:
            with self.lock:
                trades_data = self._load_trades()
                position_id = position_data.get('position_id')
                
                # Trova il trade
                trade_found = False
                for trade in trades_data['trades']:
                    if trade['trade_id'] == position_id and trade['status'] == 'OPEN':
                        # Aggiorna con dati di chiusura
                        trade['status'] = 'CLOSED'
                        trade['close_time'] = position_data.get('close_time', datetime.now().isoformat())
                        trade['close_timestamp'] = self._parse_timestamp(trade['close_time'])
                        trade['exit_price'] = float(exit_price)
                        trade['close_reason'] = close_reason
                        
                        # PnL da Bybit (più accurato - include tutte le fee)
                        if bybit_trade_data:
                            realized_pnl = self._extract_realized_pnl(bybit_trade_data)
                            if realized_pnl is not None:
                                trade['realized_pnl_usd'] = float(realized_pnl)
                                # Calcola % dal margin
                                if trade['initial_margin'] > 0:
                                    trade['realized_pnl_pct'] = (float(realized_pnl) / trade['initial_margin']) * 100
                            
                            # Fee di chiusura
                            trade['close_fee'] = self._extract_fee(bybit_trade_data)
                            trade['bybit_raw_close'] = bybit_trade_data
                        else:
                            # Fallback: usa PnL calcolato dalla posizione
                            trade['realized_pnl_usd'] = float(position_data.get('unrealized_pnl_usd', 0))
                            trade['realized_pnl_pct'] = float(position_data.get('unrealized_pnl_pct', 0))
                        
                        # Calcola durata
                        if trade.get('open_timestamp') and trade.get('close_timestamp'):
                            duration_seconds = trade['close_timestamp'] - trade['open_timestamp']
                            trade['duration_minutes'] = round(duration_seconds / 60, 2)
                        
                        # Calcola total fee
                        if trade.get('open_fee') and trade.get('close_fee'):
                            trade['total_fee'] = trade['open_fee'] + trade['close_fee']
                        
                        trade['closed_at'] = datetime.now().isoformat()
                        trade_found = True
                        break
                
                if not trade_found:
                    logging.warning(f"⚠️ Trade {position_id} not found in history (might be from before logger was active)")
                    # Crea un nuovo record anche per trade chiuso
                    self._log_closed_trade_retroactive(
                        trades_data, position_data, exit_price, close_reason, bybit_trade_data
                    )
                
                # Salva su file
                self._save_trades(trades_data)
                
                # Aggiorna statistiche
                self._stats['total_trades_closed'] += 1
                self._stats['last_update'] = datetime.now().isoformat()
                
                symbol_short = position_data.get('symbol', '').replace('/USDT:USDT', '')
                pnl = position_data.get('unrealized_pnl_pct', 0)
                pnl_usd = position_data.get('unrealized_pnl_usd', 0)
                
                logging.info(
                    f"📝 TRADE CLOSED logged: {symbol_short} | "
                    f"Exit: ${exit_price:.6f} | "
                    f"PnL: {pnl:+.2f}% (${pnl_usd:+.2f}) | "
                    f"Reason: {close_reason}"
                )
                
                return True
                
        except Exception as e:
            logging.error(f"❌ Error logging trade close: {e}", exc_info=True)
            return False
    
    def _log_closed_trade_retroactive(
        self,
        trades_data: Dict,
        position_data: Dict,
        exit_price: float,
        close_reason: str,
        bybit_trade_data: Optional[Dict]
    ):
        """Crea un record retroattivo per un trade che non era stato loggato in apertura"""
        try:
            trade_record = {
                'trade_id': position_data.get('position_id', f"RETRO_{datetime.now().timestamp()}"),
                'symbol': position_data.get('symbol', 'UNKNOWN'),
                'symbol_short': position_data.get('symbol', '').replace('/USDT:USDT', ''),
                'status': 'CLOSED',
                
                # Apertura (dati parziali)
                'open_time': position_data.get('entry_time', 'UNKNOWN'),
                'open_timestamp': self._parse_timestamp(position_data.get('entry_time')),
                'side': position_data.get('side', 'UNKNOWN').upper(),
                'entry_price': float(position_data.get('entry_price', 0)),
                'position_size': float(position_data.get('position_size', 0)),
                'leverage': float(position_data.get('leverage', config.LEVERAGE)),
                'initial_margin': float(position_data.get('real_initial_margin', 0)) or (
                    float(position_data.get('position_size', 0)) / float(position_data.get('leverage', config.LEVERAGE))
                ),
                
                # Chiusura
                'close_time': position_data.get('close_time', datetime.now().isoformat()),
                'close_timestamp': self._parse_timestamp(position_data.get('close_time', datetime.now().isoformat())),
                'exit_price': float(exit_price),
                'close_reason': close_reason,
                'realized_pnl_usd': float(position_data.get('unrealized_pnl_usd', 0)),
                'realized_pnl_pct': float(position_data.get('unrealized_pnl_pct', 0)),
                
                # Note
                'origin': 'RETROACTIVE',
                'note': 'Trade logged retroactively (opened before logger was active)',
                'logged_at': datetime.now().isoformat(),
                
                # Bybit data se disponibile
                'bybit_raw_close': bybit_trade_data if bybit_trade_data else None
            }
            
            trades_data['trades'].append(trade_record)
            logging.info(f"📝 Retroactive trade record created for {trade_record['symbol_short']}")
            
        except Exception as e:
            logging.error(f"❌ Error creating retroactive trade: {e}")
    
    def _load_trades(self) -> Dict:
        """Carica i trade dal file JSON"""
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # File non esiste o corrotto, crea nuovo
            return {
                'trades': [],
                'metadata': {
                    'created': datetime.now().isoformat(),
                    'version': '1.0'
                }
            }
    
    def _save_trades(self, trades_data: Dict):
        """Salva i trade sul file JSON"""
        try:
            # Aggiorna metadata
            if 'metadata' not in trades_data:
                trades_data['metadata'] = {}
            
            trades_data['metadata']['last_updated'] = datetime.now().isoformat()
            trades_data['metadata']['total_trades'] = len(trades_data['trades'])
            trades_data['metadata']['open_trades'] = sum(1 for t in trades_data['trades'] if t['status'] == 'OPEN')
            trades_data['metadata']['closed_trades'] = sum(1 for t in trades_data['trades'] if t['status'] == 'CLOSED')
            
            # Salva con formattazione leggibile
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(trades_data, f, indent=2, ensure_ascii=False, default=str)
                
        except Exception as e:
            logging.error(f"❌ Error saving trades file: {e}")
            raise
    
    def _parse_timestamp(self, time_str: Optional[str]) -> Optional[float]:
        """Converte una stringa ISO timestamp in Unix timestamp"""
        if not time_str:
            return None
        try:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            return dt.timestamp()
        except Exception:
            return None
    
    def _extract_fee(self, bybit_data: Optional[Dict]) -> Optional[float]:
        """Estrae la fee dai dati Bybit"""
        if not bybit_data:
            return None
        
        try:
            # Prova diversi campi per la fee
            if 'fee' in bybit_data:
                return abs(float(bybit_data['fee']))
            elif 'info' in bybit_data and 'execFee' in bybit_data['info']:
                return abs(float(bybit_data['info']['execFee']))
            elif 'cost' in bybit_data:
                # Fee è tipicamente una % del cost
                cost = float(bybit_data['cost'])
                fee_rate = float(bybit_data.get('fees', {}).get('rate', 0.0006))  # Default 0.06%
                return abs(cost * fee_rate)
        except (ValueError, TypeError, KeyError):
            pass
        
        return None
    
    def _extract_realized_pnl(self, bybit_trade_data: Optional[Dict]) -> Optional[float]:
        """Estrae il PnL realizzato dai dati Bybit"""
        if not bybit_trade_data:
            return None
        
        try:
            # Cerca realizedPnl in info
            if 'info' in bybit_trade_data:
                pnl = bybit_trade_data['info'].get('realizedPnl') or bybit_trade_data['info'].get('closedPnl')
                if pnl not in (None, '', '0'):
                    return float(pnl)
            
            # Fallback: cerca in root
            if 'realizedPnl' in bybit_trade_data:
                return float(bybit_trade_data['realizedPnl'])
                
        except (ValueError, TypeError, KeyError):
            pass
        
        return None
    
    def get_stats(self) -> Dict:
        """Ritorna statistiche del logger"""
        with self.lock:
            trades_data = self._load_trades()
            
            closed_trades = [t for t in trades_data['trades'] if t['status'] == 'CLOSED' and t.get('realized_pnl_usd') is not None]
            
            stats = {
                'total_trades': len(trades_data['trades']),
                'open_trades': sum(1 for t in trades_data['trades'] if t['status'] == 'OPEN'),
                'closed_trades': len(closed_trades),
                'total_pnl': sum(t['realized_pnl_usd'] for t in closed_trades),
                'win_rate': (sum(1 for t in closed_trades if t['realized_pnl_usd'] > 0) / len(closed_trades) * 100) if closed_trades else 0,
                'last_update': self._stats['last_update']
            }
            
            return stats


    async def sync_closed_trades_from_bybit(self, exchange, days_back: int = 7, limit: int = 50) -> Dict:
        """
        Sincronizza i trade chiusi recuperando i dati REALI da Bybit
        Usa l'endpoint /v5/position/closed-pnl che contiene i valori CORRETTI
        
        Args:
            exchange: Istanza ccxt dell'exchange
            days_back: Giorni nel passato da cui cercare (max 7 per Bybit)
            limit: Numero massimo di posizioni da recuperare
        
        Returns:
            Dict: Statistiche della sincronizzazione
        """
        from datetime import timedelta
        
        logging.info(f"🔄 Starting sync from Bybit closed-pnl endpoint (last {days_back} days)...")
        
        try:
            # Prepare time range (Bybit is STRICT about 7 days max)
            if days_back > 7:
                logging.warning(f"⚠️ Bybit limits range to 7 days, adjusting from {days_back}")
                days_back = 7
            
            now = datetime.now()
            end_time = int(now.timestamp() * 1000)
            start_datetime = now - timedelta(days=days_back)
            start_time = int(start_datetime.timestamp() * 1000)
            
            # Double check range
            time_range_days = (end_time - start_time) / (1000 * 60 * 60 * 24)
            if time_range_days > 7:
                start_time = end_time - (7 * 24 * 60 * 60 * 1000)
                logging.warning(f"⚠️ Range adjusted to exactly 7 days")
            
            # Call Bybit V5 API - VERIFIED CORRECT ENDPOINT
            response = await exchange.private_get_v5_position_closed_pnl({
                'category': 'linear',
                'startTime': start_time,
                'endTime': end_time,
                'limit': limit
            })
            
            ret_code = response.get('retCode', -1)
            if int(ret_code) != 0:
                ret_msg = response.get('retMsg', 'Unknown')
                logging.error(f"❌ Bybit API error (code {ret_code}): {ret_msg}")
                return {'success': False, 'error': ret_msg}
            
            closed_pnl_list = response.get('result', {}).get('list', [])
            
            if not closed_pnl_list:
                logging.info(f"📭 No closed positions found in last {days_back} days")
                return {'success': True, 'trades_found': 0, 'trades_updated': 0}
            
            logging.info(f"✅ Found {len(closed_pnl_list)} closed positions from Bybit")
            
            # Process and update trades
            trades_updated = 0
            trades_created = 0
            
            with self.lock:
                trades_data = self._load_trades()
                
                for pnl_record in closed_pnl_list:
                    try:
                        # Extract symbol
                        symbol_raw = pnl_record.get('symbol', '')
                        if not symbol_raw:
                            continue
                        
                        # Convert to ccxt format
                        if '/' not in symbol_raw:
                            symbol = f"{symbol_raw.replace('USDT', '')}/USDT:USDT"
                        else:
                            symbol = symbol_raw
                        
                        # Extract VERIFIED fields from Bybit
                        bybit_data = {
                            'symbol': symbol,
                            'side': pnl_record.get('side', '').upper(),
                            'avgEntryPrice': float(pnl_record.get('avgEntryPrice', 0) or 0),
                            'avgExitPrice': float(pnl_record.get('avgExitPrice', 0) or 0),
                            'qty': float(pnl_record.get('qty', 0) or 0),
                            'leverage': float(pnl_record.get('leverage', 0) or 0),
                            
                            # VERIFIED PNL AND FEES from Bybit
                            'closedPnl': float(pnl_record.get('closedPnl', 0) or 0),
                            'openFee': float(pnl_record.get('openFee', 0) or 0),
                            'closeFee': float(pnl_record.get('closeFee', 0) or 0),
                            
                            # Timestamps
                            'createdTime': pnl_record.get('createdTime'),
                            'updatedTime': pnl_record.get('updatedTime'),
                            
                            # Additional info
                            'orderId': pnl_record.get('orderId'),
                            'orderType': pnl_record.get('orderType'),
                            'fillCount': pnl_record.get('fillCount', 0),
                        }
                        
                        # Try to find existing trade by symbol and times
                        trade_matched = self._find_matching_trade(
                            trades_data['trades'], 
                            symbol, 
                            bybit_data
                        )
                        
                        if trade_matched:
                            # Update existing trade with REAL Bybit data
                            self._update_trade_with_bybit_data(trade_matched, bybit_data)
                            trades_updated += 1
                            logging.info(f"✅ Updated {symbol.replace('/USDT:USDT', '')} with Bybit data")
                        else:
                            # Create new retroactive trade
                            self._create_trade_from_bybit_data(trades_data['trades'], bybit_data)
                            trades_created += 1
                            logging.info(f"📝 Created retroactive trade for {symbol.replace('/USDT:USDT', '')}")
                    
                    except Exception as e:
                        logging.error(f"⚠️ Error processing position: {e}")
                        continue
                
                # Save updated data
                self._save_trades(trades_data)
            
            result = {
                'success': True,
                'trades_found': len(closed_pnl_list),
                'trades_updated': trades_updated,
                'trades_created': trades_created
            }
            
            logging.info(
                f"✅ Sync completed: {trades_updated} updated, "
                f"{trades_created} created from Bybit data"
            )
            
            return result
            
        except Exception as e:
            logging.error(f"❌ Error syncing closed trades from Bybit: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _find_matching_trade(self, trades: List[Dict], symbol: str, bybit_data: Dict) -> Optional[Dict]:
        """Trova un trade esistente che corrisponde ai dati Bybit"""
        try:
            # Cerca per symbol e timestamp vicini
            for trade in trades:
                if (trade.get('symbol') == symbol and 
                    trade.get('status') == 'CLOSED'):
                    # Check if timestamps are close (within 1 minute)
                    if bybit_data.get('updatedTime'):
                        bybit_close_ts = int(bybit_data['updatedTime']) / 1000
                        trade_close_ts = trade.get('close_timestamp', 0)
                        
                        if trade_close_ts and abs(bybit_close_ts - trade_close_ts) < 60:
                            return trade
            return None
        except Exception:
            return None
    
    def _update_trade_with_bybit_data(self, trade: Dict, bybit_data: Dict):
        """Aggiorna un trade esistente con i dati REALI da Bybit"""
        try:
            # Update con valori VERIFICATI da Bybit
            trade['realized_pnl_usd'] = bybit_data['closedPnl']
            trade['open_fee'] = bybit_data['openFee']
            trade['close_fee'] = bybit_data['closeFee']
            trade['total_fee'] = bybit_data['openFee'] + bybit_data['closeFee']
            
            # Update prices if available
            if bybit_data['avgEntryPrice'] > 0:
                trade['entry_price'] = bybit_data['avgEntryPrice']
            if bybit_data['avgExitPrice'] > 0:
                trade['exit_price'] = bybit_data['avgExitPrice']
            
            # Recalculate PnL%
            if trade.get('initial_margin', 0) > 0:
                trade['realized_pnl_pct'] = (bybit_data['closedPnl'] / trade['initial_margin']) * 100
            
            # Mark as verified by Bybit
            trade['verified_by_bybit'] = True
            trade['bybit_sync_time'] = datetime.now().isoformat()
            trade['bybit_raw_data'] = bybit_data
            
        except Exception as e:
            logging.error(f"Error updating trade with Bybit data: {e}")
    
    def _create_trade_from_bybit_data(self, trades: List[Dict], bybit_data: Dict):
        """Crea un nuovo trade dai dati Bybit (per trade che non erano nel logger)"""
        try:
            symbol_short = bybit_data['symbol'].replace('/USDT:USDT', '')
            
            # Calculate metrics
            notional = bybit_data['qty'] * bybit_data['avgEntryPrice']
            margin = notional / bybit_data['leverage'] if bybit_data['leverage'] > 0 else notional
            
            # Calculate duration
            duration_minutes = 0
            created_str = 'Unknown'
            updated_str = 'Unknown'
            
            if bybit_data.get('createdTime') and bybit_data.get('updatedTime'):
                try:
                    created_ts = int(bybit_data['createdTime']) / 1000
                    updated_ts = int(bybit_data['updatedTime']) / 1000
                    duration_minutes = (updated_ts - created_ts) / 60
                    
                    created_str = datetime.fromtimestamp(created_ts).strftime('%Y-%m-%d %H:%M:%S')
                    updated_str = datetime.fromtimestamp(updated_ts).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass
            
            # Create trade record
            trade_record = {
                'trade_id': f"BYBIT_{bybit_data.get('orderId', 'UNKNOWN')}",
                'symbol': bybit_data['symbol'],
                'symbol_short': symbol_short,
                'status': 'CLOSED',
                
                # Entry
                'open_time': created_str,
                'open_timestamp': int(bybit_data.get('createdTime', 0)) / 1000 if bybit_data.get('createdTime') else None,
                'side': bybit_data['side'],
                'entry_price': bybit_data['avgEntryPrice'],
                'position_size': notional,
                'contracts': bybit_data['qty'],
                'leverage': bybit_data['leverage'],
                'initial_margin': margin,
                'open_fee': bybit_data['openFee'],
                
                # Exit
                'close_time': updated_str,
                'close_timestamp': int(bybit_data.get('updatedTime', 0)) / 1000 if bybit_data.get('updatedTime') else None,
                'exit_price': bybit_data['avgExitPrice'],
                'close_fee': bybit_data['closeFee'],
                'total_fee': bybit_data['openFee'] + bybit_data['closeFee'],
                
                # PnL VERIFIED from Bybit
                'realized_pnl_usd': bybit_data['closedPnl'],
                'realized_pnl_pct': (bybit_data['closedPnl'] / margin * 100) if margin > 0 else 0,
                
                # Metadata
                'duration_minutes': duration_minutes,
                'close_reason': 'UNKNOWN',
                'origin': 'BYBIT_SYNC',
                'verified_by_bybit': True,
                'bybit_sync_time': datetime.now().isoformat(),
                'bybit_raw_data': bybit_data,
                'logged_at': datetime.now().isoformat(),
                'note': 'Trade created from Bybit closed-pnl endpoint (not logged during execution)'
            }
            
            trades.append(trade_record)
            
        except Exception as e:
            logging.error(f"Error creating trade from Bybit data: {e}")


# Istanza globale
global_trade_history_logger = TradeHistoryLogger()


def log_trade_opened_from_position(position) -> bool:
    """
    Helper per loggare un trade aperto da un oggetto ThreadSafePosition
    
    Args:
        position: Oggetto ThreadSafePosition
    
    Returns:
        bool: True se loggato con successo
    """
    try:
        position_data = {
            'position_id': position.position_id,
            'symbol': position.symbol,
            'entry_time': position.entry_time,
            'side': position.side,
            'entry_price': position.entry_price,
            'position_size': position.position_size,
            'leverage': position.leverage,
            'real_initial_margin': position.real_initial_margin,
            'stop_loss': position.stop_loss,
            'take_profit': position.take_profit,
            'confidence': position.confidence,
            'origin': position.origin
        }
        
        return global_trade_history_logger.log_trade_opened(position_data)
        
    except Exception as e:
        logging.error(f"❌ Error in log_trade_opened_from_position: {e}")
        return False


def log_trade_closed_from_position(position, exit_price: float, close_reason: str) -> bool:
    """
    Helper per loggare un trade chiuso da un oggetto ThreadSafePosition
    
    Args:
        position: Oggetto ThreadSafePosition
        exit_price: Prezzo di uscita
        close_reason: Motivo della chiusura
    
    Returns:
        bool: True se loggato con successo
    """
    try:
        position_data = {
            'position_id': position.position_id,
            'symbol': position.symbol,
            'entry_time': position.entry_time,
            'close_time': position.close_time,
            'side': position.side,
            'entry_price': position.entry_price,
            'position_size': position.position_size,
            'leverage': position.leverage,
            'real_initial_margin': position.real_initial_margin,
            'unrealized_pnl_usd': position.unrealized_pnl_usd,
            'unrealized_pnl_pct': position.unrealized_pnl_pct
        }
        
        return global_trade_history_logger.log_trade_closed(
            position_data, exit_price, close_reason
        )
        
    except Exception as e:
        logging.error(f"❌ Error in log_trade_closed_from_position: {e}")
        return False
