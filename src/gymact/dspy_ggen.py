"""DSPy-shaped deterministic programs backed by ggen agents, with zero LMs.

This module intentionally does *not* emulate ``dspy.LM``.  A DSPy Signature
is a typed I/O contract; ggen is the implementation.  ``GgenPredict`` maps
signature inputs into a ``GgenAgentRuntime`` invocation and returns the
manufactured signature outputs.  If DSPy is installed, ``Prediction`` is used
as the result carrier; otherwise the zero-dependency ``GgenPrediction`` model
keeps the same values available to GymAct callers and tests.

No prompt, completion, token, or model-provider path exists here.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import Field

from gymact.ggen_agent import GgenAgentRuntime
from gymact.models import FrozenModel, Standing


class GgenPrediction(FrozenModel):
    """Zero-dependency prediction carrier when DSPy is not installed."""

    values: dict[str, Any] = Field(default_factory=dict)
    receipt_digest: str
    standing: Standing
    llm_calls: int = 0

    def __getattr__(self, name: str) -> Any:
        values = object.__getattribute__(self, "values")
        if name in values:
            return values[name]
        raise AttributeError(name)


def _field_names(signature: Any, name: str) -> tuple[str, ...]:
    """Read DSPy v2/v3-style signature field mappings without importing DSPy."""
    fields = getattr(signature, name, None)
    if fields is None and isinstance(signature, type):
        fields = getattr(signature, name, None)
    if isinstance(fields, Mapping):
        return tuple(str(key) for key in fields)
    return ()


class GgenPredict:
    """``dspy.Predict``-shaped asynchronous program implemented by ggen.

    ``signature`` may be a real DSPy Signature class/instance or any object
    exposing ``input_fields``/``output_fields`` mappings.  The latter keeps
    the core path testable without making DSPy a mandatory GymAct dependency.
    """

    def __init__(
        self,
        signature: Any,
        *,
        runtime: GgenAgentRuntime,
        agent_id: str,
    ) -> None:
        self.signature = signature
        self.runtime = runtime
        self.agent_id = agent_id
        self.input_fields = _field_names(signature, "input_fields")
        self.output_fields = _field_names(signature, "output_fields")

    async def acall(self, **kwargs: Any) -> Any:
        if self.input_fields:
            missing = tuple(name for name in self.input_fields if name not in kwargs)
            if missing:
                raise ValueError(f"DSPY_GGEN_INPUT_MISSING:{missing!r}")
            unknown = tuple(name for name in kwargs if name not in self.input_fields)
            if unknown:
                raise ValueError(f"DSPY_GGEN_INPUT_UNKNOWN:{unknown!r}")

        result = await self.runtime.invoke(
            self.agent_id,
            observation=kwargs,
            inputs=kwargs,
        )
        if result.standing is not Standing.ALIVE:
            raise RuntimeError(result.reason)

        values = dict(result.output)
        if self.output_fields:
            missing_outputs = tuple(name for name in self.output_fields if name not in values)
            if missing_outputs:
                raise ValueError(f"DSPY_GGEN_OUTPUT_MISSING:{missing_outputs!r}")
            values = {name: values[name] for name in self.output_fields}

        try:
            import dspy
        except ImportError:
            return GgenPrediction(
                values=values,
                receipt_digest=result.receipt_digest,
                standing=result.standing,
            )

        return dspy.Prediction(
            **values,
            _gymact_receipt_digest=result.receipt_digest,
            _gymact_standing=result.standing.value,
            _gymact_llm_calls=0,
        )



def build_dspy_ggen_module(
    signature: Any,
    *,
    runtime: GgenAgentRuntime,
    agent_id: str,
) -> Any:
    """Return a real ``dspy.Module`` whose ``acall`` never constructs an LM.

    DSPy's synchronous ``forward`` contract cannot safely drive GymAct's
    asynchronous runtime from an already-running event loop, so this module
    makes the boundary explicit: use ``await module.acall(...)``.  This is an
    execution adapter, not an LM compatibility shim.
    """
    try:
        import dspy
    except ImportError as exc:
        raise ImportError(
            "build_dspy_ggen_module requires the optional 'dspy' extra: "
            "install with `pip install 'gymact[dspy]'`."
        ) from exc

    predictor = GgenPredict(signature, runtime=runtime, agent_id=agent_id)

    class GgenDSPyModule(dspy.Module):
        def forward(self, **kwargs: Any) -> Any:
            del kwargs
            raise RuntimeError("DSPY_GGEN_ASYNC_ONLY_USE_ACALL")

        async def acall(self, **kwargs: Any) -> Any:
            return await predictor.acall(**kwargs)

    return GgenDSPyModule()
