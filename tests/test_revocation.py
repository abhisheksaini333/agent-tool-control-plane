import pytest
from helpers import make_control, submit, BOB, ALICE


def test_reviewer_can_revoke_pending_approval_and_execution_is_denied():
    control = make_control()
    request = submit(control)
    request = control.approve(BOB, request["id"], request["binding"], 1, 101)
    revoked = control.revoke(BOB, request["id"], 2, 102)
    assert revoked["status"] == "revoked" and revoked["approval"]["revoked"]
    with pytest.raises(PermissionError):
        control.authorize_execution(revoked, 103)
    assert control.audit.list("acme")[-1]["action"] == "approval.revoked"


def test_requester_cannot_impersonate_the_reviewer():
    control = make_control()
    request = submit(control)
    request = control.approve(BOB, request["id"], request["binding"], 1, 101)
    with pytest.raises(PermissionError):
        control.revoke(ALICE, request["id"], 2, 102)
