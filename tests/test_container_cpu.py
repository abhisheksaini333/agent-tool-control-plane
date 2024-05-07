import json
import os
import pytest
from keel.runner import DockerRunner

pytestmark = pytest.mark.skipif(
    os.environ.get("KEEL_DOCKER_TESTS") != "1", reason="Actual Docker CPU probe"
)


def test_actual_busy_loop_is_throttled_by_cpu_quota():
    runner = DockerRunner(timeout=12)
    raw, metrics = runner._invoke({}, command=["python", "/app/probe.py", "cpu"])
    report = json.loads(raw)
    assert report["cpu_max"] == "25000 100000"
    assert report["throttled_periods"] > 0
    assert report["wall_seconds"] >= 3
    assert 0.02 < report["cpu_seconds"] < report["wall_seconds"] * 0.6
