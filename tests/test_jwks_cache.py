import httpx
import pytest
from keel.auth import AuthenticationError
from test_jwt_identity import signed


def test_identity_provider_outage_has_bounded_key_refresh(signed):
    verifier, token = signed
    requests = []

    def offline(request):
        requests.append(request)
        return httpx.Response(503)

    verifier.client = httpx.Client(transport=httpx.MockTransport(offline))
    clock = [100]
    verifier.clock = lambda: clock[0]
    for _ in range(3):
        with pytest.raises(AuthenticationError):
            verifier.verify(token())
    assert len(requests) == 1
    clock[0] = 106
    with pytest.raises(AuthenticationError):
        verifier.verify(token())
    assert len(requests) == 2


def test_cached_valid_keys_avoid_an_identity_network_call_per_request(signed):
    verifier, token = signed
    calls = []
    verifier.client.event_hooks["request"] = [lambda request: calls.append(request)]
    for _ in range(3):
        assert verifier.verify(token()).subject == "alice"
    assert len(calls) == 1
