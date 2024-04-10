import hashlib
import json
from pathlib import Path
import subprocess
import sys

WORKER = Path(__file__).resolve().parents[1] / "worker/main.py"


def message(handler="sha256", arguments=None):
    return {
        "protocol": 1,
        "request_id": "request-one",
        "tenant": "acme",
        "binding": "a" * 64,
        "handler": handler,
        "arguments": arguments or {"text": "hello"},
    }


def invoke(payload):
    return subprocess.run(
        [sys.executable, str(WORKER)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def test_standalone_worker_hashes_text_with_bound_response():
    result = invoke(message())
    assert result.returncode == 0
    reply = json.loads(result.stdout)
    assert reply["binding"] == "a" * 64 and reply["request_id"] == "request-one"
    assert reply["result"]["sha256"] == hashlib.sha256(b"hello").hexdigest()


def test_worker_rejects_unknown_handlers_and_extra_protocol_fields():
    for payload in [
        message("shell"),
        {**message(), "command": "curl example.org"},
        {**message(), "protocol": 2},
    ]:
        result = invoke(payload)
        assert result.returncode != 0
        assert "Traceback" not in result.stderr
        assert "invalid_request" in result.stdout
