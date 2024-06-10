from test_api_requests import api
from test_api_approval import create
from keel.execution import Execution
from keel.inventory import Inventory
from helpers import BOB


def test_operator_views_hide_worker_tokens_and_expose_request_audit(api):
    client, control = api
    request = create(client)
    control.approve(BOB, request["id"], request["binding"], 1, 100)
    claimed = Execution(control).claim("acme", request["id"], "worker", 100)
    headers = {"Authorization": "Bearer alice-token"}
    response = client.get(f'/api/requests/{request["id"]}', headers=headers)
    assert claimed["lease"]["token"] not in response.text
    assert "credential" not in response.json()["tool"]
    events = client.get(f'/api/requests/{request["id"]}/audit', headers=headers)
    assert events.status_code == 200
    assert events.json()[-1]["action"] == "execution.claimed"
    assert client.get("/api/audit", headers=headers).status_code == 403


def test_inventory_view_is_scoped_to_authenticated_tenant(api):
    client, control = api
    Inventory(control.store).provision("acme", "SKU-1", 10)
    Inventory(control.store).provision("north", "PRIVATE", 99)
    response = client.get(
        "/api/inventory", headers={"Authorization": "Bearer alice-token"}
    )
    assert response.status_code == 200
    assert response.json() == [{"sku": "SKU-1", "available": 10}]
