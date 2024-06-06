from test_api_requests import api, FixtureVerifier
from helpers import ADMIN, MANIFEST


def test_catalog_returns_only_active_tools_and_no_credential_alias(api):
    client, control = api
    response = client.get("/api/tools", headers={"Authorization": "Bearer alice-token"})
    assert response.status_code == 200
    assert response.json()[0]["name"] == "inventory.reserve"
    assert "credential" not in response.json()[0]
    assert response.json()[0]["schema"]["additionalProperties"] is False
    control.registry.disable(ADMIN, "inventory.reserve")
    assert (
        client.get("/api/tools", headers={"Authorization": "Bearer alice-token"}).json()
        == []
    )


def test_registry_mutations_require_current_administrator(api, monkeypatch):
    client, control = api
    original = FixtureVerifier.verify
    monkeypatch.setattr(
        FixtureVerifier,
        "verify",
        lambda self, token: ADMIN if token == "admin-token" else original(self, token),
    )
    body = {**MANIFEST, "version": "1.0.1", "description": "Updated inventory contract"}
    assert (
        client.post(
            "/api/registry", headers={"Authorization": "Bearer alice-token"}, json=body
        ).status_code
        == 403
    )
    created = client.post(
        "/api/registry", headers={"Authorization": "Bearer admin-token"}, json=body
    )
    assert created.status_code == 201
    active = client.post(
        "/api/registry/inventory.reserve/activate",
        headers={"Authorization": "Bearer admin-token"},
        json={"version": "1.0.1"},
    )
    assert active.status_code == 200 and active.json()["generation"] == 2
    control.accounts.revoke("acme", "admin")
    assert (
        client.post(
            "/api/registry/inventory.reserve/disable",
            headers={"Authorization": "Bearer admin-token"},
        ).status_code
        == 403
    )
