# 🛡️ GUIDA PROTEZIONE CAPITALE - Evitare Perdite Considerevoli

## 🚨 SITUAZIONE ATTUALE

Se il bot sta **perdendo soldi**, devi agire **SUBITO** per proteggere il capitale. Non aspettare "sperando migliori".

---

## 🔴 AZIONI IMMEDIATE (DA FARE ORA)

### 1️⃣ **FERMA TUTTO IN LIVE MODE**

**Se stai perdendo in LIVE, FERMA SUBITO**:

```python
# In config.py - CAMBIA SUBITO:
DEMO_MODE = True  # DA False → True
DEMO_BALANCE = 1000.0

# Oppure FERMA il bot completamente:
# Ctrl+C per terminare
```

**Perché**: Non puoi testare strategie con soldi veri. Demo mode è GRATIS e sicuro.

---

### 2️⃣ **CHIUDI POSIZIONI APERTE MANUALMENTE**

**Se hai posizioni losing aperte**:

1. Vai su Bybit web/app
2. Vai su "Positions"
3. Per ogni posizione losing:
   - Se loss < -10%: CHIUDI subito
   - Se loss -10% a -30%: valuta se aspettare SL o chiudi
   - Se loss > -30%: CHIUDI IMMEDIATAMENTE (disaster)

**Formula rapida**:
```
Loss tollerabile = 2-3% del capitale totale per posizione
Loss inaccettabile = 5%+ del capitale totale per posizione
```

**Esempio**:
- Capitale: $1000
- Posizione: $40 margin × 8x leva = $320 notional
- Loss -20% = -$64 = **-6.4% capitale totale** → CHIUDI SUBITO!

---

### 3️⃣ **ANALIZZA DOVE STAI PERDENDO**

Usa `data_cache/trade_history.json` per vedere pattern:

```python
# Apri il file e analizza:
{
  "closed_trades": [
    {
      "symbol": "BTC/USDT:USDT",
      "side": "LONG",
      "entry_price": 45000,
      "exit_price": 43500,
      "pnl_pct": -3.3,  # -3.3% prezzo
      "pnl_usd": -26.4,  # -$26.4 loss
      "close_reason": "STOP_LOSS"
    },
    ...
  ]
}
```

**Domande chiave**:
1. Win rate < 50%? → ML non funziona
2. Average loss > average win? → Risk/reward sbagliato
3. Stop loss hit spesso? → Entries premature
4. Simboli specifici perdono? → Evitali
5. Long o Short perdono più? → Mercato trending

---

### 4️⃣ **CALCOLA DRAWDOWN MASSIMO TOLLERABILE**

**Formula sicura**:
```
Max Drawdown Accettabile = 20% del capitale

Capitale: $1000
Max Loss Accettabile: $200
Se perdi $200 → STOP trading, rivedi strategia
```

**Stop Loss per Giorno**:
```
Daily Loss Limit = 5% del capitale

Capitale: $1000
Max Loss/Day: $50
Se perdi $50 in un giorno → STOP per oggi
```

**Implementa nel codice**:
```python
# In config.py - AGGIUNGI:
MAX_DAILY_LOSS_PCT = 0.05  # 5% max loss per day
MAX_TOTAL_DRAWDOWN_PCT = 0.20  # 20% max total drawdown

# In trading_engine.py - AGGIUNGI CHECK:
if daily_loss > (balance * MAX_DAILY_LOSS_PCT):
    logging.critical("🚨 DAILY LOSS LIMIT HIT - STOPPING!")
    sys.exit(1)
```

---

## 🛡️ STRATEGIE DEFENSIVE (Setup Ultra-Conservativo)

### Setup 1: CAPITAL PRESERVATION (Massima Sicurezza)

```python
# config.py - ULTRA-CONSERVATIVO

# MODALITÀ
DEMO_MODE = True  # SEMPRE demo finché non provato
DEMO_BALANCE = 5000.0

# POSITION SIZING (MINIMO)
FIXED_POSITION_SIZE_AMOUNT = 20.0  # $20 invece di $40
MAX_CONCURRENT_POSITIONS = 3  # Max 3 invece di 5

# RISK MANAGEMENT (STRETTISSIMO)
STOP_LOSS_PCT = 0.04  # -4% invece di -6% (SL più stretto)
MIN_CONFIDENCE = 0.85  # 85% minimum (solo best signals)

# LEVERAGE (BASSO)
LEVERAGE = 5  # 5x invece di 8x (meno risk)

# SIMBOLI (SOLO MAJORS)
TOP_ANALYSIS_CRYPTO = 10  # Top 10 solo
SYMBOL_WHITELIST = [  # SOLO questi
    'BTC/USDT:USDT',
    'ETH/USDT:USDT', 
    'BNB/USDT:USDT',
    'SOL/USDT:USDT',
    'XRP/USDT:USDT'
]

# TRADING FREQUENCY (RIDOTTO)
TRADE_CYCLE_INTERVAL = 1800  # 30 min invece di 15 min

# DISABILITA TUTTO TEORICO
AI_VALIDATION_ENABLED = False
DUAL_ENGINE_ENABLED = False
MARKET_INTELLIGENCE_ENABLED = False
TRAILING_ENABLED = False
EARLY_EXIT_ENABLED = False
```

**Risultato**:
- 3 posizioni × $20 = max $60 exposure
- Con leva 5x = $300 notional total
- Con SL -4% = max -$12 loss per trade
- Max total loss (3 trades) = -$36 = -0.7% se hai $5000

---

### Setup 2: PAPER TRADING LUNGO (30+ Giorni)

**Obiettivo**: Provare strategia SENZA rischiare

```python
# config.py
DEMO_MODE = True
DEMO_BALANCE = 10000.0  # Simula $10k

# Tieni log dettagliati per 30 giorni:
# - Win rate per day
# - Max drawdown
# - Sharpe ratio
# - Profit factor
```

**Metriche Target** (prima di live):
```
Win Rate: ≥ 55%
Profit Factor: ≥ 1.5 (avg win / avg loss)
Max Drawdown: ≤ 15%
Sharpe Ratio: ≥ 1.0
Consecutive Losses: ≤ 5
```

**Se NON raggiungi questi target dopo 30 giorni**:
→ **Non andare in live!** ML non ha edge sul mercato.

---

### Setup 3: MICRO-POSITIONS (Test Edge con Risk Minimo)

```python
# config.py - MICRO TESTING

# POSITION SIZE MINUSCOLO
FIXED_POSITION_SIZE_AMOUNT = 10.0  # $10 solo (1% of $1000)
MAX_CONCURRENT_POSITIONS = 2  # Max 2 posizioni

# LEVERAGE MINIMO
LEVERAGE = 3  # 3x (quasi spot trading)

# SL MOLTO STRETTO
STOP_LOSS_PCT = 0.03  # -3% (exit veloce se sbagliato)

# CONFIDENCE ALTISSIMA
MIN_CONFIDENCE = 0.90  # 90% = solo best of best
```

**Obiettivo**: Testare se ML ha edge con risk micro ($10-20 max loss/day)

**Se profittevole con micro-positions**:
→ Aumenta gradualmente ($20 → $30 → $40)

**Se perde anche con micro-positions**:
→ ML non ha edge, non scalare!

---

## 📊 STRATEGIE ALTERNATIVE (Se ML Non Funziona)

### Opzione A: MANUAL OVERRIDE

**Usa bot come SCREENER, tu decidi**:

```python
# In trading_engine.py - MODIFICA:
# Invece di execute_trade() automatico:

for signal in top_signals:
    print(f"🔍 SIGNAL: {signal['symbol']} {signal['direction']}")
    print(f"   Confidence: {signal['confidence']}%")
    print(f"   RSI: {signal['indicators']['rsi']}")
    print(f"   MACD: {signal['indicators']['macd']}")
    
    # Aspetta input utente
    action = input("Execute? (y/n): ")
    if action.lower() == 'y':
        execute_trade(signal)
```

**Vantaggio**: Tu valuti contesto macro che ML non vede.

---

### Opzione B: SOLO LONG IN BULL / SOLO SHORT IN BEAR

**Filtra direzione basata su trend macro**:

```python
# In config.py - AGGIUNGI:
MARKET_MODE = "BULL"  # "BULL", "BEAR", "NEUTRAL"

# In signal processing:
if MARKET_MODE == "BULL":
    signals = [s for s in signals if s['direction'] == 'LONG']
elif MARKET_MODE == "BEAR":
    signals = [s for s in signals if s['direction'] == 'SHORT']
```

**Ragionamento**: Non combattere il trend principale.

---

### Opzione C: ONLY BEST TIMEFRAME

**Usa solo 1 timeframe (il migliore)**:

```python
# Analizza quale timeframe ha win rate migliore:
# - 5m: rumoroso, false signals
# - 15m: bilanciato
# - 30m: più stabile, meno trade

# In config.py:
ENABLED_TIMEFRAMES = ["30m"]  # Solo 30m (più stabile)
```

---

### Opzione D: CORRELATION FILTER

**Non aprire trade su simboli correlati**:

```python
# Se hai BTC long, non aprire ETH long (correlazione alta)
# Diversifica su asset decorrelati

# In config.py:
MAX_CORRELATED_POSITIONS = 1  # Max 1 posizione per group

CORRELATION_GROUPS = {
    "major_layer1": ["BTC", "ETH", "BNB"],
    "defi": ["UNI", "AAVE", "LINK"],
    "gaming": ["AXS", "SAND", "MANA"]
}
```

---

## 🚨 RED FLAGS (Segnali di Pericolo)

### 🔴 **STOP TRADING SE**:

**1. Win Rate < 45% dopo 20+ trade**
```
Significa: ML peggio di random (50%)
Azione: STOP, rivedi labeling/features
```

**2. Consecutive Losses > 7**
```
Significa: Losing streak anomalo
Azione: STOP, retrain modelli
```

**3. Drawdown > 20% del capitale**
```
Capitale: $1000 → $800 (-20%)
Azione: STOP IMMEDIATO
```

**4. Daily Loss > 5% per 3 giorni consecutivi**
```
Giorno 1: -5% (-$50)
Giorno 2: -5% (-$47.5)
Giorno 3: -5% (-$45.1)
Totale: -14.3% in 3 giorni
Azione: STOP per 1 settimana, rivedi tutto
```

**5. Un Trade Loss > 10% del capitale**
```
Loss singolo: -$100 su $1000 capitale
Azione: Position sizing TROPPO grande, aggiusta
```

---

## ✅ GREEN FLAGS (Segnali Positivi)

### 🟢 **CONTINUA SE**:

**1. Win Rate 55-65%**
```
Buon edge, ma non eccessivo (sospetto)
```

**2. Profit Factor > 1.5**
```
Profit Factor = Avg Win / Avg Loss
1.5 = vincenti compensano perdenti + extra
```

**3. Max Drawdown < 15%**
```
Volatilità gestibile
```

**4. Recovery dopo Losses**
```
Dopo losing streak, torna in profit
Significa: no systematic bias
```

**5. Consistency**
```
Win rate stabile settimana dopo settimana
Non solo lucky weeks
```

---

## 💡 BEST PRACTICES OPERATIVE

### 1. **START SMALL, SCALE GRADUALLY**

```
Week 1: $10/trade (micro)
Week 2: $15/trade (se win rate ≥ 55%)
Week 3: $20/trade (se ancora profittevole)
Week 4+: $30-40/trade (solo se consistent)

MAI saltare da $10 a $100!
```

### 2. **DAILY REVIEW**

```
Ogni giorno:
- Check posizioni aperte
- Review trade chiusi (win/loss reasons)
- Update trade journal
- Calcola win rate giornaliero
- Verifica se sopra/sotto target
```

### 3. **WEEKLY RETRAIN**

```
Ogni settimana:
- Retrain modelli con dati ultimi 90 giorni
- Dati freschi = pattern aggiornati
- Mercato cambia, modelli devono seguire
```

### 4. **POSITION SIZE RULE**

```
MAI risk > 2% del capitale per trade

Capitale: $1000
Max Risk: $20 per trade

Con leva 8x e SL -6%:
- Margin: $40
- Notional: $320
- SL hit: -$19.2 (6% × $320)
- Risk: 1.9% del capitale ✅ OK

Con leva 10x e SL -6%:
- Margin: $40  
- Notional: $400
- SL hit: -$24 (6% × $400)
- Risk: 2.4% del capitale ❌ TROPPO!
```

### 5. **DIVERSIFICATION**

```
NON:
- 5 posizioni BTC + ETH + BNB (tutti layer 1)
- Tutte LONG o tutte SHORT
- Tutte aperte stesso momento

SÌ:
- Mix di categorie (layer 1, defi, gaming, etc.)
- Mix direction (2 long, 1 short)
- Aperture scaglionate nel tempo
```

---

## 🎯 PIANO D'AZIONE CONCRETO

### Fase 1: STOP BLEEDING (Oggi)

```
✅ Ferma bot in live
✅ Chiudi posizioni losing (> -10%)
✅ Calcola total loss fino ad ora
✅ Backup config attuale
✅ Passa a DEMO MODE
```

### Fase 2: ANALYZE (Giorni 1-3)

```
✅ Analizza trade_history.json
✅ Calcola win rate per:
   - Simbolo
   - Direction (LONG vs SHORT)
   - Timeframe
   - Confidence range
✅ Identifica pattern losses
✅ Identifica winning patterns
```

### Fase 3: OPTIMIZE (Giorni 4-7)

```
✅ Applica config ultra-conservativo
✅ Disabilita tutti componenti teorici
✅ Confidence ≥ 80% minimum
✅ Retrain modelli con dati recenti
✅ Test in DEMO 7 giorni
```

### Fase 4: VALIDATE (Giorni 8-37)

```
✅ Paper trading 30 giorni completi
✅ Track metriche giornaliere
✅ Target win rate ≥ 55%
✅ Se target hit → Fase 5
✅ Se target miss → Rivedi ML/labeling
```

### Fase 5: MICRO-LIVE (Giorni 38-67)

```
✅ Switch a live con $10/trade
✅ Max 2 posizioni simultanee
✅ Leverage 3-5x (non 8x)
✅ Test 30 giorni con risk micro
✅ Se profittevole → Fase 6
✅ Se perde → STOP, no edge
```

### Fase 6: SCALE (Giorni 68+)

```
✅ Aumenta gradualmente $10 → $20 → $30
✅ Una settimana per livello
✅ Solo se win rate mantiene ≥ 55%
✅ Mai rush, pazienza paga
```

---

## ⚠️ COSA FARE SE NULLA FUNZIONA

### Opzione 1: RIVEDI FUNDAMENTALS

```
Problemi comuni:
- Labeling sbagliato (SL-aware non corretto)
- Features non informative (66 troppi? troppo rumore?)
- Training data vecchi (modelli obsoleti)
- Overfitting (modelli memorizzano invece di generalizzare)
- Data leakage (futuro contamina training)
```

### Opzione 2: CONSIDERA ALTERNATIVES

```
Se dopo 60+ giorni testing ML non funziona:

❌ ML Algorithmic Trading potrebbe non avere edge

✅ Alternative:
- Manual trading (usa bot come screener)
- DCA (dollar cost averaging) su BTC/ETH
- Holding long-term
- Index investing crypto
- Stop trading, investi altrove
```

### Opzione 3: ACCEPT REALITY

```
VERITÀ SCOMODA:
- Mercato crypto è MOLTO volatile
- Retail traders (99%) perdono soldi
- ML edge è difficile da trovare
- Institutional players hanno vantaggi enormi
- Costi (fees, slippage, spreads) erodono profit

Se perdi dopo TUTTO:
→ Non è fallimento, è esperienza
→ Hai imparato coding, ML, trading
→ Capitale preservato è vittoria
→ Meglio STOP che insistere e perdere tutto
```

---

## 🎓 CONCLUSIONE

**Proteggere capitale > Fare profit**

**Setup Sicuro Minimo**:
1. ✅ Demo mode 30+ giorni
2. ✅ Win rate ≥ 55% provato
3. ✅ Position size $10-20 (micro)
4. ✅ Max 3 posizioni simultanee
5. ✅ Leverage 3-5x (non 8-10x)
6. ✅ SL -4% (stretto)
7. ✅ Confidence ≥ 85%
8. ✅ Top 10 simboli solo (majors)
9. ✅ Daily loss limit 5%
10. ✅ Total drawdown limit 20%

**Se NON rispetti questi**:
→ Risk di blown account è ALTO!

**Remember**: Bot non è ATM (bancomat). È tool che AMPLIFICA edge se esiste. Se edge non c'è, amplifica losses!

**Testa, misura, valida. SOLO POI scala.**

Non saltare step. Pazienza salva capitale. 🛡️
