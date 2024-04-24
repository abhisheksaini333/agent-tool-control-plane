import json
import os
import pytest
from keel.runner import DockerRunner

pytestmark = pytest.mark.skipif(
    os.environ.get("KEEL_DOCKER_TESTS") != "1", reason="Actual Docker isolation probes"
)


def test_actual_worker_cannot_write_root_or_reach_external_network():
    runner = DockerRunner(timeout=8)
    raw, measured = runner._invoke({}, command=["python", "/app/probe.py", "isolation"])
    report = json.loads(raw)
    assert report["uid"] != 0
    assert report["root_write_denied"] and report["network_denied"]
    assert report["memory_max"] == 67108864 and report["pids_max"] == 32
    assert report["nofile"] == [64, 64]
    assert report["no_new_privileges"] == "1"
    assert report["effective_capabilities"] == "0000000000000000"
