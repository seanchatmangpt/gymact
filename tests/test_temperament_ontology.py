from __future__ import annotations

from gymact.policy_ecology import DEFAULT_TEMPERAMENT_AXES
from gymact.temperament_ontology import (
    TEMPERAMENT_ENGINEERING_SOURCE,
    assert_public_temperament_vocabulary,
    load_temperament_axis_specs,
)


def test_ontology_is_source_for_exact_nine_axis_runtime_projection() -> None:
    specs = load_temperament_axis_specs()
    assert len(specs) == 9
    assert {spec.axis_id for spec in specs} == {
        "boldness",
        "exploration",
        "activity",
        "aggressiveness",
        "sociability",
        "self_model_plasticity",
        "forcefulness",
        "initiative",
        "expressiveness",
    }
    assert {axis.axis_id for axis in DEFAULT_TEMPERAMENT_AXES} == {
        spec.axis_id for spec in specs
    }


def test_five_animal_and_four_robot_native_axes_are_preserved() -> None:
    specs = load_temperament_axis_specs()
    animal = [spec for spec in specs if spec.origin == "animal-temperament-axis"]
    robot = [spec for spec in specs if spec.origin == "robot-native-axis"]
    assert len(animal) == 5
    assert len(robot) == 4


def test_every_axis_is_provenance_bound_to_the_paper() -> None:
    specs = load_temperament_axis_specs()
    assert all(spec.source_ref == TEMPERAMENT_ENGINEERING_SOURCE for spec in specs)
    assert all(
        axis.provenance_refs == (TEMPERAMENT_ENGINEERING_SOURCE,)
        for axis in DEFAULT_TEMPERAMENT_AXES
    )


def test_temperament_ontology_uses_no_custom_predicates_or_classes() -> None:
    assert_public_temperament_vocabulary()
