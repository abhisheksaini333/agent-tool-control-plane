import pytest
from keel.inventory import Inventory
from keel.store import Store


def test_reservation_decrements_stock_once_and_is_tenant_scoped():
    store = Store()
    inventory = Inventory(store)
    inventory.provision("acme", "SKU-1", 10)
    with store.transaction():
        first = inventory.reserve("acme", "request-one", {"sku": "SKU-1", "quantity": 2})
    with store.transaction():
        assert inventory.reserve("acme", "request-one", {"sku": "SKU-1", "quantity": 2}) == first
    assert inventory.list("acme")[0]["available"] == 8
    assert inventory.list("other") == []
    with pytest.raises(ValueError):
        with store.transaction():
            inventory.reserve("acme", "request-one", {"sku": "SKU-1", "quantity": 3})


def test_insufficient_stock_rolls_back_without_a_reservation():
    store = Store()
    inventory = Inventory(store)
    inventory.provision("acme", "SKU-1", 1)
    with pytest.raises(ValueError):
        with store.transaction():
            inventory.reserve("acme", "request-one", {"sku": "SKU-1", "quantity": 2})
    assert inventory.list("acme")[0]["available"] == 1
    assert store.list("acme", "reservations") == []
