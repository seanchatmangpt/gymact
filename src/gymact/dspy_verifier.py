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

from typing import Any

try:
    import dspy as _dspy
except ImportError:  # pragma: no cover - exercised via require_standing in tests
    _dspy = None


if _dspy is not None:

    class SuspicionOfMismatch(_dspy.Signature):
        """Score how suspicious a claimed expected/observed match is. A
        genuine match scores near 0; a real mismatch dressed up as a match
        scores near 100. Compare field by field -- do not just eyeball
        overall similarity."""

        # `dict[str, Any]` is a real, known, NOT-fully-resolved limitation
        # here -- flagged honestly, not accommodated as a design choice.
        # `Any` accepts everything, so Pydantic cannot actually validate
        # against it; a prior version of this docstring claimed "structural
        # typing catches a shape mismatch," which is false for `Any` as the
        # value type (confirmed live: a real `dspy.predict.predict` WARNING
        # already fires -- "Type mismatch for field 'expected'...
        # incompatible" -- against a genuinely nested real test fixture,
        # `{"nested": {"a": 1}}`, even with this exact annotation already in
        # place). The real fix -- a proper recursive JSON-value type
        # (`str | int | float | bool | None | list[JSONValue] |
        # dict[str, JSONValue]`), which WOULD be genuinely structural and
        # matches this field's real domain (arbitrary, possibly-nested
        # state; a flat scalar-only dict would be dishonest to that real
        # domain, not just verbose) -- was attempted and reverted: it
        # crashes Pydantic's schema generation inside `dspy.Signature`'s own
        # metaclass with infinite recursion. Left as a real, named, open gap
        # rather than a claimed non-benefit.
        expected: dict[str, Any] = _dspy.InputField(
            desc="real expected state subset the actor claims is satisfied"
        )
        observed: dict[str, Any] = _dspy.InputField(
            desc="real, independently-read current state"
        )
        # Real ge/le constraints (not just prose in `desc`), matching
        # dspy.ai's own GEPA trusted-monitor tutorial's suspicion_score
        # field exactly -- DSPy surfaces a clear validation warning if the
        # LM's output falls outside these bounds instead of silently
        # accepting an out-of-range score.
        suspicion_score: int = _dspy.OutputField(
            desc="0 = genuinely matches; 100 = certainly does not", ge=0, le=100
        )
        reason: str = _dspy.OutputField(
            desc="one sentence naming the specific field(s) that do or don't match"
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
        lm = self._dspy.LM(self._judge_model_id, max_tokens=16000)
        with self._dspy.context(lm=lm):
            prediction = self._program(expected=expected, observed=observed)
        score = int(prediction.suspicion_score)
        passed = score < self._threshold
        # `reason` is a fixed, judge-authored string -- never provider text --
        # matching `PostconditionVerifier.judge()`'s own documented invariant.
        reason = (
            f"DSPY_TRUSTED_MONITOR:suspicion={score}:threshold={self._threshold}:"
            f"{prediction.reason}"
        )
        return passed, reason
