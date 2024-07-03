from fastapi.testclient import TestClient
from keel.api import create_app
from keel.admission import AdmissionDenied, AdmissionUnavailable
from keel.settings import Settings
from helpers import make_control
from test_api_requests import FixtureVerifier


class DenyingAdmission:
    def __init__(self, error):
        self.error = error

    def check(self, actor):
        raise self.error


def test_rate_or_admission_outage_prevents_mutations_but_keeps_inspection():
    for error, status in [
        (AdmissionDenied(9), 429),
        (AdmissionUnavailable("offline"), 503),
    ]:
        control = make_control()
        app = create_app(
            control,
            FixtureVerifier(),
            Settings.from_env({"KEEL_LOCAL_DEMO": "1"}),
            clock=lambda: 100,
            admission=DenyingAdmission(error),
        )
        client = TestClient(app)
        headers = {"Authorization": "Bearer alice-token", "Idempotency-Key": "limited"}
        response = client.post(
            "/api/requests",
            headers=headers,
            json={
                "tool": "inventory.reserve",
                "version": "1.0.0",
                "arguments": {"sku": "SKU-1", "quantity": 2},
            },
        )
        assert response.status_code == status
        if status == 429:
            assert response.headers["retry-after"] == "9"
        assert client.get("/api/requests", headers=headers).status_code == 200
        assert control.store.list("acme", "requests") == []
