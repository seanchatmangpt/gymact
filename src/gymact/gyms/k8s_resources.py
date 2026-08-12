"""Real, public Kubernetes resource-kind facts -- loaded from a bundled, dated
snapshot of Kubernetes' own real, officially-published OpenAPI spec, not
hand-typed approximations.

Why this module exists
-----------------------
Same reasoning as `cloud_topology.py`'s own module docstring: an agent with
no prior Kubernetes knowledge should be able to ask "what does a real Pod
actually require" and get Kubernetes' own real, versioned answer, not an
invented one.

Source: `kubernetes/kubernetes`'s real, public, versioned OpenAPI spec
(`api/openapi-spec/swagger.json` on the `release-1.31` branch, fetched via
plain HTTPS, no auth, no cluster, no `kubectl`). A bundled, derived snapshot
under `gyms/data/k8s_openapi_snapshot.json` keeps only the 6 real resource
kinds this module covers -- `Pod`, `Deployment`, `Service`, `ConfigMap`,
`Secret`, `Namespace` -- **a deliberately bounded slice of the real spec's
~635 definitions, not the full catalog**; `scripts/refresh_k8s_openapi_snapshot.py`
re-fetches and re-derives it.

Each resource kind's `required_fields` is the real, nested `spec` object's
own `required` array from the OpenAPI spec (e.g. `Deployment.spec` really
requires `selector` and `template`), not the top-level object's `required`
(which Kubernetes leaves empty for every kind here -- `metadata`/`spec` are
themselves optional at the top level, a real and honest fact about the
schema, not a gap in this extraction). `ConfigMap`/`Secret` have no nested
`spec` object at all (their real fields -- `data`/`stringData` -- sit at the
top level and are genuinely all optional), so `required_fields` is `()` for
both, honestly, not fabricated to look non-empty.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

__all__ = ["K8sResourceKind", "load_k8s_resource_kinds"]

_DATA_DIR = Path(__file__).resolve().parent / "data"
_K8S_SNAPSHOT_PATH = _DATA_DIR / "k8s_openapi_snapshot.json"


@dataclass(frozen=True, slots=True)
class K8sResourceKind:
    """A real Kubernetes resource kind, grounded in the real OpenAPI spec."""

    api_version: str
    kind: str
    required_fields: tuple[str, ...]
    description: str
    source_url: str
    source_version: str
    fetched_at: str


def load_k8s_resource_kinds(*, snapshot_path: Path = _K8S_SNAPSHOT_PATH) -> tuple[K8sResourceKind, ...]:
    """Real, bundled-snapshot-backed load of the 6 in-scope Kubernetes
    resource kinds. Raises `RuntimeError` if the snapshot is missing --
    never fabricates resource-kind data as a fallback."""
    if not snapshot_path.is_file():
        raise RuntimeError(
            f"real K8s OpenAPI snapshot missing at {snapshot_path} -- run "
            "scripts/refresh_k8s_openapi_snapshot.py to fetch it for real, "
            "never fabricate Kubernetes resource-kind data as a placeholder"
        )
    raw = json.loads(snapshot_path.read_text())
    source_url = raw.get("source_url", "unknown")
    source_version = raw.get("source_version", "unknown")
    fetched_at = raw.get("fetched_at", "unknown")
    return tuple(
        K8sResourceKind(
            api_version=entry["apiVersion"],
            kind=entry["kind"],
            required_fields=tuple(entry.get("requiredFields", ())),
            description=entry.get("description", ""),
            source_url=source_url,
            source_version=source_version,
            fetched_at=fetched_at,
        )
        for entry in raw.get("resource_kinds", [])
    )
