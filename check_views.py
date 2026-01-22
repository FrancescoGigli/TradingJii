import sqlite3

conn = sqlite3.connect('shared/data_cache/trading_data.db')

# Get all views
cursor = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='view'")
views = cursor.fetchall()

print(f"\n=== VIEWS IN DATABASE ({len(views)} found) ===\n")
for name, sql in views:
    print(f"VIEW: {name}")
    print("-" * 50)
    print(sql[:1000] if sql else "No SQL")
    print("\n")

# Check columns in training_labels
print("\n=== COLUMNS IN training_labels ===")
cursor = conn.execute("PRAGMA table_info(training_labels)")
for col in cursor.fetchall():
    print(f"  {col[1]}: {col[2]}")

conn.close()
