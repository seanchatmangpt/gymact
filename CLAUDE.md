# GymAct engineering law

GymAct is a Python reference runtime for a public-semantic execution profile over bounded benchmark worlds.

## Semantic authority

- Do not add GymAct-owned OWL/RDFS classes or RDF/OWL properties merely for convenience.
- Prefer PROF, PROV-O, P-PLAN, SOSA/SSN, WoT TD/TM, ODRL, SHACL, EARL, DQV, QUDT, DCAT, SKOS, OWL-Time, and DCTERMS.
- `urn:gymact:*` is for profile resources, ABox identities, SKOS concepts, and SHACL shapes.
- Before adding handwritten semantic machinery, prove the requirement cannot be represented as a public-ontology fact, constraint, profile, mapping, or projection.

## Consequence law

Never collapse these claims:

```text
request accepted != world changed != objective verified != benchmark scored
```

- An `authority_ref` is not permission.
- Required authority is fail-closed unless the injected `AuthorityResolver` explicitly admits the exact operation.
- A transport must never grant authority by itself.
- Provider failures must not disappear as successful or unreceipted consequential operations.
- Idempotency-key reuse with a different intent is a refusal, not a replay.

## Python vs Rust/ggen

Python composes mature Python libraries directly: Pydantic, FastAPI, FastMCP, Typer, FastStream, RDFLib, pySHACL, Gymnasium/PettingZoo where applicable.

Do not generate Python boilerplate with ggen when the host ecosystem already derives the surface correctly from Python types. ggen is the bridge from the same admitted RDF graph into Rust/WIT/WASM/static manufacture and an independent equivalence checkpoint.

## Evidence and standing

Use `UNKNOWN`, `PARTIAL_ALIVE`, `ALIVE`, `BLOCKED`, `BUILD_BROKEN`, `UNSUPPORTED`, and typed `REFUSED` reasons. Importability is not scenario execution. A benchmark integration retains its own execution standing.

A gym's pytest suite passing is a claim about `request accepted`, not `objective verified` — a provider's own unit tests can correctly pass while proving nothing about whether a real end-to-end episode was actuated. Whether a gym is actuated is decided only by a real, schema-valid, conformant-replay, `solved=True` OCEL 2.0 log (`reports/ocel/<subject>/episode.ocel.json`), asserted on directly per `.claude/rules/ocel-standing.md` — never by a hardcoded expected value or by trusting a summarizing script's packaged verdict.

Do not claim release standing for the current project version until exact-head CI has executed the semantic/runtime tests, Python matrix, package/wheel installation, docs build, lock validation, and container build required by the release contract.

## Git workflow

Documented explicitly per the 2026-08-13 dev_portfolio FMEA/RCA close-out, because the prior
state (silence in this file, a convention that only ever existed as one-off commit-message
prose -- "per repo git-workflow rule" in `af6d46d`/`ad96ef3`) let a real branch-per-task/PR
convention decay without any agent session being able to discover it.

- **Current, real convention: direct commits to `main` are acceptable for solo/agent
  iteration.** The last several dozen commits on `main` are direct, non-merge commits, and
  this repo is private on a plan tier where `gh api repos/.../branches/main/protection`
  returns 403 (branch protection cannot be purchased/configured here) -- there is no
  technical enforcement mechanism for a stricter policy even if one were declared, so
  declaring one without a backstop would just decay again the same way the PR-era
  convention did.
- Branch-per-task tooling still exists and is fine to use whenever isolation is wanted
  (parallel agent work, a change you want reviewed before merging, an experiment you might
  discard): `agent/*`, `feat/*` branch naming and `git worktree` are both already in active
  use elsewhere in this repo's history (`git branch -a`). Use them when isolation earns its
  cost; do not treat direct-to-`main` as forbidden when it doesn't.
- Per this project's fix-forward discipline, never rewrite or force-move already-committed,
  evidenced work off `main` retroactively just to match a workflow preference decided later.
- If a stricter policy (e.g. mandatory branch-per-task) is ever actually wanted, state it
  here explicitly and back it with a local pre-commit hook that warns (not blocks, matching
  this repo's no-destructive-ops ethos) when `HEAD == main` -- GitHub-side branch protection
  is not available on this plan tier, so any enforcement has to be local.

## Change discipline

- Keep the generic kernel smaller than benchmark-specific integrations.
- New benchmark families should normally become providers/profiles, not new transports.
- Keep FastAPI, FastMCP, FastStream, and CLI semantics downstream of the same runtime.
- Preserve the public semantic graph as the cross-language authority boundary.