"""Actual PostgreSQL persistence tests. KEEL_TEST_DATABASE_URL is opt-in."""
import os
import uuid
import pytest
from keel.postgres import PostgresStore
from keel.control import Control
from keel.execution import Execution
from keel.inventory import Inventory
from helpers import make_control, submit, BOB, FixturePolicy


@pytest.fixture
def pg():
    url = os.environ.get("KEEL_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Actual PostgreSQL test URL not configured")
    schema = "keeltest_" + uuid.uuid4().hex
    store = PostgresStore(url, schema)
    try:
        yield store, url, schema
    finally:
        from psycopg2 import connect, sql
        with connect(url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        store.close()


def test_postgres_reopens_requests_and_commits_one_effect(pg):
    store, url, schema = pg
    control = make_control(store)
    request = submit(control)
    control.approve(BOB, request["id"], request["binding"], 1, 101)
    Inventory(store).provision("acme", "SKU-1", 10)
    other = PostgresStore(url, schema)
    try:
        execution = Execution(Control(other, FixturePolicy()))
        claimed = execution.claim("acme", request["id"], "worker", 102)
        receipt = execution.complete("acme", request["id"], claimed["lease"], {"ok": True}, 103)
        assert receipt["effect"]["available_after"] == 8
        assert store.get("acme", "requests", request["id"])["status"] == "completed"
    finally:
        other.close()
