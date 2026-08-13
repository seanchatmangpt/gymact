# Contributing to gymact

## Adding a new gym: two proofs, not one

Every gym under `src/gymact/gyms/<name>.py` MUST ship with **both** of the
following before it merges. Neither substitutes for the other -- they prove
different things.

1. **A real unit test** (`tests/test_<name>.py` or `tests/gyms/test_<name>_unit.py`,
   Chicago style: real collaborators, real subprocess/API calls, real
   filesystem/state -- never `unittest.mock`/`Mock`/`patch`). This proves the
   provider's own Python API (`materialize`/`observe`/`actuate`/`verify`/
   `checkpoint`/`restore`/`teardown`) behaves correctly given its inputs.

2. **A real episode script** (`scripts/run_<name>_episode.py`, mirroring
   `scripts/run_dev_portfolio_episode.py`'s shape: materialize -> observe/act
   -> verify -> teardown -> `write_ocel_log`) that actually runs end-to-end
   against the real `GymAct` kernel and commits a real OCEL 2.0 log to
   `reports/ocel/<name>/episode.ocel.json`. This proves the gym was actually
   *actuated* through the kernel's real receipt/OCEL machinery, not just
   unit-tested in isolation.

**Why both are required, stated explicitly so it isn't lost again:**
`tests/test_ocel_standing.py`'s own module docstring already makes this
point precisely -- "a provider's own unit tests can legitimately pass while
proving only that the provider's Python API behaves correctly given its
inputs... it says nothing about whether a real end-to-end episode was
actually run and independently verified." A green pytest run alone is
**not** sufficient standing for a gym in this repo. `reports/ocel/` is where
that second, independent proof lives, and `tests/test_ocel_standing.py`
re-derives standing directly from those logs, not from any script's own
summary.

### Reference pattern

`dev_portfolio` (`src/gymact/gyms/dev_portfolio.py`,
`tests/gyms/test_dev_portfolio_unit.py`,
`scripts/run_dev_portfolio_episode.py`,
`reports/ocel/dev-portfolio/episode.ocel.json`) is the reference pair for a
READ-only gym. `togaf` is the reference pair with an `xfail`-documented gap
(see `tests/test_ocel_standing.py`'s `_ACT_REASON_KERNEL_GAP_SUBJECTS`/
`_NO_ACT_CAPABILITY_SUBJECTS`) for gyms that cannot yet reach full `act`
standing for a real, named reason -- name the gap explicitly with
`pytest.mark.xfail(strict=True, reason=...)`, don't silently omit coverage.

### When live infrastructure is genuinely unavailable

Gyms backed by real infrastructure (a Kubernetes cluster, a local Docker
daemon, an external MCP benchmark server) MUST fail closed, not degrade
silently, when that infrastructure is absent -- see
`gymact.standing.require_standing` and the `GYMACT_ALLOW_DEGRADED_STANDINGS`
env var pattern already used by `kubernetes_reconciliation.py` and
`terraform_docker_apply.py`'s test collection. Never substitute a mock for
the real collaborator to make CI green; a named, loud skip/refusal is the
correct outcome when the real dependency genuinely isn't reachable.

## Origin of this document

Written 2026-08 closing an ecosystem-wide FMEA+RCA finding: 27 of 30 gyms
had real pytest coverage but no episode script and no OCEL log, because no
document stated that both were required -- `docs/integrations/consumer-setup.md`
is scoped to external integrators, not internal gym authors, and no
`CONTRIBUTING.md` existed at all. `dev_portfolio`'s test landed reactively,
in a later commit than the gym itself, after an earlier audit named the gap
-- not because a convention was already being followed. This file is that
convention, made explicit and durable.
