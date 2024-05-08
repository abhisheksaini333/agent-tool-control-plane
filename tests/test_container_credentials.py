import hashlib
import json
import os
import pytest
from keel.credentials import CredentialVault
from keel.runner import DockerRunner
from test_receipts import ready

pytestmark = pytest.mark.skipif(
    os.environ.get("KEEL_DOCKER_TESTS") != "1", reason="Actual Docker credential probes"
)


def test_only_one_private_credential_is_visible_without_environment_leak(tmp_path):
    secrets = {
        "report-signing": "report-private-key-" + "r" * 32,
        "inventory-signing": "inventory-private-key-" + "i" * 32,
    }
    for alias, secret in secrets.items():
        path = tmp_path / alias
        path.write_text(secret)
        path.chmod(0o600)
    vault = CredentialVault(tmp_path)
    runner = DockerRunner(vault, timeout=15)
    with vault.materialize("report-signing") as (directory, secret):
        raw, _ = runner._invoke(
            {}, directory, command=["python", "/app/probe.py", "credentials"]
        )
    report = json.loads(raw)
    assert report["files"] == ["key"] and not report["credential_in_environment"]
    assert (
        report["key_sha256"]
        == hashlib.sha256(secrets["report-signing"].encode()).hexdigest()
    )
    assert not any(report["forbidden_paths"].values())
    _, _, request = ready()
    result = runner.run(request)
    assert result["result"]["quantity"] == 2 and result["result"]["signature"]
    assert all(secret not in json.dumps(result) for secret in secrets.values())
