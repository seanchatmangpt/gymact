from __future__ import annotations

import pytest
from pydantic import ValidationError

from gymact.world import (
    AffordanceKind,
    EffectIntent,
    EffectPortRequired,
    EffectResult,
    WorldObject,
    WorldRuntime,
    construct,
    effect,
    proof,
    sense,
)


class ExampleWorldObject(WorldObject):
    value: int = 2

    @sense
    def read(self) -> dict[str, int]:
        """Read current value."""
        return {"value": self.value}

    @construct
    def add(self, left: int, right: int = 1) -> int:
        """Construct a pure derived value."""
        return left + right

    @effect(capability_ref="urn:test:capability:set")
    def propose(self, key: str, value: int) -> dict[str, object]:
        """Construct a consequence payload; do not perform it."""
        return {"key": key, "value": value}

    @proof
    def agrees(self, expected: int) -> bool:
        """Check a local proposition without consequence."""
        return self.value == expected


class ReceiptPort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, EffectIntent]] = []

    async def execute(self, *, subject_ref: str, intent: EffectIntent) -> EffectResult:
        self.calls.append((subject_ref, intent))
        return EffectResult(
            accepted=True,
            receipt={"receipt_id": "urn:test:receipt:1"},
            result={"observed": intent.payload},
        )


def test_metaclass_derives_pydantic_contracts_and_moves() -> None:
    obj = ExampleWorldObject(iri="urn:test:object")
    world = WorldRuntime()
    world.register(obj)

    moves = {move.affordance: move for move in world.moves()}
    assert set(moves) == {"read", "add", "propose", "agrees"}
    assert moves["read"].kind is AffordanceKind.SENSE
    assert moves["add"].kind is AffordanceKind.CONSTRUCT
    assert moves["propose"].kind is AffordanceKind.EFFECT
    assert moves["agrees"].kind is AffordanceKind.PROOF
    assert moves["propose"].capability_ref == "urn:test:capability:set"
    assert moves["add"].input_schema["required"] == ["left"]
    assert moves["add"].input_schema["properties"]["right"]["default"] == 1


@pytest.mark.asyncio
async def test_non_effect_affordances_execute_without_effect_port() -> None:
    world = WorldRuntime()
    world.register(ExampleWorldObject(iri="urn:test:object", value=7))

    assert await world.invoke(subject_ref="urn:test:object", affordance="read") == {"value": 7}
    assert (
        await world.invoke(
            subject_ref="urn:test:object",
            affordance="add",
            arguments={"left": 4},
        )
        == 5
    )
    assert await world.invoke(
        subject_ref="urn:test:object",
        affordance="agrees",
        arguments={"expected": 7},
    )


@pytest.mark.asyncio
async def test_effect_is_refused_without_consequence_port() -> None:
    world = WorldRuntime()
    obj = ExampleWorldObject(iri="urn:test:object")
    world.register(obj)

    # Direct Python call is construction only: it returns data and cannot actuate.
    assert obj.propose("x", 9) == {"key": "x", "value": 9}

    with pytest.raises(EffectPortRequired, match="REFUSED:EFFECT_PORT_REQUIRED"):
        await world.invoke(
            subject_ref="urn:test:object",
            affordance="propose",
            arguments={"key": "x", "value": 9},
        )


@pytest.mark.asyncio
async def test_effect_reaches_only_the_injected_receipted_port() -> None:
    port = ReceiptPort()
    world = WorldRuntime(effect_port=port)
    world.register(ExampleWorldObject(iri="urn:test:object"))

    result = await world.invoke(
        subject_ref="urn:test:object",
        affordance="propose",
        arguments={"key": "x", "value": 9},
    )

    assert result.accepted
    assert result.receipt == {"receipt_id": "urn:test:receipt:1"}
    assert len(port.calls) == 1
    subject_ref, intent = port.calls[0]
    assert subject_ref == "urn:test:object"
    assert intent == EffectIntent(
        capability_ref="urn:test:capability:set",
        payload={"key": "x", "value": 9},
    )


@pytest.mark.asyncio
async def test_pydantic_signature_contract_refuses_invalid_arguments() -> None:
    world = WorldRuntime()
    world.register(ExampleWorldObject(iri="urn:test:object"))

    with pytest.raises(ValidationError):
        await world.invoke(
            subject_ref="urn:test:object",
            affordance="add",
            arguments={"left": "not-an-int"},
        )


def test_metaclass_refuses_variadic_affordance() -> None:
    with pytest.raises(TypeError, match="AFFORDANCE_VARIADIC_REFUSED"):

        class Invalid(WorldObject):
            @construct
            def anything(self, *values: int) -> int:
                return sum(values)


def test_metaclass_refuses_private_affordance() -> None:
    with pytest.raises(TypeError, match="PRIVATE_AFFORDANCE_REFUSED"):

        class Invalid(WorldObject):
            @sense
            def _hidden(self) -> dict[str, int]:
                return {"hidden": 1}
