"""Versioned OPA Data API adapter. Unavailable decisions never imply permission."""
import httpx


class PolicyUnavailable(RuntimeError):
    pass


class OpaPolicy:
    def __init__(self, base_url, client=None):
        self.url = base_url.rstrip("/") + "/v1/data/keel/decision"
        self.client = client or httpx.Client(timeout=2, trust_env=False)

    def evaluate(self, actor, tool, action="invoke", requester=None):
        context = {"action": action, "actor": actor.record(), "tenant": actor.tenant, "tool": {"handler": tool["handler"], "risk": tool["risk"], "enabled": True}, "requester": requester}
        try:
            response = self.client.post(self.url, json={"input": context}, timeout=2)
            response.raise_for_status()
            if len(response.content) > 16384:
                raise ValueError("Oversized policy decision")
            result = response.json()["result"]
            if not isinstance(result, dict) or type(result.get("allow")) is not bool or type(result.get("requires_approval")) is not bool:
                raise ValueError("Invalid policy decision")
            if not isinstance(result.get("revision"), str) or not 1 <= len(result["revision"]) <= 128:
                raise ValueError("Missing policy revision")
            return {key: result[key] for key in ("allow", "requires_approval", "revision")}
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise PolicyUnavailable("Policy evaluation unavailable; execution denied") from error

    def close(self):
        self.client.close()
