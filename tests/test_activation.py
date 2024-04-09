import pytest
from keel.registry import Registry
from keel.store import Store
from test_registry import ADMIN, MANIFEST


def test_activation_has_monotonic_generation_and_can_be_revoked():
    registry = Registry(Store())
    tool = registry.publish(ADMIN, MANIFEST)
    active = registry.activate(ADMIN, tool["name"], tool["version"])
    assert (
        active["generation"] == 1
        and registry.current("acme", tool["name"])["tool"] == tool
    )
    disabled = registry.disable(ADMIN, tool["name"])
    assert disabled["generation"] == 2 and not disabled["enabled"]
    assert registry.current("acme", tool["name"]) is None
    assert registry.activate(ADMIN, tool["name"], tool["version"])["generation"] == 3


def test_unknown_version_does_not_replace_active_tool():
    registry = Registry(Store())
    tool = registry.publish(ADMIN, MANIFEST)
    registry.activate(ADMIN, tool["name"], tool["version"])
    with pytest.raises(ValueError):
        registry.activate(ADMIN, tool["name"], "2.0.0")
    assert registry.current("acme", tool["name"])["generation"] == 1
