import sqlite3

DB_PATH = '/app/shared/data_cache/trading_data.db'
print('Database:', DB_PATH)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('Tabelle esistenti:', tables)

for table in ['historical_ohlcv', 'backfill_status', 'training_labels']:
    if table in tables:
        cur.execute(f'SELECT COUNT(*) FROM {table}')
        count = cur.fetchone()[0]
        print(f'{table}: {count:,} righe -> ELIMINATA')
        cur.execute(f'DROP TABLE IF EXISTS {table}')
    else:
        print(f'{table}: non esistente')

conn.commit()
print('VACUUM in corso...')
cur.execute('VACUUM')
conn.close()
print('Reset completato!')
