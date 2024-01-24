import pytest
from keel.accounts import Accounts
from keel.identity import Actor
from keel.store import Store


def test_token_roles_are_intersected_with_current_account_permissions():
    accounts = Accounts(Store())
    accounts.provision("acme", "alice", {"operator", "approver"})
    token = Actor("acme", "alice", frozenset({"operator", "administrator"}))
    assert accounts.effective(token).roles == frozenset({"operator"})
    accounts.provision("other", "alice", {"administrator"})
    assert accounts.effective(token).tenant == "acme"
    accounts.revoke("acme", "alice")
    with pytest.raises(PermissionError):
        accounts.effective(token)


def test_stored_caller_cannot_be_restored_by_a_stale_token():
    accounts = Accounts(Store())
    accounts.provision("acme", "alice", {"operator"})
    accounts.revoke("acme", "alice")
    with pytest.raises(PermissionError):
        accounts.current("acme", "alice")
    with pytest.raises(PermissionError):
        accounts.current("acme", "missing")
