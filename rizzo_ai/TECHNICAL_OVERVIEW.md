# Documentazione Tecnica – Trading Agent

## 1. Introduzione

Questo documento descrive in modo tecnico e dettagliato il funzionamento del progetto **Trading Agent**.

L’obiettivo del sistema è costruire un **agente di trading automatizzato** che:

- raccoglie dati di mercato e metadati da **Hyperliquid** (prezzi, volumi, orderbook, parametri di trading);
- effettua **analisi tecnica** su timeframe a 15 minuti (e giornaliero per i pivot);
- integra **news**, **sentiment di mercato** (Fear & Greed Index) e **previsioni di prezzo** a breve termine tramite **Prophet**;
- costruisce un **prompt strutturato** per un modello LLM (OpenAI), includendo portfolio corrente, segnali di mercato e contesto macro;
- riceve dal LLM una decisione di trading in formato JSON rigidamente definito;
- converte tale decisione in operazioni reali su Hyperliquid (apertura/chiusura/hold di posizioni);
- salva su **PostgreSQL** tutti i dettagli dell’esecuzione (stato dell’account, contesto usato per l’LLM, decisione finale, errori) per audit, analisi e miglioramento futuro.

Il file di ingresso principale in produzione è **`main.py`**, come specificato in `railway.json`.


## 2. Architettura ad alto livello

A livello logico, l’architettura è suddivisa in più layer:

1. **Layer di dati esterni**
   - Hyperliquid: dati OHLCV, orderbook, metadati su simboli, stato account, esecuzione ordini.
   - CoinJournal RSS: news crypto in tempo (quasi) reale.
   - CoinMarketCap: Fear & Greed Index (sentiment di mercato).
   - Whale Alert: movimenti di grandi quantità di crypto (modulo già pronto ma opzionale nel prompt principale).
   - Prophet (modello locale): forecasting a breve termine sui prezzi.

2. **Layer di analisi**
   - `indicators.py`: analisi tecnica multi‑ticker con indicatori (EMA, MACD, RSI, ATR, Pivot Points) e volumi orderbook.
   - `forecaster.py`: previsioni 15m / 1h con Prophet.
   - `sentiment.py`: sentiment Fear & Greed da CoinMarketCap.
   - `news_feed.py`: ingestion e normalizzazione del feed RSS di CoinJournal.
   - `whalealert.py`: trasformazione degli alert raw in testi leggibili.

3. **Layer decisionale (LLM)**
   - `system_prompt.txt`: template del prompt di sistema che descrive il ruolo dell’agente e le regole di output.
   - `trading_agent.py`: wrapper verso l’API OpenAI (modello `gpt-5.1`) con schema JSON rigidamente applicato.

4. **Layer esecuzione ordini**
   - `hyperliquid_trader.py`: adapter verso l’SDK `hyperliquid-python-sdk`, gestione leva, calcolo size, apertura/chiusura posizioni e lettura dello stato dell’account.

5. **Layer persistenza**
   - `db_utils.py`: gestione schema PostgreSQL e funzioni di logging per snapshot account, contesti LLM, operazioni del bot, errori.

6. **Layer orchestrazione**
   - `main.py`: orchestratore principale che compone tutti i layer precedenti in un flusso di esecuzione end‑to‑end.
   - `test_trading.py`: script di test manuale focalizzato su Hyperliquid.


## 3. Flusso di esecuzione end‑to‑end

Questa sezione descrive una singola esecuzione tipica del bot a partire da `main.py`.

### 3.1 Caricamento configurazione e inizializzazione trader

File: **`main.py`**

1. Carica variabili d’ambiente con `dotenv`:
   - `PRIVATE_KEY`: chiave privata per firmare operazioni Hyperliquid.
   - `WALLET_ADDRESS`: indirizzo wallet associato.

2. Configura modalità testnet/mainnet:
   ```python
   TESTNET = True   # True = testnet, False = mainnet
   VERBOSE = True   # stampa info extra
   ```

3. Valida che `PRIVATE_KEY` e `WALLET_ADDRESS` siano presenti; in caso contrario solleva `RuntimeError`.

4. Inizializza il trader HL:
   ```python
   bot = HyperLiquidTrader(
       secret_key=PRIVATE_KEY,
       account_address=WALLET_ADDRESS,
       testnet=TESTNET,
   )
   ```

### 3.2 Raccolta dati di mercato e contesto

1. Definisce i ticker da analizzare:
   ```python
   tickers = ['BTC', 'ETH', 'SOL']
   ```

2. **Analisi tecnica multi‑ticker** – `indicators.py`:
   ```python
   indicators_txt, indicators_json = analyze_multiple_tickers(tickers)
   ```
   - `indicators_txt`: stringa testuale formattata per il prompt (sezioni `<BTC_data>`, `<ETH_data>`, ecc.).
   - `indicators_json`: lista di dizionari strutturati con tutti i dettagli tecnici per ogni ticker.

3. **News** – `news_feed.py`:
   ```python
   news_txt = fetch_latest_news()
   ```
   - testo multilinea con righe del tipo
     `YYYY-MM-DD HH:MM:SSZ | Titolo: descrizione...`.

4. **Sentiment** – `sentiment.py`:
   ```python
   sentiment_txt, sentiment_json = get_sentiment()
   ```
   - `sentiment_txt`: stringa formattata con valore, classificazione, timestamp.
   - `sentiment_json`: dizionario con chiavi come `valore`, `classificazione`, `timestamp`.

5. **Forecast** – `forecaster.py`:
   ```python
   forecasts_txt, forecasts_json = get_crypto_forecasts()
   ```
   - `forecasts_txt`: tabella ASCII con colonne `Ticker`, `Timeframe`, `Ultimo Prezzo`, `Previsione`, `Limite Inferiore`, `Limite Superiore`, `Variazione %`, `Timestamp Previsione`.
   - `forecasts_json`: JSON serializzato (lista di record) usato per persistenza.

6. **Costruzione blocco contesto per il prompt**:
   ```python
   msg_info = f"""<indicatori>\n{indicators_txt}\n</indicatori>\n\n
    <news>\n{news_txt}</news>\n\n
    <sentiment>\n{sentiment_txt}\n</sentiment>\n\n
    <forecast>\n{forecasts_txt}\n</forecast>\n\n"""
   ```

Il contesto è incapsulato in tag XML‑like (`<indicatori>`, `<news>`, `<sentiment>`, `<forecast>`) per rendere più robusto il parsing lato LLM e per aumentare la leggibilità.

> Nota: il modulo `whalealert.py` è pronto per essere integrato come ulteriore blocco (es. `<whalealerts>`), ma nel codice corrente la chiamata è commentata.

### 3.3 Stato account e snapshot DB

1. Lettura stato account tramite `HyperLiquidTrader`:
   ```python
   account_status = bot.get_account_status()
   portfolio_data = f"{json.dumps(account_status)}"
   ```
   - `account_status` è un dict con chiavi:
     - `balance_usd`: saldo totale in USD.
     - `open_positions`: lista di posizioni aperte, ciascuna con `symbol`, `side`, `size`, `entry_price`, `mark_price`, `pnl_usd`, `leverage`.

2. Logging snapshot su DB – `db_utils.log_account_status`:
   ```python
   snapshot_id = db_utils.log_account_status(account_status)
   ```
   - crea una riga in `account_snapshots` e righe associate in `open_positions`.

### 3.4 Costruzione del prompt LLM

1. Carica il template da `system_prompt.txt`:
   ```python
   with open('system_prompt.txt', 'r') as f:
       system_prompt = f.read()
   ```

2. Effettua `.format(portfolio_data, msg_info)`:
   - il template contiene due `{}` che vengono sostituiti rispettivamente con:
     1. JSON dello stato dell’account (`portfolio_data`)
     2. contesto strutturato (`msg_info`)

Il risultato è un **prompt completo** che descrive:

- il ruolo dell’agente: *“You are a cryptocurrency trading AI...”*;
- il portfolio attuale (bilancio, posizioni aperte);
- il contesto informazioni (indicatori, news, sentiment, forecast);
- le **regole** su come decidere e su come formattare l’output (solo JSON con vincoli precisi).

### 3.5 Chiamata all’agente di trading (LLM)

Modulo: **`trading_agent.py`**, funzione `previsione_trading_agent(prompt)`.

1. Utilizza l’SDK OpenAI (`OpenAI`) con API key letta da variabile d’ambiente `OPENAI_API_KEY`.

2. Chiama `client.responses.create(...)` con:
   - `model="gpt-5.1"`;
   - `input=prompt` (stringa lunga costruita in `main.py`);
   - blocco `text.format` che definisce una **JSON Schema** per l’output del modello:
     - campi obbligatori: `operation`, `symbol`, `direction`, `target_portion_of_balance`, `leverage`, `reason`;
     - enumerazioni controllate per `operation` (open/close/hold), `symbol` (BTC/ETH/SOL), `direction` (long/short);
     - limiti numerici su `target_portion_of_balance` (0‑1) e `leverage` (1‑10);
     - `additionalProperties=False` per evitare chiavi extra.

3. Il metodo ritorna un oggetto risposta; `response.output_text` contiene l’oggetto JSON in stringa.

4. `previsione_trading_agent` fa `json.loads(response.output_text)` e restituisce un dizionario Python.

### 3.6 Esecuzione dell’ordine su Hyperliquid

1. In `main.py`:
   ```python
   out = previsione_trading_agent(system_prompt)
   bot.execute_signal(out)
   ```

2. `execute_signal(order_json)` in `hyperliquid_trader.py`:

   - Valida i campi tramite `_validate_order_input` (seconda barriera oltre al JSON Schema).
   - Estrae:
     - `op = order_json["operation"]`
     - `symbol = order_json["symbol"]`
     - `direction = order_json["direction"]`
     - `portion = Decimal(str(order_json["target_portion_of_balance"]))`
     - `leverage = int(order_json.get("leverage", 1))`

   - Gestione casi:
     - **`hold`**: logga e ritorna struttura `{"status": "hold", ...}` senza chiamare l’API.
     - **`close`**: chiama `self.exchange.market_close(symbol)`.
     - **`open`**:
       1. **Imposta la leva** desiderata tramite `set_leverage_for_symbol(symbol, leverage, is_cross=True)`.
       2. Attende 0.5 secondi per evitare race conditions.
       3. Recupera lo **user state** via `self.info.user_state(self.account_address)` e calcola `balance_usd` dall’`accountValue`.
       4. Calcola `notional = balance_usd * portion * leverage`.
       5. Recupera prezzi mid via `self.info.all_mids()` e `mark_px = mids[symbol]`.
       6. Calcola `raw_size = notional / mark_px`.
       7. Recupera i metadati del simbolo da `self.meta["universe"]` (min size `minSz`, decimali `szDecimals`, `maxLeverage`, ...).
       8. Verifica se la leva richiesta supera `maxLeverage` e, in tal caso, logga un warning.
       9. Arrotonda la size a `szDecimals` decimali, rispettando fino a 8 decimali e assicurando che non scenda sotto `minSz` (in tal caso usa `minSz`).
       10. Determina se l’ordine è `BUY` (long) o `SELL` (short).
       11. Chiama `self.exchange.market_open(symbol, is_buy, size_float, None, 0.01)`.

### 3.7 Logging dell’operazione e contesto

Dopo l’esecuzione, `main.py` logga il tutto su DB:

```python
op_id = db_utils.log_bot_operation(
    out,
    system_prompt=system_prompt,
    indicators=indicators_json,
    news_text=news_txt,
    sentiment=sentiment_json,
    forecasts=forecasts_json,
)
```

- `log_bot_operation` crea:
  - un record in `ai_contexts` (contenente il prompt intero);
  - record in `indicators_contexts` per ogni ticker;
  - record in `news_contexts`, `sentiment_contexts`, `forecasts_contexts` se i relativi dati sono presenti;
  - una riga in `bot_operations` con i campi chiave dell’ordine e il JSON completo della decisione.

### 3.8 Gestione errori globali

Tutto il blocco principale di `main.py` è racchiuso in un `try/except`. In caso di eccezione:

- `db_utils.log_error(e, context={...}, source="trading_agent")` registra:
  - tipo di errore, messaggio, traceback
  - contesto: prompt, indicatori, news, sentiment, forecast, balance
  - eventuale sorgente (qui `trading_agent`).


## 4. Dettaglio moduli e funzioni

### 4.1 `main.py`

**Responsabilità:** orchestrazione principale e gestione di un ciclo di decisione.

Funzioni / logica principale:

- Setup Hyperliquid (`HyperLiquidTrader`).
- Calcolo indicatori multi‑ticker (`analyze_multiple_tickers`).
- Lettura news (`fetch_latest_news`).
- Lettura sentiment (`get_sentiment`).
- Lettura forecast (`get_crypto_forecasts`).
- Composizione del prompt (`system_prompt.txt`).
- Chiamata al LLM (`previsione_trading_agent`).
- Esecuzione dell’ordine (`execute_signal`).
- Logging su DB (`log_account_status`, `log_bot_operation`).
- Logging errori globali (`log_error`).

### 4.2 `trading_agent.py`

**Responsabilità:** incapsulare la chiamata all’API OpenAI e forzare il formato JSON dell’output.

Elementi chiave:

- Lettura `OPENAI_API_KEY` da `.env`.
- Istanziamento client `OpenAI`.

Funzione:

- `previsione_trading_agent(prompt: str) -> dict`:
  - input: stringa con system prompt + contesto;
  - output: dizionario Python con chiavi
    `operation`, `symbol`, `direction`, `target_portion_of_balance`, `leverage`, `reason`.

### 4.3 `hyperliquid_trader.py`

**Responsabilità:** adapter tra decisioni LLM (JSON) e ordini reali su Hyperliquid.

Classe: `HyperLiquidTrader`.

Metodi principali:

- `__init__(secret_key, account_address, testnet=True, skip_ws=True)`
  - Imposta `Info` e `Exchange` dell’SDK.
  - Recupera meta‑informazioni via `self.info.meta()`.

- `_validate_order_input(order_json)`
  - Verifica coerenza di base dei parametri.

- `get_current_leverage(symbol)` / `set_leverage_for_symbol(symbol, leverage, is_cross=True)`
  - Gestione e monitoraggio leva corrente per ogni simbolo.

- `execute_signal(order_json)`
  - Interpreta l’oggetto JSON generato dal LLM e chiama le API HL appropriate.

- `get_account_status() -> Dict[str, Any]`
  - Mappa `user_state` in una struttura semplificata per il resto del sistema.

- `debug_symbol_limits(symbol: str = None)`
  - Esplora la meta per identificare `minSz`, `szDecimals`, `pxDecimals`, `maxLeverage`, ecc.

### 4.4 `indicators.py`

**Responsabilità:** calcolo di indicatori tecnici e composizione di output strutturati per LLM e DB.

Classe: `CryptoTechnicalAnalysisHL`.

Metodi principali:

- `get_orderbook_volume(ticker: str) -> str`
  - Somma volumi bid/ask dal livello 2 dell’orderbook.

- `fetch_ohlcv(coin: str, interval: str, limit: int) -> pd.DataFrame`
  - Recupera dati OHLCV da Hyperliquid.

- `calculate_ema`, `calculate_macd`, `calculate_rsi`, `calculate_atr`, `calculate_pivot_points`
  - Wrapper sugli indicatori della libreria `ta` e logica pivot.

- `get_complete_analysis(ticker: str) -> dict`
  - Costruisce una vista complessiva per il ticker (current, intraday, longer_term, pivot, derivatives).

- `format_output(data: Dict) -> str`
  - Trasforma il dict in testo formattato per il prompt.

Funzione di livello modulo:

- `analyze_multiple_tickers(tickers: List[str], testnet: bool = True) -> Tuple[str, List[Dict]]`
  - Esegue `get_complete_analysis` e `format_output` per ciascun ticker;
  - ritorna stringa aggregata e lista di dict.

### 4.5 `forecaster.py`

**Responsabilità:** forecasting di breve termine con Prophet.

Classe: `HyperliquidForecaster`.

Metodi principali:

- `_fetch_candles(coin: str, interval: str, limit: int) -> pd.DataFrame`
  - Prepara dati in formato compatibile con Prophet (`ds`, `y`).

- `forecast(coin: str, interval: str) -> (pd.DataFrame, float)`
  - Addestra Prophet e produce l’ultima previsione + ultimo prezzo.

- `forecast_many(tickers: list, intervals=("15m", "1h")) -> List[Dict]`
  - Genera previsioni multi‑ticker / multi‑timeframe.

- `get_crypto_forecasts(...)`: wrapper di alto livello usato da `main.py`.

### 4.6 `sentiment.py`

**Responsabilità:** recuperare il Fear & Greed Index da CoinMarketCap e trasformarlo in formato testuale/JSON.

Funzioni:

- `get_latest_fear_and_greed() -> Optional[Dict]`
  - Chiama l’endpoint CMC, gestisce errori di rete e parsing JSON.

- `get_sentiment() -> Tuple[str, Dict] | str`
  - Ritorna stringa per il prompt e dict per il DB (se dati presenti), altrimenti una stringa di errore.

### 4.7 `news_feed.py`

**Responsabilità:** ingestion e normalizzazione di notizie crypto da feed RSS.

Funzioni:

- `_strip_html_tags(text: str) -> str`
  - Pulisce HTML e normalizza whitespace.

- `fetch_latest_news(max_chars: int = 4000) -> str`
  - Richiede il feed RSS;
  - parse XML con `ElementTree`;
  - per ogni `item` crea una riga testo con timestamp normalizzato (preferibilmente in UTC) e titolo+descrizione;
  - applica limite di lunghezza totale (con truncation ellittica dell’ultima entry se necessario).

### 4.8 `whalealert.py`

**Responsabilità:** gestione e formattazione degli alert di movimenti crypto significativi.

Funzioni:

- `get_whale_alerts()`
  - Chiama endpoint `whale-alert.io`, parse JSON e stampa gli alert in modo leggibile.

- `format_whale_alerts_to_string() -> str`
  - Versione che ritorna una stringa (utilizzabile in un prompt).

### 4.9 `db_utils.py`

**Responsabilità:** definizione schema DB e funzioni di logging/lettura.

Elementi chiave:

- `DBConfig`, `get_db_config()`, `get_connection()` – setup connessione a PostgreSQL tramite `DATABASE_URL`.

- `SCHEMA_SQL` e `MIGRATION_SQL` – definizione e migrazione dello schema.

Tabelle principali:

1. `account_snapshots`
   - `id`, `created_at`, `balance_usd`, `raw_payload` (JSONB con lo stato completo Hyperliquid).

2. `open_positions`
   - posizioni aperte per snapshot, con dettagli `symbol`, `side`, `size`, `entry_price`, `mark_price`, `pnl_usd`, `leverage`.

3. `ai_contexts`
   - contesto AI per ogni decisione (prompt intero).

4. `indicators_contexts`
   - indicatori normalizzati per ticker e contesto (inclusi JSONB per serie intraday e longer term).

5. `news_contexts`, `sentiment_contexts`, `forecasts_contexts`
   - testi news, sentiment Fear & Greed e forecast pricing per contesto.

6. `bot_operations`
   - decisioni del bot, con campi chiave (operation, symbol, direction, leverage, target_portion_of_balance) e `raw_payload` JSON.

7. `errors`
   - errori avvenuti in esecuzione, con traceback completo e context JSON.

Funzioni principali:

- `init_db()` – crea/migra schema.
- `log_error(exc, context=None, source=None)` – registra errori.
- `log_account_status(account_status)` – salva snapshot account e posizioni.
- `log_bot_operation(operation_payload, system_prompt, indicators, news_text, sentiment, forecasts)` – salva contesto, indicatori, news, sentiment, forecast e operazione in tabelle dedicate.
- `get_latest_account_snapshot()` – restituisce ultimo snapshot account.
- `get_recent_bot_operations(limit=50)` – restituisce lista di ultime operazioni.

### 4.10 `test_trading.py`

**Responsabilità:** script di test/manual QA per `HyperLiquidTrader`.

- Inizializza il trader su testnet.
- Stampa limiti del simbolo (`debug_symbol_limits("BTC")`).
- Stampa leva corrente e stato account.
- Esegue una chiamata di prova a `execute_signal` con un segnale predefinito (attualmente `operation: "close"` su BNB) per verificare che la pipeline di esecuzione funzioni.

### 4.11 Altri file

- `README.md`: overview funzionale ad alto livello (in italiano).
- `requirements.txt`: elenco dipendenze Python (ccxt, pandas, numpy, ta, tradingview-screener, prophet, yfinance, matplotlib, python-dotenv, hyperliquid-python-sdk, eth-account, toonify, psycopg2-binary).
- `system_prompt.txt`: template del prompt generico.
- `formatted_system_prompt.txt`: esempio di prompt già popolato (snapshot utile per debug).
- `railway.json`: configurazione deploy Railway (builder NIXPACKS, startCommand `python main.py`, restart policy `ON_FAILURE`).
- `.gitignore`: configurazione standard per progetti Python, virtualenv, IDE, ecc.


## 5. Integrazioni esterne e variabili d’ambiente

### 5.1 Hyperliquid

- Richiede chiavi associate al wallet:
  - `PRIVATE_KEY`
  - `WALLET_ADDRESS`
- Usa `hyperliquid-python-sdk` per:
  - `Info` (dati di mercato, meta, orderbook, user_state);
  - `Exchange` (market_open, market_close, update_leverage).

### 5.2 OpenAI

- Variabile `OPENAI_API_KEY` con la chiave API.
- Modello usato: `gpt-5.1` con output vincolato da JSON Schema.

### 5.3 CoinMarketCap – Fear & Greed

- Variabile `CMC_PRO_API_KEY`.
- Endpoint: `https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical` con `limit=1`.

### 5.4 Database PostgreSQL

- Variabile `DATABASE_URL` con DSN tipo:
  - `postgresql://user:password@host:port/database`.


## 6. Gestione errori, logging e osservabilità

- Errori di rete verso servizi esterni sono generalmente catturati e loggati (spesso stampati a stdout, in alcuni casi ignorati ma riportati in stringhe di errore).
- `main.py` racchiude il flusso principale in un `try/except` e, in caso di eccezione, invoca `db_utils.log_error` con un contesto ricco che include:
  - prompt di sistema;
  - ticker;
  - indicatori grezzi;
  - news;
  - sentiment;
  - forecast;
  - stato dell’account.
- Il DB diventa quindi fonte di verità per:
  - ricostruire le decisioni dell’agente;
  - eseguire debug di errori;
  - analizzare performance nel tempo.


## 7. Estensioni e personalizzazioni possibili

1. **Aggiunta di nuovi ticker**
   - aggiornare la lista `tickers` in `main.py` e, se necessario, espandere l’enum `symbol` nello schema JSON in `trading_agent.py`;
   - verificare che Hyperliquid supporti tali ticker e che `hyperliquid_trader.py` gestisca correttamente min size / leva.

2. **Integrazione Whale Alerts nel prompt principale**
   - scommentare l’uso di `format_whale_alerts_to_string()` in `main.py`;
   - aggiungere una nuova sezione `<whalealerts> ... </whalealerts>` nel `system_prompt.txt` (e gestire la formattazione).

3. **Nuovi indicatori tecnici**
   - espandere `CryptoTechnicalAnalysisHL` con ulteriori indicatori supportati da `ta`;
   - arricchire sia il dict quanto la stringa formattata;
   - estendere schema DB (`indicators_contexts`) se si vogliono salvare i nuovi campi in forma strutturata.

4. **Strategie multi‑agente**
   - utilizzare `db_utils` per salvare contesti di più agenti con prompt differenti e confrontare performance;
   - introdurre un campo `agent_id` nelle tabelle `ai_contexts` / `bot_operations` per distinguere le configurazioni.

5. **Schedulazione e frequenza di esecuzione**
   - il progetto, così com’è, esegue una singola decisione ad avvio;
   - l’utente può integrarlo con un scheduler (cron, worker, o meccanismo interno) per avere cicli di decisione continui (es. ogni 15 minuti).


## 8. Requisiti di esecuzione e deploy

- **Python** 3.x con le dipendenze di `requirements.txt` installate.
- Disponibilità di un database PostgreSQL accessibile tramite `DATABASE_URL`.
- Variabili d’ambiente configurate:
  - `OPENAI_API_KEY`
  - `PRIVATE_KEY`
  - `WALLET_ADDRESS`
  - `CMC_PRO_API_KEY`
  - `DATABASE_URL`

### 8.1 Deploy su Railway

- Il file `railway.json` configura:
  - builder: `NIXPACKS`;
  - comando di start: `python main.py`;
  - policy di restart: `ON_FAILURE` con massimo 10 retry.

Su Railway sarà necessario configurare le variabili d’ambiente e il database PostgreSQL (come servizio o esterno).


## 9. Conclusioni

Il progetto **Trading Agent** fornisce un’architettura completa per un agente di trading AI‑driven:

- raccoglie una grande quantità di segnali (tecnici, fondamentali e di sentiment);
- li integra in un prompt strutturato e storicizzabile;
- delega la decisione ad un LLM con output rigorosamente schema‑driven;
- esegue ordini reali su un exchange (Hyperliquid) rispettando vincoli operativi (min size, leva, ecc.);
- salva in un database relazionale tutte le informazioni necessarie per analisi e miglioramento del sistema.

Questo documento può fungere da base per chi vuole:
- comprendere a fondo il flusso end‑to‑end;
- estendere la logica di analisi o di decisione;
- integrare nuovi moduli di dati esterni o nuove strategie;
- effettuare audit e monitoring di produzione.
