from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from gymact.awesome_ai_gyms import parse_awesome_ai_gyms_tsv

HEADER = "name\tcanonical_url\tcategory\tkind\tmodes\ttags\tprovenance\n"


def test_catalog_candidates_are_inert_and_stable() -> None:
    text = HEADER + (
        "WebArena\thttps://github.com/web-arena-x/webarena\tweb\tenvironment\t"
        "train,eval\tweb-agent\taarle,arle\n"
    )

    first = parse_awesome_ai_gyms_tsv(text)[0]
    second = parse_awesome_ai_gyms_tsv(text)[0]

    assert first.gym_ref == second.gym_ref
    assert first.gym_ref.startswith("awesome-ai-gym:")
    assert first.standing == "UNKNOWN"
    assert first.authority == "NONE"
    assert first.admission == "CANDIDATE_ONLY"
    assert not hasattr(first, "provider")
    with pytest.raises(FrozenInstanceError):
        first.authority = "DO"  # type: ignore[misc]


def test_parser_preserves_all_candidates_without_selecting() -> None:
    text = HEADER + (
        "WebArena\thttps://github.com/web-arena-x/webarena\tweb\tenvironment\t"
        "eval\tweb-agent\taarle\n"
        "SWE-Gym\thttps://github.com/SWE-Gym/SWE-Gym\tcoding\tenvironment\t"
        "train,eval\tsoftware-engineering\taarle\n"
    )

    candidates = parse_awesome_ai_gyms_tsv(text)

    assert [candidate.name for candidate in candidates] == ["WebArena", "SWE-Gym"]
    assert all(candidate.standing == "UNKNOWN" for candidate in candidates)


def test_duplicate_url_is_refused() -> None:
    row = "A\thttps://github.com/example/a\tweb\tenvironment\teval\t\taarle\n"
    text = HEADER + row + row.replace("A\t", "B\t", 1)

    with pytest.raises(ValueError, match="AWESOME_AI_GYM_DUPLICATE_URL"):
        parse_awesome_ai_gyms_tsv(text)
