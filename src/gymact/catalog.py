"""Unified provider catalog for built-ins, exact-pinned benchmark vendors, and plugins.

Catalog membership is structural knowledge, not execution readiness. Creating or
registering a provider never implies that dependencies, data, authority, budget, or a
benchmark evaluator are available.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from gymact.gyms.vendor_benchmarks import VENDOR_SPECS, audit_vendor, provider_for_vendor
from gymact.models import FrozenModel, Standing
from gymact.plugins import load_provider_plugin
from gymact.providers import EnvironmentProvider
from gymact.registry import builtin_provider_names, create_builtin_provider


class ProviderSource(StrEnum):
    BUILTIN = "BUILTIN"
    VENDOR_BENCHMARK = "VENDOR_BENCHMARK"
    PLUGIN = "PLUGIN"


class ProviderDescriptor(FrozenModel):
    name: str
    source: ProviderSource
    revision: str | None = None
    materialization_requires_authority: bool | None = None
    source_ref: str


class ProviderReadiness(FrozenModel):
    descriptor: ProviderDescriptor
    standing: Standing
    reason: str

    @property
    def ready_for_materialization_attempt(self) -> bool:
        return self.standing in {Standing.STRUCTURAL, Standing.PARTIAL_ALIVE, Standing.ALIVE}


@dataclass(frozen=True, slots=True)
class _CatalogEntry:
    descriptor: ProviderDescriptor
    factory: Callable[[], EnvironmentProvider]


class ProviderCatalog:
    """Explicit provider construction registry with zero ambient execution."""

    def __init__(self) -> None:
        self._entries: dict[str, _CatalogEntry] = {}

    def add(
        self,
        descriptor: ProviderDescriptor,
        factory: Callable[[], EnvironmentProvider],
    ) -> None:
        if descriptor.name in self._entries:
            raise ValueError(f"DUPLICATE_PROVIDER:{descriptor.name}")
        self._entries[descriptor.name] = _CatalogEntry(descriptor, factory)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def describe(self, name: str) -> ProviderDescriptor:
        try:
            return self._entries[name].descriptor
        except KeyError as exc:
            raise KeyError(f"UNSUPPORTED:UNKNOWN_PROVIDER:{name}") from exc

    def create(self, name: str) -> EnvironmentProvider:
        try:
            provider = self._entries[name].factory()
        except KeyError as exc:
            raise KeyError(f"UNSUPPORTED:UNKNOWN_PROVIDER:{name}") from exc
        if not isinstance(provider, EnvironmentProvider):
            raise TypeError(f"provider {name!r} does not satisfy EnvironmentProvider")
        return provider

    def register(self, runtime: object, names: Iterable[str] | None = None) -> tuple[str, ...]:
        register_provider = getattr(runtime, "register_provider", None)
        if register_provider is None:
            raise TypeError("runtime does not expose register_provider")
        selected = tuple(names) if names is not None else self.names()
        for name in selected:
            register_provider(self.create(name))
        return selected

    def readiness(
        self,
        name: str,
        *,
        lab_root: str | Path | None = None,
    ) -> ProviderReadiness:
        descriptor = self.describe(name)
        if descriptor.source is ProviderSource.VENDOR_BENCHMARK:
            audit = audit_vendor(
                name,
                root=(Path(lab_root).expanduser() / "vendor" / "gyms" / name)
                if lab_root is not None
                else None,
            )
            standing = {
                "PARTIAL_ALIVE": Standing.PARTIAL_ALIVE,
                "BLOCKED": Standing.BLOCKED,
                "REFUSED": Standing.REFUSED,
            }.get(audit.standing, Standing.UNKNOWN)
            return ProviderReadiness(
                descriptor=descriptor,
                standing=standing,
                reason=audit.reason,
            )
        if descriptor.source is ProviderSource.PLUGIN:
            try:
                self.create(name)
            except Exception as exc:
                return ProviderReadiness(
                    descriptor=descriptor,
                    standing=Standing.BLOCKED,
                    reason=f"PLUGIN_LOAD_BLOCKED:{type(exc).__name__}",
                )
        return ProviderReadiness(
            descriptor=descriptor,
            standing=Standing.STRUCTURAL,
            reason="PROVIDER_CONSTRUCTIBLE_NOT_MATERIALIZED",
        )


def _plugin_factory(name: str) -> Callable[[], EnvironmentProvider]:
    def load() -> EnvironmentProvider:
        result = load_provider_plugin(name)
        if result.standing is not Standing.ALIVE or result.provider is None:
            raise RuntimeError(f"PLUGIN_NOT_ALIVE:{name}:{result.standing.value}")
        if not isinstance(result.provider, EnvironmentProvider):
            raise TypeError("plugin does not satisfy EnvironmentProvider")
        return result.provider

    return load


def default_provider_catalog(*, plugin_names: Iterable[str] = ()) -> ProviderCatalog:
    """Return the common provider basis without touching any consequential world."""

    catalog = ProviderCatalog()
    for name in builtin_provider_names():
        provider = create_builtin_provider(name)
        catalog.add(
            ProviderDescriptor(
                name=name,
                source=ProviderSource.BUILTIN,
                materialization_requires_authority=bool(
                    getattr(provider, "materialization_requires_authority", False)
                ),
                source_ref=f"urn:gymact:provider:builtin:{name}",
            ),
            lambda name=name: create_builtin_provider(name),
        )
    for name, spec in sorted(VENDOR_SPECS.items()):
        catalog.add(
            ProviderDescriptor(
                name=name,
                source=ProviderSource.VENDOR_BENCHMARK,
                revision=spec.revision,
                materialization_requires_authority=True,
                source_ref=f"urn:gymact:vendor:{name}:{spec.revision}",
            ),
            lambda name=name: provider_for_vendor(name),
        )
    for name in sorted(set(plugin_names)):
        catalog.add(
            ProviderDescriptor(
                name=name,
                source=ProviderSource.PLUGIN,
                source_ref=f"urn:gymact:provider-plugin:{name}",
            ),
            _plugin_factory(name),
        )
    return catalog
