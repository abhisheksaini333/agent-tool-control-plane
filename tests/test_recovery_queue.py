from test_leases import queued
from keel.execution import Execution


def test_expired_final_attempt_is_terminal_without_reclaiming_live_workers():
    control, request = queued()
    execution = Execution(control)
    for now in [102, 163, 224]:
        claimed = execution.claim("acme", request["id"], "worker", now)
    assert execution.ready("acme", 250) == []
    assert control.store.get("acme", "requests", request["id"])["status"] == "running"
    assert execution.ready("acme", 285) == []
    final = control.store.get("acme", "requests", request["id"])
    assert final["status"] == "failed" and final["error"] == "attempts_exhausted"


def test_expired_approval_is_not_left_in_the_ready_queue():
    control, request = queued()
    execution = Execution(control)
    assert execution.ready("acme", 200)[0]["id"] == request["id"]
    assert execution.ready("acme", 401) == []
    assert control.store.get("acme", "requests", request["id"])["status"] == "expired"
