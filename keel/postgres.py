"""PostgreSQL document adapter with cross-process transaction serialization.

This bounded demo serializes mutations using an advisory transaction lock.
The lock is released by PostgreSQL on commit, rollback or connection death.
"""
import threading
import psycopg2
from psycopg2 import sql
from .store import Store, DDL


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, url, schema):
        self.raw = psycopg2.connect(url, connect_timeout=5)
        self.raw.autocommit = True
        with self.raw.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
            )
            cursor.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            cursor.execute("SET statement_timeout = '10s'")
            cursor.execute("SET lock_timeout = '5s'")

    def execute(self, query, arguments=()):
        with self.raw.cursor() as cursor:
            if query == "BEGIN IMMEDIATE":
                cursor.execute("BEGIN")
                try:
                    cursor.execute("SELECT pg_advisory_xact_lock(2024015484)")
                except BaseException:
                    self.raw.rollback()
                    raise
            else:
                cursor.execute(query.replace("?", "%s"), arguments)
            return Rows(cursor.fetchall() if cursor.description else [])

    def close(self):
        self.raw.close()


class PostgresStore(Store):
    def __init__(self, url, schema="public"):
        self.db = Connection(url, schema)
        self.lock = threading.RLock()
        self.local = threading.local()
        self.db.execute(DDL)
