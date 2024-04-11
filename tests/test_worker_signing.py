import hashlib
import hmac
import json
import pytest
import worker.main as program
from test_worker_program import message


def test_signing_uses_mounted_credential_without_returning_it(tmp_path, monkeypatch):
    key = b"report-key-with-more-than-32-bytes"
    path = tmp_path / "key"
    path.write_bytes(key)
    monkeypatch.setattr(program, "CREDENTIAL_PATH", path)
    request = message("sign_report")
    reply = program.handle(request)
    expected = hmac.new(
        key,
        json.dumps(
            request, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode(),
        hashlib.sha256,
    ).hexdigest()
    assert reply["result"]["signature"] == expected
    assert key.decode() not in json.dumps(reply)
    changed = {**request, "tenant": "other"}
    assert program.handle(changed)["result"]["signature"] != expected


def test_signing_fails_without_a_strong_credential(tmp_path, monkeypatch):
    path = tmp_path / "missing"
    monkeypatch.setattr(program, "CREDENTIAL_PATH", path)
    with pytest.raises(OSError):
        program.handle(message("sign_report"))
    path.write_text("short")
    with pytest.raises(ValueError):
        program.handle(message("sign_report"))
