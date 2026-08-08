# OCEL Standing: A Gym's "Working" Claim Is Never a pytest Verdict

## The rule

Whether a gym "works" is a claim about a real, independently observed and verified
consequence — not about whether its unit tests pass. A provider's own pytest suite
(`tests/test_<gym>.py`) can legitimately and correctly pass while proving only that the
provider's Python API behaves correctly given its inputs. That is unit-level Chicago-style
testing done right, not a defect — but it says nothing about whether a real end-to-end
episode was actually run and independently verified.

The only thing that may back a "this gym is actuated" claim is a real
`reports/ocel/<subject>/episode.ocel.json` log, re-derived the same way every time:

1. real `jsonschema` validation against the real official OCEL 2.0 schema
   (`gymact.ocel.validate_ocel_log`);
2. real replay of the extracted operation sequence, in real recorded event time order, via
   `gymact.process.ConformanceChecker`;
3. real `solved=True` evidence read directly off a real `act` event's own attributes.

A subject with no OCEL log for it is `NOT_RUN`, not "probably fine." A subject whose log is
schema-invalid, nonconformant, or has no `act` event carrying real `solved=True` evidence is
a real, specific, unresolved gap — name it, don't paper over it.

**Why:** pytest and OCEL standing are two disconnected proof systems here. One checks "did
the provider's Python API behave correctly given these inputs"; the other checks "did a real
end-to-end episode, replayed from its own emitted event log, produce a verified outcome."
Reporting the first as evidence of the second is exactly the collapse this repo's own
consequence law forbids: `request accepted != world changed != objective verified != benchmark
scored`. A green pytest run is a fact about `request accepted`; only a conformant, `solved=True`
OCEL replay is evidence of `objective verified`.

## Verification requirement, precisely

Assert on the real derived state directly — do not compare a hardcoded expected string
(e.g. `"GYMACT_ACTUATED"`) against a helper's own packaged verdict, and do not trust
`scripts/ocel_standing.py`'s output as an unquestioned oracle from inside a test. That would
just relocate the same "trust the actuator's own success report" mistake one level up, from
a provider to a summarizing script. `tests/test_ocel_standing.py` is the canonical pattern:
load the real log, call `validate_ocel_log` and `ConformanceChecker().check(...)` directly,
and assert on their real return values and the real `act` event attributes.

`scripts/ocel_standing.py` remains useful as a human-facing batch report (`python
scripts/ocel_standing.py reports/ocel`) — it is not banned, it is just not a substitute for a
direct-state test assertion.

## A red test naming a real gap is preferable to a silent one

When `tests/test_ocel_standing.py` fails for a subject, that failure is correct and should
not be "fixed" by loosening the assertion, adding a hardcoded exception, or deleting the
parametrized case. Fix it by closing the real gap (install the missing dependency, make the
plan actually verify, resolve the nonconformant replay) or, if the gap is expected to persist
for a stated reason, mark it explicitly (e.g. `pytest.mark.xfail(reason="...", strict=True)`)
rather than leaving it silently red or silently deleted.

## See also

- `.claude/rules/actuation-authority.md` — the same accepted != effect != verified law, at
  the actuation-authority layer this rule applies to standing claims
- `~/.claude/rules/testing-chicago-style.md` — the general Chicago-style discipline this rule
  extends to a second, stricter proof layer above ordinary unit tests
- `tests/test_ocel_standing.py` — the canonical implementation of this rule
