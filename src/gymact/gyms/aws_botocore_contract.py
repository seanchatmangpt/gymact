from __future__ import annotations

import json
import re
from typing import Any

from gymact.gyms.cloud_contract import (
    CloudConditionalRequiredPathRule,
    CloudContractEvidence,
    CloudContractProfile,
    CloudContractSource,
    CloudErrorStatusRule,
    CloudOperationContract,
    digest_cloud_contract_source,
)


class AwsBotocoreContractCompilationError(ValueError):
    """Fail closed on malformed botocore service models."""


def _pascal_to_snake(value: str) -> str:
    first = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first).lower()


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AwsBotocoreContractCompilationError(f"{field} must be an object")
    return value


def _shape_path_contract(
    shapes: dict[str, Any], shape_ref: Any, operation: str, *, field: str, root: str
) -> tuple[tuple[tuple[str, ...], ...], tuple[CloudConditionalRequiredPathRule, ...]]:
    if shape_ref is None:
        return (), ()
    ref = _mapping(shape_ref, f"operations.{operation}.{field}")
    shape_name = ref.get("shape")
    if not isinstance(shape_name, str) or not shape_name:
        raise AwsBotocoreContractCompilationError(
            f"operations.{operation}.{field}.shape must be a non-empty string"
        )

    unconditional: set[tuple[str, ...]] = set()
    conditional: set[tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]] = set()

    def walk(
        current: str,
        prefix: tuple[str, ...],
        guards: tuple[tuple[str, ...], ...],
        ancestry: tuple[str, ...],
        *,
        operation_root: bool = False,
    ) -> None:
        shape = _mapping(shapes.get(current), f"shapes.{current}")
        shape_type = shape.get("type")
        if not isinstance(shape_type, str) or not shape_type:
            raise AwsBotocoreContractCompilationError(
                f"shapes.{current}.type must be a non-empty string"
            )
        if shape_type != "structure":
            if operation_root:
                raise AwsBotocoreContractCompilationError(
                    f"shapes.{current}.type must be 'structure' for an operation input/output"
                )
            return

        required_raw = shape.get("required", [])
        if not isinstance(required_raw, list) or any(
            not isinstance(member, str) or not member for member in required_raw
        ):
            raise AwsBotocoreContractCompilationError(
                f"shapes.{current}.required must be a list of non-empty strings"
            )
        required = set(required_raw)
        members = _mapping(shape.get("members", {}), f"shapes.{current}.members")
        for member in required:
            if member not in members:
                raise AwsBotocoreContractCompilationError(
                    f"shapes.{current}.required member {member!r} is absent from members"
                )

        for member in sorted(members):
            member_ref = _mapping(members[member], f"shapes.{current}.members.{member}")
            child = member_ref.get("shape")
            if not isinstance(child, str) or not child:
                raise AwsBotocoreContractCompilationError(
                    f"shapes.{current}.members.{member}.shape must be a non-empty string"
                )
            child_shape = _mapping(shapes.get(child), f"shapes.{child}")
            child_type = child_shape.get("type")
            if not isinstance(child_type, str) or not child_type:
                raise AwsBotocoreContractCompilationError(
                    f"shapes.{child}.type must be a non-empty string"
                )

            member_path = (root, *prefix, member)
            next_guards = guards
            if member in required:
                if guards:
                    conditional.add((guards, member_path))
                else:
                    unconditional.add(member_path)
            elif child_type == "structure":
                next_guards = (*guards, member_path)

            if child_type == "structure" and child not in ancestry:
                walk(child, (*prefix, member), next_guards, (*ancestry, child))

    walk(shape_name, (), (), (shape_name,), operation_root=True)
    rules = tuple(
        CloudConditionalRequiredPathRule(guard_paths=guards, path=path)
        for guards, path in sorted(conditional, key=repr)
    )
    return tuple(sorted(unconditional, key=repr)), rules


def _error_contract(
    shapes: dict[str, Any], errors: Any, operation: str
) -> tuple[tuple[str | None, ...], tuple[int, ...], tuple[CloudErrorStatusRule, ...]]:
    if errors is None:
        return (None,), (), ()
    if not isinstance(errors, list):
        raise AwsBotocoreContractCompilationError(
            f"operations.{operation}.errors must be an array"
        )
    codes: set[str | None] = {None}
    statuses: set[int] = set()
    statuses_by_code: dict[str, set[int]] = {}
    for index, error_ref in enumerate(errors):
        ref = _mapping(error_ref, f"operations.{operation}.errors[{index}]")
        shape_name = ref.get("shape")
        if not isinstance(shape_name, str) or not shape_name:
            raise AwsBotocoreContractCompilationError(
                f"operations.{operation}.errors[{index}].shape must be a non-empty string"
            )
        shape = _mapping(shapes.get(shape_name), f"shapes.{shape_name}")
        error = _mapping(shape.get("error", {}), f"shapes.{shape_name}.error")
        code = error.get("code")
        if code is not None:
            if not isinstance(code, str) or not code:
                raise AwsBotocoreContractCompilationError(
                    f"shapes.{shape_name}.error.code must be a non-empty string"
                )
            codes.add(code)
        status = error.get("httpStatusCode")
        if status is not None:
            if not isinstance(status, int) or isinstance(status, bool):
                raise AwsBotocoreContractCompilationError(
                    f"shapes.{shape_name}.error.httpStatusCode must be an integer"
                )
            statuses.add(status)
        if code is not None and status is not None:
            statuses_by_code.setdefault(code, set()).add(status)
    ordered_codes = tuple(sorted(codes, key=lambda value: "" if value is None else value))
    rules = tuple(
        CloudErrorStatusRule(error_code=code, status_codes=tuple(sorted(code_statuses)))
        for code, code_statuses in sorted(statuses_by_code.items())
    )
    return ordered_codes, tuple(sorted(statuses)), rules


def compile_aws_botocore_contract(
    source_document: bytes, *, source_uri: str
) -> CloudContractEvidence:
    if not isinstance(source_document, bytes):
        raise TypeError("source_document must be bytes")
    if not isinstance(source_uri, str) or not source_uri.strip():
        raise AwsBotocoreContractCompilationError("source_uri must be non-empty")
    try:
        model = json.loads(source_document)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AwsBotocoreContractCompilationError("source_document must be valid UTF-8 JSON") from exc
    model = _mapping(model, "service_model")
    metadata = _mapping(model.get("metadata"), "metadata")
    service = metadata.get("endpointPrefix")
    api_version = metadata.get("apiVersion")
    if not isinstance(service, str) or not service:
        raise AwsBotocoreContractCompilationError("metadata.endpointPrefix must be non-empty")
    if not isinstance(api_version, str) or not api_version:
        raise AwsBotocoreContractCompilationError("metadata.apiVersion must be non-empty")
    operations = _mapping(model.get("operations"), "operations")
    shapes = _mapping(model.get("shapes"), "shapes")
    if not operations:
        raise AwsBotocoreContractCompilationError("operations must not be empty")

    contracts: list[CloudOperationContract] = []
    for operation_name in sorted(operations):
        operation = _mapping(operations[operation_name], f"operations.{operation_name}")
        required_paths, conditional_required_paths = _shape_path_contract(
            shapes, operation.get("input"), operation_name, field="input", root="request"
        )
        success_required_paths, success_conditional_required_paths = _shape_path_contract(
            shapes, operation.get("output"), operation_name, field="output", root="response"
        )
        http = _mapping(operation.get("http", {}), f"operations.{operation_name}.http")
        success_status = http.get("responseCode", 200)
        if not isinstance(success_status, int) or isinstance(success_status, bool):
            raise AwsBotocoreContractCompilationError(
                f"operations.{operation_name}.http.responseCode must be an integer"
            )
        error_codes, error_statuses, error_status_rules = _error_contract(
            shapes, operation.get("errors"), operation_name
        )
        contracts.append(
            CloudOperationContract(
                surface="boto3",
                operation=f"{service}.{_pascal_to_snake(operation_name)}",
                required_paths=required_paths,
                success_required_paths=success_required_paths,
                conditional_required_paths=conditional_required_paths,
                success_conditional_required_paths=success_conditional_required_paths,
                allowed_status_codes=tuple(sorted({success_status, *error_statuses})),
                allowed_error_codes=error_codes,
                error_status_rules=error_status_rules,
            )
        )

    return CloudContractEvidence(
        profile=CloudContractProfile(
            name=f"aws-botocore:{service}:{api_version}", operations=tuple(contracts)
        ),
        source=CloudContractSource(
            uri=source_uri.strip(),
            digest=digest_cloud_contract_source(source_document),
            media_type="application/json",
        ),
    )
