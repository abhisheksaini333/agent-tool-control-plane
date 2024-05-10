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
        return bool(
            request["status"] == "running"
            and current
            and lease
            and current["token"] == lease["token"]
            and current["fence"] == lease["fence"]
            and current["owner"] == lease["owner"]
            and now < current["expires_at"]
        )

    def claim(self, tenant, request_id, owner, now):
        identifier(owner, "worker owner")
        with self.store.transaction():
            request = self.control._request(tenant, request_id)
            ready = (
                request["status"] in {"queued", "retry_wait"}
                and now >= request["next_attempt_at"]
            )
            abandoned = (
                request["status"] == "running"
                and request["lease"]
                and now >= request["lease"]["expires_at"]
            )
            if not (ready or abandoned) or request["attempts"] >= self.max_attempts:
                raise ValueError("Request is not claimable")
            self.control.authorize_execution(request, now)
            now = self.control.current_time(now)
            request["attempts"] += 1
            request["lease"] = {
                "owner": owner,
                "token": uuid.uuid4().hex,
                "fence": request["attempts"],
                "expires_at": now + self.lease_seconds,
            }
            request.update(status="running", revision=request["revision"] + 1)
            self.store.put(tenant, "requests", request_id, request)
            self.control.audit.append(
                tenant,
                owner,
                "execution.claimed",
                request_id,
                {"attempt": request["attempts"], "recovered": bool(abandoned)},
                now,
            )
        return deepcopy(request)

    def complete(self, tenant, request_id, lease, output, now):
        completion = {
            "lease_digest": digest(
                {key: lease[key] for key in ("owner", "token", "fence")}
            ),
            "output_digest": digest(output),
        }
        with self.store.transaction():
            request = self.control._request(tenant, request_id)
            previous = self.store.get(tenant, "completions", request_id)
            if previous:
                if previous != completion:
                    raise ValueError(
                        "Completion already binds another worker or result"
                    )
                return self.store.get(tenant, "receipts", request_id)
            if not self.owns(request, lease, now):
                raise ValueError("Worker no longer owns this execution")
            self.control.authorize_execution(request, now)
            now = self.control.current_time(now)
            if not self.owns(request, lease, now):
                raise ValueError("Worker lease expired during authorization")
            effect = None
            if request["tool"]["handler"] == "reserve_inventory":
                effect = Inventory(self.store).reserve(
                    tenant, request_id, request["arguments"]
                )
            receipt = {
                "id": request_id,
                "tenant": tenant,
                "caller": request["caller"],
                "tool": request["tool"]["name"],
                "version": request["tool"]["version"],
                "binding": request["binding"],
                "arguments_digest": request["arguments_digest"],
                "completed_at": now,
                "attempt": request["attempts"],
                "output": redact(output),
                "effect": effect,
            }
            self.store.put(tenant, "receipts", request_id, receipt)
            self.store.put(tenant, "completions", request_id, completion)
            request.update(
                status="completed",
                lease=None,
                receipt=receipt,
                finished_at=now,
                revision=request["revision"] + 1,
            )
            self.store.put(tenant, "requests", request_id, request)
            self.control.audit.append(
                tenant,
                lease["owner"],
                "execution.completed",
                request_id,
                {"receipt": request_id, "effect_committed": effect is not None},
                now,
            )
        return receipt

    def fail(self, tenant, request_id, lease, code, now):
        transient = {
            "worker_unavailable",
            "worker_timeout",
            "worker_exit",
            "policy_unavailable",
        }
        permanent = {
            "invalid_output",
            "authorization_changed",
            "insufficient_inventory",
            "resource_limit",
            "internal_failure",
        }
        if code not in transient | permanent:
            raise ValueError("Unknown safe failure code")
        with self.store.transaction():
            request = self.control._request(tenant, request_id)
            if not self.owns(request, lease, now):
                return None
            retry = code in transient and request["attempts"] < self.max_attempts
            request.update(
                status="retry_wait" if retry else "failed",
                lease=None,
                error=code,
                revision=request["revision"] + 1,
                next_attempt_at=now + 2 ** request["attempts"],
            )
            if not retry:
                request["finished_at"] = now
            self.store.put(tenant, "requests", request_id, request)
            self.control.audit.append(
                tenant,
                lease["owner"],
                "execution.retry_scheduled" if retry else "execution.failed",
                request_id,
                {"code": code, "attempt": request["attempts"]},
                now,
            )
        return request

    def ready(self, tenant, now):
        candidates = []
        with self.store.transaction():
            for request in self.store.list(tenant, "requests"):
                if request["status"] not in {
                    "queued",
                    "retry_wait",
                    "running",
                    "awaiting_approval",
                }:
                    continue
                if (
                    request["status"] == "running"
                    and request["lease"]
                    and now < request["lease"]["expires_at"]
                ):
                    continue
                approval = request["approval"]
                expired = now >= request["expires_at"] or (
                    approval and now >= approval["expires_at"]
                )
                exhausted = request["attempts"] >= self.max_attempts
                if expired or exhausted:
                    code = (
                        "approval_or_request_expired"
                        if expired
                        else "attempts_exhausted"
                    )
                    request.update(
                        status="expired" if expired else "failed",
                        error=code,
                        lease=None,
                        finished_at=now,
                        revision=request["revision"] + 1,
                    )
                    self.store.put(tenant, "requests", request["id"], request)
                    self.control.audit.append(
                        tenant,
                        "recovery",
                        "execution.closed",
                        request["id"],
                        {"code": code},
                        now,
                    )
                elif (
                    request["status"] != "awaiting_approval"
                    and now >= request["next_attempt_at"]
                ):
                    candidates.append(request)
        return sorted(candidates, key=lambda r: (r["created_at"], r["id"]))[:100]

    def defer_unclaimed(self, tenant, request_id, expected_revision, code, now):
        if code not in {"policy_unavailable", "authorization_changed"}:
            raise ValueError("Invalid pre-dispatch failure")
        with self.store.transaction():
            request = self.control._request(tenant, request_id)
            live = (
                request["status"] == "running"
                and request["lease"]
                and now < request["lease"]["expires_at"]
            )
            if (
                live
                or request["revision"] != expected_revision
                or request["status"] not in {"queued", "retry_wait", "running"}
            ):
                return None
            request["policy_failures"] = request.get("policy_failures", 0) + 1
            retry = code == "policy_unavailable" and request["policy_failures"] < 5
            request.update(
                status="retry_wait" if retry else "rejected",
                lease=None,
                error=code,
                revision=request["revision"] + 1,
                next_attempt_at=now + min(2 ** request["policy_failures"], 30),
            )
            if not retry:
                request["finished_at"] = now
            self.store.put(tenant, "requests", request_id, request)
            self.control.audit.append(
                tenant,
                "policy-check",
                "execution.deferred" if retry else "execution.rejected",
                request_id,
                {"code": code, "failures": request["policy_failures"]},
                now,
            )
        return request
