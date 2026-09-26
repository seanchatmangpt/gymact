"""Durable, replayable storage for powerless policy populations.

This store persists candidate policy-ecology state and conditioning transitions.
It is deliberately not a ReceiptLedger: storing or replaying a population does
not prove execution, grant authority, or create standing for any consequence.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from gymact.evidence import canonical_bytes, digest
from gymact.models import FrozenModel
from gymact.policy_ecology import (
    DEFAULT_TEMPERAMENT_AXES,
    ConditionAxis,
    PolicyPopulation,
    condition_population,
)


class PopulationRecord(FrozenModel):
    population_digest: str = Field(min_length=1)
    canonical_json: str = Field(min_length=1)

    def population(self) -> PolicyPopulation:
        return PolicyPopulation.model_validate(json.loads(self.canonical_json))


class PopulationTransitionRecord(FrozenModel):
    transition_digest: str = Field(min_length=1)
    parent_digest: str = Field(min_length=1)
    child_digest: str = Field(min_length=1)
    cue: float
    axes: tuple[ConditionAxis, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def distinct_transition(self) -> Self:
        if not self.transition_digest.strip():
            raise ValueError("REFUSED:EMPTY_POPULATION_TRANSITION_DIGEST")
        return self


def population_digest(population: PolicyPopulation) -> str:
    return digest(population.model_dump(mode="json"))


def population_record(population: PolicyPopulation) -> PopulationRecord:
    payload = population.model_dump(mode="json")
    return PopulationRecord(
        population_digest=digest(payload),
        canonical_json=canonical_bytes(payload).decode("utf-8"),
    )


def transition_digest(
    *,
    parent_digest: str,
    child_digest: str,
    cue: float,
    axes: tuple[ConditionAxis, ...],
) -> str:
    return digest(
        {
            "parent_digest": parent_digest,
            "child_digest": child_digest,
            "cue": cue,
            "axes": [axis.model_dump(mode="json") for axis in axes],
        }
    )


class SQLitePolicyEcologyStore:
    """SQLite-backed immutable population/conditioning registry."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._connection = sqlite3.connect(self.path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS policy_populations (
                population_digest TEXT PRIMARY KEY,
                canonical_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS policy_population_transitions (
                transition_digest TEXT PRIMARY KEY,
                parent_digest TEXT NOT NULL,
                child_digest TEXT NOT NULL,
                cue REAL NOT NULL,
                axes_json TEXT NOT NULL,
                FOREIGN KEY(parent_digest)
                    REFERENCES policy_populations(population_digest),
                FOREIGN KEY(child_digest)
                    REFERENCES policy_populations(population_digest)
            );
            CREATE INDEX IF NOT EXISTS idx_policy_population_transition_parent
              ON policy_population_transitions(parent_digest);
            """
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def put(self, population: PolicyPopulation) -> PopulationRecord:
        record = population_record(population)
        existing = self._connection.execute(
            """
            SELECT canonical_json
            FROM policy_populations
            WHERE population_digest = ?
            """,
            (record.population_digest,),
        ).fetchone()
        if existing is not None:
            if existing[0] != record.canonical_json:
                raise ValueError("REFUSED:POLICY_POPULATION_DIGEST_CONFLICT")
            return record

        self._connection.execute(
            """
            INSERT INTO policy_populations(population_digest, canonical_json)
            VALUES (?, ?)
            """,
            (record.population_digest, record.canonical_json),
        )
        self._connection.commit()
        return record

    def get(self, population_digest_value: str) -> PolicyPopulation | None:
        row = self._connection.execute(
            """
            SELECT canonical_json
            FROM policy_populations
            WHERE population_digest = ?
            """,
            (population_digest_value,),
        ).fetchone()
        if row is None:
            return None
        population = PolicyPopulation.model_validate(json.loads(row[0]))
        if population_digest(population) != population_digest_value:
            raise ValueError("REFUSED:STORED_POLICY_POPULATION_DIGEST_MISMATCH")
        return population

    def condition(
        self,
        parent_digest: str,
        *,
        cue: float,
        axes: tuple[ConditionAxis, ...] = DEFAULT_TEMPERAMENT_AXES,
    ) -> PopulationTransitionRecord:
        parent = self.get(parent_digest)
        if parent is None:
            raise ValueError("REFUSED:POLICY_POPULATION_PARENT_NOT_FOUND")

        child = condition_population(parent, cue=cue, axes=axes)
        child_record = self.put(child)
        transition_id = transition_digest(
            parent_digest=parent_digest,
            child_digest=child_record.population_digest,
            cue=cue,
            axes=axes,
        )
        record = PopulationTransitionRecord(
            transition_digest=transition_id,
            parent_digest=parent_digest,
            child_digest=child_record.population_digest,
            cue=cue,
            axes=axes,
        )
        axes_json = canonical_bytes(
            [axis.model_dump(mode="json") for axis in axes]
        ).decode("utf-8")

        existing = self._connection.execute(
            """
            SELECT parent_digest, child_digest, cue, axes_json
            FROM policy_population_transitions
            WHERE transition_digest = ?
            """,
            (transition_id,),
        ).fetchone()
        expected = (
            record.parent_digest,
            record.child_digest,
            record.cue,
            axes_json,
        )
        if existing is not None:
            if existing != expected:
                raise ValueError("REFUSED:POLICY_POPULATION_TRANSITION_CONFLICT")
            return record

        self._connection.execute(
            """
            INSERT INTO policy_population_transitions(
                transition_digest,
                parent_digest,
                child_digest,
                cue,
                axes_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            expected[:0] + (transition_id,) + expected,
        )
        self._connection.commit()
        return record

    def transition(self, transition_digest_value: str) -> PopulationTransitionRecord | None:
        row = self._connection.execute(
            """
            SELECT parent_digest, child_digest, cue, axes_json
            FROM policy_population_transitions
            WHERE transition_digest = ?
            """,
            (transition_digest_value,),
        ).fetchone()
        if row is None:
            return None
        parent_digest, child_digest, cue, axes_json = row
        axes = tuple(
            ConditionAxis.model_validate(item)
            for item in json.loads(axes_json)
        )
        return PopulationTransitionRecord(
            transition_digest=transition_digest_value,
            parent_digest=parent_digest,
            child_digest=child_digest,
            cue=cue,
            axes=axes,
        )

    def replay(self, transition_digest_value: str) -> bool:
        transition = self.transition(transition_digest_value)
        if transition is None:
            raise ValueError("REFUSED:POLICY_POPULATION_TRANSITION_NOT_FOUND")
        parent = self.get(transition.parent_digest)
        child = self.get(transition.child_digest)
        if parent is None or child is None:
            return False
        replayed = condition_population(
            parent,
            cue=transition.cue,
            axes=transition.axes,
        )
        return (
            population_digest(replayed) == transition.child_digest
            and replayed == child
            and transition_digest(
                parent_digest=transition.parent_digest,
                child_digest=transition.child_digest,
                cue=transition.cue,
                axes=transition.axes,
            )
            == transition.transition_digest
        )

    def transitions_from(
        self,
        parent_digest: str,
    ) -> tuple[PopulationTransitionRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT transition_digest
            FROM policy_population_transitions
            WHERE parent_digest = ?
            ORDER BY transition_digest
            """,
            (parent_digest,),
        ).fetchall()
        records = tuple(self.transition(row[0]) for row in rows)
        return tuple(record for record in records if record is not None)

    def verify(self) -> bool:
        rows = self._connection.execute(
            """
            SELECT population_digest, canonical_json
            FROM policy_populations
            ORDER BY population_digest
            """
        ).fetchall()
        for digest_value, canonical_json in rows:
            try:
                population = PolicyPopulation.model_validate(json.loads(canonical_json))
            except (TypeError, ValueError, json.JSONDecodeError):
                return False
            if population_digest(population) != digest_value:
                return False
            if canonical_bytes(population.model_dump(mode="json")).decode("utf-8") != canonical_json:
                return False

        transitions = self._connection.execute(
            """
            SELECT transition_digest
            FROM policy_population_transitions
            ORDER BY transition_digest
            """
        ).fetchall()
        return all(self.replay(row[0]) for row in transitions)
