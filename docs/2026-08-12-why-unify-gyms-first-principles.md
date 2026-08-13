# Why unify gyms at all? — first principles, before GymAct is assumed as the answer

**Status: paper only. Nothing here is implemented, decided, or committed.**
Companion to `2026-08-12-gymact-certification-and-ggen-from-sregym.md`, which
assumed GymAct as the unification point and asked what certification should
mean given that. This document steps back one level further and interrogates
the assumption itself: why unify gyms behind one interface at all, and if so,
why *this* interface, at *this* layer, in *this* package? Grounded throughout
in real, cited code and real observations from this session — not abstract
architecture debate.

## What a "gym" actually is

Strip the name of its OpenAI-Gym heritage and it's a specific shape: a
**resettable, observable, actionable interaction surface**, bounded enough
that an agent can be evaluated or trained against it repeatably. Classic RL
gyms: `reset()`/`step()`/`reward()`, over a *simulation* — consequences are
free to discard.

GymAct's real generalization (`src/gymact/providers.py`): `materialize()` /
`observe()` / `actuate()` / `verify()` / `checkpoint()` / `restore()` /
`teardown()` — same shape, but now some real instances of it are **not
simulations**. `SregymEnvironment` mutates a real Kubernetes cluster.
`TerraformDockerApplyProvider` presumably applies real infrastructure state.
Consequences are no longer free to discard. That is the actual thing being
generalized here: the RL-gym interaction shape, fused with real-world
actuation semantics (authority, idempotency, evidence) that a pure
simulation never needed. Naming this precisely matters, because the case
*for* unification and the case *against* it both hinge on whether that fusion
was the right one to make in one shared package.

## The strongest real argument for unifying at all

Not hypothetical — read directly this session:
`gymact/src/gymact/gyms/sregym.py`'s docstring and the vendored
`kubectl_mcp_tools.py` it wraps. SREGym's own, native MCP surface
(`exec_kubectl_cmd_safely`) has **zero notion of authority, idempotency, or
evidence**. It is a bare tool: given a command string, it runs it. If GymAct
did not exist, every consumer wanting to actuate SREGym safely would have to
build authority-gating, idempotency-conflict detection, and a tamper-evident
evidence chain *themselves*, on top of that bare tool — or, more realistically
(this is the load-bearing empirical claim), most consumers would not build
it at all, and every real actuation against SREGym across the whole ecosystem
would be exactly as unsafe as its raw MCP surface is today.

This is the real value proposition, stated precisely: **GymAct does not
unify "how do I call a tool" — MCP already does that, natively, per-gym, for
free.** GymAct unifies a *cross-cutting safety and evidence concern* that no
individual gym's own interface provides, and that would otherwise be
reimplemented per-gym, inconsistently, or not at all. `docs/assurance.md`'s
real consequence pipeline (semantic profile → materialization intent →
provider admission + SHACL validation → authority decision → bounded
actuation → independent post-observation → BLAKE3 evidence chain →
independent verification) is genuinely hard, genuinely general, and
genuinely absent from every individual gym's own native surface, confirmed
by reading one of them directly.

## The real costs of unification, also not hypothetical

Three real, observed costs from this session, not speculation:

**1. Impedance mismatch is already showing at 21 real providers.**
`requires_authority` genuinely varies (`sregym` defaults `True`; several
others default `False`; `multicloud` is internally inconsistent between its
`Environment` and `Provider` classes — found directly, not inferred). A
generic `Environment` Protocol necessarily discards whatever doesn't fit —
every provider's `config: dict[str, Any]` escape hatch at `materialize()` is
itself evidence the interface stopped trying to genericize everything, and
started tunneling gym-specific concerns through an untyped bag. This is a
real, structural cost that grows, not shrinks, as the catalog grows.

**2. The import graph is monolithic by construction.**
`gymact/__init__.py` eagerly imports ~40+ names spanning the *entire*
package — `runtime`, `crown_runtime`, `replay`, `physical`, `combinatorial`,
`brce`, all of it — on `import gymact.anything`. A consumer wanting only
`gymact.gyms.sregym` pays the dependency and import-time cost of the whole
package. Worse (found directly, previously in this same investigation):
**this makes independent verification of any part of GymAct structurally
impossible from inside GymAct itself** — no submodule can prove GymAct
wasn't importable in its own process, because it necessarily was. This is a
direct, structural cost of choosing "one Python package" as the unification
mechanism, not an incidental implementation detail.

**3. Single point of trust, single point of coupling.**
One shared package means a bug in the shared idempotency-key logic affects
`sregym` *and* `multicloud` *and* `terraform_docker_apply` simultaneously.
Every consumer (autofde-lab, and whoever else) is pinned to gymact's release
cadence — and, checked directly, that pin today is a **local editable path
dependency, not even a git tag** (`{ path = "/Users/sac/gymact", editable =
true }` in autofde-lab's `pyproject.toml`). Fragmentation (each gym hosting
its own safety logic) would have avoided this specific coupling, at the cost
of duplicated — and probably worse, inconsistent — safety logic per gym.

## Why GymAct specifically, versus the real alternatives

Three alternative unification points, each real and worth taking seriously,
not strawmen:

### Alternative A — unify at the MCP layer only, no shared package

Already exists natively for `sregym` (real kubectl/jaeger/loki/prometheus/
submit MCP routes) and presumably for other gyms. Zero extra engineering.
**Why it's insufficient**: MCP is a wire protocol for tool discovery/
invocation. It says nothing about authority envelopes, idempotency-key
conflicts, or receipt chains — those are exactly the concerns GymAct's real
value proposition (above) is about. Stopping at MCP means every actuation
across the ecosystem is exactly as unsafe as SREGym's raw surface is today.
This is the sharpest real argument *for* GymAct over "just use MCP" — but it
does not, by itself, argue for GymAct being a single monolithic Python
package rather than something narrower.

### Alternative B — a network-level safety/evidence proxy in front of arbitrary MCP servers

Instead of `import gymact.gyms.sregym`, a consumer in any language points an
MCP client at `authority-evidence-proxy://sregym-mcp-server`; the proxy
enforces authority/idempotency/evidence transparently. This would solve
costs #2 and #3 above for free — a network boundary is a far stronger
isolation guarantee than "please don't import this submodule," and
independent verification becomes trivial (a separate client hitting the
proxy over the network is independent by construction, no `sys.modules`
inspection needed). It would also make the safety substrate
language-agnostic, not Python-specific. The real cost: operational — running
and hosting a proxy service is a categorically different commitment than
`pip install`, and every one of GymAct's real, hard-won pieces (attestation,
receipt chains, admission pipeline) would need porting to run at that
boundary. Not dismissed here — genuinely the strongest structural
alternative found, and not evaluated further than this because it would be a
different, larger project, not a refinement of GymAct.

### Alternative C — unify around a published CONTRACT, not a canonical implementation

This is not hypothetical either — **GymAct already has the seed of this**,
unused for gym-provider certification. `src/gymact/contract.py`'s
`RuntimeContract` (docstring: *"Stable contract consumable by ggen, Rust/WIT/
WASM or independent checkers"*) is a real, `BaseModel`-typed, self-digested
object: `gymact_version`, `profile_uri`, `canonicalization` (`"RFC8785-JCS"`),
`digest_algorithm` (`"blake3-256"`), `operations`, `surfaces`,
`public_semantics`, `schemas`, and `contract_digest`, with a real
`verify_digest()` method that **recomputes the digest from the payload
itself** — the exact same "don't trust the stored value" discipline this
whole investigation kept re-deriving independently.

The reframe this enables: producing `RuntimeContract` requires importing
GymAct (naturally — someone has to introspect the real types to build it).
But **verifying conformance against an already-exported `RuntimeContract`
JSON does not** — the contract, once serialized, is data, and
`verify_digest()`-style comparison needs nothing but that JSON. This is
structurally the same shape this document's companion piece proposed for
per-gym certification (a persisted, independently-re-digestible manifest) —
except GymAct already ships the primitive at the *whole-runtime* level, one
layer up from any single provider. Under this framing, "certifying a gym
provider" stops meaning "does this Python object pass my checks" and starts
meaning "does this implementation (in any language, any process) conform to
the *published contract*" — coherent to verify independently, because the
contract is a versioned, digested artifact, not a piece of code you must
import to compare against.

**This was not evaluated for correctness or completeness this session** —
whether `RuntimeContract`'s current fields are sufficient to certify a real
gym provider's behavior (versus GymAct's own Python/DCM/Crown internals,
which is what it currently seems scoped to) is an open, unverified question,
named here rather than assumed.

## What the real evidence actually suggests

Not a recommendation to rebuild anything — a sharpened set of honest
positions, each tied to what was actually found:

- The case *for* unifying the safety substrate (authority/idempotency/
  evidence) is real and strong. SREGym's own bare MCP surface is direct
  evidence of the gap; nothing in this investigation undermines that case.
- The case *against* unifying it inside **one canonical Python package**
  specifically is also real: impedance mismatch already visible at 21
  providers, a monolithic import graph with a structural
  independent-verification cost, and single-package trust/coupling.
- Of the two live alternatives that keep the safety-substrate value without
  those costs, **Alternative C (contract-based conformance) is cheaper to
  reach from here than Alternative B (a network proxy)** — GymAct already
  ships a real, digested, "independent checkers" — labeled primitive
  (`RuntimeContract`) that Alternative B would have to build from nothing.
  Alternative B is the more radical, more general fix (language-agnostic,
  stronger isolation) but a materially larger undertaking.
- None of this argues GymAct-as-a-package was the wrong call to date — the
  safety substrate had to be *built* somewhere first, and building it inside
  one real, working Python package before generalizing the unification
  *point* is a defensible, ordinary sequencing. The open question this
  document leaves is only about what comes *next*, not a retroactive
  indictment of what exists.

## What we still don't know

Same discipline as the companion document: this is one investigation's real
findings, not a settled architecture.

- Is `RuntimeContract` actually rich enough, today, to certify a *gym
  provider's* real behavior (SREGym's `requires_authority`, its five MCP
  routes) — or is it currently scoped only to GymAct's own internal
  Python/DCM/Crown surfaces? Unchecked this session.
- Would a network-proxy model (Alternative B) actually get adopted by real
  consumers, or does the operational cost kill it regardless of its
  structural elegance? No real consumer demand was surveyed.
- Is the impedance-mismatch cost (#1 above) actually a problem in practice,
  or a reasonable price for the amortized-engineering benefit? This
  document names the tension; it does not resolve it.

## See also

- `2026-08-12-gymact-certification-and-ggen-from-sregym.md` — the narrower,
  "given GymAct as the unification point, what should certification mean"
  companion this document generalizes past.
- `docs/assurance.md` — the real, implemented consequence pipeline this
  whole unification argument is actually about.
- `src/gymact/contract.py` — `RuntimeContract`/`build_contract()`, the real,
  underused primitive Alternative C is built on.
- `docs/gymact-thesis.md` §4.4 — the self-certification doctrine both
  documents keep independently re-deriving from different angles.
