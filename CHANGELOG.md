# Changelog

## [Unreleased]

### Added

- OCEL 2.0 process-mining export off any episode's real receipt trail: `GymAct.episode_receipts()` and `GymAct.episode_ocel_log()`, backed by a new receipt-accumulation chokepoint (`_emit`) that every existing lifecycle call now routes through.
- `probe_repo` FastMCP tool: a read-only repository prober (README/pyproject/setup.py plus a top-level listing, truncated) with no shell/exec access -- actual command execution stays behind `actuate()`/authority, unaffected by this addition.
- `GenericDiscoveredProvider` (`gymact.gyms.discovered`): a generic `EnvironmentProvider` that runs an LLM-proposed, bounded subprocess recipe (`command`/`cwd`/`timeout_seconds`/`success_markers`) against an arbitrary checked-out repo, rather than a hand-written adapter per benchmark subject.
- `scripts/discover_and_actuate.py`: an end-to-end probe -> propose -> actuate -> OCEL driver exercising the above.
- `scripts/ocel_standing.py`: a strict standing-derivation script that computes actuation standing purely from on-disk OCEL logs (schema validation + `ConformanceChecker` replay + an explicit `solved=True` marker check on `act` receipts). Currently scoped to the `GenericDiscoveredProvider` convention specifically -- it does not yet recognize other providers' own success signals (e.g. `TerraformPlanProvider`'s `verify()` boolean), so a passing provider-level test suite is not automatically the same claim as a `GYMACT_ACTUATED` corpus standing for those providers yet.
- Real cross-validation: an episode's exported OCEL log is independently re-validated via a real `cargo run --bin wpm -- receipt verify-ocel2` subprocess against `~/wasm4pm` (`tests/test_ggen_legacy_gym.py::test_ocel_export_is_independently_validated_by_wasm4pm`), skipping cleanly via `require_standing` when no local wasm4pm checkout is present.
- `KubernetesReconciliationProvider` (`gymact.gyms.kubernetes_reconciliation`): a real `kubectl`-subprocess-backed provider whose `materialize()` applies a real manifest to a real local `kind` cluster and whose `verify()` polls real cluster-observed pod phase rather than trusting `kubectl apply`'s exit code.
- `McpClientSessionProvider` (`gymact.gyms.mcp_client_session`): a real `fastmcp.Client` session against a real subject MCP server (client-of-a-subject, distinct from GymAct's own existing MCP server-side surface).
- `TerraformPlanProvider` (`gymact.gyms.terraform_plan`): a real `terraform`/`tofu` `init -backend=false` + `plan` provider with exactly one DO capability (`plan`) and structurally no `apply`/`destroy` capability.
- `TerraformDockerApplyProvider` (`gymact.gyms.terraform_docker_apply`): a real `apply`/`destroy`-capable Terraform provider, safely scoped to a hand-authored, checked-in config targeting only colima's local Docker daemon (`kreuzwerker/docker` provider) -- never a cloud provider.

## 26.8.7 - 2026-08-07

### Added

- Public-ontology GymAct application profile using PROF, PROV-O, P-PLAN, SOSA/SSN, WoT TD, ODRL, SHACL, EARL, DQV, QUDT, DCAT, SKOS, OWL-Time, and Dublin Core Terms.
- Mechanical zero-custom-TBox admission check plus real pySHACL validation.
- `sosa:Procedure` capability projection with SHACL-enforced title and READ/DO consequence classification.
- Pydantic v2 canonical runtime models separating semantic capability IRI from provider-local binding.
- Environment/EnvironmentProvider execution boundary and deterministic reference MemoryProvider.
- Receipted, idempotent environment materialization with optional external authority admission.
- Fail-closed external AuthorityResolver for consequential actuation, restore, and teardown.
- Per-episode concurrency serialization, exact idempotent replay, and conflicting-key refusal.
- Bounded provider failure receipts with error digests rather than arbitrary provider text.
- Independent observation and verification; benchmark scoring remains a distinct layer.
- Native Python surfaces through FastAPI/OpenAPI, FastMCP, Typer, and FastStream.
- Profile export for ggen/Rust/WIT/WASM or other independent compilers.
- Python 3.11/3.12/3.13 CI, strict docs, clean wheel/sdist installation, and production container admission gates.

### Architectural rule

Python composes mature Python libraries directly. Rust/WIT/WASM projections are manufactured separately from the same admitted semantic graph. Provider bindings are implementation detail; public semantic capability identity is the interoperability boundary.
