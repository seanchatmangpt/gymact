from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gymact.policy_ecology import (
    ConditionAxis,
    PolicyPhenotype,
    PolicyPopulation,
    PopulationKind,
    ReactionNorm,
    StrategicCondition,
    WeightedPhenotype,
)
from gymact.policy_ecology_store import (
    SQLitePolicyEcologyStore,
    population_digest,
)


def adaptive_population() -> PolicyPopulation:
    return PolicyPopulation(
        kind=PopulationKind.ADAPTIVE,
        reaction_norm=ReactionNorm(slopes=(("exploration", 0.5),)),
        members=(
            WeightedPhenotype(
                phenotype=PolicyPhenotype(
                    policy_ref="urn:planner:Astar",
                    condition=StrategicCondition(values=(("exploration", 0.25),)),
                    evidence_refs=("urn:evidence:paper",),
                ),
                weight=1.0,
            ),
        ),
    )


def test_store_is_idempotent_and_round_trips_exact_population(tmp_path: Path) -> None:
    population = adaptive_population()
    with SQLitePolicyEcologyStore(tmp_path / "ecology.sqlite") as store:
        first = store.put(population)
        second = store.put(population)
        assert first == second
        assert first.population_digest == population_digest(population)
        assert store.get(first.population_digest) == population
        assert store.verify()


def test_condition_transition_is_replayable_and_preserves_parent(tmp_path: Path) -> None:
    population = adaptive_population()
    axes = (ConditionAxis(axis_id="exploration", lower=0.0, upper=1.0),)

    with SQLitePolicyEcologyStore(tmp_path / "ecology.sqlite") as store:
        parent = store.put(population)
        transition = store.condition(parent.population_digest, cue=1.0, axes=axes)
        child = store.get(transition.child_digest)

        assert child is not None
        assert child.members[0].phenotype.condition.as_dict()["exploration"] == pytest.approx(
            0.75
        )
        assert store.get(parent.population_digest) == population
        assert store.replay(transition.transition_digest)
        assert store.transitions_from(parent.population_digest) == (transition,)
        assert store.verify()


def test_missing_parent_is_typed_refusal(tmp_path: Path) -> None:
    with SQLitePolicyEcologyStore(tmp_path / "ecology.sqlite") as store:
        with pytest.raises(
            ValueError,
            match="REFUSED:POLICY_POPULATION_PARENT_NOT_FOUND",
        ):
            store.condition("missing", cue=1.0)


def test_tampered_population_payload_breaks_store_verification(tmp_path: Path) -> None:
    path = tmp_path / "ecology.sqlite"
    population = adaptive_population()
    with SQLitePolicyEcologyStore(path) as store:
        record = store.put(population)

    connection = sqlite3.connect(path)
    connection.execute(
        """
        UPDATE policy_populations
        SET canonical_json = ?
        WHERE population_digest = ?
        """,
        ('{"kind":"engineered","members":[]}', record.population_digest),
    )
    connection.commit()
    connection.close()

    with SQLitePolicyEcologyStore(path) as store:
        assert not store.verify()


def test_transition_replay_detects_child_tamper(tmp_path: Path) -> None:
    path = tmp_path / "ecology.sqlite"
    axes = (ConditionAxis(axis_id="exploration", lower=0.0, upper=1.0),)
    with SQLitePolicyEcologyStore(path) as store:
        parent = store.put(adaptive_population())
        transition = store.condition(parent.population_digest, cue=1.0, axes=axes)

    connection = sqlite3.connect(path)
    connection.execute(
        """
        UPDATE policy_population_transitions
        SET child_digest = parent_digest
        WHERE transition_digest = ?
        """,
        (transition.transition_digest,),
    )
    connection.commit()
    connection.close()

    with SQLitePolicyEcologyStore(path) as store:
        assert not store.replay(transition.transition_digest)
        assert not store.verify()
