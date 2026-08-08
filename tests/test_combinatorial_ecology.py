from __future__ import annotations

from gymact.combinatorial import (
    AdmissionContext,
    DecisionPhase,
    MorphismKind,
    PossibilityObject,
    PossibilityObjectKind,
    explore_maximal_reversible,
)
from gymact.ecology import (
    EcologyAlternative,
    EcologyDimension,
    IrreversibleOption,
    manufacture_ecology,
)


def test_layered_ecology_represents_cartesian_path_space_without_early_choice() -> None:
    start = PossibilityObject(
        object_id="o-star",
        kind=PossibilityObjectKind.ADMITTED_OBSERVATION,
        semantic_ref="urn:observation:admitted",
    )
    ecology = manufacture_ecology(
        start=start,
        dimensions=(
            EcologyDimension(
                dimension_id="planner",
                object_kind=PossibilityObjectKind.PLANNER,
                morphism_kind=MorphismKind.PLAN,
                phase=DecisionPhase.SELECT,
                alternatives=tuple(
                    EcologyAlternative(alternative_id=f"p{i}", semantic_ref=f"urn:planner:{i}")
                    for i in range(3)
                ),
            ),
            EcologyDimension(
                dimension_id="provider",
                object_kind=PossibilityObjectKind.PROVIDER,
                alternatives=tuple(
                    EcologyAlternative(alternative_id=f"e{i}", semantic_ref=f"urn:provider:{i}")
                    for i in range(2)
                ),
            ),
            EcologyDimension(
                dimension_id="verifier",
                object_kind=PossibilityObjectKind.VERIFIER,
                morphism_kind=MorphismKind.VERIFY,
                phase=DecisionPhase.CONSTRUCT,
                alternatives=tuple(
                    EcologyAlternative(alternative_id=f"v{i}", semantic_ref=f"urn:verifier:{i}")
                    for i in range(2)
                ),
            ),
        ),
        irreversible=(
            IrreversibleOption(
                option_id="effect",
                target=PossibilityObject(
                    object_id="effect",
                    kind=PossibilityObjectKind.RECEIPT,
                    semantic_ref="urn:effect:verified",
                ),
            ),
        ),
    )
    assert ecology.reversible_path_cardinality == 12
    assert ecology.irreversible_choice_cardinality == 12

    exploration = explore_maximal_reversible(
        ecology.graph,
        start_ids=(start.object_id,),
        context=AdmissionContext(execution_grant_ref="urn:grant:present"),
    )
    terminal_reversible = [
        path for path in exploration.paths if path.object_ids[-1].startswith("verifier:")
    ]
    assert len(terminal_reversible) == 12
    assert len(exploration.irreversible_frontier) == 12
    assert all(item.admitted for item in exploration.irreversible_frontier)


def test_ecology_graph_size_is_compact_relative_to_path_product() -> None:
    start = PossibilityObject(
        object_id="o",
        kind=PossibilityObjectKind.ADMITTED_OBSERVATION,
        semantic_ref="urn:o",
    )
    dimensions = tuple(
        EcologyDimension(
            dimension_id=f"d{dimension}",
            object_kind=PossibilityObjectKind.CAPABILITY,
            alternatives=tuple(
                EcologyAlternative(
                    alternative_id=f"a{alternative}",
                    semantic_ref=f"urn:d{dimension}:a{alternative}",
                )
                for alternative in range(5)
            ),
        )
        for dimension in range(4)
    )
    ecology = manufacture_ecology(start=start, dimensions=dimensions)
    assert ecology.reversible_path_cardinality == 625
    assert len(ecology.graph.objects) == 21
    assert len(ecology.graph.morphisms) == 80
