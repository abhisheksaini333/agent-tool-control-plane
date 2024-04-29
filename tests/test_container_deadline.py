import os
import subprocess
import time
import pytest
from keel.runner import DockerRunner, WorkerFailure

pytestmark = pytest.mark.skipif(
    os.environ.get("KEEL_DOCKER_TESTS") != "1", reason="Actual Docker deadline probes"
)


def test_actual_hung_worker_is_stopped_at_deadline_and_removed():
    runner = DockerRunner(timeout=3)
    started = time.monotonic()
    with pytest.raises(WorkerFailure) as error:
        runner._invoke({}, command=["python", "/app/probe.py", "sleep"])
    assert error.value.code == "worker_timeout"
    assert time.monotonic() - started < 12
    assert runner.last_execution["failure"] == "worker_timeout"
    name = runner.last_execution["name"]
    assert (
        subprocess.run(["docker", "inspect", name], capture_output=True).returncode != 0
    )


def test_actual_cancelled_worker_is_removed():
    runner = DockerRunner(timeout=8)
    started = time.monotonic()
    with pytest.raises(WorkerFailure) as error:
        runner._invoke(
            {},
            cancelled=lambda: time.monotonic() - started > 2,
            command=["python", "/app/probe.py", "sleep"],
        )
    assert error.value.code == "cancelled"
    assert (
        subprocess.run(
            ["docker", "inspect", runner.last_execution["name"]], capture_output=True
        ).returncode
        != 0
    )
