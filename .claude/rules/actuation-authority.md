# Actuation Authority: Zero Unreceipted Actuation

## The invariant

No consequential operation executes without crossing an explicit authority boundary and
producing evidence sufficient to bind subject, capability, authority, intent, pre-state,
actuation, consequence, post-state, verification, and replay.

This holds regardless of caller: an MCP tool call, a BPMN service task, a generated Rust
function, a CLI invocation, or an LLM-proposed plan. None of these carry ambient authority.
They manufacture an *intent*. Only the executor's authority boundary may turn an intent
into an actuation.

```
Intent  ≠  Action  ≠  Effect  ≠  Verified Effect
```

- Command acceptance is not effect.
- Actuator success response is not verified consequence.
- A generated Terraform/Kubernetes/API call is not authorized merely because it validates.

## In GymAct terms

- `sosa:Actuation` requires an `odrl:Policy` permission reference before it may execute.
- Observation (`sosa:Observation`, read-only) never requires authority.
- A capability's `consequence class` (READ vs DO) determines whether authority is required
  — encode this on the capability, not as an afterthought in the caller.
- Verification (EARL) is independent of the actuator's own success report. Do not treat
  "the tool returned 200" as "the world changed as intended."

## Practical checks when adding a capability

1. Does this capability cause a state change in the target world? If yes → `DO`, requires
   authority + independent postcondition verification.
2. If refused (no authority, stale plan, ambiguous process correlation, forged/incomplete
   observation), the refusal itself must be typed and evidenced — not a silent no-op.
3. Idempotency: duplicate/replayed intents must not cause duplicate consequences.

## Closed gap: `requires_authority` config default for 8 real-side-effect providers (2026-08-08)

A repo-wide hardening audit found that `GymAct._authority_decision` (`src/gymact/kernel.py`)
short-circuits to `admitted=True, reason="AUTHORITY_NOT_REQUIRED"` whenever the caller's
`required` flag is `False` — the injected `AuthorityResolver` is never consulted at all in that
path, not merely permissively authorized. `cli.py`'s `demo` command hit exactly this bug (fixed
2026-08-08: its memory environment never set `requires_authority=True`), and the same pattern was
present in `config.get("requires_authority", False)` across 8 providers with real external side
effects: `kubernetes_reconciliation.py` (real `kubectl apply`/`delete`), `terraform_docker_apply.py`
(real `terraform apply`/`destroy`), `terraform_plan.py`, `cube_container_counter.py`,
`gymnasium_env.py`, `mcp_client_session.py`, `inspect_evals.py`, `cube_counter.py`.

**Fixed**, scoped narrowly: each of the 8 providers' `config.get("requires_authority", False)`
default was flipped to `True`, so `act`/`restore`/`teardown` now require an admitted authority
unless a caller explicitly opts out. Every test in the 8 corresponding test files that previously
relied on the old unauthorized-by-default path was individually reviewed and updated to construct
`GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))` and pass an explicit
`authority_ref=AUTHORITY` on every real `act`/`restore`/`teardown` call — no test's *purpose* was
changed, only its authority admission became explicit and load-bearing, matching this rule's own
invariant. Full suite confirmed deterministic across two consecutive runs after the fix.

**Deliberately NOT changed**, and named as still-out-of-scope rather than silently expanded into:

- `EnvironmentProvider.materialization_requires_authority` (the separate class-attribute knob
  gating `materialize()` itself, decoupled from the config-default knob above) was flipped to
  `True` and then reverted for all 8 providers after real testing showed it breaks `materialize()`
  for a plain `GymAct()` (default `DenyAuthorityResolver`) far more broadly than the demonstrated
  bug class, which was specifically about unauthorized `act()`, not `materialize()`.
- `discovered.py` and `browsergym.py` were flipped, found to break tests, and reverted — neither
  was in the audited 8-provider list; `discovered.py` already has dedicated, explicit
  both-ways authority test coverage (`test_discovered_authority.py`).
- `MemoryProvider` (`src/gymact/providers.py`) was flipped and reverted after it broke ~27 tests
  across core kernel infrastructure (`test_core.py`, `test_sota.py`, `test_stream.py`,
  `test_errc_innovations.py`, `test_evidence_sota.py`, `test_ggen_legacy_gym.py`,
  `test_production_surfaces.py`) — none of which were part of the original named gap; its default
  remains `False`, still an open, unaudited item.

## Closed gap: `GymAct.verify()` trusted a provider's own self-reported verdict (2026-08-10)

`GymAct.verify()` (`src/gymact/kernel.py`) used to call `state.environment.verify(expected)`
and return whatever `(passed, observed)` tuple the provider itself computed as the real
result. The provider — the exact thing being graded — both produced the observation and
rendered the verdict, with only a size/timeout bound as a backstop. Confirmed concretely: a
provider's `verify()` (e.g. `vendor_benchmarks.py`, `sregym.py`) could return `passed=True`
unconditionally regardless of `expected`, and nothing downstream would catch it.

**Fixed**: an injected `gymact.verification.PostconditionVerifier` (mirroring
`AuthorityResolver`'s already-proven externalization) now renders the actual verdict. The
provider's own `verify()` report is still collected — as an audit signal, not discarded — and
if it disagrees with the independent judgment, that divergence is recorded on the resulting
Receipt (`PROVIDER_VERIFY_DIVERGENCE:provider_reported=<bool>`), turning a dishonest provider's
lie into real, positive evidence instead of silently trusting it. `verify()` now also records a
real `Receipt`/OCEL event for the first time — previously no gym's real `verify` operation ever
produced one at all.

## Documented invariant: `observe()` must be an independent read, never an `actuate()` echo

Not a code gap (no current provider violates this), but an explicit contract for every future
`Environment` implementation: `observe()` must genuinely re-query external state through its
own channel (a separate subprocess/API/file read) — never simply return `actuate()`'s own
self-reported effect dict. If `observe()` merely echoes what `actuate()` claimed happened, the
`PostconditionVerifier` fix above still independently judges `expected` against `observed`, but
`observed` itself would be unaudited provider narration, and the whole verification boundary
degrades back to self-certification one level down.

`gymact.gyms.kubernetes_reconciliation.KubernetesReconciliationProvider` is the reference
pattern: `verify()` polls real cluster-observed state (`kubectl get pod -o json`'s
`.status.phase`) independent of `kubectl apply`'s own exit code — read that provider's
docstring/tests when building a new gym. This is a code-review checklist item, not a
mechanically-enforceable check: there is no generic way to prove a provider's `observe()`
re-queries reality rather than replaying cached state, stated honestly as a limit rather than
papered over.

## See also

- `.claude/rules/ontology.md` — ODRL/EARL/PROV terms this invariant is built from
- `.claude/rules/explore-exploit.md` — this invariant applies identically in lab and prod
- `.claude/rules/ocel-standing.md` — the "name the real gap" discipline this section follows
- `src/gymact/verification.py` — the `PostconditionVerifier` module this section documents
