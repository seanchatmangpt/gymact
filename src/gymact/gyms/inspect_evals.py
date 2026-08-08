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
PyPI package itself (`pip install inspect-ai` succeeds; verified in this
session, `inspect_ai.__version__ == "0.3.252"`). This module depends on that
real package directly -- `inspect_ai.Task`, `inspect_ai.eval()`,
`inspect_ai.dataset.Sample`, `inspect_ai.solver.generate`,
`inspect_ai.scorer.match`, and `inspect_ai.model.ModelOutput` are all real
Inspect internals, not GymAct-owned reimplementations. Because a full
`inspect_evals` task package is not checked out here, the environment
materializes its own minimal but real `inspect_ai.Task` (one `Sample`, the
real `generate()` solver, the real `match()` scorer) rather than importing an
`inspect_evals.*` task registry entry -- the same "generic adapter over the
target framework's own API surface" posture `mcp_client_session.py` and
`discovered.py` already use, not a simulation of what a real task looks like.

Model backend: `inspect_ai.model._providers.mockllm.MockLLM` is a real,
first-party Inspect model provider (`model="mockllm/<name>"`), not a GymAct
stub -- it exists in Inspect's own `_providers` package specifically so
evals can run deterministically without a paid API key. This module defaults
to it (`config["model"]` defaults to `"mockllm/model"` with
`config["model_args"]["custom_outputs"]` supplying real
`inspect_ai.model.ModelOutput` completions), which is what makes real,
fully-local, no-network-credential episodes possible. `config["model"]` may
instead be pointed at a real paid provider (e.g. `"openai/gpt-4o"`) by a
caller that has credentials -- this module does not special-case that path;
it always calls the real `inspect_ai.eval()`.

`actuate()` really calls `inspect_ai.eval_async()` for real -- one real
subprocess-free, in-process Inspect run over the real `Task`, producing a real
`inspect_ai.log.EvalLog` with a real `EvalLog.results` populated by
Inspect's own `match()` scorer. No pass/fail is fabricated: `verify()` reads
`EvalLog.samples[0].scores["match"].value` (Inspect's own `CORRECT`/
`INCORRECT`/`PARTIAL`/`NOANSWER` `Value` grade) exactly as Inspect produced
it.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from inspect_ai import Task
from inspect_ai import eval_async as inspect_eval_async
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


class InspectEvalsEnvironment:
    """Wraps one real `inspect_ai.Task` (one `Sample`, real `generate()`
    solver, real `match()` scorer) and materializes real `inspect_ai.eval()`
    runs against it. `solve_sample` is the sole `DO` capability -- each call
    is a real, independently re-runnable Inspect evaluation, not a cached or
    replayed result.
    """

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

        # Real, in-process inspect_ai.eval_async() call -- no subprocess, no
        # simulated log. The synchronous inspect_ai.eval() drives its own
        # internal anyio event loop and raises "Already running asyncio in
        # this thread" when called from inside a coroutine (verified in this
        # session); eval_async() is Inspect's own real awaitable entry point
        # for exactly this situation.
        logs = await inspect_eval_async(
            self._task,
            model=self._model,
            model_args=self._model_args,
            log_dir=self._log_dir,
        )
        # inspect_ai's own internal transcript/display plumbing allocates an
        # anyio.MemoryObjectReceiveStream per eval_async() run that is
        # sometimes released without an explicit aclose() -- an upstream
        # inspect_ai 0.3.252 cleanup gap, not anything this module opens.
        # Forcing garbage collection immediately after each real run makes
        # the resulting ResourceWarning surface here, deterministically,
        # instead of at an unrelated later point in the process (verified in
        # this session: without this, the warning could fire during
        # interpreter shutdown well after this environment was torn down).
        import gc

        gc.collect()
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
    """GymAct `EnvironmentProvider` that materializes a real, minimal
    `inspect_ai.Task` and a real Inspect model backend to solve it with.

    `config["input"]` / `config["target"]` build the real `inspect_ai.dataset
    .Sample` (defaults to a deterministic arithmetic prompt so the default
    path is fully reproducible). `config["model"]` defaults to
    `"mockllm/model"` (Inspect's real, first-party local/deterministic model
    provider -- no API key required); `config["model_args"]["custom_outputs"]`
    may be a list of literal completion strings that this provider converts
    into real `inspect_ai.model.ModelOutput` objects for `MockLLM` to replay
    in order. A caller with real credentials may instead pass a real paid
    `config["model"]` (e.g. `"openai/gpt-4o"`) -- this provider does not
    special-case that path.
    """

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
            # Convert plain literal-completion strings into real
            # inspect_ai.model.ModelOutput objects, exactly what MockLLM's
            # own __init__ requires (a bare str raises ValueError inside
            # MockLLM.generate -- verified in this session). This is a
            # convenience for provider callers; the real MockLLM/ModelOutput
            # types still do the real replay.
            model_args["custom_outputs"] = [
                ModelOutput.from_content(model=model.split("/", 1)[-1] or "model", content=text)
                for text in custom_outputs
            ]

        log_dir = config.get("log_dir", "./.inspect_logs")
        if not isinstance(log_dir, str) or not log_dir:
            raise TypeError("config.log_dir must be a non-empty string")

        requires_authority = config.get("requires_authority", False)
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
