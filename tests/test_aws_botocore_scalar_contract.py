from __future__ import annotations

import json
from dataclasses import replace

import pytest
from gymact.gyms.aws_botocore_scalar_contract import (
    AwsBotocoreScalarContractCompilationError,
    compile_aws_botocore_scalar_contract,
    receipt_aws_botocore_scalar_contract,
    replay_aws_botocore_scalar_contract,
    validate_aws_botocore_scalar_trace,
    without_scalar_rules,
)
from gymact.gyms.cloud_fidelity import CloudTraceStep


SOURCE_URI = "botocore://s3/2006-03-01/service-2.json"


def _source(*, string_min: object = 3, count_max: object = 10) -> bytes:
    model = {
        "metadata": {"endpointPrefix": "s3", "apiVersion": "2006-03-01"},
        "operations": {
            "PutWidget": {
                "input": {"shape": "PutWidgetInput"},
                "output": {"shape": "PutWidgetOutput"},
            }
        },
        "shapes": {
            "PutWidgetInput": {
                "type": "structure",
                "members": {
                    "Name": {"shape": "WidgetName"},
                    "Count": {"shape": "WidgetCount"},
                    "Tags": {"shape": "TagList"},
                    "Matrix": {"shape": "MatrixOuter"},
                },
            },
            "PutWidgetOutput": {
                "type": "structure",
                "members": {"Token": {"shape": "Token"}},
            },
            "WidgetName": {
                "type": "string",
                "min": string_min,
                "max": 8,
                "enum": ["beta", "alpha", "alpha"],
                "pattern": "^[a-z]+$",
            },
            "WidgetCount": {"type": "integer", "min": 1, "max": count_max},
            "TagList": {"type": "list", "member": {"shape": "Tag"}},
            "Tag": {
                "type": "structure",
                "members": {"Value": {"shape": "TagValue"}},
            },
            "TagValue": {"type": "string", "min": 2, "max": 4},
            "MatrixOuter": {"type": "list", "member": {"shape": "MatrixInner"}},
            "MatrixInner": {"type": "list", "member": {"shape": "MatrixValue"}},
            "MatrixValue": {"type": "integer", "min": 0, "max": 5},
            "Token": {"type": "string", "min": 4, "max": 12},
        },
    }
    return json.dumps(model, sort_keys=True).encode()


def _step(
    *,
    name: str = "alpha",
    count: int = 5,
    tags: list[dict[str, str]] | None = None,
    matrix: list[list[int]] | None = None,
    token: str = "abcd",
    error_code: str | None = None,
) -> CloudTraceStep:
    return CloudTraceStep(
        surface="boto3",
        operation="s3.put_widget",
        request={
            "Name": name,
            "Count": count,
            "Tags": tags if tags is not None else [{"Value": "ok"}],
            "Matrix": matrix if matrix is not None else [[0, 5], [2]],
        },
        response={"Token": token},
        status_code=200 if error_code is None else 400,
        error_code=error_code,
    )


def test_manufactures_and_admits_scalar_constraints_across_nested_collections() -> None:
    contract = compile_aws_botocore_scalar_contract(_source(), source_uri=SOURCE_URI)

    result = validate_aws_botocore_scalar_trace(contract, [_step()])

    assert result.admitted
    assert result.checked_steps == 1
    assert result.checked_values == 7
    operation = contract.operations[0]
    assert operation.operation == "s3.put_widget"
    assert any(rule.enum_values == ("alpha", "beta") for rule in operation.rules)


def test_string_length_and_enum_fail_at_exact_public_path() -> None:
    contract = compile_aws_botocore_scalar_contract(_source(), source_uri=SOURCE_URI)

    result = validate_aws_botocore_scalar_trace(contract, [_step(name="zz")])

    assert not result.admitted
    assert {(item.path, item.reason) for item in result.differences} == {
        (("request", "Name"), "trace_scalar_below_min_length"),
        (("request", "Name"), "trace_scalar_enum_mismatch"),
    }


def test_numeric_bound_failure_is_not_hidden_by_valid_type() -> None:
    contract = compile_aws_botocore_scalar_contract(_source(), source_uri=SOURCE_URI)

    result = validate_aws_botocore_scalar_trace(contract, [_step(count=11)])

    assert not result.admitted
    assert result.differences[0].path == ("request", "Count")
    assert result.differences[0].reason == "trace_scalar_above_max"


def test_nested_collection_scalar_failure_preserves_index_path() -> None:
    contract = compile_aws_botocore_scalar_contract(_source(), source_uri=SOURCE_URI)

    result = validate_aws_botocore_scalar_trace(
        contract,
        [_step(tags=[{"Value": "x"}], matrix=[[0], [7]])],
    )

    observed = {(item.path, item.reason) for item in result.differences}
    assert (("request", "Tags", 0, "Value"), "trace_scalar_below_min_length") in observed
    assert (("request", "Matrix", 1, 0), "trace_scalar_above_max") in observed


def test_wrong_nested_container_type_fails_closed() -> None:
    contract = compile_aws_botocore_scalar_contract(_source(), source_uri=SOURCE_URI)
    step = _step()
    step = replace(step, request={**step.request, "Matrix": ["not-a-list"]})

    result = validate_aws_botocore_scalar_trace(contract, [step])

    assert not result.admitted
    assert any(
        item.path == ("request", "Matrix", 0)
        and item.reason == "trace_scalar_container_type_mismatch"
        for item in result.differences
    )


def test_success_response_constraints_do_not_leak_into_provider_errors() -> None:
    contract = compile_aws_botocore_scalar_contract(_source(), source_uri=SOURCE_URI)

    success = validate_aws_botocore_scalar_trace(contract, [_step(token="x")])
    provider_error = validate_aws_botocore_scalar_trace(
        contract,
        [_step(token="x", error_code="InvalidRequest")],
    )

    assert not success.admitted
    assert success.differences[0].path == ("response", "Token")
    assert provider_error.admitted


def test_bool_is_not_an_integer_even_though_python_subclasses_int() -> None:
    contract = compile_aws_botocore_scalar_contract(_source(), source_uri=SOURCE_URI)
    step = _step()
    step = replace(step, request={**step.request, "Count": True})

    result = validate_aws_botocore_scalar_trace(contract, [step])

    assert not result.admitted
    assert result.differences[0].reason == "trace_scalar_type_mismatch"


@pytest.mark.parametrize(
    ("string_min", "count_max", "message"),
    [
        (True, 10, "WidgetName.min must be a non-negative integer"),
        (3, False, "WidgetCount.max must be numeric"),
        (-1, 10, "WidgetName.min must be a non-negative integer"),
    ],
)
def test_malformed_provider_constraints_refuse_during_manufacture(
    string_min: object,
    count_max: object,
    message: str,
) -> None:
    with pytest.raises(AwsBotocoreScalarContractCompilationError, match=message):
        compile_aws_botocore_scalar_contract(
            _source(string_min=string_min, count_max=count_max),
            source_uri=SOURCE_URI,
        )


def test_removing_scalar_law_invalidates_existing_receipt() -> None:
    contract = compile_aws_botocore_scalar_contract(_source(), source_uri=SOURCE_URI)
    receipt = receipt_aws_botocore_scalar_contract(contract)

    weakened = without_scalar_rules(contract)

    assert replay_aws_botocore_scalar_contract(contract, receipt)
    assert not replay_aws_botocore_scalar_contract(weakened, receipt)


def test_source_identity_is_bound_to_receipt() -> None:
    contract = compile_aws_botocore_scalar_contract(_source(), source_uri=SOURCE_URI)
    receipt = receipt_aws_botocore_scalar_contract(contract)
    drifted = replace(contract, source_uri="botocore://s3/drifted/service-2.json")

    assert not replay_aws_botocore_scalar_contract(drifted, receipt)
