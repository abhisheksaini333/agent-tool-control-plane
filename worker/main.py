"""Dependency-free, fixed-handler worker. No shell or dynamic imports."""
import hashlib
import hmac
from pathlib import Path
import json
import re
import sys

CREDENTIAL_PATH = Path("/run/credential/key")

FIELDS = {"protocol", "request_id", "tenant", "binding", "handler", "arguments"}


def text_argument(arguments):
    if (
        set(arguments) != {"text"}
        or not isinstance(arguments["text"], str)
        or len(arguments["text"]) > 4096
    ):
        raise ValueError("Invalid text argument")
    return arguments["text"]


def handle(request):
    if (
        not isinstance(request, dict)
        or set(request) != FIELDS
        or type(request["protocol"]) is not int
        or request["protocol"] != 1
    ):
        raise ValueError("Invalid protocol")
    for name in ["request_id", "tenant"]:
        if not isinstance(request[name], str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}", request[name]
        ):
            raise ValueError("Invalid identity")
    if not isinstance(request["binding"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", request["binding"]
    ):
        raise ValueError("Invalid binding")
    if not isinstance(request["arguments"], dict):
        raise ValueError("Invalid arguments")
    if request["handler"] in {"sha256", "sign_report"}:
        text = text_argument(request["arguments"])
        result = {
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "bytes": len(text.encode()),
        }
        if request["handler"] == "sign_report":
            result["signature"] = sign(request)
    else:
        raise ValueError("Unknown installed handler")
    return {
        "protocol": 1,
        "request_id": request["request_id"],
        "binding": request["binding"],
        "handler": request["handler"],
        "result": result,
    }


def sign(request):
    key = CREDENTIAL_PATH.read_bytes()
    if not 32 <= len(key) <= 4096:
        raise ValueError("Invalid credential length")
    payload = json.dumps(
        request,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def main():
    try:
        payload = sys.stdin.buffer.read(65537)
        if len(payload) > 65536:
            raise ValueError("Input too large")
        request = json.loads(payload)
        reply = handle(request)
        print(json.dumps(reply, sort_keys=True, separators=(",", ":"), allow_nan=False))
        return 0
    except OSError:
        print('{"error":"credential_unavailable"}')
        return 3
    except (ValueError, TypeError, KeyError, UnicodeError):
        print('{"error":"invalid_request"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
