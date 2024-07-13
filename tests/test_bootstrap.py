import pytest
from keel.bootstrap import seed_demo
from keel.store import Store
from keel.accounts import Accounts


def test_demo_bootstrap_is_explicit_and_does_not_reset_revocations_or_inventory():
    store = Store()
    with pytest.raises(PermissionError):
        seed_demo(store, enabled=False)
    seed_demo(store, enabled=True)
    users = store.list("acme", "accounts")
    alice = next(user for user in users if user["display_name"] == "Alice Chen")
    Accounts(store).revoke("acme", alice["subject"])
    with store.transaction():
        stock = store.get("acme", "inventory", "KIT-EDGE")
        stock["available"] = 3
        store.put("acme", "inventory", "KIT-EDGE", stock)
    count = len(store.list("acme", "audit"))
    seed_demo(store, enabled=True)
    assert not store.get("acme", "accounts", alice["subject"])["enabled"]
    assert store.get("acme", "inventory", "KIT-EDGE")["available"] == 3
    assert len(store.list("acme", "audit")) == count
    assert len(store.list("acme", "active_tools")) == 3
