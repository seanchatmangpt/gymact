import json
from dataclasses import replace

import pytest

from gymact.gyms.aws_botocore_collection_contract import (
    AwsBotocoreCollectionContractCompilationError,
    compile_aws_botocore_collection_contract,
    receipt_aws_botocore_collection_contract,
    replay_aws_botocore_collection_contract,
    validate_aws_botocore_collection_contract,
    without_collection_rules,
)
from gymact.gyms.cloud_fidelity import CloudTraceStep

SOURCE_URI = "urn:aws:botocore:collections:service-2"


def _service_model() -> bytes:
    model = {
        "metadata": {"endpointPrefix": "collections", "apiVersion": "2026-08-22"},
        "operations": {
            "PutBatch": {
                "http": {"responseCode": 200},
                "input": {"shape": "PutBatchRequest"},
                "output": {"shape": "PutBatchOutput"},
            }
        },
        "shapes": {
            "PutBatchRequest": {
                "type": "structure",
                "members": {
                    "Envelope": {"shape": "Envelope"},
                    "Tags": {"shape": "TagMap"},
                },
            },
            "Envelope": {
                "type": "structure",
                "members": {"Items": {"shape": "ItemList"}},
            },
            "ItemList": {"type": "list", "member": {"shape": "Item"}},
            "Item": {
                "type": "structure",
                "required": ["Id", "Spec"],
                "members": {
                    "Id": {"shape": "String"},
                    "Spec": {"shape": "Spec"},
                },
            },
            "Spec": {
                "type": "structure",
                "required": ["Region"],
                "members": {"Region": {"shape": "String"}},
            },
            "TagMap": {
                "type": "map",
                "key": {"shape": "String"},
                "value": {"shape": "Tag"},
            },
            "Tag": {
                "type": "structure",
                "required": ["Value"],
                "members": {"Value": {"shape": "String"}},
            },
            "PutBatchOutput": {
                "type": "structure",
                "members": {"Results": {"shape": "ResultList"}},
            },
            "ResultList": {"type": "list", "member": {"shape": "Result"}},
            "Result": {
                "type": "structure",
                "required": ["Id"],
                "members": {"Id": {"shape": "String"}},
            },
            "String": {"type": "string"},
        },
    }
    return json.dumps(model, separators=(",", ":")).encode()


def _compile(source: bytes | None = None):
    return compile_aws_botocore_collection_contract(
        _service_model() if source is None else source,
        source_uri=SOURCE_URI,
    )


def _step(*, request=None, response=None, error_code=None):
    return CloudTraceStep(
        surface="boto3",
        operation="collections.put_batch",
        request={} if request is None else request,
        response={} if response is None else response,
        status_code=200 if error_code is None else 500,
        error_code=error_code,
    )


def test_manufactures_list_map_and_success_rules_deterministically() -> None:
    first = _compile()
    second = _compile()
    operation = first.operations[0]

    assert first == second
    assert {
        (rule.container_path, rule.container_kind): frozenset(rule.required_relative_paths)
        for rule in operation.rules
    } == {
        (("request", "Envelope", "Items"), "list"): frozenset(
            {("Id",), ("Spec",), ("Spec", "Region")}
        ),
        (("request", "Tags"), "map"): frozenset({("Value",)}),
    }
    assert {
        (rule.container_path, rule.container_kind): frozenset(rule.required_relative_paths)
        for rule in operation.success_rules
    } == {
        (("response", "Results"), "list"): frozenset({("Id",)})
    }


def test_absent_optional_collections_do_not_activate_rules() -> None:
    result = validate_aws_botocore_collection_contract((_step(),), _compile())

    assert result.admitted is True
    assert result.checked_collection_members == 0


def test_every_list_element_must_satisfy_required_structure_paths() -> None:
    step = _step(
        request={
            "Envelope": {
                "Items": [
                    {"Id": "a", "Spec": {"Region": "us-east-1"}},
                    {"Id": "b", "Spec": {}},
                ]
            }
        }
    )
    result = validate_aws_botocore_collection_contract((step,), _compile())

    assert result.admitted is False
    assert result.checked_collection_members == 2
    assert [(diff.reason, diff.path) for diff in result.differences] == [
        (
            "trace_collection_missing_required_element_path",
            ("request", "Envelope", "Items", 1, "Spec", "Region"),
        )
    ]


def test_every_map_value_must_satisfy_required_structure_paths() -> None:
    step = _step(request={"Tags": {"alpha": {"Value": "1"}, "beta": {}}})
    result = validate_aws_botocore_collection_contract((step,), _compile())

    assert result.admitted is False
    assert result.checked_collection_members == 2
    assert [(diff.reason, diff.path) for diff in result.differences] == [
        (
            "trace_collection_missing_required_element_path",
            ("request", "Tags", "beta", "Value"),
        )
    ]


def test_wrong_container_type_is_refused() -> None:
    result = validate_aws_botocore_collection_contract(
        (_step(request={"Envelope": {"Items": {"not": "a-list"}}}),), _compile()
    )

    assert result.admitted is False
    assert result.differences[0].reason == "trace_collection_type_mismatch"
    assert result.differences[0].path == ("request", "Envelope", "Items")


def test_non_object_element_cannot_satisfy_structure_requirement() -> None:
    result = validate_aws_botocore_collection_contract(
        (_step(request={"Envelope": {"Items": ["not-an-object"]}}),), _compile()
    )

    assert result.admitted is False
    assert result.checked_collection_members == 1
    assert result.differences[0].path == ("request", "Envelope", "Items", 0, "Id")


def test_success_collection_rules_do_not_leak_into_error_outcomes() -> None:
    success = validate_aws_botocore_collection_contract(
        (_step(response={"Results": [{}]}),), _compile()
    )
    error = validate_aws_botocore_collection_contract(
        (_step(response={"Results": [{}]}, error_code="InternalError"),), _compile()
    )

    assert success.admitted is False
    assert success.differences[0].path == ("response", "Results", 0, "Id")
    assert error.admitted is True


def test_receipt_replay_falsifies_rejected_no_collection_alternative() -> None:
    contract = _compile()
    receipt = receipt_aws_botocore_collection_contract(contract)

    assert replay_aws_botocore_collection_contract(contract, receipt) is True
    assert replay_aws_botocore_collection_contract(
        without_collection_rules(contract), receipt
    ) is False


def test_rule_change_invalidates_receipt_even_when_source_identity_is_unchanged() -> None:
    contract = _compile()
    receipt = receipt_aws_botocore_collection_contract(contract)
    operation = contract.operations[0]
    weakened_rule = replace(operation.rules[0], required_relative_paths=(("Id",),))
    changed = replace(
        contract,
        operations=(replace(operation, rules=(weakened_rule, *operation.rules[1:])),),
    )

    assert changed.source_digest == contract.source_digest
    assert replay_aws_botocore_collection_contract(changed, receipt) is False


def test_dangling_collection_member_shape_fails_closed() -> None:
    model = json.loads(_service_model())
    model["shapes"]["ItemList"]["member"] = {"shape": "Missing"}

    with pytest.raises(
        AwsBotocoreCollectionContractCompilationError,
        match="shapes.Missing is missing",
    ):
        _compile(json.dumps(model, separators=(",", ":")).encode())


def test_nested_collection_element_shape_is_manufactured_and_executed() -> None:
    model = json.loads(_service_model())
    model["shapes"]["ItemList"]["member"] = {"shape": "NestedList"}
    model["shapes"]["NestedList"] = {"type": "list", "member": {"shape": "Item"}}
    contract = _compile(json.dumps(model, separators=(",", ":")).encode())
    nested_rule = next(
        rule
        for rule in contract.operations[0].rules
        if rule.container_path == ("request", "Envelope", "Items")
    )

    assert [
        (step.relative_path, step.container_kind) for step in nested_rule.nested_collections
    ] == [((), "list")]

    result = validate_aws_botocore_collection_contract(
        (
            _step(
                request={
                    "Envelope": {
                        "Items": [[{"Id": "a", "Spec": {"Region": "us-east-1"}}]]
                    }
                }
            ),
        ),
        contract,
    )
    assert result.admitted is True
    # The validator counts every visited collection member: one outer member
    # (the nested list) and one inner Item member whose structure is checked.
    assert result.checked_collection_members == 2
