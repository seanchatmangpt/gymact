# The Chatman Ecosystem, read through ERRC / 80-20 / 1000x

**Status: paper only. No code, org change, or repo action proposed here is
executed.** Fourth in the series started with the three GymAct-scoped papers
this session (`2026-08-12-gymact-certification-and-ggen-from-sregym.md`,
`2026-08-12-why-unify-gyms-first-principles.md`,
`2026-08-12-gymact-process-mining-reading-van-der-aalst.md`) — this one
widens the aperture from GymAct alone to the full, real, local portfolio.

## On method

Three lenses, applied together, each with a precise meaning kept distinct
throughout rather than blurred into one vague "strategy" pass:

- **ERRC** (Kim & Mauborgne, *Blue Ocean Strategy*): four actions —
  **Eliminate** (what should stop existing), **Reduce** (what should shrink
  below industry/internal norm), **Raise** (what should grow above it),
  **Create** (what doesn't exist yet and should). The framework's discipline
  is that a real strategy touches all four, not just "create more" — most
  strategy documents fail by only ever proposing Create.
- **80/20**: which ~20% of the ecosystem's real mass or effort accounts for
  ~80% of its real, load-bearing value — and, symmetrically, which 80% of
  mass is low-leverage.
- **1000x**: not "better," but which single, disproportionate move would
  unlock capability out of scale with its own cost — the opposite of
  incremental roadmap thinking.

Every claim below is grounded in real, this-session-verified facts: each
repo's own root doctrine file (`CLAUDE.md`/`AGENTS.md`/`README.md`), and a
real file-count census run directly (`find ~/<repo> -name "*.rs" -o -name
"*.py"`, excluding vendor/build/worktree noise). Where a claim would need
evidence not yet gathered (e.g. whether two repos' overlapping claims are
redundant or complementary), it is named as an open question, not asserted.

## The real portfolio, by the numbers

| Repo | Source files | Last commit | Self-declared role (verbatim/paraphrased from its own root doctrine) |
|---|---:|---|---|
| `autofde-lab` | 16,488 | 2026-08-12 | "the canonical decision, planning, hypothesis, and integration control plane... does not itself receive ambient authority to actuate" |
| `praxis` | 13,763 | 2026-08-06 | "Chatman Engine is the concrete realization of μ (`A = μ(O*)`)" |
| `wasm4pm` | 3,164 | 2026-08-12 | owns process-model evidence and continuously maintained process hypotheses; owns "all analysis: discovery, conformance, fitness, precision, variants" (stated directly in `ggen`'s own `CLAUDE.md`) |
| `ggen` | 2,538 | 2026-08-12 | deterministic manufacture: "Code precipitates from RDF via five-stage pipeline μ₁-μ₅"; "EMITS process evidence. ggen does NOT analyse it." |
| `mfw` | 1,593 | 2026-07-29 | owns admission, broker, standing verdicts (per `autofde-lab`'s own `CLAUDE.md`: "No admission, no broker, no actuation, no standing verdict. `mfw` owns those.") |
| `bcinr` | 962 | 2026-08-09 | "performance-first systems library... branchless algorithms, PDDL planning, POWL workflows, and cryptographic receipts"; owns the symbolic partial-order scheduler (per `autofde-lab`'s `CLAUDE.md`) |
| `wasm4pm-compat` | 870 | 2026-08-12 | ggen-provisioned compatibility/witness layer for `wasm4pm` |
| `SREGym` | 523 | 2026-08-12 | (fork; a real, live benchmark — not portfolio-owned infrastructure, included for scale contrast only) |
| `ggen-legacy` | 65 | 2026-08-07 | legacy-repository reconstitution for Fortune-5-scale estates — a distinct, specialized downstream application, **not** redundant with `ggen` core (verified: real, different scope — repository archaeology + replacement manufacture + retirement standing) |
| `ggen-create` | 50 | 2026-08-07 | scaffolds new ggen packages from working examples (hygen-create parity contract) — also distinct, not redundant |
| `gymact` | 240 | 2026-08-11 | executable benchmark-world truth and consequences: "owns executable benchmark-world truth and consequences. A gym result is not production authority." |
| `autofde` (production actuation) | **0 — does not exist** | — | per `FORWARD_DEPLOYMENT.md`: owns "production authority, the exclusive `BRCE.DO` consequence path, re-observation, consequence receipts, and replay. Zero production actuation is valid without a receipt-bearing BRCE path." Confirmed directly, earlier this session: no `~/autofde` repository exists anywhere on this machine. |

Total real source mass across the 11 that exist: ~40,206 files.
`autofde-lab` + `praxis` alone: 30,251 — **~75% of the portfolio's entire
code mass**, in the two repos whose own doctrine explicitly denies them
production-actuation authority.

## The 80/20 finding: the ecosystem's mass is inverted relative to its own stated authority

`FORWARD_DEPLOYMENT.md`'s own canonical lifecycle:

```text
parse → route → admit/refuse → diagnose/repair → construct
     → BRCE.DO → verify → receipt → replay/hook → standing
```

and its own governing formula, `A = μ(O*)`, `R = receipt(A)`. Read plainly:
**nothing in this lifecycle is real, production-consequential authority
until `BRCE.DO` and `receipt(A)`** — and the repo that owns that stage
(named "`autofde`" in the doctrine, distinct from `autofde-lab`) has zero
files, confirmed absent from this machine.

Meanwhile the two repos explicitly and repeatedly denied that authority by
their own doctrine — `autofde-lab` ("does not itself receive ambient
authority to actuate customer systems") and, on a plain reading, `praxis`
(its own claim is to realize μ, the *construction* function, not `BRCE.DO`
or `receipt(A)`) — together hold three-quarters of all real code in the
portfolio. `gymact`, the one repo whose own doctrine names it as touching
**executable, real-consequence benchmark worlds** ("A gym result is not
production authority" is a real disclaimer, but the disclaimer exists
precisely because `gymact` is the closest thing to real consequence that
does exist) is the *smallest* of the core repos measured — 240 files,
roughly 1.5% of `autofde-lab`'s size alone.

This is the paper's sharpest 80/20 finding, stated precisely: **the
portfolio's code mass and its portfolio's own stated locus of consequence
point in opposite directions.** This is not, by itself, evidence of
misallocation — a planning/candidate-generation layer legitimately needs
more code than an actuation layer if actuation is meant to stay minimal and
auditable by design (a receipt-bearing `BRCE.DO` path arguably *should* be
small and heavily scrutinized, not large). But it is worth naming plainly
rather than left implicit, because it means: **~75% of this portfolio's
engineering investment currently produces artifacts (candidate plans,
hypotheses, possibility graphs) that cannot become real consequences without
a fourth-stage system that does not yet exist.**

## ERRC, applied

### Eliminate

- **Nothing found this session warrants elimination with confidence.**
  The one candidate considered — `ggen-legacy`/`ggen-create` as redundant
  with `ggen` core — was checked directly and rejected: both have real,
  distinct, specialized scopes (Fortune-5 legacy-repo reconstitution;
  new-package scaffolding), not duplicated function. Naming a real
  investigation that produced a negative result is itself evidence this
  paper isn't reaching for Eliminate items to pad the framework out.

### Reduce

- **New engineering mass in `autofde-lab` and `praxis`, specifically**,
  until the fourth-stage (`autofde`, production actuation) exists to
  consume what they produce. Not a claim that existing work in either repo
  is wasted — it is real, evidenced, working candidate-generation
  machinery — but continuing to grow the two largest repos in a four-stage
  pipeline whose consequential stage is unbuilt is a real, checkable
  imbalance, not a hypothetical one.
- **Overlapping μ-realization claims between `praxis` and `ggen`** — named
  as an open question, not an elimination target: `praxis`'s `CLAUDE.md`
  states "Chatman Engine is the concrete realization of μ (`A = μ(O*)`)";
  `ggen`'s states "Code precipitates from RDF via five-stage pipeline
  μ₁-μ₅," `A = μ(O)`. No confirmed dependency relationship between the two
  was found this session (`praxis`'s own doctrine mentions `ggen-pack` once,
  in passing) — it is real, open, and worth someone with authority over
  both repos resolving directly: are these complementary (e.g. `ggen`
  generates code, `praxis` is deliberately-hand-optimized execution
  substrate) or genuinely redundant claims to the same formula? This paper
  does not know, and says so rather than guessing.

### Raise

- **The fourth stage, `autofde` (production authority, `BRCE.DO`,
  consequence receipts, replay)** — named in the portfolio's own governing
  document, currently the single largest gap between what the ecosystem's
  doctrine claims as its purpose (a path "from incomplete operational
  observation to admitted context, lawful construction, authorized
  actuation, receipts, and replay") and what exists. This is the portfolio's
  own stated telos, unbuilt.
- **`gymact`'s real evidence machinery, relative to its own small size** —
  240 files already contain a genuine RFC8785+BLAKE3 hash-chained receipt
  ledger, real HMAC-signed attestation checkpoints, and a real,
  schema-validated OCEL 2.0 exporter (all confirmed directly this session,
  see the process-mining companion paper). Proportionally, this is some of
  the highest evidence-density-per-file in the portfolio — worth raising as
  a real, working reference pattern the larger repos could be measured
  against, not treated as a small satellite project because of its file
  count.

### Create — the 1000x candidate

**Wire `gymact.ocel`'s real OCEL 2.0 export into `wasm4pm`'s real,
already-existing process-mining analysis engine.**

This is the paper's headline finding, and it converges directly with the
process-mining companion paper's central gap: that paper's §5 sketched,
*hypothetically and illustratively only*, what a fitness/precision/
generalization/simplicity-scored conformance checker would look like for
gymact's OCEL log — explicitly declining to propose building it, since no
such capability was known to exist. **This session's ecosystem-wide pass
found that `wasm4pm` already, by its own repo's stated scope
(confirmed via `ggen`'s own `CLAUDE.md`, which explicitly defers analysis to
it), owns exactly that: "discovery, conformance, fitness, precision,
variants."**

If that scope claim holds up under direct verification (not yet done this
session — named as the necessary next check, not assumed true merely
because two repos' doctrine agree with each other), the 1000x argument is
precise: the hard part of van der Aalst-grade process mining — discovery
algorithms, alignment/token-replay conformance checking, the four quality
dimensions — would not need to be built for `gymact` at all. It would need
to be **wired**: point `wasm4pm`'s real analysis engine at the real,
already-schema-validated OCEL logs `gymact.ocel.receipts_to_ocel()` already
produces. Near-zero net-new algorithmic code: one export path, one
consumption contract, versus building fitness/precision/generalization/
simplicity computation from scratch inside `gymact` (which is what the
process-mining paper's §5 stopped short of proposing precisely because that
cost looked large in isolation — it looks categorically different once a
real, already-built consumer is in scope).

This is also where 80/20 and 1000x meet: `wasm4pm` is 3,164 files — real,
substantial, but a fraction of `autofde-lab`'s 16,488 — and if its stated
analysis scope is real, it is currently the highest-leverage *underused*
asset in the whole portfolio relative to `gymact`'s specific evidence gap.

## What this paper itself would not survive independent checking on

Same discipline as the process-mining companion's §8, applied here:

- The central 1000x claim rests on **`wasm4pm`'s doctrine as reported by a
  different repo (`ggen`'s `CLAUDE.md`)**, not on this paper independently
  reading `wasm4pm`'s own source and confirming it can actually ingest an
  arbitrary OCEL 2.0 JSON log, let alone `gymact`'s specific one. This is a
  real, named gap in this paper's own evidence, not glossed over.
- The 80/20 file-count census is a real, directly-run command, but source
  file count is a rough proxy for "engineering mass" — it says nothing about
  code density, test coverage, or how much of any repo's file count is
  vendored/generated versus hand-authored. `autofde-lab`'s 16,488 in
  particular includes generated ontology projections and vendored gym
  checkouts this session already knows about; the true hand-authored,
  load-bearing figure is smaller than the raw count and was not separated
  out here.
- "Nothing found this session warrants elimination" is a negative result
  from checking exactly one candidate pair (`ggen-legacy`/`ggen-create` vs.
  `ggen`) — it is not a claim that no elimination candidate exists anywhere
  in an 11-repo, ~40,000-file portfolio; it is honest about the one check
  actually performed.

## What we don't know / non-commitments

- Whether `wasm4pm` can actually consume `gymact`'s specific OCEL 2.0
  output today, without adapter work — unverified, the single most
  important open item this paper leaves.
- Whether `praxis` and `ggen`'s overlapping μ-claims are complementary or
  redundant — named, not resolved.
- Whether the `autofde-lab`+`praxis` mass-vs-authority imbalance reflects a
  real strategic problem or a defensible "candidate layers are naturally
  larger than actuation layers" pattern — this paper states the fact and
  names both readings; it does not adjudicate between them.
- Whether building the fourth stage (`autofde`) is actually the right next
  investment, or whether the ecosystem is intentionally sequenced to mature
  the candidate layers fully before actuation — a real strategic choice this
  paper surfaces as a gap, not a recommendation to act on immediately.

## See also

- `2026-08-12-gymact-ocel-analysis-implementation-plan-part2.md` — **Part 2:
  this paper's headline Create finding was checked directly against
  wasm4pm's own source and found overstated (wasm4pm's real OCEL analysis
  capability is narrower and less reachable than described here); Part 2
  corrects it and validates a real alternative path (`pm4py`, used
  directly) with an actually-executed check, not just a plan.
- `2026-08-12-gymact-process-mining-reading-van-der-aalst.md` — the direct
  precedent for this paper's headline Create finding; its §5 explicitly
  declined to propose building fitness/precision/generalization/simplicity
  computation for gymact, for want of a known consumer — this paper found
  the candidate consumer.
- `2026-08-12-why-unify-gyms-first-principles.md` — the companion asking why
  gyms unify behind GymAct specifically; relevant background for why
  `gymact`'s small-but-dense evidence machinery looks the way it does.
- `2026-08-12-gymact-certification-and-ggen-from-sregym.md` — the
  certification companion; its ggen-role argument (manufacture the *shape*,
  never the verdict) is the same discipline this paper's Create section
  respects (wire evidence to an analysis engine; don't have either side
  self-certify the result).
- `~/autofde-lab/FORWARD_DEPLOYMENT.md` — source of the portfolio's own
  canonical lifecycle and `A = μ(O*)`, `R = receipt(A)` formulation this
  paper's 80/20 argument is built directly against.
