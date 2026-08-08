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

## See also

- `.claude/rules/ontology.md` — ODRL/EARL/PROV terms this invariant is built from
- `.claude/rules/explore-exploit.md` — this invariant applies identically in lab and prod
- `.claude/rules/ocel-standing.md` — the "name the real gap" discipline this section follows
