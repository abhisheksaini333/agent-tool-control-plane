"""Keycloak access-token verification against a fixed issuer and JWKS URL."""
import threading
import time
import httpx
import jwt
from .identity import actor_from_claims


class AuthenticationError(PermissionError):
    pass


class JwtVerifier:
    def __init__(
        self, issuer, audience, client=None, parties=("keel-console",), clock=None
    ):
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self.parties = frozenset(parties)
        self.url = self.issuer + "/protocol/openid-connect/certs"
        self.client = client or httpx.Client(timeout=2, trust_env=False)
        self.clock = clock or time.monotonic
        self.keys = {}
        self.expires = 0
        self.refresh_after = 0
        self.lock = threading.Lock()

    def _refresh(self):
        self.refresh_after = self.clock() + 5
        response = self.client.get(self.url, timeout=2)
        response.raise_for_status()
        if len(response.content) > 65536:
            raise ValueError("Oversized signing key response")
        supplied = response.json()["keys"]
        if not isinstance(supplied, list) or not 1 <= len(supplied) <= 32:
            raise ValueError("Invalid signing key set")
        keys = {}
        for key in supplied:
            if (
                key.get("kty") != "RSA"
                or key.get("use", "sig") != "sig"
                or key.get("alg", "RS256") != "RS256"
            ):
                continue
            kid = key.get("kid")
            if not isinstance(kid, str) or not 1 <= len(kid) <= 128 or kid in keys:
                raise ValueError("Invalid signing key identifier")
            keys[kid] = jwt.PyJWK.from_dict(key, algorithm="RS256").key
        if not keys:
            raise ValueError("No supported signing keys")
        self.keys = keys
        self.expires = self.clock() + 300

    def verify(self, token):
        try:
            if not isinstance(token, str) or len(token) > 16384:
                raise ValueError("Invalid access token size")
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if (
                header.get("alg") != "RS256"
                or not isinstance(kid, str)
                or not 1 <= len(kid) <= 128
            ):
                raise ValueError("Unsupported access token header")
            with self.lock:
                now = self.clock()
                if now >= self.expires or (
                    kid not in self.keys and now >= self.refresh_after
                ):
                    self._refresh()
                key = self.keys.get(kid)
            if key is None:
                raise ValueError("Unknown signing key")
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
            if claims.get("typ") != "Bearer" or claims.get("azp") not in self.parties:
                raise ValueError("Token is not an authorized API access token")
            return actor_from_claims(claims)
        except (
            jwt.PyJWTError,
            httpx.HTTPError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
        ) as error:
            raise AuthenticationError("A valid API access token is required") from error

    def close(self):
        self.client.close()
