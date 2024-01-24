import pytest
from keel.audit import Audit, redact
from keel.store import Store


def test_nested_credentials_and_known_secret_values_are_redacted():
    original = {"authorization": "Bearer abc", "nested": [{"api_key": "abc", "message": "failed using secret-value"}]}
    clean = redact(original, ["secret-value"])
    assert clean["authorization"] == "[redacted]"
    assert clean["nested"][0] == {"api_key": "[redacted]", "message": "failed using [redacted]"}
    assert original["authorization"] == "Bearer abc"


def test_audit_chain_is_transactional_and_tenant_scoped():
    store = Store()
    audit = Audit(store)
    with store.transaction():
        audit.append("acme", "alice", "request.created", "r1", {"digest": "abc"}, 1)
        audit.append("acme", "bob", "request.approved", "r1", {}, 2)
    events = audit.list("acme")
    assert [e["sequence"] for e in events] == [1, 2]
    assert events[1]["previous"] == events[0]["hash"] and audit.verify("acme")
    assert audit.list("other") == []
    with pytest.raises(ValueError):
        with store.transaction():
            audit.append("acme", "alice", "test", "r1", {}, 3)
            raise ValueError("rollback")
    assert len(audit.list("acme")) == 2
