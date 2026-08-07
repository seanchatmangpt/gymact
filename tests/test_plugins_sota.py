from __future__ import annotations

from dataclasses import dataclass

import gymact.plugins as plugins
from gymact import MemoryProvider, Standing


@dataclass(frozen=True)
class _Entry:
    name: str
    value: str
    loaded: object

    def load(self) -> object:
        if isinstance(self.loaded, Exception):
            raise self.loaded
        return self.loaded


def test_plugin_discovery_is_metadata_only_and_sorted() -> None:
    entries = (
        _Entry("zeta", "zeta:Provider", RuntimeError("must-not-load")),
        _Entry("alpha", "alpha:Provider", RuntimeError("must-not-load")),
    )
    discovered = plugins.discover_provider_plugins(entries)
    assert [item.name for item in discovered] == ["alpha", "zeta"]
    assert [item.value for item in discovered] == ["alpha:Provider", "zeta:Provider"]


def test_explicit_plugin_load_accepts_environment_provider() -> None:
    entry = _Entry("memory", "module:provider", MemoryProvider())
    result = plugins.load_provider_plugin("memory", (entry,))
    assert result.standing == Standing.ALIVE
    assert isinstance(result.provider, MemoryProvider)


def test_duplicate_plugin_identity_is_refused_without_import() -> None:
    entries = (
        _Entry("duplicate", "a:Provider", RuntimeError("must-not-load")),
        _Entry("duplicate", "b:Provider", RuntimeError("must-not-load")),
    )
    result = plugins.load_provider_plugin("duplicate", entries)
    assert result.standing == Standing.REFUSED
    assert result.error_type == "DuplicateEntryPoint"
    assert result.error_digest is not None and len(result.error_digest) == 64


def test_plugin_import_failure_is_blocked_and_hashed() -> None:
    entry = _Entry("broken", "broken:Provider", RuntimeError("secret diagnostic"))
    result = plugins.load_provider_plugin("broken", (entry,))
    assert result.standing == Standing.BLOCKED
    assert result.error_type == "RuntimeError"
    assert result.error_digest is not None and len(result.error_digest) == 64
    assert "secret diagnostic" not in result.model_dump_json()


def test_plugin_contract_failure_is_blocked() -> None:
    entry = _Entry("wrong", "wrong:value", object())
    result = plugins.load_provider_plugin("wrong", (entry,))
    assert result.standing == Standing.BLOCKED
    assert result.error_type == "TypeError"
