"""A separate claimant process exits after commit; a new owner must be fenced."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import pytest
from keel.execution import Execution
from keel.inventory import Inventory
from keel.store import Store
from helpers import ALICE, BOB, make_control
from test_postgres import pg

CHILD = """
import json, os, sys, time
from keel.control import Control
from keel.execution import Execution
from keel.postgres import PostgresStore
from keel.store import Store
from helpers import FixturePolicy
config = json.load(sys.stdin)
store = PostgresStore(config['url'],config['schema']) if config['kind']=='postgres' else Store(config['path'])
execution = Execution(Control(store,FixturePolicy()))
execution.lease_seconds = 0.1  # Test clock budget only; production lease remains60seconds.
execution.claim('acme',config['request_id'],'crashing-worker',time.time())
os._exit(23)
"""


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_process_death_preserves_claim_and_new_owner_rejects_old_completion(
    backend, request, tmp_path
):
    if backend == "postgres":
        store, url, schema = request.getfixturevalue("pg")
        config = {"kind": "postgres", "url": url, "schema": schema}
    else:
        path = tmp_path / "recovery.db"
        store = Store(path)
        config = {"kind": "sqlite", "path": str(path)}
    try:
        control = make_control(store)
        work = control.submit(
            ALICE,
            "inventory.reserve",
            "1.0.0",
            {"sku": "SKU-1", "quantity": 2},
            "process-recovery",
            time.time(),
        )
        control.approve(BOB, work["id"], work["binding"], 1, time.time())
        Inventory(store).provision("acme", "SKU-1", 10)
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join([str(Path.cwd()), str(Path.cwd() / "tests")]),
        }
        child = subprocess.run(
            [sys.executable, "-c", CHILD],
            input=json.dumps({**config, "request_id": work["id"]}),
            text=True,
            capture_output=True,
            timeout=10,
            env=env,
        )
        assert child.returncode == 23, child.stderr
        abandoned = store.get("acme", "requests", work["id"])
        assert abandoned["lease"]["owner"] == "crashing-worker"
        assert abandoned["status"] == "running"
        time.sleep(max(0, abandoned["lease"]["expires_at"] - time.time() + 0.02))
        execution = Execution(control)
        recovered = execution.claim(
            "acme", work["id"], "replacement-worker", time.time()
        )
        assert recovered["attempts"] == 2 and recovered["lease"]["fence"] == 2
        with pytest.raises(ValueError, match="no longer owns"):
            execution.complete(
                "acme", work["id"], abandoned["lease"], {"fixture": True}, time.time()
            )
        receipt = execution.complete(
            "acme", work["id"], recovered["lease"], {"fixture": True}, time.time()
        )
        assert receipt["effect"]["available_after"] == 8
        assert len(store.list("acme", "receipts")) == 1
        assert control.audit.verify("acme")
    finally:
        if backend == "sqlite":
            store.close()
