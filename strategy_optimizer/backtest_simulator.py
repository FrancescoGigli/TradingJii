"""
Backtest Simulator - Simula trading con StrategyParams per GA

Estende il TradingSimulator esistente e lo adatta per l'Algoritmo Genetico.
Applica i parametri di un cromosoma (StrategyParams) ai segnali storici
e simula i trade risultanti.

BLOCCO 3: Strategy Optimizer
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import logging
import numpy as np
import pandas as pd

# Riusa il TradingSimulator esistente
from training.training_simulator import TradingSimulator as BaseTradingSimulator
from training.training_simulator import TradeResult as BaseTradeResult

# Import delle strutture del GA
from strategy_optimizer.strategy_params import StrategyParams
from strategy_optimizer.fitness_evaluator import TradeResult, FitnessEvaluator, PerformanceMetrics

_LOG = logging.getLogger(__name__)


@dataclass
class Signal:
    """Segnale XGBoost per un asset/timeframe/timestamp"""
    # Identificatori (required)
    symbol: str
    timeframe: str
    timestamp: str  # o int per index
    candle_index: int  # Indice nella serie storica
    
    # Probabilità XGBoost (required)
    p_up: float
    p_down: float
    p_neutral: float
    
    # Metriche aggiuntive (required)
    ret_exp: float  # Ritorno atteso
    
    # Dati mercato al momento del segnale (required)
    price: float
    atr: float
    volatility: float
    
    # Optional fields (con default devono venire DOPO i required)
    p_sl: float = 0.0  # Prob. SL (opzionale)
    future_data: pd.DataFrame = None  # Dataframe con high/low/close futuro


class BacktestSimulator:
    """
    Simula trading applicando StrategyParams a segnali storici
    
    Input:
        - Lista di Signal storici (da XGBoost)
        - StrategyParams (cromosoma da testare)
        
    Output:
        - Lista di TradeResult
        - PerformanceMetrics via FitnessEvaluator
    """
    
    def __init__(
        self,
        initial_capital: float = 1000.0,
        taker_fee: float = 0.00055,  # Bybit 0.055%
        slippage: float = 0.003,     # 0.3% slippage
    ):
        """
        Args:
            initial_capital: Capitale iniziale per simulazione
            taker_fee: Fee taker (0.055% su Bybit)
            slippage: Slippage stimato (0.3%)
        """
        self.initial_capital = initial_capital
        self.taker_fee = taker_fee
        self.slippage = slippage
        
        # Tracking stato simulazione
        self.current_capital = initial_capital
        self.open_positions = []
        self.consecutive_sl = 0
        
        _LOG.debug(f"BacktestSimulator initialized: capital=${initial_capital:.2f}")
    
    def simulate(
        self,
        signals: List[Signal],
        params: StrategyParams,
        duration_days: int = 90
    ) -> Tuple[List[TradeResult], PerformanceMetrics]:
        """
        Simula trading completo su lista segnali storici
        
        Args:
            signals: Lista segnali XGBoost storici
            params: StrategyParams da applicare
            duration_days: Durata periodo test (per CAGR)
            
        Returns:
            (lista_trade, metriche_performance)
        """
        _LOG.debug(f"Starting backtest: {len(signals)} signals, params gen={params.generation}")
        
        # Reset stato
        self.current_capital = self.initial_capital
        self.open_positions = []
        self.consecutive_sl = 0
        trades = []
        
        # Crea simulatore base con parametri dal cromosoma
        base_simulator = self._create_base_simulator(params)
        
        # Processa ogni segnale
        for signal in signals:
            # Check se il segnale passa i filtri del cromosoma
            if not self._should_trade_signal(signal, params):
                continue
            
            # Check max posizioni
            if len(self.open_positions) >= params.max_positions:
                continue
            
            # Determina direzione
            direction = self._get_trade_direction(signal, params)
            if direction is None:
                continue
            
            # Calcola size
            margin_to_use = self._calculate_position_size(signal, params)
            if margin_to_use <= 0 or margin_to_use > self.current_capital:
                continue
            
            # Simula il trade usando il simulatore base
            trade_result = self._simulate_single_trade(
                signal=signal,
                direction=direction,
                margin=margin_to_use,
                params=params,
                base_simulator=base_simulator
            )
            
            if trade_result:
                trades.append(trade_result)
                
                # Aggiorna capitale
                self.current_capital += trade_result.pnl_usd
                
                # Tracking consecutive SL
                if trade_result.exit_reason == 'SL':
                    self.consecutive_sl += 1
                else:
                    self.consecutive_sl = 0
        
        # Valuta performance
        evaluator = FitnessEvaluator(
            initial_capital=self.initial_capital,
            cagr_weight=0.5,
            sharpe_weight=0.3,
            drawdown_penalty=0.2,
            min_trades_threshold=10
        )
        
        metrics = evaluator.evaluate(trades, duration_days=duration_days)
        
        _LOG.debug(
            f"Backtest complete: {len(trades)} trades, "
            f"fitness={metrics.fitness_score:.2f}, "
            f"win_rate={metrics.win_rate:.1%}"
        )
        
        return trades, metrics
    
    def _create_base_simulator(self, params: StrategyParams) -> BaseTradingSimulator:
        """Crea TradingSimulator base con parametri da cromosoma"""
        simulator = BaseTradingSimulator()
        
        # Override parametri con quelli del cromosoma
        simulator.leverage = params.get_leverage(0.65, 0.05)  # Usa leva base
        simulator.stop_loss_pct = params.sl_percentage
        simulator.trailing_trigger_roe = 0.12  # Fixed per ora (TODO: parametrizzare)
        simulator.trailing_distance_roe = 0.08
        simulator.min_confidence = params.min_confidence_buy  # Sarà overridden per signal specifici
        
        return simulator
    
    def _should_trade_signal(self, signal: Signal, params: StrategyParams) -> bool:
        """
        Applica filtri StrategyParams al segnale
        
        Returns:
            True se segnale passa tutti i filtri
        """
        # Determina confidenza per direzione
        confidence = max(signal.p_up, signal.p_down)
        
        # Usa il metodo del cromosoma per filtrare
        return params.should_trade(
            confidence=confidence,
            ret_exp=signal.ret_exp,
            p_sl=signal.p_sl,
            volatility=signal.volatility,
            consecutive_sl=self.consecutive_sl
        )
    
    def _get_trade_direction(self, signal: Signal, params: StrategyParams) -> str | None:
        """
        Determina direzione trade (LONG/SHORT) dal segnale
        
        Returns:
            'BUY', 'SELL', o None
        """
        # Check soglie specifiche per direzione
        if signal.p_up >= params.min_confidence_buy and signal.p_up > signal.p_down:
            return 'BUY'
        elif signal.p_down >= params.min_confidence_sell and signal.p_down > signal.p_up:
            return 'SELL'
        else:
            return None
    
    def _calculate_position_size(self, signal: Signal, params: StrategyParams) -> float:
        """
        Calcola margin da usare per la posizione
        
        Returns:
            Margin in USD
        """
        if params.use_fixed_size:
            # Size fissa
            return params.fixed_size_usd
        else:
            # Size basata su rischio
            risk_amount = self.current_capital * params.risk_per_trade_pct
            
            # Con SL percentage: margin = risk / (sl_pct * leverage)
            leverage = params.get_leverage(
                confidence=max(signal.p_up, signal.p_down),
                volatility=signal.volatility
            )
            
            margin = risk_amount / (params.sl_percentage * leverage)
            
            return min(margin, self.current_capital * 0.2)  # Max 20% del capitale per trade
    
    def _simulate_single_trade(
        self,
        signal: Signal,
        direction: str,
        margin: float,
        params: StrategyParams,
        base_simulator: BaseTradingSimulator
    ) -> TradeResult | None:
        """
        Simula singolo trade usando TradingSimulator base
        
        Returns:
            TradeResult o None se trade fallisce
        """
        try:
            # Usa il simulatore base per simulare il trade
            base_result = base_simulator.simulate_trade(
                symbol=signal.symbol,
                direction=direction,
                entry_idx=signal.candle_index,
                entry_price=signal.price,
                future_data=signal.future_data,
                confidence=max(signal.p_up, signal.p_down)
            )
            
            # Converti BaseTradeResult in TradeResult con costi
            pnl_gross = base_result.profit_loss_roe * margin
            
            # Calcola costi (entry + exit)
            notional = margin * base_simulator.leverage
            entry_cost = notional * (self.taker_fee + self.slippage)
            exit_cost = notional * (self.taker_fee + self.slippage)
            total_costs = entry_cost + exit_cost
            
            # P&L netto
            pnl_net = pnl_gross - total_costs
            pnl_pct = (pnl_net / margin) * 100 if margin > 0 else 0.0
            roe_pct = pnl_pct  # Con margin = 100% del margin, roe = pnl_pct
            
            return TradeResult(
                symbol=base_result.symbol,
                entry_time=str(signal.timestamp),
                exit_time=str(signal.timestamp),  # Placeholder (TODO: migliorare)
                direction=direction,
                entry_price=base_result.entry_price,
                exit_price=base_result.exit_price,
                position_size=notional / base_result.entry_price,
                leverage=base_simulator.leverage,
                margin_used=margin,
                pnl_usd=pnl_net,
                pnl_pct=pnl_pct,
                roe_pct=roe_pct,
                exit_reason=base_result.exit_reason,
                confidence=base_result.confidence,
                volatility=signal.volatility
            )
            
        except Exception as e:
            _LOG.warning(f"Failed to simulate trade for {signal.symbol}: {e}")
            return None
    
    def backtest_with_signals_from_model(
        self,
        model,
        scaler,
        X_test: np.ndarray,
        df_test: pd.DataFrame,
        params: StrategyParams,
        duration_days: int = 90
    ) -> Tuple[List[TradeResult], PerformanceMetrics]:
        """
        Backtesta usando previsioni da modello XGBoost
        
        Args:
            model: Modello XGBoost trained
            scaler: Scaler fitted
            X_test: Features test
            df_test: DataFrame con OHLCV test
            params: StrategyParams da applicare
            duration_days: Durata periodo
            
        Returns:
            (trades, metrics)
        """
        _LOG.info(f"Generating signals from model predictions...")
        
        # Scale features
        X_test_scaled = scaler.transform(X_test)
        
        # Predizioni
        y_pred = model.predict(X_test_scaled)
        y_proba = model.predict_proba(X_test_scaled)
        
        # Crea segnali
        signals = []
        for i in range(len(X_test)):
            if i >= len(df_test):
                break
            
            row = df_test.iloc[i]
            
            # Crea Signal
            signal = Signal(
                symbol=row.get('symbol', 'MIXED'),
                timeframe='15m',  # TODO: parametrizzare
                timestamp=row.name if isinstance(row.name, str) else str(i),
                candle_index=i,
                p_up=y_proba[i][1] if len(y_proba[i]) > 1 else 0.0,
                p_down=y_proba[i][2] if len(y_proba[i]) > 2 else 0.0,
                p_neutral=y_proba[i][0],
                ret_exp=0.03,  # Placeholder (TODO: da regressore)
                p_sl=0.25,     # Placeholder
                price=row['close'],
                atr=row.get('atr', row['close'] * 0.03),
                volatility=row.get('volatility', 0.05),
                future_data=df_test.iloc[i+1:] if i+1 < len(df_test) else pd.DataFrame()
            )
            
            signals.append(signal)
        
        _LOG.info(f"Generated {len(signals)} signals from model")
        
        # Simula
        return self.simulate(signals, params, duration_days)


def quick_backtest(
    model,
    scaler,
    X_test: np.ndarray,
    df_test: pd.DataFrame,
    params: StrategyParams,
    initial_capital: float = 1000.0,
    duration_days: int = 90
) -> PerformanceMetrics:
    """
    Funzione utility per backtest rapido
    
    Args:
        model: Modello XGBoost
        scaler: Scaler
        X_test: Features test
        df_test: DataFrame test
        params: StrategyParams
        initial_capital: Capitale iniziale
        duration_days: Durata periodo
        
    Returns:
        PerformanceMetrics
    """
    simulator = BacktestSimulator(initial_capital=initial_capital)
    trades, metrics = simulator.backtest_with_signals_from_model(
        model=model,
        scaler=scaler,
        X_test=X_test,
        df_test=df_test,
        params=params,
        duration_days=duration_days
    )
    
    return metrics


if __name__ == "__main__":
    # Test del modulo
    print("=== Test BacktestSimulator ===\n")
    
    # Mock signal for testing
    mock_signal = Signal(
        symbol="BTC/USDT:USDT",
        timeframe="15m",
        timestamp="2024-01-01 10:00",
        candle_index=100,
        p_up=0.75,
        p_down=0.15,
        p_neutral=0.10,
        ret_exp=0.03,
        p_sl=0.25,
        price=40000,
        atr=800,
        volatility=0.05,
        future_data=pd.DataFrame({
            'high': [40100, 40200, 40300],
            'low': [39900, 40000, 40100],
            'close': [40050, 40150, 40250]
        })
    )
    
    # Create params
    params = StrategyParams.from_config()
    
    # Create simulator
    simulator = BacktestSimulator(initial_capital=1000.0)
    
    # Test single signal
    print(f"Testing signal: {mock_signal.symbol}")
    print(f"  P_UP: {mock_signal.p_up:.2f}, P_DOWN: {mock_signal.p_down:.2f}")
    print(f"  Should trade: {simulator._should_trade_signal(mock_signal, params)}")
    print(f"  Direction: {simulator._get_trade_direction(mock_signal, params)}")
    print(f"  Size: ${simulator._calculate_position_size(mock_signal, params):.2f}")
    
    print("\n✅ BacktestSimulator test complete")
