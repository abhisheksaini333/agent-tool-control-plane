"""Dependency-free, fixed-handler worker. No shell or dynamic imports."""
import hashlib
import json
import re
import sys

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
    if request["handler"] == "sha256":
        text = text_argument(request["arguments"])
        result = {
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "bytes": len(text.encode()),
        }
    else:
        raise ValueError("Unknown installed handler")
    return {
        "protocol": 1,
        "request_id": request["request_id"],
        "binding": request["binding"],
        "handler": request["handler"],
        "result": result,
    }


def main():
    try:
        payload = sys.stdin.buffer.read(65537)
        if len(payload) > 65536:
            raise ValueError("Input too large")
        request = json.loads(payload)
        reply = handle(request)
        print(json.dumps(reply, sort_keys=True, separators=(",", ":"), allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, UnicodeError):
        print('{"error":"invalid_request"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
