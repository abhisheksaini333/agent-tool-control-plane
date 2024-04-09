import pytest
from test_leases import queued
from keel.execution import Execution


def test_transient_failures_back_off_and_stop_after_three_attempts():
    control, request = queued()
    execution = Execution(control)
    now = 102
    for attempt in range(1, 4):
        claimed = execution.claim("acme", request["id"], "worker", now)
        failed = execution.fail(
            "acme", request["id"], claimed["lease"], "worker_unavailable", now + 1
        )
        if attempt < 3:
            assert failed["status"] == "retry_wait"
            with pytest.raises(ValueError):
                execution.claim("acme", request["id"], "worker", now + 1)
            now = failed["next_attempt_at"]
        else:
            assert failed["status"] == "failed" and failed["attempts"] == 3


def test_losing_worker_cannot_fail_winner_and_permanent_errors_do_not_retry():
    control, request = queued()
    execution = Execution(control)
    first = execution.claim("acme", request["id"], "first", 102)
    second = execution.claim("acme", request["id"], "second", 163)
    assert (
        execution.fail("acme", request["id"], first["lease"], "worker_unavailable", 164)
        is None
    )
    assert control.store.get("acme", "requests", request["id"])["status"] == "running"
    failed = execution.fail(
        "acme", request["id"], second["lease"], "invalid_output", 164
    )
    assert failed["status"] == "failed"
