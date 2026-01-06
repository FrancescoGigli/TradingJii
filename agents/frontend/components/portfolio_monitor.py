"""
📊 Portfolio Monitor - Live Balance & Positions

Agente che recupera automaticamente:
- Balance USDT da Bybit
- Posizioni aperte con PnL in tempo reale

Si aggiorna ogni 30 secondi usando st_autorefresh già presente.
"""

import streamlit as st
import streamlit.components.v1 as components
from typing import Optional, List, Dict
from datetime import datetime

from styles.colors import PALETTE


def render_portfolio_panel():
    """
    Render il pannello portfolio nella sidebar.
    Mostra balance e posizioni live da Bybit.
    """
    try:
        from services.bybit_service import get_bybit_service
        
        bybit = get_bybit_service()
        
        st.markdown("---")
        st.markdown("### 💰 Portfolio Live")
        
        if not bybit.is_available:
            st.warning("⚠️ Bybit API non configurata")
            st.caption("Aggiungi BYBIT_API_KEY e BYBIT_API_SECRET al .env")
            return
        
        # ═══════════════════════════════════════════════════════════════════
        # BALANCE
        # ═══════════════════════════════════════════════════════════════════
        with st.spinner("Caricamento balance..."):
            balance = bybit.get_balance()
        
        if balance.is_real:
            # Mostra balance
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    "💵 Balance Totale",
                    f"${balance.total_usdt:,.2f}",
                    help="Balance totale USDT su Bybit"
                )
            with col2:
                st.metric(
                    "🟢 Disponibile",
                    f"${balance.available_usdt:,.2f}",
                    help="USDT disponibile per trading"
                )
            
            if balance.used_usdt > 0:
                st.caption(f"🔒 In uso: ${balance.used_usdt:,.2f}")
        else:
            st.error("❌ Impossibile recuperare balance")
            st.caption("Controlla le chiavi API o riprova più tardi")
        
        # ═══════════════════════════════════════════════════════════════════
        # POSIZIONI APERTE
        # ═══════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.markdown("#### 📊 Posizioni Aperte")
        
        with st.spinner("Caricamento posizioni..."):
            positions = bybit.get_positions()
        
        if not positions:
            st.info("📭 Nessuna posizione aperta")
        else:
            # Mostra ogni posizione
            for pos in positions:
                render_position_card(pos)
        
        # Timestamp ultimo aggiornamento
        st.caption(f"🔄 Ultimo update: {datetime.now().strftime('%H:%M:%S')}")
        
    except Exception as e:
        st.error(f"❌ Errore: {str(e)}")


def render_position_card(pos):
    """Render una singola posizione come card"""
    
    # Determina colori basati su direzione e PnL
    is_long = pos.side == 'long'
    side_color = PALETTE['accent_green'] if is_long else PALETTE['accent_red']
    side_emoji = "🟢" if is_long else "🔴"
    side_text = "LONG" if is_long else "SHORT"
    
    pnl_color = PALETTE['accent_green'] if pos.unrealized_pnl >= 0 else PALETTE['accent_red']
    pnl_emoji = "📈" if pos.unrealized_pnl >= 0 else "📉"
    
    # Calcola PnL percentuale
    if pos.entry_price > 0 and pos.size > 0:
        position_value = pos.entry_price * pos.size
        pnl_pct = (pos.unrealized_pnl / position_value) * 100 * pos.leverage
    else:
        pnl_pct = 0
    
    # Symbol senza /USDT:USDT
    symbol_short = pos.symbol.replace('/USDT:USDT', '').replace('/', '')
    
    # Card HTML
    html = f"""
    <div style="
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid {side_color}40;
        border-left: 4px solid {side_color};
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="font-size: 1.1rem; font-weight: bold; color: #fff;">
                    {symbol_short}
                </span>
                <span style="
                    background: {side_color}20;
                    color: {side_color};
                    padding: 2px 8px;
                    border-radius: 4px;
                    font-size: 0.75rem;
                    margin-left: 8px;
                ">{side_emoji} {side_text}</span>
            </div>
            <div style="text-align: right;">
                <span style="color: {pnl_color}; font-weight: bold; font-size: 1rem;">
                    {pnl_emoji} ${pos.unrealized_pnl:+,.2f}
                </span>
                <br>
                <span style="color: {pnl_color}; font-size: 0.8rem;">
                    ({pnl_pct:+.2f}%)
                </span>
            </div>
        </div>
        
        <div style="
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 8px;
            margin-top: 10px;
            font-size: 0.75rem;
        ">
            <div>
                <span style="color: #888;">Entry</span><br>
                <span style="color: #fff;">${pos.entry_price:,.2f}</span>
            </div>
            <div>
                <span style="color: #888;">Mark</span><br>
                <span style="color: #fff;">${pos.current_price:,.2f}</span>
            </div>
            <div>
                <span style="color: #888;">Size</span><br>
                <span style="color: #fff;">{pos.size:.4f}</span>
            </div>
        </div>
        
        <div style="
            display: flex;
            justify-content: space-between;
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid rgba(255,255,255,0.1);
            font-size: 0.7rem;
            color: #888;
        ">
            <span>⚡ {pos.leverage}x</span>
            <span>{'🛑 SL: $' + f'{pos.stop_loss:,.2f}' if pos.stop_loss else '⚠️ No SL'}</span>
            <span>{'🎯 TP: $' + f'{pos.take_profit:,.2f}' if pos.take_profit else ''}</span>
        </div>
    </div>
    """
    
    components.html(html, height=140)


def render_portfolio_summary():
    """
    Render un summary compatto del portfolio (per header).
    Restituisce None se non disponibile.
    """
    try:
        from services.bybit_service import get_bybit_service
        
        bybit = get_bybit_service()
        
        if not bybit.is_available:
            return None
        
        balance = bybit.get_balance()
        positions = bybit.get_positions()
        
        # Calcola PnL totale
        total_pnl = sum(p.unrealized_pnl for p in positions)
        
        return {
            'balance': balance.total_usdt if balance.is_real else 0,
            'available': balance.available_usdt if balance.is_real else 0,
            'positions_count': len(positions),
            'total_pnl': total_pnl,
            'is_real': balance.is_real
        }
        
    except Exception:
        return None


def render_portfolio_tab():
    """
    Render una tab completa dedicata al portfolio.
    Mostra balance, posizioni e storico in modo più dettagliato.
    """
    st.markdown("### 💼 Portfolio Manager")
    st.markdown("""
    <p style="color: #a0a0a0; font-size: 0.9rem;">
    Monitora il tuo account Bybit in tempo reale. Balance e posizioni si aggiornano ogni 30 secondi.
    </p>
    """, unsafe_allow_html=True)
    
    try:
        from services.bybit_service import get_bybit_service
        
        bybit = get_bybit_service()
        
        if not bybit.is_available:
            st.error("❌ Bybit API non configurata")
            st.markdown("""
            Per attivare il Portfolio Manager:
            
            1. Apri il file `.env`
            2. Aggiungi le tue chiavi Bybit:
               ```
               BYBIT_API_KEY=la_tua_chiave
               BYBIT_API_SECRET=il_tuo_secret
               ```
            3. Riavvia i container: `docker-compose up -d`
            """)
            return
        
        # ═══════════════════════════════════════════════════════════════════
        # BALANCE OVERVIEW
        # ═══════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.markdown("#### 💰 Account Balance")
        
        balance = bybit.get_balance()
        
        if balance.is_real:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💵 Totale", f"${balance.total_usdt:,.2f}")
            with col2:
                st.metric("🟢 Disponibile", f"${balance.available_usdt:,.2f}")
            with col3:
                st.metric("🔒 In Uso", f"${balance.used_usdt:,.2f}")
            with col4:
                used_pct = (balance.used_usdt / balance.total_usdt * 100) if balance.total_usdt > 0 else 0
                st.metric("📊 Utilizzo", f"{used_pct:.1f}%")
        else:
            st.warning("⚠️ Impossibile recuperare balance. Controlla le chiavi API.")
        
        # ═══════════════════════════════════════════════════════════════════
        # POSIZIONI APERTE
        # ═══════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.markdown("#### 📊 Posizioni Aperte")
        
        positions = bybit.get_positions()
        
        if not positions:
            st.info("📭 Nessuna posizione aperta al momento")
        else:
            # Summary
            total_pnl = sum(p.unrealized_pnl for p in positions)
            long_count = sum(1 for p in positions if p.side == 'long')
            short_count = len(positions) - long_count
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                pnl_color = "normal" if total_pnl >= 0 else "inverse"
                st.metric("📈 PnL Totale", f"${total_pnl:+,.2f}", delta_color=pnl_color)
            with col2:
                st.metric("🟢 Long", long_count)
            with col3:
                st.metric("🔴 Short", short_count)
            
            st.markdown("")
            
            # Tabella posizioni
            for pos in positions:
                render_position_card_full(pos)
        
        # Timestamp
        st.markdown("---")
        st.caption(f"🔄 Ultimo aggiornamento: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        st.caption("I dati si aggiornano automaticamente ogni 30 secondi")
        
    except Exception as e:
        st.error(f"❌ Errore: {str(e)}")


def render_position_card_full(pos):
    """Render posizione con più dettagli per la tab Portfolio"""
    
    is_long = pos.side == 'long'
    side_color = "#00ff88" if is_long else "#ff4757"
    side_emoji = "🟢" if is_long else "🔴"
    side_text = "LONG" if is_long else "SHORT"
    
    pnl_color = "#00ff88" if pos.unrealized_pnl >= 0 else "#ff4757"
    
    # PnL percentuale
    if pos.entry_price > 0 and pos.size > 0:
        position_value = pos.entry_price * pos.size
        pnl_pct = (pos.unrealized_pnl / position_value) * 100 * pos.leverage
    else:
        pnl_pct = 0
    
    symbol_short = pos.symbol.replace('/USDT:USDT', '').replace('/', '')
    
    with st.container():
        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
        
        with col1:
            st.markdown(f"**{symbol_short}** {side_emoji} {side_text}")
            st.caption(f"⚡ {pos.leverage}x leverage")
        
        with col2:
            st.metric("Entry", f"${pos.entry_price:,.2f}")
        
        with col3:
            st.metric("Mark", f"${pos.current_price:,.2f}")
        
        with col4:
            st.metric("Size", f"{pos.size:.4f}")
        
        with col5:
            st.metric(
                "PnL",
                f"${pos.unrealized_pnl:+,.2f}",
                f"{pnl_pct:+.2f}%"
            )
        
        # SL/TP info
        sl_text = f"🛑 SL: ${pos.stop_loss:,.2f}" if pos.stop_loss else "⚠️ No Stop Loss!"
        tp_text = f"🎯 TP: ${pos.take_profit:,.2f}" if pos.take_profit else "No Take Profit"
        
        if not pos.stop_loss:
            st.warning(sl_text)
        else:
            st.caption(f"{sl_text} | {tp_text}")
        
        st.markdown("---")
