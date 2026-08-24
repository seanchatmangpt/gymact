def normalize_provider_result(result: dict[str, object]) -> tuple[object, object, object]:
    return result.get("accepted"), result.get("changed"), result.get("verified")


def test_provider_equivalence_requires_same_semantic_outcome_not_same_shape() -> None:
    left = {"accepted": True, "changed": True, "verified": False, "provider": "a"}
    right = {"accepted": True, "changed": True, "verified": False, "provider": "b", "latency_ms": 2}
    divergent = {"accepted": True, "changed": False, "verified": False, "provider": "c"}
    assert normalize_provider_result(left) == normalize_provider_result(right)
    assert normalize_provider_result(left) != normalize_provider_result(divergent)
