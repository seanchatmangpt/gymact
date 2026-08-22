from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Any, Literal

import blake3
import rfc8785

from gymact.gyms.cloud_contract import digest_cloud_contract_source
from gymact.gyms.cloud_fidelity import CloudTraceStep, FidelityDifference, JsonPath


class AwsBotocoreScalarContractCompilationError(ValueError):
    """Fail closed when provider-published scalar constraint law is malformed."""


ScalarKind = Literal["string", "integer", "long", "float", "double"]
CollectionKind = Literal["list", "map"]


@dataclass(frozen=True, slots=True)
class AwsScalarTraversalStep:
    relative_path: tuple[str, ...]
    container_kind: CollectionKind


@dataclass(frozen=True, slots=True)
class AwsScalarConstraintRule:
    value_path: JsonPath
    scalar_kind: ScalarKind
    min_value: int | float | None = None
    max_value: int | float | None = None
    min_length: int | None = None
    max_length: int | None = None
    enum_values: tuple[str, ...] = ()
    outer_collection_kind: CollectionKind | None = None
    nested_collections: tuple[AwsScalarTraversalStep, ...] = ()
    scalar_relative_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AwsOperationScalarContract:
    surface: str
    operation: str
    rules: tuple[AwsScalarConstraintRule, ...] = ()
    success_rules: tuple[AwsScalarConstraintRule, ...] = ()


@dataclass(frozen=True, slots=True)
class AwsBotocoreScalarContract:
    name: str
    source_uri: str
    source_digest: str
    operations: tuple[AwsOperationScalarContract, ...]


@dataclass(frozen=True, slots=True)
class AwsBotocoreScalarReceipt:
    digest: str
    source_digest: str
    operation_count: int
    rule_count: int


@dataclass(frozen=True, slots=True)
class AwsBotocoreScalarResult:
    admitted: bool
    checked_steps: int
    checked_values: int
    differences: tuple[FidelityDifference, ...]


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AwsBotocoreScalarContractCompilationError(f"{field} must be an object")
    return value


def _shape(shapes: dict[str, Any], name: str) -> dict[str, Any]:
    value = shapes.get(name)
    if value is None:
        raise AwsBotocoreScalarContractCompilationError(f"shapes.{name} is missing")
    shape = _mapping(value, f"shapes.{name}")
    kind = shape.get("type")
    if not isinstance(kind, str) or not kind:
        raise AwsBotocoreScalarContractCompilationError(
            f"shapes.{name}.type must be a non-empty string"
        )
    return shape


def _pascal_to_snake(value: str) -> str:
    output: list[str] = []
    for index, char in enumerate(value):
        if index and char.isupper() and (
            not value[index - 1].isupper()
            or (index + 1 < len(value) and value[index + 1].islower())
        ):
            output.append("_")
        output.append(char.lower())
    return "".join(output)


def _non_negative_int(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AwsBotocoreScalarContractCompilationError(
            f"{field} must be a non-negative integer"
        )
    return value


def _number(value: Any, field: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AwsBotocoreScalarContractCompilationError(f"{field} must be numeric")
    return value


def _scalar_constraints(
    shape: dict[str, Any], shape_name: str
) -> tuple[ScalarKind, dict[str, Any]] | None:
    kind = shape["type"]
    if kind == "string":
        minimum = _non_negative_int(shape.get("min"), f"shapes.{shape_name}.min")
        maximum = _non_negative_int(shape.get("max"), f"shapes.{shape_name}.max")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise AwsBotocoreScalarContractCompilationError(
                f"shapes.{shape_name}.min must be <= max"
            )
        raw_enum = shape.get("enum", [])
        if not isinstance(raw_enum, list) or any(
            not isinstance(item, str) for item in raw_enum
        ):
            raise AwsBotocoreScalarContractCompilationError(
                f"shapes.{shape_name}.enum must be an array of strings"
            )
        enum_values = tuple(sorted(set(raw_enum)))
        if minimum is None and maximum is None and not enum_values:
            return None
        return "string", {
            "min_length": minimum,
            "max_length": maximum,
            "enum_values": enum_values,
        }
    if kind in {"integer", "long", "float", "double"}:
        minimum = _number(shape.get("min"), f"shapes.{shape_name}.min")
        maximum = _number(shape.get("max"), f"shapes.{shape_name}.max")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise AwsBotocoreScalarContractCompilationError(
                f"shapes.{shape_name}.min must be <= max"
            )
        if minimum is None and maximum is None:
            return None
        return kind, {"min_value": minimum, "max_value": maximum}
    return None


def _collection_child(shapes: dict[str, Any], shape_name: str) -> tuple[str, str]:
    shape = _shape(shapes, shape_name)
    kind = shape["type"]
    if kind not in {"list", "map"}:
        raise AwsBotocoreScalarContractCompilationError(
            f"shapes.{shape_name}.type must be list or map"
        )
    field = "member" if kind == "list" else "value"
    ref = _mapping(shape.get(field), f"shapes.{shape_name}.{field}")
    child = ref.get("shape")
    if not isinstance(child, str) or not child:
        raise AwsBotocoreScalarContractCompilationError(
            f"shapes.{shape_name}.{field}.shape must be a non-empty string"
        )
    return child, _shape(shapes, child)["type"]


def _make_rule(
    *,
    value_path: JsonPath,
    shape: dict[str, Any],
    shape_name: str,
    outer_collection_kind: CollectionKind | None = None,
    nested_collections: tuple[AwsScalarTraversalStep, ...] = (),
    scalar_relative_path: tuple[str, ...] = (),
) -> AwsScalarConstraintRule | None:
    constraints = _scalar_constraints(shape, shape_name)
    if constraints is None:
        return None
    kind, values = constraints
    return AwsScalarConstraintRule(
        value_path=value_path,
        scalar_kind=kind,
        outer_collection_kind=outer_collection_kind,
        nested_collections=nested_collections,
        scalar_relative_path=scalar_relative_path,
        **values,
    )


def _rules_for_root(
    shapes: dict[str, Any], shape_ref: Any, operation: str, *, field: str, root: str
) -> tuple[AwsScalarConstraintRule, ...]:
    if shape_ref is None:
        return ()
    ref = _mapping(shape_ref, f"operations.{operation}.{field}")
    root_shape = ref.get("shape")
    if not isinstance(root_shape, str) or not root_shape:
        raise AwsBotocoreScalarContractCompilationError(
            f"operations.{operation}.{field}.shape must be a non-empty string"
        )
    if _shape(shapes, root_shape)["type"] != "structure":
        raise AwsBotocoreScalarContractCompilationError(
            f"shapes.{root_shape}.type must be 'structure' for operation input/output"
        )

    rules: set[AwsScalarConstraintRule] = set()

    def walk_collection(
        collection_shape: str,
        *,
        container_path: JsonPath,
        outer_kind: CollectionKind,
        nested: tuple[AwsScalarTraversalStep, ...],
        ancestry: tuple[str, ...],
    ) -> None:
        if collection_shape in ancestry:
            chain = " -> ".join((*ancestry, collection_shape))
            raise AwsBotocoreScalarContractCompilationError(
                f"recursive collection cycle is unsupported: {chain}"
            )
        child, child_kind = _collection_child(shapes, collection_shape)
        next_ancestry = (*ancestry, collection_shape)
        child_shape = _shape(shapes, child)
        direct = _make_rule(
            value_path=container_path,
            shape=child_shape,
            shape_name=child,
            outer_collection_kind=outer_kind,
            nested_collections=nested,
        )
        if direct is not None:
            rules.add(direct)
            return
        if child_kind in {"list", "map"}:
            walk_collection(
                child,
                container_path=container_path,
                outer_kind=outer_kind,
                nested=(*nested, AwsScalarTraversalStep((), child_kind)),
                ancestry=next_ancestry,
            )
            return
        if child_kind != "structure":
            return

        def walk_structure(
            current: str,
            prefix: tuple[str, ...],
            structure_ancestry: tuple[str, ...],
        ) -> None:
            if current in structure_ancestry:
                return
            current_shape = _shape(shapes, current)
            members = _mapping(
                current_shape.get("members", {}), f"shapes.{current}.members"
            )
            for member in sorted(members):
                member_ref = _mapping(
                    members[member], f"shapes.{current}.members.{member}"
                )
                member_shape_name = member_ref.get("shape")
                if not isinstance(member_shape_name, str) or not member_shape_name:
                    raise AwsBotocoreScalarContractCompilationError(
                        f"shapes.{current}.members.{member}.shape must be non-empty"
                    )
                member_shape = _shape(shapes, member_shape_name)
                member_path = (*prefix, member)
                scalar_rule = _make_rule(
                    value_path=container_path,
                    shape=member_shape,
                    shape_name=member_shape_name,
                    outer_collection_kind=outer_kind,
                    nested_collections=nested,
                    scalar_relative_path=member_path,
                )
                if scalar_rule is not None:
                    rules.add(scalar_rule)
                elif member_shape["type"] in {"list", "map"}:
                    walk_collection(
                        member_shape_name,
                        container_path=container_path,
                        outer_kind=outer_kind,
                        nested=(
                            *nested,
                            AwsScalarTraversalStep(member_path, member_shape["type"]),
                        ),
                        ancestry=next_ancestry,
                    )
                elif member_shape["type"] == "structure":
                    walk_structure(
                        member_shape_name,
                        member_path,
                        (*structure_ancestry, current),
                    )

        walk_structure(child, (), ())

    def walk_structure(
        current: str, prefix: tuple[str, ...], ancestry: tuple[str, ...]
    ) -> None:
        if current in ancestry:
            return
        current_shape = _shape(shapes, current)
        members = _mapping(
            current_shape.get("members", {}), f"shapes.{current}.members"
        )
        for member in sorted(members):
            member_ref = _mapping(
                members[member], f"shapes.{current}.members.{member}"
            )
            child = member_ref.get("shape")
            if not isinstance(child, str) or not child:
                raise AwsBotocoreScalarContractCompilationError(
                    f"shapes.{current}.members.{member}.shape must be non-empty"
                )
            child_shape = _shape(shapes, child)
            path = (root, *prefix, member)
            scalar_rule = _make_rule(
                value_path=path, shape=child_shape, shape_name=child
            )
            if scalar_rule is not None:
                rules.add(scalar_rule)
            elif child_shape["type"] in {"list", "map"}:
                walk_collection(
                    child,
                    container_path=path,
                    outer_kind=child_shape["type"],
                    nested=(),
                    ancestry=(),
                )
            elif child_shape["type"] == "structure":
                walk_structure(child, (*prefix, member), (*ancestry, current))

    walk_structure(root_shape, (), ())
    return tuple(sorted(rules, key=repr))


def compile_aws_botocore_scalar_contract(
    source_document: bytes, *, source_uri: str
) -> AwsBotocoreScalarContract:
    if not isinstance(source_document, bytes):
        raise TypeError("source_document must be bytes")
    if not isinstance(source_uri, str) or not source_uri.strip():
        raise AwsBotocoreScalarContractCompilationError("source_uri must be non-empty")
    try:
        model = json.loads(source_document)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AwsBotocoreScalarContractCompilationError(
            "source_document must be valid UTF-8 JSON"
        ) from exc
    model = _mapping(model, "service_model")
    metadata = _mapping(model.get("metadata"), "metadata")
    service = metadata.get("endpointPrefix")
    api_version = metadata.get("apiVersion")
    if not isinstance(service, str) or not service:
        raise AwsBotocoreScalarContractCompilationError(
            "metadata.endpointPrefix must be non-empty"
        )
    if not isinstance(api_version, str) or not api_version:
        raise AwsBotocoreScalarContractCompilationError(
            "metadata.apiVersion must be non-empty"
        )
    operations = _mapping(model.get("operations"), "operations")
    shapes = _mapping(model.get("shapes"), "shapes")
    if not operations:
        raise AwsBotocoreScalarContractCompilationError("operations must not be empty")

    compiled: list[AwsOperationScalarContract] = []
    for operation_name in sorted(operations):
        operation = _mapping(
            operations[operation_name], f"operations.{operation_name}"
        )
        compiled.append(
            AwsOperationScalarContract(
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
    return AwsBotocoreScalarContract(
        name=f"aws-botocore-scalar:{service}:{api_version}",
        source_uri=source_uri.strip(),
        source_digest=digest_cloud_contract_source(source_document),
        operations=tuple(compiled),
    )


def _rule_payload(rule: AwsScalarConstraintRule) -> dict[str, Any]:
    return {
        "value_path": list(rule.value_path),
        "scalar_kind": rule.scalar_kind,
        "min_value": rule.min_value,
        "max_value": rule.max_value,
        "min_length": rule.min_length,
        "max_length": rule.max_length,
        "enum_values": list(rule.enum_values),
        "outer_collection_kind": rule.outer_collection_kind,
        "nested_collections": [
            {
                "relative_path": list(step.relative_path),
                "container_kind": step.container_kind,
            }
            for step in rule.nested_collections
        ],
        "scalar_relative_path": list(rule.scalar_relative_path),
    }


def _contract_payload(contract: AwsBotocoreScalarContract) -> dict[str, Any]:
    return {
        "name": contract.name,
        "source_uri": contract.source_uri,
        "source_digest": contract.source_digest,
        "operations": [
            {
                "surface": operation.surface,
                "operation": operation.operation,
                "rules": [_rule_payload(rule) for rule in operation.rules],
                "success_rules": [
                    _rule_payload(rule) for rule in operation.success_rules
                ],
            }
            for operation in sorted(
                contract.operations, key=lambda item: (item.surface, item.operation)
            )
        ],
    }


def receipt_aws_botocore_scalar_contract(
    contract: AwsBotocoreScalarContract,
) -> AwsBotocoreScalarReceipt:
    canonical = rfc8785.dumps(_contract_payload(contract))
    return AwsBotocoreScalarReceipt(
        digest=blake3.blake3(canonical).hexdigest(),
        source_digest=contract.source_digest,
        operation_count=len(contract.operations),
        rule_count=sum(
            len(operation.rules) + len(operation.success_rules)
            for operation in contract.operations
        ),
    )


def replay_aws_botocore_scalar_contract(
    contract: AwsBotocoreScalarContract,
    receipt: AwsBotocoreScalarReceipt,
) -> bool:
    return receipt_aws_botocore_scalar_contract(contract) == receipt


def _lookup(value: Any, path: Iterable[str | int]) -> tuple[bool, Any]:
    current = value
    for token in path:
        if isinstance(token, int):
            if not isinstance(current, list) or token < 0 or token >= len(current):
                return False, None
            current = current[token]
        else:
            if not isinstance(current, dict) or token not in current:
                return False, None
            current = current[token]
    return True, current


def _members(value: Any, kind: CollectionKind) -> tuple[tuple[str | int, Any], ...]:
    if kind == "list":
        if not isinstance(value, list):
            return ()
        return tuple(enumerate(value))
    if not isinstance(value, dict):
        return ()
    return tuple((key, value[key]) for key in sorted(value))


def _validate_scalar(
    value: Any,
    rule: AwsScalarConstraintRule,
    *,
    step_index: int,
    path: JsonPath,
    differences: list[FidelityDifference],
) -> None:
    if rule.scalar_kind == "string":
        if not isinstance(value, str):
            differences.append(
                FidelityDifference(
                    step_index,
                    path,
                    "trace_scalar_type_mismatch",
                    "string",
                    type(value).__name__,
                )
            )
            return
        if rule.min_length is not None and len(value) < rule.min_length:
            differences.append(
                FidelityDifference(
                    step_index,
                    path,
                    "trace_scalar_below_min_length",
                    rule.min_length,
                    len(value),
                )
            )
        if rule.max_length is not None and len(value) > rule.max_length:
            differences.append(
                FidelityDifference(
                    step_index,
                    path,
                    "trace_scalar_above_max_length",
                    rule.max_length,
                    len(value),
                )
            )
        if rule.enum_values and value not in rule.enum_values:
            differences.append(
                FidelityDifference(
                    step_index,
                    path,
                    "trace_scalar_enum_mismatch",
                    rule.enum_values,
                    value,
                )
            )
        return

    numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
    if rule.scalar_kind in {"integer", "long"}:
        numeric = isinstance(value, int) and not isinstance(value, bool)
    if not numeric:
        differences.append(
            FidelityDifference(
                step_index,
                path,
                "trace_scalar_type_mismatch",
                rule.scalar_kind,
                type(value).__name__,
            )
        )
        return
    if rule.min_value is not None and value < rule.min_value:
        differences.append(
            FidelityDifference(
                step_index,
                path,
                "trace_scalar_below_min",
                rule.min_value,
                value,
            )
        )
    if rule.max_value is not None and value > rule.max_value:
        differences.append(
            FidelityDifference(
                step_index,
                path,
                "trace_scalar_above_max",
                rule.max_value,
                value,
            )
        )


def _validate_rule(
    step: CloudTraceStep,
    rule: AwsScalarConstraintRule,
    *,
    step_index: int,
    differences: list[FidelityDifference],
) -> int:
    root = {"request": step.request, "response": step.response}
    exists, value = _lookup(root, rule.value_path)
    if not exists:
        return 0
    if rule.outer_collection_kind is None:
        _validate_scalar(
            value,
            rule,
            step_index=step_index,
            path=rule.value_path,
            differences=differences,
        )
        return 1

    expected_type = list if rule.outer_collection_kind == "list" else dict
    if not isinstance(value, expected_type):
        differences.append(
            FidelityDifference(
                step_index,
                rule.value_path,
                "trace_scalar_container_type_mismatch",
                rule.outer_collection_kind,
                type(value).__name__,
            )
        )
        return 0

    frontier: tuple[tuple[JsonPath, Any], ...] = tuple(
        ((*rule.value_path, token), member)
        for token, member in _members(value, rule.outer_collection_kind)
    )
    for traversal in rule.nested_collections:
        next_frontier: list[tuple[JsonPath, Any]] = []
        for member_path, member in frontier:
            found, nested = _lookup(member, traversal.relative_path)
            if not found:
                continue
            nested_path = (*member_path, *traversal.relative_path)
            expected_nested = list if traversal.container_kind == "list" else dict
            if not isinstance(nested, expected_nested):
                differences.append(
                    FidelityDifference(
                        step_index,
                        nested_path,
                        "trace_scalar_container_type_mismatch",
                        traversal.container_kind,
                        type(nested).__name__,
                    )
                )
                continue
            next_frontier.extend(
                ((*nested_path, token), child)
                for token, child in _members(nested, traversal.container_kind)
            )
        frontier = tuple(next_frontier)

    checked = 0
    for member_path, member in frontier:
        found, scalar = _lookup(member, rule.scalar_relative_path)
        if not found:
            continue
        scalar_path = (*member_path, *rule.scalar_relative_path)
        _validate_scalar(
            scalar,
            rule,
            step_index=step_index,
            path=scalar_path,
            differences=differences,
        )
        checked += 1
    return checked


def validate_aws_botocore_scalar_trace(
    contract: AwsBotocoreScalarContract,
    trace: Iterable[CloudTraceStep],
) -> AwsBotocoreScalarResult:
    operation_map = {(item.surface, item.operation): item for item in contract.operations}
    differences: list[FidelityDifference] = []
    checked_values = 0
    steps = tuple(trace)
    for index, step in enumerate(steps):
        operation = operation_map.get((step.surface, step.operation))
        if operation is None:
            differences.append(
                FidelityDifference(
                    index,
                    ("operation",),
                    "trace_scalar_operation_not_admitted",
                    sorted(f"{surface}:{name}" for surface, name in operation_map),
                    f"{step.surface}:{step.operation}",
                )
            )
            continue
        for rule in operation.rules:
            checked_values += _validate_rule(
                step, rule, step_index=index, differences=differences
            )
        if step.error_code is None:
            for rule in operation.success_rules:
                checked_values += _validate_rule(
                    step, rule, step_index=index, differences=differences
                )
    return AwsBotocoreScalarResult(
        admitted=not differences,
        checked_steps=len(steps),
        checked_values=checked_values,
        differences=tuple(differences),
    )


def without_scalar_rules(contract: AwsBotocoreScalarContract) -> AwsBotocoreScalarContract:
    return replace(
        contract,
        operations=tuple(
            replace(operation, rules=(), success_rules=())
            for operation in contract.operations
        ),
    )
