# 📊 Logging System Guide

## Overview
Il sistema di logging è stato migliorato con 3 livelli di verbosità per ridurre il "rumore" e rendere più chiaro cosa sta succedendo.

## Come Configurare

Apri `config.py` e cerca la sezione:
```python
# ----------------------------------------------------------------------
# Logging Mode - NEW: Multi-level verbosity
# ----------------------------------------------------------------------
LOG_VERBOSITY = "MINIMAL"  # Cambia qui: "MINIMAL", "NORMAL", "DETAILED"
```

## Livelli di Verbosità

### 🎯 MINIMAL (consigliato per trading live)
**Output pulito con solo eventi critici:**
- ✅ Apertura/chiusura posizioni
- 💰 P&L e bilancio
- 🎯 Decisioni finali (BUY/SELL/SKIP)
- ❌ Errori e warning importanti
- 📊 Summary del ciclo

**Blocca:**
- Debug tecnici
- Calcoli interni
- Verifiche SL ripetitive
- API calls dettagli
- Trailing updates prolissi

**Usa quando:** Vuoi vedere solo cosa succede realmente (trade aperti/chiusi, guadagni/perdite)

### 📊 NORMAL (buon compromesso)
**Include MINIMAL + operazioni standard:**
- 🧠 Predizioni ML e confidence
- 🛡️ Controlli risk management
- 🎪 Trailing stop activations
- 🎯 Adaptive sizing decisions
- ⚖️ Consensus tra timeframe

**Usa quando:** Vuoi capire perché il bot prende certe decisioni

### 🔍 DETAILED (per debug)
**Tutto, incluso:**
- 🐛 Debug messages
- 📡 API calls
- 🔧 Normalizzazioni prezzi
- 💾 Cache operations
- 📏 Pre-flight validations

**Usa quando:** Stai investigando un problema o sviluppando

## Esempi di Output

### MINIMAL Mode (pulito)
```
📊 Logging: MINIMAL mode (only trades & P&L)
ℹ️ ┌──────────────────────────────────────────────────────────┐
ℹ️ │ TRADE #1: DASH BUY                                       │
ℹ️ │ 🎯 Signal: 🟢 BUY | Confidence: 100.0% | ML: 3/3         │
ℹ️ │ 💰 Entry: $122.20 | Size: 2.57 | Margin: $31.43        │
ℹ️ │ ✅ Status: SUCCESS - Position opened with protection    │
ℹ️ └──────────────────────────────────────────────────────────┘
ℹ️ ✅ POSITION OPENED: DASH protected with automatic stop loss

💰 Balance synced: $326.96 → $322.62 (-4.34)
📊 Trade closed: DASH | IM: $31.43 | PnL: +7.31 USD (+23.2% ROE)
```

### NORMAL Mode (più dettagli)
```
14:03:09 📊 Logging: NORMAL mode (standard operations)
14:03:09 ℹ️ 📊 Consensus: 🟢 15m=BUY, 🟢 30m=BUY, 🟢 1h=BUY → 🎯 100% agreement
14:03:09 ℹ️ 🧠 ML Confidence: 🚀 100.0% ████████████████████
14:03:09 ℹ️ 🤖 RL Filter: ✅ APPROVED
14:03:09 ℹ️ 🛡️ Risk Manager: ✅ APPROVED (position size validated)
14:03:10 ℹ️ 🎯 ADAPTIVE SIZING | Wallet: $314.33 | Slot: $62.87
14:03:11 ℹ️ ┌──────────────────────────────────────────────────────────┐
14:03:11 ℹ️ │ TRADE #1: DASH BUY                                       │
...
```

### DETAILED Mode (tutto)
```
14:03:09 📊 Logging: DETAILED mode (full debug)
14:03:09 🐛 Cache hit for positions: TTL remaining 25s
14:03:09 🐛 Using PORTFOLIO SIZING: $31.43 margin (precalculated)
14:03:11 ℹ️ ✅ Pre-flight OK: size 3.000000 within [0.01, 1040.0]
14:03:11 ℹ️ 📏 Position size: 2.572267 → 3.000000
14:03:12 🐛 🔧 SL normalized with precision handler: 119.145 → 119.140
...
```

## Quick Switch

Per passare rapidamente tra modalità, basta cambiare una riga in `config.py`:

```python
LOG_VERBOSITY = "MINIMAL"  # Pulito - solo trade
LOG_VERBOSITY = "NORMAL"   # Dettagli utili
LOG_VERBOSITY = "DETAILED" # Tutto per debug
```

Poi riavvia il bot.

## Confronto Output

### Prima (vecchio sistema, prolisso)
```
2025-11-06 14:03:10 INFO ℹ️ 🔧 AUTO-FIX: Corrected 5 stop losses
2025-11-06 14:03:10 WARNING ⚠️ Negative volatility -1.38327 detected
2025-11-06 14:03:10 INFO ℹ️ 🔍 DEBUG PRE-SET: HYPE side=sell, long=False
2025-11-06 14:03:10 INFO ℹ️ 💰 POSITION SIZING: $25.15 USD (MODERATE)
2025-11-06 14:03:10 INFO ℹ️ 🔍 Checking stop losses for correctness...
2025-11-06 14:03:11 WARNING ⚠️ ⚠️ KITE: NO STOP LOSS! Setting SL...
2025-11-06 14:03:11 INFO ℹ️ ✅ KITE: SL VERIFIED @ $0.073000
[100+ linee simili...]
```

### Dopo (MINIMAL mode, pulito)
```
ℹ️ 📊 TRADE #1: DASH BUY | $122.20 | Size: 2.57 | +100% confidence
ℹ️ ✅ Position opened with stop loss protection
💰 Balance synced: $326.96 → $322.62 (-4.34)
📊 Trade closed: DASH | PnL: +7.31 USD (+23.2% ROE) ✅
ℹ️ 📊 CYCLE COMPLETED | Time: 565s | Active: 3 positions | P&L: +$13.84
```

## Raccomandazioni

- **Trading Live:** Usa `MINIMAL` - vedi solo risultati importanti
- **Monitoring:** Usa `NORMAL` - capisci le decisioni del bot
- **Debugging:** Usa `DETAILED` - analizza problemi tecnici

## Note Tecniche

Il nuovo sistema:
- ✅ Filtra messaggi ridondanti (DEBUG PRE/POST/VERIFY)
- ✅ Blocca warning inutili (volatilità negativa, ecc)
- ✅ Mantiene tutti gli errori critici visibili
- ✅ Timestamp solo in NORMAL/DETAILED
- ✅ Output colorato con emoji per chiarezza
