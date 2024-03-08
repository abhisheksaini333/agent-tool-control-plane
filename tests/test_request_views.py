import pytest
from helpers import make_control, submit, ALICE, BOB
from keel.identity import Actor


def test_requester_sees_own_requests_while_approver_can_review_tenant():
    control = make_control()
    request = submit(control)
    control.accounts.provision("acme", "charlie", {"operator"})
    charlie = Actor("acme", "charlie", frozenset({"operator"}))
    assert control.get(ALICE, request["id"])["id"] == request["id"]
    assert control.get(BOB, request["id"])["id"] == request["id"]
    assert control.list_requests(charlie) == []
    with pytest.raises(LookupError):
        control.get(charlie, request["id"])
    control.accounts.provision("other", "bob", {"approver"})
    with pytest.raises(LookupError):
        control.get(Actor("other", "bob", BOB.roles), request["id"])


def test_list_is_newest_first_and_bounded():
    control = make_control()
    first = submit(control, "one", 100)
    second = submit(control, "two", 101)
    assert [r["id"] for r in control.list_requests(BOB, limit=1)] == [second["id"]]
    with pytest.raises(ValueError):
        control.list_requests(BOB, limit=1001)
