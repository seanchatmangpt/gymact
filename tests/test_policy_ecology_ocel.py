from __future__ import annotations

import pytest

from gymact.policy_ecology_ocel import (
    PolicyEcologyEvent,
    PolicyEcologyEventType,
    policy_ecology_events_to_ocel,
    policy_ecology_ocel_digest,
)


def events() -> tuple[PolicyEcologyEvent, ...]:
    return (
        PolicyEcologyEvent(
            event_id="evt:manufacture",
            event_type=PolicyEcologyEventType.MANUFACTURE,
            occurred_at="2026-09-25T12:00:00Z",
            population_digest="pop:0",
            population_kind="adaptive",
            design_ref="design:mission:exploration",
            evidence_refs=("https://arxiv.org/abs/2609.29423",),
        ),
        PolicyEcologyEvent(
            event_id="evt:condition",
            event_type=PolicyEcologyEventType.CONDITION,
            occurred_at="2026-09-25T12:01:00Z",
            population_digest="pop:1",
            population_kind="adaptive",
            parent_population_digest="pop:0",
            cue=0.75,
        ),
        PolicyEcologyEvent(
            event_id="evt:evaluate",
            event_type=PolicyEcologyEventType.EVALUATE,
            occurred_at="2026-09-25T12:02:00Z",
            population_digest="pop:1",
            population_kind="adaptive",
            attributes={"mean_absolute_error": 0.03},
        ),
    )


def test_policy_ecology_lifecycle_is_official_schema_valid_ocel() -> None:
    log = policy_ecology_events_to_ocel(events())
    assert [event["type"] for event in log["events"]] == [
        "manufacture_policy_population",
        "condition_policy_population",
        "evaluate_policy_population",
    ]
    assert {obj["id"] for obj in log["objects"]} == {"pop:0", "pop:1"}


def test_condition_event_links_parent_and_child_population() -> None:
    log = policy_ecology_events_to_ocel(events())
    conditioned = log["events"][1]
    assert conditioned["relationships"] == [
        {"objectId": "pop:1", "qualifier": "population"},
        {"objectId": "pop:0", "qualifier": "parent_population"},
    ]
    attributes = {item["name"]: item["value"] for item in conditioned["attributes"]}
    assert attributes["standing"] == "CANDIDATE"
    assert attributes["candidate_only"] == "true"
    assert "authority" not in attributes


def test_ocel_digest_is_stable_for_same_lifecycle() -> None:
    assert policy_ecology_ocel_digest(events()) == policy_ecology_ocel_digest(events())


def test_condition_event_requires_parent_and_cue() -> None:
    with pytest.raises(
        ValueError,
        match="REFUSED:CONDITION_EVENT_REQUIRES_PARENT_POPULATION",
    ):
        PolicyEcologyEvent(
            event_id="bad",
            event_type=PolicyEcologyEventType.CONDITION,
            occurred_at="2026-09-25T12:00:00Z",
            population_digest="pop:1",
            population_kind="adaptive",
            cue=0.5,
        )


def test_empty_lifecycle_is_refused() -> None:
    with pytest.raises(ValueError, match="REFUSED:POLICY_ECOLOGY_OCEL_REQUIRES_EVENT"):
        policy_ecology_events_to_ocel(())
