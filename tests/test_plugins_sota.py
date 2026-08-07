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


def test_plugin_discovery_is_metadata_only_and_sorted(monkeypatch) -> None:
    entries = (
        _Entry("zeta", "zeta:Provider", RuntimeError("must-not-load")),
        _Entry("alpha", "alpha:Provider", RuntimeError("must-not-load")),
    )
    monkeypatch.setattr(plugins, "_provider_entry_points", lambda: entries)
    discovered = plugins.discover_provider_plugins()
    assert [item.name for item in discovered] == ["alpha", "zeta"]
    assert [item.value for item in discovered] == ["alpha:Provider", "zeta:Provider"]


def test_explicit_plugin_load_accepts_environment_provider(monkeypatch) -> None:
    entry = _Entry("memory", "module:provider", MemoryProvider())
    monkeypatch.setattr(plugins, "_provider_entry_points", lambda: (entry,))
    result = plugins.load_provider_plugin("memory")
    assert result.standing == Standing.ALIVE
    assert isinstance(result.provider, MemoryProvider)


def test_duplicate_plugin_identity_is_refused_without_import(monkeypatch) -> None:
    entries = (
        _Entry("duplicate", "a:Provider", RuntimeError("must-not-load")),
        _Entry("duplicate", "b:Provider", RuntimeError("must-not-load")),
    )
    monkeypatch.setattr(plugins, "_provider_entry_points", lambda: entries)
    result = plugins.load_provider_plugin("duplicate")
    assert result.standing == Standing.REFUSED
    assert result.error_type == "DuplicateEntryPoint"
    assert result.error_digest is not None and len(result.error_digest) == 64


def test_plugin_import_failure_is_blocked_and_hashed(monkeypatch) -> None:
    entry = _Entry("broken", "broken:Provider", RuntimeError("secret diagnostic"))
    monkeypatch.setattr(plugins, "_provider_entry_points", lambda: (entry,))
    result = plugins.load_provider_plugin("broken")
    assert result.standing == Standing.BLOCKED
    assert result.error_type == "RuntimeError"
    assert result.error_digest is not None and len(result.error_digest) == 64
    assert "secret diagnostic" not in result.model_dump_json()


def test_plugin_contract_failure_is_blocked(monkeypatch) -> None:
    entry = _Entry("wrong", "wrong:value", object())
    monkeypatch.setattr(plugins, "_provider_entry_points", lambda: (entry,))
    result = plugins.load_provider_plugin("wrong")
    assert result.standing == Standing.BLOCKED
    assert result.error_type == "TypeError"
