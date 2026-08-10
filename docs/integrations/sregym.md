# SREGym — first fully supported GymAct gym

GymAct treats [SREGym](https://github.com/SREGym/SREGym) as the first benchmark gym with an explicit end-to-end support contract.

Compatibility baseline is admitted through the shared `vendor_benchmarks.py` exact-pin machinery (`VENDOR_SPECS["sregym"]`), not a standalone constant — see `_audit_spec`/`VendorSpec` in `gymact.gyms.vendor_benchmarks`.

## Support contract

“Supported” does **not** mean GymAct reimplements SREGym. SREGym remains authoritative for problem definitions, Kubernetes deployment, fault/noise injection, MCP tool exposure, diagnosis/mitigation oracles, agent isolation, and native result artifacts. GymAct wraps that real execution with admission, authority, consequence classification, receipts, verification, replay, and standing.

The boundary is:

```text
SREGym checkout + exact-pinned revision (vendor_benchmarks.py audit)
  -> GymAct SregymVendorProvider materialization
  -> long-lived `main.py` subprocess + persistent MCP clients
  -> admitted SREGym run intent
  -> BRCE / authority-gated DO (run_kubectl / submit_diagnosis / submit_mitigation)
  -> upstream conductor HTTP/MCP surface
  -> GymAct observation (/status polling)
  -> independent GymAct verify
  -> Receipt / OCEL replay
```

The implementation lives in `gymact.gyms.sregym`.

## Session shape: persistent, not one-shot

Unlike `vendor_benchmarks.py`'s `VendorBenchmarkProvider` (one subprocess per call), SREGym needs a persistent session across a multi-step trial: repeated `kubectl` calls through its MCP surface, then a final diagnosis/mitigation submission. `SregymEnvironment.__init__` launches `main.py` once as a long-lived subprocess and keeps real `fastmcp.Client` connections open against its `kubectl-mcp` server (default port 9954, `/kubectl/sse`, tool `exec_kubectl_cmd_safely`) and its conductor HTTP API (default port 8000, `/status` for polling, `/submit_mcp/sse` for the `submit` MCP tool) across every `actuate()` call — matching `mcp_client_session.py`'s "open once, reuse" pattern.

## What is preserved from SREGym

`config.agent_name` selects the real sregym client driver invoked via `main.py --agent <agent_name> --model <judge_model_id> --problem <problem_id> --agent-timeout <wall_clock_timeout_s>`. It defaults to `"debug"` — a real, pre-existing `agents.yaml` entry (`kickoff_command: python -c "import signal; signal.pause()"`) that keeps the conductor's HTTP API alive and responsive while `SregymEnvironment` drives it externally via `actuate()`, rather than letting the client run its own internal benchmark loop to completion and exit (confirmed against a live checkout this session — see `sregym.py`'s own module/function docstrings for the full investigation trail: `autofde_lab_planner`'s driver does not exist on disk, `autofde_lab_dspy` and `--use-external-harness` both exit before `SregymEnvironment` can drive them externally).

Materialization config keys: `agent_name` (default `"debug"`), `judge_model_id`, `problem_id`, `wall_clock_timeout_s`, `judge_api_base`/`judge_api_key_placeholder` (rendered into `AGENT_API_BASE`/`AGENT_API_KEY` env vars), `mcp_server_port`, `api_port`, `startup_timeout_seconds`, `verify_timeout_seconds`, `teardown_timeout_seconds`, `requires_authority` (defaults `True`), and `root` (defaults to the vendor-audited checkout root).

The provider deliberately launches SREGym in its own `uv` project. SREGym has a large, fast-moving dependency graph and owns its execution environment. GymAct therefore does not vendor or flatten those dependencies into GymAct itself.

## Real capabilities

`SREGYM_CAPABILITIES` (registered under provider name `"sregym"`):

- `urn:gymact:sregym:capability:observe_cluster_state` (READ) — the conductor's real `/status` endpoint.
- `urn:gymact:sregym:capability:run_kubectl` (DO) — a real `kubectl` command through sregym's real `kubectl-mcp` server.
- `urn:gymact:sregym:capability:submit_diagnosis` (DO) — a real diagnosis, via the conductor's `submit` MCP tool.
- `urn:gymact:sregym:capability:submit_mitigation` (DO) — a real mitigation, via the same `submit` MCP tool.
- `urn:gymact:sregym:capability:get_benchmark_status` (READ) — the conductor's `/status` endpoint, benchmark-stage view.

## Consequence and scoring law

SREGym is a live Kubernetes benchmark. Every `run_kubectl`/`submit_diagnosis`/`submit_mitigation` invocation is `Consequence.DO` and `SregymEnvironment.requires_authority` defaults `True`.

A subprocess exit or a successful MCP tool call is not a benchmark verdict. GymAct's `verify()` independently judges observed state; it does not trust the provider's own success report. This preserves GymAct's global law:

```text
request accepted != world changed != objective verified != benchmark scored
```

## Prerequisites

Prepare SREGym according to its own installation instructions. GymAct requires an actual checkout and checks for the host-side tools that SREGym's current quickstart requires:

- Git;
- `uv`;
- Docker;
- `kubectl`;
- Helm.

SREGym currently requires Python 3.12 for its own project. GymAct itself may still run on its broader supported Python range because execution crosses the subprocess/project boundary.

Set `config.root` to an absolute checkout path, or rely on `vendor_root("sregym")`'s default vendor-directory resolution. The provider fails closed on upstream revision drift by default via `vendor_benchmarks.py`'s `_audit_spec` — a mismatched pinned revision refuses materialization before any subprocess starts.

## Single-problem episode

```python
from gymact import MaterializationIntent
from gymact.gyms.sregym import SregymVendorProvider

runtime.register_provider(SregymVendorProvider())
materialized = await runtime.materialize(
    MaterializationIntent(
        provider="sregym",
        config={
            "root": "/absolute/path/to/SREGym",
            "problem_id": "misconfig_app_hotel_res",
            "judge_model_id": "openai/gemma-4-26b-a4b-it",
            "wall_clock_timeout_s": 600,
        },
    )
)
```

Materialization does not run the benchmark. It only admits an exact SREGym checkout/configuration as the episode subject and starts the persistent conductor subprocess/MCP session. The relevant DO capability must then flow through the normal GymAct authority/BRCE path.

Because SREGym attempts may legitimately run for many minutes, configure `RuntimeLimits.actuate_timeout_s` high enough for the admitted timeout plus SREGym deployment/evaluation overhead. The kernel maximum is 3600 seconds.

## ggen E2E verifier pack

`ggen/sregym-e2e-pack/` is the compiled-side Gall checkpoint for this integration. It obeys the GymAct ggen boundary: **ggen does not generate the Python provider and does not actuate SREGym**. The real benchmark remains on the Python/SREGym path above. The pack projects the same admitted semantic facts into a powerless Rust/WIT verifier closure.

The pack ontology fixes the following facts before generation:

- exact upstream repository and vendor-audited compatibility revision;
- `urn:gymact:sregym:capability:submit_mitigation` as a GymAct `DO` capability representing a completed benchmark attempt (retargeted from the earlier `capability:run` IRI when the provider implementation changed from a CLI-wrapping design to the persistent-MCP-session `SregymVendorProvider` — a provider swap, not a semantic redesign);
- terminal predicate `solved=true`;
- receipt order `materialize -> act -> verify -> teardown`;
- required evidence `authority-admitted`, `native-result-artifact-read`, `ocel-schema-valid`, and `replay-conformant`;
- WIT package/interface/world identity.

A real `ggen sync run` against the pack manufactures, in the consumer tree only:

```text
src/sregym_e2e_contract.rs
wit/sregym-e2e.wit
tests/sregym_e2e_contract_proof.rs
```

The generated Rust verifier has no subprocess, Kubernetes, credential, model, or BRCE execution API. It can only return `Alive` when the exact subject, `solved=true`, exact receipt sequence, and all required evidence IDs are present; otherwise it returns `Refused`.

Run the pack acceptance boundary with:

```bash
GGEN_BIN=/path/to/ggen RUSTC_BIN=/path/to/rustc \
  bash ggen/sregym-e2e-pack/check.sh
```

That checker performs real `ggen sync run`, verifies the signed ggen receipt and receipt history, checks exact generated content, compiles and executes the generated Rust proof, verifies second-sync byte identity, then injects a conflicting SREGym revision and requires `010_contract.rq` to refuse without changing the prior generated bytes. Generated projections are scratch/consumer outputs and are **not committed** to GymAct.

## Real ALIVE criterion

Provider/unit tests and successful ggen manufacture are **not** sufficient to claim an SREGym benchmark subject ALIVE. A SREGym subject is ALIVE only after all of the following are observed for the exact admitted problem/revision/model configuration:

1. the real SREGym checkout and exact upstream revision are admitted;
2. a real SREGym problem is deployed and fault-injected;
3. the agent runs against SREGym's real interface;
4. the upstream diagnosis/mitigation oracle results are read from SREGym's real MCP/HTTP surface, not synthesized;
5. GymAct independently verifies the expected terminal observation;
6. the materialize/act/verify/teardown receipt sequence is exported as a schema-valid OCEL 2.0 log and conformant replay succeeds.

Until step 6 has happened for an exact subject, the integration may be structurally complete but that benchmark execution is not crowned ALIVE. The generated ggen verifier is an independent projection of this admission law, not a substitute for the real episode evidence.

## Checkpoint semantics

GymAct does not pretend a JSON checkpoint can restore a Kubernetes world. SREGym owns recovery and cleanup. Before actuation, the GymAct evidence state can be restored. After actuation, `restore()` refuses rather than manufacturing a false rollback claim.

## Upstream drift

The compatibility revision is admitted through `vendor_benchmarks.py`'s shared exact-pin machinery. Updating it is a compatibility event: inspect upstream CLI/MCP-surface/result-schema changes, update the ggen E2E graph/gate in the same change, rerun GymAct contract tests and the ggen pack checker, then execute at least one real problem end to end before changing standing for the new revision.
