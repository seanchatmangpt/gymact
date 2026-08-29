from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any, Iterable, Literal

import blake3
import rfc8785

from gymact.gyms.cloud_contract import digest_cloud_contract_source
from gymact.gyms.cloud_fidelity import CloudTraceStep, FidelityDifference, JsonPath


class AwsBotocoreCardinalityContractCompilationError(ValueError):
    """Fail closed when botocore collection cardinality law is malformed."""


@dataclass(frozen=True, slots=True)
class AwsCardinalityTraversalStep:
    relative_path: tuple[str, ...]
    container_kind: Literal["list", "map"]


@dataclass(frozen=True, slots=True)
class AwsCollectionCardinalityRule:
    container_path: JsonPath
    container_kind: Literal["list", "map"]
    min_items: int | None = None
    max_items: int | None = None
    nested_collections: tuple[AwsCardinalityTraversalStep, ...] = ()


@dataclass(frozen=True, slots=True)
class AwsOperationCardinalityContract:
    surface: str
    operation: str
    rules: tuple[AwsCollectionCardinalityRule, ...] = ()
    success_rules: tuple[AwsCollectionCardinalityRule, ...] = ()


@dataclass(frozen=True, slots=True)
class AwsBotocoreCardinalityContract:
    name: str
    source_uri: str
    source_digest: str
    operations: tuple[AwsOperationCardinalityContract, ...]


@dataclass(frozen=True, slots=True)
class AwsBotocoreCardinalityReceipt:
    digest: str
    source_digest: str
    operation_count: int
    rule_count: int


@dataclass(frozen=True, slots=True)
class AwsBotocoreCardinalityResult:
    admitted: bool
    checked_steps: int
    checked_collections: int
    differences: tuple[FidelityDifference, ...]


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AwsBotocoreCardinalityContractCompilationError(f"{field} must be an object")
    return value


def _shape(shapes: dict[str, Any], name: str) -> dict[str, Any]:
    value = shapes.get(name)
    if value is None:
        raise AwsBotocoreCardinalityContractCompilationError(f"shapes.{name} is missing")
    shape = _mapping(value, f"shapes.{name}")
    kind = shape.get("type")
    if not isinstance(kind, str) or not kind:
        raise AwsBotocoreCardinalityContractCompilationError(
            f"shapes.{name}.type must be a non-empty string"
        )
    return shape


def _pascal_to_snake(value: str) -> str:
    out: list[str] = []
    for index, char in enumerate(value):
        if index and char.isupper() and (
            not value[index - 1].isupper()
            or (index + 1 < len(value) and value[index + 1].islower())
        ):
            out.append("_")
        out.append(char.lower())
    return "".join(out)


def _collection_child(shapes: dict[str, Any], shape_name: str) -> tuple[str, str]:
    shape = _shape(shapes, shape_name)
    kind = shape["type"]
    if kind not in {"list", "map"}:
        raise AwsBotocoreCardinalityContractCompilationError(
            f"shapes.{shape_name}.type must be list or map for collection traversal"
        )
    field = "member" if kind == "list" else "value"
    ref = _mapping(shape.get(field), f"shapes.{shape_name}.{field}")
    child = ref.get("shape")
    if not isinstance(child, str) or not child:
        raise AwsBotocoreCardinalityContractCompilationError(
            f"shapes.{shape_name}.{field}.shape must be a non-empty string"
        )
    return child, _shape(shapes, child)["type"]


def _bound(shape: dict[str, Any], field: Literal["min", "max"], shape_name: str) -> int | None:
    value = shape.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AwsBotocoreCardinalityContractCompilationError(
            f"shapes.{shape_name}.{field} must be a non-negative integer"
        )
    return value


def _cardinality_for_shape(
    shapes: dict[str, Any], shape_name: str
) -> tuple[int | None, int | None]:
    shape = _shape(shapes, shape_name)
    minimum = _bound(shape, "min", shape_name)
    maximum = _bound(shape, "max", shape_name)
    if minimum is not None and maximum is not None and minimum > maximum:
        raise AwsBotocoreCardinalityContractCompilationError(
            f"shapes.{shape_name}.min must be <= max"
        )
    return minimum, maximum


def _collection_rules(
    shapes: dict[str, Any],
    collection_shape: str,
    *,
    container_path: JsonPath,
    outer_kind: Literal["list", "map"],
    nested: tuple[AwsCardinalityTraversalStep, ...] = (),
    ancestry: tuple[str, ...] = (),
) -> set[AwsCollectionCardinalityRule]:
    if collection_shape in ancestry:
        chain = " -> ".join((*ancestry, collection_shape))
        raise AwsBotocoreCardinalityContractCompilationError(
            f"recursive collection cycle is unsupported: {chain}"
        )
    shape = _shape(shapes, collection_shape)
    kind = shape["type"]
    if kind not in {"list", "map"}:
        raise AwsBotocoreCardinalityContractCompilationError(
            f"shapes.{collection_shape}.type must be list or map"
        )
    minimum, maximum = _cardinality_for_shape(shapes, collection_shape)
    rules: set[AwsCollectionCardinalityRule] = set()
    if minimum is not None or maximum is not None:
        rules.add(
            AwsCollectionCardinalityRule(
                container_path=container_path,
                container_kind=outer_kind,
                min_items=minimum,
                max_items=maximum,
                nested_collections=nested,
            )
        )

    child, child_kind = _collection_child(shapes, collection_shape)
    next_ancestry = (*ancestry, collection_shape)
    if child_kind in {"list", "map"}:
        rules.update(
            _collection_rules(
                shapes,
                child,
                container_path=container_path,
                outer_kind=outer_kind,
                nested=(*nested, AwsCardinalityTraversalStep((), child_kind)),
                ancestry=next_ancestry,
            )
        )
        return rules
    if child_kind != "structure":
        return rules

    def walk_structure(
        current: str,
        prefix: tuple[str, ...],
        structure_ancestry: tuple[str, ...],
    ) -> None:
        if current in structure_ancestry:
            return
        current_shape = _shape(shapes, current)
        if current_shape["type"] != "structure":
            return
        members = _mapping(current_shape.get("members", {}), f"shapes.{current}.members")
        for member in sorted(members):
            member_ref = _mapping(members[member], f"shapes.{current}.members.{member}")
            member_shape = member_ref.get("shape")
            if not isinstance(member_shape, str) or not member_shape:
                raise AwsBotocoreCardinalityContractCompilationError(
                    f"shapes.{current}.members.{member}.shape must be a non-empty string"
                )
            member_kind = _shape(shapes, member_shape)["type"]
            member_path = (*prefix, member)
            if member_kind in {"list", "map"}:
                rules.update(
                    _collection_rules(
                        shapes,
                        member_shape,
                        container_path=container_path,
                        outer_kind=outer_kind,
                        nested=(
                            *nested,
                            AwsCardinalityTraversalStep(member_path, member_kind),
                        ),
                        ancestry=next_ancestry,
                    )
                )
            elif member_kind == "structure":
                walk_structure(
                    member_shape,
                    member_path,
                    (*structure_ancestry, current),
                )

    walk_structure(child, (), ())
    return rules


def _rules_for_root(
    shapes: dict[str, Any], shape_ref: Any, operation: str, *, field: str, root: str
) -> tuple[AwsCollectionCardinalityRule, ...]:
    if shape_ref is None:
        return ()
    ref = _mapping(shape_ref, f"operations.{operation}.{field}")
    root_shape = ref.get("shape")
    if not isinstance(root_shape, str) or not root_shape:
        raise AwsBotocoreCardinalityContractCompilationError(
            f"operations.{operation}.{field}.shape must be a non-empty string"
        )
    if _shape(shapes, root_shape)["type"] != "structure":
        raise AwsBotocoreCardinalityContractCompilationError(
            f"shapes.{root_shape}.type must be 'structure' for an operation input/output"
        )

    rules: set[AwsCollectionCardinalityRule] = set()

    def walk_structure(current: str, prefix: tuple[str, ...], ancestry: tuple[str, ...]) -> None:
        if current in ancestry:
            return
        shape = _shape(shapes, current)
        members = _mapping(shape.get("members", {}), f"shapes.{current}.members")
        for member in sorted(members):
            member_ref = _mapping(members[member], f"shapes.{current}.members.{member}")
            child = member_ref.get("shape")
            if not isinstance(child, str) or not child:
                raise AwsBotocoreCardinalityContractCompilationError(
                    f"shapes.{current}.members.{member}.shape must be a non-empty string"
                )
            child_shape = _shape(shapes, child)
            path = (root, *prefix, member)
            if child_shape["type"] in {"list", "map"}:
                rules.update(
                    _collection_rules(
                        shapes,
                        child,
                        container_path=path,
                        outer_kind=child_shape["type"],
                    )
                )
            elif child_shape["type"] == "structure":
                walk_structure(child, (*prefix, member), (*ancestry, current))

    walk_structure(root_shape, (), ())
    return tuple(
        sorted(
            rules,
            key=lambda rule: (
                repr(rule.container_path),
                rule.container_kind,
                repr(rule.nested_collections),
                rule.min_items if rule.min_items is not None else -1,
                rule.max_items if rule.max_items is not None else -1,
            ),
        )
    )


def compile_aws_botocore_cardinality_contract(
    source_document: bytes, *, source_uri: str
) -> AwsBotocoreCardinalityContract:
    if not isinstance(source_document, bytes):
        raise TypeError("source_document must be bytes")
    if not isinstance(source_uri, str) or not source_uri.strip():
        raise AwsBotocoreCardinalityContractCompilationError("source_uri must be non-empty")
    try:
        model = json.loads(source_document)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AwsBotocoreCardinalityContractCompilationError(
            "source_document must be valid UTF-8 JSON"
        ) from exc
    model = _mapping(model, "service_model")
    metadata = _mapping(model.get("metadata"), "metadata")
    service = metadata.get("endpointPrefix")
    api_version = metadata.get("apiVersion")
    if not isinstance(service, str) or not service:
        raise AwsBotocoreCardinalityContractCompilationError(
            "metadata.endpointPrefix must be non-empty"
        )
    if not isinstance(api_version, str) or not api_version:
        raise AwsBotocoreCardinalityContractCompilationError(
            "metadata.apiVersion must be non-empty"
        )
    operations = _mapping(model.get("operations"), "operations")
    shapes = _mapping(model.get("shapes"), "shapes")
    if not operations:
        raise AwsBotocoreCardinalityContractCompilationError("operations must not be empty")

    compiled: list[AwsOperationCardinalityContract] = []
    for operation_name in sorted(operations):
        operation = _mapping(operations[operation_name], f"operations.{operation_name}")
        compiled.append(
            AwsOperationCardinalityContract(
                surface="boto3",
                operation=f"{service}.{_pascal_to_snake(operation_name)}",
                rules=_rules_for_root(
                    shapes,
                    operation.get("input"),
                    operation_name,
                    field="input",
                    root="request",
                ),
                success_rules=_rules_for_root(
                    shapes,
                    operation.get("output"),
                    operation_name,
                    field="output",
                    root="response",
                ),
            )
        )
    return AwsBotocoreCardinalityContract(
        name=f"aws-botocore-cardinality:{service}:{api_version}",
        source_uri=source_uri.strip(),
        source_digest=digest_cloud_contract_source(source_document),
        operations=tuple(compiled),
    )


def _rule_payload(rule: AwsCollectionCardinalityRule) -> dict[str, Any]:
    return {
        "container_path": list(rule.container_path),
        "container_kind": rule.container_kind,
        "min_items": rule.min_items,
        "max_items": rule.max_items,
        "nested_collections": [
            {
                "relative_path": list(step.relative_path),
                "container_kind": step.container_kind,
            }
            for step in rule.nested_collections
        ],
    }


def _contract_payload(contract: AwsBotocoreCardinalityContract) -> dict[str, Any]:
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
            for operation in sorted(
                contract.operations, key=lambda item: (item.surface, item.operation)
            )
        ],
    }


def receipt_aws_botocore_cardinality_contract(
    contract: AwsBotocoreCardinalityContract,
) -> AwsBotocoreCardinalityReceipt:
    canonical = rfc8785.dumps(_contract_payload(contract))
    return AwsBotocoreCardinalityReceipt(
        digest=blake3.blake3(canonical).hexdigest(),
        source_digest=contract.source_digest,
        operation_count=len(contract.operations),
        rule_count=sum(
            len(operation.rules) + len(operation.success_rules)
            for operation in contract.operations
        ),
    )


def replay_aws_botocore_cardinality_contract(
    contract: AwsBotocoreCardinalityContract,
    receipt: AwsBotocoreCardinalityReceipt,
) -> bool:
    return receipt_aws_botocore_cardinality_contract(contract) == receipt


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


def _collection_members(value: Any, kind: Literal["list", "map"]) -> Iterable[tuple[str | int, Any]]:
    if kind == "list":
        if not isinstance(value, list):
            return ()
        return tuple(enumerate(value))
    if not isinstance(value, dict):
        return ()
    return tuple((key, value[key]) for key in sorted(value))


def _lookup_relative(value: Any, path: tuple[str, ...]) -> tuple[bool, Any]:
    current = value
    for token in path:
        if not isinstance(current, dict) or token not in current:
            return False, None
        current = current[token]
    return True, current


def _nested_targets(
    outer_value: Any,
    outer_path: JsonPath,
    outer_kind: Literal["list", "map"],
    nested: tuple[AwsCardinalityTraversalStep, ...],
    *,
    step_index: int,
    differences: list[FidelityDifference],
) -> tuple[tuple[JsonPath, Any, Literal["list", "map"]], ...]:
    current: tuple[tuple[JsonPath, Any, Literal["list", "map"]], ...] = (
        (outer_path, outer_value, outer_kind),
    )
    for traversal in nested:
        next_values: list[tuple[JsonPath, Any, Literal["list", "map"]]] = []
        for path, collection, kind in current:
            expected_type = list if kind == "list" else dict
            if not isinstance(collection, expected_type):
                differences.append(
                    FidelityDifference(
                        step_index,
                        path,
                        "collection_cardinality_type_mismatch",
                        kind,
                        type(collection).__name__,
                    )
                )
                continue
            for key, member in _collection_members(collection, kind):
                found, nested_value = _lookup_relative(member, traversal.relative_path)
                nested_path: JsonPath = (*path, key, *traversal.relative_path)
                if not found:
                    continue
                expected_nested_type = list if traversal.container_kind == "list" else dict
                if not isinstance(nested_value, expected_nested_type):
                    differences.append(
                        FidelityDifference(
                            step_index,
                            nested_path,
                            "collection_cardinality_type_mismatch",
                            traversal.container_kind,
                            type(nested_value).__name__,
                        )
                    )
                    continue
                next_values.append((nested_path, nested_value, traversal.container_kind))
        current = tuple(next_values)
    return current


def _check_rule(
    step: CloudTraceStep,
    step_index: int,
    rule: AwsCollectionCardinalityRule,
    differences: list[FidelityDifference],
) -> int:
    found, outer_value = _lookup(step, rule.container_path)
    if not found:
        return 0
    expected_type = list if rule.container_kind == "list" else dict
    if not isinstance(outer_value, expected_type):
        differences.append(
            FidelityDifference(
                step_index,
                rule.container_path,
                "collection_cardinality_type_mismatch",
                rule.container_kind,
                type(outer_value).__name__,
            )
        )
        return 0
    targets = _nested_targets(
        outer_value,
        rule.container_path,
        rule.container_kind,
        rule.nested_collections,
        step_index=step_index,
        differences=differences,
    )
    checked = 0
    for path, collection, kind in targets:
        expected_target_type = list if kind == "list" else dict
        if not isinstance(collection, expected_target_type):
            continue
        checked += 1
        size = len(collection)
        if rule.min_items is not None and size < rule.min_items:
            differences.append(
                FidelityDifference(
                    step_index,
                    path,
                    "collection_cardinality_below_min",
                    rule.min_items,
                    size,
                )
            )
        if rule.max_items is not None and size > rule.max_items:
            differences.append(
                FidelityDifference(
                    step_index,
                    path,
                    "collection_cardinality_above_max",
                    rule.max_items,
                    size,
                )
            )
    return checked


def validate_aws_botocore_cardinality(
    contract: AwsBotocoreCardinalityContract,
    trace: Iterable[CloudTraceStep],
) -> AwsBotocoreCardinalityResult:
    steps = tuple(trace)
    operation_map = {
        (operation.surface, operation.operation): operation for operation in contract.operations
    }
    differences: list[FidelityDifference] = []
    checked_collections = 0
    for index, step in enumerate(steps):
        operation = operation_map.get((step.surface, step.operation))
        if operation is None:
            differences.append(
                FidelityDifference(
                    index,
                    ("operation",),
                    "cardinality_contract_operation_missing",
                    sorted(f"{surface}:{name}" for surface, name in operation_map),
                    f"{step.surface}:{step.operation}",
                )
            )
            continue
        for rule in operation.rules:
            checked_collections += _check_rule(step, index, rule, differences)
        if step.error_code is None:
            for rule in operation.success_rules:
                checked_collections += _check_rule(step, index, rule, differences)
    return AwsBotocoreCardinalityResult(
        admitted=not differences,
        checked_steps=len(steps),
        checked_collections=checked_collections,
        differences=tuple(differences),
    )


def without_cardinality_rules(
    contract: AwsBotocoreCardinalityContract,
) -> AwsBotocoreCardinalityContract:
    """Explicit rejected-alternative helper used to falsify receipt weakening."""
    return replace(
        contract,
        operations=tuple(
            replace(operation, rules=(), success_rules=()) for operation in contract.operations
        ),
    )
