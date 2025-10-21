# 📂 Scripts e Utility

Questa cartella contiene script di utility e strumenti di analisi per il bot di trading.

## 🔧 Script Disponibili

### `check_position_mode.py`
Utility diagnostica per verificare la modalità delle posizioni su Bybit.

**Utilizzo**:
```bash
python scripts/check_position_mode.py
```

### `test_tkinter_dashboard.py`
Script di test per verificare il funzionamento della dashboard PyQt6.

**Utilizzo**:
```bash
python scripts/test_tkinter_dashboard.py
```

### `view_complete_session.py`
Visualizza i dettagli completi di una sessione di trading, inclusi tutti i trade eseguiti.

**Utilizzo**:
```bash
python scripts/view_complete_session.py
```

**Output**: Mostra statistiche dettagliate della sessione, PnL per ogni posizione, win rate, ecc.

### `view_current_status.py`
Visualizza lo stato corrente del bot e delle posizioni attive.

**Utilizzo**:
```bash
python scripts/view_current_status.py
```

**Output**: 
- Posizioni attive
- Balance disponibile
- Margin utilizzato
- PnL unrealized

### `view_trade_decisions.py`
Visualizza le decisioni di trading registrate nel database, con dettagli su ML predictions e market context.

**Utilizzo**:
```bash
python scripts/view_trade_decisions.py
```

**Output**: Storico decisioni con:
- Segnali ML per timeframe
- Market context (volatilità, RSI, ADX)
- Confidence scores
- Risultati delle posizioni

## 📝 Note

Questi script sono utility standalone e NON sono necessari per il funzionamento del bot. Sono strumenti di analisi e debugging che possono essere eseguiti manualmente quando necessario.

Per eseguire il bot principale, usa invece:
```bash
python main.py
