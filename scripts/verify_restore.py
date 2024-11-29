"""Read a consistent local snapshot and restore only into a new disposable DB.

The backup remains private at the supplied path. No existing database is replaced.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn, make_dsn
from keel.audit import Audit
from keel.postgres import PostgresStore
from keel.settings import Settings


def fingerprint(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tenant,kind,key,body FROM public.documents ORDER BY tenant,kind,key"
        )
        rows = cursor.fetchall()
    encoded = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()
    return len(rows), hashlib.sha256(encoded).hexdigest()


def verify(database_url, container, backup):
    settings = parse_dsn(database_url)
    if settings.get("host") not in {"127.0.0.1", "localhost"}:
        raise ValueError("Restore verification requires the local demo database")
    source_name = settings.get("dbname", "keel")
    user = settings.get("user", "keel")
    backup = Path(backup)
    backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target_name = "keel_restore_" + uuid.uuid4().hex
    target_url = make_dsn(database_url, dbname=target_name)
    created = False
    source = psycopg2.connect(database_url)
    source.set_session(isolation_level="REPEATABLE READ", readonly=True)
    admin = psycopg2.connect(database_url)
    admin.autocommit = True
    try:
        with source.cursor() as cursor:
            cursor.execute("SELECT pg_export_snapshot()")
            snapshot = cursor.fetchone()[0]
        before_count, before_hash = fingerprint(source)
        descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    container,
                    "pg_dump",
                    "-U",
                    user,
                    "-d",
                    source_name,
                    "--format=custom",
                    "--schema=public",
                    "--no-owner",
                    "--snapshot",
                    snapshot,
                ],
                stdout=output,
                stderr=subprocess.PIPE,
                check=True,
                timeout=60,
            )
        source.rollback()
        with admin.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_name))
            )
            created = True
        # pg_dump includes CREATE SCHEMA public. Remove only the empty schema
        # in the uniquely created target; the source schema is never touched.
        target = psycopg2.connect(target_url)
        try:
            with target.cursor() as cursor:
                cursor.execute("DROP SCHEMA public")
            target.commit()
        finally:
            target.close()
        with backup.open("rb") as stream:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    container,
                    "pg_restore",
                    "-U",
                    user,
                    "-d",
                    target_name,
                    "--no-owner",
                    "--no-privileges",
                    "--exit-on-error",
                ],
                stdin=stream,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=True,
                timeout=60,
            )
        restored = psycopg2.connect(target_url)
        try:
            after_count, after_hash = fingerprint(restored)
        finally:
            restored.close()
        if (before_count, before_hash) != (after_count, after_hash):
            raise AssertionError(
                "Restored documents do not match the exported snapshot"
            )
        store = PostgresStore(target_url)
        try:
            with store.db.raw.cursor() as cursor:
                cursor.execute("SELECT DISTINCT tenant FROM documents")
                tenants = [row[0] for row in cursor.fetchall()]
            receipts = reservations = 0
            for tenant in tenants:
                if not Audit(store).verify(tenant):
                    raise AssertionError("Restored audit chain is invalid")
                for receipt in store.list(tenant, "receipts"):
                    request = store.get(tenant, "requests", receipt["id"])
                    assert (
                        request["status"] == "completed"
                        and request["receipt"] == receipt
                    )
                    if receipt["effect"] is not None:
                        assert (
                            store.get(tenant, "reservations", receipt["id"])
                            == receipt["effect"]
                        )
                    receipts += 1
                reservations += len(store.list(tenant, "reservations"))
        finally:
            store.close()
        return {
            "passed": True,
            "source_database": source_name,
            "disposable_target": target_name,
            "documents": before_count,
            "document_sha256": before_hash,
            "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
            "receipts": receipts,
            "reservations": reservations,
            "checks": {
                "snapshot_equal": True,
                "audit_chains_valid": True,
                "receipt_effect_links_valid": True,
                "source_not_replaced": True,
            },
        }
    finally:
        source.close()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(
                    sql.SQL("DROP DATABASE {}").format(sql.Identifier(target_name))
                )
        admin.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="keel-control-postgres-1")
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings.from_env()
    if not settings.local_demo:
        raise SystemExit("Explicit KEEL_LOCAL_DEMO=1 is required")
    report = verify(settings.database_url, args.container, args.backup)
    report["checks"]["disposable_target_removed"] = True
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("Snapshot restore, document equality and receipt/audit checks passed")
