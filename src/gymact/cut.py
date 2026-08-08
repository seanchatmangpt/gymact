"""Explicit irreversible cut from maximal possibility closure into BRCE.

Selection is separated from exploration and from execution. The cut binds one
admitted DO-frontier edge to the exact action, prepared subject, grant identity and
selection basis. It still cannot actuate; it manufactures a receiptable BRCE request.
"""
from __future__ import annotations

from pydantic import Field

from gymact.action_contract import (
    ActionDefinition,
    ExecutionGrant,
    PreparedAction,
    admit_execution,
)
from gymact.brce import BrokerRequest
from gymact.combinatorial import (
    DecisionPhase,
    ExplorationResult,
    PossibilityGraph,
)
from gymact.evidence import digest
from gymact.models import FrozenModel


class IrreversibleSelection(FrozenModel):
    graph_digest: str = Field(min_length=1)
    path_id: str = Field(min_length=1)
    morphism_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    action_ref: str = Field(min_length=1)
    capability_ref: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    prepared_digest: str = Field(min_length=1)
    grant_digest: str = Field(min_length=1)
    selector_ref: str = Field(min_length=1)
    basis_refs: tuple[str, ...] = ()
    selection_digest: str = Field(min_length=1)

    def verify_digest(self) -> bool:
        payload = self.model_dump(mode="json", exclude={"selection_digest"})
        return digest(payload) == self.selection_digest


class CombinatorialBrokerRequest(FrozenModel):
    selection: IrreversibleSelection
    broker_request: BrokerRequest


def select_irreversible_cut(
    graph: PossibilityGraph,
    exploration: ExplorationResult,
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
    """Select one already-admitted DO frontier edge without executing it."""
    if exploration.graph_digest != graph.graph_digest:
        raise ValueError("POSSIBILITY_GRAPH_DRIFT")
    frontier = next(
        (
            item
            for item in exploration.irreversible_frontier
            if item.path_id == path_id and item.morphism_id == morphism_id
        ),
        None,
    )
    if frontier is None:
        raise ValueError("IRREVERSIBLE_FRONTIER_EDGE_NOT_FOUND")
    if not frontier.admitted:
        raise ValueError(f"IRREVERSIBLE_FRONTIER_NOT_ADMITTED:{frontier.reason}")
    morphism = next(item for item in graph.morphisms if item.morphism_id == morphism_id)
    if morphism.phase is not DecisionPhase.DO:
        raise ValueError("SELECTED_MORPHISM_IS_NOT_DO")
    if prepared.action_ref != action.semantic_id:
        raise ValueError("SELECTION_ACTION_IDENTITY_MISMATCH")
    admission = admit_execution(
        action,
        prepared,
        grant,
        current_revision=current_revision,
    )
    if not admission.admitted:
        raise ValueError(f"SELECTION_GRANT_NOT_ADMITTED:{admission.reason}")
    payload = {
        "graph_digest": graph.graph_digest,
        "path_id": path_id,
        "morphism_id": morphism_id,
        "target_id": frontier.target_id,
        "action_ref": action.semantic_id,
        "capability_ref": action.capability_ref,
        "subject_ref": prepared.subject.semantic_id,
        "prepared_digest": digest(prepared.model_dump(mode="json")),
        "grant_digest": digest(grant.model_dump(mode="json")),
        "selector_ref": selector_ref,
        "basis_refs": basis_refs,
    }
    return IrreversibleSelection(**payload, selection_digest=digest(payload))


def manufacture_broker_request(
    selection: IrreversibleSelection,
    *,
    action: ActionDefinition,
    prepared: PreparedAction,
    grant: ExecutionGrant,
    current_revision: str | None = None,
    expected: dict[str, object] | None = None,
) -> CombinatorialBrokerRequest:
    """Manufacture the BRCE request and re-check every identity bound by the cut."""
    if not selection.verify_digest():
        raise ValueError("IRREVERSIBLE_SELECTION_DIGEST_MISMATCH")
    if selection.action_ref != action.semantic_id:
        raise ValueError("IRREVERSIBLE_SELECTION_ACTION_DRIFT")
    if selection.capability_ref != action.capability_ref:
        raise ValueError("IRREVERSIBLE_SELECTION_CAPABILITY_DRIFT")
    if selection.subject_ref != prepared.subject.semantic_id:
        raise ValueError("IRREVERSIBLE_SELECTION_SUBJECT_DRIFT")
    if selection.prepared_digest != digest(prepared.model_dump(mode="json")):
        raise ValueError("IRREVERSIBLE_SELECTION_PREPARED_DRIFT")
    if selection.grant_digest != digest(grant.model_dump(mode="json")):
        raise ValueError("IRREVERSIBLE_SELECTION_GRANT_DRIFT")
    request = BrokerRequest(
        action=action,
        prepared=prepared,
        grant=grant,
        current_revision=current_revision,
        expected=expected or {},
    )
    return CombinatorialBrokerRequest(selection=selection, broker_request=request)
