from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any, Iterable, Literal

import blake3
import rfc8785

from gymact.gyms.cloud_contract import digest_cloud_contract_source
from gymact.gyms.cloud_fidelity import CloudTraceStep, FidelityDifference, JsonPath


class AwsBotocoreCollectionContractCompilationError(ValueError):
    """Fail closed when collection contract law cannot be manufactured exactly."""


@dataclass(frozen=True, slots=True)
class AwsCollectionElementRule:
    container_path: JsonPath
    container_kind: Literal["list", "map"]
    required_relative_paths: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class AwsOperationCollectionContract:
    surface: str
    operation: str
    rules: tuple[AwsCollectionElementRule, ...] = ()
    success_rules: tuple[AwsCollectionElementRule, ...] = ()


@dataclass(frozen=True, slots=True)
class AwsBotocoreCollectionContract:
    name: str
    source_uri: str
    source_digest: str
    operations: tuple[AwsOperationCollectionContract, ...]


@dataclass(frozen=True, slots=True)
class AwsBotocoreCollectionReceipt:
    digest: str
    source_digest: str
    operation_count: int
    rule_count: int


@dataclass(frozen=True, slots=True)
class AwsBotocoreCollectionResult:
    admitted: bool
    checked_steps: int
    checked_collection_members: int
    differences: tuple[FidelityDifference, ...]


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AwsBotocoreCollectionContractCompilationError(f"{field} must be an object")
    return value


def _pascal_to_snake(value: str) -> str:
    out: list[str] = []
    for index, char in enumerate(value):
        if index and char.isupper() and (not value[index - 1].isupper() or (index + 1 < len(value) and value[index + 1].islower())):
            out.append("_")
        out.append(char.lower())
    return "".join(out)


def _shape(shapes: dict[str, Any], name: str) -> dict[str, Any]:
    value = shapes.get(name)
    if value is None:
        raise AwsBotocoreCollectionContractCompilationError(f"shapes.{name} is missing")
    shape = _mapping(value, f"shapes.{name}")
    kind = shape.get("type")
    if not isinstance(kind, str) or not kind:
        raise AwsBotocoreCollectionContractCompilationError(
            f"shapes.{name}.type must be a non-empty string"
        )
    return shape


def _required_structure_paths(
    shapes: dict[str, Any], shape_name: str, ancestry: tuple[str, ...] = ()
) -> tuple[tuple[str, ...], ...]:
    shape = _shape(shapes, shape_name)
    if shape["type"] != "structure":
        return ()
    if shape_name in ancestry:
        return ()
    required_raw = shape.get("required", [])
    if not isinstance(required_raw, list) or any(not isinstance(item, str) or not item for item in required_raw):
        raise AwsBotocoreCollectionContractCompilationError(
            f"shapes.{shape_name}.required must be a list of non-empty strings"
        )
    members = _mapping(shape.get("members", {}), f"shapes.{shape_name}.members")
    result: set[tuple[str, ...]] = set()
    for member in sorted(required_raw):
        if member not in members:
            raise AwsBotocoreCollectionContractCompilationError(
                f"shapes.{shape_name}.required member {member!r} is absent from members"
            )
        ref = _mapping(members[member], f"shapes.{shape_name}.members.{member}")
        child = ref.get("shape")
        if not isinstance(child, str) or not child:
            raise AwsBotocoreCollectionContractCompilationError(
                f"shapes.{shape_name}.members.{member}.shape must be a non-empty string"
            )
        child_shape = _shape(shapes, child)
        result.add((member,))
        if child_shape["type"] == "structure":
            for nested in _required_structure_paths(shapes, child, (*ancestry, shape_name)):
                result.add((member, *nested))
    return tuple(sorted(result, key=repr))


def _collection_member_shape(
    shapes: dict[str, Any], shape_name: str, kind: str
) -> tuple[str, tuple[tuple[str, ...], ...]]:
    shape = _shape(shapes, shape_name)
    field = "member" if kind == "list" else "value"
    ref = _mapping(shape.get(field), f"shapes.{shape_name}.{field}")
    child = ref.get("shape")
    if not isinstance(child, str) or not child:
        raise AwsBotocoreCollectionContractCompilationError(
            f"shapes.{shape_name}.{field}.shape must be a non-empty string"
        )
    child_shape = _shape(shapes, child)
    if child_shape["type"] in {"list", "map"}:
        raise AwsBotocoreCollectionContractCompilationError(
            f"nested collection shape {child!r} is unsupported by this bounded algebra"
        )
    return child, _required_structure_paths(shapes, child)


def _rules_for_root(
    shapes: dict[str, Any], shape_ref: Any, operation: str, *, field: str, root: str
) -> tuple[AwsCollectionElementRule, ...]:
    if shape_ref is None:
        return ()
    ref = _mapping(shape_ref, f"operations.{operation}.{field}")
    root_shape = ref.get("shape")
    if not isinstance(root_shape, str) or not root_shape:
        raise AwsBotocoreCollectionContractCompilationError(
            f"operations.{operation}.{field}.shape must be a non-empty string"
        )
    if _shape(shapes, root_shape)["type"] != "structure":
        raise AwsBotocoreCollectionContractCompilationError(
            f"shapes.{root_shape}.type must be 'structure' for an operation input/output"
        )

    rules: set[AwsCollectionElementRule] = set()

    def walk_structure(current: str, prefix: tuple[str, ...], ancestry: tuple[str, ...]) -> None:
        if current in ancestry:
            return
        shape = _shape(shapes, current)
        if shape["type"] != "structure":
            return
        members = _mapping(shape.get("members", {}), f"shapes.{current}.members")
        for member in sorted(members):
            member_ref = _mapping(members[member], f"shapes.{current}.members.{member}")
            child = member_ref.get("shape")
            if not isinstance(child, str) or not child:
                raise AwsBotocoreCollectionContractCompilationError(
                    f"shapes.{current}.members.{member}.shape must be a non-empty string"
                )
            child_shape = _shape(shapes, child)
            path = (root, *prefix, member)
            if child_shape["type"] in {"list", "map"}:
                _, required_paths = _collection_member_shape(shapes, child, child_shape["type"])
                if required_paths:
                    rules.add(
                        AwsCollectionElementRule(
                            container_path=path,
                            container_kind=child_shape["type"],
                            required_relative_paths=required_paths,
                        )
                    )
            elif child_shape["type"] == "structure":
                walk_structure(child, (*prefix, member), (*ancestry, current))

    walk_structure(root_shape, (), ())
    return tuple(sorted(rules, key=lambda rule: (repr(rule.container_path), rule.container_kind, repr(rule.required_relative_paths))))


def compile_aws_botocore_collection_contract(
    source_document: bytes, *, source_uri: str
) -> AwsBotocoreCollectionContract:
    if not isinstance(source_document, bytes):
        raise TypeError("source_document must be bytes")
    if not isinstance(source_uri, str) or not source_uri.strip():
        raise AwsBotocoreCollectionContractCompilationError("source_uri must be non-empty")
    try:
        model = json.loads(source_document)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AwsBotocoreCollectionContractCompilationError(
            "source_document must be valid UTF-8 JSON"
        ) from exc
    model = _mapping(model, "service_model")
    metadata = _mapping(model.get("metadata"), "metadata")
    service = metadata.get("endpointPrefix")
    api_version = metadata.get("apiVersion")
    if not isinstance(service, str) or not service:
        raise AwsBotocoreCollectionContractCompilationError("metadata.endpointPrefix must be non-empty")
    if not isinstance(api_version, str) or not api_version:
        raise AwsBotocoreCollectionContractCompilationError("metadata.apiVersion must be non-empty")
    operations = _mapping(model.get("operations"), "operations")
    shapes = _mapping(model.get("shapes"), "shapes")
    if not operations:
        raise AwsBotocoreCollectionContractCompilationError("operations must not be empty")

    compiled: list[AwsOperationCollectionContract] = []
    for operation_name in sorted(operations):
        operation = _mapping(operations[operation_name], f"operations.{operation_name}")
        compiled.append(
            AwsOperationCollectionContract(
                surface="boto3",
                operation=f"{service}.{_pascal_to_snake(operation_name)}",
                rules=_rules_for_root(
                    shapes, operation.get("input"), operation_name, field="input", root="request"
                ),
                success_rules=_rules_for_root(
                    shapes, operation.get("output"), operation_name, field="output", root="response"
                ),
            )
        )
    return AwsBotocoreCollectionContract(
        name=f"aws-botocore-collections:{service}:{api_version}",
        source_uri=source_uri.strip(),
        source_digest=digest_cloud_contract_source(source_document),
        operations=tuple(compiled),
    )


def _rule_payload(rule: AwsCollectionElementRule) -> dict[str, Any]:
    return {
        "container_path": list(rule.container_path),
        "container_kind": rule.container_kind,
        "required_relative_paths": [list(path) for path in rule.required_relative_paths],
    }


def _contract_payload(contract: AwsBotocoreCollectionContract) -> dict[str, Any]:
    return {
        "name": contract.name,
        "source_uri": contract.source_uri,
        "source_digest": contract.source_digest,
        "operations": [
            {
                "surface": operation.surface,
                "operation": operation.operation,
                "rules": [_rule_payload(rule) for rule in operation.rules],
                "success_rules": [_rule_payload(rule) for rule in operation.success_rules],
            }
            for operation in sorted(contract.operations, key=lambda item: (item.surface, item.operation))
        ],
    }


def receipt_aws_botocore_collection_contract(
    contract: AwsBotocoreCollectionContract,
) -> AwsBotocoreCollectionReceipt:
    canonical = rfc8785.dumps(_contract_payload(contract))
    return AwsBotocoreCollectionReceipt(
        digest=blake3.blake3(canonical).hexdigest(),
        source_digest=contract.source_digest,
        operation_count=len(contract.operations),
        rule_count=sum(len(operation.rules) + len(operation.success_rules) for operation in contract.operations),
    )


def replay_aws_botocore_collection_contract(
    contract: AwsBotocoreCollectionContract, receipt: AwsBotocoreCollectionReceipt
) -> bool:
    return receipt_aws_botocore_collection_contract(contract) == receipt


def _lookup(step: CloudTraceStep, path: JsonPath) -> tuple[bool, Any]:
    if not path or path[0] not in {"request", "response"}:
        return False, None
    value: Any = getattr(step, path[0])
    for token in path[1:]:
        if isinstance(token, int):
            if not isinstance(value, list) or token < 0 or token >= len(value):
                return False, None
            value = value[token]
        else:
            if not isinstance(value, dict) or token not in value:
                return False, None
            value = value[token]
    return True, value


def _relative_present(value: Any, path: tuple[str, ...]) -> bool:
    current = value
    for token in path:
        if not isinstance(current, dict) or token not in current:
            return False
        current = current[token]
    return True


def _validate_rule(
    *,
    step_index: int,
    step: CloudTraceStep,
    rule: AwsCollectionElementRule,
    side: str,
    differences: list[FidelityDifference],
) -> int:
    found, collection = _lookup(step, rule.container_path)
    if not found:
        return 0
    expected_type = list if rule.container_kind == "list" else dict
    if not isinstance(collection, expected_type):
        differences.append(
            FidelityDifference(
                step_index,
                rule.container_path,
                f"{side}_collection_type_mismatch",
                rule.container_kind,
                type(collection).__name__,
            )
        )
        return 0
    members = enumerate(collection) if isinstance(collection, list) else ((key, collection[key]) for key in sorted(collection))
    checked = 0
    for member_key, member_value in members:
        checked += 1
        for relative in rule.required_relative_paths:
            concrete = (*rule.container_path, member_key, *relative)
            if not _relative_present(member_value, relative):
                differences.append(
                    FidelityDifference(
                        step_index,
                        concrete,
                        f"{side}_collection_missing_required_element_path",
                        "present",
                        None,
                    )
                )
    return checked


def validate_aws_botocore_collection_contract(
    trace: Iterable[CloudTraceStep],
    contract: AwsBotocoreCollectionContract,
    *,
    side: str = "trace",
) -> AwsBotocoreCollectionResult:
    steps = tuple(trace)
    differences: list[FidelityDifference] = []
    index = {(item.surface, item.operation): item for item in contract.operations}
    if len(index) != len(contract.operations):
        differences.append(
            FidelityDifference(None, ("collection_contract",), f"{side}_duplicate_collection_operation", "unique surface+operation", None)
        )
    checked_members = 0
    for step_index, step in enumerate(steps):
        operation = index.get((step.surface, step.operation))
        if operation is None:
            continue
        for rule in operation.rules:
            checked_members += _validate_rule(
                step_index=step_index,
                step=step,
                rule=rule,
                side=side,
                differences=differences,
            )
        if step.error_code is None:
            for rule in operation.success_rules:
                checked_members += _validate_rule(
                    step_index=step_index,
                    step=step,
                    rule=rule,
                    side=side,
                    differences=differences,
                )
    return AwsBotocoreCollectionResult(
        admitted=not differences,
        checked_steps=len(steps),
        checked_collection_members=checked_members,
        differences=tuple(differences),
    )


def without_collection_rules(
    contract: AwsBotocoreCollectionContract,
) -> AwsBotocoreCollectionContract:
    """Explicit rejected-alternative helper used to falsify receipt weakening."""
    return replace(
        contract,
        operations=tuple(replace(operation, rules=(), success_rules=()) for operation in contract.operations),
    )
