# Multicloud Gym — Ontology, Provider, and Verification Report

Version: 26.8.8 (unreleased-since-tag head). Last updated 2026-08-08.

## What this is

A new GymAct provider, `MulticloudProvider`/`MulticloudEnvironment`
(`src/gymact/gyms/multicloud.py`), exposing 20 capabilities across AWS, Azure, and GCP
IAM/storage/compute (7 AWS, 6 Azure, 7 GCP), grounded in a public-ontology capability
catalog (`ggen/multicloud-gym-pack/ontology.ttl`, currently untracked).

## Ontology design

Per `.claude/rules/ontology.md`, the catalog reuses only existing public vocabularies —
no new `rdfs:Class` or `owl:*Property` was declared. The grounding pass confirmed each
prefix resolves to a real, dereferenceable namespace and applied terms only where they
add real semantic content beyond the unchanged base typing:

| Prefix | Namespace | Grounds |
|---|---|---|
| `dct:` | `http://purl.org/dc/terms/` | `dct:title`/`dct:type` on every `sosa:Procedure` (SHACL-required, unchanged) |
| `sosa:` | `http://www.w3.org/ns/sosa/` | base typing of every capability as `sosa:Procedure` (unchanged) |
| `odrl:` | `http://www.w3.org/ns/odrl/2/` | `rdf:type odrl:Permission` on the 3 policy-attach/role-assign ops: AWS `iam.attach_role_policy`, Azure `authorization.create_role_assignment`, GCP `iam.add_iam_policy_binding` |
| `org:` | `http://www.w3.org/ns/org#` | `rdfs:seeAlso org:Role` on `aws.iam.create_role` only |
| `dcat:` | `http://www.w3.org/ns/dcat#` (matches the http-scheme already committed in `src/gymact/ontology/profile.ttl`) | `rdfs:seeAlso dcat:Distribution` on the 3 bucket/account-creation ops |
| `prov:` | `http://www.w3.org/ns/prov#` | `rdfs:seeAlso prov:Entity, prov:Activity` on the 3 compute-provisioning ops |
| `rdfs:` | `http://www.w3.org/2000/01/rdf-schema#` | the `seeAlso` linking predicate (core RDFS, not invented) |

Deliberate non-additions, documented as comments in the file rather than silently
omitted:

- `gcp.iam.create_service_account` gets no role/identity grounding — a GCP service
  account is an identity, not an `org:Role`, and no identity-vocabulary research was
  done this pass.
- `sosa:Actuation`/`sosa:Actuator` (confirmed real terms) were **not** applied anywhere
  in this catalog — they type an invocation *event*, not the capability/procedure
  *type* the catalog describes; applying them here would conflate the two.
- ODRL's generic `odrl:Action`/`odrl:action`/`odrl:target` were confirmed real but not
  used — redundant with `sosa:Procedure` at this level, or require instance data this
  catalog doesn't carry.

## Provider design

`CAPABILITY_REGISTRY` in `src/gymact/gyms/multicloud.py` holds 20 `Capability` objects,
one per `sosa:Procedure` in `ontology.ttl`, with `iri`/`title`/`consequence` copied
verbatim from that file's `dct:title`/`dct:type` facts.

`MulticloudEnvironment` is a real in-memory state machine
(`_state = {"aws": {...}, "azure": {...}, "gcp": {...}}`) with zero network, credential,
or cloud-API use — documented directly in the module docstring. `requires_authority=True`
by default. `actuate()` dispatches through a `binding -> handler` table; DO handlers
mutate real dict entries and generate realistic-looking simulated IDs (AWS ARNs,
Azure resource-ID paths, GCP resource-name paths), and enforce referential integrity —
e.g. attaching a policy to a nonexistent role raises, which the runtime surfaces as a
real `BLOCKED` receipt rather than a silent success. `observe()`/`checkpoint()` deep-copy;
`verify()` mirrors `MemoryEnvironment`'s shallow-key-match pattern; `restore()`/
`teardown()` mirror `MemoryEnvironment` exactly.

`MulticloudProvider` sets `materialization_requires_authority = False` (materialization
itself unauthenticated, matching `MemoryProvider`'s convention) — only DO actuation
inside the environment is authority-gated. Confirmed by reading `gymact/kernel.py`'s
real `act()`: it refuses any READ-consequence capability outright
(`READ_CAPABILITY_IS_NOT_ACTUATION`) before authority is ever checked, and gates only
DO capabilities on `environment.requires_authority`.

## Real test / verification results

`tests/test_multicloud.py` (14 tests): ontology-parity test that parses the real
`ontology.ttl` with `rdflib` and compares `(title, consequence)` per IRI against
`CAPABILITY_REGISTRY`, plus uniqueness and three-cloud-coverage checks; functional tests
through the real `gymact.runtime.GymAct` orchestrator (authority refusal with world
unchanged, admitted actuation via a real `AllowListAuthorityResolver`, provider-side
referential-integrity failure surfacing as `BLOCKED`, READ-capability actuation refusal,
idempotent actuation, checkpoint/restore round-trip including restore's own authority
gate, idempotent teardown); and a cross-cloud scenario test creating an AWS IAM role,
Azure storage account, Azure VM, GCP service account, GCP IAM binding, and GCP compute
instance in one episode, verified and torn down.

Real pytest output:

```
tests/test_multicloud.py ..............                                  [100%]
============================== 14 passed in 0.42s ==============================
```

Real mock-usage grep (required by `~/.claude/rules/testing-chicago-style.md`), zero
matches:

```
$ grep -rnE "unittest\.mock|Mock\(|MagicMock|patch\(|monkeypatch|@patch|create_autospec|mocker\." --include="*.py" src/gymact/gyms/multicloud.py tests/test_multicloud.py
(no output, exit code 1)
```

### Independent re-verification (this session)

Full text of the independent re-verification pass, quoted verbatim:

> **1. pytest — CONFIRMED, real run**
> `.venv/bin/python -m pytest tests/test_multicloud.py -v` → `14 passed in 0.41s`. Includes a genuine ontology-parity test (`test_capability_registry_matches_ontology_exactly`) that does a real rdflib parse of `ggen/multicloud-gym-pack/ontology.ttl` and diffs it against `CAPABILITY_REGISTRY` — no gaps, no drift, real comparison, not a stub.
>
> **2. Mock usage — CONFIRMED zero**
> The grep against `src/gymact/gyms/multicloud.py` and `tests/test_multicloud.py` for `unittest.mock|Mock(|MagicMock|patch(|monkeypatch|@patch|create_autospec|mocker.` returned no matches (exit code 1). Genuinely mock-free.
>
> **3. ggen pack validation — FAILS, contradicts the builder's claim**
> Mirrored `just ggen-bridge-check` exactly for `multicloud-gym-pack` against a fresh scratch consumer project (real `ggen sync run`, binary confirmed on PATH at `/Users/sac/.cargo/bin/ggen`, version 26.8.6):
>
> ```
> ERROR: CLI execution failed: Command execution failed: validation error: [FM-PACK-002]
> pack `multicloud-gym-pack`: pack.toml unreadable at
> `/Users/sac/gymact/ggen/multicloud-gym-pack/pack.toml`: No such file or directory (os error 2).
> Remediation: every pack must ship a pack.toml.
> ```
>
> Root cause, independently confirmed by directory listing: `ggen/multicloud-gym-pack/` has **no `pack.toml`** and its `templates/` directory is **completely empty** (`ls -la` shows only `.`/`..`). By contrast `ggen/gymact-bridge-pack/` has a real `pack.toml` and 4 real `.tmpl` files. So neither of the two things needed for `ggen sync run` to work exists in the multicloud pack — the run fails before it ever reaches template generation.
>
> **Any claim that the 4 expected files (operation catalog, MCP tool schema, reference doc, cross-check proof test) were "genuinely generated with real content" via a real `ggen sync run` does not hold up.** No such run is possible against this pack as it currently exists — it fails immediately on pack loading, not partway through generation. This is a `BLOCKED`/`UNSUPPORTED` standing for the ggen bridge, not `ALIVE`. There is also no template borrowing to flag either way, since there are no templates at all — the pack is simply not wired into ggen yet, only the ontology/gates/symlinks exist.
>
> **4. SHACL admission — mixed**
>
> - GymAct's own core profile: `.venv/bin/gymact validate-profile` → `{"conforms": true, ... "triple_count": 96}`, exit 0. Core profile unaffected/still passing.
> - The multicloud pack's own SPARQL gates, run for real via rdflib against the real parsed `ontology.ttl` (since ggen never got far enough to run them itself): `010_required.rq` → 0 violations, `020_single_valued.rq` → 0 violations. The ontology file itself is internally well-formed and gate-clean.
>
> **Capability count discrepancy:** the task description states 18 capabilities. The real count, verified two independent ways (rdflib `COUNT(DISTINCT ?s)` over `sosa:Procedure` in `ontology.ttl`, and `len(CAPABILITY_REGISTRY)` in the actual Python module), is **20**, not 18. Both counts agree with each other (20=20, which is what the passing parity test checks), so the code/ontology pair is internally consistent — but whoever reported "18" to you undercounted by 2.
>
> ### Bottom line
> - Tests: real, passing, mock-free. Ontology/code parity: real and correct at 20 capabilities (not 18).
> - ggen packaging: **not functional**. `ggen/multicloud-gym-pack` is missing `pack.toml` and has zero templates, so `ggen sync run` fails at the pack-loading stage. Whatever the builder reported about a successful ggen bridge run for this pack is not reproducible and does not match the current filesystem state — this part of the build is `BLOCKED`, not `ALIVE`.

## What this does and does not establish

**Does establish**: a working, mock-free, in-memory SIMULATED environment exercising
GymAct's real authority/receipt/verification machinery (`kernel.py`'s `act()`,
`AuthorityResolver`, `BLOCKED` refusal typing, checkpoint/restore) against a 20-capability
catalog spanning AWS/Azure/GCP IAM, storage, and compute concepts, with its capability
catalog grounded in real public ontologies and zero new custom TBox terms. Test suite is
real, passing, and independently re-verified this session.

**Does not establish**: any real multicloud infrastructure automation. This is a
**SIMULATED** environment — no real cloud API calls, no AWS/Azure/GCP SDK use, no
credentials of any kind, and no network I/O. `MulticloudEnvironment` is a pure Python
dict mutated in-process; its generated ARNs/resource-ID paths are realistic-looking
strings, not real cloud resources. A real integration would need real cloud SDK calls
(`boto3`, `azure-sdk`, `google-cloud`) behind the same `Capability`/authority boundary
this provider already establishes — that work has not been attempted here.

The ggen packaging story for this gym is also unresolved: `ggen/multicloud-gym-pack`
currently has no `pack.toml` and an empty `templates/` directory, so `ggen sync run`
fails at pack-loading before any template generation — a `BLOCKED` standing, distinct
from and not implied by the passing pytest suite.

## Relevant paths

- `/Users/sac/gymact/src/gymact/gyms/multicloud.py`
- `/Users/sac/gymact/tests/test_multicloud.py`
- `/Users/sac/gymact/ggen/multicloud-gym-pack/ontology.ttl` (untracked)
- `/Users/sac/gymact/ggen/multicloud-gym-pack/` (missing `pack.toml`, empty `templates/`)
- `/Users/sac/gymact/ggen/gymact-bridge-pack/pack.toml` (working reference pack, for comparison)
- `/Users/sac/gymact/justfile` (lines 89–133, `ggen-bridge-check` target, the pattern mirrored during re-verification)
