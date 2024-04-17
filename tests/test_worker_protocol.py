import json
import pytest
from keel.protocol import payload_for, verify_reply
from test_receipts import ready
import worker.main as program


def test_worker_reply_must_match_request_and_signed_arguments(tmp_path, monkeypatch):
    _, _, request = ready()
    secret = "inventory-key-with-at-least-32-bytes"
    key = tmp_path / "key"
    key.write_text(secret)
    monkeypatch.setattr(program, "CREDENTIAL_PATH", key)
    payload = payload_for(request)
    reply = program.handle(payload)
    assert verify_reply(request, json.dumps(reply), secret)["quantity"] == 2
    for altered in [
        {**reply, "binding": "f" * 64},
        {**reply, "result": {**reply["result"], "quantity": 3}},
        {**reply, "result": {**reply["result"], "signature": "0" * 64}},
    ]:
        with pytest.raises(ValueError):
            verify_reply(request, json.dumps(altered), secret)


def test_malformed_and_oversized_worker_output_cannot_become_a_receipt():
    _, _, request = ready()
    for text in ["not json", "{}", "x" * 65537, '{"protocol":1,"protocol":2}']:
        with pytest.raises(ValueError):
            verify_reply(request, text, "secret")
