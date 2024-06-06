"""Versioned manifests select trusted handlers, never executable commands."""
from copy import deepcopy
import re
import time
from .canonical import digest
from .accounts import Accounts
from .audit import Audit
from .identity import identifier
from .schemas import validate_schema

HANDLERS = {
    "sha256": {"risk": "read", "credential": None},
    "sign_report": {"risk": "read", "credential": "report-signing"},
    "reserve_inventory": {"risk": "effect", "credential": "inventory-signing"},
}
FIELDS = {"name", "version", "handler", "description", "schema"}


class Registry:
    def __init__(self, store):
        self.store = store

    def publish(self, actor, manifest):
        if set(manifest) != FIELDS:
            raise ValueError("Manifest contains missing or untrusted fields")
        identifier(manifest["name"], "tool name")
        if not re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", manifest["version"]):
            raise ValueError("Version must use major.minor.patch")
        if manifest["handler"] not in HANDLERS:
            raise ValueError("Handler is not installed in the trusted catalog")
        if (
            not isinstance(manifest["description"], str)
            or len(manifest["description"]) > 2000
        ):
            raise ValueError("Description must contain at most 2000 characters")
        validate_schema(manifest["schema"])
        record = {**deepcopy(manifest), **HANDLERS[manifest["handler"]]}
        record["digest"] = digest(record)
        key = f'{record["name"]}@{record["version"]}'
        with self.store.transaction():
            actor = Accounts(self.store).effective(actor)
            if "administrator" not in actor.roles:
                raise PermissionError("Administrator role required")
            previous = self.store.get(actor.tenant, "tools", key)
            if previous and previous != record:
                raise ValueError("Published versions cannot be changed")
            self.store.put(actor.tenant, "tools", key, record)
            if not previous:
                Audit(self.store).append(
                    actor.tenant,
                    actor.subject,
                    "tool.published",
                    None,
                    {
                        "name": record["name"],
                        "version": record["version"],
                        "digest": record["digest"],
                    },
                    time.time(),
                )
        return record

    def get(self, tenant, name, version):
        return self.store.get(tenant, "tools", f"{name}@{version}")

    def activate(self, actor, name, version):
        with self.store.transaction():
            actor = Accounts(self.store).effective(actor)
            if "administrator" not in actor.roles:
                raise PermissionError("Administrator role required")
            tool = self.get(actor.tenant, name, version)
            if not tool:
                raise ValueError("Unknown tool version")
            previous = self.store.get(actor.tenant, "active_tools", name)
            active = {
                "name": name,
                "version": version,
                "digest": tool["digest"],
                "generation": (previous["generation"] if previous else 0) + 1,
                "enabled": True,
            }
            self.store.put(actor.tenant, "active_tools", name, active)
            Audit(self.store).append(
                actor.tenant,
                actor.subject,
                "tool.activated",
                None,
                {"name": name, "version": version, "generation": active["generation"]},
                time.time(),
            )
        return active

    def disable(self, actor, name):
        with self.store.transaction():
            actor = Accounts(self.store).effective(actor)
            if "administrator" not in actor.roles:
                raise PermissionError("Administrator role required")
            active = self.store.get(actor.tenant, "active_tools", name)
            if not active:
                raise ValueError("Unknown active tool")
            active.update(enabled=False, generation=active["generation"] + 1)
            self.store.put(actor.tenant, "active_tools", name, active)
            Audit(self.store).append(
                actor.tenant,
                actor.subject,
                "tool.disabled",
                None,
                {"name": name, "generation": active["generation"]},
                time.time(),
            )
        return active

    def current(self, tenant, name):
        active = self.store.get(tenant, "active_tools", name)
        if not active or not active["enabled"]:
            return None
        return {**active, "tool": self.get(tenant, name, active["version"])}
