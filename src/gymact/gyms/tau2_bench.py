"""Real GymAct `Environment`/`EnvironmentProvider` backed by the actual,
externally-published `tau2` package (Sierra's tau2-bench / tau^3-bench,
`vendor-tau2-bench` pin in autofde-lab's `docs/papers/gym-lock.ttl`,
upstream `sierra-research/tau2-bench`).

tau2-bench simulates a customer-service agent operating real domain tools
(retail order lookups/refunds, airline booking changes, etc.) against a
real, deterministic, in-process domain database (`tau2.environment.db.DB`,
a pydantic model). This module wraps that real object graph directly --
`tau2.registry`'s own `get_environment`/`get_tasks` factories, the real
`Environment.use_tool`/`run_env_assertion` methods, and the real
`Task.evaluation_criteria` a task ships with -- never a re-derived shadow
copy of tau2's own domain/tool/task semantics.

Full end-to-end tau2-bench evaluation (`tau2 run`) drives a live LLM user
simulator that free-forms a conversation with the agent. That user
simulator genuinely requires a configured LLM API key (OpenAI/Anthropic/
etc: see tau2's own `docs/getting-started.md`) and is out of scope for
this provider -- GymAct's `EnvironmentProvider` contract calls for a
materialized world with real capabilities/observe/actuate/verify, not an
embedded conversational agent loop. What this module provides instead is
the real, LLM-free, deterministic substrate tau2-bench itself uses to
grade a trajectory: real domain tools as GymAct `DO`/`READ` capabilities,
a real domain DB as the observation, and real, deterministic verification
against the task's own shipped `EvaluationCriteria` --
`env_assertions` (`Environment.run_env_assertion`, exactly tau2's own
`EnvironmentEvaluator` mechanism) and the DB-end-state check (replay the
task's own reference `actions` on a fresh env and compare
`get_db_hash()`, exactly tau2's `RewardType.DB` mechanism) -- both real
tau2 code paths, not a fabricated pass/fail. `RewardType.COMMUNICATE` and
`RewardType.NL_ASSERTION` require the live conversation/an LLM judge and
are reported as `unavailable` in `verify()`'s info payload rather than
silently scored.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

try:
    from tau2 import registry as tau2_registry
    from tau2.data_model.tasks import Action, EnvFunctionCall, RewardType, Task
    from tau2.environment.environment import Environment as Tau2Environment

    TAU2_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when tau2 is absent
    TAU2_AVAILABLE = False

# Core (extra-free) tau2 domains: airline/retail/mock ship in tau2's base
# install; telecom needs no extras either but its `get_environment` takes a
# required `policy` selector, so it is left to future work rather than
# guessed at here. banking_knowledge requires the `knowledge` extra
# (retrieval pipeline) and is out of scope.
_SUPPORTED_DOMAINS = ("retail", "airline", "mock")

_DOMAIN_ACCESSORS = {
    "retail": ("get_retail_domain_get_environment", "get_retail_domain_get_tasks"),
}


def _domain_factories(domain: str) -> tuple[Any, Any]:
    """Resolve the real, tau2-registry-imported `get_environment`/`get_tasks`
    pair for `domain`. Uses the exact functions `tau2.registry` itself
    imports (not a re-derived import path), so a change to tau2's own
    module layout surfaces here rather than silently drifting."""
    if domain == "retail":
        from tau2.domains.retail.environment import get_environment, get_tasks
    elif domain == "airline":
        from tau2.domains.airline.environment import get_environment, get_tasks
    elif domain == "mock":
        from tau2.domains.mock.environment import get_environment, get_tasks
    else:  # pragma: no cover - guarded by materialize()'s own check
        raise ValueError(f"unsupported tau2 domain: {domain!r}")
    return get_environment, get_tasks


def _to_jsonable(value: Any) -> Any:
    """Recursively convert a real tau2 tool-call return value (which may be
    a pydantic `BaseModel`, e.g. an `Order`/`User`) into JSON-serializable
    plain Python data -- never fabricates or drops fields, only reshapes
    what the real tau2 tool actually returned."""
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


def _tool_capabilities(env: "Tau2Environment") -> tuple[Capability, ...]:
    """Build one real GymAct `Capability` per real tau2 assistant tool.
    `DO`/`READ` is read from the tool's own `mutates_state` classification
    (`ToolKitBase.tool_mutates_state`) -- tau2's own authority-relevant fact
    about the tool, not a guess from its name."""
    capabilities = []
    for tool in env.get_tools():
        mutates = env.tools.tool_mutates_state(tool.name)
        capabilities.append(
            Capability(
                iri=f"urn:gymact:tau2-bench:capability:{env.domain_name}:{tool.name}",
                title=tool.short_desc or tool.name,
                consequence=Consequence.DO if mutates else Consequence.READ,
                binding=tool.name,
            )
        )
    return tuple(capabilities)


class Tau2BenchEnvironment:
    """Wraps a real, materialized `tau2.environment.environment.Environment`
    for one real tau2 `Task`.

    All state reads/writes go through the real tau2 `Environment` object
    (`self._env.use_tool`, `self._env.run_env_assertion`,
    `self._env.tools.db`) -- gymnasium_env.py's real-object pattern applied
    to tau2's domain/tool/DB object graph instead of a physics simulator.
    """

    def __init__(
        self,
        *,
        domain: str,
        task: "Task",
        env: "Tau2Environment",
        requires_authority: bool = True,
    ) -> None:
        self.environment_id = f"urn:gymact:tau2-bench:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._domain = domain
        self._task = task
        self._env = env
        self._capabilities = _tool_capabilities(env)
        self._trajectory: list[dict[str, Any]] = []
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return self._capabilities

    def _db_state(self) -> dict[str, Any]:
        if self._env.tools is None:  # pragma: no cover - all supported domains have tools
            return {}
        return self._env.tools.db.model_dump(mode="json")

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return {
            "domain": self._domain,
            "task_id": self._task.id,
            "policy": self._env.policy,
            "db": self._db_state(),
            "db_hash": self._env.get_db_hash(),
            "trajectory": list(self._trajectory),
        }

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_open()
        before_hash = self._env.get_db_hash()
        tool_name = capability.binding
        try:
            result = self._env.use_tool(tool_name, **payload)
        except Exception as exc:
            # Consequence law: request accepted != world changed. A real
            # tau2 tool call that raises (invalid order id, policy
            # violation, etc.) never silently becomes a successful mutation
            # -- record and re-raise the real tau2 exception.
            self._trajectory.append(
                {"tool": tool_name, "arguments": payload, "error": str(exc)}
            )
            raise
        after_hash = self._env.get_db_hash()
        jsonable_result = _to_jsonable(result)
        entry = {
            "tool": tool_name,
            "arguments": payload,
            "result": jsonable_result,
            "db_hash_before": before_hash,
            "db_hash_after": after_hash,
        }
        self._trajectory.append(entry)
        return {
            "before": {"db_hash": before_hash},
            "after": {"db_hash": after_hash, "db": self._db_state()},
            "result": jsonable_result,
            "capability": capability.iri,
        }

    def _replay_reference_db_hash(self) -> str | None:
        """Real `RewardType.DB` mechanism: replay the task's own reference
        `evaluation_criteria.actions` on a *fresh* env sharing the same
        initial state, and return that env's resulting DB hash. Returns
        None if the task ships no reference trajectory."""
        criteria = self._task.evaluation_criteria
        if criteria is None or not criteria.actions:
            return None
        get_environment, _ = _domain_factories(self._domain)
        fresh_env = get_environment()
        _apply_initial_state(fresh_env, self._task)
        for action in criteria.actions:
            requestor = "user" if action.requestor == "user" else "assistant"
            fresh_env.make_tool_call(
                action.name, requestor=requestor, **(action.arguments or {})
            )
        return fresh_env.get_db_hash()

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Deterministic, LLM-free verification against the task's own real
        `EvaluationCriteria` -- exactly the two tau2 reward components that
        do not require a live conversation or an LLM judge:

        - `RewardType.ENV_ASSERTION`: replay each real `EnvAssertion` via
          `Environment.run_env_assertion` (tau2's own assertion runner).
        - `RewardType.DB`: compare this environment's real DB hash against
          the hash of a fresh env that replayed the task's own reference
          `actions` (tau2's own DB-end-state mechanism).

        `communicate_info` and `nl_assertions` require the live
        conversation transcript / an LLM judge and are reported as
        `"unavailable"` rather than fabricated.
        """
        self._ensure_open()
        criteria = self._task.evaluation_criteria
        info: dict[str, Any] = {
            "domain": self._domain,
            "task_id": self._task.id,
            "db_hash": self._env.get_db_hash(),
        }
        if criteria is None:
            info["note"] = "task ships no evaluation_criteria"
            return True, info

        checks: dict[str, bool] = {}

        if criteria.env_assertions:
            assertion_results = []
            for assertion in criteria.env_assertions:
                passed = self._env.run_env_assertion(assertion, raise_assertion_error=False)
                assertion_results.append({"func_name": assertion.func_name, "passed": passed})
            info["env_assertions"] = assertion_results
            checks["env_assertion"] = all(r["passed"] for r in assertion_results)

        if criteria.actions:
            reference_hash = self._replay_reference_db_hash()
            actual_hash = self._env.get_db_hash()
            info["db_check"] = {
                "reference_hash": reference_hash,
                "actual_hash": actual_hash,
            }
            checks["db"] = reference_hash is not None and reference_hash == actual_hash

        if criteria.communicate_info:
            info["communicate_info"] = "unavailable: requires the live conversation transcript"
        if criteria.nl_assertions:
            info["nl_assertions"] = "unavailable: requires an LLM judge"

        for key, value in expected.items():
            if key in checks:
                checks[key] = checks[key] and bool(value) == checks[key]

        info["checks"] = checks
        passed = all(checks.values()) if checks else True
        return passed, info

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {"db": self._db_state(), "trajectory": list(self._trajectory)}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        if self._env.tools is not None:
            db_cls = type(self._env.tools.db)
            self._env.tools.db = db_cls.model_validate(checkpoint["db"])
        self._trajectory = list(checkpoint["trajectory"])

    async def teardown(self) -> None:
        self._closed = True


def _apply_initial_state(env: "Tau2Environment", task: "Task") -> None:
    """Apply a real tau2 `Task.initial_state` to a real, freshly-constructed
    `Environment` -- tau2's own initialization data/actions, not a
    re-derived substitute."""
    initial_state = task.initial_state
    if initial_state is None:
        return
    if initial_state.initialization_data is not None:
        agent_data = initial_state.initialization_data.agent_data
        if agent_data and env.tools is not None:
            env.tools.update_db(agent_data)
        user_data = initial_state.initialization_data.user_data
        if user_data and env.user_tools is not None:
            env.user_tools.update_db(user_data)
    if initial_state.initialization_actions:
        env.run_env_function_calls(initial_state.initialization_actions)


class Tau2BenchProvider:
    """GymAct `EnvironmentProvider` that materializes real tau2-bench
    domain/task worlds.

    `config`:
      - `domain` (str, default "retail"): one of `_SUPPORTED_DOMAINS`.
      - `task_id` (str | None): a real task id from that domain's task set
        (`tau2.domains.<domain>.environment.get_tasks()`). Defaults to the
        first task in the "base" split.
      - `requires_authority` (bool, default True): DO capabilities mutate
        a real simulated customer/order database -- authority is required
        by default per `.claude/rules/actuation-authority.md`.
    """

    name = "tau2-bench"
    # Materializing a tau2 world only constructs real, but purely in-process,
    # Python state (domain/task objects, a fresh DB) -- no external side
    # effect occurs yet, so materialization itself needs no authority
    # (matches memory/gymnasium's own providers). Authority is required at
    # `act()` time instead, gated per-episode via `Tau2BenchEnvironment.
    # requires_authority` (default True) on every DO capability, per
    # `.claude/rules/actuation-authority.md`.
    materialization_requires_authority = False

    def __init__(self, *, requires_authority: bool = True) -> None:
        self.requires_authority = requires_authority

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> Tau2BenchEnvironment:
        if not TAU2_AVAILABLE:
            raise RuntimeError(
                "tau2 is not installed. Install the 'tau2-bench' extra "
                "(Python >=3.12,<3.14) to materialize this provider."
            )
        domain = config.get("domain", scenario or "retail")
        if not isinstance(domain, str):
            raise TypeError("config.domain must be a str")
        if domain not in _SUPPORTED_DOMAINS:
            raise ValueError(
                f"unsupported tau2 domain {domain!r}; supported: {_SUPPORTED_DOMAINS}"
            )
        task_id = config.get("task_id")
        if task_id is not None and not isinstance(task_id, str):
            raise TypeError("config.task_id must be a str or None")
        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")

        get_environment, get_tasks = _domain_factories(domain)
        tasks = get_tasks()
        if not tasks:
            raise RuntimeError(f"tau2 domain {domain!r} shipped zero tasks")
        if task_id is None:
            task = tasks[0]
        else:
            matches = [t for t in tasks if t.id == task_id]
            if not matches:
                available = sorted(t.id for t in tasks)[:10]
                raise ValueError(
                    f"unknown task_id {task_id!r} for domain {domain!r}; "
                    f"first available: {available}"
                )
            task = matches[0]

        env = get_environment()
        _apply_initial_state(env, task)
        return Tau2BenchEnvironment(
            domain=domain,
            task=task,
            env=env,
            requires_authority=self.requires_authority or requires_authority,
        )
