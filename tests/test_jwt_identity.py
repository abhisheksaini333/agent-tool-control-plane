import json
import time
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from keel.auth import JwtVerifier, AuthenticationError


@pytest.fixture
def signed():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    public.update(kid="key-one", alg="RS256", use="sig")
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"keys": [public]})
        )
    )
    verifier = JwtVerifier(
        "http://localhost:8294/realms/keel", "keel-api", client=client
    )

    def token(**changes):
        claims = {
            "iss": verifier.issuer,
            "aud": "keel-api",
            "sub": "alice",
            "tenant": "acme",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
            "typ": "Bearer",
            "azp": "keel-console",
            "realm_access": {"roles": ["operator"]},
        }
        claims.update(changes)
        return jwt.encode(
            claims, private, algorithm="RS256", headers={"kid": "key-one"}
        )

    return verifier, token


def test_actual_rsa_signature_produces_a_tenant_actor(signed):
    verifier, token = signed
    actor = verifier.verify(token())
    assert actor.subject == "alice" and actor.tenant == "acme"
    assert actor.roles == frozenset({"operator"})


@pytest.mark.parametrize(
    "changes",
    [
        {"aud": "another-api"},
        {"iss": "https://attacker"},
        {"exp": 1},
        {"tenant": ["acme", "other"]},
        {"typ": "ID"},
        {"azp": "unknown-client"},
        {"sub": ""},
    ],
)
def test_signed_but_inappropriate_tokens_are_denied(signed, changes):
    verifier, token = signed
    with pytest.raises(AuthenticationError):
        verifier.verify(token(**changes))


def test_unsigned_and_symmetric_tokens_are_rejected(signed):
    verifier, _ = signed
    for token in [
        "not.jwt",
        jwt.encode(
            {"sub": "alice"}, "attacker", algorithm="HS256", headers={"kid": "key-one"}
        ),
    ]:
        with pytest.raises(AuthenticationError):
            verifier.verify(token)
