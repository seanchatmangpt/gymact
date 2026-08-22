from __future__ import annotations

from rdflib import RDF, URIRef
from rdflib.namespace import DCTERMS, PROV, SKOS

from gymact.envharness import Contract, ContractRule, HarnessAction, HarnessSpec, Stage, TaskSpec
from gymact.envharness_semantic import (
    DQV,
    EARL,
    ODRL,
    PAPER,
    PPLAN,
    SOSA,
    envrigger_graph,
    harness_graph,
)
from gymact.envrigger import (
    CandidateEvaluation,
    Diagnosis,
    EnvRiggerResult,
    ValidationMetrics,
)
from gymact.models import Standing

SET = "urn:gymact:memory:capability:set"


def test_harness_projection_uses_public_predicates_and_local_abox_skos_only() -> None:
    spec = HarnessSpec(
        identifier="urn:gymact:envharness:test",
        stages=(Stage(actions=(HarnessAction(capability=SET, payload={"key": "x", "value": 1}),)),),
        contracts=(
            Contract(
                rules=(ContractRule(capability=SET, effect="deny", reason="TEST_DENY"),),
                hide_observation_keys=frozenset({"secret"}),
            ),
        ),
    )
    task = TaskSpec(provider="memory", goal={"x": 1}, harness=spec)

    graph = harness_graph(spec, tasks=(task, task))

    assert (URIRef(spec.identifier), RDF.type, PPLAN.Plan) in graph
    assert (URIRef(spec.identifier), RDF.type, PROV.Plan) in graph
    assert (URIRef(spec.identifier), DCTERMS.source, PAPER) in graph
    assert (URIRef(spec.identifier), DCTERMS.identifier, None) in graph
    assert any(predicate == SOSA.usedProcedure for _, predicate, _ in graph)
    assert any(predicate == ODRL.prohibition for _, predicate, _ in graph)
    assert any(obj == SKOS.Concept for _, _, obj in graph)
    assert not any(str(predicate).startswith("urn:gymact:") for _, predicate, _ in graph)


def test_envrigger_projection_records_validation_as_prov_earl_and_dqv() -> None:
    diagnosis = Diagnosis(
        rollout_count=2,
        success_rate=0.5,
        mean_steps=3.0,
        repeated_capability=None,
        max_consecutive_repeat=1,
        failure_reasons=(),
        signal="MIXED_SUCCESS_OBSERVED",
    )
    harness = HarnessSpec(identifier="urn:gymact:envharness:candidate")
    evaluation = CandidateEvaluation(
        revision=1,
        harness=harness,
        diagnosis=diagnosis,
        validation=ValidationMetrics(
            rollouts=2,
            solved=1,
            success_rate=0.5,
            mean_steps=3.0,
            fresh_rollouts=True,
        ),
        disposition="ACCEPT",
        reason="CANDIDATE_SOLVABLE_AND_CHALLENGING",
    )
    result = EnvRiggerResult(
        standing=Standing.ALIVE,
        baseline=(),
        baseline_diagnosis=diagnosis,
        evaluations=(evaluation,),
        accepted_harness=harness,
        reason="CANDIDATE_SOLVABLE_AND_CHALLENGING",
    )

    graph = envrigger_graph(result, run_iri="urn:gymact:envrigger:run:test")

    assert any(obj == EARL.Assertion for _, _, obj in graph)
    assert any(predicate == EARL.outcome and obj == EARL.passed for _, predicate, obj in graph)
    assert any(obj == PROV.Activity for _, _, obj in graph)
    assert any(predicate == DQV.hasQualityMeasurement for _, predicate, _ in graph)
    assert any(obj == DQV.QualityMeasurement for _, _, obj in graph)
    assert not any(str(predicate).startswith("urn:gymact:") for _, predicate, _ in graph)
