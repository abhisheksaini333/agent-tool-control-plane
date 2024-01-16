import math
import pytest
from keel.canonical import canonical, digest


def test_canonical_digest_is_order_independent_and_type_sensitive():
    assert digest({"b": 2, "a": "✓"}) == digest({"a": "✓", "b": 2})
    assert digest({"amount": 1}) != digest({"amount": "1"})
    assert canonical({"x": "✓"}) == '{"x":"✓"}'


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1: "bad"}, (1, 2), {"a": object()}, 2 ** 54])
def test_nonportable_or_ambiguous_json_is_rejected(value):
    with pytest.raises(ValueError):
        canonical(value)


def test_nested_payloads_are_bounded():
    value = {}
    for _ in range(30):
        value = {"a": value}
    with pytest.raises(ValueError):
        canonical(value)
    with pytest.raises(ValueError):
        canonical({"text": "x" * 70000})
