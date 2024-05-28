from test_api_requests import api


def create(client):
    return client.post(
        "/api/requests",
        headers={
            "Authorization": "Bearer alice-token",
            "Idempotency-Key": "approval-one",
        },
        json={
            "tool": "inventory.reserve",
            "version": "1.0.0",
            "arguments": {"sku": "SKU-1", "quantity": 2},
        },
    ).json()


def test_http_approval_is_exact_and_rejects_repeat_or_argument_edits(api):
    client, _ = api
    request = create(client)
    path = f'/api/requests/{request["id"]}/approval'
    headers = {"Authorization": "Bearer bob-token"}
    body = {"binding": request["binding"], "revision": request["revision"]}
    assert (
        client.post(
            path, headers=headers, json={**body, "arguments": {"quantity": 3}}
        ).status_code
        == 422
    )
    assert (
        client.post(
            path, headers=headers, json={**body, "binding": "f" * 64}
        ).status_code
        == 409
    )
    approved = client.post(path, headers=headers, json=body)
    assert approved.status_code == 200 and approved.json()["status"] == "queued"
    assert client.post(path, headers=headers, json=body).status_code == 409


def test_http_approval_requires_approver_permission(api):
    client, _ = api
    request = create(client)
    response = client.post(
        f'/api/requests/{request["id"]}/approval',
        headers={"Authorization": "Bearer alice-token"},
        json={"binding": request["binding"], "revision": 1},
    )
    assert response.status_code == 403
