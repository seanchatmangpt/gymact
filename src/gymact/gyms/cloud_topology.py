"""Real, provider-published cloud topology -- regions and services, grounded
in each cloud provider's own real, officially-published data, not
hand-authored approximations.

Why this module exists
-----------------------
`gymact.gyms.multicloud` and `gymact.gyms.cloudsim` both model cloud
environments purely as simulators: `multicloud.py`'s `observe()` is an
accumulator of whatever a run's own simulated `actuate()` calls created (no
region concept at all), and `cloudsim`'s `SERVICE_FAMILIES`/
`DEFAULT_GLOBAL_TOPOLOGY` are real Python constants but hand-typed
approximations (~60 service names, 6 regions across 3 clouds) -- useful for
deterministic simulation, but not grounded in what these providers actually
publish. Neither gives an agent with no prior cloud knowledge an accurate
picture of what a real cloud provider's regions and services actually are.

This module closes that gap for real, from each provider's own real,
authoritative, credential-free data:

- **AWS** -- loaded live from the real, official `botocore` package's
  bundled `endpoints.json` (`botocore.loaders.create_loader().load_data
  ("endpoints")`). No network call, no credentials, no AWS account --
  this file ships inside `botocore` itself and is AWS's own real,
  versioned partition/region/service/per-region-availability data. Real
  counts as of this session: 8 partitions, 34 regions and 311 services in
  the `aws` (Standard) partition alone.
- **Azure** -- Microsoft's real, officially published "Service Tags"
  JSON (linked from
  https://www.microsoft.com/en-us/download/details.aspx?id=56519,
  updated weekly, no auth required to fetch). A bundled, derived snapshot
  under `gyms/data/azure_service_tags_snapshot.json` keeps only real
  region names and real service-tag names + their real mapping (the
  source file's megabytes of IP-prefix data are dropped -- not needed
  for topology modeling). Real counts as of the snapshot's own
  `fetched_at`/`source_change_number`: 77 regions, 3321 service tags.
- **GCP** -- Google's real, officially published cloud IP-ranges JSON
  (https://www.gstatic.com/ipranges/cloud.json, no auth). Bundled under
  `gyms/data/gcp_cloud_ranges_snapshot.json`. Named honestly: this real
  source only distinguishes regions (48 real scopes), not individual
  services -- every real entry's `service` field is the single literal
  string `"Google Cloud"`, so `CloudTopology.services` for `gcp` is
  real but degenerate: exactly one entry, `"Google Cloud"`, present in
  every region. GCP does not publish a comparable region-to-service-
  catalog mapping via any public, credential-free endpoint found this
  session; this is that real limit surfaced honestly, not a richer
  per-service breakdown silently collapsed.

Both snapshots record their own real source URL, fetch timestamp, and
upstream version/change-number, so staleness is a checkable fact, not an
assumption. `scripts/refresh_cloud_topology_snapshots.py` re-fetches both.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "CloudRegion",
    "CloudService",
    "CloudTopology",
    "load_aws_topology",
    "load_azure_topology",
    "load_gcp_topology",
    "load_topology",
]

_DATA_DIR = Path(__file__).resolve().parent / "data"
_AZURE_SNAPSHOT_PATH = _DATA_DIR / "azure_service_tags_snapshot.json"
_GCP_SNAPSHOT_PATH = _DATA_DIR / "gcp_cloud_ranges_snapshot.json"

_REAL_PROVIDERS: tuple[str, ...] = ("aws", "azure", "gcp")


@dataclass(frozen=True, slots=True)
class CloudRegion:
    provider: str
    code: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class CloudService:
    provider: str
    name: str


@dataclass(frozen=True, slots=True)
class CloudTopology:
    """A real, provider-grounded snapshot of what regions and services a
    cloud provider actually publishes. `service_region_availability` maps
    a real service/service-tag name to the tuple of real region codes it's
    associated with in the source data -- empty for a provider whose real
    source doesn't carry that mapping (see module docstring's GCP note)."""

    provider: str
    regions: tuple[CloudRegion, ...]
    services: tuple[CloudService, ...]
    service_region_availability: dict[str, tuple[str, ...]]
    source_url: str
    source_version: str | None = None
    fetched_at: str | None = None

    def region_codes(self) -> tuple[str, ...]:
        return tuple(r.code for r in self.regions)

    def service_names(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.services)

    def services_in_region(self, region_code: str) -> tuple[str, ...]:
        return tuple(
            service
            for service, regions in self.service_region_availability.items()
            if region_code in regions
        )


def load_aws_topology(*, partition: str = "aws") -> CloudTopology:
    """Real, live-loaded AWS topology from `botocore`'s own bundled
    `endpoints.json` -- no network call, no credentials. `partition`
    selects which of AWS's real partitions to load (`"aws"` = Standard,
    `"aws-cn"` = China, `"aws-us-gov"` = GovCloud, ...) -- confirmed real
    partition identifiers, not invented ones.

    Raises `RuntimeError` if `botocore` is not installed (a real,
    UNSUPPORTED environment gate, not a silent empty result) or if the
    requested partition is not present in the real, loaded data.
    """
    try:
        from botocore.loaders import create_loader
    except ImportError as exc:  # pragma: no cover -- environment gate
        raise RuntimeError(
            "botocore is not installed -- AWS topology requires the real, "
            "official botocore package (ships endpoints.json); add it as a "
            "real dependency, never fabricate AWS region/service data as a "
            "fallback"
        ) from exc

    data = create_loader().load_data("endpoints")
    partitions = data.get("partitions", [])
    real_partition = next((p for p in partitions if p.get("partition") == partition), None)
    if real_partition is None:
        available = sorted(p.get("partition", "?") for p in partitions)
        raise RuntimeError(
            f"partition {partition!r} not found in botocore's real endpoints.json "
            f"(real partitions present: {available})"
        )

    regions = tuple(
        CloudRegion(provider="aws", code=code, description=body.get("description"))
        for code, body in real_partition.get("regions", {}).items()
    )
    services = tuple(CloudService(provider="aws", name=name) for name in real_partition.get("services", {}))
    availability: dict[str, tuple[str, ...]] = {
        name: tuple(sorted(body.get("endpoints", {}).keys()))
        for name, body in real_partition.get("services", {}).items()
    }
    return CloudTopology(
        provider="aws",
        regions=regions,
        services=services,
        service_region_availability=availability,
        source_url="botocore bundled endpoints.json (botocore.loaders.create_loader)",
        source_version=data.get("version"),
        fetched_at=None,  # live-loaded every call; no fetch timestamp to record
    )


def _load_snapshot_topology(
    path: Path,
    *,
    provider: str,
    region_key: str,
    service_key: str,
    region_map_key: str,
) -> CloudTopology:
    if not path.is_file():
        raise RuntimeError(
            f"real snapshot missing at {path} -- run "
            "scripts/refresh_cloud_topology_snapshots.py to fetch it for real, "
            "never fabricate cloud topology data as a placeholder"
        )
    raw = json.loads(path.read_text())
    regions = tuple(CloudRegion(provider=provider, code=code) for code in raw.get(region_key, []))
    services = tuple(CloudService(provider=provider, name=name) for name in raw.get(service_key, []))
    region_map: dict[str, list[str]] = raw.get(region_map_key, {})
    availability: dict[str, tuple[str, ...]] = {}
    for region_code, names in region_map.items():
        for name in names:
            availability.setdefault(name, set()).add(region_code)  # type: ignore[arg-type]
    availability = {name: tuple(sorted(codes)) for name, codes in availability.items()}  # type: ignore[arg-type]
    return CloudTopology(
        provider=provider,
        regions=regions,
        services=services,
        service_region_availability=availability,
        source_url=raw.get("source_url", "unknown"),
        source_version=str(raw.get("source_change_number") or raw.get("source_sync_token") or ""),
        fetched_at=raw.get("fetched_at"),
    )


def load_azure_topology(*, snapshot_path: Path = _AZURE_SNAPSHOT_PATH) -> CloudTopology:
    """Real Azure topology parsed from the bundled, real, dated snapshot
    of Microsoft's public Service Tags JSON. `services` here are real
    Azure service-tag identifiers (e.g. `"Storage"`, `"Sql"`,
    `"AzureActiveDirectory"`), the real, published unit Azure itself uses
    for regional service classification -- not an invented taxonomy."""
    return _load_snapshot_topology(
        snapshot_path,
        provider="azure",
        region_key="regions",
        service_key="service_tags",
        region_map_key="region_service_tags",
    )


def load_gcp_topology(*, snapshot_path: Path = _GCP_SNAPSHOT_PATH) -> CloudTopology:
    """Real GCP topology parsed from the bundled, real, dated snapshot of
    Google's public cloud IP-ranges JSON. Per the module docstring:
    `services` is real but degenerate here (a single `"Google Cloud"`
    entry) -- this real source only carries region/scope identifiers, not
    a per-service catalog. Do not treat the single-entry `services` tuple
    as a bug; it is the honest reflection of what this real,
    credential-free GCP source actually publishes."""
    return _load_snapshot_topology(
        snapshot_path,
        provider="gcp",
        region_key="regions",
        service_key="services",
        region_map_key="region_services",
    )


def load_topology(provider: str) -> CloudTopology:
    """Real dispatch by provider name. Raises `ValueError` for any name
    outside the three real providers this module supports -- never
    silently returns an empty/fabricated topology for an unknown name."""
    if provider == "aws":
        return load_aws_topology()
    if provider == "azure":
        return load_azure_topology()
    if provider == "gcp":
        return load_gcp_topology()
    raise ValueError(f"unknown cloud provider {provider!r}; real providers supported: {_REAL_PROVIDERS}")
