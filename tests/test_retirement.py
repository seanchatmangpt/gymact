from __future__ import annotations

from gymact.compileout import (
    RecipeIdentity,
    admit_compiled_recipe,
    compile_recipe,
)
from gymact.intelligence import CompileOutObservation
from gymact.models import Standing
from gymact.retirement import (
    ResidualWorkProfile,
    RetirementDisposition,
    evaluate_retirement,
    retirement_receipt,
)


def identity() -> RecipeIdentity:
    return RecipeIdentity(
        problem_identity="problem-1",
        environment_identity="environment-1",
        authority_class="bounded-write",
        policy_revision="policy-v1",
        verifier_ref="verifier-v1",
        action_ref="capability-v1",
        input_contract_digest="sha256:input",
    )


def recipe(receipts: tuple[str, ...] = ("r1", "r2")):
    return compile_recipe(
        identity(),
        candidate_ref="candidate:deterministic-v1",
        source_receipt_refs=receipts,
    )


def compiled_observation(**updates) -> CompileOutObservation:
    values = {
        "cold_model_tokens": 1000,
        "hot_model_tokens": 0,
        "cold_cost": 5.0,
        "hot_cost": 0.1,
        "cold_wall_time_s": 10.0,
        "hot_wall_time_s": 0.5,
        "authority_preserved": True,
        "verification_preserved": True,
        "cold_receipt_ref": "cold-receipt",
        "hot_receipt_ref": "hot-receipt",
    }
    values.update(updates)
    return CompileOutObservation(**values)


def low_residual() -> ResidualWorkProfile:
    return ResidualWorkProfile(
        exception_share=0.05,
        exception_effort_multiplier=1.0,
        ordinary_review_multiplier=0.01,
        rework=0.01,
        automation_support=0.01,
        baseline_overhead=0.0,
    )


def test_exact_verified_hot_path_retires_general_llm_from_recurring_class() -> None:
    compiled = recipe()
    admission = admit_compiled_recipe(compiled, identity())

    decision = evaluate_retirement(
        compiled,
        admission,
        compiled_observation(),
        low_residual(),
        information_sufficient=True,
        max_residual_work_ratio=0.10,
    )

    assert decision.disposition is RetirementDisposition.RETIRE_GENERAL_LLM
    assert decision.standing is Standing.ALIVE
    assert decision.general_llm_required is False
    assert decision.deterministic_candidate_ref == "candidate:deterministic-v1"
    assert decision.reason == "EXACT_RECURRING_PATH_COMPILED_OUT"


def test_evidence_ceiling_retains_general_llm_even_with_zero_token_hot_path() -> None:
    compiled = recipe()
    admission = admit_compiled_recipe(compiled, identity())

    decision = evaluate_retirement(
        compiled,
        admission,
        compiled_observation(),
        low_residual(),
        information_sufficient=False,
        max_residual_work_ratio=0.10,
    )

    assert decision.disposition is RetirementDisposition.RETAIN_GENERAL_LLM
    assert decision.standing is Standing.BLOCKED
    assert decision.general_llm_required is True
    assert decision.reason == "EVIDENCE_CEILING"


def test_compileout_must_preserve_authority_and_verification() -> None:
    compiled = recipe()
    admission = admit_compiled_recipe(compiled, identity())
    observation = compiled_observation(verification_preserved=False)

    decision = evaluate_retirement(
        compiled,
        admission,
        observation,
        low_residual(),
        information_sufficient=True,
        max_residual_work_ratio=0.10,
    )

    assert observation.compiled_out is False
    assert decision.disposition is RetirementDisposition.RETAIN_GENERAL_LLM
    assert decision.reason == "COMPILE_OUT_NOT_PROVEN"


def test_insufficient_recurrent_receipts_stays_in_shadow() -> None:
    compiled = recipe(("r1",))
    admission = admit_compiled_recipe(compiled, identity())

    decision = evaluate_retirement(
        compiled,
        admission,
        compiled_observation(),
        low_residual(),
        information_sufficient=True,
        max_residual_work_ratio=0.10,
    )

    assert decision.disposition is RetirementDisposition.SHADOW_DETERMINISTIC
    assert decision.general_llm_required is True
    assert decision.reason == "INSUFFICIENT_RECURRENT_RECEIPTS"


def test_residual_work_above_threshold_stays_in_shadow() -> None:
    compiled = recipe()
    admission = admit_compiled_recipe(compiled, identity())
    residual = ResidualWorkProfile(
        exception_share=0.30,
        exception_effort_multiplier=1.0,
        ordinary_review_multiplier=0.20,
        rework=0.10,
        automation_support=0.05,
        baseline_overhead=0.0,
    )

    decision = evaluate_retirement(
        compiled,
        admission,
        compiled_observation(),
        residual,
        information_sufficient=True,
        max_residual_work_ratio=0.10,
    )

    assert residual.ratio > 0.10
    assert decision.disposition is RetirementDisposition.SHADOW_DETERMINISTIC
    assert decision.reason == "RESIDUAL_WORK_ABOVE_RETIREMENT_THRESHOLD"


def test_stale_recipe_identity_retains_general_llm() -> None:
    compiled = recipe()
    current = identity().model_copy(update={"policy_revision": "policy-v2"})
    admission = admit_compiled_recipe(compiled, current)

    decision = evaluate_retirement(
        compiled,
        admission,
        compiled_observation(),
        low_residual(),
        information_sufficient=True,
        max_residual_work_ratio=0.10,
    )

    assert admission.admitted is False
    assert admission.standing is Standing.STALE
    assert decision.disposition is RetirementDisposition.RETAIN_GENERAL_LLM
    assert decision.standing is Standing.STALE


def test_retirement_receipt_is_deterministic_and_authority_free() -> None:
    compiled = recipe()
    observation = compiled_observation()
    admission = admit_compiled_recipe(compiled, identity())
    decision = evaluate_retirement(
        compiled,
        admission,
        observation,
        low_residual(),
        information_sufficient=True,
        max_residual_work_ratio=0.10,
    )

    first = retirement_receipt(
        compiled,
        decision,
        observation,
        information_sufficient=True,
    )
    second = retirement_receipt(
        compiled,
        decision,
        observation,
        information_sufficient=True,
    )

    assert first.receipt_digest == second.receipt_digest
    assert first.decision.general_llm_required is False
    payload = first.model_dump(mode="json")
    assert "authority_ref" not in payload
    assert "principal" not in payload


def test_retirement_threshold_and_minimum_receipts_are_explicit() -> None:
    compiled = recipe()
    admission = admit_compiled_recipe(compiled, identity())

    import pytest

    with pytest.raises(ValueError, match="MAX_RESIDUAL_WORK_RATIO"):
        evaluate_retirement(
            compiled,
            admission,
            compiled_observation(),
            low_residual(),
            information_sufficient=True,
            max_residual_work_ratio=1.1,
        )

    with pytest.raises(ValueError, match="MINIMUM_SOURCE_RECEIPTS"):
        evaluate_retirement(
            compiled,
            admission,
            compiled_observation(),
            low_residual(),
            information_sufficient=True,
            max_residual_work_ratio=0.10,
            minimum_source_receipts=1,
        )
