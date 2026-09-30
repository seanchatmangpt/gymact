# FDE factory simulation, read through ERRC

**Status: SIMULATION only (`origin=SIMULATED`, `observed_execution=false`, `llm_calls=0`, `human_interactions=0`). No ALIVE, PARTIAL_ALIVE or release standing is claimed.** What was executed: `scripts/run_fde_factory_sim.py` and `tests/test_fde_factory_sim.py` were run against `src/gymact/fde_factory_sim.py`. What is proposed: nothing is admitted as an ERRC move. Nothing here claims release standing: exact-head CI has not run. The consequence chain stays unmerged: request accepted != world changed != objective verified != benchmark scored. A green pytest run is a claim about "request accepted", not "objective verified".

## Method

ERRC = Eliminate / Reduce / Raise / Create, as in `docs/2026-08-12-chatman-ecosystem-errc-8020-1000x.md` and `docs/2026-09-28-v26.9.28-integration-errc.md`. Each candidate row was put through an adversarial versus-fairness and overclaim review. Every candidate row was refuted or downgraded, so the four move sections below carry negative results, not items.

| Lens | Question | Law it enforces |
|---|---|---|
| Consequence | Does the row keep accepted, changed, verified and scored apart? | `CLAUDE.md` consequence law |
| Semantic | Does it add any GymAct-owned class or property? | `.claude/rules/ontology.md` |
| Standing | Is there a real `reports/ocel/<subject>/episode.ocel.json` behind it? | `.claude/rules/ocel-standing.md` |
| Boundary | Is it production-ready, or lab work? | `.claude/rules/explore-exploit.md` |

## Measured facts (this run)

- `PYTHONPATH=src python scripts/run_fde_factory_sim.py` first line: `origin=SIMULATED observed_execution=False llm_calls=0 human_interactions=0`.
- `report_digest=94335d927472892e54924436fbf7234446232050daa670b062a69d66660df09a` (deterministic, re-run matched).
- Cognition evals / verify evals / lookups: baseline 2038 / 60 / 60; factory 280 / 61 / 60. Ratio about 7.3x on the default seed and 60-engagement stream.
- `redundant_explorations(factory)=0`, `unverified_consequences(factory)=0`. Both are zero by construction, not evidence (see below).
- Per-class factory cost curves: class-01 `[26,0,0,0,13,...]`, class-02 `[52,0,0,0,0,0,40,...]`. These two classes show re-exploration after drift.
- `python -m pytest tests/test_fde_factory_sim.py -q`: 10 passed.
- Reviewer reruns reported in the brief: seeds 1-20 gave a baseline/factory ratio of min 6.34, median 7.35, max 9.30. The ratio depends on stream length: 292 vs 135 at 6 engagements, 508 vs 142 at 12, 1067 vs 227 at 30. Denied-authority factory run: 240 cognition evals, 0 verify, 60 of 60 `REFUSED_AUTHORITY`. The brief's earlier figure of 227 was wrong. All figures in this bullet were re-executed directly against `gymact.fde_factory_sim` on 2026-09-30 (seeds 1-20 with the default drift schedule; the 6/12/30-engagement rows with `drift_events=()`); the median was corrected from 7.38 to 7.35.

## Eliminate

Nothing admitted. The candidate "re-deriving an already-solved case class every engagement" was refuted. The baseline is a strawman with no memory (`NO_COMPOUNDING`), so the 7.3x comes from memory vs no memory. No docs-only arm and no ungated-cache arm exist. The factory still explores on first solve and on drift (8 of 60), so at most this is a reduction. The claim "60 verifies in both arms" was also inaccurate (61 vs 60). *Proposed (not admitted).*

## Reduce

Nothing admitted. The candidate "drift cost bounded, paid once per drifted class" was refuted. The baseline cannot hold a stale recipe, so drift handling is a mitigation of a risk the factory introduces, not a reduction against the comparator. The bound rests on two hand-placed drift events and one seed. *Proposed (not admitted).*

## Raise

Nothing admitted. Three candidates were refuted.

- Exact-identity recipe cache over docs: no docs arm is simulated. The statement "every later engagement costs 0 cognition" is false for drifted classes (13 and 40 evals).
- Re-verification on reuse with lazy drift detection: the `:288`/`:337` citations were `REFUSED_AUTHORITY` branches, not drift records. `IDENTITY_DRIFT` and `VERIFY_DIVERGENCE` records carry `Standing.CANDIDATE`, not `REFUSED`. The verifier shares the hidden truth with the explorer, so "independent" does not hold.
- Fail-closed authority: both arms use the same injected resolver, so the result does not separate the factory from the baseline. Authority is checked after exploration and compilation, so the cache is populated before any authority decision.

*Proposed (not admitted).*

## Create

Nothing admitted. Three candidates were refuted.

- Reproducible, self-labelled comparison artifact: determinism is shown, fidelity is not. The digest covers spec and trace digests, not the provenance fields it was claimed to pin. `llm_calls` and `human_interactions` are constants. The module composes existing `compileout`, authority and `evidence.digest`, so it is closer to REUSE or ADAPT than CREATE under `.claude/rules/composition-admission.md`. Overlap with `src/gymact/retirement.py` was not checked.
- Fail-closed authority boundary through the loop: the denied-mode numbers in the row were wrong (227 vs 240) and "compiles once per class" was false (7 explorations for 6 classes, from an announced drift). `AuthorityResolver` already exists, and the sim drives it by hand rather than through the real `GymAct` kernel.

*Proposed (not admitted).*

## Dropped / not claimed

All 8 candidate rows were dropped. Reasons in short:

- Strawman baseline in every row: no memory, no docs arm, no ungated-cache arm, no stale-runbook arm. The "conventional FDE" side is asserted prose, not simulated.
- Wrong or loose numbers: denied-mode 227 (actual 240); "60 verifies in both arms" (61 vs 60); "0 cognition for every later engagement" (drifted classes pay 13 and 40).
- Move categories decorative: Eliminate/Raise/Create labels where Reduce, Reuse or Adapt fit.
- "Independent verify" overclaimed: `World.evaluate` generates the challenge and renders the verdict from the same hidden truth.
- Mis-cited evidence: `:288`/`:337` are authority refusals, not drift records.
- Provenance fields are not bound by the digest.
- The ratio is stream-length and seed dependent, and the default 60 engagements sit near the favorable end.

## Standing

This is SIMULATED. There is no `reports/ocel/fde-factory-sim/episode.ocel.json`, so by `.claude/rules/ocel-standing.md` the subject is `NOT_RUN` for actuated standing. Pytest passing is a "request accepted" fact. To claim more, it would need:

- a real-source OCEL 2.0 log that passes `gymact.ocel.validate_ocel_log`, replays conformantly via `gymact.process.ConformanceChecker`, and carries a real `act` event with `solved=True`;
- authorized, bounded production use under an injected `AuthorityResolver` with an independent `PostconditionVerifier`;
- exact-head CI for release standing.

Nothing here says anything about real customer outcomes.

## What is missing

From the completeness critic pass:

- No composition of recipes: each class compiles to one recipe, with no cross-class transfer and no recipe chaining.
- `decision_cache` and `cost_ledger` are unused.
- No day-based evidence ladder: standing never rises above `CANDIDATE`, and no time-indexed accumulation of evidence is modelled.
- No realistic comparators: docs-only arm, ungated cache arm, stale-runbook arm, reuse-with-human-smoke-test arm.
- Verifier not informationally independent; `gymact.verification.PostconditionVerifier` and the `GymAct` kernel are not exercised. No receipts, idempotency-key reuse, provider failure, or scoring layer.
- Drift model is a single step per class per schedule. No gradual drift, drift back, or repeated drift. Detection is lazy, with no measure of stale-window exposure.
- Authority is fixed allow-list or deny-all, checked after cognition is spent. No partial or mid-stream revocation.
- Cost unit is an in-memory eval count on a 48-disposition toy world, not time, money or human effort.
- Only the factory's counters are printed per class; the baseline's curves and counters are not.
- `scripts/run_fde_factory_sim.py` raises `BrokenPipeError` when piped to `head` (minor robustness).
- Reuse of `src/gymact/retirement.py` is unverified.

## What this does not claim

- No release standing; exact-head CI has not run. Not run: Python matrix, wheel install, docs build, lock validation, container build.
- No ALIVE or PARTIAL_ALIVE standing for the simulation, and no OCEL log for it.
- No claim that the factory beats real FDE practice, or anything about real Sony or WD outcomes.
- "Merged" is not "on `main`"; this doc is uncommitted prose.
- The four lenses above are one reviewer's framing, plus adversarial reruns by the same harness, not independent reviewers.
- No machine ledger row was added; `src/gymact/schemas/errc-v26.8.7.json` is untouched and every item in it stays `SATISFIED`.
- No source file or test was modified.

Not done: a fair-baseline rerun (docs arm, ungated cache, stale-runbook arm), a real-source OCEL log, and a seed and stream-length sweep committed as evidence.
