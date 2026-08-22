from gymact.gyms.cloud_fidelity import CloudTraceStep, compare_cloud_traces


def _aws_create_bucket_trace(*, request_id: str = "req-1") -> tuple[CloudTraceStep, ...]:
    return (
        CloudTraceStep(
            surface="aws-cli",
            operation="s3api.create-bucket",
            request={"Bucket": "gymact-fidelity", "Region": "us-east-1"},
            response={
                "Location": "/gymact-fidelity",
                "ResponseMetadata": {"RequestId": request_id, "HTTPStatusCode": 200},
            },
            status_code=200,
        ),
    )


def test_identical_agent_visible_trace_is_equivalent() -> None:
    result = compare_cloud_traces(_aws_create_bucket_trace(), _aws_create_bucket_trace())

    assert result.equivalent is True
    assert result.compared_steps == 1
    assert result.differences == ()


def test_provider_error_code_mismatch_is_never_ignored() -> None:
    reference = (
        CloudTraceStep(
            surface="boto3",
            operation="ec2.run_instances",
            request={"ImageId": "ami-123", "MinCount": 1, "MaxCount": 1},
            status_code=400,
            error_code="InsufficientInstanceCapacity",
        ),
    )
    twin = (
        CloudTraceStep(
            surface="boto3",
            operation="ec2.run_instances",
            request={"ImageId": "ami-123", "MinCount": 1, "MaxCount": 1},
            status_code=400,
            error_code="InternalError",
        ),
    )

    result = compare_cloud_traces(reference, twin, ignored_paths={("error_code",)})

    assert result.equivalent is False
    assert any(diff.path == ("error_code",) for diff in result.differences)
    assert any(diff.reason == "invalid_ignored_path" for diff in result.differences)


def test_volatile_payload_field_requires_explicit_path_admission() -> None:
    reference = _aws_create_bucket_trace(request_id="real-request-id")
    twin = _aws_create_bucket_trace(request_id="twin-request-id")

    strict = compare_cloud_traces(reference, twin)
    admitted = compare_cloud_traces(
        reference,
        twin,
        ignored_paths={("response", "ResponseMetadata", "RequestId")},
    )

    assert strict.equivalent is False
    assert admitted.equivalent is True


def test_missing_step_is_detected_even_when_shared_prefix_matches() -> None:
    first = _aws_create_bucket_trace()[0]
    second = CloudTraceStep(
        surface="aws-cli",
        operation="s3api.head-bucket",
        request={"Bucket": "gymact-fidelity"},
        response={"ResponseMetadata": {"HTTPStatusCode": 200}},
        status_code=200,
    )

    result = compare_cloud_traces((first, second), (first,))

    assert result.equivalent is False
    assert result.compared_steps == 1
    assert result.differences[0].reason == "step_count_mismatch"


def test_resource_shape_leak_is_detected() -> None:
    reference = (
        CloudTraceStep(
            surface="boto3",
            operation="iam.create_role",
            request={"RoleName": "worker"},
            response={"Role": {"Arn": "arn:aws:iam::123456789012:role/worker"}},
            status_code=200,
        ),
    )
    twin = (
        CloudTraceStep(
            surface="boto3",
            operation="iam.create_role",
            request={"RoleName": "worker"},
            response={"Role": {"Arn": "gymact://iam/role/worker"}},
            status_code=200,
        ),
    )

    result = compare_cloud_traces(reference, twin)

    assert result.equivalent is False
    assert any(diff.path == ("response", "Role", "Arn") for diff in result.differences)


def _two_step_request_id_trace(first: str, second: str) -> tuple[CloudTraceStep, ...]:
    create = _aws_create_bucket_trace(request_id=first)[0]
    head = CloudTraceStep(
        surface="aws-cli",
        operation="s3api.head-bucket",
        request={"Bucket": "gymact-fidelity"},
        response={"ResponseMetadata": {"RequestId": second, "HTTPStatusCode": 200}},
        status_code=200,
    )
    return create, head


def test_multistep_global_ignore_is_refused_as_overbroad() -> None:
    reference = _two_step_request_id_trace("real-create", "real-head")
    twin = _two_step_request_id_trace("twin-create", "twin-head")

    result = compare_cloud_traces(
        reference,
        twin,
        ignored_paths={("response", "ResponseMetadata", "RequestId")},
    )

    assert result.equivalent is False
    assert any(diff.reason == "unscoped_ignored_path" for diff in result.differences)
    assert sum(diff.reason == "value_mismatch" for diff in result.differences) == 2


def test_step_scoped_ignore_suppresses_only_the_admitted_operation() -> None:
    reference = _two_step_request_id_trace("real-create", "real-head")
    twin = _two_step_request_id_trace("twin-create", "twin-head")

    result = compare_cloud_traces(
        reference,
        twin,
        ignored_paths_by_step={0: {("response", "ResponseMetadata", "RequestId")}},
    )

    assert result.equivalent is False
    assert not any(diff.step == 0 and diff.reason == "value_mismatch" for diff in result.differences)
    assert any(diff.step == 1 and diff.reason == "value_mismatch" for diff in result.differences)


def test_step_scoped_response_volatility_can_be_admitted_per_operation() -> None:
    reference = _two_step_request_id_trace("real-create", "real-head")
    twin = _two_step_request_id_trace("twin-create", "twin-head")
    path = ("response", "ResponseMetadata", "RequestId")

    result = compare_cloud_traces(
        reference,
        twin,
        ignored_paths_by_step={0: {path}, 1: {path}},
    )

    assert result.equivalent is True


def test_request_fields_cannot_be_suppressed_as_volatility() -> None:
    reference = _aws_create_bucket_trace()
    twin = (
        CloudTraceStep(
            surface="aws-cli",
            operation="s3api.create-bucket",
            request={"Bucket": "different", "Region": "us-east-1"},
            response=reference[0].response,
            status_code=200,
        ),
    )

    result = compare_cloud_traces(reference, twin, ignored_paths={("request", "Bucket")})

    assert result.equivalent is False
    assert any(diff.reason == "invalid_ignored_path" for diff in result.differences)
    assert any(diff.path == ("request", "Bucket") for diff in result.differences)


def test_out_of_range_scoped_ignore_is_refused() -> None:
    trace = _aws_create_bucket_trace()

    result = compare_cloud_traces(
        trace,
        trace,
        ignored_paths_by_step={1: {("response", "ResponseMetadata", "RequestId")}},
    )

    assert result.equivalent is False
    assert any(diff.reason == "invalid_ignored_step" for diff in result.differences)
