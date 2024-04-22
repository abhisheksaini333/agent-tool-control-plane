import os
import pytest
from keel.runner import DockerRunner
from test_registry import MANIFEST
from keel.canonical import digest


def hash_request():
    return {
        "id": "hash-one",
        "tenant": "acme",
        "binding": "a" * 64,
        "tool": {**MANIFEST, "risk": "read", "credential": None},
        "arguments": {"text": "hello"},
    }


def test_worker_configuration_denies_network_and_privileged_resources():
    runner = DockerRunner()
    command = runner.create_command("keel-test", None)
    for flag in [
        "--read-only",
        "--cap-drop=ALL",
        "--network=none",
        "--security-opt=no-new-privileges",
        "--memory=64m",
        "--memory-swap=64m",
        "--cpus=0.25",
        "--pids-limit=32",
    ]:
        assert flag in command
    assert "docker.sock" not in " ".join(command)


@pytest.mark.skipif(
    os.environ.get("KEEL_DOCKER_TESTS") != "1", reason="Actual Docker opt-in"
)
def test_actual_worker_hashes_in_restricted_container():
    runner = DockerRunner()
    reply = runner.run(hash_request())
    assert (
        reply["result"]["sha256"]
        == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )
    assert reply["metrics"]["exit_code"] == 0
    assert runner.last_execution["network"] == "none"
    assert runner.last_execution["memory_bytes"] == 67108864
