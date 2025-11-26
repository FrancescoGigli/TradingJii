"""
Stop Loss Manager - Sistema di gestione stop loss e trailing stop
Implementa:
- Stop loss fisso a -40% dall'entry
- Trailing stop dinamico quando profitto > 10%
- Distanza fissa di 8% dal prezzo corrente per trailing stop
"""

from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Any, Optional
from datetime import datetime
import time


class StopLossManager:
    def __init__(self, trader, db_utils):
        """
        Args:
            trader: istanza di HyperLiquidTrader
            db_utils: modulo db_utils per logging
        """
        self.trader = trader
        self.db = db_utils
        
        # Parametri configurabili
        self.INITIAL_STOP_LOSS_PCT = Decimal("0.40")  # -40% stop iniziale
        self.TRAILING_ACTIVATION_PCT = Decimal("0.10")  # Attiva trailing a +10%
        self.TRAILING_FIRST_STOP_PCT = Decimal("0.02")  # Primo stop a +2%
        self.TRAILING_DISTANCE_PCT = Decimal("0.08")  # Distanza 8% per trailing
        self.TRAILING_STEP_PCT = Decimal("0.10")  # Step di 10% per trailing
    
    def calculate_initial_stop(self, entry_price: Decimal, side: str) -> Decimal:
        """
        Calcola lo stop loss iniziale a -40% dall'entry
        
        Args:
            entry_price: prezzo di entrata
            side: 'long' o 'short'
        
        Returns:
            Decimal: prezzo dello stop loss
        """
        if side == "long":
            # Per long: stop sotto l'entry
            stop_price = entry_price * (Decimal("1") - self.INITIAL_STOP_LOSS_PCT)
        else:
            # Per short: stop sopra l'entry
            stop_price = entry_price * (Decimal("1") + self.INITIAL_STOP_LOSS_PCT)
        
        return stop_price.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
    
    def calculate_profit_pct(self, entry_price: Decimal, current_price: Decimal, side: str) -> Decimal:
        """
        Calcola la percentuale di profitto/perdita (già con leva inclusa)
        
        Args:
            entry_price: prezzo di entrata
            current_price: prezzo corrente
            side: 'long' o 'short'
        
        Returns:
            Decimal: percentuale di profitto (positivo) o perdita (negativo)
        """
        if side == "long":
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        
        return pnl_pct
    
    def calculate_trailing_stop(self, entry_price: Decimal, current_price: Decimal, 
                                side: str, highest_profit_pct: Decimal) -> Decimal:
        """
        Calcola il trailing stop basato sul profitto massimo raggiunto
        
        Logica:
        - Se profitto > 10%: stop a +2%
        - Per ogni 10% addizionale (20%, 30%, 40%...): stop a 8% sotto il nuovo livello
        
        Args:
            entry_price: prezzo di entrata
            current_price: prezzo corrente
            side: 'long' o 'short'
            highest_profit_pct: massimo profitto raggiunto finora
        
        Returns:
            Decimal: prezzo del trailing stop
        """
        # Se non abbiamo raggiunto il 10%, usa stop iniziale
        if highest_profit_pct < self.TRAILING_ACTIVATION_PCT:
            return self.calculate_initial_stop(entry_price, side)
        
        # Calcola il numero di "step" da 10% raggiunti
        steps = int(highest_profit_pct / self.TRAILING_STEP_PCT)
        
        if steps == 1:
            # Primo step: profitto 10-19% → stop a +2%
            stop_profit_pct = self.TRAILING_FIRST_STOP_PCT
        else:
            # Step successivi: profitto a step * 10% - 8%
            # Es: step 2 (20%) → stop a 12% (20% - 8%)
            #     step 3 (30%) → stop a 22% (30% - 8%)
            stop_profit_pct = (Decimal(str(steps)) * self.TRAILING_STEP_PCT) - self.TRAILING_DISTANCE_PCT
        
        # Calcola il prezzo dello stop
        if side == "long":
            stop_price = entry_price * (Decimal("1") + stop_profit_pct)
        else:
            stop_price = entry_price * (Decimal("1") - stop_profit_pct)
        
        return stop_price.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
    
    def get_position_stops(self) -> Dict[str, Dict[str, Any]]:
        """
        Recupera gli stop loss attivi dal database
        
        Returns:
            Dict: {symbol: {entry_price, current_stop_price, stop_type, highest_profit_pct, ...}}
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT symbol, entry_price, current_stop_price, stop_type, 
                       highest_profit_pct, leverage, side
                FROM position_stops
                WHERE is_active = TRUE
            """)
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            stops = {}
            for row in results:
                stops[row[0]] = {
                    'entry_price': Decimal(str(row[1])),
                    'current_stop_price': Decimal(str(row[2])),
                    'stop_type': row[3],
                    'highest_profit_pct': Decimal(str(row[4] or 0)),
                    'leverage': row[5],
                    'side': row[6]
                }
            
            return stops
            
        except Exception as e:
            print(f"⚠️ Errore recuperando stop dal database: {e}")
            return {}
    
    def update_position_stop(self, symbol: str, entry_price: Decimal, side: str,
                            current_stop_price: Decimal, stop_type: str,
                            highest_profit_pct: Decimal, leverage: int = 10):
        """
        Aggiorna o crea record di stop loss per una posizione
        
        Args:
            symbol: simbolo della posizione
            entry_price: prezzo di entrata
            side: 'long' o 'short'
            current_stop_price: prezzo dello stop corrente
            stop_type: 'fixed' o 'trailing'
            highest_profit_pct: massimo profitto raggiunto
            leverage: leva utilizzata
        """
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Disattiva eventuali stop precedenti per questo simbolo
            cursor.execute("""
                UPDATE position_stops
                SET is_active = FALSE
                WHERE symbol = %s AND is_active = TRUE
            """, (symbol,))
            
            # Inserisci nuovo record
            cursor.execute("""
                INSERT INTO position_stops 
                (symbol, entry_price, side, current_stop_price, stop_type, 
                 highest_profit_pct, leverage, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            """, (
                symbol,
                float(entry_price),
                side,
                float(current_stop_price),
                stop_type,
                float(highest_profit_pct),
                leverage
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"⚠️ Errore aggiornando stop per {symbol}: {e}")
    
    def deactivate_position_stop(self, symbol: str):
        """Disattiva lo stop per una posizione chiusa"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE position_stops
                SET is_active = FALSE
                WHERE symbol = %s AND is_active = TRUE
            """, (symbol,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"⚠️ Errore disattivando stop per {symbol}: {e}")
    
    def check_and_execute_stops(self) -> List[Dict[str, Any]]:
        """
        Controlla tutte le posizioni aperte e esegue le chiusure necessarie
        
        Returns:
            List[Dict]: lista delle posizioni chiuse con dettagli
        """
        print("\n🛡️ CONTROLLO STOP LOSS E TRAILING STOP")
        print("=" * 60)
        
        closed_positions = []
        
        try:
            # Ottieni posizioni aperte dal trader
            account_status = self.trader.get_account_status()
            open_positions = account_status.get('open_positions', [])
            
            if not open_positions:
                print("✅ Nessuna posizione aperta da monitorare")
                return closed_positions
            
            # Ottieni prezzi correnti
            mids = self.trader.info.all_mids()
            
            # Ottieni stop dal database
            saved_stops = self.get_position_stops()
            
            for position in open_positions:
                symbol = position['symbol']
                side = position['side']
                entry_price = Decimal(str(position['entry_price']))
                current_price = Decimal(str(mids.get(symbol, position['mark_price'])))
                size = position['size']
                
                print(f"\n📊 {symbol} ({side.upper()})")
                print(f"   Entry: ${entry_price:.4f} | Current: ${current_price:.4f}")
                
                # Calcola profitto corrente
                profit_pct = self.calculate_profit_pct(entry_price, current_price, side)
                print(f"   Profit: {profit_pct * 100:.2f}%")
                
                # Recupera o inizializza stop
                if symbol in saved_stops:
                    stop_data = saved_stops[symbol]
                    highest_profit_pct = max(stop_data['highest_profit_pct'], profit_pct)
                else:
                    # Prima volta che vediamo questa posizione
                    highest_profit_pct = profit_pct
                    stop_data = None
                
                # Calcola stop appropriato
                if highest_profit_pct >= self.TRAILING_ACTIVATION_PCT:
                    # Usa trailing stop
                    stop_price = self.calculate_trailing_stop(
                        entry_price, current_price, side, highest_profit_pct
                    )
                    stop_type = "trailing"
                else:
                    # Usa stop fisso
                    stop_price = self.calculate_initial_stop(entry_price, side)
                    stop_type = "fixed"
                
                print(f"   Stop Type: {stop_type.upper()}")
                print(f"   Stop Price: ${stop_price:.4f}")
                print(f"   Highest Profit: {highest_profit_pct * 100:.2f}%")
                
                # Verifica se lo stop è stato colpito
                stop_hit = False
                if side == "long":
                    stop_hit = current_price <= stop_price
                else:
                    stop_hit = current_price >= stop_price
                
                if stop_hit:
                    print(f"   🚨 STOP HIT! Chiusura posizione...")
                    
                    # Esegui chiusura
                    reason = f"{stop_type}_stop_loss"
                    try:
                        result = self.trader.close_position_with_reason(symbol, reason)
                        
                        closure_info = {
                            'symbol': symbol,
                            'side': side,
                            'entry_price': float(entry_price),
                            'close_price': float(current_price),
                            'size': size,
                            'profit_pct': float(profit_pct * 100),
                            'stop_type': stop_type,
                            'reason': reason,
                            'timestamp': datetime.now().isoformat(),
                            'exchange_result': result
                        }
                        
                        closed_positions.append(closure_info)
                        
                        # Disattiva lo stop nel database
                        self.deactivate_position_stop(symbol)
                        
                        print(f"   ✅ Posizione chiusa con successo")
                        
                    except Exception as e:
                        print(f"   ❌ Errore chiudendo posizione: {e}")
                
                else:
                    # Stop non colpito, aggiorna il database
                    print(f"   ✅ Stop NON colpito, posizione mantenuta")
                    
                    self.update_position_stop(
                        symbol=symbol,
                        entry_price=entry_price,
                        side=side,
                        current_stop_price=stop_price,
                        stop_type=stop_type,
                        highest_profit_pct=highest_profit_pct,
                        leverage=10
                    )
            
            print("\n" + "=" * 60)
            if closed_positions:
                print(f"🔴 {len(closed_positions)} posizione/i chiusa/e per stop loss")
            else:
                print("✅ Tutte le posizioni sono sicure")
            
            return closed_positions
            
        except Exception as e:
            print(f"❌ Errore nel controllo degli stop: {e}")
            import traceback
            traceback.print_exc()
            return closed_positions
