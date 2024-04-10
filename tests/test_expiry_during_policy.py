import pytest
from test_receipts import ready
from keel.inventory import Inventory


def test_approval_expiring_during_policy_check_prevents_commit():
    control, execution, request = ready()
    time = [400]
    control.clock = lambda: time[0]
    original = control.policy.evaluate

    def slow_policy(*args, **kwargs):
        decision = original(*args, **kwargs)
        time[0] = 402
        return decision

    control.policy.evaluate = slow_policy
    with pytest.raises(PermissionError):
        execution.complete("acme", request["id"], request["lease"], {"ok": True}, 103)
    assert Inventory(control.store).list("acme")[0]["available"] == 10
