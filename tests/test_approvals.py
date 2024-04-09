import pytest
from helpers import make_control, submit, ALICE, BOB, ADMIN
from keel.identity import Actor


def test_approval_binds_exact_request_and_independent_reviewer():
    control = make_control()
    request = submit(control)
    approved = control.approve(BOB, request["id"], request["binding"], 1, 101)
    assert approved["status"] == "queued" and approved["approval"]["subject"] == "bob"
    assert approved["approval"]["binding"] == request["binding"]
    assert approved["approval"]["expires_at"] == 401
    assert approved["revision"] == 2


def test_changed_binding_stale_revision_and_repeat_are_rejected():
    control = make_control()
    request = submit(control)
    for binding, revision in [("f" * 64, 1), (request["binding"], 99)]:
        with pytest.raises(ValueError):
            control.approve(BOB, request["id"], binding, revision, 101)
    approved = control.approve(BOB, request["id"], request["binding"], 1, 101)
    with pytest.raises(ValueError):
        control.approve(
            BOB, request["id"], request["binding"], approved["revision"], 102
        )


def test_cross_tenant_and_self_approval_are_denied():
    control = make_control()
    request = submit(control)
    control.accounts.provision("other", "bob", {"approver"})
    with pytest.raises(LookupError):
        control.approve(
            Actor("other", "bob", frozenset({"approver"})),
            request["id"],
            request["binding"],
            1,
            101,
        )
    control.accounts.provision("acme", "alice", {"operator", "approver"})
    with pytest.raises((ValueError, PermissionError)):
        control.approve(
            Actor("acme", "alice", frozenset({"operator", "approver"})),
            request["id"],
            request["binding"],
            1,
            101,
        )
