from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
JsonPath = tuple[str | int, ...]


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


def _path_is_ignored(path: JsonPath, ignored_paths: frozenset[JsonPath]) -> bool:
    return path in ignored_paths


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
) -> CloudFidelityResult:
    """Compare two cloud traces at the agent-visible boundary.

    Volatility is fail-closed: nothing is ignored implicitly. A caller must
    name each JSON path that is legitimately non-deterministic. Transport,
    operation, status code and provider error code are never suppressible by
    ``ignored_paths`` because they are top-level contract fields rather than
    response payload details.
    """

    reference_steps = tuple(reference)
    twin_steps = tuple(twin)
    ignored = frozenset(tuple(path) for path in ignored_paths)
    differences: list[FidelityDifference] = []

    if len(reference_steps) != len(twin_steps):
        differences.append(
            FidelityDifference(None, (), "step_count_mismatch", len(reference_steps), len(twin_steps))
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
        compared_steps=min(len(reference_steps), len(twin_steps)),
        differences=tuple(differences),
    )
