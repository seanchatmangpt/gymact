#!/usr/bin/env python3
"""Re-fetch the real, public, credential-free Azure and GCP topology
snapshots bundled under `src/gymact/gyms/data/` and used by
`gymact.gyms.cloud_topology`. AWS needs no snapshot -- it is loaded live
from the installed `botocore` package's own bundled `endpoints.json` on
every call (see `cloud_topology.load_aws_topology`).

Both sources are real, officially published by the respective cloud
provider, and require no authentication:

- Azure Service Tags (public cloud): the same file linked from
  https://www.microsoft.com/en-us/download/details.aspx?id=56519 -- this
  script resolves the current dated download URL by scraping that page's
  real `<a>` link (Microsoft rotates the exact filename/URL on every
  publish, per its own real `changeNumber` versioning), then fetches the
  real JSON. Only region names + service-tag names + their real mapping
  are kept in the bundled snapshot -- the source file's real IP-prefix
  lists (megabytes of CIDR blocks, not needed for topology modeling) are
  intentionally dropped to keep the snapshot small.
- GCP published IP ranges: https://www.gstatic.com/ipranges/cloud.json --
  real, small, fetched and re-derived directly.

Run this periodically to keep the bundled snapshots from silently going
stale; each snapshot records its own real `fetched_at` timestamp and
source version/change-number so staleness is honestly checkable, never
implicit.
"""

from __future__ import annotations

import datetime
import json
import re
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "src" / "gymact" / "gyms" / "data"

_AZURE_LANDING_PAGE = "https://www.microsoft.com/en-us/download/details.aspx?id=56519"
_AZURE_URL_PATTERN = re.compile(
    r"https://download\.microsoft\.com/download/[^\"']*ServiceTags_Public[^\"']*\.json"
)
_GCP_URL = "https://www.gstatic.com/ipranges/cloud.json"


def _fetch(url: str, *, timeout: float = 30.0) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 -- real, public, HTTPS-only URLs
        return response.read()


def refresh_azure_snapshot() -> Path:
    landing = _fetch(_AZURE_LANDING_PAGE).decode("utf-8", errors="replace")
    match = _AZURE_URL_PATTERN.search(landing)
    if match is None:
        raise RuntimeError(
            f"could not find a real ServiceTags_Public download link on {_AZURE_LANDING_PAGE}"
        )
    real_url = match.group(0)
    raw = json.loads(_fetch(real_url))

    regions: set[str] = set()
    service_tags: set[str] = set()
    region_service_tags: dict[str, set[str]] = {}
    for entry in raw["values"]:
        service_tags.add(entry["id"])
        region = entry["properties"].get("region")
        if region:
            regions.add(region)
            region_service_tags.setdefault(region, set()).add(entry["id"])

    snapshot = {
        "source_url": _AZURE_LANDING_PAGE,
        "source_download_url": real_url,
        "source_change_number": raw.get("changeNumber"),
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "regions": sorted(regions),
        "service_tags": sorted(service_tags),
        "region_service_tags": {k: sorted(v) for k, v in sorted(region_service_tags.items())},
    }
    out_path = DATA_DIR / "azure_service_tags_snapshot.json"
    out_path.write_text(json.dumps(snapshot, indent=2))
    return out_path


def refresh_gcp_snapshot() -> Path:
    raw = json.loads(_fetch(_GCP_URL))
    regions: set[str] = set()
    services: set[str] = set()
    region_services: dict[str, set[str]] = {}
    for prefix in raw["prefixes"]:
        scope = prefix.get("scope")
        service = prefix.get("service", "unknown")
        if scope:
            regions.add(scope)
            services.add(service)
            region_services.setdefault(scope, set()).add(service)

    snapshot = {
        "source_url": _GCP_URL,
        "source_sync_token": raw.get("syncToken"),
        "source_creation_time": raw.get("creationTime"),
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "regions": sorted(regions),
        "services": sorted(services),
        "region_services": {k: sorted(v) for k, v in sorted(region_services.items())},
    }
    out_path = DATA_DIR / "gcp_cloud_ranges_snapshot.json"
    out_path.write_text(json.dumps(snapshot, indent=2))
    return out_path


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    azure_path = refresh_azure_snapshot()
    print(f"wrote {azure_path} ({azure_path.stat().st_size} bytes)")
    gcp_path = refresh_gcp_snapshot()
    print(f"wrote {gcp_path} ({gcp_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
