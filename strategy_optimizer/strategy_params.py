"""
Strategy Parameters - Cromosoma per Algoritmo Genetico

Definisce la struttura dei parametri della strategia che verranno ottimizzati
dall'algoritmo genetico. Ogni istanza di StrategyParams rappresenta un
"cromosoma" nel processo evolutivo.

BLOCCO 3: Strategy Optimizer
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Any
import json


@dataclass
class StrategyParams:
    """
    Cromosoma per Algoritmo Genetico - Parametri Strategia Trading
    
    Contiene tutti i parametri ottimizzabili della strategia, organizzati in:
    1. Soglie segnali XGBoost
    2. Pesi multi-timeframe
    3. SL/TP e Risk/Reward
    4. Leva dinamica
    5. Filtri rischio numerici
    """
    
    # ========================================================================
    # 1. SOGLIE SEGNALI XGBOOST
    # ========================================================================
    min_confidence_buy: float = 0.65        # Soglia minima P_UP per LONG
    min_confidence_sell: float = 0.65       # Soglia minima P_DOWN per SHORT
    min_ret_exp: float = 0.02               # Ritorno atteso minimo (2%)
    max_p_sl: float = 0.30                  # Prob. max SL hit (30%)
    
    # ========================================================================
    # 2. MULTI-TIMEFRAME
    # ========================================================================
    weight_15m: float = 1.0                 # Peso timeframe 15m
    weight_30m: float = 1.2                 # Peso timeframe 30m
    weight_1h: float = 1.5                  # Peso timeframe 1h
    min_aggregate_confidence: float = 0.70  # Confidenza aggregata minima
    
    # ========================================================================
    # 3. STOP LOSS / TAKE PROFIT e RISK/REWARD
    # ========================================================================
    sl_atr_multiplier: float = 2.0          # SL = ATR × questo (default 2.0)
    tp_atr_multiplier: float = 5.0          # TP = ATR × questo (default 5.0)
    min_risk_reward: float = 2.0            # R/R minimo accettabile
    
    # SL percentage based (alternativo ad ATR)
    sl_percentage: float = 0.06             # SL fisso in % (6% default)
    use_atr_sl: bool = False                # False = usa sl_percentage
    
    # ========================================================================
    # 4. LEVA DINAMICA
    # ========================================================================
    leverage_min: int = 3                   # Leva minima
    leverage_max: int = 10                  # Leva massima
    leverage_base: int = 5                  # Leva base di default
    
    # Fattori per leva dinamica (se abilitata)
    leverage_conf_factor: float = 2.0       # Fattore confidenza → leva
    leverage_vol_factor: float = -1.0       # Fattore volatilità → leva (negativo)
    use_dynamic_leverage: bool = False      # True = leva varia con conf/vol
    
    # ========================================================================
    # 5. FILTRI RISCHIO NUMERICI
    # ========================================================================
    max_volatility: float = 0.08            # Volatilità massima (8%)
    max_drawdown_pct: float = 0.20          # Max drawdown tollerato (20%)
    max_consecutive_sl: int = 3             # Stop loss consecutivi max
    
    # Filtri aggiuntivi
    min_volume_threshold: float = 1_000_000  # Volume minimo asset
    max_correlation: float = 0.80            # Correlazione max tra posizioni
    
    # ========================================================================
    # 6. POSITION SIZING
    # ========================================================================
    risk_per_trade_pct: float = 0.02        # Rischio per trade (2% capitale)
    max_positions: int = 10                 # Numero max posizioni simultanee
    use_fixed_size: bool = True             # True = size fissa, False = risk-based
    fixed_size_usd: float = 15.0            # Size fissa in USD
    
    # ========================================================================
    # METADATI
    # ========================================================================
    generation: int = 0                     # Generazione GA di appartenenza
    fitness_score: float = 0.0              # Fitness calcolato
    
    def __post_init__(self):
        """Validazione parametri dopo inizializzazione"""
        # Validazione soglie confidence
        assert 0.0 <= self.min_confidence_buy <= 1.0, "min_confidence_buy must be in [0, 1]"
        assert 0.0 <= self.min_confidence_sell <= 1.0, "min_confidence_sell must be in [0, 1]"
        
        # Validazione leva
        assert 1 <= self.leverage_min <= self.leverage_max <= 20, "Invalid leverage range"
        assert self.leverage_min <= self.leverage_base <= self.leverage_max, "leverage_base out of range"
        
        # Validazione risk
        assert 0.0 < self.risk_per_trade_pct <= 0.10, "risk_per_trade_pct must be in (0, 0.10]"
        assert 0.0 < self.max_drawdown_pct <= 1.0, "max_drawdown_pct must be in (0, 1.0]"
        
        # Validazione R/R
        assert self.min_risk_reward >= 1.0, "min_risk_reward must be >= 1.0"
        
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Converte in JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StrategyParams:
        """Crea istanza da dizionario"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> StrategyParams:
        """Crea istanza da JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @classmethod
    def from_config(cls) -> StrategyParams:
        """
        Crea istanza con parametri attuali da config.py
        Utile come baseline per confronto con GA
        """
        import config
        
        return cls(
            # Soglie segnali
            min_confidence_buy=getattr(config, 'MIN_CONFIDENCE', 0.65),
            min_confidence_sell=getattr(config, 'MIN_CONFIDENCE', 0.65),
            min_ret_exp=0.02,  # Default
            max_p_sl=0.30,     # Default
            
            # Multi-timeframe
            weight_15m=config.TIMEFRAME_WEIGHTS.get('15m', 1.0),
            weight_30m=config.TIMEFRAME_WEIGHTS.get('30m', 1.2),
            weight_1h=config.TIMEFRAME_WEIGHTS.get('1h', 1.5),
            min_aggregate_confidence=getattr(config, 'MIN_ENSEMBLE_CONFIDENCE', 0.70),
            
            # SL/TP
            sl_percentage=config.STOP_LOSS_PCT,
            use_atr_sl=False,
            tp_atr_multiplier=5.0,
            min_risk_reward=config.TP_MIN_DISTANCE_FROM_SL if hasattr(config, 'TP_MIN_DISTANCE_FROM_SL') else 2.5,
            
            # Leva
            leverage_base=config.LEVERAGE,
            leverage_min=3,
            leverage_max=10,
            use_dynamic_leverage=False,
            
            # Filtri rischio
            max_volatility=config.VOLATILITY_HIGH_THRESHOLD if hasattr(config, 'VOLATILITY_HIGH_THRESHOLD') else 0.08,
            max_drawdown_pct=0.20,
            max_consecutive_sl=3,
            
            # Position sizing
            risk_per_trade_pct=0.02,
            max_positions=config.MAX_CONCURRENT_POSITIONS,
            use_fixed_size=config.FIXED_POSITION_SIZE_ENABLED,
            fixed_size_usd=config.FIXED_POSITION_SIZE_AMOUNT if hasattr(config, 'FIXED_POSITION_SIZE_AMOUNT') else 15.0,
        )
    
    def get_leverage(self, confidence: float, volatility: float) -> int:
        """
        Calcola leva dinamica basata su confidenza e volatilità
        
        Args:
            confidence: Confidenza segnale [0, 1]
            volatility: Volatilità corrente
            
        Returns:
            Leva da utilizzare
        """
        if not self.use_dynamic_leverage:
            return self.leverage_base
        
        # Leva dinamica: aumenta con confidenza, diminuisce con volatilità
        leverage = self.leverage_base
        leverage += (confidence - 0.5) * self.leverage_conf_factor
        leverage += volatility * self.leverage_vol_factor
        
        # Clamp tra min e max
        leverage = int(max(self.leverage_min, min(self.leverage_max, leverage)))
        
        return leverage
    
    def get_timeframe_weights(self) -> Dict[str, float]:
        """Restituisce dizionario pesi timeframe"""
        return {
            '15m': self.weight_15m,
            '30m': self.weight_30m,
            '1h': self.weight_1h,
        }
    
    def should_trade(
        self, 
        confidence: float, 
        ret_exp: float, 
        p_sl: float, 
        volatility: float,
        consecutive_sl: int
    ) -> bool:
        """
        Valuta se un segnale soddisfa tutti i filtri
        
        Args:
            confidence: Confidenza del segnale
            ret_exp: Ritorno atteso
            p_sl: Probabilità stop loss
            volatility: Volatilità corrente
            consecutive_sl: Stop loss consecutivi
            
        Returns:
            True se il segnale passa tutti i filtri
        """
        # Check soglie base
        if confidence < max(self.min_confidence_buy, self.min_confidence_sell):
            return False
        
        if ret_exp < self.min_ret_exp:
            return False
        
        if p_sl > self.max_p_sl:
            return False
        
        # Check filtri rischio
        if volatility > self.max_volatility:
            return False
        
        if consecutive_sl >= self.max_consecutive_sl:
            return False
        
        return True
    
    def __repr__(self) -> str:
        """Rappresentazione leggibile"""
        return (
            f"StrategyParams(gen={self.generation}, fitness={self.fitness_score:.4f}, "
            f"conf={self.min_confidence_buy:.2f}, sl={self.sl_percentage:.2%}, "
            f"lev={self.leverage_base}, rr={self.min_risk_reward:.1f})"
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_random_params(
    generation: int = 0,
    bounds: Dict[str, tuple] = None
) -> StrategyParams:
    """
    Crea parametri casuali per popolazione iniziale GA
    
    Args:
        generation: Numero generazione
        bounds: Dizionario con limiti (min, max) per ogni parametro
        
    Returns:
        StrategyParams con valori casuali
    """
    import random
    
    # Bounds di default (se non specificati)
    default_bounds = {
        'min_confidence_buy': (0.55, 0.80),
        'min_confidence_sell': (0.55, 0.80),
        'min_ret_exp': (0.01, 0.05),
        'max_p_sl': (0.20, 0.40),
        'weight_15m': (0.8, 1.2),
        'weight_30m': (1.0, 1.5),
        'weight_1h': (1.2, 2.0),
        'sl_percentage': (0.04, 0.10),
        'tp_atr_multiplier': (3.0, 8.0),
        'min_risk_reward': (1.5, 4.0),
        'leverage_base': (3, 10),
        'max_volatility': (0.05, 0.12),
        'risk_per_trade_pct': (0.01, 0.05),
    }
    
    bounds = bounds or default_bounds
    
    def rand_in_range(key: str, default_val):
        if key in bounds:
            min_val, max_val = bounds[key]
            if isinstance(default_val, int):
                return random.randint(int(min_val), int(max_val))
            else:
                return random.uniform(min_val, max_val)
        return default_val
    
    # Crea istanza con valori casuali
    baseline = StrategyParams.from_config()
    
    return StrategyParams(
        min_confidence_buy=rand_in_range('min_confidence_buy', baseline.min_confidence_buy),
        min_confidence_sell=rand_in_range('min_confidence_sell', baseline.min_confidence_sell),
        min_ret_exp=rand_in_range('min_ret_exp', baseline.min_ret_exp),
        max_p_sl=rand_in_range('max_p_sl', baseline.max_p_sl),
        weight_15m=rand_in_range('weight_15m', baseline.weight_15m),
        weight_30m=rand_in_range('weight_30m', baseline.weight_30m),
        weight_1h=rand_in_range('weight_1h', baseline.weight_1h),
        min_aggregate_confidence=baseline.min_aggregate_confidence,
        sl_percentage=rand_in_range('sl_percentage', baseline.sl_percentage),
        tp_atr_multiplier=rand_in_range('tp_atr_multiplier', baseline.tp_atr_multiplier),
        min_risk_reward=rand_in_range('min_risk_reward', baseline.min_risk_reward),
        leverage_base=rand_in_range('leverage_base', baseline.leverage_base),
        max_volatility=rand_in_range('max_volatility', baseline.max_volatility),
        risk_per_trade_pct=rand_in_range('risk_per_trade_pct', baseline.risk_per_trade_pct),
        generation=generation,
        # Altri parametri mantengono valori di default
        leverage_min=baseline.leverage_min,
        leverage_max=baseline.leverage_max,
        use_dynamic_leverage=baseline.use_dynamic_leverage,
        max_drawdown_pct=baseline.max_drawdown_pct,
        max_consecutive_sl=baseline.max_consecutive_sl,
        max_positions=baseline.max_positions,
        use_fixed_size=baseline.use_fixed_size,
        fixed_size_usd=baseline.fixed_size_usd,
    )


if __name__ == "__main__":
    # Test del modulo
    print("=== Test StrategyParams ===\n")
    
    # Test 1: Creazione da config
    params_config = StrategyParams.from_config()
    print("1. Parametri da config.py:")
    print(params_config)
    print()
    
    # Test 2: Creazione casuale
    params_random = create_random_params(generation=1)
    print("2. Parametri casuali:")
    print(params_random)
    print()
    
    # Test 3: Serializzazione JSON
    print("3. JSON serialization:")
    json_str = params_config.to_json()
    print(json_str[:200] + "...")
    print()
    
    # Test 4: Filtro segnale
    print("4. Test filtro segnale:")
    should_trade = params_config.should_trade(
        confidence=0.70,
        ret_exp=0.03,
        p_sl=0.25,
        volatility=0.05,
        consecutive_sl=1
    )
    print(f"Should trade: {should_trade}")
