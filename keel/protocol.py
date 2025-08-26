"""Verify worker output as untrusted data before any business effect."""
import hashlib
import hmac
import json
from .canonical import canonical


def payload_for(request):
    return {
        "protocol": 1,
        "request_id": request["id"],
        "tenant": request["tenant"],
        "binding": request["binding"],
        "handler": request["tool"]["handler"],
        "arguments": request["arguments"],
    }


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate worker response field")
        result[key] = value
    return result


def verify_reply(request, raw, secret=None):
    if not isinstance(raw, str):
        raise ValueError("Worker output must be UTF-8 text")
    try:
        if len(raw.encode("utf-8")) > 65536:
            raise ValueError("Worker output exceeds 64 KiB")
        reply = json.loads(raw, object_pairs_hook=_unique)
        payload = payload_for(request)
        if not isinstance(reply, dict) or set(reply) != {
            "protocol",
            "request_id",
            "binding",
            "handler",
            "result",
        }:
            raise ValueError("Invalid worker response fields")
        for key in ["protocol", "request_id", "binding", "handler"]:
            if type(reply[key]) is not type(payload[key]) or reply[key] != payload[key]:
                raise ValueError("Worker response does not match request")
        handler = payload["handler"]
        arguments = payload["arguments"]
        if handler in {"sha256", "sign_report"}:
            text = arguments["text"].encode()
            expected = {"sha256": hashlib.sha256(text).hexdigest(), "bytes": len(text)}
        elif handler == "reserve_inventory":
            expected = {"sku": arguments["sku"], "quantity": arguments["quantity"]}
        else:
            raise ValueError("Unknown worker handler")
        if handler in {"sign_report", "reserve_inventory"}:
            if not secret:
                raise ValueError("Signed handler needs scoped credential")
            expected["signature"] = hmac.new(
                secret.encode(), canonical(payload).encode(), hashlib.sha256
            ).hexdigest()
        if not hmac.compare_digest(canonical(reply["result"]), canonical(expected)):
            raise ValueError("Worker result failed integrity validation")
        return expected
    except (KeyError, TypeError, AttributeError, UnicodeError) as error:
        raise ValueError("Invalid worker response") from error
