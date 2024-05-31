from test_api_requests import api
from test_api_approval import create


def test_http_cancel_checks_revision_and_approval_cannot_follow(api):
    client, _ = api
    request = create(client)
    path = f'/api/requests/{request["id"]}'
    assert (
        client.post(
            path + "/cancel",
            headers={"Authorization": "Bearer alice-token"},
            json={"revision": 2},
        ).status_code
        == 409
    )
    cancelled = client.post(
        path + "/cancel",
        headers={"Authorization": "Bearer alice-token"},
        json={"revision": 1},
    )
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert (
        client.post(
            path + "/approval",
            headers={"Authorization": "Bearer bob-token"},
            json={"binding": request["binding"], "revision": 2},
        ).status_code
        == 409
    )


def test_http_reviewer_revokes_approved_work(api):
    client, _ = api
    request = create(client)
    path = f'/api/requests/{request["id"]}'
    headers = {"Authorization": "Bearer bob-token"}
    client.post(
        path + "/approval",
        headers=headers,
        json={"binding": request["binding"], "revision": 1},
    ).raise_for_status()
    response = client.post(path + "/revoke", headers=headers, json={"revision": 2})
    assert response.status_code == 200 and response.json()["status"] == "revoked"
