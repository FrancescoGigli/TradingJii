#!/usr/bin/env python3
"""
Script per refactorizzare trading_dashboard.py usando i moduli creati.
Sostituisce i metodi lunghi con chiamate ai moduli dedicati.
"""

import re

# Leggi il file originale
with open('core/trading_dashboard.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Backup
with open('core/trading_dashboard.py.before_refactor', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Backup creato: trading_dashboard.py.before_refactor")

# 1. Aggiorna gli imports
old_import = "# Import dashboard modules\nfrom core.dashboard import ColorHelper, create_adaptive_memory_table, populate_adaptive_memory_table"

new_import = """# Import dashboard modules (REFACTORED)
from core.dashboard import (
    ColorHelper,
    PositionTablePopulator,
    ClosedTablePopulator,
    create_adaptive_memory_table,
    populate_adaptive_memory_table
)"""

if old_import in content:
    content = content.replace(old_import, new_import)
    print("✅ Imports aggiornati")
else:
    print("⚠️ Import pattern non trovato, skip")

# 2. Sostituisci _populate_position_table
# Trova l'intero metodo (dalla definizione fino al prossimo metodo)
pattern_populate_position = r'(    def _populate_position_table\(self, table: QTableWidget, positions: list, tab_name: str\):.*?)(\n    def \w+\()'

replacement_populate_position = r'''    def _populate_position_table(self, table: QTableWidget, positions: list, tab_name: str):
        """Populate a position table with position data - REFACTORED"""
        # Delegate to dedicated populator module
        PositionTablePopulator.populate(table, positions, tab_name)
\2'''

content, count = re.subn(pattern_populate_position, replacement_populate_position, content, flags=re.DOTALL)
if count > 0:
    print(f"✅ _populate_position_table sostituito ({count} occorrenze)")
else:
    print("❌ _populate_position_table NON sostituito")

# 3. Sostituisci _populate_closed_tab
pattern_populate_closed = r'(    def _populate_closed_tab\(self, table: QTableWidget, closed_positions: list\):.*?)(\n    def \w+\()'

replacement_populate_closed = r'''    def _populate_closed_tab(self, table: QTableWidget, closed_positions: list):
        """Populate closed positions tab - REFACTORED"""
        # Delegate to dedicated populator module
        ClosedTablePopulator.populate(table, closed_positions)
\2'''

content, count = re.subn(pattern_populate_closed, replacement_populate_closed, content, flags=re.DOTALL)
if count > 0:
    print(f"✅ _populate_closed_tab sostituito ({count} occorrenze)")
else:
    print("❌ _populate_closed_tab NON sostituito")

# Scrivi il file refactorizzato
with open('core/trading_dashboard.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ Refactoring completato!")
print("📄 File originale: core/trading_dashboard.py.before_refactor")
print("📄 File refactorizzato: core/trading_dashboard.py")

# Conta le righe
lines_before = len(open('core/trading_dashboard.py.before_refactor', 'r', encoding='utf-8').readlines())
lines_after = len(open('core/trading_dashboard.py', 'r', encoding='utf-8').readlines())
reduction = lines_before - lines_after
reduction_pct = (reduction / lines_before) * 100

print(f"\n📊 Statistiche:")
print(f"   Prima: {lines_before} righe")
print(f"   Dopo: {lines_after} righe")
print(f"   Riduzione: {reduction} righe (-{reduction_pct:.1f}%)")
