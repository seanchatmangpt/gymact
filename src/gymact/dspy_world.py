"""DSPy ReAct navigation over :mod:`gymact.world`.

This module is intentionally domain-free. The model receives only the lawful
moves manufactured by a ``WorldRuntime``. Effect moves still terminate at the
runtime's injected consequence port (normally ``BRCEEffectPort`` in production),
so ReAct chooses/navigates but never gains ambient DO authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gymact.world import WorldRuntime


@dataclass
class WorldAgentResult:
    outcome: str
    goal_accomplished: bool = False


class WorldReActAgent:
    """Bounded DSPy ReAct navigator over one registered ``WorldRuntime``."""

    def __init__(
        self,
        world: WorldRuntime,
        *,
        model_id: str = "groq/openai/gpt-oss-20b",
        max_iters: int = 6,
    ) -> None:
        try:
            import dspy
        except ImportError as exc:  # pragma: no cover - optional dependency contract
            raise ImportError(
                "gymact.dspy_world requires the optional 'dspy' extra: "
                "install with `pip install 'gymact[dspy]'` or `uv sync --extra dspy`."
            ) from exc

        self._dspy = dspy
        self._world = world
        self._model_id = model_id
        self._max_iters = max_iters

    async def run_goal(self, goal: str) -> WorldAgentResult:
        """Navigate only moves currently exposed by the world."""

        dspy = self._dspy

        class NavigateWorld(dspy.Signature):
            """Accomplish a goal by navigating only lawful world affordances.

            Never invent a hidden tool or treat a planned effect as an observed
            consequence.
            """

            goal: str = dspy.InputField(desc="the bounded world goal")
            available_moves: str = dspy.InputField(
                desc="machine-rendered lawful move topology available before reasoning"
            )
            outcome: str = dspy.OutputField(
                desc="honest summary of consequences actually observed through tools"
            )
            goal_accomplished: bool = dspy.OutputField(
                desc="true only when the tool trace establishes the goal"
            )

        move_text = "\n".join(
            f"{move.subject_ref}::{move.affordance} [{move.kind.value}] "
            f"schema={move.input_schema!r}"
            for move in self._world.moves()
        )
        react = dspy.ReAct(
            NavigateWorld,
            tools=self._world.dspy_tools(),
            max_iters=self._max_iters,
        )
        lm = dspy.LM(self._model_id, max_tokens=16000)
        with dspy.context(lm=lm):
            prediction = await react.acall(goal=goal, available_moves=move_text)

        return WorldAgentResult(
            outcome=prediction.outcome,
            goal_accomplished=bool(prediction.goal_accomplished),
        )
