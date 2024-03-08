"""Transactional request lifecycle. All times come from the trusted server."""
from copy import deepcopy
import uuid
from .accounts import Accounts
from .audit import Audit
from .canonical import digest
from .identity import Actor, identifier
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
            retry_key = digest({"caller": actor.subject, "key": idempotency_key})
            fingerprint = digest({"name": name, "version": version, "arguments": arguments})
            previous = self.store.get(actor.tenant, "idempotency", retry_key)
            if previous:
                if previous["fingerprint"] != fingerprint:
                    raise ValueError("Idempotency key already binds different arguments")
                return self.store.get(actor.tenant, "requests", previous["request_id"])
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
                "caller_roles": sorted(actor.roles), "caller_generation": self.store.get(actor.tenant, "accounts", actor.subject)["generation"], "tool": deepcopy(tool),
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
            self.store.put(actor.tenant, "idempotency", retry_key, {"fingerprint": fingerprint, "request_id": request["id"]})
            self.audit.append(actor.tenant, actor.subject, "request.created", request["id"], {"binding": request["binding"], "tool": name, "version": version}, now)
        return request

    @staticmethod
    def binding(request):
        return digest({key: request[key] for key in ("id", "tenant", "caller", "caller_roles", "caller_generation", "tool", "tool_generation", "arguments", "arguments_digest", "policy_revision", "requires_approval", "expires_at")})

    def _request(self, tenant, request_id):
        request = self.store.get(tenant, "requests", request_id)
        if not request:
            raise LookupError("Request not found")
        return request

    def _current_authorization(self, request, now):
        if request["binding"] != self.binding(request) or digest(request["arguments"]) != request["arguments_digest"]:
            raise ValueError("Request binding no longer matches its arguments")
        if now >= request["expires_at"]:
            raise ValueError("Request has expired")
        active = self.registry.current(request["tenant"], request["tool"]["name"])
        if not active or active["generation"] != request["tool_generation"] or active["digest"] != request["tool"]["digest"]:
            raise ValueError("Tool activation changed; submit a fresh request")
        caller = self.accounts.current(request["tenant"], request["caller"])
        account = self.store.get(caller.tenant, "accounts", caller.subject)
        if account["generation"] != request["caller_generation"]:
            raise PermissionError("Caller permissions changed; submit a fresh request")
        caller = Actor(caller.tenant, caller.subject, caller.roles & frozenset(request["caller_roles"]))
        decision = self.policy.evaluate(caller, request["tool"])
        if not decision["allow"] or decision["revision"] != request["policy_revision"] or decision["requires_approval"] != request["requires_approval"]:
            raise PermissionError("Current policy no longer authorizes this binding")
        return caller

    def approve(self, actor, request_id, binding, expected_revision, now):
        with self.store.transaction():
            actor = self.accounts.effective(actor)
            request = self._request(actor.tenant, request_id)
            if request["status"] != "awaiting_approval" or request["revision"] != expected_revision or request["binding"] != binding:
                raise ValueError("Approval requires the exact current request")
            self._current_authorization(request, now)
            decision = self.policy.evaluate(actor, request["tool"], "approve", request["caller"])
            if not decision["allow"] or decision["revision"] != request["policy_revision"]:
                raise PermissionError("Independent approver permission required")
            request["approval"] = {"subject": actor.subject, "tenant": actor.tenant, "binding": binding, "created_at": now, "expires_at": min(now + 300, request["expires_at"]), "account_generation": self.store.get(actor.tenant, "accounts", actor.subject)["generation"], "revoked": False}
            request.update(status="queued", revision=request["revision"] + 1)
            self.store.put(actor.tenant, "requests", request_id, request)
            self.audit.append(actor.tenant, actor.subject, "request.approved", request_id, {"binding": binding, "expires_at": request["approval"]["expires_at"]}, now)
        return request

    def authorize_execution(self, request, now):
        """Call inside the same transaction as dispatch reservation or effect commit."""
        self._current_authorization(request, now)
        if request["tool"]["risk"] == "effect" and not request["requires_approval"]:
            raise PermissionError("Effect handlers always require human approval")
        if not request["requires_approval"]:
            return
        approval = request["approval"]
        if not approval or approval["revoked"] or approval["binding"] != request["binding"] or approval["tenant"] != request["tenant"] or now >= approval["expires_at"]:
            raise PermissionError("A current exact approval is required")
        approver = self.accounts.current(request["tenant"], approval["subject"])
        account = self.store.get(approver.tenant, "accounts", approver.subject)
        if account["generation"] != approval["account_generation"]:
            raise PermissionError("Approver permissions changed")
        decision = self.policy.evaluate(approver, request["tool"], "approve", request["caller"])
        if not decision["allow"] or decision["revision"] != request["policy_revision"]:
            raise PermissionError("Approval no longer passes current policy")

    @staticmethod
    def _visible(actor, request):
        return request["caller"] == actor.subject or bool(actor.roles & {"approver", "auditor", "administrator"})

    def get(self, actor, request_id):
        actor = self.accounts.effective(actor)
        request = self._request(actor.tenant, request_id)
        if not self._visible(actor, request):
            raise LookupError("Request not found")
        return request

    def list_requests(self, actor, limit=100):
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("Limit must be between 1 and 200")
        actor = self.accounts.effective(actor)
        visible = [r for r in self.store.list(actor.tenant, "requests") if self._visible(actor, r)]
        return sorted(visible, key=lambda r: (r["created_at"], r["id"]), reverse=True)[:limit]
