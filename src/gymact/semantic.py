"""Public-ontology application-profile authority for GymAct."""

from __future__ import annotations

from importlib.resources import files

from pydantic import BaseModel, ConfigDict
from pyshacl import validate as shacl_validate
from rdflib import Graph, Namespace, OWL, RDF

GYMACT_INSTANCE_PREFIX = "urn:gymact:"
PROF = Namespace("http://www.w3.org/ns/dx/prof/")


class SemanticValidation(BaseModel):
    """Result of validating GymAct's packaged semantic authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    conforms: bool
    triple_count: int
    custom_tbox_terms: tuple[str, ...]
    report_text: str


class ProfileAuthority:
    """Load and validate the packaged GymAct PROF application profile."""

    profile_uri = "urn:gymact:profile:v26.8.7"

    @staticmethod
    def _resource(name: str):
        return files("gymact.ontology").joinpath(name)

    def graph(self) -> Graph:
        graph = Graph()
        graph.parse(self._resource("profile.ttl"), format="turtle")
        return graph

    def shapes(self) -> Graph:
        graph = Graph()
        graph.parse(self._resource("profile.shacl.ttl"), format="turtle")
        return graph

    def validate(self) -> SemanticValidation:
        """Run real SHACL plus the zero-custom-TBox invariant."""
        graph = self.graph()
        custom_tbox: list[str] = []
        tbox_types = (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty)
        for subject, _, object_ in graph.triples((None, RDF.type, None)):
            if object_ in tbox_types and str(subject).startswith(GYMACT_INSTANCE_PREFIX):
                custom_tbox.append(str(subject))

        conforms, _, report = shacl_validate(
            graph,
            shacl_graph=self.shapes(),
            inference="rdfs",
            abort_on_first=False,
            allow_infos=False,
            allow_warnings=False,
        )
        effective = bool(conforms) and not custom_tbox
        report_text = str(report)
        if custom_tbox:
            report_text += "\nCUSTOM_TBOX_REFUSED: " + ", ".join(sorted(custom_tbox))
        return SemanticValidation(
            conforms=effective,
            triple_count=len(graph),
            custom_tbox_terms=tuple(sorted(custom_tbox)),
            report_text=report_text,
        )
