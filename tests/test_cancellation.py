import pytest
from helpers import make_control, submit, ALICE, BOB
from keel.identity import Actor


def test_requester_cancels_pending_request_and_fences_approval():
    control = make_control()
    request = submit(control)
    cancelled = control.cancel(ALICE, request["id"], 1, 101)
    assert cancelled["status"] == "cancelled" and cancelled["lease"] is None
    with pytest.raises(ValueError):
        control.approve(
            BOB, request["id"], request["binding"], cancelled["revision"], 102
        )


def test_peer_operator_and_stale_cancel_cannot_change_request():
    control = make_control()
    request = submit(control)
    control.accounts.provision("acme", "peer", {"operator"})
    with pytest.raises(PermissionError):
        control.cancel(
            Actor("acme", "peer", frozenset({"operator"})), request["id"], 1, 101
        )
    with pytest.raises(ValueError):
        control.cancel(ALICE, request["id"], 0, 101)
    assert control.get(ALICE, request["id"])["status"] == "awaiting_approval"
