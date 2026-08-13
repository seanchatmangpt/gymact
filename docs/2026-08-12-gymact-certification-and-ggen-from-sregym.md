# What "GymAct Certified" and ggen's role in it should be — a SREGym-eyed proposal

**Status: paper only. Nothing in this document is implemented. No code, ontology, or
schema described here exists yet.** It is a design proposal, written from one
concrete vantage point (driving real SREGym trials through GymAct) because a
concrete vantage point disciplines a design better than an abstract one — but
it is explicitly *not* a commitment to what any future consumer will actually
want. See "What we don't know" at the end before building anything from this.

## Why SREGym as the lens, and not a generic one

A certification concept designed in the abstract tends to certify what's easy
to check, not what a real consumer actually needed to know before trusting a
provider. This document instead asks: given everything actually observed
while driving real SREGym trials through GymAct, what would "GymAct
Certified" have needed to mean to be *useful*, not just *true*?

Concrete, real observations from that vantage point:

- `SregymEnvironment` is one of GymAct's heaviest real providers:
  `requires_authority=True` by default (unlike most others), a persistent
  multi-step session (not one-shot subprocess), a real MCP/HTTP surface
  across five real routes, and real, gym-specific capability payloads
  (`run_kubectl`'s command string, `submit_diagnosis`/`submit_mitigation`'s
  free-text solution). None of that is generic — every one of those facts is
  something a *consumer* of `gymact.gyms.sregym` needs to know before
  actuating anything for real, and none of it is expressible as "this object
  satisfies `EnvironmentProvider`."
- The actual failures hit while driving real trials this session were never
  "the provider doesn't satisfy the Protocol" — they were environment-shape
  failures one layer down: a stale/wrongly-shaped cluster, a flaky external
  image pull, a real-but-undocumented `tool_choice` incompatibility between
  the LM backend and the tool-calling loop. A certification scoped only to
  Protocol conformance would have said nothing useful about any of them.
- `requires_authority` genuinely varies by provider (sregym defaults `True`;
  several others default `False`; multicloud is internally inconsistent
  between its `Environment` and `Provider` classes). A consumer choosing
  whether to actuate a gym for real needs this fact surfaced, not buried in
  source.

So: SREGym is not a special case to generalize away. It's evidence that a
useful certification concept has to say something about *behavioral,
provider-specific facts* that matter to a real actuator deciding whether to
trust a gym — not just "this class has the right methods."

## The real, hard problem: independent verification is structurally impossible from inside GymAct

This is the single most important finding of this exploration, and it wasn't
obvious until checked directly: **`gymact/__init__.py` eagerly imports nearly
the entire package** (`runtime`, `providers`, `authority`, `evidence`,
`crown_runtime`, `replay`, ~40 more names). Importing *any* submodule of
`gymact` — including a hypothetical `gymact.certification` — triggers that
same `__init__.py`.

Why this matters: `~/autofde-lab`'s own `standalone_verifier.py` establishes
the real bar for "independent" in this ecosystem — it refuses to run if the
producing runtime is even *importable* in its process
(`FORBIDDEN_RUNTIME_MODULES`, checked against `sys.modules`, not merely
intended). That bar is achievable from *outside* GymAct (a separate consumer
package can simply choose not to import `gymact`). It is **not** achievable
from *inside* GymAct — any module living in this package cannot prove GymAct
wasn't importable in its own process, because it necessarily was.

This is not a workaround-able implementation detail; it is why
"self-certification" is named as an anti-pattern in this repo's own thesis
(§4.4) in the first place. **A certification mechanism that lives inside
GymAct cannot be the independent verifier — structurally, not by discipline.**
Two honest options follow from this, not one:

1. GymAct exposes the real, checkable facts (contract digest, capability
   schemas, per-provider `requires_authority`/behavioral metadata, a
   `build_contract()`-style self-digest — several of these already exist per
   `docs/assurance.md`'s "Cross-runtime contract" section) — and certification
   itself is computed and owned by a consumer, outside this package. This is
   what autofde-lab's existing `gymact_certification_checker.py` already is,
   correctly scoped.
2. GymAct's *own* test suite (`tests/test_two_gym_gate.py`,
   `test_bounded_discovery_gyms.py`, `test_registry_completeness_chicago.py`,
   and siblings — all real, already exist) is internal QA, not certification.
   It should stay named as exactly that: real, valuable, generic
   provider-conformance testing, never described as "certifying" anything to
   an external consumer, because it cannot independently verify itself.

## What ggen's real role could be — schema and profile, not verdict

ggen should never compute a certification verdict — that would just relocate
the self-certification problem into a code-generation step instead of a
runtime one. Its real, useful role is upstream of verification: **defining,
per real gym, what a certification profile even needs to check.**

Concrete shape, modeled on two real precedents found elsewhere in this
org's stack (not invented here):

- **`~/ggen`'s own `gates/*.rq` pattern** (SHACL shapes hand-translated to
  SPARQL, executed against ground-truth RDF, proven actually-executed via a
  real test rather than left as an unproven doctrine claim) — the right
  shape for *encoding* what a gym-specific certification profile checks: not
  a Python function per gym, but a declarative, per-gym set of law-queries
  (`sregym/010_requires_authority_matches_declared.rq`,
  `sregym/020_five_mcp_routes_present.rq`, ...) that a generic runner
  executes against real, observed facts about a materialized provider —
  the SREGym-specific facts named above, not just Protocol shape.
- **`ggen-architecture::certification`'s real data model**
  (`CertificationAward`/`RequirementReceipt`, with
  `positive_witness_digest`/`negative_falsifier_digest`/
  `independent_verifier_digest`/`replay_digest` fields) — the right shape for
  the *manifest schema itself*: a certification claim that structurally
  carries not just "it passed" but *whose* verification produced it and what
  would have falsified it, matching this ecosystem's own repeated "no
  self-certification" doctrine as a schema-level property, not just a
  process-level one.

Concretely, ggen's job would be: given a gym's real capability
catalog + a hand-authored `ontology/<gym>-certification-profile.ttl`
(per-gym required facts — SREGym's `requires_authority=True`, its five real
MCP routes, its `submit_diagnosis`/`submit_mitigation` free-text-solution
shape), generate (a) the SPARQL law-queries a runner executes, and (b) the
typed manifest schema those queries populate. ggen manufactures the *shape*
of the check and the *shape* of the receipt. It never runs the check itself,
and it never lives inside GymAct's own package boundary for the same
independence reason above — the generated verifier is a consumer artifact,
not a GymAct-internal one.

## Sketch of the resulting shape (illustrative, not a commitment)

```text
gym source (gymact.gyms.sregym)
        |
        v  (real, already exists: build_contract()-style self-digest)
GymAct's own real, checkable facts
        |
        v  (NEW, proposed: a per-gym certification profile, hand-authored RDF)
ontology/sregym-certification-profile.ttl
   - requires_authority: true (declared, matches real default)
   - required_mcp_routes: [kubectl, jaeger, loki, prometheus, submit]
   - capability_catalog: [observe_cluster_state, run_kubectl, submit_diagnosis, submit_mitigation, verify]
        |
        v  (ggen: manufacture, not verify)
generated SPARQL law-queries + generated CertificationManifest schema
        |
        v  (a SEPARATE consumer package -- not gymact, not the generator -- e.g. autofde-lab today)
real certification run: structural checks + profile-declared behavioral checks
   + a persisted, digested manifest
        |
        v  (a genuinely independent process, per standalone_verifier.py's bar)
re-verification from durable artifact alone, gymact proven absent from sys.modules
```

This is a sketch to make the earlier prose concrete, not a proposed API.

## What we don't know

This document is written from exactly one real vantage point (an SRE-agent
consumer driving diagnosis/mitigation trials). It should not be mistaken for
knowing what other real consumers of GymAct would need:

- Would a consumer running `terraform_docker_apply` or `multicloud` want the
  same profile shape, or does infra-provisioning certification look
  completely different from SRE-diagnosis certification (different risk
  profile, different "what matters before I trust this" questions)?
- Is a per-gym SPARQL profile the right granularity, or is it too fine
  (should certification be per-*capability*, not per-*gym*)?
- Who would actually consume a `CertificationManifest` — a human deciding
  whether to enable a gym in production, a CI gate blocking a merge, an
  automated agent deciding whether to actuate at all? Each implies a
  different real interface (a report, a boolean gate, a runtime check), and
  this document doesn't know which.
- Does this need to exist at all yet, given real trial volume this session
  was ~0-1 completed trials? A certification scheme with no real corpus of
  provider failures to have caught is a hypothesis, not a proven need.

None of these are answered here on purpose. The honest next step is not to
build this — it's to find a second real consumer with a real, different need
and see how much of this sketch survives contact with it.

## See also

- `2026-08-12-why-unify-gyms-first-principles.md` — the more foundational
  companion this document assumes the answer to: *why unify gyms behind
  GymAct at all*, and whether the unification point should be a Python
  package, a network proxy, or a published contract. Read that one first if
  the premise "GymAct is the right unification point" itself is in question.
- `2026-08-12-gymact-process-mining-reading-van-der-aalst.md` — extends this
  document's central self-certification finding through a different, more
  precise lens (Wil van der Aalst's process mining): the `__init__.py`
  import-graph argument here and the "log/model must be independently
  produced" argument there land on the same structural requirement from two
  separate directions.
- `~/gymact/docs/assurance.md` — the real, already-implemented consequence
  pipeline and evidence chain this proposal builds on top of, never
  duplicates.
- `~/gymact/docs/gymact-thesis.md` §4.4 — "Independent verification, and the
  self-certification bug it replaced," the doctrine this document's central
  finding (certification can't live inside GymAct) is a structural
  consequence of.
- `~/autofde-lab/src/autofde_lab/reasoning/gymact_certification_checker.py` —
  the one real, already-existing, correctly-external implementation of
  option 1 above, as of this session (owned by a concurrent session; not
  modified by this document).
- `~/autofde-lab/src/autofde_lab/hub/domain/gym_procedure/standalone_verifier.py`
  — the real bar for "independent" this whole proposal is built against.
