from test_api_requests import api


def test_large_bodies_are_rejected_before_json_parsing(api):
    client, control = api
    response = client.post(
        "/api/requests",
        headers={
            "Authorization": "Bearer alice-token",
            "Content-Type": "application/json",
        },
        content=b"x" * 65537,
    )
    assert response.status_code == 413
    assert control.store.list("acme", "requests") == []


def test_api_security_headers_and_exact_origin_preflight(api):
    client, _ = api
    response = client.get("/health")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-request-id"]
    allowed = client.options(
        "/api/requests",
        headers={
            "Origin": "http://localhost:5294",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,idempotency-key,content-type",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5294"
    denied = client.options(
        "/api/requests",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
