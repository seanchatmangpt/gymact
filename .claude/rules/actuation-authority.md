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

## Known gap: provider-level `requires_authority` defaults (2026-08-08)

A repo-wide hardening audit found that `GymAct._authority_decision` (`src/gymact/kernel.py`)
short-circuits to `admitted=True, reason="AUTHORITY_NOT_REQUIRED"` whenever the caller's
`required` flag is `False` — the injected `AuthorityResolver` is never consulted at all in that
path, not merely permissively authorized. `required` is driven by two independently-defaulted
knobs, both currently `False` with no in-code justification at their point of declaration:

- `EnvironmentProvider.materialization_requires_authority` (class attribute) gates `materialize()`.
- `config.get("requires_authority", False)` (instance value, set at materialize time) gates
  `act`/`restore`/`teardown`.

These are decoupled — changing one does not change the other. `cli.py`'s `demo` command hit
exactly this bug (fixed 2026-08-08: its memory environment never set `requires_authority=True`, so
the documented "no `--authority` → REFUSED" behavior was never actually gated) and it is the same
pattern in 8 providers with real external side effects: `kubernetes_reconciliation.py` (real
`kubectl apply`/`delete`), `terraform_docker_apply.py` (real `terraform apply`/`destroy`),
`terraform_plan.py`, `cube_container_counter.py`, `gymnasium_env.py`, `mcp_client_session.py`,
`inspect_evals.py`, `cube_counter.py` — each currently relies on the caller to opt in to authority
gating via config rather than requiring it by default.

This is being tracked as a real, open, named gap — not silently accepted — per
`ocel-standing.md`'s "name the real gap, don't paper over it" discipline. A kernel-level fix (no
default, explicit bool required at every call site) or a per-provider default flip would break
~30 existing tests across those 8 modules that currently omit `requires_authority` from config and
rely on real actuation succeeding; each needs individual review (does the test intend to exercise
the authorized path, and should it now pass `requires_authority: True/False` explicitly?) rather
than a single blanket default change. `MemoryProvider` (`src/gymact/providers.py`) has no real external side effects, but flipping its
default was investigated and deferred too: no single test asserts its current `False` default in
isolation (an earlier draft of this note incorrectly assumed
`test_provider_requires_no_authority_by_default` in `test_bounded_discovery_gyms.py` covered it —
that test is parametrized over `SwitchboardProvider`/`ResourceFlowProvider`/`LockAndKeyProvider`
only), but `MemoryProvider()` with default config is used pervasively across the test suite for
materialize+act flows with no requires_authority key, so the real blast radius is unaudited and a
flip is deferred until that audit is done, same as the 8 side-effecting providers above.
`test_discovered_authority.py` (already passes the flag explicitly both ways) is not part of this
gap.

## See also

- `.claude/rules/ontology.md` — ODRL/EARL/PROV terms this invariant is built from
- `.claude/rules/explore-exploit.md` — this invariant applies identically in lab and prod
- `.claude/rules/ocel-standing.md` — the "name the real gap" discipline this section follows
