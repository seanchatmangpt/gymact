"""Log-only verifier-verdict re-derivation — distinct from `gymact.replay`.

`gymact.replay.replay_ledger` means ledger/chain-hash *integrity*
verification (`ReplayMode.EVIDENCE_REPLAY`/`LIVE_REEXECUTION`) — it never
re-derives a domain verifier's pass/fail from a log, and its own docstring
says so ("replay validates evidence and never silently actuates"). This
module is the distinctly-named capability that collision was missing,
named per `docs/jira/v26.8.12/cloud-cert-wbpr-prd.md` FR4 (Correction 5):
given a real, already-captured observation (the exact dict a domain's
`verify()` would compute its own pass/fail from), reproduce that verdict
with no subprocess and no live poll.

Only domains whose verifier already computes its verdict purely from state
already captured at actuation time (no live poll) can be truly replayed
from a log alone. `gymact.gyms.terraform_plan.TerraformPlanEnvironment.
verify()` is exactly this shape: its `expected == {}` predicate reads only
`init_attempted`/`init_returncode`/`plan_attempted`/`plan_timed_out`/
`plan_returncode`/`plan_stdout` — fields already written into `self._state`
by `materialize_real_init()`/`actuate()`, never re-derived from a fresh
subprocess call inside `verify()` itself. `terraform_plan_verify_from_log`
below is that exact predicate, factored out so both the live environment
and a pure log-replay path share one implementation instead of two that
could silently drift apart.

Domains whose verifier polls *live* external state (Kubernetes, the
`*goat` bridges) cannot be added here with the same guarantee — see
`docs/jira/v26.8.12/cloud-cert-wbpr-implementation-inventory.md`'s FR4 row
for why those need a materially weaker "snapshot-consistency" mode instead,
not attempted in this module.
"""

from __future__ import annotations

from typing import Any


def terraform_plan_verify_from_log(observed: dict[str, Any]) -> bool:
    """The exact predicate `TerraformPlanEnvironment.verify()` uses for
    `expected == {}` — reproduced here so it is callable against a stored
    observation dict (e.g. an OCEL event's `after`/observed attributes)
    with no subprocess, no live Terraform/tofu binary, no working
    directory. Kept in sync with `terraform_plan.py::verify()` by having
    that method call this function directly, not a parallel copy.
    """
    init_ok = observed.get("init_attempted") is True and observed.get("init_returncode") == 0
    plan_ran = (
        observed.get("plan_attempted") is True
        and observed.get("plan_timed_out") is False
        and observed.get("plan_returncode") is not None
        and bool(observed.get("plan_stdout")) is True
    )
    return init_ok and plan_ran
