from __future__ import annotations

import pytest

from gymact.gdmcp import (
    GdmcpRefusal,
    SREGYM_LITE_PROBLEMS,
    SREGYM_RUN_KUBECTL,
    SREGYM_SUBMIT_DIAGNOSIS,
    SREGYM_SUBMIT_MITIGATION,
    SREGYM_UPSTREAM_REVISION,
    compile_sregym_solution,
    known_sregym_programs,
    sregym_lite_coverage,
)


def _compile(problem_id: str = "wrong_dns_policy_astronomy_shop"):
    return compile_sregym_solution(
        problem_id,
        episode_id="urn:gymact:episode:gdmcp-test",
        upstream_revision=SREGYM_UPSTREAM_REVISION,
        bindings={"namespace": "sregym-test"},
        authority_ref="urn:gymact:authority:test",
    )


def test_gdmcp_compiles_known_solution_without_llm_or_tool_selection():
    compiled = _compile()

    assert compiled.llm_calls == 0
    assert compiled.problem_id == "wrong_dns_policy_astronomy_shop"
    assert compiled.upstream_revision == SREGYM_UPSTREAM_REVISION
    assert [intent.capability for intent in compiled.intents] == [
        SREGYM_SUBMIT_DIAGNOSIS,
        SREGYM_RUN_KUBECTL,
        SREGYM_RUN_KUBECTL,
        SREGYM_SUBMIT_MITIGATION,
    ]
    assert all(intent.principal == "urn:gymact:agent:gdmcp" for intent in compiled.intents)
    assert "sregym-test" in compiled.intents[1].payload["command"]


def test_same_subject_and_bindings_compile_byte_equivalent_intents():
    first = _compile()
    second = _compile()

    assert first.program_digest == second.program_digest
    assert [item.model_dump(mode="json") for item in first.intents] == [
        item.model_dump(mode="json") for item in second.intents
    ]


def test_unknown_problem_is_novelty_refusal_not_llm_fallback():
    with pytest.raises(GdmcpRefusal, match="REFUSED:GDMCP_SOLUTION_UNKNOWN"):
        _compile("problem_that_does_not_exist")


def test_upstream_revision_drift_is_refused():
    with pytest.raises(GdmcpRefusal, match="REFUSED:GDMCP_SUBJECT_DRIFT"):
        compile_sregym_solution(
            "wrong_dns_policy_astronomy_shop",
            episode_id="urn:gymact:episode:gdmcp-test",
            upstream_revision="deadbeef",
            bindings={"namespace": "sregym-test"},
        )


@pytest.mark.parametrize(
    "bindings,code",
    [
        ({}, "GDMCP_BINDING_SET_MISMATCH"),
        (
            {"namespace": "sregym-test", "extra": "surprise"},
            "GDMCP_BINDING_SET_MISMATCH",
        ),
        ({"namespace": "prod;rm-rf"}, "GDMCP_INVALID_NAMESPACE"),
    ],
)
def test_runtime_binding_surface_fails_closed(bindings, code):
    with pytest.raises(GdmcpRefusal, match=f"REFUSED:{code}"):
        compile_sregym_solution(
            "wrong_dns_policy_astronomy_shop",
            episode_id="urn:gymact:episode:gdmcp-test",
            upstream_revision=SREGYM_UPSTREAM_REVISION,
            bindings=bindings,
        )


def test_all_authored_programs_are_source_grounded_and_zero_llm():
    programs = known_sregym_programs()
    assert programs
    for program in programs:
        assert program.llm_calls == 0
        assert program.upstream_revision == SREGYM_UPSTREAM_REVISION
        assert program.source_refs
        assert all(
            ref.startswith(f"SREGym/SREGym@{SREGYM_UPSTREAM_REVISION}:")
            for ref in program.source_refs
        )
        assert all(step.source_ref for step in program.steps)


def test_sregym_lite_coverage_is_explicit_not_overclaimed():
    coverage = sregym_lite_coverage()
    authored = {program.problem_id for program in known_sregym_programs()}

    assert len(SREGYM_LITE_PROBLEMS) == 21
    assert authored <= set(SREGYM_LITE_PROBLEMS)
    assert coverage.admitted_subjects == 21
    assert coverage.compiled_subjects == len(authored)
    assert coverage.compiled_subjects == 2
    assert coverage.deterministic_projection_ratio == pytest.approx(2 / 21)
