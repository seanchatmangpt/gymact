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
class AwsNestedCollectionStep:
    relative_path: tuple[str, ...]
    container_kind: Literal["list", "map"]


@dataclass(frozen=True, slots=True)
class AwsCollectionElementRule:
    container_path: JsonPath
    container_kind: Literal["list", "map"]
    required_relative_paths: tuple[tuple[str, ...], ...]
    nested_collections: tuple[AwsNestedCollectionStep, ...] = ()


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
        if index and char.isupper() and (
            not value[index - 1].isupper()
            or (index + 1 < len(value) and value[index + 1].islower())
        ):
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
    if not isinstance(required_raw, list) or any(
        not isinstance(item, str) or not item for item in required_raw
    ):
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


def _collection_child(shapes: dict[str, Any], shape_name: str) -> tuple[str, str]:
    shape = _shape(shapes, shape_name)
    kind = shape["type"]
    if kind not in {"list", "map"}:
        raise AwsBotocoreCollectionContractCompilationError(
            f"shapes.{shape_name}.type must be list or map for collection traversal"
        )
    field = "member" if kind == "list" else "value"
    ref = _mapping(shape.get(field), f"shapes.{shape_name}.{field}")
    child = ref.get("shape")
    if not isinstance(child, str) or not child:
        raise AwsBotocoreCollectionContractCompilationError(
            f"shapes.{shape_name}.{field}.shape must be a non-empty string"
        )
    return child, _shape(shapes, child)["type"]


def _collection_rules(
    shapes: dict[str, Any],
    collection_shape: str,
    *,
    container_path: JsonPath,
    outer_kind: Literal["list", "map"],
    nested: tuple[AwsNestedCollectionStep, ...] = (),
    ancestry: tuple[str, ...] = (),
) -> set[AwsCollectionElementRule]:
    if collection_shape in ancestry:
        chain = " -> ".join((*ancestry, collection_shape))
        raise AwsBotocoreCollectionContractCompilationError(
            f"recursive collection cycle is unsupported: {chain}"
        )
    collection = _shape(shapes, collection_shape)
    kind = collection["type"]
    if kind not in {"list", "map"}:
        raise AwsBotocoreCollectionContractCompilationError(
            f"shapes.{collection_shape}.type must be list or map"
        )
    child, child_kind = _collection_child(shapes, collection_shape)
    next_ancestry = (*ancestry, collection_shape)
    rules: set[AwsCollectionElementRule] = set()

    if child_kind in {"list", "map"}:
        rules.update(
            _collection_rules(
                shapes,
                child,
                container_path=container_path,
                outer_kind=outer_kind,
                nested=(*nested, AwsNestedCollectionStep((), child_kind)),
                ancestry=next_ancestry,
            )
        )
        return rules

    if child_kind != "structure":
        return rules

    required_paths = _required_structure_paths(shapes, child)
    if required_paths:
        rules.add(
            AwsCollectionElementRule(
                container_path=container_path,
                container_kind=outer_kind,
                required_relative_paths=required_paths,
                nested_collections=nested,
            )
        )

    def walk_structure(
        current: str,
        prefix: tuple[str, ...],
        structure_ancestry: tuple[str, ...],
    ) -> None:
        if current in structure_ancestry:
            return
        shape = _shape(shapes, current)
        if shape["type"] != "structure":
            return
        members = _mapping(shape.get("members", {}), f"shapes.{current}.members")
        for member in sorted(members):
            member_ref = _mapping(members[member], f"shapes.{current}.members.{member}")
            member_shape = member_ref.get("shape")
            if not isinstance(member_shape, str) or not member_shape:
                raise AwsBotocoreCollectionContractCompilationError(
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
                            AwsNestedCollectionStep(member_path, member_kind),
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
                repr(rule.required_relative_paths),
            ),
        )
    )


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
        raise AwsBotocoreCollectionContractCompilationError(
            "metadata.endpointPrefix must be non-empty"
        )
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
        "nested_collections": [
            {
                "relative_path": list(step.relative_path),
                "container_kind": step.container_kind,
            }
            for step in rule.nested_collections
        ],
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
            for operation in sorted(
                contract.operations, key=lambda item: (item.surface, item.operation)
            )
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
        rule_count=sum(
            len(operation.rules) + len(operation.success_rules)
            for operation in contract.operations
        ),
    )


def replay_aws_botocore_collection_contract(
    contract: AwsBotocoreCollectionContract, receipt: AwsBotocoreCollectionReceipt
) -> bool:
    return receipt_aws_botocore_collection_contract(contract) == receipt


def _lookup_value(value: Any, path: tuple[str, ...]) -> tuple[bool, Any]:
    current = value
    for token in path:
        if not isinstance(current, dict) or token not in current:
            return False, None
        current = current[token]
    return True, current


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
    return _lookup_value(value, path)[0]


def _members(collection: Any, kind: Literal["list", "map"]):
    if kind == "list":
        return enumerate(collection)
    return ((key, collection[key]) for key in sorted(collection))


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

    checked = 0

    def walk_collection(
        current_collection: Any,
        kind: Literal["list", "map"],
        concrete_path: JsonPath,
        nested_steps: tuple[AwsNestedCollectionStep, ...],
    ) -> None:
        nonlocal checked
        expected_type = list if kind == "list" else dict
        if not isinstance(current_collection, expected_type):
            differences.append(
                FidelityDifference(
                    step_index,
                    concrete_path,
                    f"{side}_collection_type_mismatch",
                    kind,
                    type(current_collection).__name__,
                )
            )
            return
        for member_key, member_value in _members(current_collection, kind):
            checked += 1
            member_path = (*concrete_path, member_key)
            if nested_steps:
                nested_step = nested_steps[0]
                nested_found, nested_collection = _lookup_value(
                    member_value, nested_step.relative_path
                )
                if not nested_found:
                    continue
                walk_collection(
                    nested_collection,
                    nested_step.container_kind,
                    (*member_path, *nested_step.relative_path),
                    nested_steps[1:],
                )
                continue
            for relative in rule.required_relative_paths:
                concrete = (*member_path, *relative)
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

    walk_collection(collection, rule.container_kind, rule.container_path, rule.nested_collections)
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
            FidelityDifference(
                None,
                ("collection_contract",),
                f"{side}_duplicate_collection_operation",
                "unique surface+operation",
                None,
            )
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
        operations=tuple(
            replace(operation, rules=(), success_rules=()) for operation in contract.operations
        ),
    )
