"""Actual Keycloak18 local realm token integration; credentials are demo-only."""
import os
import httpx
import pytest
from keel.auth import JwtVerifier, AuthenticationError
from keel.bootstrap import demo_users

pytestmark = pytest.mark.skipif(
    not os.environ.get("KEEL_TEST_OIDC_ISSUER"),
    reason="Actual Keycloak issuer not configured",
)


def test_actual_keycloak_identity_matches_seed_and_audience_is_enforced():
    issuer = os.environ["KEEL_TEST_OIDC_ISSUER"]
    response = httpx.post(
        issuer + "/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "keel-demo-cli",
            "username": "alice",
            "password": "keel-demo-password",
        },
        timeout=15,
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    verifier = JwtVerifier(issuer, "keel-api")
    try:
        actor = verifier.verify(token)
        alice = next(user for user in demo_users() if user["username"] == "alice")
        assert actor.subject == alice["id"] and actor.tenant == "acme"
        assert actor.roles == frozenset({"operator"})
    finally:
        verifier.close()
    wrong = JwtVerifier(issuer, "other-api")
    try:
        with pytest.raises(AuthenticationError):
            wrong.verify(token)
    finally:
        wrong.close()
