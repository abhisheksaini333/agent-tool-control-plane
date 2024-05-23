import pytest
from keel.settings import Settings


def test_local_demo_requires_explicit_configuration_and_fixed_origins():
    settings = Settings.from_env({"KEEL_LOCAL_DEMO": "1"})
    assert settings.issuer == "http://localhost:8294/realms/keel"
    assert settings.web_origin == "http://localhost:5294"
    assert settings.tenants == ("acme", "north")
    assert "keel-local-only" not in repr(settings)


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"KEEL_LOCAL_DEMO": "1", "KEEL_WEB_ORIGIN": "*"},
        {"KEEL_LOCAL_DEMO": "1", "KEEL_OIDC_ISSUER": "http://attacker.example/realm"},
        {"KEEL_LOCAL_DEMO": "1", "KEEL_TENANTS": "acme,../other"},
    ],
)
def test_unsafe_or_incomplete_settings_fail_at_startup(environment):
    with pytest.raises(ValueError):
        Settings.from_env(environment)
