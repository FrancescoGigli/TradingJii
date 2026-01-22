# 🔧 Streamlit Table Display Fix

## Problema

Le tabelle in Streamlit con `st.dataframe()` non mostravano i dati visibili nel tema scuro custom.

**Causa**: Streamlit usa un componente canvas-based chiamato **Glide Data Grid** per `st.dataframe()` che:
- Non risponde bene agli stili CSS custom
- Ha il proprio sistema di rendering interno
- Il testo e lo sfondo possono avere colori simili nel tema scuro

## Soluzione

Sostituire `st.dataframe()` con una **tabella HTML custom** usando `st.markdown()` con `unsafe_allow_html=True`.

### Codice della Soluzione

```python
def _render_html_table(df: pd.DataFrame, height: int = 400):
    """
    Render DataFrame as styled HTML table with dark theme - ALL COLUMNS VISIBLE.
    """
    if df is None or len(df) == 0:
        st.warning("No data to display")
        return
    
    # CSS per la tabella
    table_css = """
    <style>
        .custom-table-container {
            max-height: HEIGHT_PLACEHOLDERpx;
            overflow-y: auto;
            overflow-x: auto;
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 10px;
            background: #0d1117;
        }
        .custom-table {
            width: 100%;
            border-collapse: collapse;
            font-family: 'Rajdhani', monospace;
            font-size: 13px;
            white-space: nowrap;
        }
        .custom-table thead {
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .custom-table th {
            background: linear-gradient(135deg, #1a1f2e 0%, #2d3548 100%);
            color: #00ffff !important;  /* Cyan */
            padding: 12px 10px;
            text-align: left;
            border-bottom: 2px solid rgba(0, 255, 255, 0.5);
            font-weight: 700;
        }
        .custom-table td {
            background: #0d1117;
            color: #e0e0ff !important;  /* Light purple-white */
            padding: 10px;
            border-bottom: 1px solid rgba(0, 255, 255, 0.1);
        }
        .custom-table tr:hover td {
            background: rgba(0, 255, 255, 0.1);
        }
        /* Colori semantici per i valori */
        .col-positive { color: #00ff88 !important; font-weight: 600; }
        .col-negative { color: #ff4757 !important; font-weight: 600; }
        .col-neutral { color: #ffc107 !important; }
    </style>
    """.replace('HEIGHT_PLACEHOLDER', str(height))
    
    # Costruzione HTML
    html_rows = []
    
    # Header
    header_cells = "".join([f"<th>{col}</th>" for col in df.columns])
    html_rows.append(f"<thead><tr>{header_cells}</tr></thead>")
    
    # Body
    html_rows.append("<tbody>")
    for _, row in df.iterrows():
        cells = []
        for col, val in zip(df.columns, row.values):
            # Applica stili condizionali
            cell_class = ""
            if 'Return' in str(col) or 'Score' in str(col):
                try:
                    if float(str(val).replace('%', '')) > 0:
                        cell_class = "col-positive"
                    elif float(str(val).replace('%', '')) < 0:
                        cell_class = "col-negative"
                except:
                    pass
            cells.append(f'<td class="{cell_class}">{val}</td>')
        html_rows.append(f"<tr>{''.join(cells)}</tr>")
    html_rows.append("</tbody>")
    
    # Combina tutto
    table_html = f"""
    {table_css}
    <div class="custom-table-container">
        <table class="custom-table">
            {''.join(html_rows)}
        </table>
    </div>
    """
    
    st.markdown(table_html, unsafe_allow_html=True)
```

## Caratteristiche della Soluzione

| Feature | Descrizione |
|---------|-------------|
| **Sfondo scuro** | `#0d1117` per visibilità |
| **Testo chiaro** | `#e0e0ff` sempre visibile |
| **Headers sticky** | Rimangono visibili durante lo scroll |
| **Scroll orizzontale** | Per tabelle con molte colonne |
| **Scroll verticale** | Con altezza configurabile |
| **Colori semantici** | Verde per positivi, rosso per negativi |
| **Hover effects** | Feedback visivo sulle righe |

## Quando Usare

Usare `_render_html_table()` invece di `st.dataframe()` quando:

1. ✅ Si usa un tema scuro custom
2. ✅ Si vuole controllo totale sugli stili
3. ✅ Si necessita di colori condizionali sui valori
4. ✅ Si vuole uno sticky header

## Limitazioni

| `_render_html_table()` | `st.dataframe()` |
|-----------------------|------------------|
| No ordinamento click | Ordinamento integrato |
| No filtri nativi | Filtri integrati |
| No editing | Editing inline |
| Più controllo CSS | Meno controllo CSS |

## File Modificato

`agents/frontend/components/tabs/train/labeling_table.py`

---

## VIEW v_xgb_training - Tutte le 24 Colonne

La VIEW `v_xgb_training` contiene **24 colonne** totali:

### Da `training_data` (OHLCV + Indicatori):
| # | Colonna | Descrizione |
|---|---------|-------------|
| 1 | `symbol` | Simbolo (es: BTC/USDT:USDT) |
| 2 | `timeframe` | Timeframe (15m o 1h) |
| 3 | `timestamp` | Data/ora della candela |
| 4 | `open` | Prezzo apertura |
| 5 | `high` | Prezzo massimo |
| 6 | `low` | Prezzo minimo |
| 7 | `close` | Prezzo chiusura |
| 8 | `volume` | Volume |
| 9 | `rsi` | RSI (14) |
| 10 | `atr` | ATR |
| 11 | `macd` | MACD |

### Da `training_labels` (Labels ML):
| # | Colonna | Descrizione |
|---|---------|-------------|
| 12 | `score_long` | Score LONG (target ML) |
| 13 | `score_short` | Score SHORT (target ML) |
| 14 | `realized_return_long` | Return realizzato LONG |
| 15 | `realized_return_short` | Return realizzato SHORT |
| 16 | `mfe_long` | Maximum Favorable Excursion LONG |
| 17 | `mfe_short` | Maximum Favorable Excursion SHORT |
| 18 | `mae_long` | Maximum Adverse Excursion LONG |
| 19 | `mae_short` | Maximum Adverse Excursion SHORT |
| 20 | `bars_held_long` | Barre tenute LONG |
| 21 | `bars_held_short` | Barre tenute SHORT |
| 22 | `exit_type_long` | Tipo uscita LONG (trailing/time/stop) |
| 23 | `exit_type_short` | Tipo uscita SHORT |
| 24 | `atr_pct` | ATR come percentuale del prezzo |

### SQL della VIEW

```sql
CREATE VIEW v_xgb_training AS
SELECT
    d.symbol, d.timeframe, d.timestamp,
    d.open, d.high, d.low, d.close, d.volume,
    d.rsi, d.atr, d.macd,
    l.score_long, l.score_short,
    l.realized_return_long, l.realized_return_short,
    l.mfe_long, l.mfe_short, l.mae_long, l.mae_short,
    l.bars_held_long, l.bars_held_short,
    l.exit_type_long, l.exit_type_short,
    l.atr_pct
FROM training_data d
INNER JOIN training_labels l
    ON d.symbol = l.symbol
   AND d.timeframe = l.timeframe
   AND d.timestamp = l.timestamp
```

---

*Documentazione creata il 21/01/2026*
