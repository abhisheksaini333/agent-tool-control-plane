from helpers import submit, BOB
from test_worker_loop import approved_control, FixtureRunner
from keel.worker import Worker
from keel.policy import PolicyUnavailable


def test_policy_outage_defers_one_candidate_without_stopping_other_work():
    control, first = approved_control()
    second = submit(control, "second", 100.5)
    control.approve(BOB, second["id"], second["binding"], 1, 101)
    original = control.policy.evaluate
    calls = [0]

    def once_unavailable(*args, **kwargs):
        calls[0] += 1
        if calls[0] == 1:
            raise PolicyUnavailable("offline")
        return original(*args, **kwargs)

    control.policy.evaluate = once_unavailable
    now = [102]
    runner = FixtureRunner()
    worker = Worker(control, runner, ["acme"], clock=lambda: now[0])
    assert worker.once()
    assert control.store.get("acme", "requests", first["id"])["status"] == "retry_wait"
    assert control.store.get("acme", "requests", second["id"])["status"] == "completed"
    now[0] = 105
    assert worker.once() and runner.calls == 2
    assert control.store.get("acme", "requests", first["id"])["status"] == "completed"


def test_revoked_caller_is_closed_without_running_or_repolling_forever():
    control, request = approved_control()
    control.accounts.revoke("acme", "alice")
    runner = FixtureRunner()
    worker = Worker(control, runner, ["acme"], clock=lambda: 102)
    assert not worker.once()
    assert control.store.get("acme", "requests", request["id"])["status"] == "rejected"
    assert runner.calls == 0
