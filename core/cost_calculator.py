"""
Cost Calculator - Minimal Implementation

Calcola costi trading (fees + slippage) per analisi stop loss e Kelly Criterion
"""

import logging
from typing import Dict


class CostCalculator:
    """Calcolatore costi trading"""
    
    def __init__(self, config):
        """
        Inizializza cost calculator
        
        Args:
            config: Config module con parametri fee e slippage
        """
        self.config = config
        
        # Fee Bybit (da config)
        self.taker_fee = getattr(config, 'BYBIT_TAKER_FEE', 0.00075)  # 0.075%
        self.maker_fee = getattr(config, 'BYBIT_MAKER_FEE', 0.00055)  # 0.055%
        
        # Slippage (da config)
        self.slippage_normal = getattr(config, 'SLIPPAGE_NORMAL', 0.003)  # 0.3%
        self.slippage_volatile = getattr(config, 'SLIPPAGE_VOLATILE', 0.010)  # 1.0%
        self.slippage_sl_panic = getattr(config, 'SLIPPAGE_SL_PANIC', 0.008)  # 0.8%
        
        # Leverage (da config)
        self.leverage = getattr(config, 'LEVERAGE', 10)
        
        logging.debug(f"💰 CostCalculator initialized | Taker: {self.taker_fee:.4%} | Leverage: {self.leverage}x")
    
    def calculate_total_round_trip_cost(
        self, 
        notional_value: float,
        use_volatile: bool = False,
        is_sl_exit: bool = False,
        is_volatile: bool = False
    ) -> Dict[str, float]:
        """
        Calcola costo totale round-trip (entry + exit)
        
        Args:
            notional_value: Valore nozionale posizione
            use_volatile: Se True, usa slippage alto (deprecated, use is_volatile)
            is_sl_exit: Se True, exit via stop loss (higher slippage)
            is_volatile: Se True, usa slippage volatile
            
        Returns:
            Dict con breakdown costi:
            - entry_fee: Fee entry
            - exit_fee: Fee exit
            - entry_slippage: Slippage entry
            - exit_slippage: Slippage exit (o SL panic)
            - total_cost: Totale costi assoluti
            - total_cost_pct: Totale costi %
            - total_cost_roe: Impatto su ROE con leverage
        """
        # Normalize parameters (backward compatibility)
        use_high_slippage = use_volatile or is_volatile
        
        # Fee (assume taker su entry e exit)
        entry_fee = notional_value * self.taker_fee
        exit_fee = notional_value * self.taker_fee
        total_fee = entry_fee + exit_fee
        
        # Slippage
        slippage_rate = self.slippage_volatile if use_high_slippage else self.slippage_normal
        entry_slippage = notional_value * slippage_rate
        
        # Exit slippage (SL panic if is_sl_exit, otherwise normal)
        if is_sl_exit:
            exit_slippage = notional_value * self.slippage_sl_panic
        else:
            exit_slippage = notional_value * slippage_rate
        
        total_slippage = entry_slippage + exit_slippage
        
        # Totale costi
        total_cost = total_fee + total_slippage
        total_cost_pct = (total_cost / notional_value) * 100  # Percentuale
        
        # Impatto su ROE (amplificato da leverage)
        total_cost_roe = total_cost_pct * self.leverage
        
        return {
            'entry_fee': entry_fee,
            'exit_fee': exit_fee,
            'entry_slippage': entry_slippage,
            'exit_slippage': exit_slippage,
            'total_fee': total_fee,
            'total_slippage': total_slippage,
            'total_cost': total_cost,
            'total_cost_pct': total_cost_pct,
            'total_cost_roe': total_cost_roe
        }


# Global instance with lazy initialization
global_cost_calculator = None


def initialize_cost_calculator(config):
    """Inizializza global cost calculator"""
    global global_cost_calculator
    if global_cost_calculator is None:
        global_cost_calculator = CostCalculator(config)
    return global_cost_calculator


def _get_cost_calculator():
    """Get or create cost calculator with lazy initialization"""
    global global_cost_calculator
    if global_cost_calculator is None:
        # Lazy init with default config
        import config
        global_cost_calculator = CostCalculator(config)
    return global_cost_calculator


# Auto-initialize on import
try:
    import config
    global_cost_calculator = CostCalculator(config)
except Exception as e:
    # Will be initialized on first use
    pass
