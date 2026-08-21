from __future__ import annotations

import json
import re
from typing import Any

from gymact.gyms.cloud_contract import (
    CloudContractEvidence,
    CloudContractProfile,
    CloudContractSource,
    CloudOperationContract,
    digest_cloud_contract_source,
)


class AwsBotocoreContractCompilationError(ValueError):
    """Fail-closed error for malformed or ambiguous botocore service models."""


def _pascal_to_snake(value: str) -> str:
    first = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first).lower()


def _as_mapping(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AwsBotocoreContractCompilationError(f"{field} must be an object")
    return value


def _shape_required_paths(
    shapes: dict[str, Any],
    shape_ref: Any,
    *,
    root: str,
    operation: str,
) -> tuple[tuple[str, str], ...]:
    if shape_ref is None:
        return ()
    ref = _as_mapping(shape_ref, field=f"operations.{operation}.{root}")
    shape_name = ref.get("shape")
    if not isinstance(shape_name, str) or not shape_name:
        raise AwsBotocoreContractCompilationError(
            f"operations.{operation}.{root}.shape must be a non-empty string"
        )
    shape = _as_mapping(shapes.get(shape_name), field=f"shapes.{shape_name}")
    required = shape.get("required", [])
    if not isinstance(required, list) or any(
        not isinstance(member, str) or not member for member in required
    ):
        raise AwsBotocoreContractCompilationError(
            f"shapes.{shape_name}.required must be a list of non-empty strings"
        )
    return tuple((root, member) for member in sorted(set(required)))


def _operation_error_contract(
    shapes: dict[str, Any],
    errors: Any,
    *,
    operation: str,
) -> tuple[tuple[str | None, ...], tuple[int, ...]]:
    if errors is None:
        return (None,), ()
    if not isinstance(errors, list):
        raise AwsBotocoreContractCompilationError(
            f"operations.{operation}.errors must be an array"
        )

    codes: set[str | None] = {None}
    statuses: set[int] = set()
    for index, error_ref in enumerate(errors):
        ref = _as_mapping(error_ref, field=f"operations.{operation}.errors[{index}]")
        shape_name = ref.get("shape")
        if not isinstance(shape_name, str) or not shape_name:
            raise AwsBotocoreContractCompilationError(
                f"operations.{operation}.errors[{index}].shape must be a non-empty string"
            )
        shape = _as_mapping(shapes.get(shape_name), field=f"shapes.{shape_name}")
        error = shape.get("error", {})
        if error is None:
            error = {}
        error = _as_mapping(error, field=f"shapes.{shape_name}.error")
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
    return tuple(sorted(codes, key=lambda value: "" if value is None else value)), tuple(
        sorted(statuses)
    )


def compile_aws_botocore_contract(
    source_document: bytes,
    *,
    source_uri: str,
) -> CloudContractEvidence:
    """Manufacture a boto3 fidelity contract from exact botocore service-model bytes.

    This is SELECT/CONSTRUCT evidence only. Parsing a provider model grants no
    cloud credentials, execution authority, or BRCE standing.
    """

    if not isinstance(source_document, bytes):
        raise TypeError("source_document must be bytes")
    if not isinstance(source_uri, str) or not source_uri.strip():
        raise AwsBotocoreContractCompilationError(
            "source_uri must be a non-empty provider-source identity"
        )
    try:
        decoded = json.loads(source_document)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AwsBotocoreContractCompilationError(
            "source_document must be valid UTF-8 JSON"
        ) from exc

    model = _as_mapping(decoded, field="service_model")
    metadata = _as_mapping(model.get("metadata"), field="metadata")
    service = metadata.get("endpointPrefix")
    api_version = metadata.get("apiVersion")
    if not isinstance(service, str) or not service:
        raise AwsBotocoreContractCompilationError(
            "metadata.endpointPrefix must be a non-empty string"
        )
    if not isinstance(api_version, str) or not api_version:
        raise AwsBotocoreContractCompilationError(
            "metadata.apiVersion must be a non-empty string"
        )

    operations = _as_mapping(model.get("operations"), field="operations")
    shapes = _as_mapping(model.get("shapes"), field="shapes")
    if not operations:
        raise AwsBotocoreContractCompilationError("operations must not be empty")

    contracts: list[CloudOperationContract] = []
    for operation_name in sorted(operations):
        if not isinstance(operation_name, str) or not operation_name:
            raise AwsBotocoreContractCompilationError(
                "operation names must be non-empty strings"
            )
        operation = _as_mapping(
            operations[operation_name],
            field=f"operations.{operation_name}",
        )
        required_paths = (
            *_shape_required_paths(
                shapes,
                operation.get("input"),
                root="request",
                operation=operation_name,
            ),
            *_shape_required_paths(
                shapes,
                operation.get("output"),
                root="response",
                operation=operation_name,
            ),
        )
        http = operation.get("http", {})
        if http is None:
            http = {}
        http = _as_mapping(http, field=f"operations.{operation_name}.http")
        success_status = http.get("responseCode", 200)
        if not isinstance(success_status, int) or isinstance(success_status, bool):
            raise AwsBotocoreContractCompilationError(
                f"operations.{operation_name}.http.responseCode must be an integer"
            )
        error_codes, error_statuses = _operation_error_contract(
            shapes,
            operation.get("errors"),
            operation=operation_name,
        )
        contracts.append(
            CloudOperationContract(
                surface="boto3",
                operation=f"{service}.{_pascal_to_snake(operation_name)}",
                required_paths=tuple(required_paths),
                allowed_status_codes=tuple(sorted({success_status, *error_statuses})),
                allowed_error_codes=error_codes,
            )
        )

    profile = CloudContractProfile(
        name=f"aws-botocore:{service}:{api_version}",
        operations=tuple(contracts),
    )
    return CloudContractEvidence(
        profile=profile,
        source=CloudContractSource(
            uri=source_uri.strip(),
            digest=digest_cloud_contract_source(source_document),
            media_type="application/json",
        ),
    )
