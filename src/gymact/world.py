"""Domain-free Python affordances for bounded executable worlds.

The public ontology remains the semantic authority. This module provides the
Python execution-facing side of that boundary: ordinary Pydantic objects whose
decorated methods are classified as observation, construction, consequence
intent, or proof affordances.

The decorators and metaclass deliberately contain no benchmark, cloud,
Kubernetes, career, ATS, or other domain vocabulary. A new domain should add
objects/profile data, not a new Python execution primitive.

Consequence law
---------------
An ``@effect`` method is *only* an intent constructor. Calling it cannot
perform a consequence. ``WorldRuntime.invoke`` routes the resulting
``EffectIntent`` through an injected ``EffectPort``. Production callers can
use ``BRCEEffectPort`` so DSPy/ReAct receives navigation affordances but never
ambient execution authority.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from enum import StrEnum
from inspect import Parameter, isawaitable, signature
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, get_type_hints, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, create_model

if TYPE_CHECKING:
    from gymact.brce import BRCEBroker, BrokerRequest


class AffordanceKind(StrEnum):
    """Universal execution roles. None are domain-specific."""

    SENSE = "sense"
    CONSTRUCT = "construct"
    EFFECT = "effect"
    PROOF = "proof"


class EffectIntent(BaseModel):
    """Constructed consequential intent. It is not authority or consequence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_ref: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class EffectResult(BaseModel):
    """Receipted disposition returned by the only allowed consequence port."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    accepted: bool
    receipt: Any
    result: Any = None


class AffordanceContract(BaseModel):
    """Machine-inspectable contract derived from one decorated method."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    name: str
    kind: AffordanceKind
    description: str = ""
    capability_ref: str | None = None
    input_model: type[BaseModel]

    @property
    def input_schema(self) -> dict[str, Any]:
        return self.input_model.model_json_schema()


class Move(BaseModel):
    """One lawful affordance exposed by a concrete world object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_ref: str
    affordance: str
    kind: AffordanceKind
    capability_ref: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class _AffordanceMarker:
    __slots__ = ("kind", "capability_ref")

    def __init__(self, kind: AffordanceKind, capability_ref: str | None = None) -> None:
        self.kind = kind
        self.capability_ref = capability_ref


def _mark(
    fn: Callable[..., Any],
    *,
    kind: AffordanceKind,
    capability_ref: str | None = None,
) -> Callable[..., Any]:
    setattr(fn, "__gymact_affordance__", _AffordanceMarker(kind, capability_ref))
    return fn


def sense(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Declare a non-consequential observation affordance."""

    return _mark(fn, kind=AffordanceKind.SENSE)


def construct(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Declare a non-consequential construction affordance."""

    return _mark(fn, kind=AffordanceKind.CONSTRUCT)


def effect(*, capability_ref: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Declare an intent-construction affordance for one semantic capability."""

    if not capability_ref:
        raise ValueError("EFFECT_CAPABILITY_REF_REQUIRED")

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        return _mark(fn, kind=AffordanceKind.EFFECT, capability_ref=capability_ref)

    return decorate


def proof(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Declare a non-consequential verification/evidence affordance."""

    return _mark(fn, kind=AffordanceKind.PROOF)


def _input_model(owner_name: str, method_name: str, fn: Callable[..., Any]) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    hints = get_type_hints(fn)
    for name, parameter in signature(fn).parameters.items():
        if name in {"self", "cls"}:
            continue
        if parameter.kind in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}:
            raise TypeError(f"AFFORDANCE_VARIADIC_REFUSED:{owner_name}.{method_name}")
        annotation = hints.get(name, Any)
        default = ... if parameter.default is Parameter.empty else parameter.default
        fields[name] = (annotation, default)
    return create_model(f"{owner_name}_{method_name}_Input", **fields)


class WorldObjectMeta(type(BaseModel)):
    """Derive affordance contracts from decorated methods at class creation."""

    def __new__(
        mcls,
        name: str,
        bases: tuple[type[Any], ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> type[Any]:
        cls = super().__new__(mcls, name, bases, namespace, **kwargs)
        contracts: dict[str, AffordanceContract] = {}
        for base in bases:
            contracts.update(getattr(base, "__affordances__", {}))

        for method_name, member in namespace.items():
            marker = getattr(member, "__gymact_affordance__", None)
            if marker is None:
                continue
            if method_name.startswith("_"):
                raise TypeError(f"PRIVATE_AFFORDANCE_REFUSED:{name}.{method_name}")
            input_model = _input_model(name, method_name, member)
            contracts[method_name] = AffordanceContract(
                name=method_name,
                kind=marker.kind,
                description=(member.__doc__ or "").strip(),
                capability_ref=marker.capability_ref,
                input_model=input_model,
            )

        cls.__affordances__ = contracts
        return cls


class WorldObject(BaseModel, metaclass=WorldObjectMeta):
    """Base for ordinary Python objects participating in a bounded world."""

    model_config = ConfigDict(extra="forbid")

    iri: str = Field(min_length=1)
    __affordances__: ClassVar[dict[str, AffordanceContract]]

    @classmethod
    def affordances(cls) -> tuple[AffordanceContract, ...]:
        return tuple(cls.__affordances__.values())


@runtime_checkable
class EffectPort(Protocol):
    """Exclusive consequence port supplied by the host runtime."""

    async def execute(self, *, subject_ref: str, intent: EffectIntent) -> EffectResult: ...


@runtime_checkable
class BrokerRequestFactory(Protocol):
    """Manufacture an admitted BRCE request from a generic effect intent."""

    def __call__(self, *, subject_ref: str, intent: EffectIntent) -> BrokerRequest: ...


class BRCEEffectPort:
    """Adapter from generic world effects to GymAct's existing BRCE-only DO path.

    The request factory owns admission-specific facts (subject revision, grant,
    expected effect, policy revision). This adapter owns no domain semantics
    and does not manufacture authority.
    """

    def __init__(self, broker: BRCEBroker, request_factory: BrokerRequestFactory) -> None:
        self._broker = broker
        self._request_factory = request_factory

    async def execute(self, *, subject_ref: str, intent: EffectIntent) -> EffectResult:
        request = self._request_factory(subject_ref=subject_ref, intent=intent)
        transition = await self._broker.execute(request)
        return EffectResult(
            accepted=transition.actuation.accepted,
            receipt=transition.receipt,
            result=transition,
        )


class EffectPortRequired(RuntimeError):
    """An effect was selected without a configured consequence port."""


class WorldRuntime:
    """Object graph + affordance dispatcher suitable for DSPy ReAct navigation."""

    def __init__(self, *, effect_port: EffectPort | None = None) -> None:
        self._objects: dict[str, WorldObject] = {}
        self._effect_port = effect_port

    def register(self, obj: WorldObject) -> None:
        if obj.iri in self._objects:
            raise ValueError(f"DUPLICATE_WORLD_OBJECT:{obj.iri}")
        self._objects[obj.iri] = obj

    def objects(self) -> tuple[WorldObject, ...]:
        return tuple(self._objects.values())

    def moves(self) -> tuple[Move, ...]:
        """Manufacture the current lawful action topology for a planner."""

        return tuple(
            Move(
                subject_ref=obj.iri,
                affordance=contract.name,
                kind=contract.kind,
                capability_ref=contract.capability_ref,
                input_schema=contract.input_schema,
                description=contract.description,
            )
            for obj in self._objects.values()
            for contract in obj.affordances()
        )

    async def invoke(
        self,
        *,
        subject_ref: str,
        affordance: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> Any:
        try:
            obj = self._objects[subject_ref]
        except KeyError as exc:
            raise KeyError(f"UNKNOWN_WORLD_OBJECT:{subject_ref}") from exc
        try:
            contract = obj.__affordances__[affordance]
        except KeyError as exc:
            raise KeyError(f"UNKNOWN_AFFORDANCE:{subject_ref}:{affordance}") from exc

        validated = contract.input_model.model_validate(dict(arguments or {}))
        method = getattr(obj, affordance)
        value = method(**validated.model_dump())
        if isawaitable(value):
            value = await value

        if contract.kind is not AffordanceKind.EFFECT:
            return value

        if self._effect_port is None:
            raise EffectPortRequired(
                f"REFUSED:EFFECT_PORT_REQUIRED subject={subject_ref!r} affordance={affordance!r}"
            )

        if isinstance(value, EffectIntent):
            intent = value
            if intent.capability_ref != contract.capability_ref:
                raise ValueError("EFFECT_CAPABILITY_MISMATCH")
        else:
            if isinstance(value, BaseModel):
                payload = value.model_dump(mode="python")
            elif isinstance(value, Mapping):
                payload = dict(value)
            else:
                raise TypeError("EFFECT_CONSTRUCTOR_MUST_RETURN_MAPPING_OR_EFFECT_INTENT")
            intent = EffectIntent(
                capability_ref=contract.capability_ref or "",
                payload=payload,
            )

        result = await self._effect_port.execute(subject_ref=subject_ref, intent=intent)
        if result.receipt is None:
            raise RuntimeError("UNRECEIPTED_EFFECT_RESULT_REFUSED")
        return result

    def dspy_tools(self) -> list[Any]:
        """Manufacture real ``dspy.Tool`` objects from the current world topology."""

        try:
            import dspy
        except ImportError as exc:
            raise ImportError(
                "WorldRuntime.dspy_tools requires the optional 'dspy' extra: "
                "`pip install 'gymact[dspy]'` or `uv sync --extra dspy`."
            ) from exc

        tools: list[Any] = []
        for subject_ref, obj in self._objects.items():
            for contract in obj.affordances():
                tool_name = _tool_name(subject_ref, contract.name)

                def make_tool(
                    subject: str,
                    spec: AffordanceContract,
                ) -> Callable[[dict[str, Any] | None], Awaitable[Any]]:
                    async def invoke_tool(arguments: dict[str, Any] | None = None) -> Any:
                        return await self.invoke(
                            subject_ref=subject,
                            affordance=spec.name,
                            arguments=arguments,
                        )

                    invoke_tool.__doc__ = _tool_description(subject, spec)
                    return invoke_tool

                tools.append(dspy.Tool(make_tool(subject_ref, contract), name=tool_name))
        return tools


def _tool_name(subject_ref: str, affordance: str) -> str:
    safe_subject = "".join(ch if ch.isalnum() else "_" for ch in subject_ref).strip("_")
    safe_affordance = "".join(ch if ch.isalnum() else "_" for ch in affordance).strip("_")
    return f"{safe_subject}__{safe_affordance}"[-120:]


def _tool_description(subject_ref: str, contract: AffordanceContract) -> str:
    authority_note = (
        "This tool only constructs and submits an intent through the configured effect port; "
        "the model has no ambient execution authority."
        if contract.kind is AffordanceKind.EFFECT
        else "This affordance is non-consequential."
    )
    return (
        f"subject={subject_ref!r}; role={contract.kind.value}; "
        f"input_schema={contract.input_schema!r}. {contract.description} {authority_note}"
    ).strip()
