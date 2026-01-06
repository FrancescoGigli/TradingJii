"""
⚙️ Risk Manager - Trading Settings & Risk Calculations

Provides:
- TradingSettings: User-configurable trading parameters
- RiskManager: Calculate SL/TP prices, position sizing

Settings are stored in Streamlit session_state for persistence across tabs.
"""

import os
import logging
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, field
from datetime import datetime

import streamlit as st

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TradingSettings:
    """
    User-configurable trading settings.
    
    These values can be modified from the sidebar and are used
    both for backtest simulation and real trading.
    """
    # Stop Loss / Take Profit
    stop_loss_pct: float = 2.0      # Stop loss percentage (e.g., 2.0 = 2%)
    take_profit_pct: float = 4.0    # Take profit percentage (e.g., 4.0 = 4%)
    
    # Leverage
    leverage: int = 5               # Leverage multiplier (1x - 20x)
    
    # Position sizing
    risk_per_trade_pct: float = 2.0  # % of balance to risk per trade
    max_position_pct: float = 20.0   # Max % of balance for single position
    
    # Advanced
    trailing_stop_enabled: bool = False
    trailing_stop_pct: float = 1.0   # Trailing stop distance
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for display/storage"""
        return {
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'leverage': self.leverage,
            'risk_per_trade_pct': self.risk_per_trade_pct,
            'max_position_pct': self.max_position_pct,
            'trailing_stop_enabled': self.trailing_stop_enabled,
            'trailing_stop_pct': self.trailing_stop_pct,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TradingSettings':
        """Create from dictionary"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class RiskManager:
    """
    Risk management calculations.
    
    Calculates:
    - Stop loss / take profit prices
    - Position sizes based on risk
    - Risk/reward ratios
    """
    
    def __init__(self, settings: TradingSettings = None):
        """
        Initialize Risk Manager.
        
        Args:
            settings: TradingSettings instance (defaults to session_state settings)
        """
        self.settings = settings or get_trading_settings()
    
    def calculate_stop_loss_price(
        self,
        entry_price: float,
        is_long: bool,
        stop_loss_pct: float = None
    ) -> float:
        """
        Calculate stop loss price.
        
        Args:
            entry_price: Entry price
            is_long: True for long, False for short
            stop_loss_pct: Override default SL percentage
        
        Returns:
            Stop loss price
        """
        sl_pct = stop_loss_pct or self.settings.stop_loss_pct
        
        if is_long:
            # Long: SL below entry
            return entry_price * (1 - sl_pct / 100)
        else:
            # Short: SL above entry
            return entry_price * (1 + sl_pct / 100)
    
    def calculate_take_profit_price(
        self,
        entry_price: float,
        is_long: bool,
        take_profit_pct: float = None
    ) -> float:
        """
        Calculate take profit price.
        
        Args:
            entry_price: Entry price
            is_long: True for long, False for short
            take_profit_pct: Override default TP percentage
        
        Returns:
            Take profit price
        """
        tp_pct = take_profit_pct or self.settings.take_profit_pct
        
        if is_long:
            # Long: TP above entry
            return entry_price * (1 + tp_pct / 100)
        else:
            # Short: TP below entry
            return entry_price * (1 - tp_pct / 100)
    
    def calculate_sl_tp_prices(
        self,
        entry_price: float,
        is_long: bool
    ) -> Tuple[float, float]:
        """
        Calculate both SL and TP prices.
        
        Returns:
            Tuple of (stop_loss_price, take_profit_price)
        """
        sl_price = self.calculate_stop_loss_price(entry_price, is_long)
        tp_price = self.calculate_take_profit_price(entry_price, is_long)
        return sl_price, tp_price
    
    def calculate_position_size(
        self,
        balance: float,
        entry_price: float,
        stop_loss_price: float = None,
        is_long: bool = True
    ) -> Dict:
        """
        Calculate position size based on risk parameters.
        
        Args:
            balance: Available balance in USDT
            entry_price: Entry price
            stop_loss_price: SL price (if None, uses default %)
            is_long: Position direction
        
        Returns:
            Dict with position sizing details
        """
        leverage = self.settings.leverage
        risk_pct = self.settings.risk_per_trade_pct
        max_position_pct = self.settings.max_position_pct
        
        # Calculate SL price if not provided
        if stop_loss_price is None:
            stop_loss_price = self.calculate_stop_loss_price(entry_price, is_long)
        
        # Calculate risk per unit
        if is_long:
            risk_per_unit = entry_price - stop_loss_price
        else:
            risk_per_unit = stop_loss_price - entry_price
        
        risk_per_unit = abs(risk_per_unit)
        
        # Calculate max risk amount
        max_risk_amount = balance * (risk_pct / 100)
        
        # Calculate position value based on risk
        if risk_per_unit > 0:
            position_value_risk = (max_risk_amount / risk_per_unit) * entry_price
        else:
            position_value_risk = 0
        
        # Calculate max position value based on % of balance
        max_position_value = balance * (max_position_pct / 100) * leverage
        
        # Use smaller of the two
        position_value = min(position_value_risk, max_position_value)
        
        # Calculate quantity
        quantity = position_value / entry_price
        
        # Calculate actual margin required
        margin_required = position_value / leverage
        
        return {
            'quantity': round(quantity, 6),
            'position_value': round(position_value, 2),
            'margin_required': round(margin_required, 2),
            'leverage': leverage,
            'stop_loss_price': round(stop_loss_price, 2),
            'risk_amount': round(max_risk_amount, 2),
            'risk_reward_ratio': round(self.settings.take_profit_pct / self.settings.stop_loss_pct, 2),
        }
    
    def calculate_pnl(
        self,
        entry_price: float,
        exit_price: float,
        quantity: float,
        is_long: bool
    ) -> Dict:
        """
        Calculate PnL for a trade.
        
        Returns:
            Dict with PnL details
        """
        if is_long:
            price_diff = exit_price - entry_price
        else:
            price_diff = entry_price - exit_price
        
        pnl_usdt = price_diff * quantity
        pnl_pct = (price_diff / entry_price) * 100 * self.settings.leverage
        
        return {
            'pnl_usdt': round(pnl_usdt, 2),
            'pnl_pct': round(pnl_pct, 2),
            'pnl_pct_with_leverage': round(pnl_pct, 2),
            'is_profit': pnl_usdt > 0
        }
    
    def get_risk_summary(self, balance: float, entry_price: float, is_long: bool) -> str:
        """Get formatted risk summary for display"""
        sl_price, tp_price = self.calculate_sl_tp_prices(entry_price, is_long)
        position = self.calculate_position_size(balance, entry_price, sl_price, is_long)
        
        direction = "LONG" if is_long else "SHORT"
        
        return f"""
**{direction} Position Summary**
- Entry: ${entry_price:,.2f}
- Stop Loss: ${sl_price:,.2f} ({self.settings.stop_loss_pct}%)
- Take Profit: ${tp_price:,.2f} ({self.settings.take_profit_pct}%)
- Position Size: {position['quantity']:.4f}
- Position Value: ${position['position_value']:,.2f}
- Margin Required: ${position['margin_required']:,.2f}
- Leverage: {position['leverage']}x
- Max Risk: ${position['risk_amount']:,.2f}
- Risk/Reward: 1:{position['risk_reward_ratio']}
"""


# ============================================================
# SESSION STATE MANAGEMENT
# ============================================================

def _get_default_settings() -> TradingSettings:
    """Get default settings from environment or hardcoded defaults"""
    return TradingSettings(
        stop_loss_pct=float(os.getenv('DEFAULT_STOP_LOSS_PCT', 2.0)),
        take_profit_pct=float(os.getenv('DEFAULT_TAKE_PROFIT_PCT', 4.0)),
        leverage=int(os.getenv('DEFAULT_LEVERAGE', 5)),
    )


def get_trading_settings() -> TradingSettings:
    """
    Get trading settings from session state.
    Creates default settings if not exists.
    """
    if 'trading_settings' not in st.session_state:
        st.session_state.trading_settings = _get_default_settings()
    
    return st.session_state.trading_settings


def update_trading_settings(**kwargs) -> TradingSettings:
    """
    Update trading settings in session state.
    
    Args:
        **kwargs: Settings to update (e.g., stop_loss_pct=2.5)
    
    Returns:
        Updated TradingSettings
    """
    settings = get_trading_settings()
    
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    
    st.session_state.trading_settings = settings
    return settings


def render_trading_settings_ui() -> TradingSettings:
    """
    Render trading settings UI in sidebar.
    
    Returns:
        Current TradingSettings after user modifications
    """
    settings = get_trading_settings()
    
    st.markdown("---")
    st.markdown("### ⚙️ Trading Settings")
    
    # Stop Loss slider
    new_sl = st.slider(
        "📉 Stop Loss %",
        min_value=0.5,
        max_value=10.0,
        value=settings.stop_loss_pct,
        step=0.5,
        help="Stop loss percentage from entry price",
        key="sidebar_sl_slider"
    )
    
    # Take Profit slider
    new_tp = st.slider(
        "📈 Take Profit %",
        min_value=1.0,
        max_value=20.0,
        value=settings.take_profit_pct,
        step=0.5,
        help="Take profit percentage from entry price",
        key="sidebar_tp_slider"
    )
    
    # Leverage selector
    leverage_options = [1, 2, 3, 5, 10, 15, 20]
    current_leverage_idx = leverage_options.index(settings.leverage) if settings.leverage in leverage_options else 3
    
    new_leverage = st.selectbox(
        "⚡ Leverage",
        options=leverage_options,
        index=current_leverage_idx,
        format_func=lambda x: f"{x}x",
        help="Leverage multiplier for positions",
        key="sidebar_leverage_select"
    )
    
    # Risk/Reward display
    if new_sl > 0:
        rr_ratio = new_tp / new_sl
        rr_color = "#00ff88" if rr_ratio >= 2 else "#ffaa00" if rr_ratio >= 1 else "#ff4757"
        st.markdown(f"""
        <div style="background: rgba(0, 255, 255, 0.05); border: 1px solid rgba(0, 255, 255, 0.2); 
                    border-radius: 8px; padding: 10px; text-align: center; margin-top: 10px;">
            <span style="color: #888; font-size: 0.8rem;">Risk/Reward Ratio</span><br>
            <span style="color: {rr_color}; font-size: 1.2rem; font-weight: bold;">1:{rr_ratio:.1f}</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Update settings if changed
    if new_sl != settings.stop_loss_pct or new_tp != settings.take_profit_pct or new_leverage != settings.leverage:
        update_trading_settings(
            stop_loss_pct=new_sl,
            take_profit_pct=new_tp,
            leverage=new_leverage
        )
    
    return get_trading_settings()
