import pytest
from keel.identity import Actor, actor_from_claims


def test_verified_claims_require_exact_single_tenant_and_subject():
    actor = actor_from_claims(
        {
            "sub": "alice",
            "tenant": "acme",
            "realm_access": {"roles": ["operator", "offline_access"]},
        }
    )
    assert actor == Actor("acme", "alice", frozenset({"operator"}))
    for claims in [
        {"sub": "alice", "tenant": ["acme", "other"]},
        {"sub": "", "tenant": "acme"},
        {"sub": "alice", "tenant": "acme/other"},
    ]:
        with pytest.raises(ValueError):
            actor_from_claims(claims)


def test_principal_is_immutable_and_does_not_promote_unknown_roles():
    actor = actor_from_claims(
        {"sub": "alice", "tenant": "acme", "realm_access": {"roles": ["superuser"]}}
    )
    assert not actor.roles
    with pytest.raises(Exception):
        actor.tenant = "other"
