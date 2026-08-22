from __future__ import annotations

import json

import pytest

from gymact.gyms.aws_botocore_cardinality_contract import (
    AwsBotocoreCardinalityContractCompilationError,
    compile_aws_botocore_cardinality_contract,
    receipt_aws_botocore_cardinality_contract,
    replay_aws_botocore_cardinality_contract,
    validate_aws_botocore_cardinality,
    without_cardinality_rules,
)
from gymact.gyms.cloud_fidelity import CloudTraceStep


SOURCE_URI = "botocore://s3/2006-03-01/service-2.json"


def _model() -> dict:
    return {
        "metadata": {"endpointPrefix": "s3", "apiVersion": "2006-03-01"},
        "operations": {
            "PutBatch": {
                "input": {"shape": "BatchInput"},
                "output": {"shape": "BatchOutput"},
            }
        },
        "shapes": {
            "BatchInput": {
                "type": "structure",
                "members": {"Groups": {"shape": "GroupList"}},
            },
            "GroupList": {"type": "list", "min": 1, "max": 2, "member": {"shape": "Group"}},
            "Group": {
                "type": "structure",
                "members": {"Tags": {"shape": "TagMap"}},
            },
            "TagMap": {"type": "map", "min": 1, "max": 2, "value": {"shape": "TagList"}},
            "TagList": {"type": "list", "min": 1, "max": 2, "member": {"shape": "Tag"}},
            "Tag": {
                "type": "structure",
                "members": {"Value": {"shape": "String"}},
            },
            "BatchOutput": {
                "type": "structure",
                "members": {"Results": {"shape": "ResultList"}},
            },
            "ResultList": {"type": "list", "min": 1, "max": 1, "member": {"shape": "Result"}},
            "Result": {
                "type": "structure",
                "members": {"Id": {"shape": "String"}},
            },
            "String": {"type": "string"},
        },
    }


def _compile(model: dict | None = None):
    payload = json.dumps(model or _model(), sort_keys=True).encode()
    return compile_aws_botocore_cardinality_contract(payload, source_uri=SOURCE_URI)


def _step(
    *,
    request: dict | None = None,
    response: dict | None = None,
    error_code: str | None = None,
) -> CloudTraceStep:
    return CloudTraceStep(
        surface="boto3",
        operation="s3.put_batch",
        request=request
        or {"Groups": [{"Tags": {"alpha": [{"Value": "ok"}]}}]},
        response=response if response is not None else {"Results": [{"Id": "r-1"}]},
        status_code=400 if error_code else 200,
        error_code=error_code,
    )


def test_manufactures_outer_and_nested_cardinality_and_admits_valid_trace() -> None:
    contract = _compile()
    operation = contract.operations[0]

    assert len(operation.rules) == 3
    assert len(operation.success_rules) == 1
    assert replay_aws_botocore_cardinality_contract(
        contract, receipt_aws_botocore_cardinality_contract(contract)
    )

    result = validate_aws_botocore_cardinality(contract, [_step()])
    assert result.admitted
    assert result.checked_steps == 1
    assert result.checked_collections == 4


def test_nested_collection_below_min_refuses_at_concrete_map_key_path() -> None:
    contract = _compile()
    step = _step(request={"Groups": [{"Tags": {"alpha": []}}]})

    result = validate_aws_botocore_cardinality(contract, [step])

    assert not result.admitted
    assert any(
        difference.reason == "collection_cardinality_below_min"
        and difference.path == ("request", "Groups", 0, "Tags", "alpha")
        and difference.reference == 1
        and difference.twin == 0
        for difference in result.differences
    )


def test_outer_collection_above_max_refuses() -> None:
    contract = _compile()
    group = {"Tags": {"alpha": [{"Value": "ok"}]}}
    result = validate_aws_botocore_cardinality(
        contract,
        [_step(request={"Groups": [group, group, group]})],
    )

    assert not result.admitted
    assert any(
        difference.reason == "collection_cardinality_above_max"
        and difference.path == ("request", "Groups")
        and difference.reference == 2
        and difference.twin == 3
        for difference in result.differences
    )


def test_success_response_cardinality_applies_only_to_success() -> None:
    contract = _compile()
    too_many = {"Results": [{"Id": "r-1"}, {"Id": "r-2"}]}

    success = validate_aws_botocore_cardinality(contract, [_step(response=too_many)])
    provider_error = validate_aws_botocore_cardinality(
        contract,
        [_step(response=too_many, error_code="InvalidRequest")],
    )

    assert not success.admitted
    assert any(
        difference.reason == "collection_cardinality_above_max"
        and difference.path == ("response", "Results")
        for difference in success.differences
    )
    assert provider_error.admitted


def test_wrong_nested_container_type_fails_closed() -> None:
    contract = _compile()
    step = _step(request={"Groups": [{"Tags": {"alpha": "not-a-list"}}]})

    result = validate_aws_botocore_cardinality(contract, [step])

    assert not result.admitted
    assert any(
        difference.reason == "collection_cardinality_type_mismatch"
        and difference.path == ("request", "Groups", 0, "Tags", "alpha")
        and difference.reference == "list"
        for difference in result.differences
    )


@pytest.mark.parametrize("minimum,maximum", [(True, 2), (-1, 2), (3, 2)])
def test_malformed_provider_bounds_refuse_manufacture(minimum: object, maximum: object) -> None:
    model = _model()
    model["shapes"]["GroupList"]["min"] = minimum
    model["shapes"]["GroupList"]["max"] = maximum

    with pytest.raises(AwsBotocoreCardinalityContractCompilationError):
        _compile(model)


def test_cardinality_law_is_receipt_load_bearing() -> None:
    contract = _compile()
    receipt = receipt_aws_botocore_cardinality_contract(contract)

    weakened = without_cardinality_rules(contract)

    assert not replay_aws_botocore_cardinality_contract(weakened, receipt)


def test_unmanufactured_operation_refuses_instead_of_skipping() -> None:
    contract = _compile()
    unknown = CloudTraceStep(
        surface="boto3",
        operation="s3.unknown_operation",
        request={},
        response={},
        status_code=200,
    )

    result = validate_aws_botocore_cardinality(contract, [unknown])

    assert not result.admitted
    assert result.differences[0].reason == "cardinality_contract_operation_missing"
