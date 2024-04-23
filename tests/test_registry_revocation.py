import pytest
from helpers import make_control, ADMIN, MANIFEST


def test_revoked_cached_administrator_cannot_mutate_registry():
    control = make_control()
    control.accounts.revoke("acme", "admin")
    for change in [
        lambda: control.registry.disable(ADMIN, MANIFEST["name"]),
        lambda: control.registry.activate(ADMIN, MANIFEST["name"], MANIFEST["version"]),
        lambda: control.registry.publish(ADMIN, {**MANIFEST, "version": "1.0.1"}),
    ]:
        with pytest.raises(PermissionError):
            change()
    assert control.registry.current("acme", MANIFEST["name"])["generation"] == 1
