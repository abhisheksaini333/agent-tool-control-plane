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
                cursor.execute(
                    sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
                )
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
        receipt = execution.complete(
            "acme", request["id"], claimed["lease"], {"ok": True}, 103
        )
        assert receipt["effect"]["available_after"] == 8
        assert store.get("acme", "requests", request["id"])["status"] == "completed"
    finally:
        other.close()


def test_two_database_connections_cannot_claim_or_complete_twice(pg):
    from concurrent.futures import ThreadPoolExecutor

    store, url, schema = pg
    control = make_control(store)
    request = submit(control)
    control.approve(BOB, request["id"], request["binding"], 1, 101)
    Inventory(store).provision("acme", "SKU-1", 10)
    other = PostgresStore(url, schema)
    executions = [Execution(control), Execution(Control(other, FixturePolicy()))]

    def claim(index):
        try:
            return executions[index].claim(
                "acme", request["id"], f"worker-{index}", 102
            )
        except ValueError:
            return None

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, [0, 1]))
        assert sum(result is not None for result in results) == 1
        winner = next(result for result in results if result)
        first = executions[0].complete(
            "acme", request["id"], winner["lease"], {"ok": True}, 103
        )
        second = executions[1].complete(
            "acme", request["id"], winner["lease"], {"ok": True}, 104
        )
        assert first == second and Inventory(store).list("acme")[0]["available"] == 8
    finally:
        other.close()


def test_database_error_after_effect_rolls_back_stock_and_receipt(pg):
    store, url, schema = pg
    control = make_control(store)
    request = submit(control)
    control.approve(BOB, request["id"], request["binding"], 1, 101)
    Inventory(store).provision("acme", "SKU-1", 10)
    execution = Execution(control)
    claimed = execution.claim("acme", request["id"], "worker", 102)
    original = store.put

    def simulate_connection_fault(tenant, kind, key, body):
        if kind == "receipts":
            raise RuntimeError("Injected crash between local effect and receipt")
        original(tenant, kind, key, body)

    store.put = simulate_connection_fault
    try:
        with pytest.raises(RuntimeError):
            execution.complete(
                "acme", request["id"], claimed["lease"], {"ok": True}, 103
            )
    finally:
        store.put = original
    assert Inventory(store).list("acme")[0]["available"] == 10
    assert store.list("acme", "receipts") == []
    receipt = execution.complete(
        "acme", request["id"], claimed["lease"], {"ok": True}, 104
    )
    assert receipt["effect"]["available_after"] == 8
