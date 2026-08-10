"""A generic, gym-agnostic DSPy ReAct agent over GymAct's own kernel surface.

This module has zero knowledge of any specific benchmark, gym, or downstream
consumer (autofde-lab or otherwise). It exists so any real `GymAct` provider's
capability surface can be Chicago-style exercised by a real, LLM-driven agent
-- the same way a hand-scripted `materialize -> act -> verify -> teardown`
test proves a gym's mechanics work, this proves a gym's capability surface is
navigable by a real reasoning loop, without hardcoding per-gym payload shapes.

Tool-wrapping deliberately never bypasses the kernel: every DO-consequence
capability call still goes through `GymAct.act()` (authority, CapabilityScope,
and consequence-law checks all still apply exactly as they do for any other
caller). This module adds no new authority path.

Grounding, not guessing
------------------------
The concrete defect this module is built to prevent: an LLM proposing an
actuation payload that references a resource it was never actually shown --
inventing a plausible-looking name instead of using a real one. GymAct's own
`Observation.state` is the only source of truth about what currently exists
in an episode's world. `_collect_string_leaves()` walks the most recent real
`observe()` result into a flat set of every real string value it contains;
`_assert_payload_is_grounded()` then refuses (raises `UngroundedActuationRefused`,
never silently drops or "fixes" the payload) any proposed DO-capability
payload whose string values are not a subset of that real, current set. This
is a generic, per-gym-payload-schema-agnostic mechanical guard -- it does not
know or need to know what a "name" or "target" field is called in any given
gym's capability payload; it only knows what the episode's own most recent
real observation actually contained.

This is deliberately a MECHANICAL check, not prompt engineering alone --
telling an LLM "don't guess" in a system prompt is not a guarantee; refusing
an ungrounded call at the tool-call boundary is.

Not every DO capability references an existing resource, though -- some
legitimately CREATE one (e.g. a `set` capability introducing a brand-new
key). Blanket-refusing every novel value would also block legitimate
creation, which is not the defect this guard targets. `create_capable_bindings`
lets a caller name exactly which bindings are real creators, per gym; the
default is empty (fail-closed), so grounding is enforced everywhere until a
caller explicitly says otherwise for a specific, named binding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gymact.kernel import GymAct
    from gymact.models import Capability, Observation


class UngroundedActuationRefused(ValueError):
    """A proposed DO-capability payload referenced a value never present in
    this episode's most recent real `observe()` result -- refused before
    any real `act()` call, not silently coerced or dropped."""

    def __init__(self, capability_ref: str, ungrounded_values: tuple[str, ...]) -> None:
        self.capability_ref = capability_ref
        self.ungrounded_values = ungrounded_values
        super().__init__(
            f"REFUSED:UNGROUNDED_ACTUATION capability={capability_ref!r} "
            f"values_not_in_last_real_observation={ungrounded_values!r}"
        )


def _collect_string_leaves(value: Any) -> set[str]:
    """Real, generic walk of a JSON-like structure collecting every string
    leaf value AND every dict key -- the vocabulary of real facts a payload
    may reference.

    Dict keys matter as much as values here: a real identifier a payload
    would reference (e.g. `{"key": "counter"}` naming an existing state
    entry) very often IS a dict key in `Observation.state` -- `{"counter": 1}`
    -- not a value. A version of this walk that only collected values would
    never ground the single most common real reference shape and would
    refuse every legitimate reference to an existing key; caught by a real
    test (`test_real_observe_grounds_a_real_existing_key`) failing against a
    real `MemoryProvider` episode before this fix."""
    found: set[str] = set()
    if isinstance(value, str):
        found.add(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                found.add(key)
            found |= _collect_string_leaves(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found |= _collect_string_leaves(item)
    return found


def _collect_only_string_values(value: Any) -> set[str]:
    """Same shape of walk as `_collect_string_leaves`, but NEVER treats a
    dict key as a candidate value -- at any depth. Dict keys anywhere inside
    a proposed payload are argument/field names from the capability's own
    schema, not data; only actual string values can reference something that
    should already exist in a real observation."""
    found: set[str] = set()
    if isinstance(value, str):
        found.add(value)
    elif isinstance(value, dict):
        for item in value.values():
            found |= _collect_only_string_values(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found |= _collect_only_string_values(item)
    return found


def _collect_payload_string_values(payload: dict[str, Any]) -> set[str]:
    """Walk a proposed actuation payload collecting only its string VALUES,
    never its own dict keys, at any depth.

    Deliberately asymmetric with `_collect_string_leaves` (used for the
    observation side, where keys ARE real entity names): a payload's dict
    keys are argument/field names from the capability's own schema
    (`"key"`, `"amount"`, `"value"`, ...) -- schema, not content, and must
    never be required to appear in a real observation. Only the actual DATA
    a payload carries can reference something that should already exist.
    Caught by a real test (`test_grounded_payload_is_accepted_without_raising`
    failing with `values_not_in_last_real_observation=('key',)`) before this
    fix -- a naive symmetric reuse of `_collect_string_leaves` here flagged
    the payload's own argument name as an ungrounded reference."""
    return _collect_only_string_values(payload)


def _assert_payload_is_grounded(
    *, capability_ref: str, payload: dict[str, Any], grounded_facts: frozenset[str]
) -> None:
    proposed = _collect_payload_string_values(payload)
    ungrounded = tuple(sorted(proposed - grounded_facts))
    if ungrounded:
        raise UngroundedActuationRefused(capability_ref, ungrounded)


@dataclass
class AgentStep:
    """One real tool invocation this agent actually made, in order."""

    tool_name: str
    payload: dict[str, Any]
    result: Any


@dataclass
class AgentRunResult:
    """What a bounded `run_goal()` call actually produced -- the real
    ReAct-loop output plus the real, ordered trace of tool calls it made."""

    outcome: str
    steps: list[AgentStep] = field(default_factory=list)
    final_observation: dict[str, Any] | None = None


class GymActReActAgent:
    """Generic, gym-agnostic DSPy ReAct agent driving one real, already-
    materialized GymAct episode through the kernel's own real `observe()`/
    `act()` surface.

    Requires the optional `dspy` extra (`pip install 'gymact[dspy]'`); this
    module itself only imports `dspy` lazily inside `__init__`, so importing
    `gymact.dspy_agent` never fails when the extra isn't installed -- only
    constructing an agent does, with a real, named `ImportError` guidance
    message, matching this repo's own optional-dependency convention.
    """

    def __init__(
        self,
        gym: GymAct,
        episode_id: str,
        *,
        judge_model_id: str = "groq/openai/gpt-oss-20b",
        authority_ref: str | None = None,
        max_iters: int = 6,
        create_capable_bindings: frozenset[str] = frozenset(),
    ) -> None:
        try:
            import dspy
        except ImportError as exc:  # pragma: no cover - exercised via importorskip in tests
            raise ImportError(
                "gymact.dspy_agent requires the optional 'dspy' extra: "
                "install with `pip install 'gymact[dspy]'` or `uv sync --extra dspy`."
            ) from exc

        self._dspy = dspy
        self._gym = gym
        self._episode_id = episode_id
        self._judge_model_id = judge_model_id
        self._authority_ref = authority_ref
        self._max_iters = max_iters
        # Bindings whose real semantics legitimately introduce a brand-new
        # fact (e.g. a "set" capability creating a not-yet-observed key) are
        # exempt from the grounding guard -- the guard's job is refusing an
        # invented REFERENCE to something that should already exist, not
        # refusing every capability that can ever mention a novel value.
        # Defaults to empty (fail-closed: nothing is exempt) -- a caller must
        # explicitly name which bindings are real creators, gym by gym.
        self._create_capable_bindings = create_capable_bindings
        self._last_observation: Observation | None = None
        self._grounded_facts: frozenset[str] = frozenset()

    async def _refresh_observation(self) -> dict[str, Any]:
        observation = await self._gym.observe(self._episode_id)
        self._last_observation = observation
        self._grounded_facts = frozenset(_collect_string_leaves(observation.state))
        return observation.state

    def _do_capabilities(self) -> tuple[Capability, ...]:
        from gymact.models import Consequence

        return tuple(
            capability
            for capability in self._gym.capabilities(self._episode_id)
            if capability.consequence is Consequence.DO
        )

    def _build_tools(self, steps: list[AgentStep]) -> list[Any]:
        dspy = self._dspy

        async def observe_tool() -> dict[str, Any]:
            """Read the real, current state of this episode. Call this
            before proposing any action -- an action referencing a value
            not present in the most recent real observation is refused."""
            state = await self._refresh_observation()
            steps.append(AgentStep(tool_name="observe", payload={}, result=state))
            return state

        tools: list[Any] = [dspy.Tool(observe_tool, name="observe")]

        for capability in self._do_capabilities():

            def make_actuator(cap: Capability) -> Any:
                async def actuate_tool(payload: dict[str, Any] | None = None) -> dict[str, Any]:
                    from gymact.models import ActuationIntent

                    real_payload = payload or {}
                    if cap.binding not in self._create_capable_bindings:
                        _assert_payload_is_grounded(
                            capability_ref=cap.iri,
                            payload=real_payload,
                            grounded_facts=self._grounded_facts,
                        )
                    result = await self._gym.act(
                        ActuationIntent(
                            episode_id=self._episode_id,
                            capability=cap.iri,
                            payload=real_payload,
                            authority_ref=self._authority_ref,
                        )
                    )
                    outcome = {
                        "accepted": result.accepted,
                        "standing": result.standing.value,
                        "reason": result.receipt.reason,
                    }
                    steps.append(
                        AgentStep(tool_name=cap.binding, payload=real_payload, result=outcome)
                    )
                    if result.accepted:
                        await self._refresh_observation()
                    return outcome

                actuate_tool.__doc__ = (
                    f"{cap.title} (real DO capability {cap.iri!r}). "
                    "Every string value in payload must already appear, verbatim, "
                    "in the most recent real observe() output -- never invent one."
                )
                return actuate_tool

            tools.append(dspy.Tool(make_actuator(capability), name=capability.binding))

        return tools

    async def run_goal(self, goal: str) -> AgentRunResult:
        """Run a bounded real ReAct loop toward `goal` against this real,
        already-materialized episode. Always starts from a real observation."""
        dspy = self._dspy
        steps: list[AgentStep] = []
        await self._refresh_observation()
        tools = self._build_tools(steps)

        class AccomplishGymGoal(dspy.Signature):
            """Accomplish the stated goal against a real, bounded gym episode
            using only the provided tools. Every tool call must reference
            only values already present in a real prior `observe()` result --
            never invent a resource name, key, or identifier."""

            goal: str = dspy.InputField(desc="the real goal to accomplish in this episode")
            outcome: str = dspy.OutputField(
                desc="a real, honest summary of what was actually accomplished"
            )

        react = dspy.ReAct(AccomplishGymGoal, tools=tools, max_iters=self._max_iters)
        lm = dspy.LM(self._judge_model_id)
        with dspy.context(lm=lm):
            prediction = await react.acall(goal=goal)

        final_state = self._last_observation.state if self._last_observation else None
        return AgentRunResult(
            outcome=prediction.outcome, steps=steps, final_observation=final_state
        )
