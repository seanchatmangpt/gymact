# SREGym — first fully supported GymAct gym

GymAct treats [SREGym](https://github.com/SREGym/SREGym) as the first benchmark gym with an explicit end-to-end support contract.

Compatibility baseline: `SREGym/SREGym@ba07faf1a322f9b6d4a279643bb796aa2f36f64b`.

## Support contract

“Supported” does **not** mean GymAct reimplements SREGym. SREGym remains authoritative for problem definitions, Kubernetes deployment, fault/noise injection, MCP tool exposure, diagnosis/mitigation oracles, agent isolation, and native result artifacts. GymAct wraps that real execution with admission, authority, consequence classification, receipts, verification, replay, and standing.

The boundary is:

```text
SREGym checkout + exact revision
  -> GymAct SREGymProvider materialization
  -> admitted SREGym run intent
  -> BRCE / authority-gated DO
  -> upstream `uv run python main.py ...`
  -> upstream result CSV
  -> GymAct observation
  -> independent GymAct verify
  -> Receipt / OCEL replay
```

The implementation lives in `gymact.gyms.sregym`.

## What is preserved from SREGym

GymAct projects directly onto the upstream CLI rather than inventing a shadow API. Supported selection and execution controls include:

- one problem via `scenario=<problem-id>` -> SREGym `--problem`;
- the upstream `sregym-lite` suite, or another upstream named suite, via `config.suite` -> `--suite`;
- upstream agent selection via `config.agent`;
- LiteLLM model and judge-model selection;
- reasoning effort;
- noise injection;
- attempt count;
- agent timeout;
- environment variables for model/provider credentials.

The provider deliberately launches SREGym in its own `uv` project. SREGym has a large, fast-moving dependency graph and owns its execution environment. GymAct therefore does not vendor or flatten those dependencies into GymAct itself.

## Consequence and scoring law

SREGym is a live Kubernetes benchmark. Every benchmark run is `Consequence.DO` and `SREGymEnvironment.requires_authority == True`.

A process exit is not a benchmark verdict. GymAct parses the native SREGym CSV and keeps these claims separate:

```text
process_returncode == 0
!= Diagnosis.success
!= Mitigation.success
!= solved
```

`diagnosis_success` and `mitigation_success` are retained separately. `solved=True` is derived only when every benchmark stage actually emitted for the attempt is successful, the run did not deploy-fail or time out, and the upstream process returned successfully.

This preserves GymAct’s global law:

```text
request accepted != world changed != objective verified != benchmark scored
```

## Prerequisites

Prepare SREGym according to its own installation instructions. GymAct requires an actual checkout and checks for the host-side tools that SREGym’s current quickstart requires:

- Git;
- `uv`;
- Docker;
- `kubectl`;
- Helm.

SREGym currently requires Python 3.12 for its own project. GymAct itself may still run on its broader supported Python range because execution crosses the subprocess/project boundary.

Set:

```bash
export SREGYM_ROOT=/absolute/path/to/SREGym
```

The provider fails closed on upstream revision drift by default. To intentionally validate a newer SREGym revision, set `config.expected_revision` to that exact SHA. `allow_revision_mismatch=true` exists only for explicit exploratory work and should not be used for a benchmark claim.

## Single-problem episode

The provider itself is registered like any other GymAct provider:

```python
from gymact import MaterializationIntent
from gymact.gyms.sregym import SREGymProvider

runtime.register_provider(SREGymProvider())
materialized = await runtime.materialize(
    MaterializationIntent(
        provider="sregym",
        scenario="target_port",
        config={
            "root": "/absolute/path/to/SREGym",
            "agent": "codex",
            "model": "gpt-5.4",
            "judge_model": "anthropic/claude-sonnet-4-6",
            "agent_timeout": 1800,
        },
    )
)
```

Materialization does not run the benchmark. It only admits an exact SREGym checkout/configuration as the episode subject. The `urn:gymact:sregym:capability:run` DO capability must then flow through the normal GymAct authority/BRCE path.

Because SREGym attempts may legitimately run for many minutes, configure `RuntimeLimits.actuate_timeout_s` high enough for the admitted `agent_timeout` plus SREGym deployment/evaluation overhead. The kernel maximum is 3600 seconds.

## SREGym-Lite

When neither `scenario` nor `config.suite` is supplied, GymAct selects upstream `sregym-lite`. You can also state it explicitly:

```python
MaterializationIntent(
    provider="sregym",
    config={
        "root": "/absolute/path/to/SREGym",
        "suite": "sregym-lite",
        "agent": "stratus",
        "model": "gpt-5",
    },
)
```

A whole-suite episode can exceed GymAct’s one-hour actuation bound depending on agent timeout and problem count. For receipted benchmarking, the preferred topology is one GymAct episode per SREGym problem, with the suite treated as the selected problem set. That yields one bounded subject and one receipt DAG per SRE incident.

## Real ALIVE criterion

Provider/unit tests are **not** sufficient to claim SREGym ALIVE. A SREGym subject is ALIVE only after all of the following are observed for the exact admitted problem/revision/model configuration:

1. the real SREGym checkout and exact upstream SHA are admitted;
2. a real SREGym problem is deployed and fault-injected;
3. the agent runs against SREGym’s real interface;
4. the upstream diagnosis/mitigation oracle results are read from SREGym’s native result artifact;
5. GymAct independently verifies the expected terminal observation (normally `{"solved": True}`);
6. the materialize/act/verify/teardown receipt sequence is exported as a schema-valid OCEL 2.0 log and conformant replay succeeds.

Until step 6 has happened for an exact subject, the integration may be structurally complete but that benchmark execution is not crowned ALIVE.

## Checkpoint semantics

GymAct does not pretend a JSON checkpoint can restore a Kubernetes world. SREGym owns recovery and cleanup. Before actuation, the GymAct evidence state can be restored. After actuation, `restore()` refuses with `SREGYM_EXTERNAL_WORLD_RESTORE_UNSUPPORTED` rather than manufacturing a false rollback claim.

## Upstream drift

The current compatibility SHA is intentionally explicit in `SREGYM_COMPAT_REVISION`. Updating it is a compatibility event: inspect upstream CLI/result-schema changes, rerun GymAct contract tests, then execute at least one real problem end to end before changing standing for the new SHA.
