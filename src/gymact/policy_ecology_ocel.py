"""OCEL 2.0 projection of policy-population lifecycle state.

These events are process evidence about candidate population manufacture,
conditioning, and evaluation. They are not execution receipts and never imply
that a policy was actuated.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from gymact.models import FrozenModel
from gymact.ocel import digest_ocel_log, validate_ocel_log


class PolicyEcologyEventType(StrEnum):
    MANUFACTURE = "manufacture_policy_population"
    CONDITION = "condition_policy_population"
    EVALUATE = "evaluate_policy_population"


class PolicyEcologyEvent(FrozenModel):
    event_id: str = Field(min_length=1)
    event_type: PolicyEcologyEventType
    occurred_at: str = Field(min_length=1)
    population_digest: str = Field(min_length=1)
    population_kind: str = Field(min_length=1)
    parent_population_digest: str | None = None
    cue: float | None = None
    design_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()
    attributes: dict[str, str | float | int | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def lifecycle_contract(self) -> "PolicyEcologyEvent":
        if (
            self.event_type is PolicyEcologyEventType.CONDITION
            and self.parent_population_digest is None
        ):
            raise ValueError("REFUSED:CONDITION_EVENT_REQUIRES_PARENT_POPULATION")
        if self.event_type is PolicyEcologyEventType.CONDITION and self.cue is None:
            raise ValueError("REFUSED:CONDITION_EVENT_REQUIRES_CUE")
        if (
            self.event_type is not PolicyEcologyEventType.CONDITION
            and self.parent_population_digest is not None
        ):
            raise ValueError("REFUSED:NON_CONDITION_EVENT_CANNOT_DECLARE_PARENT")
        return self


def _event_attributes(event: PolicyEcologyEvent) -> list[dict[str, Any]]:
    attributes: list[dict[str, Any]] = [
        {"name": "standing", "value": "CANDIDATE"},
        {"name": "candidate_only", "value": "true"},
        {"name": "population_kind", "value": event.population_kind},
    ]
    if event.cue is not None:
        attributes.append({"name": "cue", "value": event.cue})
    if event.design_ref is not None:
        attributes.append({"name": "design_ref", "value": event.design_ref})
    for evidence_ref in event.evidence_refs:
        attributes.append({"name": "evidence_ref", "value": evidence_ref})
    for name, value in sorted(event.attributes.items()):
        attributes.append({"name": name, "value": value})
    return attributes


def policy_ecology_events_to_ocel(
    events: tuple[PolicyEcologyEvent, ...],
) -> dict[str, Any]:
    """Project candidate population lifecycle events to official OCEL 2.0 JSON."""
    if not events:
        raise ValueError("REFUSED:POLICY_ECOLOGY_OCEL_REQUIRES_EVENT")

    event_ids = [event.event_id for event in events]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("REFUSED:DUPLICATE_POLICY_ECOLOGY_EVENT_ID")

    population_ids: set[str] = set()
    kinds: dict[str, str] = {}
    projected_events: list[dict[str, Any]] = []

    for event in events:
        population_ids.add(event.population_digest)
        kinds[event.population_digest] = event.population_kind

        relationships = [
            {
                "objectId": event.population_digest,
                "qualifier": "population",
            }
        ]
        if event.parent_population_digest is not None:
            population_ids.add(event.parent_population_digest)
            relationships.append(
                {
                    "objectId": event.parent_population_digest,
                    "qualifier": "parent_population",
                }
            )

        projected_events.append(
            {
                "id": event.event_id,
                "type": event.event_type.value,
                "time": event.occurred_at,
                "attributes": _event_attributes(event),
                "relationships": relationships,
            }
        )

    objects = [
        {
            "id": population_id,
            "type": "policy_population",
            "attributes": (
                [{"name": "population_kind", "value": kinds[population_id]}]
                if population_id in kinds
                else []
            ),
        }
        for population_id in sorted(population_ids)
    ]

    event_types = [
        {
            "name": event_type.value,
            "attributes": [
                {"name": "standing", "type": "string"},
                {"name": "candidate_only", "type": "string"},
                {"name": "population_kind", "type": "string"},
            ],
        }
        for event_type in sorted(
            {event.event_type for event in events},
            key=lambda item: item.value,
        )
    ]

    log = {
        "eventTypes": event_types,
        "objectTypes": [
            {
                "name": "policy_population",
                "attributes": [{"name": "population_kind", "type": "string"}],
            }
        ],
        "events": projected_events,
        "objects": objects,
    }
    validate_ocel_log(log)
    return log


def policy_ecology_ocel_digest(events: tuple[PolicyEcologyEvent, ...]) -> str:
    return digest_ocel_log(policy_ecology_events_to_ocel(events))
