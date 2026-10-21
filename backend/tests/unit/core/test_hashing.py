import pytest

from app.core.hashing import compute_payload_hash


def test_known_value():
    # sha256 of the exact text {"a":1,"b":2}
    expected = "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    assert compute_payload_hash({"a": 1, "b": 2}) == expected


def test_key_order_does_not_matter():
    assert compute_payload_hash({"a": 1, "b": 2}) == compute_payload_hash({"b": 2, "a": 1})


def test_nested_key_order_does_not_matter():
    one = {"x": {"p": 1, "q": 2}, "y": [1, 2]}
    two = {"y": [1, 2], "x": {"q": 2, "p": 1}}
    assert compute_payload_hash(one) == compute_payload_hash(two)


def test_different_payloads_give_different_hashes():
    assert compute_payload_hash({"amount": 100}) != compute_payload_hash({"amount": 101})


def test_list_order_matters():
    assert compute_payload_hash({"a": [1, 2]}) != compute_payload_hash({"a": [2, 1]})


def test_hash_is_64_lowercase_hex():
    h = compute_payload_hash({"k": "v"})
    assert len(h) == 64
    assert h == h.lower()
    int(h, 16)


def test_empty_payload_is_allowed():
    assert len(compute_payload_hash({})) == 64


def test_unicode_is_hashed_as_utf8():
    assert compute_payload_hash({"name": "José"}) == "0264c9b67e4687fb6eb775c9517fa029a75fa2b3e041da81bd8703885d13647b"


def test_nan_is_rejected():
    with pytest.raises(ValueError):
        compute_payload_hash({"x": float("nan")})
