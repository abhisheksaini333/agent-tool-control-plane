"""Bounded, portable JSON used for exact request bindings."""
import hashlib
import json
import math


def _validate(value, depth=0):
    if depth > 20:
        raise ValueError("JSON nesting exceeds 20 levels")
    if value is None or type(value) in {str, bool}:
        return
    if type(value) is int:
        if abs(value) > 2**53 - 1:
            raise ValueError("Integers must be portable across JSON clients")
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Non-finite numbers are not JSON")
        return
    if type(value) is list:
        for item in value:
            _validate(item, depth + 1)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _validate(item, depth + 1)
        return
    raise ValueError("Only JSON values and string object keys are accepted")


def canonical(value):
    _validate(value)
    text = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    if len(text.encode("utf-8")) > 65536:
        raise ValueError("JSON exceeds 64 KiB")
    return text


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()
