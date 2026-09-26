"""Ontology-backed temperament-axis vocabulary.

The RDF file is the semantic source. Python projects its SKOS concepts into
small immutable runtime values; it does not maintain a parallel axis registry.
"""

from __future__ import annotations

from importlib.resources import files

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS

from gymact.models import FrozenModel

TEMPERAMENT_SCHEME = URIRef("urn:gymact:temperament-scheme")
TEMPERAMENT_ENGINEERING_SOURCE = "https://arxiv.org/abs/2609.29423"


class TemperamentAxisSpec(FrozenModel):
    axis_id: str
    label: str
    origin: str
    source_ref: str
    semantic_ref: str


def temperament_ontology_graph() -> Graph:
    resource = files("gymact.ontology").joinpath("temperament_engineering.ttl")
    graph = Graph()
    graph.parse(data=resource.read_text(encoding="utf-8"), format="turtle")
    return graph


def load_temperament_axis_specs() -> tuple[TemperamentAxisSpec, ...]:
    graph = temperament_ontology_graph()
    source = URIRef(TEMPERAMENT_ENGINEERING_SOURCE)

    if (TEMPERAMENT_SCHEME, RDF.type, SKOS.ConceptScheme) not in graph:
        raise ValueError("REFUSED:TEMPERAMENT_ONTOLOGY_SCHEME_MISSING")
    if (TEMPERAMENT_SCHEME, DCTERMS.source, source) not in graph:
        raise ValueError("REFUSED:TEMPERAMENT_ONTOLOGY_SOURCE_MISMATCH")

    specs: list[TemperamentAxisSpec] = []
    seen: set[str] = set()
    for subject in graph.subjects(SKOS.inScheme, TEMPERAMENT_SCHEME):
        notation = graph.value(subject, SKOS.notation)
        label = graph.value(subject, SKOS.prefLabel)
        origin = graph.value(subject, DCTERMS.type)
        axis_source = graph.value(subject, DCTERMS.source)

        if notation is None or label is None or origin is None or axis_source is None:
            raise ValueError("REFUSED:TEMPERAMENT_ONTOLOGY_AXIS_INCOMPLETE")
        axis_id = str(notation)
        if axis_id in seen:
            raise ValueError(f"REFUSED:DUPLICATE_TEMPERAMENT_ONTOLOGY_AXIS:{axis_id}")
        if str(axis_source) != TEMPERAMENT_ENGINEERING_SOURCE:
            raise ValueError(f"REFUSED:TEMPERAMENT_ONTOLOGY_AXIS_SOURCE:{axis_id}")
        if str(origin) not in {"animal-temperament-axis", "robot-native-axis"}:
            raise ValueError(f"REFUSED:TEMPERAMENT_ONTOLOGY_AXIS_ORIGIN:{axis_id}")

        seen.add(axis_id)
        specs.append(
            TemperamentAxisSpec(
                axis_id=axis_id,
                label=str(label),
                origin=str(origin),
                source_ref=str(axis_source),
                semantic_ref=str(subject),
            )
        )

    if len(specs) != 9:
        raise ValueError(f"REFUSED:TEMPERAMENT_ONTOLOGY_AXIS_COUNT:{len(specs)}")

    return tuple(sorted(specs, key=lambda item: item.axis_id))


def assert_public_temperament_vocabulary() -> None:
    """Refuse local custom predicates/classes in the temperament source graph."""
    graph = temperament_ontology_graph()
    allowed_predicate_namespaces = (
        str(RDF),
        str(DCTERMS),
        str(SKOS),
    )
    for subject, predicate, obj in graph:
        if str(predicate).startswith("urn:gymact:"):
            raise ValueError(f"REFUSED:TEMPERAMENT_CUSTOM_PREDICATE:{predicate}")
        if predicate == RDF.type and isinstance(obj, URIRef) and str(obj).startswith("urn:gymact:"):
            raise ValueError(f"REFUSED:TEMPERAMENT_CUSTOM_CLASS:{obj}")
        if not str(predicate).startswith(allowed_predicate_namespaces):
            raise ValueError(f"REFUSED:TEMPERAMENT_UNKNOWN_PREDICATE:{predicate}")
