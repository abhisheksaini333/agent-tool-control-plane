import pytest
from keel.store import Store


def test_documents_are_tenant_scoped_and_copied(tmp_path):
    store = Store(tmp_path / "keel.db")
    with store.transaction():
        store.put("acme", "requests", "one", {"status": "queued"})
        store.put("north", "requests", "one", {"status": "secret"})
    value = store.get("acme", "requests", "one")
    value["status"] = "changed"
    assert store.get("acme", "requests", "one")["status"] == "queued"
    assert store.list("north", "requests") == [{"status": "secret"}]
    store.close()
    reopened = Store(tmp_path / "keel.db")
    assert reopened.get("acme", "requests", "one")["status"] == "queued"
    reopened.close()


def test_transaction_rolls_back_and_writes_require_transaction():
    store = Store()
    with pytest.raises(RuntimeError):
        store.put("acme", "requests", "one", {})
    with pytest.raises(ValueError):
        with store.transaction():
            store.put("acme", "requests", "one", {"status": "queued"})
            raise ValueError("rollback")
    assert store.get("acme", "requests", "one") is None
