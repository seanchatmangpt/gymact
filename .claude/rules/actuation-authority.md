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

## See also

- `.claude/rules/ontology.md` — ODRL/EARL/PROV terms this invariant is built from
- `.claude/rules/explore-exploit.md` — this invariant applies identically in lab and prod
