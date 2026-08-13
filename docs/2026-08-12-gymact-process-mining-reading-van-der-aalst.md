# GymAct, read through Wil van der Aalst's process mining — a paper

**Status: paper only. No code, schema, or algorithm proposed here is
implemented.** Third in a series with `2026-08-12-gymact-certification-and-ggen-from-sregym.md`
and `2026-08-12-why-unify-gyms-first-principles.md`, both cross-linked
below. This one applies one specific, real body of published work — Wil
van der Aalst's process mining — to GymAct's actual evidence and
conformance code, precisely, not as a costume.

## On method

This paper applies van der Aalst's published, named methods — discovery,
conformance checking, the fitness/precision/generalization/simplicity
quality dimensions, OCEL 2.0, the independence stance — to GymAct's actual
code. It does not claim to represent his opinions, and it is not a
hagiography. Per-claim hedging ("van der Aalst might say...") is dropped
after this paragraph: every claim below is either (a) a documented fact
about his published work, cited to the specific paper/venue/year, or (b) an
explicitly-labeled *application* of that method to GymAct, argued on its
own merits — never a prediction of what he personally would say. §8 is the
one place personal-reaction framing returns, and it is reframed there as
"apply his own adversarial discipline to this document," not ventriloquism.

## 1. The lens: independence, never self-report

Process mining's entire methodology rests on comparing two independently
produced artifacts: an event log (what actually happened, recorded) and a
process model (a claim about what is allowed to happen) — never one
grading the other. This is structural, not incidental: van der Aalst's own
three-discipline taxonomy (below) only makes sense under that separation —
*discovery* produces a model *from* a log; *conformance checking* then
independently *checks* a model *against* a log, treated as ground truth
external to the model being checked. The paper co-authored under the title
**"In Log and Model We Trust? A Generalized Conformance Checking
Framework"** (2016) makes the same point rhetorically in its title: neither
artifact is owed automatic trust. His 2012 event-log quality guidelines
(cited via the Process Mining Manifesto lineage) name **trustworthiness**,
**completeness**, and **well-defined semantics** as real, separate
prerequisites a log must meet before it may be relied on at all — the log
is not exempt from scrutiny either.

This is the lens the rest of this paper uses, applied to GymAct's own code
and — in §8 — to this paper's own claims.

## 2. A prior finding, extended: self-certification as a log-model identity violation

The companion certification paper found something structural, not stylistic:
`gymact/__init__.py` eagerly imports the entire package, so no module living
inside GymAct can prove GymAct was not importable in its own process — a
verifier inside the package cannot be independent of the thing it verifies,
by construction. Read through §1's lens, this is exactly the failure
conformance checking exists to rule out: a model and the thing checking
conformance against it must be produced by genuinely separate processes, or
the "check" reduces to the model reading its own claims back to itself. The
finding was reached from a different angle (Python import graphs, not
process mining) and lands on the same structural requirement. This section
is a bridge, not a restatement — the rest of this paper is about a
different, more specific gap: even setting the self-certification question
aside entirely, what GymAct's own internal conformance-checking code does
today falls well short of what conformance checking means in van der
Aalst's own technical sense.

## 3. The organizing spine, applied

*Process Mining: Data Science in Action* organizes the field around three
disciplines: **discovery** (construct a model from a log, no prior model
assumed), **conformance checking** (compare an existing model against a
log), and **enhancement** (repair or extend an a-priori model using
information mined from the log). Applying this taxonomy to GymAct's real
modules, precisely:

- **Discovery**: absent. `gymact/process.py`'s `LIFECYCLE` dict (confirmed
  directly, `process.py:26-74`) is a hand-written transition table — eight
  `Operation` values, each mapped to its legal successors by a human
  author, not derived from any log by any discovery algorithm (Alpha,
  Heuristics, Inductive, or otherwise). Nothing in the codebase mines a
  model from observed episodes.
- **Conformance checking**: present in name, narrower in substance — see
  §4.
- **Enhancement**: absent. No mechanism in GymAct feeds real, observed
  deviations back into `LIFECYCLE` to repair or extend it; the table is
  static source, edited by hand if it changes at all.

Van der Aalst's own Alpha algorithm — his original discovery method — had
real, named limitations discovered after publication: it cannot rediscover
short loops (length one or two), it assumes a complete log, and it is too
sensitive to infrequent/noisy behavior to be practical on real logs. These
gaps directly motivated the Heuristics Miner and later the Inductive Miner.
The field he founded treats "supersede your own earlier method once its
real limits are found" as ordinary practice, not an admission of failure.
That is the standard §4 and §6 hold `process.py` and `replay.py` to —
not because either is uniquely bad, but because the field this paper is
reading GymAct through has its own public precedent for exactly this kind
of correction.

## 4. Finding 1 (the spine): a real OCEL 2.0 log with nothing checking against it

`gymact/ocel.py` (confirmed directly, full file) is a genuine, working OCEL
2.0 exporter — not a stub, not an aspiration. `receipts_to_ocel()` builds
real object types (`episode`, `environment` from `subject_ref`,
`capability` from `capability_ref`) with **qualified relationships**
(`{"objectId": ..., "qualifier": "episode"|"environment"|"capability"}`,
`ocel.py:75-79`) — the exact relationship-qualifier structure OCEL 2.0
requires. `validate_ocel_log()` checks the output against the real,
vendored *official* OCEL 2.0 JSON Schema, fetched from
`ocel-standard.org` (`ocel.py:9-11, 122-133`) — not a hand-approximated
schema. This is wired into the runtime (`GymActKernel.episode_ocel_log()`),
not orphaned code. Among everything surveyed in this paper's research pass,
this is GymAct's single closest point of contact with van der Aalst's own
later, most personally-associated body of work — he co-created the OCEL 2.0
standard at the PADS chair, RWTH Aachen, released October 2023.

Paired against this, precisely: `gymact/process.py`'s `ConformanceChecker`
(confirmed directly, `process.py:96-133`) never consumes this log. It takes
a bare `list[Operation]` — a caller-assembled sequence, not an OCEL
artifact — and returns `ConformanceResult(conformant: bool,
deviations: list[Deviation])`. No fitness score. No precision score. No
generalization measure. No simplicity measure. Zero instances of any of
van der Aalst's four named quality dimensions (Buijs, van Dongen, van der
Aalst, 2012) anywhere in the module.

The finding is not "GymAct lacks conformance checking" — it has real
conformance-checking code, doing real, useful work (catching a real,
concrete class of bug: an episode's operations executed out of legal
order). The finding is sharper and more falsifiable than that: **the real
OCEL 2.0 log GymAct already, genuinely produces and the real conformance
checker GymAct already, genuinely runs are two disconnected artifacts.**
`process.py` could be checking richer conformance against the exact log
`ocel.py` already builds, schema-validated, from the same underlying
`Receipt` data — and today does not.

## 5. Finding 2: an illustrative sketch of a scored checker (not a proposal)

Given the real OCEL log `ocel.py` already produces and the real
`LIFECYCLE` table `process.py` already has, here is what each of van der
Aalst's four dimensions would concretely mean if applied to them together.
This is illustrative only — no algorithm, schema, or code here is proposed
for implementation, matching the discipline of both companion papers.

- **Fitness**: for every real episode's event sequence in the OCEL log
  (an `episode` object's related events, ordered by `time`), can
  `LIFECYCLE` replay it without deviation? This is close to what
  `ConformanceChecker.check()` already computes per-episode — the
  aggregate, corpus-wide *fitness ratio* (fraction of real episodes/traces
  that replay cleanly) is the part currently missing; today's checker
  reports pass/fail per call, never a ratio over the whole observed corpus.
- **Precision**: does `LIFECYCLE` permit operation sequences that never
  actually occur in any real OCEL log? `LIFECYCLE`'s `OBSERVE` node alone
  permits five real successors (`process.py:32-37`) — whether all five are
  ever actually exercised in practice, or whether the table is more
  permissive than observed reality, is an open, checkable-in-principle
  question this paper does not answer.
- **Generalization**: does the checker penalize a plausible but
  not-yet-observed real sequence (e.g. a legitimate `CHECKPOINT` between two
  `ACT`s never yet seen in a real episode) as if it were a genuine
  deviation? Van der Aalst's own field treats over-tight fitting to the
  exact observed log as a real quality defect, not a virtue — a hand-written
  table like `LIFECYCLE` is not automatically safe from this failure mode
  just because a human, not a mining algorithm, authored it.
- **Simplicity**: `LIFECYCLE` is already about as simple a representation
  as a transition table can be — eight nodes, direct edges, no nested
  structure. Whether it is simpler *than warranted* (i.e., underfit —
  missing real, legitimate structure a discovered model would have
  surfaced, such as distinguishing "first-ever `OBSERVE`" from
  "`OBSERVE` after `RESTORE`") is, again, open and not answered here.

Whether a real implementation of this would use **token-based replay**
(cheaper, the older and still-used technique for scalable fitness
computation) or **alignment-based conformance checking** (more expensive,
explicitly surfaces log-only/model-only "skip" moves, generally considered
more precise) is a real, open design choice in van der Aalst's own
literature — not resolved here, and not GymAct-specific.

## 6. Finding 3: the `replay` false friend

`gymact/replay.py`'s own opening line (confirmed directly,
`replay.py:1`): *"Evidence replay admission. Replay validates evidence and
never silently actuates."* `ReplayMode` (`replay.py:12-16`) names four
modes (`EVIDENCE_REPLAY`, `VERIFIER_REPLAY`, `SIMULATION_REPLAY`,
`LIVE_REEXECUTION`); `replay_ledger()` performs hash-chain verification,
causal-parent-closure checking, and identity-field consistency checking
against a caller-supplied `ReplayExpectation` — explicitly documented as
having "no executor parameter and therefore cannot actuate."

This is a real terminology collision, not a criticism of the mechanism
itself (which is real, useful, and does what it says). Van der Aalst's
technical sense of "replay" is specific and different: re-executing a
process model's formal semantics (firing Petri net transitions, walking an
automaton) against a recorded log's events, to compute fitness and related
metrics. GymAct's `replay` computes no fitness, touches no process model,
and never executes anything against `LIFECYCLE` — it verifies the
*evidence chain's own cryptographic integrity*, a ledger-verification sense
of "replay" closer to blockchain/audit-log usage than to process mining's.

Two options, presented evenhandedly, no winner picked here: rename this
module's public vocabulary to avoid the collision (e.g. `ledger_integrity`
in place of `replay`), or leave the name and add an explicit disambiguating
note to its module docstring naming the two senses and which one applies.
Either is a small, concrete, low-risk change relative to §4/§5's larger
open questions — named here as a real finding worth acting on, separately
from them.

## 7. Finding 4: does episode-as-case-notion cause deficiency?

Van der Aalst's 2019 paper "Object-Centric Process Mining: Dealing with
Divergence and Convergence in Event Data" (SEFM 2019) names three precise
problems that arise from flattening multi-object event data into a single
case notion: **convergence** (one event duplicated across multiple cases
because it relates to multiple objects of the chosen case-notion type),
**divergence** (spurious repeated activity within one case, caused by
events tied to a different, non-case-notion object type), and
**deficiency** (events dropped entirely because they don't fit any case
under the chosen notion).

`gymact/evidence.py`'s ledger is natively single-case-shaped: `episode_id`
is the real, functioning case notion (used throughout, e.g. as one of two
fields defining "same intended effect" for idempotency comparison).
Genuine multi-object structure — `subject_ref` and `capability_ref` as
real, identity-bearing OCEL objects with qualified relationships to
events — exists only inside `ocel.py`'s projection, built downstream from
the flat receipt chain, not as `evidence.py`'s own native structure.

Applying the precise vocabulary rather than a vague worry: does this cause
**deficiency**? Concretely — if a real `capability_ref` (e.g. `run_kubectl`)
or a real `subject_ref` (a specific environment) participates across
multiple real episodes, is any event about that capability's or
environment's cross-episode behavior ever dropped because `episode_id` is
the ledger's only native grouping key? This paper does not assert an
answer — it names the question the vocabulary makes precisely askable,
which the pre-OCEL-vocabulary version of this concern could not do.
**Convergence** and **divergence** are less obviously evidenced by what was
read this session: convergence would require an event tied to multiple
episodes under an episode-as-case notion, which the model as read does not
appear to produce (each `Receipt` carries exactly one `episode_id`);
divergence would require events from a non-case object type appearing as
spurious repeats within one episode, which was not observed in the
`receipts_to_ocel` output structure as read. Naming which of the three
problems is and is not evidenced, rather than asserting all three apply
uniformly, is itself an application of §1's discipline — a vague
"object-centricity would help" claim is exactly the kind of unfalsifiable
statement this paper's own lens exists to rule out.

## 8. What this document itself would not survive independent conformance checking on

Applying §1's lens to this paper, not just to GymAct's code:

- This document is itself **self-reported** — written from one vantage
  point, in one investigative pass, never checked against an independent
  observer's separate reading of the same code, still less against a real
  trace of GymAct's behavior collected over time.
- §5's sketch is **argued, not measured** — no real fitness ratio, no real
  precision score, was computed against any real OCEL log this session.
  Van der Aalst's own field treats an argued-but-unmeasured quality claim
  as exactly the failure mode conformance checking exists to catch; this
  paper's §5 is, by its own standard, unverified.
- §3's classification of `LIFECYCLE` as "hand-written, not discovered" is a
  source-reading claim, confirmed by reading the file directly this
  session, but not independently cross-checked against, say, git blame
  history or author testimony that no discovery process ever informed its
  original construction.
- §7's deficiency question is explicitly left open rather than answered —
  correctly, by this paper's own discipline, but worth stating plainly:
  this paper resolves fewer questions than it poses.

What would be required to actually check this paper's own central claim
(§4): run `ConformanceChecker` against real OCEL logs collected from real
episodes, and report the real, measured fitness/precision numbers — not
argued ones. That is explicitly out of scope here, by the same paper-only
discipline the two companion documents already committed to. It is the
obvious next artifact if anyone wanted to move past illustration.

## 9. What we don't know / non-commitments

- Whether a real fitness/precision/generalization/simplicity-scored
  checker is worth building at all, given GymAct's real trial volume to
  date (this session's own related investigation found ~0-1 completed real
  trials of a different, adjacent system) — a scoring mechanism with no
  real corpus of deviations to have caught is a hypothesis, not a proven
  need, the same caution the certification companion paper already named.
- Whether token-based replay or alignment-based conformance checking would
  be the right technique, if this were ever built — not resolved here.
- Whether `replay.py` should actually be renamed, or merely documented more
  precisely — no recommendation given, both options named as live.
- Whether §7's deficiency question has a real answer at all, or whether
  `episode_id`-as-case-notion is simply the right grain for what GymAct
  needs and no real information is lost — genuinely open.

None of this is a commitment to build anything. It is a paper, applying one
real body of published work precisely to one real, existing codebase.

## See also

- `2026-08-12-chatman-ecosystem-errc-8020-1000x.md` — widens this paper's
  §5 gap (no known consumer for a fitness/precision/generalization/
  simplicity-scored check) to the whole portfolio, and finds a candidate:
  `wasm4pm`'s own doctrine claims exactly this analysis capability already.
- `2026-08-12-gymact-ocel-analysis-implementation-plan-part2.md` — checked
  that candidate directly, found it overstated, and instead **actually ran**
  van der Aalst & Berti's real object-centric Petri net discovery
  (`pm4py.discover_oc_petri_net`) plus token-based replay against a real
  gymact OCEL fixture this session — real evidence this paper's §5 sketch
  is achievable, not merely illustrative, once a real consumer is used.
- `2026-08-12-gymact-certification-and-ggen-from-sregym.md` — the
  certification companion this paper's §2 extends rather than restates.
- `2026-08-12-why-unify-gyms-first-principles.md` — the more foundational
  companion asking why gyms should unify behind GymAct at all; this paper
  assumes GymAct's existence and asks a narrower, internal question about
  its evidence/conformance model specifically.
- `src/gymact/process.py`, `src/gymact/ocel.py`, `src/gymact/replay.py`,
  `src/gymact/evidence.py` — the real code every finding above cites
  directly.
- Buijs, J.C.A.M., van Dongen, B.F., van der Aalst, W.M.P. (2012), "On the
  Role of Fitness, Precision, Generalization and Simplicity in Process
  Discovery" — source of the four quality dimensions used throughout.
- van der Aalst, W.M.P. et al. (2016), "In Log and Model We Trust? A
  Generalized Conformance Checking Framework" — source of §1's independence
  framing.
- van der Aalst, W.M.P. (2019), "Object-Centric Process Mining: Dealing
  with Divergence and Convergence in Event Data," SEFM 2019 — source of
  §7's convergence/divergence/deficiency vocabulary.
- van der Aalst, W.M.P. et al., OCEL 2.0 Specification (2023),
  ocel-standard.org / arXiv:2403.01975 — the standard `ocel.py` implements.
