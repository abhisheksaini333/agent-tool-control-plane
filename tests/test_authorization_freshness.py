import pytest
from helpers import make_control, submit, BOB, ADMIN


def approved():
    control = make_control()
    request = submit(control)
    return control, control.approve(BOB, request["id"], request["binding"], 1, 101)


def test_approval_expiry_and_revoked_reviewer_are_rechecked():
    control, request = approved()
    control.authorize_execution(request, 200)
    with pytest.raises(PermissionError):
        control.authorize_execution(request, 401)
    control.accounts.revoke("acme", "bob")
    control.accounts.provision("acme", "bob", {"approver"})
    with pytest.raises(PermissionError):
        control.authorize_execution(request, 200)


def test_tool_reactivation_policy_change_and_argument_edits_invalidate_binding():
    control, request = approved()
    altered = {**request, "arguments": {"sku": "SKU-1", "quantity": 3}}
    with pytest.raises(ValueError):
        control.authorize_execution(altered, 200)
    control.policy.revision = "changed"
    with pytest.raises(PermissionError):
        control.authorize_execution(request, 200)
    control.policy.revision = "fixture-policy-1"
    control.registry.disable(ADMIN, "inventory.reserve")
    control.registry.activate(ADMIN, "inventory.reserve", "1.0.0")
    with pytest.raises(ValueError):
        control.authorize_execution(request, 200)
