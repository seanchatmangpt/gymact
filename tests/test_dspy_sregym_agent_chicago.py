"""Chicago-style tests for `gymact.dspy_sregym_agent` -- the sregym-specific
DSPy ReAct agent. No mocks: `_summarize_one_deployment`/
`_summarize_deployment_configs` are tested directly against real, captured
`kubectl get deployment[s] -o json` fixtures (`tests/fixtures/
real_sregym_deployment*.json`) -- fast, offline, no live cluster needed to
iterate on the parsing logic. `SregymDiagnosisAgent` itself is exercised
only via its real, live, gated end-to-end test in
`scripts/run_dspy_sregym_diagnosis.py` (needs a real cluster + Groq key,
not suited to a fast unit test).

Per `gymact.standing.require_standing`, real is the default: if the
optional `dspy` extra isn't installed, this module FAILS unless the run
explicitly opts into the degraded standing.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from gymact.standing import require_standing

require_standing(
    "LOCAL_EXTRA:dspy",
    available=importlib.util.find_spec("dspy") is not None,
    reason="the optional 'dspy' extra is not installed -- `uv sync --extra dspy`",
)

from gymact.dspy_sregym_agent import (  # noqa: E402
    DeploymentConfigSummary,
    K8sDeployment,
    _summarize_deployment_configs,
    _summarize_one_deployment,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestSummarizeOneDeployment:
    """Real parsing against a real, captured `kubectl get deployment
    consul -n hotel-reservation -o json` response."""

    def test_extracts_real_image_command_resources_replicas(self):
        raw = json.loads((FIXTURES / "real_sregym_deployment.json").read_text())
        summary = _summarize_one_deployment(raw)
        assert isinstance(summary, DeploymentConfigSummary)
        assert summary.name == "consul"
        assert summary.image == "hashicorp/consul:1.22.3"
        assert summary.replicas == 1
        assert summary.resource_requests == {"cpu": "100m"}
        assert summary.resource_limits == {"cpu": "1"}

    def test_real_deployment_validates_against_the_real_k8s_shape(self):
        # Direct proof the typed K8sDeployment model actually accepts a
        # real, unmodified Kubernetes API response -- not just our own
        # hand-shaped fixture -- extra real fields (status, managedFields,
        # metadata.annotations, ...) are ignored, not rejected.
        raw = json.loads((FIXTURES / "real_sregym_deployment.json").read_text())
        deployment = K8sDeployment.model_validate(raw)
        assert deployment.metadata.name == "consul"
        assert deployment.spec.replicas == 1

    def test_env_vars_are_sorted_name_equals_value_pairs(self):
        raw = json.loads((FIXTURES / "real_sregym_deployments_list.json").read_text())
        frontend = next(
            item for item in raw["items"] if item["metadata"]["name"] == "frontend"
        )
        summary = _summarize_one_deployment(frontend)
        assert summary.env == ["JAEGER_SAMPLE_RATIO=1"]
        assert summary.command == ["frontend"]


class TestSummarizeDeploymentConfigs:
    """Real parsing of a real, captured multi-item `List` response."""

    def test_summarizes_every_real_item_in_the_list(self):
        raw = json.loads((FIXTURES / "real_sregym_deployments_list.json").read_text())
        summaries = _summarize_deployment_configs(raw)
        names = {summary.name for summary in summaries}
        assert names == {"consul", "frontend"}

    def test_empty_items_list_produces_empty_summary_not_an_error(self):
        assert _summarize_deployment_configs({"items": []}) == []
