import pytest
import worker.main as program
from test_worker_program import message


def test_inventory_worker_prepares_signed_intent_without_mutating_business_state(
    tmp_path, monkeypatch
):
    key = tmp_path / "key"
    key.write_bytes(b"inventory-signing-material-32bytes")
    monkeypatch.setattr(program, "CREDENTIAL_PATH", key)
    request = message("reserve_inventory", {"sku": "SKU-1", "quantity": 2})
    result = program.handle(request)["result"]
    assert result["sku"] == "SKU-1" and result["quantity"] == 2
    assert len(result["signature"]) == 64
    assert sorted(p.name for p in tmp_path.iterdir()) == ["key"]


@pytest.mark.parametrize(
    "arguments",
    [
        {"sku": "../other", "quantity": 1},
        {"sku": "SKU-1", "quantity": True},
        {"sku": "SKU-1", "quantity": 11},
        {"sku": "SKU-1", "quantity": 1, "admin": True},
    ],
)
def test_inventory_worker_revalidates_its_own_contract(arguments):
    with pytest.raises(ValueError):
        program.handle(message("reserve_inventory", arguments))
