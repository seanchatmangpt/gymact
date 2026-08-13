# GymAct OCEL analysis — Part 2: implementation plan, based on validated results

**Status: mostly paper, one real check actually executed this session (see
§3).** Part 2 of the series started with
`2026-08-12-chatman-ecosystem-errc-8020-1000x.md` (Part 1). Where Part 1's
headline "Create" finding rested on a secondhand doctrine claim, this
document corrects it against real, directly-checked evidence, then plans —
and partially executes — the corrected path.

## 1. Correction notice, stated up front

Part 1 proposed wiring gymact's real OCEL 2.0 export into "wasm4pm's
process-mining analysis engine," based on gymact/ggen's own `CLAUDE.md`
stating *"wasm4pm-compat and wasm4pm own all analysis: discovery,
conformance, fitness, precision, variants."* This claim was checked directly
against wasm4pm's own source this session. **It does not hold as stated.**
This is the opening finding of Part 2, not a footnote — the whole series'
discipline has been "never let doctrine substitute for a real check," and
that discipline caught a real overstatement in its own prior output.

## 2. What wasm4pm actually offers today, precisely

- `wasm4pm-compat::ocel`'s own module docs are explicit and self-disclaiming:
  *"Not an OCEL engine. It does not discover object-centric Petri nets,
  flatten for conformance, or compute any metric... Structure only.
  Graduate to `wasm4pm` when an OCEL log must be executed."* The compat
  layer explicitly does not do what the doctrine attributed to it.
- `wasm4pm`'s real, native OCEL capability is narrower than the doctrine
  claim: `discover_ocel_dfg_pure` — a genuine, working directly-follows-graph
  discovery algorithm, real and tested — plus
  `validate_ocel_object_lifecycles`, a rule-based conformance checker, not a
  fitness/precision computation against a discovered model.
- **The only real JSON-ingestion entrypoint (`load_ocel2_from_json`) is
  `#[wasm_bindgen]`, gated behind the `ocel` Cargo feature — reachable only
  from a WASM/JS host, not from Python or a Rust CLI.**
- **The one real, human-invokable CLI path (`wpm audit`) actively refuses
  OCEL input**, printing "The wpm audit command currently supports XES
  event logs (IEEE 1849)... flatten it first," and naming a `wpm
  conformance` TypeScript command that could not be confirmed as an actually
  registered, working command (only found in shell-completion help-text
  assertions).
- **No fitness/precision/generalization/simplicity — van der Aalst's real
  quality quartet — and no variants analysis exist anywhere in wasm4pm's own
  native code.** The complete named set exists only in a vendored,
  third-party `pm4py` copy sitting inert inside the wasm4pm repo
  (`~/wasm4pm/vendors/pm4py/`) — real, mature, but not wasm4pm's own work
  and not integrated into anything.

## 3. The corrected path: `pm4py`, directly — validated, not just proposed

`pm4py` does not need to be reached through wasm4pm's vendored copy or its
WASM boundary at all. It is an independently real, mature, pip-installable
Python library (version `2.7.22.1` confirmed already present in this
session's environment) with native OCEL 2.0 support and real
discovery/conformance implementations, including
`pm4py.discover_oc_petri_net` — object-centric Petri net discovery, citing
its real source directly in the function's own docstring: *"van der Aalst,
Wil MP, and Alessandro Berti. 'Discovering object-centric Petri nets.'
Fundamenta Informaticae 175.1-4 (2020)."* This is not an approximation of
his method reached through an intermediary — it is a real implementation of
a real paper he co-authored.

**This was actually run this session, not just proposed**, against
`~/gymact/tests/fixtures/real_episode.ocel.json` — a real, already-existing
gymact fixture (one of ten real `.ocel.json` files found on disk under
`~/gymact/{tests/fixtures,reports/ocel/*}`):

```python
import pm4py
ocel = pm4py.read_ocel2_json('tests/fixtures/real_episode.ocel.json')
# object types: ['episode', 'environment', 'capability'] -- gymact's real shape, preserved correctly
result = pm4py.discover_oc_petri_net(ocel, diagnostics_with_tbr=True)
```

Real results:
- **Parsed cleanly**, no adapter code needed — `pm4py.read_ocel2_json`
  consumed gymact's `receipts_to_ocel()` output as-is, correctly recovering
  its real object types (`episode`, `environment`, `capability`) and five
  real events (`materialize`, `act`, `act`, `verify`, `teardown`).
- **Real object-centric Petri nets were discovered**, one per object type
  (`episode`: 5 places/5 transitions/10 arcs; `environment`: same shape;
  `capability`: 4 places/5 transitions/10 arcs).
- **Real token-based replay diagnostics came back** (`tbr_results`): for
  every place, in every object type's discovered net, `missing=0` and
  `remaining=0` — a perfect replay, computed by pm4py's own real algorithm,
  not asserted by this document.

**Honest caveat, stated precisely rather than oversold**: this is discovery
run on a single real episode, then replay of that *same* episode against the
*just-discovered* model — a perfect-fitness result here is expected and
close to vacuous (the model was built to fit exactly this trace), not
evidence of generalization to unseen episodes. It is real, positive proof of
two narrower, still-valuable things: (a) the real pipeline — gymact's real
OCEL export → `pm4py`'s real parser → `pm4py`'s real discovery →
`pm4py`'s real token-based replay — runs end to end without any adapter
code, and (b) `pm4py`'s object-centric algorithms handle gymact's specific
three-object-type shape correctly. Real, corpus-wide fitness (many episodes,
model discovered from some, replayed against held-out others) was not
computed and would need real multi-episode data this session's real trial
volume does not yet provide (per Part 1's own honest accounting: ~0-1
completed real trials of the adjacent SREGym system).

## 4. Implementation plan, phased

**Phase 0 — verification-only: COMPLETE, this session, real.** Confirmed
`pm4py` ingests gymact's real OCEL export as-is and runs real discovery +
token-based replay against it, no adapter code needed. This is stronger
evidence than the original plan's minimal "does it parse" bar required.

**Phase 1 — a thin, external, gymact-independent analysis module (not yet
built).** Matching the independent-verification discipline the
certification and process-mining companion papers already established: a
small script/module living *outside* gymact's own package (importing
gymact's OCEL JSON output as data, never gymact's runtime — the same
"producer must not be the checker" boundary `standalone_verifier.py`
enforces elsewhere in this ecosystem), that runs `pm4py`'s real discovery +
conformance against a real, growing corpus of persisted gymact OCEL logs
(the ten real `.ocel.json` files already on disk are a real starting
corpus) and reports real, aggregate fitness/precision numbers — not
single-episode, self-fitting ones like §3's proof-of-pipeline run.

**Phase 2 — deferred, not committed to now.** Whether to formalize Phase 1
into a recurring pipeline (e.g. a CI job re-running analysis on every new
episode) depends on whether Phase 1's real numbers, over a real
multi-episode corpus, turn out to be useful — matching every prior paper's
"don't build ahead of a proven need" discipline. Not decided here.

**Named alternative, not recommended first but not dismissed**: build a
real Python↔WASM bridge to wasm4pm's `load_ocel2_from_json`/
`discover_ocel_dfg_pure`, or add native fitness/precision computation to
wasm4pm's own Rust OCEL code. This would keep the capability inside the
ecosystem's own stack rather than depending on an external pip package, at
real, larger engineering cost (a working WASM/JS↔Python bridge, or new Rust
algorithm work) for capability §3 already demonstrates `pm4py` provides
today, directly, for real.

## 5. What we still don't know

- Whether real, multi-episode, held-out fitness/precision numbers (not
  §3's single-episode, self-fitting proof-of-pipeline) would actually be
  meaningful at gymact's current real trial volume — genuinely open, and
  the same caution Part 1 and this session's earlier memory-learning
  investigation both already named independently.
- Whether Phase 1's external analysis module should live in gymact's own
  repo (as a clearly-separated, non-runtime-importing sibling directory) or
  in a wholly separate repo — not decided; the independence requirement is
  named, the exact location is not.
- Whether `pm4py`'s object-centric Petri net discovery is the right
  algorithm choice for gymact's specific, small-vocabulary, eight-operation
  lifecycle, versus a simpler directly-follows-graph view — §3 used the
  richer method because it was the one whose docstring directly cited van
  der Aalst; a real comparison of both was not run this session.

## See also

- `2026-08-12-chatman-ecosystem-errc-8020-1000x.md` — Part 1; this document
  corrects its headline finding rather than silently revising it.
- `2026-08-12-gymact-process-mining-reading-van-der-aalst.md` — the
  original process-mining paper whose §5 stopped short of proposing a
  scored checker for want of a known consumer; §3 above is real, executed
  evidence that a real consumer (`pm4py`, used directly) exists and works
  against gymact's actual OCEL output today.
- `2026-08-12-gymact-certification-and-ggen-from-sregym.md` — source of the
  "producer must not be the checker" independence discipline Phase 1 above
  is designed to respect.
- `~/gymact/tests/fixtures/real_episode.ocel.json` — the real fixture §3's
  check ran against.
