# 📝 SISTEMA DI LOGGING TRADE HISTORY

## Panoramica

Il sistema registra automaticamente **tutti i trade** (aperti e chiusi) in un file JSON con tutti i dettagli recuperati da Bybit ogni 30 secondi durante il sync.

## File Creato

📁 **Percorso**: `data_cache/trade_history.json`

Il file viene creato automaticamente al primo avvio del bot se non esiste.

## Dati Registrati

### All'Apertura del Trade
- ✅ Trade ID univoco
- ✅ Symbol (e versione short)
- ✅ Timestamp apertura (ISO format + Unix timestamp)
- ✅ Lato (BUY/SELL)
- ✅ Prezzo entry
- ✅ Position size (contracts e USD value)
- ✅ Leva utilizzata
- ✅ Initial Margin reale
- ✅ Stop Loss impostato
- ✅ Take Profit (se presente)
- ✅ Confidence del signal ML
- ✅ Origine (BOT o SYNCED)
- ✅ Fee di apertura (se disponibile da Bybit)

### Alla Chiusura del Trade
- ✅ Timestamp chiusura (ISO format + Unix timestamp)
- ✅ Prezzo exit
- ✅ PnL realizzato in USD (da Bybit, include TUTTE le fee)
- ✅ PnL realizzato in % (calcolato sul margin)
- ✅ Fee di chiusura (da Bybit)
- ✅ Durata in minuti
- ✅ Motivo chiusura (STOP_LOSS, MANUAL, SYNC_CLOSED, etc.)
- ✅ Fee totali (apertura + chiusura)

## Esempio Struttura JSON

```json
{
  "trades": [
    {
      "trade_id": "SOLUSDT_20250117_090245_123456",
      "symbol": "SOL/USDT:USDT",
      "symbol_short": "SOLUSDT",
      "status": "OPEN",
      
      "open_time": "2025-01-17T09:02:45.123456",
      "open_timestamp": 1737097365.123456,
      
      "side": "BUY",
      "entry_price": 145.234,
      "position_size": 1450.00,
      "contracts": 9.9876,
      
      "leverage": 10,
      "initial_margin": 145.00,
      
      "stop_loss": 137.972,
      "take_profit": null,
      
      "confidence": 0.85,
      "origin": "BOT",
      "open_fee": 0.087,
      
      "close_time": null,
      "close_timestamp": null,
      "exit_price": null,
      "close_fee": null,
      "realized_pnl_usd": null,
      "realized_pnl_pct": null,
      "close_reason": null,
      "duration_minutes": null,
      "total_fee": null,
      
      "logged_at": "2025-01-17T09:02:45.234567"
    },
    {
      "trade_id": "ETHUSDT_20250117_083012_654321",
      "symbol": "ETH/USDT:USDT",
      "symbol_short": "ETHUSDT",
      "status": "CLOSED",
      
      "open_time": "2025-01-17T08:30:12.654321",
      "open_timestamp": 1737095412.654321,
      
      "side": "SELL",
      "entry_price": 3245.67,
      "position_size": 3245.67,
      "contracts": 1.0,
      
      "leverage": 10,
      "initial_margin": 324.57,
      
      "stop_loss": 3408.96,
      "take_profit": null,
      
      "confidence": 0.78,
      "origin": "BOT",
      "open_fee": 0.195,
      
      "close_time": "2025-01-17T09:15:30.123456",
      "close_timestamp": 1737098130.123456,
      "exit_price": 3180.45,
      "close_fee": 0.191,
      "realized_pnl_usd": 18.23,
      "realized_pnl_pct": 5.62,
      "close_reason": "SYNC_CLOSED",
      "duration_minutes": 45.30,
      "total_fee": 0.386,
      
      "logged_at": "2025-01-17T08:30:12.765432",
      "closed_at": "2025-01-17T09:15:30.234567",
      
      "bybit_raw_close": {
        "id": "order_123456",
        "price": 3180.45,
        "info": {
          "realizedPnl": "18.23",
          "execFee": "0.191"
        }
      }
    }
  ],
  "metadata": {
    "created": "2025-01-17T08:00:00.000000",
    "last_updated": "2025-01-17T09:15:30.345678",
    "version": "1.0",
    "total_trades": 2,
    "open_trades": 1,
    "closed_trades": 1
  }
}
```

## Come Funziona

### 1. Apertura Trade
Quando un trade viene aperto (sia dal bot che sincronizzato da Bybit), viene automaticamente registrato:

- **Apertura diretta dal bot** → `core/trading_orchestrator.py` chiama `log_trade_opened_from_position()`
- **Sincronizzazione da Bybit** → `core/position_management/position_sync.py` chiama `log_trade_opened_from_position()`

### 2. Check Periodici (ogni 30s)
Durante il sync con Bybit:
- Il bot rileva nuove posizioni aperte → vengono loggate
- Il bot rileva posizioni chiuse → i record vengono aggiornati con dati di chiusura

### 3. Chiusura Trade
Quando un trade viene chiuso:
- Il bot recupera i dati REALI da Bybit (trade history)
- Include PnL realizzato con TUTTE le fee (open + close + funding)
- Aggiorna il record con timestamp, exit price, PnL, fee, e motivo

### 4. Trade Retroattivi
Se il bot trova un trade chiuso che non era stato loggato in apertura (es. bot riavviato):
- Crea un record retroattivo con tutti i dati disponibili
- Marca come `"origin": "RETROACTIVE"` per tracciabilità

## Accesso ai Dati

### File JSON Diretto
```python
import json

# Leggi il file
with open('data_cache/trade_history.json', 'r') as f:
    data = json.load(f)

# Ottieni tutti i trade
all_trades = data['trades']

# Filtra trade aperti
open_trades = [t for t in all_trades if t['status'] == 'OPEN']

# Filtra trade chiusi
closed_trades = [t for t in all_trades if t['status'] == 'CLOSED']

# Calcola PnL totale
total_pnl = sum(t['realized_pnl_usd'] for t in closed_trades if t['realized_pnl_usd'])
```

### API del Logger
```python
from core.trade_history_logger import global_trade_history_logger

# Ottieni statistiche
stats = global_trade_history_logger.get_stats()
print(f"Total trades: {stats['total_trades']}")
print(f"Win rate: {stats['win_rate']:.1f}%")
print(f"Total PnL: ${stats['total_pnl']:.2f}")
```

## Caratteristiche

### ✅ Thread-Safe
Il logger usa lock per garantire scritture sicure anche con accessi concorrenti.

### ✅ Dati Accurati da Bybit
- PnL realizzato include TUTTE le fee (trading + funding)
- Timestamp reali di apertura/chiusura
- Prezzi esatti di entry/exit

### ✅ Gestione Errori
- Se non riesce a recuperare dati da Bybit, usa fallback calcolati
- Log chiari di cosa è stato recuperato vs calcolato

### ✅ Formato Leggibile
- JSON indentato e formattato
- Timestamp sia ISO che Unix per facile parsing
- Metadata automatici con statistiche

## Monitoraggio

Il logger produce log informativi:

```
📝 TRADE OPENED logged: SOLUSDT 🟢 Entry: $145.234000 | Margin: $145.00 | Lev: 10x
📝 TRADE CLOSED logged: ETHUSDT | Exit: $3180.450000 | PnL: +5.62% ($18.23) | Reason: SYNC_CLOSED
```

## Best Practices

1. **Backup Periodico**: Il file JSON contiene dati preziosi, fai backup regolari
2. **Analisi Post-Trading**: Usa i dati per analizzare performance e pattern
3. **Verifica Accuratezza**: Confronta con Bybit periodicamente
4. **Non Modificare Manualmente**: Lascia che il sistema gestisca il file

## Troubleshooting

### File Non Creato
- Il bot deve essere avviato almeno una volta
- Verifica permessi scrittura su `data_cache/`

### Dati Mancanti
- Trade precedenti all'attivazione non saranno loggati
- Solo trade futuri verranno tracciati

### PnL Non Accurato
- Se "bybit_raw_close" è null, il PnL è calcolato (non include fee)
- Se presente, il PnL è da Bybit (accurato al 100%)

## Integrazione Futura

Il file JSON può essere usato per:
- 📊 Dashboard personalizzate
- 📈 Analisi ML delle performance
- 💾 Database relazionale (import in PostgreSQL/MySQL)
- 📧 Report automatici via email
- 🔔 Alert su Telegram/Discord
- 📉 Grafici con matplotlib/plotly

## Versioning

**Versione Corrente**: 1.0
- Sistema completo di logging
- Integrazione con position sync
- Recupero dati da Bybit trade history
