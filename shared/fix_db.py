import sqlite3
conn = sqlite3.connect('/app/shared/crypto_data.db')
cur = conn.cursor()

# Check current status
cur.execute('SELECT status, COUNT(*) FROM backfill_status GROUP BY status')
print('Before:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

# Fix PENDING to SKIPPED
cur.execute("UPDATE backfill_status SET status = 'SKIPPED', error_message = 'Not processed - download completed' WHERE status = 'PENDING'")
updated = cur.rowcount
conn.commit()
print(f'\nUpdated {updated} PENDING -> SKIPPED')

# Check after
cur.execute('SELECT status, COUNT(*) FROM backfill_status GROUP BY status')
print('\nAfter:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

conn.close()
