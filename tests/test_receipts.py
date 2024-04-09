import pytest
from helpers import ALICE, BOB
from test_leases import queued
from keel.execution import Execution
from keel.inventory import Inventory


def ready():
    control, request = queued()
    Inventory(control.store).provision("acme", "SKU-1", 10)
    execution = Execution(control)
    claimed = execution.claim("acme", request["id"], "worker-a", 102)
    return control, execution, claimed


def test_effect_and_receipt_commit_once_and_completion_retry_is_idempotent():
    control, execution, request = ready()
    result = {"checked": True}
    first = execution.complete("acme", request["id"], request["lease"], result, 103)
    assert (
        execution.complete("acme", request["id"], request["lease"], result, 104)
        == first
    )
    assert first["effect"]["quantity"] == 2
    assert Inventory(control.store).list("acme")[0]["available"] == 8
    assert len(control.store.list("acme", "receipts")) == 1
    assert control.get(ALICE, request["id"])["status"] == "completed"


def test_cancel_and_revoke_before_completion_prevent_the_effect():
    for action in ["cancel", "revoke"]:
        control, execution, request = ready()
        getattr(control, action)(
            ALICE if action == "cancel" else BOB,
            request["id"],
            request["revision"],
            103,
        )
        with pytest.raises(ValueError):
            execution.complete("acme", request["id"], request["lease"], {}, 104)
        assert Inventory(control.store).list("acme")[0]["available"] == 10


def test_stale_worker_and_changed_completion_cannot_commit():
    control, execution, old = ready()
    new = execution.claim("acme", old["id"], "worker-b", 163)
    with pytest.raises(ValueError):
        execution.complete("acme", old["id"], old["lease"], {}, 164)
    execution.complete("acme", new["id"], new["lease"], {"ok": True}, 164)
    with pytest.raises(ValueError):
        execution.complete("acme", new["id"], new["lease"], {"ok": False}, 165)
    with pytest.raises(ValueError):
        control.cancel(ALICE, new["id"], control.get(ALICE, new["id"])["revision"], 165)
