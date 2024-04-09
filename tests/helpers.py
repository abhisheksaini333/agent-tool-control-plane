from copy import deepcopy
from keel.accounts import Accounts
from keel.identity import Actor
from keel.registry import Registry
from keel.store import Store

ALICE = Actor("acme", "alice", frozenset({"operator"}))
BOB = Actor("acme", "bob", frozenset({"approver"}))
ADMIN = Actor("acme", "admin", frozenset({"administrator"}))
MANIFEST = {
    "name": "inventory.reserve",
    "version": "1.0.0",
    "handler": "reserve_inventory",
    "description": "Reserve demonstration inventory",
    "schema": {
        "type": "object",
        "properties": {
            "sku": {"type": "string", "maxLength": 40},
            "quantity": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["sku", "quantity"],
        "additionalProperties": False,
    },
}


class FixturePolicy:
    """Deterministic domain fixture, never used in the application."""

    revision = "fixture-policy-1"

    def evaluate(self, actor, tool, action="invoke", requester=None):
        role = "operator" if action == "invoke" else "approver"
        return {
            "allow": role in actor.roles
            and (action != "approve" or actor.subject != requester),
            "requires_approval": tool["risk"] == "effect",
            "revision": self.revision,
        }


def make_control(store=None, policy=None):
    from keel.control import Control

    store = store or Store()
    accounts = Accounts(store)
    for actor in [ALICE, BOB, ADMIN]:
        accounts.provision(actor.tenant, actor.subject, actor.roles)
    registry = Registry(store)
    registry.publish(ADMIN, deepcopy(MANIFEST))
    registry.activate(ADMIN, MANIFEST["name"], MANIFEST["version"])
    return Control(store, policy or FixturePolicy())


def submit(control, key="request-1", now=100):
    return control.submit(
        ALICE, "inventory.reserve", "1.0.0", {"sku": "SKU-1", "quantity": 2}, key, now
    )
