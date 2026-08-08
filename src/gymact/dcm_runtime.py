"""Canonical Design for Combinatorial Maximum decision court.

The court admits and explores public-ontology possibility graphs. It does not choose
or actuate implicitly. An explicit irreversible cut is required before BRCE execution.
"""
from __future__ import annotations

from typing import Iterable

from gymact.action_contract import ActionDefinition, ExecutionGrant, PreparedAction
from gymact.brce import BrokerRuntime
from gymact.combinatorial import (
    AdmissionContext,
    ExplorationBounds,
    ExplorationResult,
    PossibilityGraph,
)
from gymact.combinatorial_rdf import (
    PossibilityRDFValidation,
    graph_to_rdf,
    rdf_to_graph,
    validate_possibility_rdf,
)
from gymact.cut import (
    CombinatorialBRCEBroker,
    CombinatorialBrokerRequest,
    IrreversibleSelection,
    manufacture_broker_request,
    select_irreversible_cut,
)
from gymact.maximal import explore_combinatorial_maximum
from gymact.models import FrozenModel
from gymact.structural_scan import StructuralSignature, structural_scan


class DecisionCourtRecord(FrozenModel):
    graph_digest: str
    rdf_validation: PossibilityRDFValidation
    structural_signature: StructuralSignature
    exploration: ExplorationResult


class DCMDecisionCourt:
    """Admit public graph, preserve reversible closure, and require explicit cut."""

    def admit_and_explore(
        self,
        graph: PossibilityGraph,
        *,
        start_ids: Iterable[str],
        context: AdmissionContext | None = None,
        bounds: ExplorationBounds | None = None,
    ) -> DecisionCourtRecord:
        rdf = graph_to_rdf(graph)
        validation = validate_possibility_rdf(rdf)
        if not validation.conforms:
            raise ValueError("POSSIBILITY_RDF_NOT_ADMITTED")
        projected = rdf_to_graph(rdf, graph_digest=graph.graph_digest)
        if projected != graph:
            raise ValueError("POSSIBILITY_RDF_PROJECTION_NOT_LOSSLESS")
        signature = structural_scan(projected)
        exploration = explore_combinatorial_maximum(
            projected,
            start_ids=start_ids,
            context=context,
            bounds=bounds,
        )
        return DecisionCourtRecord(
            graph_digest=projected.graph_digest,
            rdf_validation=validation,
            structural_signature=signature,
            exploration=exploration,
        )

    def select(
        self,
        graph: PossibilityGraph,
        court: DecisionCourtRecord,
        *,
        path_id: str,
        morphism_id: str,
        action: ActionDefinition,
        prepared: PreparedAction,
        grant: ExecutionGrant,
        selector_ref: str,
        basis_refs: tuple[str, ...] = (),
        current_revision: str | None = None,
    ) -> IrreversibleSelection:
        if court.graph_digest != graph.graph_digest:
            raise ValueError("DECISION_COURT_GRAPH_DRIFT")
        return select_irreversible_cut(
            graph,
            court.exploration,
            path_id=path_id,
            morphism_id=morphism_id,
            action=action,
            prepared=prepared,
            grant=grant,
            selector_ref=selector_ref,
            basis_refs=basis_refs,
            current_revision=current_revision,
        )

    def manufacture_request(
        self,
        selection: IrreversibleSelection,
        *,
        action: ActionDefinition,
        prepared: PreparedAction,
        grant: ExecutionGrant,
        current_revision: str | None = None,
        expected: dict[str, object] | None = None,
    ) -> CombinatorialBrokerRequest:
        return manufacture_broker_request(
            selection,
            action=action,
            prepared=prepared,
            grant=grant,
            current_revision=current_revision,
            expected=expected,
        )

    async def execute(
        self,
        runtime: BrokerRuntime,
        request: CombinatorialBrokerRequest,
    ):
        """Execute only an already-cut combinatorial BRCE request."""
        return await CombinatorialBRCEBroker(runtime).execute(request)
