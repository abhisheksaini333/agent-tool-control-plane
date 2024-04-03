"""Durable worker ownership and atomic completion boundaries."""
from copy import deepcopy
import uuid
from .identity import identifier
from .canonical import digest
from .audit import redact
from .inventory import Inventory


class Execution:
    lease_seconds = 60
    max_attempts = 3

    def __init__(self, control):
        self.control = control
        self.store = control.store

    @staticmethod
    def owns(request, lease, now):
        current = request["lease"]
        return bool(request["status"] == "running" and current and lease and current["token"] == lease["token"] and current["fence"] == lease["fence"] and current["owner"] == lease["owner"] and now < current["expires_at"])

    def claim(self, tenant, request_id, owner, now):
        identifier(owner, "worker owner")
        with self.store.transaction():
            request = self.control._request(tenant, request_id)
            ready = request["status"] in {"queued", "retry_wait"} and now >= request["next_attempt_at"]
            abandoned = request["status"] == "running" and request["lease"] and now >= request["lease"]["expires_at"]
            if not (ready or abandoned) or request["attempts"] >= self.max_attempts:
                raise ValueError("Request is not claimable")
            self.control.authorize_execution(request, now)
            request["attempts"] += 1
            request["lease"] = {"owner": owner, "token": uuid.uuid4().hex, "fence": request["attempts"], "expires_at": now + self.lease_seconds}
            request.update(status="running", revision=request["revision"] + 1)
            self.store.put(tenant, "requests", request_id, request)
            self.control.audit.append(tenant, owner, "execution.claimed", request_id, {"attempt": request["attempts"], "recovered": bool(abandoned)}, now)
        return deepcopy(request)

    def complete(self, tenant, request_id, lease, output, now):
        completion = {"lease_digest": digest({key: lease[key] for key in ("owner", "token", "fence")}), "output_digest": digest(output)}
        with self.store.transaction():
            request = self.control._request(tenant, request_id)
            previous = self.store.get(tenant, "completions", request_id)
            if previous:
                if previous != completion:
                    raise ValueError("Completion already binds another worker or result")
                return self.store.get(tenant, "receipts", request_id)
            if not self.owns(request, lease, now):
                raise ValueError("Worker no longer owns this execution")
            self.control.authorize_execution(request, now)
            effect = None
            if request["tool"]["handler"] == "reserve_inventory":
                effect = Inventory(self.store).reserve(tenant, request_id, request["arguments"])
            receipt = {"id": request_id, "tenant": tenant, "caller": request["caller"], "tool": request["tool"]["name"], "version": request["tool"]["version"], "binding": request["binding"], "arguments_digest": request["arguments_digest"], "completed_at": now, "attempt": request["attempts"], "output": redact(output), "effect": effect}
            self.store.put(tenant, "receipts", request_id, receipt)
            self.store.put(tenant, "completions", request_id, completion)
            request.update(status="completed", lease=None, receipt=receipt, finished_at=now, revision=request["revision"] + 1)
            self.store.put(tenant, "requests", request_id, request)
            self.control.audit.append(tenant, lease["owner"], "execution.completed", request_id, {"receipt": request_id, "effect_committed": effect is not None}, now)
        return receipt
