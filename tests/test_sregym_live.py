"""Chicago-style: a real GymAct episode driven against a real SREGym
checkout, real Kubernetes cluster, and the real upstream `uv run python
main.py` conductor -- not simulated.

Closes the real gap named in the swegym-follow-up capability-coverage audit:
`sregym.run` -- the ONE capability this first-class provider exposes -- had
no test exercising its real `actuate()` success path at all (only
materialize/classification/CSV-parsing/checkpoint-refusal are covered in
`tests/test_sregym.py`, per that file's own explicit docstring: "A real
SREGym episode remains a separate standing and is validated with the
procedure in docs/integrations/sregym.md").

Per `gymact.standing.require_standing`, the real thing is the default: if no
real SREGym checkout (a real `$SREGYM_ROOT` with `main.py` + `pyproject.toml`,
matching `SREGymProvider.materialize`'s own validation) or required binary
(`git`/`uv`/`docker`/`kubectl`/`helm`, matching `sregym.py`'s own
`_REQUIRED_BINARIES`) is present, this module FAILS unless the run
explicitly sets `GYMACT_ALLOW_DEGRADED_STANDINGS` to include
"LOCAL_GYM:sregym" (or "*") -- a skip here is something a run must opt
into, never something it silently gets. Matches
`test_kubernetes_reconciliation.py`'s and `test_swegym_live.py`'s contract.

Honest note: this checkout has git/uv/docker/kubectl/helm all present, but
no real SREGym checkout ($SREGYM_ROOT unset, no ~/SREGym or ~/sregym
directory) -- so this module is EXPECTED to fail loudly (naming the real
gap) rather than pass, unless a real checkout is supplied. That failure is
the correct, useful signal this repo's own doctrine asks for: a red/refused
module naming a real, specific, closeable gap is preferable to no test
existing at all.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from gymact.standing import require_standing

_REQUIRED_BINARIES = ("git", "uv", "docker", "kubectl", "helm")


def _binaries_available() -> bool:
    return all(shutil.which(binary) is not None for binary in _REQUIRED_BINARIES)


def _real_checkout_root() -> Path | None:
    """Mirror `SREGymProvider.materialize`'s own real checkout validation exactly:
    a directory with both `main.py` and `pyproject.toml` present."""
    candidates = [os.environ.get("SREGYM_ROOT")]
    for candidate in candidates:
        if not candidate:
            continue
        root = Path(candidate).expanduser()
        if (root / "main.py").is_file() and (root / "pyproject.toml").is_file():
            return root
    return None


def _cluster_reachable() -> bool:
    if shutil.which("kubectl") is None:
        return False
    try:
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


_ROOT = _real_checkout_root()

require_standing(
    "LOCAL_GYM:sregym",
    available=_binaries_available() and _cluster_reachable() and _ROOT is not None,
    reason=(
        "no real SREGym checkout at $SREGYM_ROOT (needs main.py + pyproject.toml), "
        "or one of git/uv/docker/kubectl/helm is missing, or no reachable Kubernetes "
        "cluster on the current kubeconfig context -- set SREGYM_ROOT to a real "
        "SREGym/SREGym checkout and ensure a local cluster is running "
        "(`kind create cluster`, `k3d cluster create`, or `colima start --kubernetes`)"
    ),
)

from gymact import AllowListAuthorityResolver, GymAct, MaterializationIntent  # noqa: E402
from gymact.gyms.sregym import SREGYM_RUN_CAPABILITY, SREGymProvider  # noqa: E402
from gymact.models import ActuationIntent  # noqa: E402
from gymact.ocel import validate_ocel_log  # noqa: E402
from gymact.process import ConformanceChecker  # noqa: E402

AUTHORITY = "urn:test:sregym-live-authority"


def _authorized_gym() -> GymAct:
    gym = GymAct(authority_resolver=AllowListAuthorityResolver({AUTHORITY}))
    gym.register_provider(SREGymProvider())
    return gym


async def test_real_sregym_conductor_run_against_a_real_checkout_and_cluster() -> None:
    """One real episode: materialize (real checkout + revision admission) ->
    act (`run`, a real DO capability that launches the real upstream `uv run
    python main.py` conductor against the real cluster) -> verify (reads the
    real upstream result CSV `sregym.py` itself parses, independent of the
    subprocess exit code alone) -> teardown."""
    gym = _authorized_gym()

    materialization = await gym.materialize(
        MaterializationIntent(
            provider="sregym",
            config={"root": str(_ROOT), "suite": "sregym-lite", "n_attempts": 1},
            authority_ref=AUTHORITY,
        )
    )
    assert materialization.accepted is True, materialization.receipt.reason
    episode_id = materialization.episode.episode_id

    outcome = await gym.act(
        ActuationIntent(
            episode_id=episode_id,
            capability=SREGYM_RUN_CAPABILITY.iri,
            payload={},
            authority_ref=AUTHORITY,
        )
    )
    assert outcome.accepted is True
    after = outcome.effect["after"] if isinstance(outcome.effect, dict) else {}
    assert after.get("attempted") is True
    assert after.get("process_returncode") == 0
    assert after.get("result_csv"), "no real upstream result CSV artifact was produced"
    assert after.get("native_results") is not None

    verification = await gym.verify(episode_id, {"attempted": True})
    assert verification.passed is True

    await gym.teardown(episode_id)

    ocel_log = gym.episode_ocel_log(episode_id)
    validate_ocel_log(ocel_log)
    events = sorted(ocel_log["events"], key=lambda e: e["time"])
    from gymact.models import Operation

    conformance = ConformanceChecker().check([Operation(e["type"]) for e in events])
    assert conformance.conformant, conformance.deviations
