"""Real OCEL 2.0 log of a DSPy run's OWN execution trace (LM calls, tool
calls, module/ReAct calls) -- a real shim into `dspy.utils.callback.
BaseCallback`, the first-class hook DSPy itself ships for exactly this
purpose (`dspy.configure(callbacks=[...])` / per-component `callbacks=`).

Deliberately a SEPARATE OCEL log from `gymact.ocel.receipts_to_ocel`'s
Receipt-based one, not a reuse of `Operation`/`Receipt`: a DSPy LM call or
a pure-reasoning tool (e.g. `dspy_sregym_agent`'s concurrent theory
panels) is not a kernel actuation and has no `Operation`/authority-gated
meaning -- forcing it into `Operation` would blur the real consequence-law
distinction this repo's own rules draw (`request accepted != world changed
...`). A real `run_kubectl`/`submit_diagnosis` tool call already produces
its own real kernel `Receipt` (see `dspy_sregym_agent.py`'s `_run_kubectl_raw`)
independently of this module; this module's job is making the REASONING
trace around those calls -- which LM said what, when, via which tool --
equally real, checkable, and schema-valid, not just narrated in a printed
transcript. Both logs validate against the exact same real OCEL 2.0 JSON
Schema (`gymact.ocel.validate_ocel_log`) and can be correlated by real
timestamp/call_id if a caller wants to merge them; this module does not
attempt that merge itself.

Object types: `dspy_run` (one per `run_diagnosis()`-style call this
callback is attached to), `lm` (one per distinct real model id called),
`tool` (one per distinct real tool name called). Event types: `lm_call`,
`tool_call`, `module_call` -- one event per real call_id, combining its
start and end (DSPy's own `on_..._start`/`on_..._end` pair) into a single
OCEL event once the call completes, since `call_id` is what correlates
them and OCEL events are naturally "one thing happened," not two.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gymact.ocel import digest_ocel_log, validate_ocel_log

try:
    from dspy.utils.callback import BaseCallback
except ImportError:  # pragma: no cover - exercised via require_standing in tests
    BaseCallback = object  # type: ignore[assignment,misc]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_jsonable(value: Any) -> Any:
    """Best-effort real JSON-safe conversion -- never raises. Tries
    Pydantic's own `.model_dump()` first (DSPy `Prediction`/Signature
    inputs/outputs are frequently real Pydantic models or dspy objects
    exposing this), falls back to `repr()` for anything else rather than
    silently dropping the value."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _safe_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_jsonable(v) for v in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _safe_jsonable(model_dump())
        except Exception:
            pass
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


class DspyOcelCallback(BaseCallback):
    """Real `dspy.utils.callback.BaseCallback` implementation accumulating
    a real, schema-valid OCEL 2.0 log of every LM/tool/module call made
    while this callback is active (global via `dspy.configure(callbacks=
    [cb])`, or local via a component's own `callbacks=[cb]` constructor
    kwarg -- both real DSPy mechanisms, not custom plumbing)."""

    def __init__(self, run_id: str) -> None:
        require_standing_ok = BaseCallback is not object
        if not require_standing_ok:
            raise ImportError(
                "gymact.dspy_ocel requires the optional 'dspy' extra: "
                "install with `pip install 'gymact[dspy]'` or `uv sync --extra dspy`."
            )
        self.run_id = run_id
        self._starts: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        self._lm_ids: set[str] = set()
        self._tool_ids: set[str] = set()
        self._module_ids: set[str] = set()

    # --- real DSPy callback hooks --------------------------------------

    def on_lm_start(self, call_id: str, instance: Any, inputs: dict[str, Any]) -> None:
        model_id = getattr(instance, "model", None) or repr(instance)
        self._lm_ids.add(model_id)
        self._start("lm_call", call_id, model_id, inputs)

    def on_lm_end(self, call_id: str, outputs: Any, exception: Exception | None = None) -> None:
        self._end("lm_call", call_id, outputs, exception)

    def on_tool_start(self, call_id: str, instance: Any, inputs: dict[str, Any]) -> None:
        tool_name = getattr(instance, "name", None) or repr(instance)
        self._tool_ids.add(tool_name)
        self._start("tool_call", call_id, tool_name, inputs)

    def on_tool_end(self, call_id: str, outputs: Any, exception: Exception | None = None) -> None:
        self._end("tool_call", call_id, outputs, exception)

    def on_module_start(self, call_id: str, instance: Any, inputs: dict[str, Any]) -> None:
        module_name = type(instance).__name__
        self._module_ids.add(module_name)
        self._start("module_call", call_id, module_name, inputs)

    def on_module_end(self, call_id: str, outputs: Any, exception: Exception | None = None) -> None:
        self._end("module_call", call_id, outputs, exception)

    # --- shared start/end bookkeeping -----------------------------------

    def _start(
        self, event_type: str, call_id: str, subject_id: str, inputs: dict[str, Any]
    ) -> None:
        self._starts[call_id] = {
            "event_type": event_type,
            "subject_id": subject_id,
            "inputs": _safe_jsonable(inputs),
            "start_time": _utc_now_iso(),
        }

    def _end(
        self, event_type: str, call_id: str, outputs: Any, exception: Exception | None
    ) -> None:
        start = self._starts.pop(call_id, None)
        if start is None:  # a call that started before this callback attached
            return
        # Real OCEL 2.0 schema constraint, confirmed against the vendored
        # schema (`schemas/ocel20-schema.json`): `events[].attributes[].value`
        # is ALWAYS required to be a literal JSON string -- the `type` field
        # declared in `eventTypes[].attributes[]` (e.g. "boolean") is
        # descriptive metadata only, never coerced/enforced by the schema
        # itself. Confirmed live: a real `False` python bool value failed
        # real jsonschema validation with "False is not of type 'string'".
        # Every value here is therefore stringified explicitly, not left to
        # Python's own JSON truthiness.
        attributes = [
            {"name": "subject_id", "value": str(start["subject_id"])},
            {"name": "inputs", "value": json.dumps(start["inputs"], default=str)},
            {"name": "outputs", "value": json.dumps(_safe_jsonable(outputs), default=str)},
            {"name": "start_time", "value": start["start_time"]},
            {"name": "failed", "value": str(exception is not None)},
        ]
        if exception is not None:
            attributes.append({"name": "exception", "value": repr(exception)})
        object_qualifier = {"lm_call": "lm", "tool_call": "tool", "module_call": "module"}[
            event_type
        ]
        self._events.append(
            {
                "id": call_id,
                "type": event_type,
                "time": _utc_now_iso(),
                "attributes": attributes,
                "relationships": [
                    {"objectId": self.run_id, "qualifier": "dspy_run"},
                    {"objectId": start["subject_id"], "qualifier": object_qualifier},
                ],
            }
        )

    # --- real OCEL 2.0 log construction ----------------------------------

    def to_ocel_log(self) -> dict[str, Any]:
        """Build the real OCEL 2.0 log dict from every call recorded so
        far. Does NOT validate -- call `gymact.ocel.validate_ocel_log` on
        the result, matching this repo's own OCEL-standing discipline
        (a log is only real evidence once independently schema-validated,
        not because this method returned without raising)."""
        objects: list[dict[str, Any]] = [
            {"id": self.run_id, "type": "dspy_run", "attributes": []}
        ]
        objects.extend({"id": mid, "type": "lm", "attributes": []} for mid in sorted(self._lm_ids))
        objects.extend(
            {"id": tid, "type": "tool", "attributes": []} for tid in sorted(self._tool_ids)
        )
        objects.extend(
            {"id": mid, "type": "module", "attributes": []} for mid in sorted(self._module_ids)
        )

        object_types = [{"name": "dspy_run", "attributes": []}]
        if self._lm_ids:
            object_types.append({"name": "lm", "attributes": []})
        if self._tool_ids:
            object_types.append({"name": "tool", "attributes": []})
        if self._module_ids:
            object_types.append({"name": "module", "attributes": []})

        event_type_names = sorted({event["type"] for event in self._events})
        event_types = [
            {
                "name": name,
                "attributes": [
                    {"name": "subject_id", "type": "string"},
                    {"name": "inputs", "type": "string"},
                    {"name": "outputs", "type": "string"},
                    {"name": "start_time", "type": "string"},
                    {"name": "failed", "type": "boolean"},
                ],
            }
            for name in event_type_names
        ]

        return {
            "eventTypes": event_types,
            "objectTypes": object_types,
            "events": self._events,
            "objects": objects,
        }


def build_and_validate_dspy_ocel_log(callback: DspyOcelCallback) -> tuple[dict[str, Any], str]:
    """Build, real-schema-validate, and digest a `DspyOcelCallback`'s
    accumulated log -- mirrors `gymact.ocel.write_ocel_log`'s
    build-validate-digest discipline (validation before the caller can
    treat this as real evidence, exactly like the kernel's own Receipt
    OCEL log)."""
    log = callback.to_ocel_log()
    validate_ocel_log(log)
    return log, digest_ocel_log(log)


def write_dspy_ocel_log(path: Path, callback: DspyOcelCallback) -> tuple[dict[str, Any], str]:
    """Build, validate, persist a `DspyOcelCallback`'s log; return (log,
    sha256 digest) -- real mirror of `gymact.ocel.write_ocel_log`'s own
    contract for the kernel's Receipt-based log. Validation runs before the
    file is written; an invalid log is never persisted as if it were real
    evidence."""
    log, digest = build_and_validate_dspy_ocel_log(callback)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, indent=2, sort_keys=True))
    return log, digest
