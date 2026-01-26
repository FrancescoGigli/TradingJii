# 📊 Tabs Refactoring Plan - Analisi e Rifattorizzazione

> Questo documento descrive la struttura attuale delle tab e le duplicazioni identificate.

---

## 📁 Struttura Attuale delle Tab

L'applicazione ha **3 tab principali** definite in `app.py`:

```
📊 Top 100 Coins  →  render_top_coins_tab()
🔄 Test (Backtest)  →  render_backtest_tab()
🎓 ML (Training)  →  render_train_tab()
```

---

## 🟢 Tab 1: Top 100 Coins (`top_coins/`)

### Struttura
| File | Funzione | Linee | Status |
|------|----------|-------|--------|
| `main.py` | Entry point | ~30 | ✅ OK |
| `coins_table.py` | Tabella Top 100 | ~200 | ✅ OK |
| `analysis.py` | Analisi coin | ~300 | ✅ OK |
| `styles.py` | Stili specifici | ~50 | ✅ OK |

### Valutazione
**✅ BEN STRUTTURATA** - Nessuna azione necessaria.
- Separazione pulita tra UI e logica
- File di dimensioni appropriate
- Nessuna duplicazione

---

## 🟢 Tab 2: Test/Backtest (`backtest/`)

### Struttura
| File | Funzione | Linee | Status |
|------|----------|-------|--------|
| `main.py` | Entry point + statistiche | ~150 | ✅ OK |
| `controls.py` | Controlli e config | ~150 | ✅ OK |
| `signals.py` | Confronto segnali | ~200 | ✅ OK |
| `xgb_section.py` | Sezione XGBoost | ~250 | ✅ OK |
| `optimization.py` | Ottimizzazione | ~200 | ✅ OK |

### Valutazione
**✅ BEN STRUTTURATA** - Nessuna azione necessaria.
- Moduli con responsabilità singola
- Dimensioni appropriate

---

## 🔴 Tab 3: ML/Training (`train/`) - PROBLEMATICA

### Struttura Attuale (5 sotto-tab)

```
📂 1. Data       →  data.py
🏷️ 2. Labeling   →  labeling.py + 6 file supporto + labeling_analysis/
🚀 3. Training   →  training.py + 5 file supporto
📈 4. Models     →  models.py + models_inference.py
🗄️ 5. Explorer   →  explorer.py
```

### File Dettagliati

#### Step 1: Data
| File | Funzione | Status |
|------|----------|--------|
| `data.py` | Fetch dati, indicatori | ✅ OK |

#### Step 2: Labeling (7 file + package)
| File | Funzione | Status |
|------|----------|--------|
| `labeling.py` | Entry point Step 2 | ⚠️ Molto complesso |
| `labeling_config.py` | Config ATR | ✅ OK |
| `labeling_pipeline.py` | Pipeline generazione | ✅ OK |
| `labeling_db.py` | Database labels | ⚠️ Simile a `database/ml_labels/` |
| `labeling_table.py` | Render tabelle | ✅ OK |
| `labeling_visualizer.py` | Visualizzazione | ✅ OK |
| `labeling_analysis/` | Package analisi | ✅ Già modularizzato |

#### Step 3: Training (6 file)
| File | Funzione | Status |
|------|----------|--------|
| `training.py` | Entry point Step 3 | ✅ OK (orchestrator) |
| `training_io_tables.py` | Tabelle I/O | 🔴 Duplica `_get_models_dir()`, `COLORS` |
| `training_commands.py` | Comandi CLI | 🔴 Duplica `COLORS` |
| `training_model_details.py` | Dettagli modello | 🔴 DUPLICATO di `models.py` |
| `training_ai_eval.py` | AI Evaluation | ⚠️ Usa shared parzialmente |
| `training_btc_inference.py` | BTC Inference | ✅ Usa shared correttamente |

#### Step 4: Models (2 file)
| File | Funzione | Status |
|------|----------|--------|
| `models.py` | Dashboard modelli | 🔴 DUPLICATO di training_model_details.py |
| `models_inference.py` | Inference utility | ⚠️ Duplica model loading |

#### Step 5: Explorer
| File | Funzione | Status |
|------|----------|--------|
| `explorer.py` | Explorer database | ✅ OK |

#### Shared Modules (sottoutilizzati!)
| File | Funzione | Status |
|------|----------|--------|
| `shared/__init__.py` | Exports | ✅ OK |
| `shared/colors.py` | Colori centralizzati | ⚠️ NON USATO da tutti |
| `shared/model_loader.py` | Model loading | 🔴 NON USATO da quasi nessuno |

---

## 🚨 DUPLICAZIONI CRITICHE IDENTIFICATE

### 1. 🔴 `_get_models_dir()` - Duplicata 3 volte
Questa funzione è definita in:
- `shared/model_loader.py` → `get_model_dir()` ✓ (fonte centrale)
- `training_model_details.py` → `_get_models_dir()` ✗ DUPLICATO
- `training_io_tables.py` → `_get_models_dir()` ✗ DUPLICATO

**Azione**: Rimuovere le duplicazioni, usare `from .shared.model_loader import get_model_dir`

### 2. 🔴 `COLORS` - Duplicato 4+ volte
Il dizionario COLORS è definito in:
- `shared/colors.py` → `COLORS` ✓ (fonte centrale)
- `training_model_details.py` → `COLORS` ✗ DUPLICATO
- `training_io_tables.py` → `COLORS` ✗ DUPLICATO  
- `training_commands.py` → `COLORS` ✗ DUPLICATO
- `models.py` → dentro funzioni ✗ DUPLICATO

**Azione**: Rimuovere tutte le definizioni locali, usare `from .shared import COLORS`

### 3. 🔴 Model Metadata Loading - Duplicato 3 volte
| File | Funzione | Stesso scopo |
|------|----------|--------------|
| `shared/model_loader.py` | `load_metadata()` | ✓ Fonte centrale |
| `training_model_details.py` | `_load_metadata()` | ✗ Duplicato |
| `models.py` | `get_available_models_by_timeframe()` | ✗ Duplicato |

**Azione**: Usare `from .shared.model_loader import load_metadata, get_available_models`

### 4. 🔴 Step 3 vs Step 4 - OVERLAP FUNZIONALE MAGGIORE

**training.py (Step 3)** mostra:
- Dettagli modello (metrics, feature importance)
- AI Evaluation
- Bitcoin Inference

**models.py (Step 4)** mostra:
- **Stesso contenuto!** (Model summary, metrics, feature importance, AI analysis, inference)

**Problema**: L'utente vede le STESSE informazioni in due posti diversi.

---

## 📋 PIANO DI AZIONE RACCOMANDATO

### Fase 1: Consolidare Model Loading (PRIORITÀ ALTA)
```
✅ DO:
- Usare SOLO shared/model_loader.py per:
  - get_model_dir()
  - load_metadata()
  - get_available_models()
  - model_exists()

❌ DON'T:
- Definire _get_models_dir() localmente
- Definire _load_metadata() localmente
```

**File da modificare:**
1. `training_model_details.py` → rimuovere funzioni locali
2. `training_io_tables.py` → rimuovere funzioni locali
3. `models.py` → rimuovere `get_available_models_by_timeframe()`
4. `models_inference.py` → rimuovere `get_model_dir()`, usare shared

### Fase 2: Consolidare COLORS (PRIORITÀ ALTA)
```
✅ DO:
- Usare SOLO from .shared import COLORS in tutti i file

❌ DON'T:
- Definire COLORS localmente in nessun file
```

**File da modificare:**
1. `training_model_details.py` → rimuovere COLORS locale
2. `training_io_tables.py` → rimuovere COLORS locale
3. `training_commands.py` → rimuovere COLORS locale
4. `models.py` → usare COLORS da shared

### Fase 3: Risolvere Overlap Step 3 vs Step 4 (PRIORITÀ MEDIA)

**Opzione A - Differenziare (Consigliata):**
- **Step 3 Training**: Focus su ESECUZIONE training
  - Comandi CLI
  - Progress/status
  - Log output
  - Quick preview ultimo modello (semplificato)
  
- **Step 4 Models**: Focus su ANALISI modelli
  - Dashboard completo
  - Tutti i grafici
  - AI Analysis
  - Inference interattivo

**Opzione B - Unificare:**
- Rimuovere `training_model_details.py` da Step 3
- Mostrare solo comandi in Step 3
- Tutti i dettagli in Step 4

### Fase 4: Pulizia Labeling (PRIORITÀ BASSA)
Valutare se `labeling_db.py` può essere unito con `database/ml_labels/`.

---

## 📊 RIEPILOGO FILE PER AZIONE

### ✅ Nessuna Azione
- `top_coins/` - tutto ok
- `backtest/` - tutto ok
- `train/data.py` - ok
- `train/labeling_config.py` - ok
- `train/labeling_pipeline.py` - ok
- `train/labeling_table.py` - ok
- `train/labeling_visualizer.py` - ok
- `train/labeling_analysis/` - ok
- `train/training.py` - ok (orchestrator)
- `train/training_btc_inference.py` - ok (usa shared)
- `train/explorer.py` - ok
- `train/shared/` - ok (fonte centrale)

### ⚠️ Modifiche Minori
- `train/training_ai_eval.py` - già usa shared, verificare completezza
- `train/labeling.py` - valutare semplificazione
- `train/labeling_db.py` - potenziale merge con database/

### 🔴 Modifiche Necessarie
| File | Azione |
|------|--------|
| `training_model_details.py` | Usare shared, rimuovere duplicati |
| `training_io_tables.py` | Usare shared, rimuovere duplicati |
| `training_commands.py` | Usare COLORS da shared |
| `models.py` | Usare shared, rimuovere duplicati |
| `models_inference.py` | Usare model_loader da shared |

---

## 🎯 Metriche di Successo

Dopo la rifattorizzazione:
- [ ] Nessuna definizione locale di `COLORS` (solo in `shared/colors.py`)
- [ ] Nessuna definizione locale di `get_model_dir()` (solo in `shared/model_loader.py`)
- [ ] Nessuna definizione locale di `load_metadata()` (solo in `shared/model_loader.py`)
- [ ] Step 3 e Step 4 con ruoli chiaramente distinti
- [ ] Tutti i file `train/*.py` importano da `shared/`

---

*Documento creato: 2026-01-26*
*Ultimo aggiornamento: 2026-01-26*
