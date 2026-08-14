"""Bridge from the vendored `awesome-ai-gyms` registry to a typed, in-process
gym-discovery index. "The index" the user asked for: real rows read from a
real, pin-audited external checkout's `registry/gyms.tsv` -- no network
calls, no re-crawling (that already happened once in awesome-ai-gyms's own
`scripts/crawl_upstreams.py`; this module only trusts the pinned snapshot).

Deliberately does NOT project into `gymact.lab.ForwardBenchSubject`: that
model's required `ontology_ref`/`capability_refs`/`environment_ref`/
`expected_evidence` fields describe an ADMITTED subject already mapped into
GymAct's own semantic/capability graph. awesome-ai-gyms's own JSON Schema
(`schema/awesome-ai-gym.schema.json`) is explicit that every row's `standing`
is `const: "UNKNOWN"` -- these are raw, unvetted discovery candidates
(awesome-ai-gyms's own README: "DISCOVER, authority=NONE"). Forcing them
into `ForwardBenchSubject`'s admitted-subject shape would mean fabricating
placeholder ontology/capability/environment refs that don't exist yet --
exactly the kind of manufactured-looking-real-but-isn't value this codebase's
evidence discipline forbids. A real bridge from `GymIndexEntry` to
`ForwardBenchSubject` belongs in a later, separate admission step, once a
specific candidate is actually being onboarded -- not a blanket batch
projection of all 190 rows.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Literal

from gymact.gyms.vendor_benchmarks import VENDOR_REVISIONS, audit_vendor, vendor_root
from gymact.models import FrozenModel

_VENDOR_NAME = "awesome-ai-gyms"
_REGISTRY_RELATIVE_PATH = Path("registry") / "gyms.tsv"

Kind = Literal["environment", "benchmark", "simulator", "framework", "infrastructure"]


class GymIndexEntry(FrozenModel):
    """One real row of awesome-ai-gyms' `registry/gyms.tsv`, typed per its
    own real `schema/awesome-ai-gym.schema.json`. `standing` is always
    `"UNKNOWN"` per that schema's `const` constraint -- a discovered
    candidate, not an admitted GymAct subject."""

    name: str
    canonical_url: str
    category: str
    kind: Kind
    modes: tuple[str, ...]
    tags: tuple[str, ...]
    provenance: tuple[str, ...]
    standing: Literal["UNKNOWN"] = "UNKNOWN"


class GymIndexUnavailable(RuntimeError):
    """Raised when the vendored awesome-ai-gyms checkout is missing or at
    the wrong pin -- same refusal discipline as every other vendor in
    `gymact.gyms.vendor_benchmarks`, never a silent empty index."""


def load_gym_index(*, lab_root: str | Path | None = None) -> tuple[GymIndexEntry, ...]:
    """Real: audits the external `awesome-ai-gyms` checkout against its
    pinned `VENDOR_REVISIONS` SHA first (`audit_vendor`, the same primitive
    every other vendored benchmark in this repo already uses); refuses
    (raises `GymIndexUnavailable`) unless the checkout's real
    `git rev-parse HEAD` matches. Only then reads and parses the real
    `registry/gyms.tsv` file from that audited checkout."""
    checkout = vendor_root(_VENDOR_NAME, lab_root=lab_root)
    audit = audit_vendor(_VENDOR_NAME, root=checkout)
    if audit.standing != "PARTIAL_ALIVE":
        raise GymIndexUnavailable(f"{audit.reason}:root={checkout}")

    tsv_path = audit.root / _REGISTRY_RELATIVE_PATH
    if not tsv_path.is_file():
        raise GymIndexUnavailable(f"REFUSED:REGISTRY_FILE_MISSING:{tsv_path}")

    entries: list[GymIndexEntry] = []
    with tsv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            entries.append(
                GymIndexEntry(
                    name=row["name"],
                    canonical_url=row["canonical_url"],
                    category=row["category"],
                    kind=row["kind"],
                    modes=tuple(m for m in row["modes"].split(",") if m),
                    tags=tuple(t for t in row["tags"].split(",") if t),
                    provenance=tuple(p for p in row["provenance"].split(",") if p),
                )
            )
    return tuple(entries)


def gym_index_provenance_ref() -> str:
    """The real `urn:` identity for the exact snapshot every `GymIndexEntry`
    returned by `load_gym_index()` was read from -- the vendored registry's
    own pinned commit, not each individual upstream gym's own revision
    (which `registry/gyms.tsv` does not carry)."""
    return f"urn:gymact:vendor:{_VENDOR_NAME}:{VENDOR_REVISIONS[_VENDOR_NAME]}"
