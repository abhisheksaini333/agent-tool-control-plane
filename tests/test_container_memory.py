import os
import pytest
from keel.runner import DockerRunner, WorkerFailure

pytestmark = pytest.mark.skipif(
    os.environ.get("KEEL_DOCKER_TESTS") != "1", reason="Actual Docker memory probe"
)


def test_actual_memory_exhaustion_is_confined_to_worker_cgroup():
    runner = DockerRunner(timeout=10)
    with pytest.raises(WorkerFailure) as error:
        runner._invoke({}, command=["python", "/app/probe.py", "memory"])
    assert error.value.code == "resource_limit"
    assert runner.last_execution["oom_killed"] is True
    assert runner.last_execution["memory_bytes"] == 67108864
    assert runner.last_execution["exit_code"] == 137
