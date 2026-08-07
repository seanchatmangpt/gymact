"""Public-ontology application-profile authority for GymAct."""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path
import shutil

from pydantic import BaseModel, ConfigDict
from pyshacl import validate as shacl_validate
from rdflib import Graph, OWL, RDF, RDFS

GYMACT_INSTANCE_PREFIX = "urn:gymact:"


class SemanticValidation(BaseModel):
    """Result of validating GymAct's packaged semantic authority."""

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

    def validate(self) -> SemanticValidation:
        """Run real SHACL plus the zero-custom-TBox invariant."""
        graph = self.graph()
        custom_tbox: list[str] = []
        tbox_types = (
            OWL.Class,
            OWL.ObjectProperty,
            OWL.DatatypeProperty,
            RDFS.Class,
            RDF.Property,
        )
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
