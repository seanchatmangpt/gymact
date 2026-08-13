"""Read-only discovery adapter for the Awesome AI Gyms DFCM registry."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_REGISTRY_COLUMNS = (
    "name",
    "canonical_url",
    "category",
    "kind",
    "modes",
    "tags",
    "provenance",
)


@dataclass(frozen=True, slots=True)
class AwesomeAIGymCandidate:
    """An inert catalog candidate; never an admitted or constructible provider."""

    gym_ref: str
    name: str
    canonical_url: str
    category: str
    kind: str
    modes: tuple[str, ...]
    tags: tuple[str, ...]
    provenance: tuple[str, ...]
    standing: Literal["UNKNOWN"] = "UNKNOWN"
    authority: Literal["NONE"] = "NONE"
    admission: Literal["CANDIDATE_ONLY"] = "CANDIDATE_ONLY"


def parse_awesome_ai_gyms_tsv(text: str) -> tuple[AwesomeAIGymCandidate, ...]:
    """Parse canonical TSV without registering, importing, or materializing any gym."""

    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    if tuple(reader.fieldnames or ()) != _REGISTRY_COLUMNS:
        raise ValueError(f"AWESOME_AI_GYMS_COLUMNS:{reader.fieldnames!r}")

    candidates: list[AwesomeAIGymCandidate] = []
    seen_urls: set[str] = set()
    for row in reader:
        canonical_url = row["canonical_url"].strip()
        if canonical_url in seen_urls:
            raise ValueError(f"AWESOME_AI_GYM_DUPLICATE_URL:{canonical_url}")
        seen_urls.add(canonical_url)
        provenance = tuple(value for value in row["provenance"].split(",") if value)
        if not canonical_url.startswith("https://") or not provenance:
            raise ValueError(f"AWESOME_AI_GYM_INVALID_CANDIDATE:{row['name']}")
        candidates.append(
            AwesomeAIGymCandidate(
                gym_ref=canonical_url,
                name=row["name"].strip(),
                canonical_url=canonical_url,
                category=row["category"].strip(),
                kind=row["kind"].strip(),
                modes=tuple(value for value in row["modes"].split(",") if value),
                tags=tuple(value for value in row["tags"].split(",") if value),
                provenance=provenance,
            )
        )
    return tuple(candidates)


def load_awesome_ai_gyms(path: str | Path) -> tuple[AwesomeAIGymCandidate, ...]:
    """Load candidates from a caller-selected registry projection."""

    return parse_awesome_ai_gyms_tsv(Path(path).read_text(encoding="utf-8"))
