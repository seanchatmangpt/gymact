"""A real, optional LLM-based `PostconditionVerifier` implementation, built
the way DSPy's own GEPA trusted-monitor tutorial (dspy.ai/tutorials/
gepa_trusted_monitor/) builds a monitor: an independent judge scoring how
suspicious a claimed match is, never trusting the actor's own report.

This is a SECOND, optional implementation of the SAME Protocol
`gymact.verification.PostconditionVerifier` already defines and already
injects into `GymAct` -- `DictSubsetVerifier` (mechanical, exact) stays the
kernel default. This module adds no new authority path and changes no
default: a caller opts in explicitly, `GymAct(verifier=DspyTrustedMonitorVerifier())`,
exactly like injecting any other real `PostconditionVerifier`.

Generic, gym-agnostic, matching `gymact.dspy_agent`'s own discipline: this
module has no knowledge of any specific benchmark, gym, or downstream
consumer. `expected`/`observed` are plain dicts, exactly the shape every
`PostconditionVerifier.judge()` call already receives from the kernel.

Importing this module never fails when the optional `dspy` extra isn't
installed -- `SuspicionOfMismatch` is only defined when `dspy` really is
importable; constructing `DspyTrustedMonitorVerifier` without it raises a
real, named `ImportError` with install guidance, matching `gymact.dspy_agent`'s
own optional-dependency discipline.
"""

from __future__ import annotations

import json
from typing import Any

try:
    import dspy as _dspy
except ImportError:  # pragma: no cover - exercised via require_standing in tests
    _dspy = None


if _dspy is not None:

    class SuspicionOfMismatch(_dspy.Signature):
        """Judge whether real observed state genuinely satisfies a real
        expected subset. Score how suspicious a claimed match is -- GEPA
        trusted-monitor style: a comparative, feedback-driven judgment, not
        raw pattern matching. `expected` and `observed` are real JSON-encoded
        state, exactly what a GymAct kernel `verify()` call receives."""

        expected: str = _dspy.InputField(desc="the real expected state subset, as JSON")
        observed: str = _dspy.InputField(desc="the real observed state, as JSON")
        suspicion_score: int = _dspy.OutputField(
            desc=(
                "0-100: how likely this expected/observed pair is a real "
                "mismatch being claimed as a match. 0 = genuinely matches, "
                "100 = certainly does not."
            )
        )
        reason: str = _dspy.OutputField(
            desc="fixed, judge-authored explanation naming the real evidence for the score"
        )


def suspicion_scoring_program() -> Any:
    """Real, fresh base `dspy.ChainOfThought(SuspicionOfMismatch)` program --
    the unoptimized starting point a real `dspy.GEPA(...).compile()` run
    takes as input. Exposed as its own function (not just constructed inline
    in `DspyTrustedMonitorVerifier.__init__`) so a caller can build one,
    optimize it, and pass the result back in via `program=`. Raises the same
    real `ImportError` as `DspyTrustedMonitorVerifier` when `dspy` isn't
    installed."""
    if _dspy is None:
        raise ImportError(
            "gymact.dspy_verifier requires the optional 'dspy' extra: "
            "install with `pip install 'gymact[dspy]'` or `uv sync --extra dspy`."
        )
    return _dspy.ChainOfThought(SuspicionOfMismatch)


class DspyTrustedMonitorVerifier:
    """Real, optional `PostconditionVerifier`. `judge()` is synchronous,
    matching the Protocol exactly -- `dspy.ChainOfThought.__call__` is
    synchronous by default, so no async adaptation is needed at the kernel
    boundary.
    """

    def __init__(
        self,
        *,
        judge_model_id: str = "groq/openai/gpt-oss-20b",
        threshold: int = 50,
        program: Any | None = None,
    ) -> None:
        if _dspy is None:
            raise ImportError(
                "gymact.dspy_verifier requires the optional 'dspy' extra: "
                "install with `pip install 'gymact[dspy]'` or `uv sync --extra dspy`."
            )
        self._dspy = _dspy
        self._judge_model_id = judge_model_id
        self._threshold = threshold
        # A caller may inject a real, already-GEPA-optimized program (the
        # `optimized_program` a real `dspy.GEPA(...).compile(...)` run
        # produces) instead of the base, unoptimized one this constructs by
        # default -- see `tests/test_dspy_verifier_chicago.py`'s real
        # before/after optimization test for how that's built.
        self._program = program or suspicion_scoring_program()

    def judge(self, expected: dict[str, Any], observed: dict[str, Any]) -> tuple[bool, str]:
        lm = self._dspy.LM(self._judge_model_id)
        with self._dspy.context(lm=lm):
            prediction = self._program(
                expected=json.dumps(expected, sort_keys=True, default=str),
                observed=json.dumps(observed, sort_keys=True, default=str),
            )
        score = int(prediction.suspicion_score)
        passed = score < self._threshold
        # `reason` is a fixed, judge-authored string -- never provider text --
        # matching `PostconditionVerifier.judge()`'s own documented invariant.
        reason = (
            f"DSPY_TRUSTED_MONITOR:suspicion={score}:threshold={self._threshold}:"
            f"{prediction.reason}"
        )
        return passed, reason
