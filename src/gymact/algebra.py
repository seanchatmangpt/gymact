"""Algebraic laws for DCM possibility paths."""
from __future__ import annotations

from gymact.combinatorial import ObjectiveVector, PossibilityPath


def identity_path(object_id: str) -> PossibilityPath:
    """Identity morphism represented by a zero-edge path at one object."""
    if not object_id:
        raise ValueError("IDENTITY_PATH_REQUIRES_OBJECT")
    return PossibilityPath(object_ids=(object_id,))


def compose_paths(left: PossibilityPath, right: PossibilityPath) -> PossibilityPath:
    """Compose adjacent paths; non-adjacent composition is mechanically refused."""
    if not left.object_ids or not right.object_ids:
        raise ValueError("PATH_COMPOSITION_REQUIRES_OBJECTS")
    if left.object_ids[-1] != right.object_ids[0]:
        raise ValueError("PATH_COMPOSITION_ENDPOINT_MISMATCH")
    return PossibilityPath(
        object_ids=(*left.object_ids, *right.object_ids[1:]),
        morphism_ids=(*left.morphism_ids, *right.morphism_ids),
        objectives=left.objectives.compose(right.objectives),
    )


def zero_objectives() -> ObjectiveVector:
    """Neutral objective element for identity-path composition."""
    return ObjectiveVector()
