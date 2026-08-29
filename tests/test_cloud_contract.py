from dataclasses import replace

from gymact.gyms.cloud_contract import (
    CloudContractEvidence,
    CloudContractProfile,
    CloudContractSource,
    CloudOperationContract,
    CloudValuePrefixRule,
    compare_cloud_traces_under_contract,
    compare_cloud_traces_under_evidence,
    digest_cloud_contract_source,
    receipt_cloud_contract_evidence,
    receipt_cloud_contract_profile,
    replay_cloud_contract_evidence,
    replay_cloud_contract_profile,
    validate_cloud_contract_source,
    validate_cloud_trace_contract,
)
from gymact.gyms.cloud_fidelity import CloudTraceStep, compare_cloud_traces

SOURCE_BYTES = b'{"service":"s3","operation":"CreateBucket","version":"2006-03-01"}'
SOURCE_URI = "urn:aws:botocore:s3:service-model"


def _create_bucket_contract() -> CloudContractProfile:
    return CloudContractProfile(
        name="aws-public-contract-v1",
        operations=(
            CloudOperationContract(
                surface="aws-cli",
                operation="s3api.create-bucket",
                required_paths=(
                    ("request", "Bucket"),
                    ("request", "Region"),
                    ("response", "Location"),
                    ("response", "ResponseMetadata", "HTTPStatusCode"),
                ),
                string_prefix_rules=(
                    CloudValuePrefixRule(("response", "Location"), "/"),
                ),
                allowed_status_codes=(200,),
                allowed_error_codes=(None,),
            ),
        ),
    )


def _create_bucket_evidence() -> CloudContractEvidence:
    return CloudContractEvidence(
        profile=_create_bucket_contract(),
        source=CloudContractSource(
            uri=SOURCE_URI,
            digest=digest_cloud_contract_source(SOURCE_BYTES),
            media_type="application/json",
        ),
    )


def _create_bucket_trace(*, location: str = "/gymact-fidelity") -> tuple[CloudTraceStep, ...]:
    return (
        CloudTraceStep(
            surface="aws-cli",
            operation="s3api.create-bucket",
            request={"Bucket": "gymact-fidelity", "Region": "us-east-1"},
            response={
                "Location": location,
                "ResponseMetadata": {"HTTPStatusCode": 200},
            },
            status_code=200,
        ),
    )


def test_valid_trace_is_admitted_and_equivalent_under_contract() -> None:
    trace = _create_bucket_trace()
    result = compare_cloud_traces_under_contract(trace, trace, _create_bucket_contract())

    assert result.equivalent is True
    assert result.differences == ()


def test_identically_malformed_traces_no_longer_create_vacuous_equivalence() -> None:
    malformed = (
        replace(
            _create_bucket_trace()[0],
            response={"ResponseMetadata": {"HTTPStatusCode": 200}},
        ),
    )

    previous = compare_cloud_traces(malformed, malformed)
    admitted = compare_cloud_traces_under_contract(
        malformed,
        malformed,
        _create_bucket_contract(),
    )

    assert previous.equivalent is True
    assert admitted.equivalent is False
    assert {diff.reason for diff in admitted.differences} == {
        "reference_contract_missing_required_path",
        "reference_contract_prefix_mismatch",
        "twin_contract_missing_required_path",
        "twin_contract_prefix_mismatch",
    }


def test_same_non_provider_resource_shape_on_both_sides_is_refused() -> None:
    profile = CloudContractProfile(
        name="aws-iam-v1",
        operations=(
            CloudOperationContract(
                surface="boto3",
                operation="iam.create_role",
                required_paths=(("response", "Role", "Arn"),),
                string_prefix_rules=(
                    CloudValuePrefixRule(
                        ("response", "Role", "Arn"),
                        "arn:aws:iam::",
                    ),
                ),
                allowed_status_codes=(200,),
                allowed_error_codes=(None,),
            ),
        ),
    )
    malformed = (
        CloudTraceStep(
            surface="boto3",
            operation="iam.create_role",
            request={"RoleName": "worker"},
            response={"Role": {"Arn": "gymact://iam/role/worker"}},
            status_code=200,
        ),
    )

    result = compare_cloud_traces_under_contract(malformed, malformed, profile)

    assert result.equivalent is False
    assert sum(
        diff.reason.endswith("contract_prefix_mismatch")
        for diff in result.differences
    ) == 2


def test_unknown_operation_is_refused_instead_of_inferred_from_reference() -> None:
    unknown = (
        CloudTraceStep(
            surface="aws-cli",
            operation="s3api.delete-bucket",
            request={"Bucket": "gymact-fidelity"},
            status_code=204,
        ),
    )

    result = validate_cloud_trace_contract(unknown, _create_bucket_contract())

    assert result.admitted is False
    assert result.differences[0].reason == "trace_contract_operation_unadmitted"


def test_duplicate_contract_identity_fails_closed() -> None:
    contract = _create_bucket_contract().operations[0]
    profile = CloudContractProfile("duplicate", (contract, contract))

    result = validate_cloud_trace_contract(_create_bucket_trace(), profile)

    assert result.admitted is False
    assert any(diff.reason == "duplicate_contract_operation" for diff in result.differences)


def test_contract_receipt_replays_deterministically_and_detects_profile_drift() -> None:
    profile = _create_bucket_contract()
    receipt = receipt_cloud_contract_profile(profile)

    assert replay_cloud_contract_profile(profile, receipt) is True
    assert receipt_cloud_contract_profile(profile) == receipt

    drifted = replace(profile, name="aws-public-contract-v2")
    assert replay_cloud_contract_profile(drifted, receipt) is False


def test_unadmitted_status_code_is_a_contract_falsifier() -> None:
    trace = (replace(_create_bucket_trace()[0], status_code=201),)

    result = validate_cloud_trace_contract(trace, _create_bucket_contract())

    assert result.admitted is False
    assert any(diff.reason == "trace_contract_status_unadmitted" for diff in result.differences)


def test_source_bound_contract_evidence_admits_exact_source_and_trace() -> None:
    trace = _create_bucket_trace()
    evidence = _create_bucket_evidence()

    source = validate_cloud_contract_source(evidence, SOURCE_BYTES)
    result = compare_cloud_traces_under_evidence(
        trace,
        trace,
        evidence,
        SOURCE_BYTES,
    )

    assert source.admitted is True
    assert result.equivalent is True


def test_tampered_source_bytes_fail_before_equivalence_can_be_claimed() -> None:
    trace = _create_bucket_trace()
    evidence = _create_bucket_evidence()

    result = compare_cloud_traces_under_evidence(
        trace,
        trace,
        evidence,
        SOURCE_BYTES + b"tampered",
    )

    assert result.equivalent is False
    assert any(
        diff.reason == "contract_source_digest_mismatch"
        for diff in result.differences
    )


def test_source_identity_and_digest_are_part_of_evidence_receipt_replay() -> None:
    evidence = _create_bucket_evidence()
    receipt = receipt_cloud_contract_evidence(evidence)

    assert replay_cloud_contract_evidence(evidence, receipt) is True

    changed_uri = replace(
        evidence,
        source=replace(evidence.source, uri=SOURCE_URI + ":v2"),
    )
    assert replay_cloud_contract_evidence(changed_uri, receipt) is False

    changed_digest = replace(
        evidence,
        source=replace(evidence.source, digest="0" * 64),
    )
    assert replay_cloud_contract_evidence(changed_digest, receipt) is False


def test_missing_source_identity_fails_closed() -> None:
    evidence = _create_bucket_evidence()
    evidence = replace(
        evidence,
        source=replace(evidence.source, uri="", media_type=""),
    )

    result = validate_cloud_contract_source(evidence, SOURCE_BYTES)

    assert result.admitted is False
    assert {diff.reason for diff in result.differences} == {
        "contract_source_uri_missing",
        "contract_source_media_type_missing",
    }
