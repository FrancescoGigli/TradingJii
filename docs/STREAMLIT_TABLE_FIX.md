# 🔧 Streamlit Table Display Fix

## Problem

In Streamlit, `st.dataframe()` tables were not readable when a custom dark theme was enabled.

**Root cause**: Streamlit uses a canvas-based component called **Glide Data Grid** for
`st.dataframe()` which:
- does not reliably respond to custom CSS
- has its own internal rendering pipeline
- may choose text/background colors that reduce contrast in dark themes

## Solution

Replace `st.dataframe()` with a custom **HTML table** rendered via `st.markdown()` and
`unsafe_allow_html=True`.

### Reference Implementation

```python
def _render_html_table(df: pd.DataFrame, height: int = 400):
    """
    Render DataFrame as styled HTML table with dark theme - ALL COLUMNS VISIBLE.
    """
    if df is None or len(df) == 0:
        st.warning("No data to display")
        return
    
    # Table CSS
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
    
    # Build HTML
    html_rows = []
    
    # Header
    header_cells = "".join([f"<th>{col}</th>" for col in df.columns])
    html_rows.append(f"<thead><tr>{header_cells}</tr></thead>")
    
    # Body
    html_rows.append("<tbody>")
    for _, row in df.iterrows():
        cells = []
        for col, val in zip(df.columns, row.values):
            # Conditional formatting
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
    
    # Combine
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

## Solution Features

| Feature | Description |
|---------|-------------|
| **Dark background** | `#0d1117` for readability |
| **Light text** | `#e0e0ff` always visible |
| **Sticky headers** | Headers remain visible while scrolling |
| **Horizontal scrolling** | For wide tables |
| **Vertical scrolling** | Configurable container height |
| **Semantic colors** | Green for positive, red for negative |
| **Hover effects** | Visual feedback on hover |

## When to Use

Use `_render_html_table()` instead of `st.dataframe()` when:

1. ✅ A custom dark theme is enabled
2. ✅ You need full styling control
3. ✅ You want conditional value coloring
4. ✅ You want sticky table headers

## Limitations

| `_render_html_table()` | `st.dataframe()` |
|-----------------------|------------------|
| No click-to-sort | Built-in sorting |
| No native filters | Built-in filters |
| No editing | Inline editing |
| More CSS control | Less CSS control |

## Related File

`agents/frontend/components/tabs/train/labeling_table.py`

---

## v_xgb_training View - All 24 Columns

The `v_xgb_training` view contains **24 columns**:

### From `training_data` (OHLCV + indicators)
| # | Column | Description |
|---|---------|-------------|
| 1 | `symbol` | Symbol (e.g., BTC/USDT:USDT) |
| 2 | `timeframe` | Timeframe (15m or 1h) |
| 3 | `timestamp` | Candle timestamp |
| 4 | `open` | Open price |
| 5 | `high` | High price |
| 6 | `low` | Low price |
| 7 | `close` | Close price |
| 8 | `volume` | Volume |
| 9 | `rsi` | RSI (14) |
| 10 | `atr` | ATR |
| 11 | `macd` | MACD |

### From `training_labels` (ML labels)
| # | Column | Description |
|---|---------|-------------|
| 12 | `score_long` | LONG score (ML target) |
| 13 | `score_short` | SHORT score (ML target) |
| 14 | `realized_return_long` | LONG realized return |
| 15 | `realized_return_short` | SHORT realized return |
| 16 | `mfe_long` | LONG maximum favorable excursion |
| 17 | `mfe_short` | SHORT maximum favorable excursion |
| 18 | `mae_long` | LONG maximum adverse excursion |
| 19 | `mae_short` | SHORT maximum adverse excursion |
| 20 | `bars_held_long` | LONG bars held |
| 21 | `bars_held_short` | SHORT bars held |
| 22 | `exit_type_long` | LONG exit type (trailing/time/stop) |
| 23 | `exit_type_short` | SHORT exit type |
| 24 | `atr_pct` | ATR as percent of price |

### View SQL

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

*Documentation created on 2026-01-21*
