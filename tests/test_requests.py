import pytest
from keel.control import Control
from helpers import make_control, submit, ALICE, BOB


def test_submission_binds_caller_tool_arguments_and_expiry():
    control = make_control()
    request = submit(control)
    assert request["status"] == "awaiting_approval"
    assert request["caller"] == ALICE.subject and request["tenant"] == ALICE.tenant
    assert request["tool"]["version"] == "1.0.0" and request["arguments_digest"]
    assert request["expires_at"] == 3700 and request["approval"] is None
    assert control.audit.verify("acme")


def test_submission_rejects_wrong_role_version_and_arguments():
    control = make_control()
    with pytest.raises(PermissionError):
        control.submit(BOB, "inventory.reserve", "1.0.0", {"sku": "S", "quantity": 1}, "one", 100)
    with pytest.raises(ValueError):
        control.submit(ALICE, "inventory.reserve", "2.0.0", {"sku": "S", "quantity": 1}, "one", 100)
    with pytest.raises(ValueError):
        control.submit(ALICE, "inventory.reserve", "1.0.0", {"sku": "S", "quantity": True}, "one", 100)
    assert control.store.list("acme", "requests") == []
