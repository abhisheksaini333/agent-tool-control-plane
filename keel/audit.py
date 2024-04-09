"""Append-only application audit with redaction and an integrity chain."""
import re
from .canonical import digest

SENSITIVE = re.compile(r"password|secret|token|authorization|credential|api.?key", re.I)


def redact(value, secrets=()):
    if isinstance(value, dict):
        return {
            key: "[redacted]" if SENSITIVE.search(key) else redact(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in sorted((s for s in secrets if s), key=len, reverse=True):
            value = value.replace(secret, "[redacted]")
        return value[:4096]
    return value


class Audit:
    def __init__(self, store):
        self.store = store

    def append(self, tenant, actor, action, request_id, details, now):
        self.store._write_required()
        head = self.store.get(tenant, "meta", "audit") or {
            "sequence": 0,
            "hash": "0" * 64,
        }
        event = {
            "sequence": head["sequence"] + 1,
            "previous": head["hash"],
            "tenant": tenant,
            "actor": actor,
            "action": action,
            "request_id": request_id,
            "details": redact(details),
            "at": now,
        }
        event["hash"] = digest(event)
        self.store.put(tenant, "audit", f'{event["sequence"]:012d}', event)
        self.store.put(
            tenant,
            "meta",
            "audit",
            {"sequence": event["sequence"], "hash": event["hash"]},
        )
        return event

    def list(self, tenant):
        return self.store.list(tenant, "audit")

    def verify(self, tenant):
        previous = "0" * 64
        for sequence, event in enumerate(self.list(tenant), 1):
            supplied = event.pop("hash")
            if (
                event["sequence"] != sequence
                or event["previous"] != previous
                or digest(event) != supplied
            ):
                return False
            previous = supplied
        head = self.store.get(tenant, "meta", "audit")
        return not head or (
            head["hash"] == previous and head["sequence"] == len(self.list(tenant))
        )
