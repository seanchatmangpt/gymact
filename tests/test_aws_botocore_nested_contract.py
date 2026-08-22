import json
from dataclasses import replace

import pytest

from gymact.gyms.aws_botocore_contract import (
    AwsBotocoreContractCompilationError,
    compile_aws_botocore_contract,
)
from gymact.gyms.cloud_contract import (
    receipt_cloud_contract_profile,
    replay_cloud_contract_profile,
    validate_cloud_trace_contract,
)
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
                "members": {
                    "Token": {"shape": "String"},
                    "Nested": {"shape": "NestedOptional"},
                },
            },
            "NestedOptional": {
                "type": "structure",
                "required": ["Code"],
                "members": {"Code": {"shape": "String"}},
            },
            "PutThingOutput": {
                "type": "structure",
                "required": ["Result"],
                "members": {
                    "Result": {"shape": "Result"},
                    "Metadata": {"shape": "Metadata"},
                },
            },
            "Result": {
                "type": "structure",
                "required": ["Id"],
                "members": {"Id": {"shape": "String"}},
            },
            "Metadata": {
                "type": "structure",
                "required": ["TraceId"],
                "members": {"TraceId": {"shape": "String"}},
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


def _success_step(*, request: dict | None = None, response: dict | None = None) -> CloudTraceStep:
    return CloudTraceStep(
        surface="boto3",
        operation="nested.put_thing",
        request=request if request is not None else {"Config": {"Region": "us-east-1"}},
        response=response if response is not None else {"Result": {"Id": "thing-1"}},
        status_code=201,
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
    assert [rule.guard_paths for rule in contract.conditional_required_paths] == [
        (("request", "Config", "Optional"),),
        (
            ("request", "Config", "Optional"),
            ("request", "Config", "Optional", "Nested"),
        ),
    ]
    assert [rule.path for rule in contract.conditional_required_paths] == [
        ("request", "Config", "Optional", "Token"),
        ("request", "Config", "Optional", "Nested", "Code"),
    ]
    assert [rule.path for rule in contract.success_conditional_required_paths] == [
        ("response", "Metadata", "TraceId")
    ]


def test_missing_nested_request_requirement_is_refused() -> None:
    result = validate_cloud_trace_contract(
        (_success_step(request={"Config": {}}),), _compile().profile
    )

    assert result.admitted is False
    assert [(diff.reason, diff.path) for diff in result.differences] == [
        (
            "trace_contract_missing_required_path",
            ("request", "Config", "Region"),
        )
    ]


def test_missing_nested_success_requirement_is_refused() -> None:
    result = validate_cloud_trace_contract(
        (_success_step(response={"Result": {}}),), _compile().profile
    )

    assert result.admitted is False
    assert [(diff.reason, diff.path) for diff in result.differences] == [
        (
            "trace_contract_missing_success_required_path",
            ("response", "Result", "Id"),
        )
    ]


def test_optional_parent_absent_does_not_activate_descendant_requirement() -> None:
    result = validate_cloud_trace_contract((_success_step(),), _compile().profile)

    assert result.admitted is True


def test_optional_parent_present_requires_provider_required_descendant() -> None:
    step = _success_step(request={"Config": {"Region": "us-east-1", "Optional": {}}})

    result = validate_cloud_trace_contract((step,), _compile().profile)

    assert result.admitted is False
    assert [(diff.reason, diff.path) for diff in result.differences] == [
        (
            "trace_contract_missing_conditional_required_path",
            ("request", "Config", "Optional", "Token"),
        )
    ]


def test_optional_parent_with_required_descendant_is_admitted() -> None:
    step = _success_step(
        request={"Config": {"Region": "us-east-1", "Optional": {"Token": "t"}}}
    )

    assert validate_cloud_trace_contract((step,), _compile().profile).admitted is True


def test_nested_optional_guard_requires_every_optional_ancestor() -> None:
    only_outer = _success_step(
        request={"Config": {"Region": "us-east-1", "Optional": {"Token": "t"}}}
    )
    both_present_missing_code = _success_step(
        request={
            "Config": {
                "Region": "us-east-1",
                "Optional": {"Token": "t", "Nested": {}},
            }
        }
    )

    assert validate_cloud_trace_contract((only_outer,), _compile().profile).admitted is True
    result = validate_cloud_trace_contract((both_present_missing_code,), _compile().profile)
    assert result.admitted is False
    assert [(diff.reason, diff.path) for diff in result.differences] == [
        (
            "trace_contract_missing_conditional_required_path",
            ("request", "Config", "Optional", "Nested", "Code"),
        )
    ]


def test_success_optional_response_parent_activates_only_on_success() -> None:
    success = _success_step(response={"Result": {"Id": "thing-1"}, "Metadata": {}})
    success_result = validate_cloud_trace_contract((success,), _compile().profile)

    assert success_result.admitted is False
    assert [(diff.reason, diff.path) for diff in success_result.differences] == [
        (
            "trace_contract_missing_success_conditional_required_path",
            ("response", "Metadata", "TraceId"),
        )
    ]

    model = json.loads(_nested_service_model())
    model["operations"]["PutThing"]["errors"] = [{"shape": "Conflict"}]
    model["shapes"]["Conflict"] = {
        "type": "structure",
        "members": {},
        "error": {"code": "Conflict", "httpStatusCode": 409},
    }
    evidence = _compile(json.dumps(model, separators=(",", ":")).encode())
    error = CloudTraceStep(
        surface="boto3",
        operation="nested.put_thing",
        request={"Config": {"Region": "us-east-1"}},
        response={"Metadata": {}},
        status_code=409,
        error_code="Conflict",
    )

    assert validate_cloud_trace_contract((error,), evidence.profile).admitted is True


def test_conditional_rules_are_bound_into_profile_receipt_replay() -> None:
    evidence = _compile()
    receipt = receipt_cloud_contract_profile(evidence.profile)
    contract = evidence.profile.operations[0]
    weakened = replace(
        evidence.profile,
        operations=(replace(contract, conditional_required_paths=()),),
    )

    assert replay_cloud_contract_profile(evidence.profile, receipt) is True
    assert replay_cloud_contract_profile(weakened, receipt) is False


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


def test_dangling_optional_shape_fails_closed() -> None:
    model = json.loads(_nested_service_model())
    model["shapes"]["Config"]["members"]["Optional"] = {"shape": "MissingShape"}
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
