import pytest
from helpers import make_control, submit, BOB
from keel.execution import Execution


def queued():
    control = make_control()
    request = submit(control)
    return control, control.approve(BOB, request["id"], request["binding"], 1, 101)


def test_one_worker_claims_a_request_and_owns_its_fencing_token():
    control, request = queued()
    execution = Execution(control)
    claimed = execution.claim("acme", request["id"], "worker-a", 102)
    assert claimed["status"] == "running" and claimed["attempts"] == 1
    assert execution.owns(claimed, claimed["lease"], 103)
    with pytest.raises(ValueError):
        execution.claim("acme", request["id"], "worker-b", 103)
    assert (
        control.store.get("acme", "requests", request["id"])["lease"]["owner"]
        == "worker-a"
    )


def test_expired_lease_can_be_reclaimed_but_old_worker_is_fenced():
    control, request = queued()
    execution = Execution(control)
    old = execution.claim("acme", request["id"], "worker-a", 102)
    new = execution.claim("acme", request["id"], "worker-b", 163)
    assert new["attempts"] == 2 and new["lease"]["fence"] == 2
    assert not execution.owns(new, old["lease"], 164)
    assert execution.owns(new, new["lease"], 164)
