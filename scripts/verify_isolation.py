"""Run actual Docker probes and write a machine-readable acceptance report."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import tempfile
from keel.credentials import CredentialVault
from keel.runner import DockerRunner, WorkerFailure


def verify():
    report = {
        "host_architecture": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "environment": "Docker Linux containers; cgroup v2",
        "probes": {},
    }
    runner = DockerRunner(timeout=15)
    for probe in ["isolation", "cpu"]:
        raw, metrics = runner._invoke({}, command=["python", "/app/probe.py", probe])
        report["probes"][probe] = {"observed": json.loads(raw), "metrics": metrics}
    isolation = report["probes"]["isolation"]["observed"]
    assert isolation["network_denied"] and isolation["root_write_denied"]
    assert isolation["uid"] != 0 and isolation["memory_max"] == 67108864
    assert (
        isolation["no_new_privileges"] == "1"
        and int(isolation["effective_capabilities"], 16) == 0
    )
    cpu = report["probes"]["cpu"]["observed"]
    assert cpu["cpu_max"] == "25000 100000" and cpu["throttled_periods"] > 0
    assert cpu["cpu_seconds"] < cpu["wall_seconds"] * 0.6
    for probe, timeout, expected in [
        ("memory", 15, "resource_limit"),
        ("sleep", 3, "worker_timeout"),
    ]:
        runner = DockerRunner(timeout=timeout)
        try:
            runner._invoke({}, command=["python", "/app/probe.py", probe])
            raise AssertionError("Probe should be stopped")
        except WorkerFailure as error:
            assert error.code == expected
        report["probes"][probe] = runner.last_execution
        assert (
            subprocess.run(
                ["docker", "inspect", runner.last_execution["name"]],
                capture_output=True,
            ).returncode
            != 0
        )
    assert report["probes"]["memory"]["oom_killed"]
    with tempfile.TemporaryDirectory(prefix="keel-vault-probe-") as root:
        secret = secrets.token_hex(32)
        path = Path(root, "report-signing")
        path.write_text(secret)
        path.chmod(0o600)
        vault = CredentialVault(root)
        with vault.materialize("report-signing") as (directory, value):
            raw, metrics = DockerRunner(timeout=15)._invoke(
                {}, directory, command=["python", "/app/probe.py", "credentials"]
            )
        observed = json.loads(raw)
        assert (
            observed["files"] == ["key"] and not observed["credential_in_environment"]
        )
        assert not any(observed["forbidden_paths"].values())
        assert observed["key_sha256"] == hashlib.sha256(secret.encode()).hexdigest()
        report["probes"]["credentials"] = {"observed": observed, "metrics": metrics}
    report["passed"] = True
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(verify(), indent=2) + "\n")
    print("Actual isolation probes passed; report:", args.output)
