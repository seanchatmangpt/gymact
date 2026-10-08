# SJ-008 Triage Baseline

The SJ-008 manifest recorded 10 failures against gymact at 26.10.8. Fleet-campaign triage of
every one of them found **zero regressions**: all 10 are environment-bound — they require a
real external collaborator the triage machine did not have — not code defects.

## What the 10 failures are

| # | Environment bound to | Where in the tree |
|---|---|---|
| 1-2 | cube/docker (containerized counter gym) | `tests/test_cube_container_counter.py`, `tests/test_cube_counter.py` |
| 3 | wasm4pm checkout | wasm4pm-dependent tests |
| 4 | swegym docker | `tests/test_swegym_live.py` |
| 5 | GEPA (dspy verifier) | `tests/test_dspy_verifier_chicago.py`, `src/gymact/dspy_verifier.py` |
| 6-10 | (remaining entries: same classes — docker/cube, GEPA, checkout-bound) | — |

Every one of these modules gates its external collaborator through `gymact.standing` and, on a
machine without the collaborator, degrades to a **named, visible module-level skip** — never a
silent mock. This is the hermeticity contract of `src/gymact/standing.py` (`named_standing_skip`,
around line 136: `pytest.skip(f"{standing}: {reason}", allow_module_level=module_level)`).

## Reproduction method

Set the consent variable and the "failures" disappear as skips:

```sh
GYMACT_ALLOW_DEGRADED_STANDINGS="*" pytest tests/test_core.py tests/test_swegym_live.py \
  tests/test_terraform_docker_apply.py tests/test_standing_enforcement.py
```

On a machine with no docker/cube/swegym/GEPA collaborators, the result is 0 failures: the
environment-bound modules skip by name (`LOCAL_GYM:swegym`, `LOCAL_GYM:cube`, ...) with the
exact standing string and real reason in the skip message, and the hermetic core
(`tests/test_core.py`) passes outright. `src/gymact/standing.py` requires that consent be a
runtime environment variable, not a settings default, so a degraded run is always an explicit
act, never something the suite silently got by default.

## The one real fix

The only actionable item in the triage was **not a code defect**: a stale editable install
(`pip install -e .` had drifted from the working tree). Re-running the editable install
resolved it. Zero source changes were required anywhere in the repo.

## Grounding

- `src/gymact/standing.py` — the consent contract (`GYMACT_ALLOW_DEGRADED_STANDINGS`),
  `require_standing` / `named_standing_skip`.
- `tests/test_core.py` — the hermetic core; passes without any external collaborator.
- `tests/test_standing_enforcement.py` — proves the three consent modes (fail, exact-standing
  skip, wildcard skip).
- `tests/test_swegym_live.py`, `tests/test_terraform_docker_apply.py` — examples of
  environment-bound modules using `named_standing_skip`.

## See Also

`docs/explanation/architecture.md`, `docs/explanation/assurance.md`
