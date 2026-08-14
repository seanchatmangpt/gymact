from __future__ import annotations

from gymact.dspy_ggen import GgenPredict
from gymact.ggen_agent import CallableGgenManufacturer, GgenAgentRuntime, GgenAgentSpec


class ExampleSignature:
    input_fields = {"question": object()}
    output_fields = {"answer": object()}


def _runtime() -> GgenAgentRuntime:
    spec = GgenAgentSpec(
        agent_id="predict",
        role_ref="urn:test:role:predict",
        planner_ref="urn:test:planner:deterministic",
        objective_ref="urn:test:objective:answer",
        observation_projection_ref="urn:test:projection:inputs",
        action_projection_ref="urn:test:projection:outputs",
        pack_ref="urn:test:pack:ggen",
        observation_keys=("question",),
        output_keys=("answer",),
    )

    def manufacture(*, spec, observation, inputs):
        del spec, inputs
        return {"answer": observation["question"].upper()}

    return GgenAgentRuntime(
        (spec,),
        CallableGgenManufacturer({"predict": manufacture}),
    )


async def test_dspy_signature_is_manufactured_without_an_lm() -> None:
    predict = GgenPredict(ExampleSignature, runtime=_runtime(), agent_id="predict")

    prediction = await predict.acall(question="manufacture")

    assert prediction.answer == "MANUFACTURE"
    assert getattr(prediction, "llm_calls", getattr(prediction, "_gymact_llm_calls", 0)) == 0


async def test_signature_rejects_unknown_input_instead_of_prompting() -> None:
    predict = GgenPredict(ExampleSignature, runtime=_runtime(), agent_id="predict")

    try:
        await predict.acall(question="ok", invented="not-in-signature")
    except ValueError as exc:
        assert str(exc).startswith("DSPY_GGEN_INPUT_UNKNOWN")
    else:
        raise AssertionError("unknown DSPy/ggen input must be refused")
