from __future__ import annotations

from rdflib import RDF, URIRef

from gymact import harness_if as hif
from gymact import harness_if_semantic as sem


def make_rule() -> hif.Constraint:
    return hif.Constraint(
        rule_id="r1",
        text="Run the verification command before completion.",
        family=hif.RuleFamily.WORKFLOW,
        modality=hif.Modality.REQUIRE,
        prior=hif.Prior.AGAINST,
        prior_lineage=hif.PriorLineage.ZERO_INJECTION,
        observability=hif.Observability.BEHAVIORAL,
        verifiability=hif.Verifiability.DETERMINISTIC,
        universality=hif.Universality.CROSS_CODING,
        scoring_method=hif.ScoringMethod.COMMAND_OUTPUT,
        severity=hif.Severity.MUST,
        surface_fit={hif.Surface.PROJECT_FILE: hif.SurfaceFit.HIGH},
        surface_variants={
            hif.Surface.PROJECT_FILE: "Run the verification command before completion."
        },
    )


def test_constraint_projection_uses_public_odrl_and_prov_terms():
    constraint = make_rule()
    graph = sem.constraint_graph(constraint)
    rule_ref = sem.HIF["rule-r1"]
    assert (rule_ref, RDF.type, sem.ODRL.Rule) in graph
    assert (rule_ref, RDF.type, sem.PROV.Entity) in graph
    assert (rule_ref, sem.DCTERMS.source, sem.PAPER) in graph
    assert not any(
        str(object_ref).startswith("urn:gymact:harness-if:class-")
        for _, predicate, object_ref in graph
        if predicate == RDF.type
    )


def test_prior_projection_is_a_sosa_observation():
    prior = hif.PriorEvidence(
        rule_id="r1",
        prior=hif.Prior.AGAINST,
        lineage=hif.PriorLineage.ZERO_INJECTION,
        probes=9,
        consensus_count=7,
        reason="ZERO_INJECTION_CONSENSUS",
    )
    graph = sem.prior_graph(prior)
    observation = sem.HIF["prior-observation-r1"]
    assert (observation, RDF.type, sem.SOSA.Observation) in graph
    assert any(subject == observation and predicate == sem.SOSA.hasResult for subject, predicate, _ in graph)


def test_verdict_projection_is_an_earl_assertion():
    verdict = hif.RuleVerdict(
        agent_id="agent-a",
        item_id="item-1",
        round_id=0,
        rule_id="r1",
        surface=hif.Surface.PROJECT_FILE,
        status=hif.VerdictStatus.PASS,
        method=hif.ScoringMethod.COMMAND_OUTPUT,
        reason="verified",
        evidence_refs=("urn:test:evidence:1",),
    )
    graph = sem.verdict_graph(verdict)
    assertion = sem.HIF["assertion-agent-a-item-1-0-r1"]
    assert (assertion, RDF.type, sem.EARL.Assertion) in graph
    assert (assertion, sem.PROV.used, URIRef("urn:test:evidence:1")) in graph


def test_metrics_and_snapshot_projection_use_dqv_and_prov_bundle():
    constraint = make_rule()
    verdict = hif.RuleVerdict(
        agent_id="agent-a",
        item_id="item-1",
        round_id=0,
        rule_id="r1",
        surface=hif.Surface.PROJECT_FILE,
        status=hif.VerdictStatus.PASS,
        method=hif.ScoringMethod.COMMAND_OUTPUT,
        reason="verified",
    )
    snapshot = hif.EvaluationSnapshot(library=(constraint,), verdicts=(verdict,))
    graph = sem.snapshot_graph(snapshot, run_iri="urn:test:harness-if:run")
    bundle = sem.HIF[f"snapshot-{snapshot.snapshot_fingerprint}"]
    assert (bundle, RDF.type, sem.PROV.Bundle) in graph
    assert any(object_ref == sem.DQV.QualityMeasurement for _, _, object_ref in graph)
