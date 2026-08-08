# Integrating a system with GymAct

**Audience**: an external system (e.g. `autofde-lab`, or any other Python codebase)
that wants to expose one or more of its own executable environments through
GymAct's semantic lifecycle, or wants GymAct's provider ecosystem (52+ vendored
benchmark gyms as of v26.8.7) available to its own planners/agents.

This is not a description of GymAct's internals — it is the checklist for
plugging a new, external system into GymAct without reinventing any of GymAct's
own contracts. Every step below names the real file/API it corresponds to in
this repo, checked against the actual source, not aspirational.

## The shape of the integration

Two independent halves, and they compose without either needing the other:

```text
Your system                              GymAct
------------                             ------
implement EnvironmentProvider   -->      registers via `gymact.providers`
  + Environment protocol                   entry-point group (discovery only,
  (Python, hand-authored)                   never ambient — see plugins.py)

declare your real capabilities  -->      validated against GymAct's real
  as sosa:Procedure facts                  SHACL shape (`urn:gymact:shape:
  (ontology.ttl, optional)                 capability`), optionally projected
                                            into Rust/MCP/docs via ggen
                                            (see ../../ggen/consumer-bridge-
                                            pack-template/)

inject your own AuthorityResolver -->    GymAct never grants authority by
  (or accept the fail-closed               itself; a DO capability is refused
  DenyAuthorityResolver default)           unless your resolver admits it

produce a real OCEL 2.0 log      -->     the only thing that may back an
  from a real end-to-end episode           "actuated" claim, per
                                            .claude/rules/ocel-standing.md
```

The first is required. The second (ontology + ggen projection) is optional and
only useful if you want a typed Rust/MCP surface or generated docs for your
capabilities — GymAct itself works with a pure-Python provider with no RDF at
all. The third and fourth apply regardless of whether you use the ontology.

## 1. Implement the provider protocol

Two `Protocol`s, both `@runtime_checkable`, in `src/gymact/providers.py`:

```python
class EnvironmentProvider(Protocol):
    name: str
    materialization_requires_authority: bool

    async def materialize(self, *, scenario: str | None, config: dict[str, Any]) -> Environment: ...


class Environment(Protocol):
    environment_id: str
    requires_authority: bool

    def capabilities(self) -> tuple[Capability, ...]: ...
    async def observe(self) -> dict[str, Any]: ...
    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]: ...
    async def checkpoint(self) -> dict[str, Any]: ...
    async def restore(self, checkpoint: dict[str, Any]) -> None: ...
    async def teardown(self) -> None: ...
```

These are `Protocol`s, not base classes — you implement them structurally, no
inheritance required. `src/gymact/providers.py::MemoryProvider`/`MemoryEnvironment`
is the reference implementation; read it before writing your own, it is the
smallest real example of every method above.

Every existing provider in `src/gymact/gyms/` (12 of them as of this writing —
`browsergym`, `cube_counter`, `kubernetes_reconciliation`, `terraform_plan`,
`vendor_benchmarks`, etc.) is a real, independent implementation of this same
protocol. If your system's environment resembles one of them structurally
(episodic step-loop, one-shot task+verify, persistent tool session, or
desired-state reconciliation — see `src/gymact/ontology/profile.ttl`'s
`urn:gymact:scheme:interaction` concepts), read the closest match first.

`Capability.consequence` (`Consequence.READ` or `Consequence.DO`) on each
capability you return from `capabilities()` is not decorative — GymAct's runtime
refuses a `DO` capability whose episode requires authority and has none admitted
(see step 3). Do not mark a capability `READ` to route around that check; per
`CLAUDE.md`'s consequence law, that is exactly the collapse
(`request accepted != world changed != objective verified`) this repo exists to
prevent.

## 2. Register your provider

GymAct discovers providers via the `gymact.providers` entry-point group
(`src/gymact/plugins.py`, `PROVIDER_ENTRYPOINT_GROUP`). In your own
`pyproject.toml`:

```toml
[project.entry-points."gymact.providers"]
your-provider-name = "your_package.module:YourProviderClass"
```

Discovery is metadata-only and never ambient — `discover_provider_plugins()`
lists installed entry points without importing anything; `load_provider_plugin(name)`
explicitly loads and validates one named plugin against the real `Environment`
protocol, returning a typed `Standing` (never silently degrading a load failure
into a working provider). A caller (yours, or GymAct's own CLI/surfaces) must name
the plugin it wants — nothing auto-loads every installed provider.

At runtime, either path works:

```python
from gymact import GymAct
from your_package.module import YourProviderClass

runtime = GymAct()
runtime.register_provider(YourProviderClass())   # direct registration
# or, via the entry-point mechanism above:
# from gymact.plugins import load_provider_plugin
# loaded = load_provider_plugin("your-provider-name")
```

## 3. Authority — inject your own resolver, never bypass it

`src/gymact/authority.py` defines the `AuthorityResolver` protocol
(`async def authorize(request: AuthorityRequest) -> AuthorityDecision`). GymAct's
default, `DenyAuthorityResolver`, is fail-closed: every `DO` operation is
refused unless a resolver explicitly admits it. `AllowListAuthorityResolver` is a
deterministic bounded resolver for tests/demos only — it is not a production
policy decision point (its own docstring says so).

For a real integration, write your own resolver against your system's actual
authority mechanism (e.g. autofde-lab's `request_authority`/broker concept, once
it exists as more than a request-only stub — see that repo's own
`docs/autofde/PRODUCT.md`) and inject it:

```python
runtime = GymAct(authority_resolver=YourAuthorityResolver())
```

An `authority_ref` string on an `ActuationIntent` is never itself permission —
your resolver's `authorize()` call is the only thing that can turn a `DO` request
into an admitted one. Do not write a resolver that admits everything; that
recreates ambient authority under a different name.

## 4. Optional: declare your capabilities as real ontology facts

If you want a typed Rust operation catalog, an MCP tool schema, or a generated
reference doc for your provider's capability surface (the same kind of artifact
`ggen/gymact-bridge-pack/` produces for GymAct's own 4 built-in operations), copy
`ggen/consumer-bridge-pack-template/` into your own repo and follow its README.
It declares zero new RDF vocabulary — only `sosa:Procedure` instances validated
against GymAct's real `urn:gymact:shape:capability` SHACL shape, fetched via:

```bash
gymact export-profile <directory>
```

which exports `profile.ttl`/`profile.shacl.ttl` with per-file SHA-256 digests, so
your copy is mechanically checkable against drift rather than trusted blindly.
This step is optional — a pure-Python provider with no ontology file at all is a
complete, valid GymAct integration.

## 5. Prove it — OCEL standing, not pytest

Per `.claude/rules/ocel-standing.md`: your own unit tests passing (that your
`EnvironmentProvider`'s Python API behaves correctly given its inputs) is not
evidence that a real end-to-end episode was actuated. The only thing that backs
an "this integration works" claim is a real, schema-valid, conformant-replay,
`solved=True` OCEL 2.0 log from an actual materialize→act→verify→teardown run
against your provider.

`src/gymact/ocel.py::write_ocel_log` / `receipts_to_ocel` produce this from a
real episode's receipts; `scripts/ocel_standing.py` and
`tests/test_ocel_standing.py` are the canonical pattern for deriving and
asserting standing from the resulting log directly (real `jsonschema` validation,
real `gymact.process.ConformanceChecker` replay, real `act` event attributes) —
never from a hardcoded expected value or from trusting a summarizing script's own
packaged verdict.

## Verification checklist

- [ ] `EnvironmentProvider`/`Environment` implemented, checked against
      `MemoryProvider` as the reference shape
- [ ] every capability correctly classified `READ` or `DO`
      (`gymact.models.Consequence`)
- [ ] registered under `gymact.providers` in your `pyproject.toml`
- [ ] a real `AuthorityResolver` injected (not `AllowListAuthorityResolver`, not
      left as the fail-closed default, for anything beyond local testing)
- [ ] (optional) `ontology.ttl` declares only real, implemented capabilities as
      `sosa:Procedure` facts, validated against a freshly `export-profile`-fetched
      SHACL shape — no hand-invented vocabulary
- [ ] a real OCEL 2.0 log exists from an actual episode against your provider,
      and `tests/test_ocel_standing.py`-style direct assertions pass against it —
      not merely your own provider's unit tests

## See also

- `../../ggen/consumer-bridge-pack-template/README.md` — the optional ggen
  projection pack
- `../../.claude/rules/ocel-standing.md` — why pytest alone never proves a gym
  works
- `../../.claude/rules/actuation-authority.md` — the authority invariant every
  `DO` capability must satisfy
- `../../.claude/rules/ontology.md` — why capability facts reuse public
  vocabulary instead of inventing new RDF classes
- `../../src/gymact/providers.py` — `MemoryProvider`, the reference
  implementation
- `../../src/gymact/gyms/` — 12 real, independent provider implementations to
  read for structural precedent
