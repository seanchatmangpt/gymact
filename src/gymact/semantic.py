"""Public-ontology application-profile authority for GymAct."""

from __future__ import annotations

import shutil
from importlib.resources import as_file, files
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from pyshacl import validate as shacl_validate
from rdflib import Graph, OWL, RDF, RDFS

GYMACT_INSTANCE_PREFIX = "urn:gymact:"


class SemanticValidation(BaseModel):
    """Result of validating GymAct semantic data against its public profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    conforms: bool
    triple_count: int
    custom_tbox_terms: tuple[str, ...]
    report_text: str


class ProfileAuthority:
    """Load, validate, and export the packaged GymAct PROF application profile."""

    profile_uri = "urn:gymact:profile:v26.8.7"

    @staticmethod
    def _resource(name: str):
        return files("gymact.ontology").joinpath(name)

    def _parse(self, name: str) -> Graph:
        graph = Graph()
        with as_file(self._resource(name)) as path:
            graph.parse(path, format="turtle")
        return graph

    def graph(self) -> Graph:
        return self._parse("profile.ttl")

    def shapes(self) -> Graph:
        return self._parse("profile.shacl.ttl")

    def bundle(self) -> Graph:
        """Return the complete packaged semantic bundle for inspection/export tooling."""
        graph = self.graph()
        for triple in self.shapes():
            graph.add(triple)
        return graph

    def export(self, directory: str | Path) -> dict[str, Path]:
        """Materialize package RDF resources for ggen or other external compilers."""
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        exported: dict[str, Path] = {}
        for name in ("profile.ttl", "profile.shacl.ttl"):
            destination = target / name
            with as_file(self._resource(name)) as source:
                shutil.copyfile(source, destination)
            exported[name] = destination
        return exported

    @staticmethod
    def _custom_tbox_terms(graph: Graph) -> tuple[str, ...]:
        tbox_types = (
            OWL.Class,
            OWL.ObjectProperty,
            OWL.DatatypeProperty,
            RDFS.Class,
            RDF.Property,
        )
        terms = {
            str(subject)
            for subject, _, object_ in graph.triples((None, RDF.type, None))
            if object_ in tbox_types and str(subject).startswith(GYMACT_INSTANCE_PREFIX)
        }
        return tuple(sorted(terms))

    def _validate_graph(self, data: Graph) -> SemanticValidation:
        shapes = self.shapes()
        bundle = Graph()
        for triple in data:
            bundle.add(triple)
        for triple in shapes:
            bundle.add(triple)
        custom_tbox = self._custom_tbox_terms(bundle)

        conforms, _, report = shacl_validate(
            data,
            shacl_graph=shapes,
            inference="rdfs",
            abort_on_first=False,
            allow_infos=False,
            allow_warnings=False,
        )
        effective = bool(conforms) and not custom_tbox
        report_text = str(report)
        if custom_tbox:
            report_text += "\nCUSTOM_TBOX_REFUSED: " + ", ".join(custom_tbox)
        return SemanticValidation(
            conforms=effective,
            triple_count=len(data),
            custom_tbox_terms=custom_tbox,
            report_text=report_text,
        )

    def validate(self) -> SemanticValidation:
        """Validate the packaged profile and the zero-custom-TBox invariant."""
        return self._validate_graph(self.graph())

    def validate_data(self, data_graph: Graph) -> SemanticValidation:
        """Validate a gym/capability ABox together with the packaged profile ABox.

        The caller's graph may define domain-specific instances and use external
        ontologies. GymAct only refuses custom ``urn:gymact:`` TBox terms, preserving
        the profile rule that GymAct itself does not grow a competing vocabulary.
        """
        combined = self.graph()
        for triple in data_graph:
            combined.add(triple)
        return self._validate_graph(combined)
