"""Transactional reference store; PostgreSQL uses the same document contract."""
from contextlib import contextmanager
import json
import sqlite3
import threading
from .canonical import canonical

DDL = """CREATE TABLE IF NOT EXISTS documents (
    tenant TEXT NOT NULL, kind TEXT NOT NULL, key TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY (tenant, kind, key)
)"""


class Store:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False, timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(DDL)
        self.lock = threading.RLock()
        self.local = threading.local()

    @contextmanager
    def transaction(self):
        with self.lock:
            if getattr(self.local, "active", False):
                raise RuntimeError("Nested transactions are not supported")
            self.db.execute("BEGIN IMMEDIATE")
            self.local.active = True
            try:
                yield self
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            finally:
                self.local.active = False

    def _write_required(self):
        if not getattr(self.local, "active", False):
            raise RuntimeError("Mutation requires a transaction")

    def get(self, tenant, kind, key):
        with self.lock:
            row = self.db.execute("SELECT body FROM documents WHERE tenant=? AND kind=? AND key=?", (tenant, kind, key)).fetchone()
            return json.loads(row[0]) if row else None

    def list(self, tenant, kind):
        with self.lock:
            rows = self.db.execute("SELECT body FROM documents WHERE tenant=? AND kind=? ORDER BY key", (tenant, kind)).fetchall()
            return [json.loads(row[0]) for row in rows]

    def put(self, tenant, kind, key, body):
        self._write_required()
        self.db.execute("INSERT INTO documents(tenant,kind,key,body) VALUES(?,?,?,?) ON CONFLICT(tenant,kind,key) DO UPDATE SET body=excluded.body", (tenant, kind, key, canonical(body)))

    def close(self):
        with self.lock:
            self.db.close()
