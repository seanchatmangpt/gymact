# Assurance model

GymAct v26.8.7 separates semantic authority, execution, evidence and standing so that an integration cannot become `ALIVE` merely because it imports or returns a successful command status.

## Consequence pipeline

```text
public semantic profile
        ↓
semantic capability identity (`sosa:Procedure`)
        ↓
materialization intent
        ↓
provider admission + SHACL capability validation
        ↓
observation
        ↓
actuation intent
        ↓
input bounds
        ↓
authority decision (when required)
        ↓
bounded provider actuation
        ↓
independent post-observation
        ↓
receipt → BLAKE3 evidence chain
        ↓
independent verification
        ↓
explicit benchmark scorer
```

The following claims are intentionally distinct:

```text
request accepted
    != provider acknowledged
    != world changed
    != objective verified
    != benchmark scored
```

## Runtime bounds

`RuntimeLimits` bounds authority, materialization, observation, actuation, verification, recovery and teardown wall-clock time. It also bounds input, observed state and checkpoint serialization size. Inputs that exceed admitted limits are refused before DO. External timeouts are `BLOCKED` because inability to establish an outcome is not a semantic denial and not success.

## Evidence

Every newly created materialization, actuation, restore and teardown receipt is appended to the configured `ReceiptLedger`. The reference `MemoryReceiptLedger` binds each record to the previous record and to the canonical receipt payload with BLAKE3-256. Idempotent replay of the same accepted operation returns the same receipt and does not manufacture a second DO record.

`GymAct.evidence_rdf()` projects the evidence graph with PROV-O and independent verification assertions with EARL. GymAct does not invent a custom evidence ontology.

## Cross-runtime contract

`build_contract()` exposes a self-digested contract containing the GymAct profile IRI, the exact evidence-backed operation vocabulary, digest algorithm and Pydantic JSON Schemas used by the Python reference runtime. This is the handoff point for ggen/Rust/WIT/WASM manufacture and observational-equivalence testing.

The Python runtime composes Python-native libraries. It does not generate FastAPI, FastMCP, Typer or FastStream boilerplate through ggen merely because code generation is possible.

## Plugin standing

Provider entry-point discovery is metadata-only. A provider plugin is imported only through an explicit `load_provider_plugin(name)` call. Missing plugins are `UNSUPPORTED`; duplicate identities are `REFUSED`; import/contract failures are `BLOCKED` with hashed error evidence.

## Standing

`UNKNOWN`, `PARTIAL_ALIVE`, `ALIVE`, `BLOCKED`, `BUILD_BROKEN`, `UNSUPPORTED` and `REFUSED` remain evidence standings, not marketing labels. External gym integrations retain their own standing independently of the GymAct kernel.
