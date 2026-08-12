#!/usr/bin/env python3
"""Re-fetch the real, public, credential-free Kubernetes OpenAPI resource-kind
snapshot bundled under `src/gymact/gyms/data/k8s_openapi_snapshot.json` and
used by `gymact.gyms.k8s_resources`.

Source: `kubernetes/kubernetes`'s real, public, versioned OpenAPI spec
(`api/openapi-spec/swagger.json`), fetched over plain HTTPS -- no auth, no
cluster, no `kubectl`. Deliberately bounded to 6 real resource kinds
(`Pod`, `Deployment`, `Service`, `ConfigMap`, `Secret`, `Namespace`), the
same disclosed-narrowing convention `k8s_resources.py`'s own module
docstring names -- not the full ~635-definition spec.

Run this periodically to keep the bundled snapshot from silently going
stale; the snapshot records its own real `fetched_at` timestamp and the
source branch/ref (`source_version`) so staleness is honestly checkable.
"""

from __future__ import annotations

import datetime
import json
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "src" / "gymact" / "gyms" / "data"

_K8S_REF = "release-1.31"
_K8S_SPEC_URL = (
    f"https://raw.githubusercontent.com/kubernetes/kubernetes/{_K8S_REF}"
    "/api/openapi-spec/swagger.json"
)

# Real definition keys -> (kind, nested spec definition key or None).
# ConfigMap/Secret have no nested spec object -- their real fields (data/
# stringData) sit at the top level and are genuinely all optional.
_TARGETS: tuple[tuple[str, str | None], ...] = (
    ("io.k8s.api.core.v1.Pod", "io.k8s.api.core.v1.PodSpec"),
    ("io.k8s.api.apps.v1.Deployment", "io.k8s.api.apps.v1.DeploymentSpec"),
    ("io.k8s.api.core.v1.Service", "io.k8s.api.core.v1.ServiceSpec"),
    ("io.k8s.api.core.v1.ConfigMap", None),
    ("io.k8s.api.core.v1.Secret", None),
    ("io.k8s.api.core.v1.Namespace", "io.k8s.api.core.v1.NamespaceSpec"),
)


def _fetch(url: str, *, timeout: float = 30.0) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 -- real, public, HTTPS-only URL
        return response.read()


def refresh_k8s_snapshot() -> Path:
    spec = json.loads(_fetch(_K8S_SPEC_URL))
    defs = spec["definitions"]

    resource_kinds = []
    for key, spec_key in _TARGETS:
        d = defs[key]
        gvk = d.get("x-kubernetes-group-version-kind", [{}])[0]
        group = gvk.get("group", "")
        version = gvk.get("version", "")
        api_version = f"{group}/{version}" if group else version
        required = sorted(defs[spec_key].get("required", [])) if spec_key else []
        resource_kinds.append(
            {
                "apiVersion": api_version,
                "kind": gvk.get("kind"),
                "requiredFields": required,
                "description": (d.get("description") or "").strip(),
            }
        )

    snapshot = {
        "source_url": _K8S_SPEC_URL,
        "source_version": _K8S_REF,
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "resource_kinds": resource_kinds,
    }
    out_path = DATA_DIR / "k8s_openapi_snapshot.json"
    out_path.write_text(json.dumps(snapshot, indent=2) + "\n")
    return out_path


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = refresh_k8s_snapshot()
    print(f"wrote {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
