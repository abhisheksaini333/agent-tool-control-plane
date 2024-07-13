"""Explicit, idempotent local demonstration seed; existing state is preserved."""
import json
from pathlib import Path
from .accounts import Accounts
from .catalog import TOOLS
from .identity import Actor
from .inventory import Inventory
from .registry import Registry


def demo_users():
    return json.loads(
        (Path(__file__).resolve().parents[1] / "infra/demo-users.json").read_text()
    )


def seed_demo(store, enabled=False):
    if not enabled:
        raise PermissionError("Demo seed requires explicit local-demo mode")
    users = demo_users()
    for tenant in sorted({user["tenant"] for user in users}):
        if store.get(tenant, "meta", "demo_seeded"):
            continue
        members = [user for user in users if user["tenant"] == tenant]
        for user in members:
            if not store.get(tenant, "accounts", user["id"]):
                Accounts(store).provision(
                    tenant, user["id"], user["roles"], user["display_name"]
                )
        administrator = next(
            user for user in members if "administrator" in user["roles"]
        )
        actor = Actor(tenant, administrator["id"], frozenset(administrator["roles"]))
        registry = Registry(store)
        for tool in TOOLS:
            if not registry.get(tenant, tool["name"], tool["version"]):
                registry.publish(actor, tool)
            if not store.get(tenant, "active_tools", tool["name"]):
                registry.activate(actor, tool["name"], tool["version"])
        for sku, quantity in [("KIT-EDGE", 120), ("KIT-DATA", 60), ("KIT-AI", 40)]:
            if not store.get(tenant, "inventory", sku):
                Inventory(store).provision(tenant, sku, quantity)
        with store.transaction():
            store.put(tenant, "meta", "demo_seeded", {"version": 1})
