"""Real GymAct `Environment`/`EnvironmentProvider` backed by CUBE's own
container-provisioned `toy_benchmark` example (`LocalInfraConfig` +
`ContainerConfig(image="python:3.12-slim")`) -- run against a real local
Docker daemon (colima), not simulated.

This is deliberately the more complex CUBE example available in this
vendored copy of cube-standard: unlike `cube_counter.py`
(`counter-cube`, pure in-memory, no `materialize()` side effect beyond
constructing a Python object), this environment's `materialize()` actually
provisions a real container and `CUBE`'s own `Task.reset()` runs a real
`container.exec("echo infra-ready")` probe inside it before returning. The
task variant used here (`count-to-3-with-decrement`) also exposes a richer
capability set (increment + decrement + get_value) than `counter-cube`'s.

`examples/toy_benchmark/counter.py` ships as a standalone script in
cube-standard (no package/pyproject.toml of its own), so it is loaded here
by file path via `importlib.util` rather than pip-installed -- this does not
copy or rewrite any of its logic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from gymact.models import Capability, Consequence

_TOY_BENCHMARK_PATH = (
    Path.home()
    / "autofde-lab"
    / "vendor"
    / "gyms"
    / "cube-standard"
    / "examples"
    / "toy_benchmark"
    / "counter.py"
)


def _load_toy_benchmark_module() -> Any:
    if not _TOY_BENCHMARK_PATH.exists():
        raise ImportError(
            "cube_container_counter requires the vendored CUBE toy_benchmark "
            f"example at {_TOY_BENCHMARK_PATH} -- run "
            "`git -c submodule.forwardbench-cube-standard.update=checkout "
            "submodule update --init vendor/gyms/cube-standard` in ~/autofde-lab"
        )
    spec = importlib.util.spec_from_file_location(
        "gymact._vendored_cube_toy_benchmark", _TOY_BENCHMARK_PATH
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"could not load module spec for {_TOY_BENCHMARK_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    _toy = _load_toy_benchmark_module()
    from cube.infra_local import LocalInfraConfig
except ImportError as exc:  # pragma: no cover - exercised via named skip in tests
    raise ImportError(
        "cube_container_counter requires the optional 'cube' extra with the "
        "'docker' extra of cube-standard itself "
        "(`uv sync --all-extras`, which now pulls cube-standard[docker]), and "
        "a reachable Docker daemon (e.g. `colima start`)."
    ) from exc

CUBE_CONTAINER_COUNTER_CAPABILITIES = (
    Capability(
        iri="urn:gymact:cube-container-counter:capability:increment",
        title="Increment the containerized CUBE counter task's counter by 1",
        consequence=Consequence.DO,
        binding="increment",
    ),
    Capability(
        iri="urn:gymact:cube-container-counter:capability:decrement",
        title="Decrement the containerized CUBE counter task's counter by 1",
        consequence=Consequence.DO,
        binding="decrement",
    ),
    Capability(
        iri="urn:gymact:cube-container-counter:capability:get_value",
        title="Read the containerized CUBE counter task's current counter value",
        consequence=Consequence.READ,
        binding="get_value",
    ),
)

_TASK_ID = "count-to-3-with-decrement"


class CubeContainerCounterEnvironment:
    """Wraps a real, container-provisioned `toy_benchmark.ReachTargetTask`.

    `materialize()` (via `__init__`) is where this genuinely differs from
    `CubeCounterEnvironment`: it opens a real `CounterBenchmarkConfig`
    context bound to a real `LocalInfraConfig`, which provisions a real
    Docker container (`python:3.12-slim`) through the real local Docker
    daemon, and CUBE's own `Task.reset()` probes it with a real
    `container.exec("echo infra-ready")` before this constructor returns.
    """

    def __init__(self, *, requires_authority: bool = False) -> None:
        self.environment_id = f"urn:gymact:cube-container-counter:environment:{uuid4().hex}"
        self.requires_authority = requires_authority
        self._closed = False

        config = _toy.CounterBenchmarkConfig()
        self._benchmark_cm = config.make(infra=LocalInfraConfig())
        self._benchmark = self._benchmark_cm.__enter__()
        task_configs = {c.task_id: c for c in config.get_task_configs()}
        self._task = task_configs[_TASK_ID].make(runtime_context=self._benchmark._runtime_context)
        # Real container provisioning + real in-container probe happens here.
        self._task.reset()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("environment is torn down")

    def capabilities(self) -> tuple[Capability, ...]:
        self._ensure_open()
        return CUBE_CONTAINER_COUNTER_CAPABILITIES

    def _state(self) -> dict[str, Any]:
        reward, info = self._task.evaluate()
        return {
            "counter": self._task.tool.counter,
            "target": self._task.target,
            "reward": reward,
            "solved": bool(info.get("solved", False)),
            "steps": info.get("steps", len(self._task.tool.history)),
            "containerized": self._task.container is not None,
        }

    async def observe(self) -> dict[str, Any]:
        self._ensure_open()
        return self._state()

    async def actuate(self, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        self._ensure_open()
        before = self._state()
        binding = capability.binding
        if binding == "increment":
            result_text = self._task.tool.increment()
        elif binding == "decrement":
            result_text = self._task.tool.decrement()
        elif binding == "get_value":
            result_text = self._task.tool.get_value()
        else:
            raise ValueError(f"unsupported CUBE container counter binding: {binding}")
        after = self._state()
        return {"before": before, "after": after, "result_text": result_text}

    async def verify(self, expected: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        self._ensure_open()
        observed = self._state()
        passed = all(observed.get(key) == value for key, value in expected.items())
        return passed, observed

    async def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {"counter": self._task.tool.counter, "history": list(self._task.tool.history)}

    async def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        self._task.tool.counter = int(checkpoint["counter"])
        self._task.tool.history = list(checkpoint["history"])

    async def teardown(self) -> None:
        if self._closed:
            return
        try:
            self._task.close()  # real container.stop()
        finally:
            self._benchmark_cm.__exit__(None, None, None)
            self._closed = True


class CubeContainerCounterProvider:
    """GymAct `EnvironmentProvider` that materializes real, container-backed
    CUBE counter tasks against a real local Docker daemon."""

    name = "cube-container-counter"
    materialization_requires_authority = False

    async def materialize(
        self, *, scenario: str | None, config: dict[str, Any]
    ) -> CubeContainerCounterEnvironment:
        del scenario
        requires_authority = config.get("requires_authority", True)
        if not isinstance(requires_authority, bool):
            raise TypeError("config.requires_authority must be a boolean")
        return CubeContainerCounterEnvironment(requires_authority=requires_authority)
