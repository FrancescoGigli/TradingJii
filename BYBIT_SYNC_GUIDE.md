# 🔄 GUIDA SINCRONIZZAZIONE TRADE DA BYBIT

## 📊 Sistema Verificato di Recupero Trade

Questo sistema usa l'**endpoint corretto** di Bybit (`/v5/position/closed-pnl`) per recuperare i dati **REALI e VERIFICATI** delle posizioni chiuse.

---

## ✅ CAMPI VERIFICATI DA BYBIT

Il sistema usa questi campi che sono stati **verificati e corrispondono** ai dati mostrati nell'interfaccia Bybit:

- `closedPnl`: **Realized PnL** esatto
- `openFee`: Fee di apertura
- `closeFee`: Fee di chiusura  
- `avgEntryPrice`: Prezzo medio di entrata
- `avgExitPrice`: Prezzo medio di uscita
- `leverage`: Leva utilizzata
- `createdTime` / `updatedTime`: Timestamp precisi

---

## 🚀 UTILIZZO NEL CODICE

### 1. Sincronizzazione Manuale

```python
from core.trade_history_logger import global_trade_history_logger
import ccxt.async_support as ccxt

async def sync_trades():
    # Crea istanza exchange
    exchange = ccxt.bybit({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True
    })
    
    # Sincronizza trade chiusi (ultimi 7 giorni)
    result = await global_trade_history_logger.sync_closed_trades_from_bybit(
        exchange=exchange,
        days_back=7,  # Max 7 per Bybit
        limit=50      # Trade da recuperare
    )
    
    print(f"✅ Sincronizzati: {result['trades_updated']} aggiornati, {result['trades_created']} creati")
    
    await exchange.close()
```

### 2. Integrazione nel Main Loop

```python
# In main.py o trading_orchestrator.py
async def periodic_sync():
    """Sincronizza trade ogni ora"""
    while True:
        try:
            result = await global_trade_history_logger.sync_closed_trades_from_bybit(
                exchange=exchange,
                days_back=1,  # Solo ultimo giorno
                limit=20
            )
            logging.info(f"🔄 Sync: {result}")
        except Exception as e:
            logging.error(f"❌ Sync error: {e}")
        
        await asyncio.sleep(3600)  # Ogni ora
```

### 3. Sincronizzazione all'Avvio

```python
# All'avvio del bot
async def startup_sync():
    """Sincronizza trade all'avvio"""
    logging.info("🔄 Starting initial sync from Bybit...")
    
    result = await global_trade_history_logger.sync_closed_trades_from_bybit(
        exchange=exchange,
        days_back=7,
        limit=100
    )
    
    if result['success']:
        logging.info(
            f"✅ Initial sync completed: "
            f"{result['trades_found']} found, "
            f"{result['trades_updated']} updated, "
            f"{result['trades_created']} created"
        )
    else:
        logging.error(f"❌ Initial sync failed: {result.get('error')}")
```

---

## 📋 COSA FA IL SISTEMA

### Aggiornamento Trade Esistenti
Se trova un trade nel logger locale che corrisponde a uno di Bybit:
- ✅ Aggiorna `realized_pnl_usd` con il valore **REALE** da Bybit
- ✅ Aggiorna `open_fee` e `close_fee` con valori precisi
- ✅ Aggiorna prezzi entry/exit se diversi
- ✅ Ricalcola PnL%
- ✅ Marca il trade come `verified_by_bybit: true`

### Creazione Trade Retroattivi
Se trova trade chiusi su Bybit che non erano nel logger:
- 📝 Crea un nuovo record completo
- 📝 Marca come `origin: "BYBIT_SYNC"`
- 📝 Include una nota che indica il trade retroattivo

---

## 🎯 VANTAGGI

1. **Dati Reali**: Usa i valori esatti da Bybit, non calcolati
2. **Verificato**: Campi testati contro l'interfaccia Bybit
3. **Completo**: Include fee separate e PnL corretto
4. **Retroattivo**: Recupera anche trade precedenti
5. **Affidabile**: Gestisce errori API e limiti di Bybit

---

## ⚠️ LIMITI BYBIT

- **Max 7 giorni**: Bybit permette max 7 giorni di history
- **Rate Limit**: Rispetta i rate limit dell'API
- **Timestamp precisi**: Match dei trade basato su timestamp (±1 min)

---

## 📊 RISULTATO DELLA SINCRONIZZAZIONE

```python
{
    'success': True,
    'trades_found': 10,      # Trade trovati su Bybit
    'trades_updated': 5,     # Trade locali aggiornati
    'trades_created': 5,     # Trade retroattivi creati
    'error': None            # Errore se fallito
}
```

---

## 🔍 VERIFICA DEI DATI

Per verificare che i dati siano corretti:

```bash
# 1. Recupera da Bybit
python scripts/fetch_bybit_closed_positions.py --limit 5 --export

# 2. Sincronizza nel logger
# (esegui il codice di sync)

# 3. Visualizza i trade
python scripts/view_trade_history.py --status CLOSED

# 4. Confronta i valori di PnL
```

I valori dovrebbero corrispondere **esattamente** perché usano gli stessi campi verificati!

---

## ✅ ESEMPIO DI TRADE VERIFICATO

```json
{
  "trade_id": "BYBIT_db87043c-f2da-47ac-b37d-53d4064deedf",
  "symbol": "SOON/USDT:USDT",
  "side": "SELL",
  "entry_price": 1.23216927,
  "exit_price": 1.22572975,
  "leverage": 5.0,
  
  "realized_pnl_usd": -1.59722813,  // ← VALORE REALE DA BYBIT
  "open_fee": 0.13892709,            // ← FEE APERTURA REALE
  "close_fee": 0.13820104,           // ← FEE CHIUSURA REALE
  "total_fee": 0.27712813,           // ← TOTALE FEE
  
  "verified_by_bybit": true,         // ← MARCATO COME VERIFICATO
  "bybit_sync_time": "2025-11-18T12:27:00",
  "origin": "BYBIT_SYNC"
}
```

---

## 🎉 CONCLUSIONE

Questo sistema garantisce che i dati nel `trade_history.json` siano **sempre allineati** con i valori reali di Bybit, usando l'endpoint corretto e i campi verificati.

**Nessuna approssimazione, solo dati reali! ✅**
