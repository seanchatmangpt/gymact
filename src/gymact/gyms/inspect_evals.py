"""Real GymAct `Environment`/`EnvironmentProvider` over UK AISI's real
`inspect_ai` framework (the runtime `inspect_evals` tasks are built on top
of).

Target selection for this module: `~/autofde-lab/vendor/gyms/inspect-evals`
is a lazy git submodule with no checked-out content in this checkout (`ls`
comes back empty, only the parent directory exists), matching the same
situation `mcp_client_session.py` already documented for `mcpmark`. There is
therefore no externally checked-out `inspect_evals` task package to import a
named eval from directly. `docs/papers/gym-lock.ttl` does pin a real revision
(`afb:pinnedRevision "b935c0e5cfa04710f016f925db75d8e81413e2cf"`) for that
submodule, so the *target framework* is real and pinned even though this repo
cannot see its checked-out tree.

What is genuinely real and installable in this sandbox: the `inspect-ai`
PyPI package itself. This module depends on that real package directly --
`inspect_ai.Task`, `inspect_ai.eval()`, `inspect_ai.dataset.Sample`,
`inspect_ai.solver.generate`, `inspect_ai.scorer.match`, and
`inspect_ai.model.ModelOutput` are all real Inspect internals, not
GymAct-owned reimplementations. Because a full `inspect_evals` task package
is not checked out here, the environment materializes its own minimal but
real `inspect_ai.Task` (one `Sample`, the real `generate()` solver, the real
`match()` scorer) rather than importing an `inspect_evals.*` task registry
entry.

Model backend: `inspect_ai.model._providers.mockllm.MockLLM` is a real,
first-party Inspect model provider (`model="mockllm/<name>"`), not a GymAct
stub. This module defaults to it so real fully-local no-network-credential
episodes are possible. A caller with credentials may instead select a real
paid provider; this module does not special-case that path.

`actuate()` delegates execution to Inspect's public synchronous `eval()`
lifecycle owner on a worker thread. That wrapper owns Inspect platform init,
display selection, async-filesystem wrapping, task-display lifetime, and the
inner `eval_async()` call. GymAct remains async by awaiting the worker thread,
while `display="none"` prevents UI/display resources and `ctl_server=False`
prevents the default AF_UNIX control endpoint. For the locked Inspect release,
GymAct tracks every sample-event receive endpoint at creation, closes it at
drain completion, and performs a final idempotent close at eval return. The
compatibility bracket is restored after each evaluation and does not suppress
resource warnings. The returned objects are real `inspect_ai.log.EvalLog`
values populated by Inspect's own scorer.
"""

from __future__ import annotations

import asyncio
from threading import Lock
from typing import Any
from uuid import uuid4

from inspect_ai import Task
from inspect_ai import eval as inspect_eval
from inspect_ai.dataset import Sample
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import CORRECT, match
from inspect_ai.solver import generate

from gymact.models import Capability, Consequence

INSPECT_SOLVE_SAMPLE_CAPABILITY = Capability(
    iri="urn:gymact:inspect-evals:capability:solve_sample",
    title="Run a real inspect_ai.eval() pass over the materialized Task and record its real"
    " scorer verdict",
    consequence=Consequence.DO,
    binding="solve_sample",
)

_DEFAULT_MODEL = "mockllm/model"
_INSPECT_EVENT_DRAIN_LOCK = Lock()


def _run_inspect_eval(
    *,
    task: Task,
    model: str,
    model_args: dict[str, Any],
    log_dir: str,
) -> list[Any]:
    """Run Inspect while deterministically closing sample-event receivers.

    Inspect creates an AnyIO memory-object receive stream for every sample.
    In the locked release its drain path closes the sender and clears both
    active references without closing the receive endpoint. Capturing only the
    receiver visible at drain time is insufficient when lifecycle transitions
    replace or clear the active sample before adapter cleanup.

    The repair stays at the adapter boundary: wrap Inspect's real emitter start
    to record every receive endpoint it creates, wrap the real drain to close
    the current endpoint when ownership ends, then idempotently close all
    captured endpoints after the public `eval()` lifecycle returns. No warning
    is filtered and no Inspect scoring or authority behavior is replaced.
    """
    from inspect_ai.hooks import _hooks as inspect_hooks

    original_start = inspect_hooks.start_sample_event_emitter
    original_drain = inspect_hooks.drain_sample_events
    owned_receives: list[Any] = []

    def start_sample_event_emitter_tracking_receive() -> None:
        original_start()
        active = inspect_hooks.sample_active()
        receive = active.event_receive if active is not None else None
        if receive is not None:
            owned_receives.append(receive)

    async def drain_sample_events_closing_receive() -> None:
        active = inspect_hooks.sample_active()
        receive = active.event_receive if active is not None else None
        try:
            await original_drain()
        finally:
            if receive is not None:
                receive.close()

    with _INSPECT_EVENT_DRAIN_LOCK:
        inspect_hooks.start_sample_event_emitter = start_sample_event_emitter_tracking_receive
        inspect_hooks.drain_sample_events = drain_sample_events_closing_receive
        try:
            return inspect_eval(
                task,
                model=model,
                model_args=model_args,
                log_dir=log_dir,
                display="none",
                ctl_server=False,
            )
        finally:
            inspect_hooks.start_sample_event_emitter = original_start
            inspect_hooks.drain_sample_events = original_drain
            for receive in owned_receives:
                receive.close()


class InspectEvalsEnvironment:
    """Wrap one real Inspect task and expose its bounded solve operation."""

    def __init__(
        self,
        *,
        task: Task,
        model: str,
        model_args: dict[str, Any],
        log_dir: str,
        requires_authority: bool = False,
    ) -> None:
        self.environment_id = f"urn:gymact:inspect-evals:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._task = task
        self._model = model
        self._model_args = model_args
        self._log_dir = log_dir
        self._last_result: dict[str, Any] = {
            "attempted": False,
            "status": None,
            "score_value": None,
            "score_answer": None,
            "solved": False,
        }
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return (INSPECT_SOLVE_SAMPLE_CAPABILITY,)

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return dict(self._last_result)

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        self._ensure_open()
        if capability.binding != "solve_sample":
            raise ValueError(f"unsupported inspect-evals binding: {capability.binding}")

        before = dict(self._last_result)

        logs = await asyncio.to_thread(
            _run_inspect_eval,
            task=self._task,
            model=self._model,
            model_args=self._model_args,
            log_dir=self._log_dir,
        )
        log = logs[0]

        score_value: str | None = None
        score_answer: str | None = None
        solved = False
        if log.samples:
            sample_scores = log.samples[0].scores or {}
            match_score = sample_scores.get("match")
            if match_score is not None:
                score_value = str(match_score.value)
                score_answer = str(match_score.answer) if match_score.answer is not None else None
                solved = match_score.value == CORRECT

        self._last_result = {
            "attempted": True,
            "status": log.status,
            "score_value": score_value,
            "score_answer": score_answer,
            "solved": solved,
        }
        after = dict(self._last_result)
        return {"before": before, "after": after}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = await self.observe()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return dict(self._last_result)

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._last_result = dict(checkpoint)

    async def teardown(self) -> None:
        self._closed = True


class InspectEvalsProvider:
    """Materialize a real minimal Inspect task and model backend."""

    name = "inspect-evals"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> InspectEvalsEnvironment:
        del scenario
        sample_input = config.get("input", "What is 2 + 2? Answer with just the number.")
        sample_target = config.get("target", "4")
        if not isinstance(sample_input, str) or not sample_input:
            raise TypeError("config.input must be a non-empty string")
        if not isinstance(sample_target, str) or not sample_target:
            raise TypeError("config.target must be a non-empty string")

        model = config.get("model", _DEFAULT_MODEL)
        if not isinstance(model, str) or not model:
            raise TypeError("config.model must be a non-empty string")

        model_args_config = config.get("model_args", {})
        if not isinstance(model_args_config, dict):
            raise TypeError("config.model_args must be an object")
        model_args = dict(model_args_config)
        custom_outputs = model_args.get("custom_outputs")
        if (
            isinstance(custom_outputs, list)
            and custom_outputs
            and isinstance(custom_outputs[0], str)
        ):
            model_args["custom_outputs"] = [
                ModelOutput.from_content(model=model.split("/", 1)[-1] or "model", content=text)
                for text in custom_outputs
            ]

        log_dir = config.get("log_dir", "./.inspect_logs")
        if not isinstance(log_dir, str) or not log_dir:
            raise TypeError("config.log_dir must be a non-empty string")

        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")

        task = Task(
            dataset=[Sample(input=sample_input, target=sample_target)],
            solver=[generate()],
            scorer=match(),
        )

        return InspectEvalsEnvironment(
            task=task,
            model=model,
            model_args=model_args,
            log_dir=log_dir,
            requires_authority=requires_authority,
        )