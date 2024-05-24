from fastapi.testclient import TestClient
import pytest
from keel.api import create_app
from keel.auth import AuthenticationError
from keel.settings import Settings
from helpers import make_control, ALICE, BOB


class FixtureVerifier:
    def verify(self, token):
        if token == "alice-token":
            return ALICE
        if token == "bob-token":
            return BOB
        raise AuthenticationError("Invalid token")


@pytest.fixture
def api():
    control = make_control()
    app = create_app(
        control,
        FixtureVerifier(),
        Settings.from_env({"KEEL_LOCAL_DEMO": "1"}),
        clock=lambda: 100,
    )
    return TestClient(app), control


def test_api_requires_identity_and_uses_verified_caller(api):
    client, control = api
    assert client.get("/api/requests").status_code == 401
    assert (
        client.get("/api/me", headers={"Authorization": "Bearer invalid"}).status_code
        == 401
    )
    headers = {"Authorization": "Bearer alice-token", "Idempotency-Key": "request-one"}
    response = client.post(
        "/api/requests",
        headers=headers,
        json={
            "tool": "inventory.reserve",
            "version": "1.0.0",
            "arguments": {"sku": "SKU-1", "quantity": 2},
        },
    )
    assert response.status_code == 201
    request = response.json()
    assert request["caller"] == "alice" and request["status"] == "awaiting_approval"
    assert client.get("/api/requests", headers=headers).json()[0]["id"] == request["id"]


def test_api_rejects_caller_injection_and_redacts_validation_values(api):
    client, control = api
    response = client.post(
        "/api/requests",
        headers={"Authorization": "Bearer alice-token", "Idempotency-Key": "one"},
        json={
            "tool": "inventory.reserve",
            "version": "1.0.0",
            "arguments": {},
            "caller": "secret-admin-value",
        },
    )
    assert response.status_code == 422
    assert "secret-admin-value" not in response.text
    assert control.store.list("acme", "requests") == []
