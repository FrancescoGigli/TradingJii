# 📊 Backtest Trade Visualization System

## 🎯 Panoramica

Sistema completo per visualizzare graficamente i trade del backtest con grafici interattivi HTML.

---

## 🚀 Workflow Completo

### STEP 1: Esegui Backtest (genera dati)

```bash
python backtest_calibration.py --months 3
```

**Cosa fa:**
- Esegue backtest walk-forward su 30 simboli
- Genera `confidence_calibration.json` (calibration table)
- Genera `backtest_visualization_data.json` (dati per grafici)
- Tempo: ~20-30 minuti

**Output:**
```
📊 BACKTEST COMPLETED
Total trades: 3740
Win rate: 65.6%

✅ CALIBRATION GENERATION COMPLETE!
📁 Calibration file: confidence_calibration.json

📊 Visualization data saved: backtest_visualization_data.json
   Top 5 symbols: ['TIA/USDT:USDT', 'SOL/USDT:USDT', ...]
```

### STEP 2: Visualizza Calibration (statico)

```bash
python visualize_calibration.py
```

**Output:**
- Grafici calibration PNG
- Tabelle win rate per range confidence
- `visualizations/calibration_results.png`

### STEP 3: Visualizza Trade (interattivo) ✨

```bash
python visualize_backtest_trades.py
```

**Output:**
- Grafico HTML interattivo con candlestick
- Top 5 simboli con più trade
- Entry/Exit markers con confidence
- P&L annotations
- `visualizations/backtest_trades_interactive.html`

---

## 📊 Cosa Visualizza il Grafico Interattivo

### Per ogni simbolo (Top 5):

**1. Candlestick Chart**
- Prezzi OHLC della moneta
- Zoom e pan interattivi

**2. Entry Points** (triangolo verde ↑)
- Dove apri il trade
- Hover mostra:
  - Entry price
  - XGBoost confidence
  - RL confidence

**3. Exit Points** (triangolo ↓)
- Verde = WIN, Rosso = LOSS
- Hover mostra:
  - Exit price
  - P&L percentage
  - Durata trade (ore)

**4. Linee di Riferimento**
- **Blu tratteggiata**: Entry price
- **Rossa tratteggiata**: Stop Loss (-3%)

**5. Annotazioni P&L**
- Etichette colorate con P&L
- "+24.5%" (verde) per WIN
- "-32.1%" (rosso) per LOSS

---

## 🎨 Esempio Output HTML

```
📊 TIA/USDT:USDT (124 trades)
   ┌─────────────────────────────────┐
   │  Candlestick + Markers          │
   │  ↑ Entry (hover: XGB 75%, RL 65%)
   │  ↓ Exit (hover: +22.5% WIN)     │
   │  ━━━ Entry line                 │
   │  - - Stop Loss                  │
   └─────────────────────────────────┘

📊 SOL/USDT:USDT (98 trades)
   ┌─────────────────────────────────┐
   │  ...                            │
   └─────────────────────────────────┘

... (altri 3 simboli)
```

**Interattività:**
- 🔍 Zoom in/out
- 🖱️ Pan (trascina)
- ℹ️ Hover per dettagli
- 📸 Screenshot
- 💾 Download PNG

---

## 📁 File Generati

### Dal Backtest
1. **`confidence_calibration.json`**
   - Tabella calibrazione XGBoost/RL
   - Usata automaticamente in live trading

2. **`backtest_visualization_data.json`**
   - Top 5 simboli con dati candlestick
   - Trade details (entry, exit, confidence, P&L)
   - Formato JSON per elaborazione

### Dalle Visualizzazioni
1. **`visualizations/calibration_results.png`**
   - Grafici calibration statici (matplotlib)
   - Win rate per confidence range

2. **`visualizations/backtest_trades_interactive.html`**
   - Grafico interattivo trade (plotly)
   - Apribile in browser

---

## 🔄 Quando Rigenerare

### Devi rieseguire il backtest se:

1. **Cambi parametri trading** in `config.py`:
   ```python
   SL_FIXED_PCT = 0.02  # Modificato da 0.03
   TRAILING_TRIGGER_PCT = 0.02  # Modificato
   ```

2. **Cambi strategia ML/RL**:
   - Riaddestri modelli
   - Modifichi logica predizione

3. **Vuoi dati più recenti**:
   - Aggiungi più mesi di storia
   - Include nuovi simboli

### Workflow Re-calibrazione

```bash
# 1. Riesegui backtest (genera nuovi dati)
python backtest_calibration.py --months 6

# 2. Rigenera grafici calibration
python visualize_calibration.py

# 3. Rigenera grafici trade
python visualize_backtest_trades.py

# 4. Usa in live (carica automaticamente nuova calibration)
python main.py
```

---

## 💡 Tips

### Per grafici migliori:

**Più trade = grafici più ricchi:**
```bash
# Aumenta periodo backtest
python backtest_calibration.py --months 12

# Risultato: ~7000-8000 trade
# Top 5 avrà 200-300 trade ciascuno
```

**Verifica simboli inclusi:**
- Top 5 sono quelli con PIÙ trade
- Non necessariamente i più profittevoli
- Vedi TIA aveva 124 trade nel backtest precedente

**Browser consigliati:**
- Chrome/Edge: Migliore performance
- Firefox: Supporto completo
- Safari: Funziona ma più lento

---

## 🐛 Troubleshooting

### "File not found: backtest_visualization_data.json"

**Causa:** Backtest non eseguito o versione vecchia

**Soluzione:**
```bash
python backtest_calibration.py --months 3
```

### "No trades in visualization data"

**Causa:** Backtest non ha generato trade

**Soluzione:**
- Verifica modelli ML caricati
- Controlla log backtest per errori
- Assicurati RL filter non troppo restrittivo

### Grafico HTML non si apre

**Causa:** File troppo grande o browser issue
