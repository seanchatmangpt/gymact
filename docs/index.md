# GymAct Documentation Hub

GymAct 26.10.8 is a public-semantic execution profile and Python reference runtime for bounded
benchmark worlds. The documentation follows the [Diataxis](https://diataxis.fr/) framework in four
quadrants. Standing vocabulary: `UNKNOWN`, `PARTIAL_ALIVE`, `ALIVE`, `BLOCKED`, `BUILD_BROKEN`,
`UNSUPPORTED`.

## 1. Explanation / Topics (Understanding-Oriented)

Why the system is shaped as it is.

- [Architecture](explanation/architecture.md) — layers of the runtime, gym roster and providers.
- [Assurance](explanation/assurance.md) — the consequence pipeline and cross-runtime contract.
- [Combinatorial maximum](explanation/combinatorial-maximum.md) — the DCM law inventory and its
  machine law at `src/gymact/schemas/dcm-v26.8.7.json`.
- [GymAct PRD/ARD](explanation/gymact-prd-ard.md) — product and architecture requirements.
- [Actuation layer PRD](explanation/prd-gymact-actuation-layer.md) — product requirements for the
  actuation layer.
- [SJ-008 triage baseline](explanation/sj-008-triage-baseline.md) — why the SJ-008 manifest's 10
  recorded failures at 26.10.8 are all environment-bound (zero regressions), and how to
  reproduce with `GYMACT_ALLOW_DEGRADED_STANDINGS`.

## 2. Reference (Information-Oriented)

- [API reference](reference/reference.md) — public modules and functions.
- [Generated reference (doc-hdit)](reference/generated/reference.md) — doc-hdit-scaffolded
  skeletons over the full code surface (1848 modules); regenerable, do not hand-edit tables.
- [Global hub](reference/global-hub.md) — external documentation hub.

## 3. Tutorials / How-To

No tutorials or how-to guides yet. Operational records (dated ERRC notes under `docs/2026-*`) are
deliberately excluded from this map.

---

The semantic profile is packaged in `src/gymact/ontology/profile.ttl`; executable profile
constraints live in `profile.shacl.ttl`. Repository README:
<https://github.com/seanchatmangpt/gymact#readme>.
