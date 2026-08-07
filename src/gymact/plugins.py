"""Explicit provider plugin discovery and loading.

Plugin loading is never ambient: callers must name the plugin entry point they want
to execute. Discovery itself is metadata-only.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint, entry_points

from pydantic import BaseModel, ConfigDict

from gymact.evidence import digest
from gymact.models import Standing
from gymact.providers import EnvironmentProvider

PROVIDER_ENTRYPOINT_GROUP = "gymact.providers"


class ProviderPluginInfo(BaseModel):
    """Metadata-only description of one installed provider entry point."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    value: str
    group: str = PROVIDER_ENTRYPOINT_GROUP


class ProviderPluginLoad(BaseModel):
    """Typed load standing without leaking raw exception detail."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    name: str
    standing: Standing
    provider: object | None = None
    error_type: str | None = None
    error_digest: str | None = None


def _provider_entry_points() -> tuple[EntryPoint, ...]:
    return tuple(entry_points(group=PROVIDER_ENTRYPOINT_GROUP))


def discover_provider_plugins() -> tuple[ProviderPluginInfo, ...]:
    """Return installed plugin metadata without importing plugin code."""
    return tuple(
        sorted(
            (
                ProviderPluginInfo(name=entry.name, value=entry.value)
                for entry in _provider_entry_points()
            ),
            key=lambda value: value.name,
        )
    )


def load_provider_plugin(name: str) -> ProviderPluginLoad:
    """Explicitly load one named provider plugin and validate its runtime protocol."""
    matches = [entry for entry in _provider_entry_points() if entry.name == name]
    if not matches:
        return ProviderPluginLoad(name=name, standing=Standing.UNSUPPORTED)
    if len(matches) != 1:
        return ProviderPluginLoad(
            name=name,
            standing=Standing.REFUSED,
            error_type="DuplicateEntryPoint",
            error_digest=digest({"name": name, "count": len(matches)}),
        )

    try:
        loaded = matches[0].load()
        provider = loaded() if isinstance(loaded, type) else loaded
        if not isinstance(provider, EnvironmentProvider):
            raise TypeError("entry point does not satisfy EnvironmentProvider")
    except Exception as exc:
        return ProviderPluginLoad(
            name=name,
            standing=Standing.BLOCKED,
            error_type=type(exc).__name__,
            error_digest=digest({"type": type(exc).__name__, "message": str(exc)}),
        )
    return ProviderPluginLoad(name=name, standing=Standing.ALIVE, provider=provider)
