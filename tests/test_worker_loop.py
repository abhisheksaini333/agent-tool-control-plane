from helpers import make_control, submit, BOB
from keel.inventory import Inventory
from keel.worker import Worker
from keel.runner import WorkerFailure


class FixtureRunner:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def run(self, request, cancelled):
        self.calls += 1
        if self.fail:
            raise WorkerFailure("worker_timeout")
        assert not cancelled()
        return {"result": {"fixture": True}}


def approved_control():
    control = make_control()
    request = submit(control)
    control.approve(BOB, request["id"], request["binding"], 1, 101)
    Inventory(control.store).provision("acme", "SKU-1", 10)
    return control, request


def test_worker_claims_runs_and_commits_once():
    control, request = approved_control()
    runner = FixtureRunner()
    worker = Worker(control, runner, ["acme"], clock=lambda: 102)
    assert worker.once()
    assert not worker.once() and runner.calls == 1
    assert control.store.get("acme", "requests", request["id"])["status"] == "completed"
    assert Inventory(control.store).list("acme")[0]["available"] == 8


def test_worker_failure_preserves_business_state_and_schedules_retry():
    control, request = approved_control()
    worker = Worker(control, FixtureRunner(fail=True), ["acme"], clock=lambda: 102)
    assert worker.once()
    assert (
        control.store.get("acme", "requests", request["id"])["status"] == "retry_wait"
    )
    assert Inventory(control.store).list("acme")[0]["available"] == 10
