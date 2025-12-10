# Strategy Optimizer - BLOCCO 3

Algoritmo Genetico (GA) per ottimizzazione automatica dei parametri di trading.

## 📋 Componenti

### 1. `strategy_params.py` - Cromosoma
Definisce tutti i parametri ottimizzabili della strategia:
- **Soglie segnali XGBoost**: confidence buy/sell, ritorno atteso, prob. SL
- **Pesi multi-timeframe**: 15m, 30m, 1h
- **SL/TP e Risk/Reward**: percentuali stop loss, take profit, R/R minimo
- **Leva dinamica**: leva base, min, max, fattori confidenza/volatilità
- **Filtri rischio**: volatilità max, drawdown max, SL consecutivi max

### 2. `fitness_evaluator.py` - Valutazione Performance
Calcola metriche complete per ogni set di parametri:
- **Return metrics**: CAGR, Total Return, Average ROE
- **Risk metrics**: Max Drawdown, Sharpe Ratio, Sortino Ratio
- **Trade quality**: Win Rate, Profit Factor, Avg R/R, SL Hit Rate
- **Formula fitness**: `(CAGR × 0.5) + (Sharpe × 0.3) - (MaxDD × 0.2)`

### 3. `backtest_simulator.py` - Simulazione Trade
Simula trading applicando parametri a segnali storici:
- Estende `training/training_simulator.py` esistente
- Applica filtri StrategyParams ai segnali XGBoost
- Simula SL/TP/Trailing realistici
- Calcola costi: fees Bybit (0.055%) + slippage (0.3%)
- Gestisce capitale, posizioni multiple, consecutive SL

### 4. `genetic_algorithm.py` - GA Engine
Implementa Algoritmo Genetico con DEAP:
- **Population**: 50-100 individui (cromosomi)
- **Generations**: 20-50 iterazioni evolutive
- **Selection**: Tournament (size=3)
- **Crossover**: Uniform (prob=0.8)
- **Mutation**: Gaussian bounded (prob=0.2)
- **Elitism**: Preserva best 2 individui
- **Tracking**: History + evolution plot

### 5. `ga_orchestrator.py` - Orchestratore Completo
Coordina l'intero processo:
- Valuta baseline (parametri attuali)
- Esegue GA optimization
- Confronta baseline vs ottimizzato
- Salva risultati (JSON, report, plot)

## 🚀 Quick Start

### Esempio 1: Ottimizzazione Rapida

```python
from strategy_optimizer.ga_orchestrator import quick_optimize

# Carica il tuo modello XGBoost e dati test
model = load_xgb_model("15m")
scaler = load_scaler("15m")
X_test, df_test = load_test_data()

# Ottimizza (veloce: 20 pop × 10 gen = 200 backtests)
best_params = quick_optimize(
    model=model,
    scaler=scaler,
    X_test=X_test,
    df_test=df_test,
    population_size=20,
    n_generations=10
)

print(f"Best confidence: {best_params.min_confidence_buy:.2%}")
print(f"Best SL: {best_params.sl_percentage:.2%}")
print(f"Fitness score: {best_params.fitness_score:.2f}")
```

### Esempio 2: Ottimizzazione Completa con Confronto

```python
from strategy_optimizer.ga_orchestrator import GAOrchestrator

# Setup orchestrator
orchestrator = GAOrchestrator(
    initial_capital=1000.0,
    duration_days=90,
    output_dir="ga_results"
)

# Run full optimization
best_params, best_metrics = orchestrator.run_optimization(
    model=model,
    scaler=scaler,
    X_test=X_test,
    df_test=df_test,
    population_size=50,    # Più grande = più esplorativo
    n_generations=30,      # Più generazioni = convergenza migliore
    save_results=True,
    compare_with_baseline=True
)

# Risultati salvati automaticamente in ga_results/
# - best_params_TIMESTAMP.json (parametri ottimali)
# - comparison_TIMESTAMP.json (confronto metriche)
# - report_TIMESTAMP.txt (report leggibile)
# - ga_evolution.png (grafico evoluzione)
```

### Esempio 3: Uso Parametri Ottimizzati in Live Trading

```python
from strategy_optimizer.strategy_params import StrategyParams

# Carica best params da ottimizzazione precedente
params = StrategyParams.from_json(open("ga_results/best_params_20241210_120000.json").read())

# Usa i parametri per filtrare segnali live
for signal in live_signals:
    # Applica filtri ottimizzati
    if params.should_trade(
        confidence=signal.confidence,
        ret_exp=signal.ret_exp,
        p_sl=signal.p_sl,
        volatility=signal.volatility,
        consecutive_sl=consecutive_sl_count
    ):
        # Calcola leva dinamica
        leverage = params.get_leverage(signal.confidence, signal.volatility)
        
        # Esegui trade con parametri ottimizzati
        execute_trade(
            symbol=signal.symbol,
            direction=signal.direction,
            leverage=leverage,
            sl_pct=params.sl_percentage,
            confidence=signal.confidence
        )
```

## 📊 Output Files

Dopo l'ottimizzazione, trovi in `ga_results/`:

### `best_params_TIMESTAMP.json`
```json
{
  "min_confidence_buy": 0.68,
  "min_confidence_sell": 0.68,
  "sl_percentage": 0.055,
  "leverage_base": 7,
  "min_risk_reward": 2.8,
  "fitness_score": 45.3,
  ...
}
```

### `comparison_TIMESTAMP.json`
```json
{
  "baseline": {
    "fitness_score": 32.5,
    "cagr": 25.3,
    "sharpe_ratio": 1.8,
    "max_drawdown_pct": 15.2,
    "win_rate": 0.52
  },
  "optimized": {
    "fitness_score": 45.3,
    "cagr": 38.7,
    "sharpe_ratio": 2.4,
    "max_drawdown_pct": 12.8,
    "win_rate": 0.61
  },
  "improvement": {
    "fitness": "+39.4%",
    "cagr": "+53.0%",
    "sharpe": "+33.3%",
    "max_dd": "-15.8%",
    "win_rate": "+17.3%"
  }
}
```

### `report_TIMESTAMP.txt`
Report testuale leggibile con tutte le metriche e confronti.

### `ga_evolution.png`
Grafico che mostra l'evoluzione della fitness durante le generazioni.

## ⚙️ Parametri GA Configurabili

```python
ga_engine = GeneticAlgorithmEngine(
    population_size=50,      # Dimensione popolazione (30-100)
    n_generations=30,        # Numero generazioni (20-50)
    crossover_prob=0.8,      # Probabilità crossover (0.7-0.9)
    mutation_prob=0.2,       # Probabilità mutazione (0.1-0.3)
    mutation_indpb=0.1,      # Prob. mutazione per gene (0.05-0.2)
    tournament_size=3,       # Dimensione tournament (3-5)
    elite_size=2,            # N. best da preservare (1-5)
    random_seed=42           # Seed per reproducibilità (opzionale)
)
```

## 🎯 Parametri Ottimizzabili

Il cromosoma include 13 parametri principali:

1. `min_confidence_buy` - Soglia confidenza per LONG (0.55-0.80)
2. `min_confidence_sell` - Soglia confidenza per SHORT (0.55-0.80)
3. `min_ret_exp` - Ritorno atteso minimo (0.01-0.05)
4. `max_p_sl` - Prob. max SL hit (0.20-0.40)
5. `weight_15m` - Peso timeframe 15m (0.8-1.2)
6. `weight_30m` - Peso timeframe 30m (1.0-1.5)
7. `weight_1h` - Peso timeframe 1h (1.2-2.0)
8. `sl_percentage` - Stop Loss % (0.04-0.10)
9. `tp_atr_multiplier` - Take Profit multiplo ATR (3.0-8.0)
10. `min_risk_reward` - R/R minimo (1.5-4.0)
11. `leverage_base` - Leva base (3-10)
12. `max_volatility` - Volatilità massima (0.05-0.12)
13. `risk_per_trade_pct` - Rischio per trade (0.01-0.05)

## 📈 Formula Fitness

```python
fitness = (CAGR × 0.5) + (Sharpe × 0.3) - (MaxDD × 0.2)
          + bonuses - penalties

Bonuses:
- Win rate > 60%: +(win_rate - 0.60) × 5
  
Penalties:
- Total trades < 10: -(10 - total_trades) × 0.5
- Win rate < 40%: -(0.40 - win_rate) × 10
- Max DD > 30%: -(max_dd - 30.0) × 0.5
```

## 🔧 Integrazione con Sistema Esistente

Il GA si integra perfettamente con i componenti esistenti:

```python
# BLOCCO 1: Data Pipeline (esistente)
from fetcher import fetch_ohlcv_data
from training.features import calculate_features
from training.labeling import label_with_triple_barrier

# BLOCCO 2: XGBoost Engine (esistente)
from training.xgb_trainer import train_xgb_model
from core.ml_predictor import RobustMLPredictor

# BLOCCO 3: GA Optimizer (NUOVO)
from strategy_optimizer.ga_orchestrator import GAOrchestrator

# BLOCCO 4: LLM Layer (esistente)
from core.ai_decision_validator import AIDecisionValidator

# BLOCCO 5: Execution Engine (esistente)
from core.trading_orchestrator import global_trading_orchestrator

# Workflow completo:
# 1. Dati → 2. XGBoost → 3. GA ottimizza params → 4. LLM valida → 5. Esegue trade
```

## 💡 Best Practices

### Ottimizzazione Efficiente
- **Prima ottimizzazione**: 30 pop × 20 gen = 600 backtests (~10-15 min)
- **Ottimizzazione fine**: 50 pop × 30 gen = 1500 backtests (~30-45 min)
- **Ri-ottimizzazione periodica**: Ogni 1-2 mesi o dopo cambio regime

### Validazione Risultati
1. **Walk-forward testing**: Testa params su periodo successivo non visto
2. **Out-of-sample**: Verifica su dati completamente nuovi
3. **Paper trading**: 1-2 settimane live prima di real money

### Overfitting Prevention
- Periodo test sufficientemente lungo (90+ giorni)
- Numero minimo trade (10+)
- Penalità su metriche irrealistiche
- Validazione su multiple coin e timeframe

## 📚 Dependencies

```bash
pip install deap>=1.4.0  # GA engine
pip install numpy pandas matplotlib
pip install xgboost scikit-learn
```

## 🐛 Troubleshooting

**"DEAP not installed"**
```bash
pip install deap
```

**"Insufficient data for backtest"**
- Assicurati X_test e df_test abbiano almeno 100+ campioni
- Periodo test minimo: 30 giorni per timeframe 15m

**"Fitness always 0"**
- Verifica che ci siano abbastanza segnali che passano i filtri
- Prova ad allargare i bounds dei parametri
- Controlla che modello XGBoost restituisca predizioni valide

**"GA non converge"**
- Aumenta numero generazioni (50+)
- Aumenta popolazione (80-100)
- Verifica che fitness function non abbia errori

## 📞 Support

Per problemi o domande:
1. Check logs dettagliati in console
2. Verifica file in `ga_results/` per analisi
3. Testa componenti singolarmente (test in `__main__` di ogni modulo)

---

**Versione**: 1.0.0  
**Autore**: Trading Bot Team  
**Data**: Dicembre 2024
