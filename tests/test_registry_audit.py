from helpers import make_control, ADMIN, MANIFEST


def test_registry_changes_are_audited_in_the_same_transaction():
    control = make_control()
    actions = [event["action"] for event in control.audit.list("acme")]
    assert actions == ["tool.published", "tool.activated"]
    control.registry.disable(ADMIN, MANIFEST["name"])
    assert control.audit.list("acme")[-1]["action"] == "tool.disabled"
    assert control.audit.verify("acme")
