from __future__ import annotations

import pytest

from gymact.gyms.gcp_exact import DiscoveryMethod
from gymact.gyms.gcp_simulator import (
    GCP_ADVANCE_CLOCK_CAPABILITY,
    GCP_INVOKE_CAPABILITY,
    GcpExactSimulator,
    GcpExactSimulatorEnvironment,
)


def _create_lro() -> DiscoveryMethod:
    return DiscoveryMethod(
        api="example",
        version="v1",
        resource_path="widgets",
        name="create",
        http_method="POST",
        path="v1/widgets",
        request_schema="Widget",
        response_schema="Operation",
        scopes=(),
    )


def _method_config(method: DiscoveryMethod) -> dict[str, object]:
    return {
        "api": method.api,
        "version": method.version,
        "resource_path": method.resource_path,
        "name": method.name,
        "http_method": method.http_method,
        "path": method.path,
        "request_schema": method.request_schema,
        "response_schema": method.response_schema,
        "scopes": list(method.scopes),
    }


@pytest.mark.asyncio
async def test_lro_quota_is_charged_once_at_submission_not_again_at_completion() -> None:
    method = _create_lro()
    env = GcpExactSimulatorEnvironment(
        methods=(method,),
        quota_limits={method.identity: 1},
        requires_authority=False,
    )

    submitted = await env.actuate(
        GCP_INVOKE_CAPABILITY,
        {"method_id": method.identity, "body": {"name": "widgets/one"}},
    )
    assert submitted["result"]["status_code"] == 200
    assert (await env.observe())["quota_usage"] == {method.identity: 1}
    assert "widgets/one" not in (await env.observe())["resources"]

    await env.actuate(GCP_ADVANCE_CLOCK_CAPABILITY, {"ticks": 1})
    observed = await env.observe()
    assert observed["quota_usage"] == {method.identity: 1}
    assert observed["resources"]["widgets/one"]["name"] == "widgets/one"

    exhausted = await env.actuate(
        GCP_INVOKE_CAPABILITY,
        {"method_id": method.identity, "body": {"name": "widgets/two"}},
    )
    assert exhausted["result"]["status_code"] == 429
    assert exhausted["result"]["body"]["error"]["status"] == "RESOURCE_EXHAUSTED"


@pytest.mark.asyncio
async def test_factory_refuses_boolean_quota_instead_of_coercing_it_to_integer() -> None:
    method = _create_lro()
    provider = GcpExactSimulator()
    with pytest.raises(ValueError, match="quota limit must be a non-negative integer"):
        await provider.materialize(
            scenario=None,
            config={
                "methods": [_method_config(method)],
                "quota_limits": {method.identity: True},
            },
        )
