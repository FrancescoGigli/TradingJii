# 📊 GUIDA CONSULTAZIONE DATI POST-MORTEM E DECISIONI

## Data Creazione
10/02/2025 - 14:03

---

## 📁 Dove Trovare i Dati

### 1. Post-Mortem Reports (Trade Falliti)
**Directory:** `trade_postmortem/`

**Quando vengono creati:**
- Automaticamente quando un trade chiude in perdita
- Dopo chiusure manuali in perdita
- Dopo early close (chiuso prima del peak)

**Formato file:**
```
trade_postmortem/
├── postmortem_SNX_20250210_143025.json
├── postmortem_SOMI_20250210_150133.json
└── postmortem_PENGU_20250210_152401.json
```

**Naming convention:**
```
postmortem_{SYMBOL}_{YYYYMMDD}_{HHMMSS}.json
```

---

### 2. Trade Decisions (Apertura Posizioni)
**Directory:** `trade_decisions/`

**Quando vengono creati:**
- Ogni volta che apri una nuova posizione
- Salva decisione ML + rationale + context

**Formato file:**
```
trade_decisions/
├── decision_SOL_20250210_120545.json
├── decision_LINK_20250210_120547.json
└── decision_AVAX_20250210_120550.json
```

**Naming convention:**
```
decision_{SYMBOL}_{YYYYMMDD}_{HHMMSS}.json
```

---

### 3. Learning Database
**File:** `learning_db/online_learning_state.json`

**Contiene:**
- Storia completa di tutti i trade (ultimi 100)
- Pattern identificati
- Adaptive threshold
- Session statistics

---

## 📖 Come Consultare i File

### Metodo 1: Visual Studio Code (Più Facile)

1. **Apri VSCode**
2. **Naviga nelle directory:**
   - `trade_postmortem/` per analisi fallimenti
   - `trade_decisions/` per decisioni apertura
3. **Apri file JSON** - VSCode formatta automaticamente
4. **Leggi analisi strutturata**

---

### Metodo 2: Python Script (Programmatico)

```python
import json
from pathlib import Path
from datetime import datetime

# Leggi tutti i post-mortem
postmortem_dir = Path("trade_postmortem")
for file in sorted(postmortem_dir.glob("*.json")):
    with open(file) as f:
        data = json.load(f)
    
    print(f"\n{'='*80}")
    print(f"Symbol: {data['symbol']}")
    print(f"Closed: {data['timestamp']}")
    print(f"PnL: {data['trade_outcome']['final_pnl_pct']:.2f}%")
    print(f"Reason: {data['trade_outcome']['close_reason']}")
    print(f"\nPrimary Issue: {data['analysis']['primary_issue']}")
    print(f"Severity: {data['analysis']['severity']}")
    print(f"\nRecommendations:")
    for rec in data['recommendations']['immediate']:
        print(f"  - {rec}")
```

---

### Metodo 3: Command Line (Rapido)

```bash
# Vedere ultimi 5 post-mortem
ls -lt trade_postmortem/*.json | head -5

# Leggere un file specifico
cat trade_postmortem/postmortem_SNX_20250210_143025.json | python -m json.tool

# Cerca per symbol
ls trade_postmortem/*SNX*.json

# Conta fallimenti per symbol
ls trade_postmortem/*.json | cut -d'_' -f2 | sort | uniq -c
```

---

## 📋 Struttura File Post-Mortem

### Esempio: `postmortem_SNX_20250210_143025.json`

```json
{
  "timestamp": "2025-02-10T14:30:25",
  "symbol": "SNX/USDT:USDT",
  
  "trade_outcome": {
    "final_pnl_pct": -50.4,
    "final_pnl_usd": -37.89,
    "close_reason": "STOP_LOSS_HIT",
    "duration_minutes": 127,
    "max_favorable_pnl_pct": 2.1
  },
  
  "decision_context": {
    "signal_strength": {
      "xgb_confidence": 0.72,
      "rl_approved": true,
      "rl_confidence": 0.55
    },
    "market_conditions": {
      "volatility": 0.045,
      "trend_strength": 18.5,
      "rsi_position": 42.0
    },
    "position_details": {
      "side": "LONG",
      "entry_price": 1.328986,
      "size_usd": 75.0,
      "leverage": 10
    }
  },
  
  "analysis": {
    "primary_issue": "WEAK_SIGNAL_IN_HIGH_VOLATILITY",
    "severity": "HIGH",
    "category": "SIGNAL_QUALITY",
    "failure_factors": [
      {
        "factor": "High Volatility",
        "impact": "CRITICAL",
        "description": "Volatility 4.5% exceeded 3.5% threshold"
      },
      {
        "factor": "Weak Trend",
        "impact": "HIGH",
        "description": "ADX 18.5 below 20 minimum threshold"
      }
    ]
  },
  
  "recommendations": {
    "immediate": [
      "Avoid SNX when volatility > 3.5%",
      "Require ADX ≥ 25 for SNX trades",
      "Consider increasing XGBoost threshold to 75% for volatile symbols"
    ],
    "pattern_learning": [
      "Added to high-volatility failure pattern database",
      "Warning will trigger for similar conditions"
    ]
  },
  
  "similar_failures": [
    {
      "symbol": "SNX/USDT:USDT",
      "date": "2025-02-08T16:22:11",
      "pnl_pct": -48.2,
      "reason": "High volatility + weak trend"
    }
  ]
}
```

---

## 📋 Struttura File Decision

### Esempio: `decision_SOL_20250210_120545.json`

```json
{
  "timestamp": "2025-02-10T12:05:45",
  "symbol": "SOL/USDT:USDT",
  
  "signal_data": {
    "signal_name": "BUY",
    "confidence": 0.78,
    "rl_approved": true,
    "rl_confidence": 0.62,
    "tf_predictions": {
      "15m": 1,
      "30m": 1,
      "1h": 1
    }
  },
  
  "market_context": {
    "current_price": 98.45,
    "volatility": 0.025,
    "volume_surge": 1.35,
    "trend_strength": 28.5,
    "rsi_position": 58.0
  },
  
  "position_params": {
    "side": "LONG",
    "entry_price": 98.45,
    "position_size": 100.0,
    "leverage": 10,
    "stop_loss": 92.54,
    "trailing_trigger": 99.04
  },
  
  "decision_rationale": {
    "ml_reasoning": "Strong bullish signal with 78% confidence",
    "rl_reasoning": "Approved with 62% confidence - favorable conditions",
    "risk_assessment": "Aggressive sizing due to high confidence + low volatility",
    "market_alignment": "Strong trend (ADX 28.5) + healthy RSI (58)"
  },
  
  "portfolio_state": {
    "available_balance": 350.0,
    "active_positions": 5,
    "total_pnl_pct": -2.1
  }
}
```

---

## 🔍 Query Utili

### 1. Analisi Performance per Symbol

```python
import json
from pathlib import Path
from collections import defaultdict

# Raccogli statistiche per symbol
stats = defaultdict(lambda: {"count": 0, "total_pnl": 0.0, "avg_pnl": 0.0})

for file in Path("trade_postmortem").glob("*.json"):
    with open(file) as f:
        data = json.load(f)
    
    symbol = data['symbol'].replace('/USDT:USDT', '')
    pnl = data['trade_outcome']['final_pnl_pct']
    
    stats[symbol]["count"] += 1
    stats[symbol]["total_pnl"] += pnl

# Calcola medie e ordina
for symbol in stats:
    stats[symbol]["avg_pnl"] = stats[symbol]["total_pnl"] / stats[symbol]["count"]

# Mostra peggiori performer
worst = sorted(stats.items(), key=lambda x: x[1]["avg_pnl"])[:5]
print("\n🔴 WORST PERFORMERS:")
for symbol, data in worst:
    print(f"{symbol}: {data['count']} trades, avg PnL: {data['avg_pnl']:.2f}%")
```

---

### 2. Analisi Pattern Comuni

```python
from collections import Counter

# Raccogli issue primari
issues = []
for file in Path("trade_postmortem").glob("*.json"):
    with open(file) as f:
        data = json.load(f)
    issues.append(data['analysis']['primary_issue'])

# Conta frequenze
issue_counts = Counter(issues)

print("\n📊 MOST COMMON ISSUES:")
for issue, count in issue_counts.most_common():
    print(f"{issue}: {count} occurrences")
```

---

### 3. Analisi Temporale

```python
from datetime import datetime, timedelta

# Raccogli trade per giorno
daily_stats = defaultdict(lambda: {"count": 0, "losing": 0, "avg_pnl": 0.0})

for file in Path("trade_postmortem").glob("*.json"):
    with open(file) as f:
        data = json.load(f)
    
    date = data['timestamp'].split('T')[0]
    pnl = data['trade_outcome']['final_pnl_pct']
    
    daily_stats[date]["count"] += 1
    if pnl < 0:
        daily_stats[date]["losing"] += 1

print("\n📅 DAILY FAILURE RATE:")
for date, stats in sorted(daily_stats.items()):
    rate = (stats["losing"] / stats["count"]) * 100
    print(f"{date}: {stats['losing']}/{stats['count']} ({rate:.1f}% failure rate)")
```

---

## 🎯 Dashboard Aggregate

### Script Completo per Dashboard

```python
#!/usr/bin/env python3
"""
Post-Mortem Dashboard - Aggregate Analysis
"""

import json
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

def generate_postmortem_dashboard():
    """Generate comprehensive dashboard from all post-mortems"""
    
    postmortem_dir = Path("trade_postmortem")
    
    if not postmortem_dir.exists() or not list(postmortem_dir.glob("*.json")):
        print("📊 POST-MORTEM DASHBOARD")
        print("=" * 80)
        print("\n⚠️ No post-mortem reports found yet.")
        print("Post-mortems will be generated automatically when trades close in loss.")
        print("\nDirectory: trade_postmortem/")
        return
    
    # Collect all data
    all_trades = []
    for file in postmortem_dir.glob("*.json"):
        with open(file) as f:
            all_trades.append(json.load(f))
    
    # Statistics
    total_failures = len(all_trades)
    total_pnl = sum(t['trade_outcome']['final_pnl_pct'] for t in all_trades)
    avg_pnl = total_pnl / total_failures if total_failures > 0 else 0
    
    # By severity
    by_severity = Counter(t['analysis']['severity'] for t in all_trades)
    
    # By category
    by_category = Counter(t['analysis']['category'] for t in all_trades)
    
    # By symbol
    by_symbol = defaultdict(lambda: {"count": 0, "total_pnl": 0.0})
    for t in all_trades:
        symbol = t['symbol'].replace('/USDT:USDT', '')
        by_symbol[symbol]["count"] += 1
        by_symbol[symbol]["total_pnl"] += t['trade_outcome']['final_pnl_pct']
    
    # Common issues
    common_issues = Counter(t['analysis']['primary_issue'] for t in all_trades)
    
    # Display Dashboard
    print("\n" + "="*80)
    print("📊 POST-MORTEM AGGREGATE DASHBOARD")
    print("="*80)
    
    print(f"\n📈 OVERALL STATISTICS")
    print(f"Total Failures Analyzed: {total_failures}")
    print(f"Average PnL per Failure: {avg_pnl:.2f}%")
    print(f"Total Loss: {total_pnl:.2f}%")
    
    print(f"\n🚨 BY SEVERITY")
    for severity, count in by_severity.most_common():
        pct = (count / total_failures) * 100
        print(f"  {severity}: {count} ({pct:.1f}%)")
    
    print(f"\n📁 BY CATEGORY")
    for category, count in by_category.most_common():
        pct = (count / total_failures) * 100
        print(f"  {category}: {count} ({pct:.1f}%)")
    
    print(f"\n🔴 WORST SYMBOLS")
    worst_symbols = sorted(by_symbol.items(), 
                          key=lambda x: x[1]["total_pnl"])[:5]
    for symbol, data in worst_symbols:
        avg = data["total_pnl"] / data["count"]
        print(f"  {symbol}: {data['count']} failures, avg {avg:.2f}%")
    
    print(f"\n⚠️ MOST COMMON ISSUES")
    for issue, count in common_issues.most_common(5):
        pct = (count / total_failures) * 100
        print(f"  {issue}: {count} ({pct:.1f}%)")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    generate_postmortem_dashboard()
```

**Salva come:** `view_postmortem_dashboard.py`

**Esegui:**
```bash
python view_postmortem_dashboard.py
```

---

## 📝 File da Cercare ADESSO

Controlla se esistono già questi file:

```bash
# Learning state (dovrebbe esistere se bot avviato)
ls -lh learning_db/online_learning_state.json

# Post-mortem (esiste solo se hai trade falliti)
ls -lh trade_postmortem/*.json

# Decisions (esiste solo se hai aperto posizioni)
ls -lh trade_decisions/*.json

# Thread-safe positions (stato corrente)
ls -lh thread_safe_positions.json
```

---

## 🔔 Quando Verranno Creati

### Post-Mortem:
- ✅ Chiudi trade in perdita → post-mortem immediato
- ✅ Chiusura manuale negativa → post-mortem + reason
- ✅ Early close (prima del peak) → post-mortem analisi

### Trade Decisions:
- ✅ Ogni nuova posizione aperta → decision salvata
- ✅ Include tutto il context e rationale

### Learning State:
- ✅ Aggiornato dopo ogni trade chiuso
- ✅ Max 100 trade in memoria
- ✅ Pattern e threshold adattivi

---

## 💡 Tips Utili

### 1. Monitoring Continuo
```bash
# Watch per nuovi post-mortem
watch -n 5 'ls -lt trade_postmortem/*.json | head -3'
```

### 2. Backup Periodico
```bash
# Backup settimanale
tar -czf postmortem_backup_$(date +%Y%m%d).tar.gz trade_postmortem/ trade_decisions/ learning_db/
```

### 3. Pulizia Vecchi File
```bash
# Rimuovi post-mortem più vecchi di 30 giorni
find trade_postmortem/ -name "*.json" -mtime +30 -delete
```

---

## 📖 Documenti di Riferimento

Per maggiori dettagli tecnici:
1. **`POST_MORTEM_ANALYSIS_GUIDE.md`** - Come funziona il sistema
2. **`ANALISI_PROCESSO_DECISIONALE_COMPLETO.md`** - Processo decisionale
3. **`VERIFICA_INTEGRAZIONE_SISTEMA.md`** - Integrazione componenti

---

## 🚀 Prossimi Passi

1. **Avvia il bot** e fai qualche trade
2. **Aspetta chiusure** (automatiche o manuali)
3. **Controlla directories** per i file generati
4. **Usa script Python** per analisi aggregate
5. **Monitora pattern** per miglioramenti

**I file verranno creati AUTOMATICAMENTE - non serve fare nulla!** ✨
