# SWE-Gym — HuggingFace-dataset-backed GymAct gym

GymAct treats [SWE-Gym](https://huggingface.co/datasets/SWE-Gym/SWE-Gym) as a benchmark gym with an explicit end-to-end support contract, grounded in the upstream dataset's own held-out test directives.

Compatibility baseline: `SWE-Gym/SWE-Gym` (HuggingFace, `train` split).

Unlike `sregym.md`, `terraform-docker`, and every other `VendorBenchmarkProvider` entry, this compatibility subject is **not** a pinned git checkout at an exact SHA. SWE-Gym ships no runnable harness repository for GymAct to launch a subprocess against. The admitted subject is a HuggingFace dataset revision: one row of `SWE-Gym/SWE-Gym` (or a caller-supplied dataset override, e.g. `SWE-Gym/SWE-Gym-Lite`), identified by its own `instance_id`, plus the upstream prebuilt Docker image published for that instance. There is no git HEAD to pin; the dataset row itself, fetched live via the `datasets` library, is the admitted upstream artifact. This is a deliberate, named difference from `SREGYM_ROOT`/`_git_head` revision pinning, not an oversight.

## Support contract

"Supported" does **not** mean GymAct reimplements SWE-Gym's grading. SWE-Gym remains authoritative for problem definitions, `FAIL_TO_PASS`/`PASS_TO_PASS` test directives, base commits, test patches, and the upstream prebuilt evaluation images. GymAct wraps that real execution with admission, authority, consequence classification, receipts, verification, replay, and standing.

The boundary is:

```text
SWE-Gym/SWE-Gym dataset row (live HuggingFace fetch, by instance_id)
  -> GymAct SWEGymProvider materialization
  -> admitted SWE-Gym task intent
  -> authority-gated DO (urn:gymact:swegym:capability:evaluate-patch)
  -> docker pull / docker run upstream xingyaoww/sweb.eval.x86_64.<instance_id> image
  -> baseline PASS_TO_PASS run (pre-patch)
  -> test_patch apply -> candidate patch apply -> FAIL_TO_PASS / PASS_TO_PASS run
  -> GymAct observation (resolved derived from real test outcomes)
  -> independent GymAct verify
  -> Receipt / OCEL replay
```

The implementation lives in `gymact.gyms.swegym`.

## What is preserved from SWE-Gym

GymAct projects directly onto the upstream dataset's own fields and the upstream Harbor image-naming convention rather than inventing a shadow grading scheme. Supported selection and execution controls include:

- one task via `task_id` -> dataset `instance_id` lookup;
- the upstream dataset or a named override via `config.dataset` (default `SWE-Gym/SWE-Gym`);
- the upstream split via `config.split` (default `train`);
- evaluation timeout via `config.eval_timeout`;
- upstream `repo`, `base_commit`, `test_patch`, `FAIL_TO_PASS`, and `PASS_TO_PASS` fields, read as-is from the dataset row;
- the exact upstream image-naming scheme (`xingyaoww/sweb.eval.x86_64.<instance_id with '__' -> '_s_'>`, lowercased) reproduced from Harbor's own `swegym/utils.py::get_image_names`;
- the exact 3-tier patch-apply fallback (`git apply` -> `git apply --reject` -> `patch --forward`) and baseline-subtract PASS_TO_PASS semantics from upstream `swegym_cube.task.SWEGymTask`.

The provider deliberately launches evaluation inside the upstream prebuilt Docker image rather than reconstructing a local Python/test environment. SWE-Gym's images already carry the pinned dependency graph and conda `testbed` environment each task requires; GymAct therefore does not vendor or flatten that graph into GymAct itself.

## Consequence and scoring law

SWE-Gym evaluation mutates a live Docker world: it pulls an image, starts a container, applies patches, executes test suites, and tears the container down. Every evaluation is `Consequence.DO` and `SWEGymEnvironment.requires_authority == True`.

A container that starts and a test command that exits is not a solved benchmark. GymAct keeps these claims separate:

```text
docker exec returncode == 0
!= fail_to_pass_results.passed
!= pass_to_pass_results.passed
!= resolved
```

`resolved` is derived only when every `FAIL_TO_PASS` test passes (strict) and every `PASS_TO_PASS` test either passes or was already failing in the pre-patch baseline run (baseline-subtract semantics — a pre-existing PASS_TO_PASS failure is never counted as a candidate-patch regression). This mirrors upstream `swegym_cube.task.SWEGymTask.evaluate` exactly.

This preserves GymAct's global law:

```text
request accepted != world changed != objective verified != benchmark scored
```

## Prerequisites

No SWE-Gym checkout is required. GymAct requires:

- the `datasets` library (HuggingFace) — materialization raises `SWEGYM_DATASET_DEPENDENCY_MISSING` if absent;
- Docker;
- Git (required inside the container path for `git apply`/safe-directory handling; also checked host-side).

The provider checks for `docker` and `git` on the host at materialization time and raises `SWEGYM_DEPENDENCY_MISSING:<binary>` if either is missing.

## Single-task episode

The provider itself is registered like any other GymAct provider:

```python
from gymact import MaterializationIntent
from gymact.gyms.swegym import SWEGymProvider

runtime.register_provider(SWEGymProvider())
materialized = await runtime.materialize(
    MaterializationIntent(
        provider="swegym",
        scenario="conan-io__conan-14760",
        config={
            "task_id": "conan-io__conan-14760",
            "eval_timeout": 1800,
        },
    )
)
```

Materialization fetches the live dataset row for `task_id` and does not run the benchmark; it only admits an exact task/image as the episode subject (`SWEGymProvider.materialization_requires_authority == False`). The `urn:gymact:swegym:capability:evaluate-patch` DO capability must then flow through the normal GymAct authority path, carrying the candidate `patch` in the actuation payload.

Because image pulls and full FAIL_TO_PASS/PASS_TO_PASS runs may legitimately take many minutes, configure `RuntimeLimits.actuate_timeout_s` high enough for `config.eval_timeout` plus image-pull overhead. The kernel maximum is 3600 seconds.

## Known image-availability gap on full-corpus admission

The SWE-Gym/SWE-Gym dataset has 2438 rows, each requiring its own upstream prebuilt image. Not every published image is guaranteed pullable: the Harbor adapter's own oracle validation found **38 of 2438** upstream images unresolvable for this reason. This is a real, live-discovered gap in upstream image availability, not a GymAct defect and not something GymAct can predict ahead of a real `docker pull`.

GymAct does **not** carry a hardcoded skip list of the known-bad 38 instance IDs — a static list would silently drift from upstream reality as images are published, removed, or repointed. Instead, `SWEGymEnvironment.actuate()` attempts a real `docker pull` for the admitted task's image and, on failure, raises a typed `SWEGYM_IMAGE_UNAVAILABLE:<task_id>` refusal discovered live at grading time. Any full-corpus (2438-task) admission claim must treat this refusal class as an expected, individually surfaced outcome for a known minority of tasks — never as evidence GymAct itself is broken, and never papered over by pre-filtering task IDs against a frozen list.

## Non-root writability gap

Some SWE-Gym images ship root-owned package subdirectories that a non-root container user cannot make writable. GymAct applies the same git-safe-directory-plus-copy/move writability normalization upstream's `swegym_cube.task.SWEGymTask._make_tool`/`_raise_if_unpatchable` applies, then probes writability directly rather than silently attempting a patch that would fail with "Permission denied" and be misread as a candidate-patch defect. An unpatchable container is a typed refusal, `SWEGYM_CONTAINER_UNPATCHABLE_NON_ROOT:<task_id>`, never a silent `resolved=False`.

## ggen E2E verifier pack

`ggen/swegym-e2e-pack/` is the compiled-side Gall checkpoint for this integration. It obeys the GymAct ggen boundary: **ggen does not generate the Python provider and does not actuate SWE-Gym**. The real benchmark remains on the Python/Docker path above. The pack projects the same admitted semantic facts into a powerless Rust/WIT verifier closure.

The pack ontology fixes the following facts before generation:

- `dct:source` pointing at the HuggingFace dataset page (`https://huggingface.co/datasets/SWE-Gym/SWE-Gym`), not a fabricated git URL, since SWE-Gym has no git checkout revision;
- `urn:gymact:swegym:capability:evaluate-patch` as a GymAct `DO` capability;
- terminal predicate `solved=true`;
- receipt order `materialize -> act -> verify -> teardown`;
- required evidence `authority-admitted`, `native-result-artifact-read`, `ocel-schema-valid`, and `replay-conformant`;
- WIT package/interface/world identity (`gymact:swegym-e2e@0.1.0`).

The ontology's `dct:hasVersion "SWE-Gym/SWE-Gym@main"` is a named placeholder pin (see the `TODO(swegym-provider-pin)` header comment in `ggen/swegym-e2e-pack/ontology.ttl`): the exact resolved HuggingFace dataset revision hash must be substituted once the Python provider module determines it live — never fabricated in its place.

## Real ALIVE criterion

Provider/unit tests and successful ggen manufacture are **not** sufficient to claim a SWE-Gym benchmark subject ALIVE. A SWE-Gym subject is ALIVE only after all of the following are observed for the exact admitted task/dataset-revision configuration:

1. the real dataset row is fetched live and admitted for the exact `task_id`;
2. the real upstream image is pulled and a real container started;
3. the real 3-tier patch-apply fallback and baseline-subtract test run execute inside that container;
4. the FAIL_TO_PASS/PASS_TO_PASS results are read from the real `docker exec` test output, not fabricated;
5. GymAct independently verifies the expected terminal observation (normally `{"resolved": True}`);
6. the materialize/act/verify/teardown receipt sequence is exported as a schema-valid OCEL 2.0 log and conformant replay succeeds.

Until step 6 has happened for an exact subject, the integration may be structurally complete but that benchmark execution is not crowned ALIVE. The generated ggen verifier is an independent projection of this admission law, not a substitute for the real episode evidence.

## Real end-to-end verification procedure

Per this repo's `.claude/rules/ocel-standing.md`, a gym's "working" claim is never a pytest verdict. Confirming SWE-Gym standing requires a real graded episode, run manually:

**Requirements:** Docker daemon running, network access (HuggingFace dataset fetch + Docker image pull), the `datasets` package installed.

1. Pick a known `task_id` from `SWE-Gym/SWE-Gym` (e.g. an instance not in the 38-image-unavailable set).
2. Materialize it:

   ```python
   materialized = await runtime.materialize(
       MaterializationIntent(
           provider="swegym",
           scenario=task_id,
           config={"task_id": task_id, "eval_timeout": 1800},
       )
   )
   ```

3. As a self-check, actuate with the task's **own gold patch** — not an agent-generated one — so that a correct outcome is independently known in advance:

   ```python
   result = await runtime.act(
       materialized,
       capability=SWEGYM_EVALUATE_CAPABILITY,
       payload={"patch": gold_patch},
       authority_ref=AUTHORITY,
   )
   ```

4. Assert `result["after"]["resolved"] is True` directly off the real observed state — never a hardcoded expected string, never trust a summarizing script's packaged verdict.
5. Export the episode's receipt sequence to `reports/ocel/swegym/episode.ocel.json` and validate it directly:

   ```python
   from gymact.ocel import validate_ocel_log
   from gymact.process import ConformanceChecker

   validate_ocel_log(log)  # real jsonschema validation against the OCEL 2.0 schema
   ConformanceChecker().check(log)  # real replay of materialize -> act -> verify -> teardown
   ```

6. Confirm the log's own `act` event carries `solved=True` (or the task-specific equivalent) as a real attribute, not an inferred/derived value from outside the log.

Only after steps 4-6 succeed for a real task_id is that SWE-Gym subject's standing ALIVE rather than structurally complete.

## Checkpoint semantics

GymAct does not pretend a JSON checkpoint can restore a Docker container's mutated filesystem. Docker and the upstream image own container lifecycle; container cleanup already happens inside `actuate()`'s own `finally` block. Before actuation, the GymAct evidence state can be restored (`checkpoint()` reports `restorable=True` only when `attempted` is still `False`). After actuation, `restore()` refuses with `SWEGYM_EXTERNAL_WORLD_RESTORE_UNSUPPORTED` rather than manufacturing a false rollback claim.

## Upstream drift

Because the compatibility subject is a live dataset fetch rather than a pinned git SHA, upstream drift takes a different shape than `sregym.md`'s SHA-bump event: a task's dataset row, `FAIL_TO_PASS`/`PASS_TO_PASS` directives, or published image can change or disappear between two materializations of the same `task_id` without any GymAct-visible version bump. Treat any change in observed `resolved` outcome for a previously-graded `task_id` as a signal to re-check the live dataset row and image before assuming a GymAct or candidate-patch regression.
