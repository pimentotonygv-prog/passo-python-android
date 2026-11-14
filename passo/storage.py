"""SQLite IPC: UI and Android service have separate processes/connections."""
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, folder):
        Path(folder).mkdir(parents=True, exist_ok=True)
        self.path = str(Path(folder)/'passo.sqlite3')
        with self.connect() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS history(id TEXT PRIMARY KEY, date INTEGER, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS commands(id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def get(self, key, fallback=None):
        with self.connect() as c:
            row = c.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else fallback

    def set(self, key, value):
        with self.connect() as c:
            c.execute('INSERT OR REPLACE INTO state VALUES (?,?)', (key, json.dumps(value)))

    def checkpoint(self, active):
        with self.connect() as c:
            for k, v in [('active', active), ('heartbeat', time.time())]:
                c.execute('INSERT OR REPLACE INTO state VALUES (?,?)', (k, json.dumps(v)))

    def archive(self, active):
        # History insertion and clearing active are one transaction.
        with self.connect() as c:
            c.execute('INSERT OR REPLACE INTO history VALUES (?,?,?)',
                      (active['id'], active['date'], json.dumps(active)))
            c.execute("INSERT OR REPLACE INTO state VALUES ('active','{}')")

    def history(self):
        with self.connect() as c:
            return [json.loads(r[0]) for r in c.execute('SELECT value FROM history ORDER BY date DESC')]

    def delete(self, identity):
        with self.connect() as c:
            c.execute('DELETE FROM history WHERE id=?', (identity,))

    def command(self, action, **kwargs):
        with self.connect() as c:
            c.execute('INSERT INTO commands(value) VALUES (?)', (json.dumps(dict(action=action, **kwargs)),))

    def commands(self):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            rows = c.execute('SELECT id,value FROM commands ORDER BY id').fetchall()
            if rows:
                c.execute('DELETE FROM commands WHERE id<=?', (rows[-1][0],))
            return [json.loads(r[1]) for r in rows]
