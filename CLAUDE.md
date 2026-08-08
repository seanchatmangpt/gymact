# GymAct engineering law

GymAct is a Python reference runtime for a public-semantic execution profile over bounded benchmark worlds.

## Canonical decision architecture

Design for Combinatorial Maximum (DCM) is the canonical production decision law.

```text
public RDF possibility graph
  -> SHACL admission
  -> lossless runtime projection
  -> structural scan
  -> complete maximal proven-reversible closure
  -> applicability filter
  -> empirical/Pareto retrieval where useful
  -> explicit semantic irreversible cut
  -> fresh authority admission
  -> BRCE
  -> consequence
  -> independent observation
  -> verification
  -> closure-bound receipt
  -> replay
```

Preserve lawful reversible alternatives before irreversible selection. A failed edge is topology, not graph failure. `COMPENSATABLE != REVERSIBLE`; `UNKNOWN != REVERSIBLE`. A truncated closure cannot authorize a cut.

A DO morphism must carry exact powerless semantic identity for action, subject, capability, verifier and expected effect before it can become an admitted irreversible frontier. Planner/model/query/cache/transport output is never authority.

`gymact.dcm` is the canonical public DCM API. Legacy selector, candidate-cache and direct `BrokerRequest` surfaces are compatibility projections only; they do not define production decision semantics.

## Semantic authority

- Do not add GymAct-owned OWL/RDFS classes or RDF/OWL properties merely for convenience.
- Prefer PROF, PROV-O, P-PLAN, SOSA/SSN, WoT TD/TM, ODRL, SHACL, EARL, DQV, QUDT, DCAT, SKOS, OWL-Time, and DCTERMS.
- `urn:gymact:*` is for profile resources, ABox identities, SKOS concepts, and SHACL shapes.
- Before adding handwritten semantic machinery, prove the requirement cannot be represented as a public-ontology fact, constraint, profile, mapping, or projection.
- The public RDF possibility graph is canonical for DCM; Python models are lossless runtime projections.

## Consequence law

Never collapse these claims:

```text
request accepted != world changed != objective verified != benchmark scored
```

- An `authority_ref` is not permission.
- Required authority is fail-closed unless the injected `AuthorityResolver` explicitly admits the exact operation.
- A request or transport must never install, grant, or widen authority by itself.
- Provider failures must not disappear as successful or unreceipted consequential operations.
- Idempotency-key reuse with a different intent is a refusal, not a replay.
- Production DO requires an explicit DCM cut and BRCE.
- The cut binds graph, complete closure, path, DO morphism, semantic consequence, prepared intent, grant, selector and evidence basis.

## Python vs Rust/ggen

Python composes mature Python libraries directly: Pydantic, FastAPI, FastMCP, Typer, FastStream, RDFLib, pySHACL, Gymnasium/PettingZoo where applicable.

Do not generate Python boilerplate with ggen when the host ecosystem already derives the surface correctly from Python types. ggen is the bridge from the same admitted RDF graph into Rust/WIT/WASM/static manufacture and an independent equivalence checkpoint.

Cognition compile-out manufactures a re-admitted graph route, not cached execution authority and not a privileged executable candidate.

## Evidence and standing

Use `UNKNOWN`, `PARTIAL_ALIVE`, `ALIVE`, `BLOCKED`, `BUILD_BROKEN`, `UNSUPPORTED`, and typed `REFUSED` reasons. Importability is not scenario execution. A benchmark integration retains its own execution standing.

DCM source implementation is `STRUCTURAL` until the exact public graph -> complete closure -> cut -> real consequence -> independent verification -> closure-bound receipt -> replay chain executes against an exact subject. Prior provider execution does not retroactively crown a new DCM path.

Do not claim v26.8.7 release standing until exact-head CI has executed the semantic/runtime tests, Python matrix, package/wheel installation, docs build, lock validation, and container build required by the release contract.

## Change discipline

- Keep the generic kernel smaller than benchmark-specific integrations.
- New benchmark families should normally become providers/profiles, not new transports.
- Keep FastAPI, FastMCP, FastStream, and CLI semantics downstream of the same DCM court/runtime.
- Preserve the public semantic graph as the cross-language authority boundary.
- Preserve every lawful reversible alternative unless an explicit ontology/capability/authority/cost/evidence bound excludes it.
- Never rank before applicability.
- Never select from truncated closure.
- Never let a compatibility optimization become a second canonical decision authority.
