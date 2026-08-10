"""Built-in provider registry; semantic capability identity stays shared across transports."""

from __future__ import annotations

from typing import Any

from gymact.gyms.cloudsim import CLOUDSIM_CAPABILITIES, CloudSimProvider
from gymact.gyms.codebase import CODEBASE_CAPABILITIES, CodebaseProvider
from gymact.gyms.discovered import DISCOVERED_RUN_CAPABILITY, GenericDiscoveredProvider
from gymact.gyms.ggen import GGEN_CAPABILITIES, GgenProvider
from gymact.gyms.ggen_legacy import GGEN_LEGACY_CAPABILITIES, GgenLegacyVerifierProvider
from gymact.gyms.kubernetes_reconciliation import (
    KUBERNETES_RECONCILIATION_CAPABILITIES,
    KubernetesReconciliationProvider,
)
from gymact.gyms.mcp_client_session import (
    MCP_CALL_TOOL_CAPABILITY,
    MCP_LIST_TOOLS_CAPABILITY,
    McpClientSessionProvider,
)
from gymact.gyms.multicloud import CAPABILITY_REGISTRY as MULTICLOUD_CAPABILITIES
from gymact.gyms.multicloud import MulticloudProvider
from gymact.gyms.sregym import SREGYM_RUN_CAPABILITY, SREGymProvider
from gymact.gyms.swegym import SWEGYM_EVALUATE_CAPABILITY, SWEGymProvider
from gymact.gyms.terraform_docker_apply import (
    TERRAFORM_DOCKER_APPLY_CAPABILITIES,
    TerraformDockerApplyProvider,
)
from gymact.gyms.terraform_plan import TERRAFORM_PLAN_CAPABILITIES, TerraformPlanProvider

# NOT registered here (deliberately, not an oversight):
#   - gymact.gyms.browsergym.BrowserGymProvider: top-level `import browsergym.core` /
#     `import gymnasium`, both gated behind the optional "gyms" extra -- importing this
#     module with only the base install raises ImportError, so registering it would break
#     a clean `import gymact.registry`.
#   - gymact.gyms.gymnasium_env.GymnasiumProvider: top-level `import gymnasium`, same
#     optional "gyms" extra gate as browsergym.py above.
#   - gymact.gyms.inspect_evals.InspectEvalsProvider: top-level `from inspect_ai import
#     ...`, gated behind the optional "gyms" extra (inspect-ai).
#   - gymact.gyms.cube_counter.CubeCounterProvider: top-level `from counter_cube...`
#     wrapped in try/except that re-raises ImportError, gated behind the optional "cube"
#     extra (cube-standard/counter-cube, Python >=3.12 only).
#   - gymact.gyms.cube_container_counter.CubeContainerCounterProvider: top-level
#     `from cube.infra_local import LocalInfraConfig` wrapped in try/except that
#     re-raises ImportError, gated behind the optional "cube" extra with Docker.
#   - gymact.gyms.vendor_benchmarks.VendorBenchmarkProvider: generic vendor-benchmark
#     dispatch surface, not a single fixed-capability gym -- registered per-vendor
#     benchmark target elsewhere, not as one flat builtin name here.
from gymact.local_providers import (
    FILESYSTEM_CAPABILITIES,
    GIT_CAPABILITIES,
    SQLITE_CAPABILITIES,
    FilesystemProvider,
    GitProvider,
    SQLiteProvider,
)
from gymact.network_providers import HTTP_JSON_CAPABILITIES, HTTPJSONProvider
from gymact.providers import MEMORY_CAPABILITIES, MemoryProvider

_BUILTINS = {
    "cloudsim": (CloudSimProvider, CLOUDSIM_CAPABILITIES),
    "codebase": (CodebaseProvider, CODEBASE_CAPABILITIES),
    "discovered": (GenericDiscoveredProvider, (DISCOVERED_RUN_CAPABILITY,)),
    "filesystem": (FilesystemProvider, FILESYSTEM_CAPABILITIES),
    "ggen": (GgenProvider, GGEN_CAPABILITIES),
    "ggen-legacy": (GgenLegacyVerifierProvider, GGEN_LEGACY_CAPABILITIES),
    "git": (GitProvider, GIT_CAPABILITIES),
    "http-json": (HTTPJSONProvider, HTTP_JSON_CAPABILITIES),
    "kubernetes-reconciliation": (
        KubernetesReconciliationProvider,
        KUBERNETES_RECONCILIATION_CAPABILITIES,
    ),
    "mcp-client-session": (
        McpClientSessionProvider,
        (MCP_LIST_TOOLS_CAPABILITY, MCP_CALL_TOOL_CAPABILITY),
    ),
    "memory": (MemoryProvider, MEMORY_CAPABILITIES),
    "multicloud": (MulticloudProvider, MULTICLOUD_CAPABILITIES),
    "sqlite": (SQLiteProvider, SQLITE_CAPABILITIES),
    "sregym": (SREGymProvider, (SREGYM_RUN_CAPABILITY,)),
    "swegym": (SWEGymProvider, (SWEGYM_EVALUATE_CAPABILITY,)),
    "terraform-docker-apply": (
        TerraformDockerApplyProvider,
        TERRAFORM_DOCKER_APPLY_CAPABILITIES,
    ),
    "terraform-plan": (TerraformPlanProvider, TERRAFORM_PLAN_CAPABILITIES),
}


def builtin_provider_names() -> tuple[str, ...]:
    return tuple(sorted(_BUILTINS))


def builtin_capabilities(name: str) -> tuple[Any, ...]:
    try:
        return _BUILTINS[name][1]
    except KeyError as exc:
        raise ValueError(f"UNKNOWN_BUILTIN_PROVIDER:{name}") from exc


def create_builtin_provider(name: str) -> Any:
    try:
        provider_type = _BUILTINS[name][0]
    except KeyError as exc:
        raise ValueError(f"UNKNOWN_BUILTIN_PROVIDER:{name}") from exc
    return provider_type()


def describe_builtin_provider(name: str) -> dict[str, Any]:
    provider = create_builtin_provider(name)
    return {
        "name": name,
        "type": type(provider).__name__,
        "materialization_requires_authority": bool(
            getattr(provider, "materialization_requires_authority", False)
        ),
        "capabilities": [item.model_dump(mode="json") for item in builtin_capabilities(name)],
    }
