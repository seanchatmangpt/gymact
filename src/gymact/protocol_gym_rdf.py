"""Public-ontology projection for protocol-discovered GymSpec."""
from __future__ import annotations

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS

from gymact.models import Consequence
from gymact.protocol_gym import ProtocolGymSpec

SOSA = Namespace("http://www.w3.org/ns/sosa/")
PROV = Namespace("http://www.w3.org/ns/prov#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


def protocol_gym_spec_to_rdf(spec: ProtocolGymSpec) -> Graph:
    graph = Graph()
    subject = URIRef(spec.subject_id if ":" in spec.subject_id else f"urn:gymact:subject:{spec.subject_id}")
    graph.add((subject, RDF.type, PROV.Entity))
    graph.add((subject, DCTERMS.identifier, Literal(spec.subject_id)))
    graph.add((subject, DCTERMS.conformsTo, URIRef(f"urn:gymact:protocol:{spec.protocol.value}")))
    graph.add((subject, PROV.value, Literal(spec.source_digest)))
    for item in spec.capabilities:
        capability = URIRef(item.semantic_id)
        graph.add((capability, RDF.type, SOSA.Procedure))
        graph.add((capability, DCTERMS.title, Literal(item.title)))
        graph.add((capability, DCTERMS.type, URIRef("urn:gymact:consequence:do" if item.consequence is Consequence.DO else "urn:gymact:consequence:read")))
        graph.add((capability, DCTERMS.identifier, Literal(item.binding)))
        graph.add((capability, PROV.wasDerivedFrom, subject))
        if item.authority_required:
            graph.add((capability, SKOS.note, Literal("authority-required")))
    return graph
