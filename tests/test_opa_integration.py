"""Actual OPA binary integration; set OPA_BIN or install opa on PATH."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import httpx
import pytest
from keel.identity import Actor
from keel.policy import OpaPolicy


@pytest.fixture(scope="module")
def opa():
    binary = os.environ.get("OPA_BIN") or shutil.which("opa")
    if not binary:
        pytest.skip("Actual OPA binary not installed")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    process = subprocess.Popen([binary, "run", "--server", "--addr", f"127.0.0.1:{port}", str(Path(__file__).resolve().parents[1] / "policy/control.rego")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client = httpx.Client(timeout=0.2, trust_env=False)
    try:
        for _ in range(50):
            try:
                if client.get(base + "/health").is_success:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        else:
            pytest.fail("OPA did not become healthy")
        policy = OpaPolicy(base)
        yield policy
        policy.close()
    finally:
        client.close()
        process.terminate()
        process.wait(timeout=5)


def test_actual_opa_requires_independent_approval(opa):
    tool = {"handler": "reserve_inventory", "risk": "effect"}
    alice = Actor("acme", "alice", frozenset({"operator", "approver"}))
    bob = Actor("acme", "bob", frozenset({"approver"}))
    assert opa.evaluate(alice, tool) == {"allow": True, "requires_approval": True, "revision": "keel-2024.1"}
    assert not opa.evaluate(alice, tool, "approve", "alice")["allow"]
    assert opa.evaluate(bob, tool, "approve", "alice")["allow"]


def test_actual_opa_rejects_forged_handler_risk_and_missing_roles(opa):
    alice = Actor("acme", "alice", frozenset({"operator"}))
    assert not opa.evaluate(alice, {"handler": "reserve_inventory", "risk": "read"})["allow"]
    guest = Actor("acme", "guest", frozenset())
    assert not opa.evaluate(guest, {"handler": "sha256", "risk": "read"})["allow"]
