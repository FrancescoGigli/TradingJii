# 🎯 Confidence Calibration System

Sistema di calibrazione delle confidence basato su risultati reali di backtest storico.

## 📋 Panoramica

Il sistema risolve il problema delle **confidence estreme (100%)** convertendo le probabilità "raw" dei modelli ML/RL in **win rate realistici** basati su performance storiche verificate.

### Problema Originale
```
XGBoost dice: "95% confidence" 
→ Ma nel backtest questo range ha solo 73% win rate!
→ Confidence non riflette la realtà
```

### Soluzione
```
XGBoost raw: 95%
↓ Calibration Layer
Confidence calibrata: 73% (win rate reale verificato)
```

---

## 🚀 Quick Start

### Step 1: Generare Calibration Table

Esegui backtest storico per generare la tabella di calibrazione:

```bash
# Backtest 6 mesi su 30 simboli (default)
python backtest_calibration.py

# Custom: 12 mesi su 50 simboli
python backtest_calibration.py --months 12 --symbols 50

# Veloce: 3 mesi su 20 simboli
python backtest_calibration.py --months 3 --symbols 20
```

**Output generato:**
- `confidence_calibration.json` - Tabella di calibrazione

**Tempo stimato:**
- 30 simboli × 6 mesi: ~1-2 ore
- 20 simboli × 3 mesi: ~30-45 minuti

### Step 2: Verifica Calibration

Il file `confidence_calibration.json` dovrebbe contenere:

```json
{
  "metadata": {
    "created": "2025-01-25T01:00:00",
    "total_trades": 487,
    "backtest_period": "2024-07-25 to 2025-01-25"
  },
  "xgb_calibration": [
    {
      "raw_range": [0.9, 1.0],
      "calibrated_value": 0.731,
      "samples": 45,
      "wins": 33,
      "losses": 12
    },
    ...
  ],
  "rl_calibration": [...]
}
```

### Step 3: Usa in Live Trading

La calibrazione viene applicata **automaticamente** quando esegui il bot:

```bash
python main.py
```

**Log di esempio:**
```
📊 Calibrazione caricata:
   Data creazione: 2025-01-25T01:00:00
   Trade analizzati: 487
   Periodo: 2024-07-25 to 2025-01-25

🎯 XGBoost raw: 0.95 → calibrated: 0.73
🤖 RL raw: 0.88 → calibrated: 0.71
```

---

## 📊 Come Funziona

### 1. Backtest Walk-Forward

```
[Candela #1] 2024-06-15 10:15
→ XGBoost analizza → 92% confidence
→ RL approva → 85% confidence
→ Trade aperto @ $67,250

[Candela #100] 2024-06-15 15:15
→ Prezzo scende → Hit trailing stop
→ Trade chiuso @ $62,190
→ SALVA: confidence=92%, result=LOSS

... ripeti per 6 mesi di dati storici ...
→ 500+ trade simulati
```

### 2. Analisi Statistica

```
Raggruppa per range confidence:

Range 90-100%: 45 trade
- 33 WIN, 12 LOSS
- Win rate: 73.3%
→ Confidence 95% = 73% reale

Range 80-90%: 120 trade
- 82 WIN, 38 LOSS  
- Win rate: 68.3%
→ Confidence 85% = 68% reale
```

### 3. Calibration Layer

```python
# In ml_predictor.py
raw_confidence = 0.95
calibrated = global_calibrator.calibrate_xgb_confidence(raw_confidence)
# → 0.73

# In rl_agent.py  
raw_confidence = 0.88
calibrated = global_calibrator.calibrate_rl_confidence(raw_confidence)
# → 0.71
```

---

## 🔧 Configurazione

### Parametri Backtest

In `backtest_calibration.py`:

```python
# Simboli da analizzare
--symbols 30  # Top 30 per volume

# Periodo storico
--months 6    # 6 mesi di dati

# Stop Loss/Trailing (da config.py)
SL_FIXED_PCT = 0.03              # 3% stop loss
TRAILING_TRIGGER_PCT = 0.015     # +1.5% trigger
TRAILING_DISTANCE_ROE = 0.10     # Proteggi 90% profit
```

### Calibration Ranges

In `core/confidence_calibrator.py`:

```python
ranges = [
    (0.90, 1.00),  # High confidence
    (0.80, 0.90),  # Medium-high
    (0.70, 0.80),  # Medium
    (0.60, 0.70),  # Medium-low
    (0.00, 0.60)   # Low
]
```

---

## 📈 Risultati Attesi

### Prima della Calibrazione
```
XGBoost: 95% confidence → apri trade
Risultato: Loss -3%
Sentiment: "Ma aveva detto 95%!" 😠
```

### Dopo la Calibrazione
```
XGBoost raw: 95%
Calibrated: 73% (3 trade su 10 andranno male)
Risultato: Loss -3%
Sentiment: "Era atteso, 73% non è garanzia" 😌
```

### Benefici
- ✅ **Confidence realistiche**: Riflettono performance reale
- ✅ **Gestione rischio migliore**: Aspettative corrette
- ✅ **No sorprese**: Sai che anche trade "sicuri" possono perdere
- ✅ **Adattativa**: Puoi ricalibrarla quando cambi parametri

---

## 🔄 Quando Ricalibrare

**Ricalibrare quando:**
1. Cambi stop loss da -3% a -2%
2. Cambi trailing trigger da +1.5% a +2%
3. Aggiungi/rimuovi timeframes
4. Modifichi soglie RL
5. Ogni 3-6 mesi per aggiornare con nuovi dati

**Come:**
```bash
# Ri-genera calibration table
python backtest_calibration.py --months 6
```

Il file `confidence_calibration.json` verrà sovrascritto automaticamente.

---

## 📝 File Creati/Modificati

### Nuovi File
1. **`core/confidence_calibrator.py`** - Modulo calibrazione
   - `ConfidenceCalibrator`: Classe per applicare calibrazione
   - `CalibrationAnalyzer`: Classe per generare tabella

2. **`backtest_calibration.py`** - Script backtest
   - Download dati storici
   - Walk-forward simulation
   - Trade management con SL/trailing
   - Generazione calibration table

3. **`CALIBRATION_README.md`** - Documentazione

### File Modificati
1. **`core/ml_predictor.py`**
   - Import `global_calibrator`
   - Calibration layer in `_ensemble_vote()`

2. **`core/rl_agent.py`**
   - Import `global_calibrator`
   - Calibration layer in `should_execute_signal()`

---

## 🐛 Troubleshooting

### Problema: "No calibration found"
**Soluzione:** Esegui prima `python backtest_calibration.py`

### Problema: "No trades completed"
**Possibili cause:**
- Periodo troppo breve (usa --months 6 minimo)
- Simboli insufficienti (usa --symbols 30 minimo)
- Modelli ML non trainati

**Soluzione:**
```bash
# 1. Verifica modelli esistano
ls trained_models/xgb_model_*.pkl

# 2. Se mancano, trainarli
python main.py  # Esegue training automatico

# 3. Poi rigenera calibrazione
python backtest_calibration.py --months 6 --symbols 30
```

### Problema: "Calibration ranges empty"
**Causa:** Pochi trade per range

**Soluzione:** Aumenta periodo o simboli:
```bash
python backtest_calibration.py --months 12 --symbols 50
```

---

## 📊 Monitoraggio

### Verifica Calibrazione Attiva

Quando avvii il bot, dovresti vedere:
```
📊 Calibrazione caricata:
   Data creazione: 2025-01-25T01:00:00
   Trade analizzati: 487
   Periodo: 2024-07-25 to 2025-01-25
```

Se vedi invece:
```
📝 Nessuna calibrazione trovata, usando confidence raw
```

Significa che devi generare la calibration table.

### Log Live Trading

Con calibrazione attiva:
```
🎯 XGBoost raw: 0.95 → calibrated: 0.73
🤖 RL raw: 0.88 → calibrated: 0.71
```

Senza calibrazione:
```
🎯 XGBoost confidence: 0.95
🤖 RL confidence: 0.88
```

---

## 🎯 Best Practices

1. **Prima calibrazione:** Usa almeno 6 mesi × 30 simboli
2. **Ricalibrare:** Ogni 3-6 mesi o dopo modifiche ai parametri
3. **Backtesting:** Verifica risultati prima di andare live
4. **Monitoring:** Controlla che calibrazione sia caricata all'avvio
5. **Backup:** Salva `confidence_calibration.json` prima di rigenerare

---

## 🚀 Next Steps

1. Genera la tua prima calibration table:
   ```bash
   python backtest_calibration.py
   ```

2. Verifica il file generato:
   ```bash
   cat confidence_calibration.json
   ```

3. Testa in live:
   ```bash
   python main.py
   ```

4. Monitora i log per vedere calibrazione in azione!

---

## 📚 Riferimenti

- **Confidence calibration theory:** [Platt Scaling](https://en.wikipedia.org/wiki/Platt_scaling)
- **Backtest methodology:** Walk-forward analysis
- **Statistical foundation:** Empirical win rate vs predicted probability

---

**Creato:** 2025-01-25  
**Versione:** 1.0  
**Autore:** Confidence Calibration System
