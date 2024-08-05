"""Actual local OIDC/API/worker acceptance. Never prints access tokens."""
import argparse
import json
from pathlib import Path
import time
import uuid
import httpx


def verify(base, issuer):
    checks = {}
    with httpx.Client(timeout=15, trust_env=False) as client:
        ready = client.get(base + "/ready")
        ready.raise_for_status()
        assert ready.json()["ready"]
        checks["dependencies_ready"] = True

        def session(username):
            response = client.post(
                issuer + "/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "keel-demo-cli",
                    "username": username,
                    "password": "keel-demo-password",
                },
            )
            response.raise_for_status()
            return {"Authorization": "Bearer " + response.json()["access_token"]}

        alice, bob, north = session("alice"), session("bob"), session("north-operator")
        before = client.get(base + "/api/inventory", headers=alice).json()
        stock_before = next(
            item["available"] for item in before if item["sku"] == "KIT-EDGE"
        )
        key = "acceptance-" + uuid.uuid4().hex
        body = {
            "tool": "inventory.reserve",
            "version": "1.0.0",
            "arguments": {"sku": "KIT-EDGE", "quantity": 1},
        }
        headers = {**alice, "Idempotency-Key": key}
        response = client.post(base + "/api/requests", headers=headers, json=body)
        response.raise_for_status()
        request = response.json()
        path = base + "/api/requests/" + request["id"]
        assert client.get(path, headers=north).status_code == 404
        checks["cross_tenant_denied"] = True
        assert (
            client.get(path, headers={"Authorization": "Bearer invalid"}).status_code
            == 401
        )
        checks["invalid_token_denied"] = True
        approval = {"binding": request["binding"], "revision": request["revision"]}
        assert (
            client.post(
                path + "/approval", headers=bob, json={**approval, "binding": "f" * 64}
            ).status_code
            == 409
        )
        assert (
            client.post(
                path + "/approval",
                headers=bob,
                json={**approval, "arguments": {"quantity": 2}},
            ).status_code
            == 422
        )
        assert (
            client.post(path + "/approval", headers=alice, json=approval).status_code
            == 403
        )
        checks["altered_and_self_approval_denied"] = True
        client.post(path + "/approval", headers=bob, json=approval).raise_for_status()
        for _ in range(100):
            completed = client.get(path, headers=alice).json()
            if completed["status"] == "completed":
                break
            assert completed["status"] not in {
                "failed",
                "rejected",
                "expired",
            }, completed["error"]
            time.sleep(0.3)
        else:
            raise AssertionError("Worker did not complete within30seconds")
        assert completed["receipt"]["effect"]["quantity"] == 1
        checks["signed_worker_effect_completed"] = bool(
            completed["receipt"]["output"]["result"]["signature"]
        )
        assert (
            client.post(path + "/approval", headers=bob, json=approval).status_code
            == 409
        )
        repeated = client.post(base + "/api/requests", headers=headers, json=body)
        repeated.raise_for_status()
        assert (
            repeated.json()["id"] == request["id"]
            and repeated.json()["status"] == "completed"
        )
        after = client.get(base + "/api/inventory", headers=alice).json()
        stock_after = next(
            item["available"] for item in after if item["sku"] == "KIT-EDGE"
        )
        assert stock_after == stock_before - 1
        checks["replay_did_not_repeat_effect"] = True
        events = client.get(path + "/audit", headers=alice).json()
        assert (
            len([event for event in events if event["action"] == "execution.completed"])
            == 1
        )
        checks["single_completion_audited"] = True
        return {
            "checks": checks,
            "request_id": request["id"],
            "stock_before": stock_before,
            "stock_after": stock_after,
            "worker_metrics": completed["receipt"]["output"]["metrics"],
            "passed": all(checks.values()),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:5484")
    parser.add_argument("--issuer", default="http://localhost:8294/realms/keel")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.api, args.issuer)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("Actual identity/API/worker acceptance passed")
