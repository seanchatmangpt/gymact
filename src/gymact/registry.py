"""Built-in provider registry; semantic capability identity stays shared across transports."""
from __future__ import annotations

from typing import Any

from gymact.gyms.cloudsim import CLOUDSIM_CAPABILITIES, CloudSimProvider
from gymact.gyms.ggen import GGEN_CAPABILITIES, GgenProvider
from gymact.gyms.sregym import SREGYM_RUN_CAPABILITY, SREGymProvider
from gymact.gyms.swegym import SWEGYM_EVALUATE_CAPABILITY, SWEGymProvider
from gymact.local_providers import (
    FILESYSTEM_CAPABILITIES,
    GIT_CAPABILITIES,
    SQLITE_CAPABILITIES,
    FilesystemProvider,
    GitProvider,
    SQLiteProvider,
)
from gymact.network_providers import HTTP_JSON_CAPABILITIES, HTTPJSONProvider
from gymact.providers import MEMORY_CAPABILITIES, MemoryProvider

_BUILTINS = {
    "cloudsim": (CloudSimProvider, CLOUDSIM_CAPABILITIES),
    "filesystem": (FilesystemProvider, FILESYSTEM_CAPABILITIES),
    "ggen": (GgenProvider, GGEN_CAPABILITIES),
    "git": (GitProvider, GIT_CAPABILITIES),
    "http-json": (HTTPJSONProvider, HTTP_JSON_CAPABILITIES),
    "memory": (MemoryProvider, MEMORY_CAPABILITIES),
    "sqlite": (SQLiteProvider, SQLITE_CAPABILITIES),
    "sregym": (SREGymProvider, (SREGYM_RUN_CAPABILITY,)),
    "swegym": (SWEGymProvider, (SWEGYM_EVALUATE_CAPABILITY,)),
}


def builtin_provider_names() -> tuple[str, ...]:
    return tuple(sorted(_BUILTINS))


def builtin_capabilities(name: str) -> tuple[Any, ...]:
    try:
        return _BUILTINS[name][1]
    except KeyError as exc:
        raise ValueError(f"UNKNOWN_BUILTIN_PROVIDER:{name}") from exc


def create_builtin_provider(name: str) -> Any:
    try:
        provider_type = _BUILTINS[name][0]
    except KeyError as exc:
        raise ValueError(f"UNKNOWN_BUILTIN_PROVIDER:{name}") from exc
    return provider_type()


def describe_builtin_provider(name: str) -> dict[str, Any]:
    provider = create_builtin_provider(name)
    return {
        "name": name,
        "type": type(provider).__name__,
        "materialization_requires_authority": bool(getattr(provider, "materialization_requires_authority", False)),
        "capabilities": [item.model_dump(mode="json") for item in builtin_capabilities(name)],
    }
