#!/usr/bin/env python3
"""Emit a real, generated JSON manifest of every registered builtin provider's
real capabilities.

Closes a real, named follow-up from `~/ggen/packs/domain-capability-pack`
(uncommitted WIP as of 2026-08-11): that pack found a live drift bug --
`autofde-lab`'s `src/autofde_lab/fabric/gymact_capabilities.toml` allowlist
hand-transcribes a subset of `gymact.gyms.sregym.SREGYM_CAPABILITIES`, and its
own header comment ("5 entries; there is no jaeger/loki/prometheus capability
in the real gymact source -- only these 5 exist") went stale the moment
`sregym.py`'s real capability count grew from 5 to 14, undetected until read
by hand. That pack's own `pack.toml` names the fix as explicit, deliberate,
out-of-scope-for-that-pack-version: "fixing gymact_capabilities.toml to be
GENERATED from this pack's admitted facts is out of scope for this version --
named follow-up, lives in a different repo." Gymact is that repo; this script
is the producer side of that follow-up -- a stable, checkable source of truth
a downstream allowlist (in any repo) can be generated from or diffed against,
instead of hand-copied and left to drift silently.

This does not, and cannot, fix `autofde-lab`'s TOML file directly (different
repo, no write access implied here) -- it only makes gymact's own real
capability surface mechanically enumerable so a consumer's own drift-guard
(such as `domain-capability-pack`'s `gates/020_exact_count_per_source.rq`) has
real, current data to check against.

Usage:
    uv run python scripts/capability_manifest.py [output_path]

With no argument, prints the manifest to stdout. With a path argument, writes
it there instead (and still prints a one-line summary to stdout).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gymact.registry import _BUILTINS  # noqa: E402  (see module docstring)


def build_manifest() -> dict[str, Any]:
    """Real, sorted, deterministic manifest of every builtin provider's real
    capabilities -- one entry per (provider, capability), reading directly off
    `gymact.registry._BUILTINS`, the same real registry
    `tests/test_registry_completeness_chicago.py` already introspects."""
    providers: list[dict[str, Any]] = []
    for provider_name in sorted(_BUILTINS):
        _provider_cls, capabilities = _BUILTINS[provider_name]
        entries = [
            {
                "iri": capability.iri,
                "title": capability.title,
                "consequence": capability.consequence.value,
                "binding": capability.binding,
            }
            for capability in capabilities
        ]
        entries.sort(key=lambda entry: entry["binding"])
        providers.append(
            {
                "provider": provider_name,
                "capability_count": len(entries),
                "capabilities": entries,
            }
        )
    total = sum(p["capability_count"] for p in providers)
    return {
        "schema": "gymact-capability-manifest-v1",
        "provider_count": len(providers),
        "total_capability_count": total,
        "providers": providers,
    }


def main(argv: list[str]) -> int:
    manifest = build_manifest()
    rendered = json.dumps(manifest, indent=2, sort_keys=False)

    if argv:
        output_path = Path(argv[0])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n")
        print(
            f"capability_manifest: wrote {manifest['provider_count']} providers, "
            f"{manifest['total_capability_count']} capabilities to {output_path}"
        )
    else:
        print(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
