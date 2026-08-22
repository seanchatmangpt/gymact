import json

import pytest

from gymact.gyms.aws_botocore_contract import (
    AwsBotocoreContractCompilationError,
    compile_aws_botocore_contract,
)
from gymact.gyms.cloud_contract import validate_cloud_trace_contract
from gymact.gyms.cloud_fidelity import CloudTraceStep

SOURCE_URI = "urn:aws:botocore:nested:service-2"


def _nested_service_model() -> bytes:
    model = {
        "metadata": {"endpointPrefix": "nested", "apiVersion": "2026-08-22"},
        "operations": {
            "PutThing": {
                "http": {"responseCode": 201},
                "input": {"shape": "PutThingRequest"},
                "output": {"shape": "PutThingOutput"},
            }
        },
        "shapes": {
            "PutThingRequest": {
                "type": "structure",
                "required": ["Config"],
                "members": {"Config": {"shape": "Config"}},
            },
            "Config": {
                "type": "structure",
                "required": ["Region"],
                "members": {
                    "Region": {"shape": "String"},
                    "Optional": {"shape": "OptionalConfig"},
                },
            },
            "OptionalConfig": {
                "type": "structure",
                "required": ["Token"],
                "members": {"Token": {"shape": "String"}},
            },
            "PutThingOutput": {
                "type": "structure",
                "required": ["Result"],
                "members": {"Result": {"shape": "Result"}},
            },
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
    return compile_aws_botocore_contract(
        _nested_service_model() if source is None else source,
        source_uri=SOURCE_URI,
    )


def test_nested_required_structures_are_manufactured_deterministically() -> None:
    first = _compile()
    second = _compile()
    contract = first.profile.operations[0]

    assert first.profile == second.profile
    assert contract.required_paths == (
        ("request", "Config"),
        ("request", "Config", "Region"),
    )
    assert contract.success_required_paths == (
        ("response", "Result"),
        ("response", "Result", "Id"),
    )


def test_missing_nested_request_requirement_is_refused() -> None:
    evidence = _compile()
    trace = (
        CloudTraceStep(
            surface="boto3",
            operation="nested.put_thing",
            request={"Config": {}},
            response={"Result": {"Id": "thing-1"}},
            status_code=201,
        ),
    )

    result = validate_cloud_trace_contract(trace, evidence.profile)

    assert result.admitted is False
    assert [(diff.reason, diff.path) for diff in result.differences] == [
        (
            "trace_contract_missing_required_path",
            ("request", "Config", "Region"),
        )
    ]


def test_missing_nested_success_requirement_is_refused() -> None:
    evidence = _compile()
    trace = (
        CloudTraceStep(
            surface="boto3",
            operation="nested.put_thing",
            request={"Config": {"Region": "us-east-1"}},
            response={"Result": {}},
            status_code=201,
        ),
    )

    result = validate_cloud_trace_contract(trace, evidence.profile)

    assert result.admitted is False
    assert [(diff.reason, diff.path) for diff in result.differences] == [
        (
            "trace_contract_missing_success_required_path",
            ("response", "Result", "Id"),
        )
    ]


def test_required_fields_under_optional_parent_are_not_overconstrained() -> None:
    evidence = _compile()
    contract = evidence.profile.operations[0]
    trace = (
        CloudTraceStep(
            surface="boto3",
            operation="nested.put_thing",
            request={"Config": {"Region": "us-east-1", "Optional": {}}},
            response={"Result": {"Id": "thing-1"}},
            status_code=201,
        ),
    )

    assert ("request", "Config", "Optional", "Token") not in contract.required_paths
    assert validate_cloud_trace_contract(trace, evidence.profile).admitted is True


def test_recursive_required_structure_stops_at_cycle_edge() -> None:
    model = json.loads(_nested_service_model())
    model["shapes"]["Config"]["required"].append("Child")
    model["shapes"]["Config"]["members"]["Child"] = {"shape": "Config"}
    source = json.dumps(model, separators=(",", ":")).encode()

    contract = _compile(source).profile.operations[0]

    assert contract.required_paths == (
        ("request", "Config"),
        ("request", "Config", "Child"),
        ("request", "Config", "Region"),
    )


def test_required_member_absent_from_members_fails_closed() -> None:
    model = json.loads(_nested_service_model())
    model["shapes"]["Config"]["required"].append("Missing")
    source = json.dumps(model, separators=(",", ":")).encode()

    with pytest.raises(AwsBotocoreContractCompilationError, match="absent from members"):
        _compile(source)


def test_dangling_nested_shape_fails_closed() -> None:
    model = json.loads(_nested_service_model())
    model["shapes"]["Config"]["members"]["Region"] = {"shape": "MissingShape"}
    source = json.dumps(model, separators=(",", ":")).encode()

    with pytest.raises(AwsBotocoreContractCompilationError, match="shapes.MissingShape"):
        _compile(source)


def test_non_structure_operation_root_fails_closed() -> None:
    model = json.loads(_nested_service_model())
    model["shapes"]["PutThingRequest"]["type"] = "string"
    source = json.dumps(model, separators=(",", ":")).encode()

    with pytest.raises(
        AwsBotocoreContractCompilationError,
        match="must be 'structure' for an operation input/output",
    ):
        _compile(source)
