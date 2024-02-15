"""Transactional request lifecycle. All times come from the trusted server."""
from copy import deepcopy
import uuid
from .accounts import Accounts
from .audit import Audit
from .canonical import digest
from .identity import identifier
from .registry import Registry
from .schemas import validate_arguments


class Control:
    def __init__(self, store, policy):
        self.store = store
        self.policy = policy
        self.accounts = Accounts(store)
        self.registry = Registry(store)
        self.audit = Audit(store)

    def submit(self, actor, name, version, arguments, idempotency_key, now):
        identifier(idempotency_key, "idempotency key")
        with self.store.transaction():
            actor = self.accounts.effective(actor)
            active = self.registry.current(actor.tenant, name)
            if not active or active["version"] != version:
                raise ValueError("Requested tool version is not active")
            tool = active["tool"]
            validate_arguments(tool["schema"], arguments)
            decision = self.policy.evaluate(actor, tool)
            if not decision["allow"]:
                raise PermissionError("Policy denied this invocation")
            request = {
                "id": uuid.uuid4().hex, "tenant": actor.tenant, "caller": actor.subject,
                "caller_roles": sorted(actor.roles), "tool": deepcopy(tool),
                "tool_generation": active["generation"], "arguments": deepcopy(arguments),
                "arguments_digest": digest(arguments), "policy_revision": decision["revision"],
                "requires_approval": decision["requires_approval"],
                "idempotency_key": idempotency_key, "created_at": now, "expires_at": now + 3600,
                "status": "awaiting_approval" if decision["requires_approval"] else "queued",
                "approval": None, "lease": None, "attempts": 0, "revision": 1,
                "next_attempt_at": now, "receipt": None, "error": None,
            }
            request["binding"] = self.binding(request)
            self.store.put(actor.tenant, "requests", request["id"], request)
            self.audit.append(actor.tenant, actor.subject, "request.created", request["id"], {"binding": request["binding"], "tool": name, "version": version}, now)
        return request

    @staticmethod
    def binding(request):
        return digest({key: request[key] for key in ("id", "tenant", "caller", "caller_roles", "tool", "tool_generation", "arguments", "arguments_digest", "policy_revision", "requires_approval", "expires_at")})
