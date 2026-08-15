from __future__ import annotations

from pathlib import Path

import pytest

from gymact.ggen_marketplace import review_marketplace
from gymact.hub import FederatedGymAdvertisement, FederatedGymRegistry
from gymact.models import Standing


def _pack(root: Path, name: str, description: str, version: str = "1.0.0") -> None:
    path = root / "packs" / name
    path.mkdir(parents=True)
    (path / "pack.toml").write_text(
        f'[pack]\nname = "{name}"\nversion = "{version}"\ndescription = "{description}"\n',
        encoding="utf-8",
    )


def test_review_scans_every_manifest_and_prioritizes_hub_semantics(tmp_path: Path) -> None:
    _pack(tmp_path, "basic-template-pack", "Generate a small static template")
    _pack(
        tmp_path,
        "federated-registry-pack",
        "Semantic registry for provider capability authority standing receipts and replay",
    )
    _pack(
        tmp_path,
        "autonomic-pack",
        "Automatic autonomic operations with receipt replay and named refusal gates",
    )

    review = review_marketplace(tmp_path)

    assert review.examined == 3
    assert review.ranked[0].pack.name == "federated-registry-pack"
    assert "federation" in review.ranked[0].dimensions
    assert "authority" in review.ranked[0].dimensions
    assert {item.pack.name for item in review.ranked} == {
        "basic-template-pack",
        "federated-registry-pack",
        "autonomic-pack",
    }


def test_review_fails_closed_on_invalid_manifest(tmp_path: Path) -> None:
    _pack(tmp_path, "broken-pack", "Broken", version="latest")
    with pytest.raises(ValueError, match="INVALID_SEMVER"):
        review_marketplace(tmp_path)


def _advertisement(gym_ref: str, *, digest: str = "a" * 64) -> FederatedGymAdvertisement:
    return FederatedGymAdvertisement(
        gym_ref=gym_ref,
        source_ref=f"{gym_ref}:catalog",
        endpoint_ref="https://gym.example.test",
        capability_refs=("urn:example:capability:solve", "urn:example:capability:observe"),
        claimed_standing=Standing.ALIVE,
        source_digest=digest,
        receipt_ref=f"{gym_ref}:receipt:1",
        protocol_refs=("https://www.w3.org/2019/wot/td",),
    )


def test_federated_registration_never_promotes_remote_alive_claim() -> None:
    registry = FederatedGymRegistry()
    record = registry.register(_advertisement("urn:example:gym:alpha"))

    assert record.advertisement.claimed_standing is Standing.ALIVE
    assert record.registry_standing is Standing.STRUCTURAL
    assert "NOT_EXECUTED" in record.admission_reason
    assert registry.register(record.advertisement) is record


def test_federated_selection_is_deterministic_and_select_only() -> None:
    registry = FederatedGymRegistry()
    registry.register(_advertisement("urn:example:gym:zeta", digest="b" * 64))
    registry.register(_advertisement("urn:example:gym:alpha", digest="c" * 64))

    result = registry.select(("urn:example:capability:solve",))

    assert result.standing is Standing.STRUCTURAL
    assert [item.advertisement.gym_ref for item in result.matches] == [
        "urn:example:gym:alpha",
        "urn:example:gym:zeta",
    ]
    assert result.reason == "ROUTE_CANDIDATES_SELECTED_NOT_EXECUTED"


def test_federated_identity_conflict_and_unsupported_route_are_explicit() -> None:
    registry = FederatedGymRegistry()
    registry.register(_advertisement("urn:example:gym:alpha"))
    with pytest.raises(ValueError, match="GYM_IDENTITY_CONFLICT"):
        registry.register(_advertisement("urn:example:gym:alpha", digest="f" * 64))

    result = registry.select(("urn:example:capability:missing",))
    assert result.standing is Standing.UNSUPPORTED
    assert result.matches == ()
