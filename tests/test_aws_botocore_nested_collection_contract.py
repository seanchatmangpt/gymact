import json
from dataclasses import replace

import pytest

from gymact.gyms.aws_botocore_collection_contract import (
    AwsBotocoreCollectionContractCompilationError,
    compile_aws_botocore_collection_contract,
    receipt_aws_botocore_collection_contract,
    replay_aws_botocore_collection_contract,
    validate_aws_botocore_collection_contract,
)
from gymact.gyms.cloud_fidelity import CloudTraceStep

SOURCE_URI = "urn:aws:botocore:nested-collections:service-2"


def _service_model() -> bytes:
    model = {
        "metadata": {"endpointPrefix": "nested", "apiVersion": "2026-08-22"},
        "operations": {
            "Put": {
                "input": {"shape": "PutRequest"},
                "output": {"shape": "PutOutput"},
            }
        },
        "shapes": {
            "PutRequest": {
                "type": "structure",
                "members": {"Groups": {"shape": "OuterList"}},
            },
            "OuterList": {"type": "list", "member": {"shape": "Batch"}},
            "Batch": {
                "type": "structure",
                "required": ["Name"],
                "members": {
                    "Name": {"shape": "String"},
                    "Tags": {"shape": "TagMap"},
                },
            },
            "TagMap": {
                "type": "map",
                "key": {"shape": "String"},
                "value": {"shape": "InnerList"},
            },
            "InnerList": {"type": "list", "member": {"shape": "Tag"}},
            "Tag": {
                "type": "structure",
                "required": ["Value"],
                "members": {"Value": {"shape": "String"}},
            },
            "PutOutput": {"type": "structure", "members": {}},
            "String": {"type": "string"},
        },
    }
    return json.dumps(model, separators=(",", ":")).encode()


def _compile(source: bytes | None = None):
    return compile_aws_botocore_collection_contract(
        _service_model() if source is None else source,
        source_uri=SOURCE_URI,
    )


def _step(request):
    return CloudTraceStep(
        surface="boto3",
        operation="nested.put",
        request=request,
        response={},
        status_code=200,
        error_code=None,
    )


def test_manufactures_nested_collection_chain_deterministically() -> None:
    first = _compile()
    second = _compile()
    nested = [rule for rule in first.operations[0].rules if rule.nested_collections]

    assert first == second
    assert len(nested) == 1
    rule = nested[0]
    assert rule.container_path == ("request", "Groups")
    assert [
        (step.relative_path, step.container_kind) for step in rule.nested_collections
    ] == [(('Tags',), "map"), ((), "list")]
    assert rule.required_relative_paths == (("Value",),)


def test_nested_missing_requirement_reports_concrete_index_and_key_path() -> None:
    result = validate_aws_botocore_collection_contract(
        (
            _step(
                {
                    "Groups": [
                        {
                            "Name": "batch-a",
                            "Tags": {"alpha": [{"Value": "1"}], "beta": [{}]},
                        }
                    ]
                }
            ),
        ),
        _compile(),
    )

    assert result.admitted is False
    assert result.differences[-1].path == (
        "request",
        "Groups",
        0,
        "Tags",
        "beta",
        0,
        "Value",
    )


def test_optional_nested_collection_absence_does_not_activate_rule() -> None:
    result = validate_aws_botocore_collection_contract(
        (_step({"Groups": [{"Name": "batch-a"}]}),),
        _compile(),
    )

    assert result.admitted is True


def test_wrong_nested_collection_type_fails_at_exact_container_path() -> None:
    result = validate_aws_botocore_collection_contract(
        (_step({"Groups": [{"Name": "batch-a", "Tags": []}]}),),
        _compile(),
    )

    assert result.admitted is False
    assert result.differences[-1].reason == "trace_collection_type_mismatch"
    assert result.differences[-1].path == ("request", "Groups", 0, "Tags")


def test_recursive_collection_cycle_fails_closed() -> None:
    model = json.loads(_service_model())
    model["shapes"]["OuterList"]["member"] = {"shape": "InnerList"}
    model["shapes"]["InnerList"]["member"] = {"shape": "OuterList"}

    with pytest.raises(
        AwsBotocoreCollectionContractCompilationError,
        match="recursive collection cycle",
    ):
        _compile(json.dumps(model, separators=(",", ":")).encode())


def test_nested_collection_path_is_bound_into_receipt_replay() -> None:
    contract = _compile()
    receipt = receipt_aws_botocore_collection_contract(contract)
    operation = contract.operations[0]
    nested_rule = next(rule for rule in operation.rules if rule.nested_collections)
    weakened_rule = replace(nested_rule, nested_collections=())
    changed = replace(
        contract,
        operations=(
            replace(
                operation,
                rules=tuple(
                    weakened_rule if rule == nested_rule else rule
                    for rule in operation.rules
                ),
            ),
        ),
    )

    assert replay_aws_botocore_collection_contract(contract, receipt) is True
    assert replay_aws_botocore_collection_contract(changed, receipt) is False
