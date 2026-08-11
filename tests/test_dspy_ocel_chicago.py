"""Chicago-style tests for `gymact.dspy_ocel`. No mocks: a real
`dspy.Predict` call against a real Groq-hosted LM, with a real
`DspyOcelCallback` attached, producing a real, schema-valid OCEL 2.0 log --
validated against the real vendored OCEL 2.0 JSON Schema via
`gymact.ocel.validate_ocel_log`, the same validator every other real OCEL
log in this repo is checked against.
"""

from __future__ import annotations

import importlib.util

import pytest

from gymact.standing import require_standing

require_standing(
    "LOCAL_EXTRA:dspy",
    available=importlib.util.find_spec("dspy") is not None,
    reason="the optional 'dspy' extra is not installed -- `uv sync --extra dspy`",
)

import dspy  # noqa: E402

from gymact.dspy_ocel import DspyOcelCallback, build_and_validate_dspy_ocel_log  # noqa: E402


def _groq_key_available() -> bool:
    import os

    return bool(os.environ.get("GROQ_API_KEY"))


class SimpleQA(dspy.Signature):
    """Answer a simple question."""

    question: str = dspy.InputField()
    answer: str = dspy.OutputField()


@pytest.mark.skipif(not _groq_key_available(), reason="no GROQ_API_KEY in this environment")
class TestDspyOcelCallback:
    async def test_real_lm_call_produces_a_real_schema_valid_ocel_log(self):
        callback = DspyOcelCallback(run_id="test-run-ocel-1")
        lm = dspy.LM("groq/llama-3.1-8b-instant", max_tokens=100, callbacks=[callback])
        with dspy.context(lm=lm):
            prediction = await dspy.Predict(SimpleQA).acall(question="What is 2+2?")

        assert prediction.answer  # real, non-empty LM output

        log, digest = build_and_validate_dspy_ocel_log(callback)
        assert digest  # real sha256, non-empty

        assert any(obj["type"] == "dspy_run" for obj in log["objects"])
        assert any(obj["type"] == "lm" for obj in log["objects"])
        assert any(event["type"] == "lm_call" for event in log["events"])

        lm_event = next(event for event in log["events"] if event["type"] == "lm_call")
        # Real OCEL 2.0 schema constraint: every attribute value must be a
        # literal string, regardless of the underlying Python type.
        for attribute in lm_event["attributes"]:
            assert isinstance(attribute["value"], str)

    async def test_a_call_that_started_before_the_callback_attached_is_skipped_not_crashed(self):
        # Real proof `_end` without a matching `_start` degrades gracefully
        # (returns, no event emitted) rather than raising -- exercised
        # directly since provoking this via a real timing race in a live
        # LM call would be flaky.
        callback = DspyOcelCallback(run_id="test-run-ocel-2")
        callback.on_lm_end(call_id="never-started", outputs={"answer": "x"}, exception=None)
        log, _ = build_and_validate_dspy_ocel_log(callback)
        assert log["events"] == []
