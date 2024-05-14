"""Actual PostgreSQL + OPA + constrained Docker effect path."""
import os
import secrets
import time
import pytest
from keel.credentials import CredentialVault
from keel.inventory import Inventory
from keel.runner import DockerRunner
from keel.worker import Worker
from helpers import make_control, ALICE, BOB
from test_postgres import pg
from test_opa_integration import opa

pytestmark = pytest.mark.skipif(
    os.environ.get("KEEL_DOCKER_TESTS") != "1", reason="Actual full-stack worker opt-in"
)


def test_real_policy_approval_worker_and_database_commit_one_effect(pg, opa, tmp_path):
    store, _, _ = pg
    control = make_control(store, opa)
    now = time.time()
    request = control.submit(
        ALICE,
        "inventory.reserve",
        "1.0.0",
        {"sku": "SKU-1", "quantity": 2},
        "real-execution",
        now,
    )
    control.approve(BOB, request["id"], request["binding"], 1, time.time())
    Inventory(store).provision("acme", "SKU-1", 10)
    key = tmp_path / "inventory-signing"
    key.write_text(secrets.token_hex(32))
    key.chmod(0o600)
    runner = DockerRunner(CredentialVault(tmp_path), timeout=15)
    worker = Worker(control, runner, ["acme"])
    assert worker.once() and not worker.once()
    completed = control.get(ALICE, request["id"])
    assert completed["status"] == "completed"
    assert completed["receipt"]["output"]["result"]["signature"]
    assert completed["receipt"]["effect"]["available_after"] == 8
    assert len(store.list("acme", "receipts")) == 1
    assert control.audit.verify("acme")
    assert runner.last_execution["network"] == "none"
