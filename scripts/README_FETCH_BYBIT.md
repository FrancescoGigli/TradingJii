# 📊 Script Fetch Bybit Closed Positions

## Descrizione

Script standalone per recuperare le ultime posizioni chiuse direttamente da Bybit e verificare l'allineamento con le statistiche locali.

## Installazione Dipendenze

Lo script usa le stesse dipendenze del bot:
```bash
pip install ccxt termcolor python-dotenv
```

## Uso Base

```bash
# Recupera ultime 20 posizioni (ultimi 7 giorni)
python scripts/fetch_bybit_closed_positions.py

# Recupera ultime 50 posizioni
python scripts/fetch_bybit_closed_positions.py --limit 50

# Recupera posizioni ultimi 30 giorni
python scripts/fetch_bybit_closed_positions.py --days 30

# Confronta con trade_history.json locale
python scripts/fetch_bybit_closed_positions.py --compare

# Esporta in JSON
python scripts/fetch_bybit_closed_positions.py --export

# Combinazione di opzioni
python scripts/fetch_bybit_closed_positions.py --limit 50 --days 14 --compare --export
```

## Output

### 1. Statistiche Generali
```
📈 STATISTICHE GENERALI:
   Totale posizioni: 15
   Vincite: 9 | Perdite: 6
   Win Rate: 60.0%
   PnL Totale: +$45.67
```

### 2. Dettagli per Posizione
Per ogni posizione chiusa mostra:
- ✅ Symbol e side (BUY/SELL)
- ✅ Entry e Exit price
- ✅ Quantità e leverage
- ✅ Notional e margin utilizzato
- ✅ PnL realizzato (USD e %)
- ✅ ROE %
- ✅ Timestamp apertura/chiusura
- ✅ Durata in minuti

### 3. Confronto con Locale (--compare)
```
🔍 CONFRONTO CON TRADE HISTORY LOCALE

📊 Trade locali chiusi: 12
📊 Trade Bybit recuperati: 15

STATISTICHE LOCALI:
   Win Rate: 58.3%
   PnL Totale: +$42.15

STATISTICHE BYBIT:
   Win Rate: 60.0%
   PnL Totale: +$45.67

✅ ALLINEAMENTO PERFETTO! Statistiche coerenti tra locale e Bybit
```

## Opzioni Disponibili

| Opzione | Tipo | Default | Descrizione |
|---------|------|---------|-------------|
| `--limit` | int | 20 | Numero massimo di posizioni da recuperare |
| `--days` | int | 7 | Giorni nel passato da cui cercare |
| `--compare` | flag | false | Confronta con trade_history.json locale |
| `--export` | flag | false | Esporta dati in bybit_closed_positions.json |

## Esempi Pratici

### Verifica Allineamento Giornaliero
```bash
python scripts/fetch_bybit_closed_positions.py --days 1 --compare
```
Verifica se i trade di oggi sono allineati con Bybit.

### Export Completo Settimanale
```bash
python scripts/fetch_bybit_closed_positions.py --days 7 --limit 100 --export
```
Esporta tutte le posizioni dell'ultima settimana in JSON.

### Check Rapido Performance
```bash
python scripts/fetch_bybit_closed_positions.py --limit 10
```
Mostra ultimi 10 trade per check rapido performance.

## Interpretazione Risultati

### ✅ Allineamento Perfetto
```
✅ ALLINEAMENTO PERFETTO! Statistiche coerenti tra locale e Bybit
```
- PnL diff < $1
- Win rate diff < 5%
- Sistema funziona correttamente

### ⚠️ Piccole Differenze
```
⚠️ Piccole differenze rilevate (probabilmente dovute a timing diverso)
   Diff PnL: $2.35
   Diff Win Rate: 3.2%
```
- Differenze minime accettabili
- Possono essere dovute a:
  - Timing diverso dei check
  - Arrotondamenti
  - Fee non ancora processate

### ❌ Differenze Significative
```
❌ ATTENZIONE: Differenze significative rilevate!
   Diff PnL: $15.00
   Diff Win Rate: 15.5%
```
- Possibili cause:
  - Logger attivato recentemente (trade precedenti non loggati)
  - Range temporale diverso
  - Bug nel logging (da investigare)

## File Output

### JSON Export (--export)
Crea `bybit_closed_positions.json`:
```json
{
  "fetched_at": "2025-01-18T09:50:00",
  "total_positions": 20,
  "positions": [
    {
      "symbol": "SOL/USDT:USDT",
      "side": "BUY",
      "entry_price": 145.234,
      "exit_price": 148.567,
      "realized_pnl": 12.45,
      "roe_pct": 8.59,
      "duration_minutes": 45.5,
      ...
    }
  ]
}
```

## Troubleshooting

### Errore: API key non trovate
```
❌ ERRORE: API key non trovate!
```
**Soluzione**: Verifica che `.env` contenga:
```
BYBIT_API_KEY=your_key
BYBIT_API_SECRET=your_secret
```

### Errore: Nessuna posizione chiusa trovata
```
📭 Nessuna posizione chiusa trovata
```
**Possibili cause**:
- Nessun trade nel periodo specificato
- Aumenta `--days` per cercare più indietro
- Aumenta `--limit` per vedere più posizioni

### Errore connessione Bybit
```
❌ Errore recuperando dati: Connection timeout
```
**Soluzione**:
- Verifica connessione internet
- Bybit potrebbe essere temporaneamente offline
- Riprova tra qualche minuto

## Best Practices

1. **Verifica Giornaliera**
   ```bash
   python scripts/fetch_bybit_closed_positions.py --days 1 --compare
   ```
   Run ogni giorno per verificare allineamento.

2. **Backup Settimanale**
   ```bash
   python scripts/fetch_bybit_closed_positions.py --days 7 --export
   ```
   Esporta dati settimanalmente per backup.

3. **Analisi Performance**
   ```bash
   python scripts/fetch_bybit_closed_positions.py --limit 50 --days 30
   ```
   Analizza performance dell'ultimo mese.

## Note

- Lo script è **read-only**: non modifica mai nulla su Bybit
- Usa le stesse credenziali del bot (da `.env`)
- Sicuro da eseguire mentre il bot è in esecuzione
- Non conta nei rate limits (usa cache quando possibile)
