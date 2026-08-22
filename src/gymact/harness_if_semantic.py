"""Public-ontology projection for GymAct's Harness-IF evaluation profile.

No GymAct-owned TBox is introduced. Local IRIs are ABox resources or SKOS
concepts only; public PROV-O, P-PLAN, ODRL, SOSA, EARL, DQV and DCTERMS terms
carry the semantics.
"""

from __future__ import annotations

from typing import Final

from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS, PROV, SKOS

from gymact.harness_if import (
    PAPER_IRI,
    BenchmarkItem,
    CohortMetrics,
    Constraint,
    EvaluationSnapshot,
    PriorEvidence,
    RuleVerdict,
    VerdictStatus,
)

PPLAN: Final = Namespace("http://purl.org/net/p-plan#")
ODRL: Final = Namespace("http://www.w3.org/ns/odrl/2/")
SOSA: Final = Namespace("http://www.w3.org/ns/sosa/")
EARL: Final = Namespace("http://www.w3.org/ns/earl#")
DQV: Final = Namespace("http://www.w3.org/ns/dqv#")
HIF: Final = Namespace("urn:gymact:harness-if:")
PAPER = URIRef(PAPER_IRI)


def _concept(graph: Graph, iri: URIRef, label: str) -> URIRef:
    graph.add((iri, RDF.type, SKOS.Concept))
    graph.add((iri, SKOS.prefLabel, Literal(label)))
    graph.add((iri, DCTERMS.source, PAPER))
    return iri


def _metric(graph: Graph, name: str, label: str) -> URIRef:
    iri = HIF[f"metric-{name}"]
    graph.add((iri, RDF.type, DQV.Metric))
    graph.add((iri, DCTERMS.title, Literal(label)))
    graph.add((iri, DCTERMS.source, PAPER))
    return iri


def constraint_graph(constraint: Constraint) -> Graph:
    graph = Graph()
    rule = HIF[f"rule-{constraint.rule_id}"]
    graph.add((rule, RDF.type, ODRL.Rule))
    graph.add((rule, RDF.type, PROV.Entity))
    graph.add((rule, DCTERMS.identifier, Literal(constraint.rule_id)))
    graph.add((rule, DCTERMS.description, Literal(constraint.text)))
    graph.add((rule, DCTERMS.source, PAPER))
    for axis, value in (
        ("family", constraint.family.value),
        ("modality", constraint.modality.value),
        ("prior", constraint.prior.value),
        ("observability", constraint.observability.value),
        ("verifiability", constraint.verifiability.value),
        ("universality", constraint.universality.value),
        ("severity", constraint.severity.value),
        ("scoring", constraint.scoring_method.value),
    ):
        concept = _concept(graph, HIF[f"{axis}-{value}"], f"{axis}: {value}")
        graph.add((rule, DCTERMS.type, concept))
    for surface, fit in constraint.surface_fit.items():
        if fit.value == "none":
            continue
        surface_concept = _concept(
            graph, HIF[f"surface-{surface.value}"], f"surface {surface.value}"
        )
        rendering = constraint.surface_variants.get(surface)
        placement = BNode()
        graph.add((placement, RDF.type, PROV.Entity))
        graph.add((placement, PROV.specializationOf, rule))
        graph.add((placement, DCTERMS.type, surface_concept))
        graph.add((placement, DCTERMS.extent, Literal(fit.value)))
        if rendering:
            graph.add((placement, PROV.value, Literal(rendering)))
    return graph


def item_graph(item: BenchmarkItem, library: dict[str, Constraint]) -> Graph:
    graph = Graph()
    item_ref = HIF[f"item-{item.item_id}"]
    plan_ref = HIF[f"scenario-{item.scenario.scenario_id}"]
    graph.add((item_ref, RDF.type, PROV.Entity))
    graph.add((plan_ref, RDF.type, PPLAN.Plan))
    graph.add((plan_ref, RDF.type, PROV.Plan))
    graph.add((item_ref, PROV.specializationOf, plan_ref))
    graph.add((item_ref, DCTERMS.source, PAPER))
    for index, placement in enumerate(item.placements):
        if placement.rule_id not in library:
            raise ValueError(f"HARNESS_IF_UNKNOWN_ITEM_RULE:{placement.rule_id}")
        placement_ref = HIF[f"item-{item.item_id}-placement-{index}"]
        rule_ref = HIF[f"rule-{placement.rule_id}"]
        surface = _concept(
            graph,
            HIF[f"surface-{placement.surface.value}"],
            f"surface {placement.surface.value}",
        )
        graph.add((placement_ref, RDF.type, PROV.Entity))
        graph.add((placement_ref, PROV.specializationOf, rule_ref))
        graph.add((placement_ref, DCTERMS.isPartOf, item_ref))
        graph.add((placement_ref, DCTERMS.type, surface))
        graph.add((placement_ref, PROV.value, Literal(placement.rendered_text)))
    return graph


def prior_graph(prior: PriorEvidence) -> Graph:
    graph = Graph()
    obs = HIF[f"prior-observation-{prior.rule_id}"]
    rule = HIF[f"rule-{prior.rule_id}"]
    property_ref = _concept(graph, HIF["behavioral-prior"], "behavioral prior")
    graph.add((obs, RDF.type, SOSA.Observation))
    graph.add((obs, SOSA.hasFeatureOfInterest, rule))
    graph.add((obs, SOSA.observedProperty, property_ref))
    graph.add((obs, DCTERMS.source, PAPER))
    lineage = _concept(
        graph,
        HIF[f"prior-lineage-{prior.lineage.value}"],
        f"prior lineage: {prior.lineage.value}",
    )
    graph.add((obs, DCTERMS.type, lineage))
    if prior.prior is not None:
        result = BNode()
        graph.add((result, RDF.type, SOSA.Result))
        graph.add((result, PROV.value, Literal(prior.prior.value)))
        graph.add((obs, SOSA.hasResult, result))
    return graph


def verdict_graph(verdict: RuleVerdict) -> Graph:
    graph = Graph()
    assertion = HIF[
        f"assertion-{verdict.agent_id}-{verdict.item_id}-{verdict.round_id}-{verdict.rule_id}"
    ]
    result = BNode()
    graph.add((assertion, RDF.type, EARL.Assertion))
    graph.add((assertion, EARL.subject, HIF[f"agent-{verdict.agent_id}"]))
    graph.add((assertion, EARL.test, HIF[f"rule-{verdict.rule_id}"]))
    graph.add((assertion, EARL.result, result))
    graph.add((assertion, DCTERMS.source, PAPER))
    graph.add((result, RDF.type, EARL.TestResult))
    if verdict.status == VerdictStatus.PASS:
        graph.add((result, EARL.outcome, EARL.passed))
    elif verdict.status == VerdictStatus.FAIL:
        graph.add((result, EARL.outcome, EARL.failed))
    else:
        graph.add((result, EARL.outcome, EARL.untested))
    graph.add((result, DCTERMS.description, Literal(verdict.reason)))
    for evidence_ref in verdict.evidence_refs:
        graph.add((assertion, PROV.used, URIRef(evidence_ref)))
    return graph


def metrics_graph(metrics: CohortMetrics, *, run_iri: str) -> Graph:
    graph = Graph()
    run = URIRef(run_iri)
    graph.add((run, RDF.type, PROV.Activity))
    graph.add((run, DCTERMS.source, PAPER))
    metric_refs = {
        "accuracy": _metric(graph, "acc", "Harness-IF Acc"),
        "filtered_accuracy": _metric(graph, "f-acc", "Harness-IF F-Acc"),
        "discrimination_weighted_accuracy": _metric(
            graph, "dw-acc", "Harness-IF DW-Acc"
        ),
        "against_prior_accuracy": _metric(graph, "ap-acc", "Harness-IF AP-Acc"),
    }
    for row in metrics.agents:
        agent = HIF[f"agent-{row.agent_id}"]
        for field, metric_ref in metric_refs.items():
            value = getattr(row, field)
            if value is None:
                continue
            measurement = BNode()
            graph.add((measurement, RDF.type, DQV.QualityMeasurement))
            graph.add((measurement, DQV.isMeasurementOf, metric_ref))
            graph.add((measurement, DQV.computedOn, agent))
            graph.add((measurement, DQV.value, Literal(value)))
            graph.add((measurement, PROV.wasGeneratedBy, run))
    return graph


def snapshot_graph(snapshot: EvaluationSnapshot, *, run_iri: str) -> Graph:
    """Project a replayable scoring snapshot; this projection carries no DO authority."""
    graph = Graph()
    bundle = HIF[f"snapshot-{snapshot.snapshot_fingerprint}"]
    graph.add((bundle, RDF.type, PROV.Bundle))
    graph.add((bundle, DCTERMS.identifier, Literal(snapshot.snapshot_fingerprint)))
    graph.add((bundle, DCTERMS.source, PAPER))
    for constraint in snapshot.library:
        graph += constraint_graph(constraint)
        graph.add((bundle, PROV.hadMember, HIF[f"rule-{constraint.rule_id}"]))
    for verdict in snapshot.verdicts:
        graph += verdict_graph(verdict)
    graph += metrics_graph(snapshot.score(), run_iri=run_iri)
    return graph
