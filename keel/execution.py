"""Durable worker ownership and atomic completion boundaries."""
from copy import deepcopy
import uuid
from .identity import identifier


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
