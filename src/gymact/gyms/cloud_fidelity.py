from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import blake3
import rfc8785

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
JsonPath = tuple[str | int, ...]
IgnoredPathsByStep = Mapping[int, Iterable[JsonPath]]


@dataclass(frozen=True, slots=True)
class CloudTraceStep:
    """One agent-visible cloud interaction used by the fidelity court.

    The court is intentionally transport-agnostic: ``surface`` names the
    externally visible interface (for example ``aws-cli``, ``boto3`` or
    ``terraform``), while request/response hold the decoded public payloads.
    Provider-private simulator state and GymAct authority internals never enter
    this structure, so a passing comparison cannot be achieved by comparing
    hidden implementation details.
    """

    surface: str
    operation: str
    request: JsonValue
    response: JsonValue | None = None
    status_code: int | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class FidelityDifference:
    step: int | None
    path: JsonPath
    reason: str
    reference: Any = None
    twin: Any = None


@dataclass(frozen=True, slots=True)
class CloudFidelityResult:
    equivalent: bool
    compared_steps: int
    differences: tuple[FidelityDifference, ...]


@dataclass(frozen=True, slots=True)
class CloudTraceReceipt:
    """Deterministic identity for one ordered agent-visible cloud trace."""

    digest: str
    step_count: int


def _trace_payload(trace: Iterable[CloudTraceStep]) -> tuple[tuple[CloudTraceStep, ...], list[dict[str, Any]]]:
    steps = tuple(trace)
    payload = [
        {
            "surface": step.surface,
            "operation": step.operation,
            "request": step.request,
            "response": step.response,
            "status_code": step.status_code,
            "error_code": step.error_code,
        }
        for step in steps
    ]
    return steps, payload


def receipt_cloud_trace(trace: Iterable[CloudTraceStep]) -> CloudTraceReceipt:
    """Bind an ordered public trace to canonical JSON and a BLAKE3 digest."""

    steps, payload = _trace_payload(trace)
    canonical = rfc8785.dumps(payload)
    return CloudTraceReceipt(
        digest=blake3.blake3(canonical).hexdigest(),
        step_count=len(steps),
    )


def replay_cloud_trace(trace: Iterable[CloudTraceStep], receipt: CloudTraceReceipt) -> bool:
    """Replay trace identity without granting execution or mutation authority."""

    replayed = receipt_cloud_trace(trace)
    return replayed == receipt


def _path_is_ignored(path: JsonPath, ignored_paths: frozenset[JsonPath]) -> bool:
    return path in ignored_paths


def _normalize_ignore_path(path: Iterable[str | int]) -> JsonPath:
    return tuple(path)


def _admit_ignored_paths(
    *,
    compared_steps: int,
    ignored_paths: Iterable[JsonPath],
    ignored_paths_by_step: IgnoredPathsByStep | None,
    differences: list[FidelityDifference],
) -> dict[int, frozenset[JsonPath]]:
    """Admit only bounded response volatility at a specific trace step.

    Legacy ``ignored_paths`` remains valid for a one-step trace. Once a trace
    contains multiple compared steps, a path without a step identity is too
    broad: the same response field may carry different semantics in another
    operation. Such requests fail closed by adding an admission difference
    instead of silently suppressing evidence.
    """

    admitted: dict[int, set[JsonPath]] = {}

    def admit(step: int, raw_path: Iterable[str | int], *, scoped: bool) -> None:
        path = _normalize_ignore_path(raw_path)
        if step < 0 or step >= compared_steps:
            differences.append(
                FidelityDifference(step, path, "invalid_ignored_step", None, compared_steps)
            )
            return
        if not path or path[0] != "response":
            differences.append(
                FidelityDifference(step, path, "invalid_ignored_path", "response-only", path)
            )
            return
        if not scoped and compared_steps != 1:
            differences.append(
                FidelityDifference(
                    None,
                    path,
                    "unscoped_ignored_path",
                    "step-scoped volatility required for multi-step traces",
                    path,
                )
            )
            return
        admitted.setdefault(step, set()).add(path)

    for path in ignored_paths:
        admit(0, path, scoped=False)

    if ignored_paths_by_step is not None:
        for step, paths in ignored_paths_by_step.items():
            if not isinstance(step, int) or isinstance(step, bool):
                differences.append(
                    FidelityDifference(None, (), "invalid_ignored_step", "integer", step)
                )
                continue
            for path in paths:
                admit(step, path, scoped=True)

    return {step: frozenset(paths) for step, paths in admitted.items()}


def _compare_json(
    reference: Any,
    twin: Any,
    *,
    step: int,
    path: JsonPath,
    ignored_paths: frozenset[JsonPath],
    differences: list[FidelityDifference],
) -> None:
    if _path_is_ignored(path, ignored_paths):
        return

    if isinstance(reference, Mapping) and isinstance(twin, Mapping):
        reference_keys = set(reference)
        twin_keys = set(twin)
        for key in sorted(reference_keys | twin_keys):
            child_path = (*path, str(key))
            if _path_is_ignored(child_path, ignored_paths):
                continue
            if key not in reference:
                differences.append(
                    FidelityDifference(step, child_path, "unexpected_key", None, twin[key])
                )
                continue
            if key not in twin:
                differences.append(
                    FidelityDifference(step, child_path, "missing_key", reference[key], None)
                )
                continue
            _compare_json(
                reference[key],
                twin[key],
                step=step,
                path=child_path,
                ignored_paths=ignored_paths,
                differences=differences,
            )
        return

    if isinstance(reference, Sequence) and not isinstance(reference, (str, bytes)):
        if not (isinstance(twin, Sequence) and not isinstance(twin, (str, bytes))):
            differences.append(
                FidelityDifference(
                    step,
                    path,
                    "type_mismatch",
                    type(reference).__name__,
                    type(twin).__name__,
                )
            )
            return
        if len(reference) != len(twin):
            differences.append(
                FidelityDifference(step, path, "length_mismatch", len(reference), len(twin))
            )
        for index, (reference_item, twin_item) in enumerate(zip(reference, twin, strict=False)):
            _compare_json(
                reference_item,
                twin_item,
                step=step,
                path=(*path, index),
                ignored_paths=ignored_paths,
                differences=differences,
            )
        return

    if reference != twin:
        differences.append(FidelityDifference(step, path, "value_mismatch", reference, twin))


def compare_cloud_traces(
    reference: Iterable[CloudTraceStep],
    twin: Iterable[CloudTraceStep],
    *,
    ignored_paths: Iterable[JsonPath] = (),
    ignored_paths_by_step: IgnoredPathsByStep | None = None,
) -> CloudFidelityResult:
    """Compare two cloud traces at the agent-visible boundary.

    Volatility is fail-closed: nothing is ignored implicitly. Suppression is
    response-only and, for multi-step traces, must be bound to the exact step
    whose provider response is legitimately non-deterministic. Legacy global
    ``ignored_paths`` therefore remains valid only for one-step traces.
    Transport, operation, request, status code and provider error code are not
    suppressible.
    """

    reference_steps = tuple(reference)
    twin_steps = tuple(twin)
    differences: list[FidelityDifference] = []

    if len(reference_steps) != len(twin_steps):
        differences.append(
            FidelityDifference(None, (), "step_count_mismatch", len(reference_steps), len(twin_steps))
        )

    compared_steps = min(len(reference_steps), len(twin_steps))
    ignored_by_step = _admit_ignored_paths(
        compared_steps=compared_steps,
        ignored_paths=ignored_paths,
        ignored_paths_by_step=ignored_paths_by_step,
        differences=differences,
    )

    for index, (reference_step, twin_step) in enumerate(
        zip(reference_steps, twin_steps, strict=False)
    ):
        for field in ("surface", "operation", "status_code", "error_code"):
            reference_value = getattr(reference_step, field)
            twin_value = getattr(twin_step, field)
            if reference_value != twin_value:
                differences.append(
                    FidelityDifference(
                        index,
                        (field,),
                        "contract_mismatch",
                        reference_value,
                        twin_value,
                    )
                )

        ignored = ignored_by_step.get(index, frozenset())
        _compare_json(
            reference_step.request,
            twin_step.request,
            step=index,
            path=("request",),
            ignored_paths=ignored,
            differences=differences,
        )
        _compare_json(
            reference_step.response,
            twin_step.response,
            step=index,
            path=("response",),
            ignored_paths=ignored,
            differences=differences,
        )

    return CloudFidelityResult(
        equivalent=not differences,
        compared_steps=compared_steps,
        differences=tuple(differences),
    )
