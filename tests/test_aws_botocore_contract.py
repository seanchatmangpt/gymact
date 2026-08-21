import json
from dataclasses import replace

import pytest

from gymact.gyms.aws_botocore_contract import (
    AwsBotocoreContractCompilationError,
    compile_aws_botocore_contract,
)
from gymact.gyms.cloud_contract import (
    compare_cloud_traces_under_evidence,
    digest_cloud_contract_source,
    receipt_cloud_contract_evidence,
    replay_cloud_contract_evidence,
    validate_cloud_trace_contract,
)
from gymact.gyms.cloud_fidelity import CloudTraceStep

SOURCE_URI = "urn:aws:botocore:s3:service-2"


def _service_model(*, reverse_operations: bool = False) -> bytes:
    operations = {
        "CreateBucket": {
            "http": {"responseCode": 200},
            "input": {"shape": "CreateBucketRequest"},
            "output": {"shape": "CreateBucketOutput"},
            "errors": [{"shape": "BucketAlreadyExists"}],
        },
        "DeleteBucket": {
            "http": {"responseCode": 204},
            "input": {"shape": "DeleteBucketRequest"},
        },
    }
    if reverse_operations:
        operations = dict(reversed(tuple(operations.items())))
    model = {
        "metadata": {"endpointPrefix": "s3", "apiVersion": "2006-03-01"},
        "operations": operations,
        "shapes": {
            "CreateBucketRequest": {
                "type": "structure",
                "required": ["Bucket", "Bucket"],
                "members": {"Bucket": {"shape": "BucketName"}},
            },
            "CreateBucketOutput": {
                "type": "structure",
                "required": ["Location"],
                "members": {"Location": {"shape": "Location"}},
            },
            "DeleteBucketRequest": {
                "type": "structure",
                "required": ["Bucket"],
                "members": {"Bucket": {"shape": "BucketName"}},
            },
            "BucketAlreadyExists": {
                "type": "structure",
                "error": {"code": "BucketAlreadyExists", "httpStatusCode": 409},
            },
            "BucketName": {"type": "string"},
            "Location": {"type": "string"},
        },
    }
    return json.dumps(model, separators=(",", ":")).encode()


def test_compiler_manufactures_deterministic_boto3_contract() -> None:
    source = _service_model()
    evidence = compile_aws_botocore_contract(source, source_uri=SOURCE_URI)

    assert evidence.profile.name == "aws-botocore:s3:2006-03-01"
    assert [contract.operation for contract in evidence.profile.operations] == [
        "s3.create_bucket",
        "s3.delete_bucket",
    ]
    create = evidence.profile.operations[0]
    assert create.surface == "boto3"
    assert create.required_paths == (("request", "Bucket"),)
    assert create.allowed_status_codes == (200, 409)
    assert create.allowed_error_codes == (None, "BucketAlreadyExists")
    assert evidence.source.digest == digest_cloud_contract_source(source)
    assert evidence.source.media_type == "application/json"


def test_success_and_provider_error_traces_are_admitted() -> None:
    evidence = compile_aws_botocore_contract(_service_model(), source_uri=SOURCE_URI)
    success = (
        CloudTraceStep(
            surface="boto3",
            operation="s3.create_bucket",
            request={"Bucket": "gymact"},
            response={"Location": "/gymact"},
            status_code=200,
        ),
    )
    failure = (
        CloudTraceStep(
            surface="boto3",
            operation="s3.create_bucket",
            request={"Bucket": "gymact"},
            response={},
            status_code=409,
            error_code="BucketAlreadyExists",
        ),
    )

    assert validate_cloud_trace_contract(success, evidence.profile).admitted is True
    assert validate_cloud_trace_contract(failure, evidence.profile).admitted is True


def test_compiled_evidence_replays_and_qualifies_trace() -> None:
    source = _service_model()
    evidence = compile_aws_botocore_contract(source, source_uri=SOURCE_URI)
    receipt = receipt_cloud_contract_evidence(evidence)
    trace = (
        CloudTraceStep(
            surface="boto3",
            operation="s3.delete_bucket",
            request={"Bucket": "gymact"},
            status_code=204,
        ),
    )

    assert replay_cloud_contract_evidence(evidence, receipt) is True
    assert compare_cloud_traces_under_evidence(
        trace, trace, evidence, source
    ).equivalent is True


def test_source_tamper_invalidates_compiled_evidence() -> None:
    source = _service_model()
    evidence = compile_aws_botocore_contract(source, source_uri=SOURCE_URI)
    trace = (
        CloudTraceStep(
            surface="boto3",
            operation="s3.delete_bucket",
            request={"Bucket": "gymact"},
            status_code=204,
        ),
    )

    result = compare_cloud_traces_under_evidence(
        trace, trace, evidence, source + b"tampered"
    )

    assert result.equivalent is False
    assert any(diff.reason == "contract_source_digest_mismatch" for diff in result.differences)


def test_operation_order_and_required_member_duplicates_do_not_change_profile() -> None:
    first = compile_aws_botocore_contract(_service_model(), source_uri=SOURCE_URI)
    second = compile_aws_botocore_contract(
        _service_model(reverse_operations=True), source_uri=SOURCE_URI
    )

    assert first.profile == second.profile


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (b"{", "valid UTF-8 JSON"),
        (
            json.dumps({"metadata": {}, "operations": {}, "shapes": {}}).encode(),
            "endpointPrefix",
        ),
        (
            json.dumps(
                {
                    "metadata": {"endpointPrefix": "s3", "apiVersion": "2006-03-01"},
                    "operations": {
                        "CreateBucket": {"input": {"shape": "MissingShape"}}
                    },
                    "shapes": {},
                }
            ).encode(),
            "shapes.MissingShape",
        ),
    ],
)
def test_malformed_models_fail_closed(source: bytes, message: str) -> None:
    with pytest.raises(AwsBotocoreContractCompilationError, match=message):
        compile_aws_botocore_contract(source, source_uri=SOURCE_URI)


def test_invalid_error_status_type_fails_closed() -> None:
    model = json.loads(_service_model())
    model["shapes"]["BucketAlreadyExists"]["error"]["httpStatusCode"] = True

    with pytest.raises(AwsBotocoreContractCompilationError, match="httpStatusCode"):
        compile_aws_botocore_contract(
            json.dumps(model).encode(),
            source_uri=SOURCE_URI,
        )


def test_blank_source_identity_is_refused() -> None:
    with pytest.raises(AwsBotocoreContractCompilationError, match="source_uri"):
        compile_aws_botocore_contract(_service_model(), source_uri="   ")


def test_profile_drift_invalidates_existing_evidence_receipt() -> None:
    evidence = compile_aws_botocore_contract(_service_model(), source_uri=SOURCE_URI)
    receipt = receipt_cloud_contract_evidence(evidence)
    drifted = replace(
        evidence,
        profile=replace(evidence.profile, name=evidence.profile.name + ":drift"),
    )

    assert replay_cloud_contract_evidence(drifted, receipt) is False
