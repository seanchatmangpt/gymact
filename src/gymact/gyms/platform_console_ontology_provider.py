"""Ontology-driven platform-console provider compiled from canonical capability RDF.

The maintained capability model lives in ``chatman-ecosystem``.  GymAct consumes
that public RDF ABox and projects each ``ce:Capability`` individual into the
generic ``OntologyDrivenProvider`` execution algebra.  It does not duplicate
platform-console capability semantics in Python.

Reversibility is authority-relevant evidence: capabilities declared
``ce:reversible false`` are elevated.  Missing elevated authority fails closed;
an elevated credential may also exercise a standard capability, while a
standard credential can never exercise an elevated one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS

from gymact.gyms.ontology_gym import OntologyDrivenProvider, OntologyTask
from gymact.models import AuthorityDecision, AuthorityRequest

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
DEFAULT_PACK_DIR: Final = (
    REPO_ROOT.parent / "chatman-ecosystem" / "ontology" / "platform-console-gym-pack"
)
PLATFORM_CONSOLE_GYM_PACK_DIR: Final = DEFAULT_PACK_DIR
PLATFORM_CONSOLE_CAPABILITIES_ONTOLOGY: Final = (
    DEFAULT_PACK_DIR.parent / "platform-console-capabilities.ttl"
)
PROVIDER_NAME: Final = "platform-console-ontology"

CE: Final = Namespace(
    "https://seanchatmangpt.github.io/chatman-ecosystem/ontology/capabilities#"
)
_STANDARD_FAMILY: Final = "standard"
_ELEVATED_FAMILY: Final = "elevated"


@dataclass(frozen=True, slots=True)
class PlatformConsoleCapability:
    """One admitted platform-console ``ce:Capability`` ABox individual."""

    iri: str
    title: str
    reversible: bool
    required_authority: str | None
    execution_owner: str | None
    description: str | None


def _required_text(graph: Graph, subject: URIRef, predicate: URIRef) -> str:
    values = tuple(graph.objects(subject, predicate))
    if len(values) != 1:
        raise ValueError(
            f"REFUSED_AMBIGUOUS_CAPABILITY_PROPERTY:{subject}:{predicate}:{len(values)}"
        )
    value = str(values[0]).strip()
    if not value:
        raise ValueError(f"REFUSED_EMPTY_CAPABILITY_PROPERTY:{subject}:{predicate}")
    return value


def _optional_text(graph: Graph, subject: URIRef, predicate: URIRef) -> str | None:
    values = tuple(graph.objects(subject, predicate))
    if not values:
        return None
    if len(values) != 1:
        raise ValueError(
            f"REFUSED_AMBIGUOUS_CAPABILITY_PROPERTY:{subject}:{predicate}:{len(values)}"
        )
    value = str(values[0]).strip()
    return value or None


def _required_boolean(graph: Graph, subject: URIRef, predicate: URIRef) -> bool:
    values = tuple(graph.objects(subject, predicate))
    if len(values) != 1:
        raise ValueError(
            f"REFUSED_AMBIGUOUS_CAPABILITY_PROPERTY:{subject}:{predicate}:{len(values)}"
        )
    value = values[0].toPython()
    if isinstance(value, bool):
        return value
    lexical = str(value).strip().lower()
    if lexical in {"true", "1"}:
        return True
    if lexical in {"false", "0"}:
        return False
    raise ValueError(f"REFUSED_INVALID_REVERSIBILITY:{subject}:{value}")


def load_platform_console_capabilities(
    path: Path = PLATFORM_CONSOLE_CAPABILITIES_ONTOLOGY,
) -> tuple[PlatformConsoleCapability, ...]:
    """Load canonical capability facts without inventing missing semantics."""

    graph = Graph()
    graph.parse(path.as_posix(), format="turtle")
    capabilities: list[PlatformConsoleCapability] = []
    for subject in sorted(graph.subjects(RDF.type, CE.Capability), key=str):
        if not isinstance(subject, URIRef):
            raise ValueError(f"REFUSED_NON_IRI_CAPABILITY:{subject}")
        capabilities.append(
            PlatformConsoleCapability(
                iri=str(subject),
                title=_required_text(graph, subject, DCTERMS.title),
                reversible=_required_boolean(graph, subject, CE.reversible),
                required_authority=_optional_text(graph, subject, CE.requiredAuthority),
                execution_owner=_optional_text(graph, subject, CE.executionOwner),
                description=_optional_text(graph, subject, DCTERMS.description),
            )
        )
    if not capabilities:
        raise ValueError(f"REFUSED_EMPTY_PLATFORM_CONSOLE_CAPABILITY_GRAPH:{path}")
    titles = [capability.title for capability in capabilities]
    if len(titles) != len(set(titles)):
        raise ValueError("REFUSED_DUPLICATE_PLATFORM_CONSOLE_CAPABILITY_TITLE")
    return tuple(sorted(capabilities, key=lambda capability: capability.title))


class PlatformConsoleOntologyDrivenProvider(OntologyDrivenProvider):
    """Generic ontology environment projected from the complete capability ABox."""

    def __init__(
        self,
        *,
        pack_dir: Path = DEFAULT_PACK_DIR,
        capability_path: Path = PLATFORM_CONSOLE_CAPABILITIES_ONTOLOGY,
    ) -> None:
        super().__init__(
            name=PROVIDER_NAME,
            pack_dir=pack_dir,
            elevated_task_families=frozenset({_ELEVATED_FAMILY}),
        )
        self._capability_path = capability_path

    def tasks(self) -> tuple[OntologyTask, ...]:
        return tuple(
            OntologyTask(
                task_iri=capability.iri,
                identifier=capability.title,
                subjects=(capability.title,),
                family=_STANDARD_FAMILY if capability.reversible else _ELEVATED_FAMILY,
            )
            for capability in load_platform_console_capabilities(self._capability_path)
        )


class FailClosedPlatformConsoleAuthorityResolver:
    """Two-tier resolver with an explicit no-elevated-authority state."""

    def __init__(
        self,
        *,
        elevated_capabilities: frozenset[str],
        standard_ref: str,
        elevated_ref: str | None,
    ) -> None:
        if not standard_ref:
            raise ValueError("REFUSED_EMPTY_STANDARD_AUTHORITY_REF")
        if elevated_ref is not None and elevated_ref == standard_ref:
            raise ValueError("REFUSED_SAME_REF_FOR_STANDARD_AND_ELEVATED")
        self._elevated_capabilities = elevated_capabilities
        self._standard_ref = standard_ref
        self._elevated_ref = elevated_ref

    async def authorize(self, request: AuthorityRequest) -> AuthorityDecision:
        ref = request.authority_ref
        if ref is None:
            return AuthorityDecision(admitted=False, reason="LIVE_AUTHORITY_REQUIRED")
        if request.capability_ref in self._elevated_capabilities:
            admitted = self._elevated_ref is not None and ref == self._elevated_ref
        else:
            admitted = ref == self._standard_ref or (
                self._elevated_ref is not None and ref == self._elevated_ref
            )
        if not admitted:
            return AuthorityDecision(admitted=False, reason="AUTHORITY_NOT_ADMITTED")
        return AuthorityDecision(
            admitted=True,
            reason="AUTHORITY_ADMITTED",
            evidence_ref=f"urn:gymact:authority-decision:{ref}",
        )


def build_platform_console_ontology_provider() -> PlatformConsoleOntologyDrivenProvider:
    """Build the provider; all task semantics are read from canonical RDF."""
    return PlatformConsoleOntologyDrivenProvider()


def build_fail_closed_authority_resolver(
    *,
    provider: PlatformConsoleOntologyDrivenProvider,
    standard_ref: str,
    elevated_ref: str | None,
) -> FailClosedPlatformConsoleAuthorityResolver:
    """Bind current ontology-derived irreversible capabilities to elevated authority."""
    return FailClosedPlatformConsoleAuthorityResolver(
        elevated_capabilities=provider.elevated_capability_iris(),
        standard_ref=standard_ref,
        elevated_ref=elevated_ref,
    )
