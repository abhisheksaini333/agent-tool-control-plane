import pytest
from helpers import make_control, submit, ALICE


def test_identical_retry_returns_original_request_without_new_audit():
    control = make_control()
    first = submit(control)
    assert submit(control, now=200) == first
    assert len(control.store.list("acme", "requests")) == 1
    assert len(control.audit.list("acme")) == 1


def test_key_cannot_be_reused_for_changed_arguments():
    control = make_control()
    first = submit(control)
    with pytest.raises(ValueError):
        control.submit(
            ALICE,
            "inventory.reserve",
            "1.0.0",
            {"sku": "SKU-1", "quantity": 3},
            "request-1",
            101,
        )
    assert (
        control.store.get("acme", "requests", first["id"])["arguments"]["quantity"] == 2
    )
