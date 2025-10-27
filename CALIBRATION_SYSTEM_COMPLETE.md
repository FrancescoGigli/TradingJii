# 🎯 Sistema di Calibrazione Confidence - Implementazione Completa

## 📋 Panoramica

Sistema completo per calibrare le confidence ML/RL basato su risultati reali di backtest storico.

---

## 🎨 File Implementati

### 1. **`core/confidence_calibrator.py`**
**Modulo principale calibrazione**
- `ConfidenceCalibrator`: Applica calibrazione via lookup table
- `CalibrationAnalyzer`: Genera tabella da risultati backtest
- `global_calibrator`: Istanza globale ready-to-use

**Funzioni chiave:**
```python
# Calibra confidence XGBoost
calibrated = global_calibrator.calibrate_xgb_confidence(raw_confidence)

# Calibra confidence RL
calibrated = global_calibrator.calibrate_rl_confidence(raw_confidence)
```

### 2. **`backtest_calibration.py`**
**Script backtest walk-forward con progress bar**

**Features:**
- ✅ Usa stesse monete del main.py (MarketAnalyzer)
- ✅ Walk-forward simulation candela per candela
- ✅ SL/Trailing identici al live (da config.py)
- ✅ Progress bar visiva con tqdm
- ✅ Tracking confidence + risultati
- ✅ Windows event loop policy fix

**Utilizzo:**
```bash
# Standard: 6 mesi, usa TOP_ANALYSIS_CRYPTO
python backtest_calibration.py --months 6

# Veloce: 3 mesi
python backtest_calibration.py --months 3

# Lungo: 12 mesi
python backtest_calibration.py --months 12
```

**Output:**
- `confidence_calibration.json` - Tabella calibrazione

### 3. **`visualize_calibration.py`**
**Visualizzatore grafici risultati**

**Features:**
- 📊 4 grafici interattivi
- 📈 XGBoost calibration chart
- 📉 Trade distribution
- 🤖 RL calibration chart
- 📝 Summary statistics

**Utilizzo:**
```bash
python visualize_calibration.py
```

**Output:**
- `visualizations/calibration_results.png`
- Tabelle testuali nel terminale

---

## 🔧 Integrazione nel Bot

### Modifiche Automatiche

**`core/ml_predictor.py`:**
```python
# Import aggiunto
from core.confidence_calibrator import global_calibrator

# In _ensemble_vote():
raw_confidence = ensemble_confidence
ensemble_confidence = global_calibrator.calibrate_xgb_confidence(raw_confidence)
```

**`core/rl_agent.py`:**
```python
# Import aggiunto  
from core.confidence_calibrator import global_calibrator

# In should_execute_signal():
raw_execution_prob = self.model(state_tensor).item()
execution_prob = global_calibrator.calibrate_rl_confidence(raw_execution_prob)
```

### Attivazione

La calibrazione si attiva **automaticamente** se esiste `confidence_calibration.json`:

```
✅ Se file esiste:
   📊 Calibrazione caricata e applicata

❌ Se file NON esiste:
   📝 Usa confidence raw (fallback graceful)
```

---

## 🚀 Workflow Completo

### STEP 1: Genera Calibration Table

```bash
# Prima volta: backtest completo
python backtest_calibration.py --months 6

# Tempo: 30-60 minuti (50 simboli × 6 mesi)
# Output: confidence_calibration.json
```

**Output terminale:**
```
📊 Processing Symbols: 100%|████████| 50/50 [30:15<00:00, 36.31s/symbol]

📊 BACKTEST COMPLETED
Total trades completed: 487
Win rate: 58.3% (284W/203L)
Average PnL: +1.24%

✅ CALIBRATION GENERATION COMPLETE!
📁 Calibration file: confidence_calibration.json
```

### STEP 2: Visualizza Risultati

```bash
python visualize_calibration.py
```

**Output:**
- Grafici interattivi
- Tabelle calibrazione
- `visualizations/calibration_results.png`

### STEP 3: Usa in Live Trading

```bash
python main.py
```

**Log avvio:**
```
📊 Calibrazione caricata:
   Data creazione: 2025-01-25T01:00:00
   Trade analizzati: 487
   Periodo: 2024-07-25 to 2025-01-25
```

**Log durante trading:**
```
🎯 XGBoost raw: 0.95 → calibrated: 0.73
🤖 RL raw: 0.88 → calibrated: 0.71
```

---

## 📊 Esempio Risultati

### Calibration Table Tipica

```
XGBoost Calibration:
Range         Raw Mid    Calibrated    Samples    Win Rate
90-100%        95.0%       73.3%         45       73.3% (33W/12L)
80-90%         85.0%       68.3%        120       68.3% (82W/38L)
70-80%         75.0%       61.1%        180       61.1% (110W/70L)
60-70%         65.0%       51.6%         95       51.6% (49W/46L)
0-60%          30.0%       45.0%         60       45.0% (27W/33L)
```

### Interpretazione

**Range 90-100% (High Confidence):**
- Modello dice: "95% sicuro"
- Realtà storica: 73% win rate
- Significa: ~3 su 10 trade andranno male
- **Conclusione**: Modello overconfident del 22%

**Range 60-70% (Medium Confidence):**
- Modello dice: "65% sicuro"
- Realtà storica: 52% win rate
- Significa: praticamente 50/50
- **Conclusione**: Segnali deboli, valutare skip

---

## 🔄 Quando Ricalibrare

### Trigger Ricalibrazio ne

1. **Cambi parametri trading:**
   - Stop loss: -3% → -2%
   - Trailing: +1.5% → +2%
   - Timeframes: Aggiungi/rimuovi

2. **Periodicamente:**
   - Ogni 3-6 mesi
   - Dopo 500+ trade live
   - Market regime change

3. **Performance deviation:**
   - Win rate live ≠ calibrated
   - Confidence non accurate

### Come Ricalibrare

```bash
# 1. Rigenera calibration table
python backtest_calibration.py --months 6

# 2. Verifica nuovi risultati
python visualize_calibration.py

# 3. Backup vecchia calibrazione (opzionale)
cp confidence_calibration.json confidence_calibration_backup.json

# 4. Usa nuova calibrazione
python main.py
```

---

## 🎯 Benefici Sistema

### Prima della Calibrazione
```
XGBoost: 95% confidence
User expectation: "Quasi certezza!"
Result: LOSS -3%
Sentiment: 😠 "Ma aveva detto 95%!"
```

### Dopo la Calibrazione
```
XGBoost raw: 95%
Calibrated: 73% (basato su 45 trade storici)
User expectation: "73% = 3 su 10 andranno male"
Result: LOSS -3%
Sentiment: 😌 "Era atteso, 73% non è garanzia"
```

### Vantaggi Concreti

1. **Aspettative realistiche** - Sai esattamente il win rate atteso
2. **Gestione rischio** - Position sizing basato su probabilità reali
3. **No overtrading** - Skippa segnali con confidence calibrata bassa
4. **Stress ridotto** - Accetti loss come parte della strategia
5. **Adattativo** - Si aggiorna con nuovi dati

---

## 📚 File di Supporto

### `CALIBRATION_README.md`
Documentazione dettagliata con:
- Quick start guide
- How it works
- Configuration
- Troubleshooting
- Best practices

---

## 🐛 Troubleshooting

### "No calibration found"
```bash
# Soluzione: Genera calibration table
python backtest_calibration.py --months 6
```

### "No trades completed"
```bash
# Possibile causa: Periodo troppo breve
python backtest_calibration.py --months 12

# O: Più simboli
# Modifica config.py: TOP_ANALYSIS_CRYPTO = 100
```

### "QWidget error"
```bash
# Fixed: Usa MarketAnalyzer invece di TradingEngine
# (Già implementato nella versione corrente)
```

### "aiodns error on Windows"
```bash
# Fixed: Windows event loop policy
# (Già implementato nella versione corrente)
```

---

## 🎉 Sistema Completo

**Files implementati:** 3 nuovi + 2 modificati
