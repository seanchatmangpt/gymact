"""Public-ontology projection of EnvHarness/EnvRigger runtime values.

No GymAct-owned TBox is introduced. Stage, Contract, Chain, candidate and validation
identities are ABox resources classified with public PROV-O/P-PLAN/SOSA/ODRL/EARL terms
and local SKOS concepts, exactly matching GymAct's ontology rule.
"""

from __future__ import annotations

from typing import Final

from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS, PROV, SKOS

from gymact.envharness import HarnessSpec, Stage, TaskSpec
from gymact.envrigger import EnvRiggerResult

PPLAN: Final = Namespace("http://purl.org/net/p-plan#")
SOSA: Final = Namespace("http://www.w3.org/ns/sosa/")
ODRL: Final = Namespace("http://www.w3.org/ns/odrl/2/")
EARL: Final = Namespace("http://www.w3.org/ns/earl#")
GYM: Final = Namespace("urn:gymact:envharness:")
PAPER = URIRef("https://arxiv.org/abs/2608.19880")

_STAGE = GYM["component-stage"]
_CONTRACT = GYM["component-contract"]
_CHAIN = GYM["component-chain"]
_CANDIDATE = GYM["envrigger-candidate"]
_VALIDATION = GYM["envrigger-validation"]


def _add_concepts(graph: Graph) -> None:
    for iri, label in (
        (_STAGE, "EnvHarness Stage"),
        (_CONTRACT, "EnvHarness Contract"),
        (_CHAIN, "EnvHarness Chain"),
        (_CANDIDATE, "EnvRigger candidate"),
        (_VALIDATION, "EnvRigger validation"),
    ):
        graph.add((iri, RDF.type, SKOS.Concept))
        graph.add((iri, SKOS.prefLabel, Literal(label)))
        graph.add((iri, DCTERMS.source, PAPER))


def harness_graph(spec: HarnessSpec, *, tasks: tuple[TaskSpec, ...] = ()) -> Graph:
    """Project a harness into public vocabulary without manufacturing execution rights."""
    graph = Graph()
    _add_concepts(graph)
    harness = URIRef(spec.identifier)
    graph.add((harness, RDF.type, PPLAN.Plan))
    graph.add((harness, RDF.type, PROV.Plan))
    graph.add((harness, DCTERMS.source, PAPER))

    prior: URIRef | BNode | None = None
    for stage_index, stage in enumerate(spec.stages):
        node = URIRef(f"{spec.identifier}:stage:{stage_index}")
        _stage_graph(graph, node, stage)
        graph.add((harness, PPLAN.hasStep, node))
        if prior is not None:
            graph.add((node, PPLAN.isPrecededBy, prior))
        prior = node

    for contract_index, contract in enumerate(spec.contracts):
        node = URIRef(f"{spec.identifier}:contract:{contract_index}")
        graph.add((node, RDF.type, ODRL.Policy))
        graph.add((node, DCTERMS.type, _CONTRACT))
        graph.add((node, DCTERMS.source, PAPER))
        graph.add((harness, PPLAN.hasStep, node))
        if prior is not None:
            graph.add((node, PPLAN.isPrecededBy, prior))
        prior = node
        for rule_index, rule in enumerate(contract.rules):
            rule_node = URIRef(f"{node}:rule:{rule_index}")
            predicate = ODRL.prohibition if rule.effect == "deny" else ODRL.permission
            graph.add((node, predicate, rule_node))
            graph.add((rule_node, ODRL.target, URIRef(rule.capability)))
            graph.add((rule_node, ODRL.action, ODRL.use))
            graph.add((rule_node, DCTERMS.description, Literal(rule.reason)))

    if tasks:
        chain = URIRef(f"{spec.identifier}:chain")
        graph.add((chain, RDF.type, PPLAN.Plan))
        graph.add((chain, RDF.type, PROV.Plan))
        graph.add((chain, DCTERMS.type, _CHAIN))
        graph.add((chain, DCTERMS.source, PAPER))
        previous_task: URIRef | None = None
        for index, task in enumerate(tasks):
            task_node = URIRef(f"{chain}:leg:{index}")
            graph.add((task_node, RDF.type, PPLAN.Step))
            graph.add((task_node, DCTERMS.identifier, Literal(task.provider)))
            graph.add((chain, PPLAN.hasStep, task_node))
            if previous_task is not None:
                graph.add((task_node, PPLAN.isPrecededBy, previous_task))
            previous_task = task_node

    return graph


def _stage_graph(graph: Graph, node: URIRef, stage: Stage) -> None:
    graph.add((node, RDF.type, PPLAN.Step))
    graph.add((node, DCTERMS.type, _STAGE))
    graph.add((node, DCTERMS.source, PAPER))
    for index, action in enumerate(stage.actions):
        action_node = URIRef(f"{node}:actuation:{index}")
        graph.add((action_node, RDF.type, SOSA.Actuation))
        graph.add((action_node, RDF.type, PROV.Activity))
        graph.add((action_node, RDF.type, PPLAN.Step))
        graph.add((action_node, SOSA.usedProcedure, URIRef(action.capability)))
        graph.add((action_node, DCTERMS.isPartOf, node))


def envrigger_graph(result: EnvRiggerResult, *, run_iri: str) -> Graph:
    """Project Observe/Diagnose/Write/Validate provenance and acceptance assertions."""
    graph = Graph()
    _add_concepts(graph)
    run = URIRef(run_iri)
    graph.add((run, RDF.type, PROV.Activity))
    graph.add((run, DCTERMS.source, PAPER))

    baseline = URIRef(f"{run_iri}:baseline")
    graph.add((baseline, RDF.type, PROV.Entity))
    graph.add((baseline, PROV.wasGeneratedBy, run))
    graph.add((baseline, DCTERMS.description, Literal(result.baseline_diagnosis.signal)))

    for evaluation in result.evaluations:
        candidate = URIRef(f"{run_iri}:candidate:{evaluation.revision}")
        validation = URIRef(f"{candidate}:validation")
        assertion = URIRef(f"{candidate}:assertion")
        graph.add((candidate, RDF.type, PROV.Entity))
        graph.add((candidate, DCTERMS.type, _CANDIDATE))
        graph.add((candidate, PROV.wasGeneratedBy, run))
        graph.add((candidate, DCTERMS.identifier, Literal(evaluation.harness.identifier)))
        graph.add((validation, RDF.type, PROV.Activity))
        graph.add((validation, DCTERMS.type, _VALIDATION))
        graph.add((validation, PROV.used, candidate))
        graph.add((validation, PROV.wasInformedBy, run))
        graph.add((assertion, RDF.type, EARL.Assertion))
        graph.add((assertion, EARL.test, validation))
        graph.add((assertion, EARL.subject, candidate))
        graph.add((assertion, EARL.result, URIRef(f"{assertion}:result")))
        result_node = URIRef(f"{assertion}:result")
        graph.add((result_node, RDF.type, EARL.TestResult))
        outcome = EARL.passed if evaluation.disposition == "ACCEPT" else EARL.failed
        graph.add((result_node, EARL.outcome, outcome))
        graph.add((result_node, DCTERMS.description, Literal(evaluation.reason)))

    return graph
