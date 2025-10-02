#!/usr/bin/env python3
"""
📱 TELEGRAM NOTIFIER

Sistema di notifiche real-time per trading bot
- Notifiche apertura/chiusura posizioni
- Trailing stop alerts
- Error notifications
- Daily summaries
- Comandi interattivi (/status, /balance, etc)

SETUP:
1. Crea bot con @BotFather su Telegram
2. Ottieni TOKEN e CHAT_ID
3. Configura in config.py
4. Enable notifications: TELEGRAM_ENABLED = True
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass

# Telegram imports (optional, graceful degradation)
try:
    from telegram import Bot, Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logging.warning("⚠️ python-telegram-bot not installed. Install with: pip install python-telegram-bot")


@dataclass
class NotificationStats:
    """Statistics per notification system"""
    positions_opened: int = 0
    positions_closed: int = 0
    trailing_alerts: int = 0
    errors_sent: int = 0
    commands_received: int = 0
    last_notification: Optional[str] = None


class TelegramNotifier:
    """
    📱 Telegram Notification System
    
    FEATURES:
    - Real-time position notifications
    - Trailing stop alerts
    - Error notifications
    - Daily summaries
    - Interactive commands (/status, /balance, /stop, /start)
    """
    
    def __init__(self, token: str, chat_id: str, enable_commands: bool = True):
        """
        Initialize Telegram Notifier
        
        Args:
            token: Telegram bot token from @BotFather
            chat_id: Your Telegram chat ID
            enable_commands: Enable interactive commands
        """
        if not TELEGRAM_AVAILABLE:
            logging.error("❌ Telegram library not available. Install python-telegram-bot")
            self.enabled = False
            return
        
        self.token = token
        self.chat_id = chat_id
        self.bot = Bot(token=token)
        self.enabled = True
        self.enable_commands = enable_commands
        
        # Statistics
        self.stats = NotificationStats()
        
        # Application for commands
        self.app = None
        if enable_commands:
            self._setup_commands()
        
        logging.info("📱 Telegram Notifier initialized")
    
    def _setup_commands(self):
        """Setup interactive commands"""
        try:
            self.app = Application.builder().token(self.token).build()
            
            # Register command handlers
            self.app.add_handler(CommandHandler("status", self._cmd_status))
            self.app.add_handler(CommandHandler("balance", self._cmd_balance))
            self.app.add_handler(CommandHandler("summary", self._cmd_summary))
            self.app.add_handler(CommandHandler("help", self._cmd_help))
            
            # Start polling in background
            asyncio.create_task(self.app.run_polling())
            
            logging.info("📱 Telegram commands enabled")
        except Exception as e:
            logging.warning(f"⚠️ Could not setup Telegram commands: {e}")
    
    # ========================================
    # NOTIFICATION METHODS
    # ========================================
    
    async def send_position_opened(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        position_size: float,
        leverage: int,
        stop_loss: float,
        confidence: float
    ):
        """
        📈 Notify position opened
        
        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell'
            entry_price: Entry price
            position_size: Position size in USD
            leverage: Leverage used
            stop_loss: Stop loss price
            confidence: ML confidence
        """
        if not self.enabled:
            return
        
        try:
            # Calculate SL distance
            sl_distance_pct = abs((stop_loss - entry_price) / entry_price) * 100
            
            # Side emoji
            side_emoji = "🟢" if side.lower() in ['buy', 'long'] else "🔴"
            side_text = "LONG" if side.lower() in ['buy', 'long'] else "SHORT"
            
            message = (
                f"{side_emoji} <b>NUOVA POSIZIONE</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"📊 Symbol: <code>{symbol.replace('/USDT:USDT', '')}</code>\n"
                f"{side_emoji} Side: <b>{side_text}</b>\n"
                f"💵 Entry: <code>${entry_price:.6f}</code>\n"
                f"📏 Size: <code>${position_size:.0f}</code> ({leverage}x)\n"
                f"🛑 SL: <code>${stop_loss:.6f}</code> (-{sl_distance_pct:.1f}%)\n"
                f"🎯 Confidence: <b>{confidence:.1%}</b>\n"
                f"⏰ {datetime.now().strftime('%H:%M:%S')}"
            )
            
            await self._send_message(message)
            self.stats.positions_opened += 1
            
        except Exception as e:
            logging.error(f"📱 Failed to send position opened notification: {e}")
    
    async def send_position_closed(
        self,
        symbol: str,
        pnl_usd: float,
        pnl_pct: float,
        reason: str,
        duration_minutes: Optional[int] = None
    ):
        """
        💰 Notify position closed
        
        Args:
            symbol: Trading symbol
            pnl_usd: P&L in USD
            pnl_pct: P&L in percentage
            reason: Close reason
            duration_minutes: Position duration in minutes
        """
        if not self.enabled:
            return
        
        try:
            # Emoji based on profit/loss
            if pnl_usd > 0:
                emoji = "✅"
                status = "PROFIT"
            elif pnl_usd < 0:
                emoji = "❌"
                status = "LOSS"
            else:
                emoji = "⚖️"
                status = "BREAKEVEN"
            
            message = (
                f"{emoji} <b>POSIZIONE CHIUSA</b> ({status})\n"
                f"━━━━━━━━━━━━━━\n"
                f"📊 Symbol: <code>{symbol.replace('/USDT:USDT', '')}</code>\n"
                f"💰 P&L: <b>${pnl_usd:+.2f}</b> (<b>{pnl_pct:+.1f}%</b>)\n"
                f"📝 Reason: <i>{reason}</i>\n"
            )
            
            if duration_minutes:
                hours = duration_minutes // 60
                minutes = duration_minutes % 60
                if hours > 0:
                    message += f"⏱️ Duration: {hours}h {minutes}m\n"
                else:
                    message += f"⏱️ Duration: {minutes}m\n"
            
            message += f"⏰ {datetime.now().strftime('%H:%M:%S')}"
            
            await self._send_message(message)
            self.stats.positions_closed += 1
            
        except Exception as e:
            logging.error(f"📱 Failed to send position closed notification: {e}")
    
    async def send_trailing_activated(
        self,
        symbol: str,
        current_profit_pct: float,
        new_sl: float,
        protected_profit_pct: float
    ):
        """
        🔥 Notify trailing stop activated
        
        Args:
            symbol: Trading symbol
            current_profit_pct: Current profit percentage
            new_sl: New stop loss price
            protected_profit_pct: Protected profit percentage
        """
        if not self.enabled:
            return
        
        try:
            message = (
                f"🔥 <b>TRAILING STOP ATTIVO</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"📊 Symbol: <code>{symbol.replace('/USDT:USDT', '')}</code>\n"
                f"📈 Profit Attuale: <b>+{current_profit_pct:.1f}%</b>\n"
                f"🛡️ New SL: <code>${new_sl:.6f}</code>\n"
                f"✅ Profitto Protetto: <b>+{protected_profit_pct:.1f}%</b>\n"
                f"⏰ {datetime.now().strftime('%H:%M:%S')}"
            )
            
            await self._send_message(message)
            self.stats.trailing_alerts += 1
            
        except Exception as e:
            logging.error(f"📱 Failed to send trailing notification: {e}")
    
    async def send_error(self, error_type: str, error_msg: str):
        """
        🚨 Notify critical error
        
        Args:
            error_type: Type of error
            error_msg: Error message
        """
        if not self.enabled:
            return
        
        try:
            message = (
                f"🚨 <b>ERROR CRITICO</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"⚠️ Type: <code>{error_type}</code>\n"
                f"📝 {error_msg}\n"
                f"⏰ {datetime.now().strftime('%H:%M:%S')}"
            )
            
            await self._send_message(message)
            self.stats.errors_sent += 1
            
        except Exception as e:
            logging.error(f"📱 Failed to send error notification: {e}")
    
    async def send_daily_summary(
        self,
        total_trades: int,
        wins: int,
        losses: int,
        total_pnl: float,
        win_rate: float,
        active_positions: int
    ):
        """
        📊 Send daily summary
        
        Args:
            total_trades: Total trades today
            wins: Winning trades
            losses: Losing trades
            total_pnl: Total P&L
            win_rate: Win rate percentage
            active_positions: Currently active positions
        """
        if not self.enabled:
            return
        
        try:
            pnl_emoji = "📈" if total_pnl > 0 else "📉"
            
            message = (
                f"📊 <b>DAILY SUMMARY</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"📈 Trades: <b>{total_trades}</b>\n"
                f"✅ Wins: <b>{wins}</b> | ❌ Losses: <b>{losses}</b>\n"
                f"🎯 Win Rate: <b>{win_rate:.1f}%</b>\n"
                f"{pnl_emoji} Total P&L: <b>${total_pnl:+.2f}</b>\n"
                f"🔄 Active: <b>{active_positions}</b> positions\n"
                f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            await self._send_message(message)
            
        except Exception as e:
            logging.error(f"📱 Failed to send daily summary: {e}")
    
    # ========================================
    # INTERNAL METHODS
    # ========================================
    
    async def _send_message(self, message: str):
        """
        Internal: Send message to Telegram
        
        Args:
            message: Message text (HTML formatted)
        """
        if not self.enabled:
            return
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            self.stats.last_notification = datetime.now().isoformat()
            logging.debug(f"📱 Telegram notification sent")
            
        except TelegramError as e:
            logging.error(f"📱 Telegram send failed: {e}")
            # Don't disable on error, just log
    
    # ========================================
    # COMMAND HANDLERS (Interactive)
    # ========================================
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            # Get position manager
            from core.thread_safe_position_manager import global_thread_safe_position_manager
            
            active_positions = global_thread_safe_position_manager.safe_get_all_active_positions()
            
            if not active_positions:
                message = "📊 <b>STATUS</b>\n\nℹ️ Nessuna posizione attiva"
            else:
                message = f"📊 <b>STATUS</b>\n\n"
                message += f"🔄 Posizioni Attive: <b>{len(active_positions)}</b>\n\n"
                
                for pos in active_positions[:5]:  # Max 5
                    pnl_emoji = "📈" if pos.unrealized_pnl_pct > 0 else "📉"
                    message += (
                        f"• <code>{pos.symbol.replace('/USDT:USDT', '')}</code>\n"
                        f"  {pnl_emoji} P&L: <b>{pos.unrealized_pnl_pct:+.1f}%</b>\n"
                    )
            
            await update.message.reply_text(message, parse_mode='HTML')
            self.stats.commands_received += 1
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
    
    async def _cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command"""
        try:
            from core.thread_safe_position_manager import global_thread_safe_position_manager
            
            summary = global_thread_safe_position_manager.safe_get_session_summary()
            
            message = (
                f"💰 <b>BALANCE</b>\n\n"
                f"💵 Total: <b>${summary['balance']:.2f}</b>\n"
                f"📊 Available: <b>${summary['available_balance']:.2f}</b>\n"
                f"🔒 Used: <b>${summary['used_margin']:.2f}</b>\n"
                f"📈 P&L: <b>${summary['total_pnl_usd']:+.2f}</b> (<b>{summary['total_pnl_pct']:+.1f}%</b>)"
            )
            
            await update.message.reply_text(message, parse_mode='HTML')
            self.stats.commands_received += 1
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
    
    async def _cmd_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /summary command"""
        try:
            from core.thread_safe_position_manager import global_thread_safe_position_manager
            
            summary = global_thread_safe_position_manager.safe_get_session_summary()
            
            message = (
                f"📊 <b>SESSION SUMMARY</b>\n\n"
                f"🔄 Active: <b>{summary['active_positions']}</b>\n"
                f"✅ Closed: <b>{summary['closed_positions']}</b>\n"
                f"💰 Total P&L: <b>${summary['total_pnl_usd']:+.2f}</b>\n"
                f"📈 P&L %: <b>{summary['total_pnl_pct']:+.1f}%</b>\n"
                f"💵 Balance: <b>${summary['balance']:.2f}</b>"
            )
            
            await update.message.reply_text(message, parse_mode='HTML')
            self.stats.commands_received += 1
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        message = (
            f"📱 <b>COMANDI DISPONIBILI</b>\n\n"
            f"/status - Mostra posizioni attive\n"
            f"/balance - Mostra balance corrente\n"
            f"/summary - Riepilogo sessione\n"
            f"/help - Mostra questo messaggio"
        )
        
        await update.message.reply_text(message, parse_mode='HTML')
        self.stats.commands_received += 1
    
    # ========================================
    # UTILITY METHODS
    # ========================================
    
    def get_stats(self) -> Dict:
        """Get notification statistics"""
        return {
            'enabled': self.enabled,
            'positions_opened': self.stats.positions_opened,
            'positions_closed': self.stats.positions_closed,
            'trailing_alerts': self.stats.trailing_alerts,
            'errors_sent': self.stats.errors_sent,
            'commands_received': self.stats.commands_received,
            'last_notification': self.stats.last_notification
        }
    
    def disable(self):
        """Disable notifications"""
        self.enabled = False
        logging.info("📱 Telegram notifications disabled")
    
    def enable(self):
        """Enable notifications"""
        if TELEGRAM_AVAILABLE:
            self.enabled = True
            logging.info("📱 Telegram notifications enabled")
        else:
            logging.error("❌ Cannot enable: Telegram library not available")


# Global instance (initialized by main.py)
global_telegram_notifier: Optional[TelegramNotifier] = None
