"""GENERATED from ggen/sregym-e2e-pack/ontology.ttl. DO NOT HAND EDIT.

This checked-in projection is consumed by the Python runtime.  The ontology is
the semantic source of truth; tests compare this projection back to that graph.
"""
from __future__ import annotations

SREGYM_UPSTREAM_REVISION = "ba07faf1a322f9b6d4a279643bb796aa2f36f64b"

SREGYM_CAPABILITY_ROWS = (
    {"iri": "urn:gymact:sregym:capability:observe_cluster_state", "title": "Read SREGym conductor status", "binding": "observe_cluster_state", "consequence": "READ", "route": "/status", "tool_name": None},
    {"iri": "urn:gymact:sregym:capability:get_benchmark_status", "title": "Read SREGym benchmark stage", "binding": "get_benchmark_status", "consequence": "READ", "route": "/status", "tool_name": None},
    {"iri": "urn:gymact:sregym:capability:run_kubectl", "title": "Execute kubectl through SREGym kubectl MCP", "binding": "run_kubectl", "consequence": "DO", "route": "/kubectl/sse", "tool_name": "exec_kubectl_cmd_safely"},
    {"iri": "urn:gymact:sregym:capability:submit_diagnosis", "title": "Submit diagnosis through SREGym submit MCP", "binding": "submit_diagnosis", "consequence": "DO", "route": "/submit_mcp/sse", "tool_name": "submit"},
    {"iri": "urn:gymact:sregym:capability:submit_mitigation", "title": "Submit mitigation through SREGym submit MCP", "binding": "submit_mitigation", "consequence": "DO", "route": "/submit_mcp/sse", "tool_name": "submit"},
    {"iri": "urn:gymact:sregym:capability:jaeger_get_services", "title": "Jaeger get_services", "binding": "jaeger_get_services", "consequence": "READ", "route": "/jaeger/sse", "tool_name": "get_services"},
    {"iri": "urn:gymact:sregym:capability:jaeger_get_operations", "title": "Jaeger get_operations", "binding": "jaeger_get_operations", "consequence": "READ", "route": "/jaeger/sse", "tool_name": "get_operations"},
    {"iri": "urn:gymact:sregym:capability:jaeger_get_traces", "title": "Jaeger get_traces", "binding": "jaeger_get_traces", "consequence": "READ", "route": "/jaeger/sse", "tool_name": "get_traces"},
    {"iri": "urn:gymact:sregym:capability:jaeger_get_dependency_graph", "title": "Jaeger get_dependency_graph", "binding": "jaeger_get_dependency_graph", "consequence": "READ", "route": "/jaeger/sse", "tool_name": "get_dependency_graph"},
    {"iri": "urn:gymact:sregym:capability:loki_get_logs", "title": "Loki get_logs", "binding": "loki_get_logs", "consequence": "READ", "route": "/loki/sse", "tool_name": "get_logs"},
    {"iri": "urn:gymact:sregym:capability:loki_get_labels", "title": "Loki get_labels", "binding": "loki_get_labels", "consequence": "READ", "route": "/loki/sse", "tool_name": "get_labels"},
    {"iri": "urn:gymact:sregym:capability:loki_get_label_values", "title": "Loki get_label_values", "binding": "loki_get_label_values", "consequence": "READ", "route": "/loki/sse", "tool_name": "get_label_values"},
    {"iri": "urn:gymact:sregym:capability:prometheus_get_metrics", "title": "Prometheus get_metrics", "binding": "prometheus_get_metrics", "consequence": "READ", "route": "/prometheus/sse", "tool_name": "get_metrics"},
    {"iri": "urn:gymact:sregym:capability:prometheus_get_alerts", "title": "Prometheus get_alerts", "binding": "prometheus_get_alerts", "consequence": "READ", "route": "/prometheus/sse", "tool_name": "get_alerts"},
)

SREGYM_LITE_PROBLEMS = (
    "admission_webhook_outage_hotel_reservation",
    "cronjob_sidecar_blocks_completion_hotel_reservation",
    "duplicate_pvc_mounts_social_network",
    "edge_request_filter_cpu_saturation",
    "env_variable_shadowing_astronomy_shop",
    "finalizer_deadlock_controller_hotel_reservation",
    "internal_traffic_policy_local_astronomy_shop",
    "kafka_poison_pill_hol_block",
    "mutating_webhook_resource_limits_social_network",
    "namespace_memory_limit",
    "network_policy_block",
    "readiness_probe_misconfiguration_social_network",
    "rolling_update_misconfigured_social_network",
    "search_rate_retry_collapse_hotel_reservation",
    "secret_rotation_stale_env_credentials_astronomy_shop",
    "service_dns_resolution_failure_social_network",
    "service_wrong_pod_selection_hotel_reservation",
    "unschedulable_incorrect_port_assignment",
    "valkey_auth_disruption",
    "wrong_dns_policy_astronomy_shop",
    "wrong_service_selector_social_network",
)

_WRONG_DNS = "SREGym/SREGym@ba07faf1a322f9b6d4a279643bb796aa2f36f64b:sregym/conductor/problems/wrong_dns_policy.py#WrongDNSPolicy.recover_fault;blob=630627e4c4d3f69f477e857252972b397757f68c"
_WRONG_DNS_INJECTOR = "SREGym/SREGym@ba07faf1a322f9b6d4a279643bb796aa2f36f64b:sregym/generators/fault/inject_virtual.py#VirtualizationFaultInjector.recover_wrong_dns_policy"
_INTERNAL_TRAFFIC = "SREGym/SREGym@ba07faf1a322f9b6d4a279643bb796aa2f36f64b:sregym/conductor/problems/internal_traffic_policy_local.py#InternalTrafficPolicyLocalAstronomyShop.recover_fault;blob=4264df2c1b88845df120aec09bb9583292f652d4"

PROGRAM_SOURCE_ROWS = (
    ("internal_traffic_policy_local_astronomy_shop", _INTERNAL_TRAFFIC),
    ("wrong_dns_policy_astronomy_shop", _WRONG_DNS),
    ("wrong_dns_policy_astronomy_shop", _WRONG_DNS_INJECTOR),
)

PROGRAM_STEP_ROWS = (
    ("internal_traffic_policy_local_astronomy_shop", 1, "urn:gymact:sregym:capability:submit_diagnosis", {"component": "service/recommendation", "cause": "internalTrafficPolicy=Local plus pinned recommendation/frontend pods causes cross-node in-cluster requests to be dropped", "gdmcp_source": _INTERNAL_TRAFFIC}, "submit the source-grounded diagnosis; no model inference", _INTERNAL_TRAFFIC),
    ("internal_traffic_policy_local_astronomy_shop", 2, "urn:gymact:sregym:capability:run_kubectl", {"command": "kubectl patch service recommendation -n {{namespace}} --type=merge -p '{\"spec\":{\"internalTrafficPolicy\":\"Cluster\"}}'"}, "restore cluster-wide service routing", _INTERNAL_TRAFFIC),
    ("internal_traffic_policy_local_astronomy_shop", 3, "urn:gymact:sregym:capability:run_kubectl", {"command": "kubectl patch deployment recommendation -n {{namespace}} --type=merge -p '{\"spec\":{\"template\":{\"spec\":{\"nodeSelector\":null}}}}'"}, "remove fault-only recommendation node pinning", _INTERNAL_TRAFFIC),
    ("internal_traffic_policy_local_astronomy_shop", 4, "urn:gymact:sregym:capability:run_kubectl", {"command": "kubectl rollout restart deployment/recommendation -n {{namespace}}"}, "restart recommendation after topology repair", _INTERNAL_TRAFFIC),
    ("internal_traffic_policy_local_astronomy_shop", 5, "urn:gymact:sregym:capability:run_kubectl", {"command": "kubectl patch deployment frontend -n {{namespace}} --type=merge -p '{\"spec\":{\"template\":{\"spec\":{\"nodeSelector\":null}}}}'"}, "remove fault-only frontend node pinning", _INTERNAL_TRAFFIC),
    ("internal_traffic_policy_local_astronomy_shop", 6, "urn:gymact:sregym:capability:run_kubectl", {"command": "kubectl rollout restart deployment/frontend -n {{namespace}}"}, "restart frontend after topology repair", _INTERNAL_TRAFFIC),
    ("internal_traffic_policy_local_astronomy_shop", 7, "urn:gymact:sregym:capability:run_kubectl", {"command": "kubectl rollout status deployment/recommendation -n {{namespace}} --timeout=180s"}, "wait for recommendation convergence", _INTERNAL_TRAFFIC),
    ("internal_traffic_policy_local_astronomy_shop", 8, "urn:gymact:sregym:capability:run_kubectl", {"command": "kubectl rollout status deployment/frontend -n {{namespace}} --timeout=180s"}, "wait for frontend convergence", _INTERNAL_TRAFFIC),
    ("internal_traffic_policy_local_astronomy_shop", 9, "urn:gymact:sregym:capability:submit_mitigation", {"action": "restored internalTrafficPolicy=Cluster, removed both injected nodeSelectors, and waited for both deployments to roll out", "gdmcp_source": _INTERNAL_TRAFFIC}, "submit the deterministic mitigation evidence", _INTERNAL_TRAFFIC),
    ("wrong_dns_policy_astronomy_shop", 1, "urn:gymact:sregym:capability:submit_diagnosis", {"component": "frontend", "cause": "deployment frontend has dnsPolicy=None and an external 8.8.8.8 resolver, breaking cluster-internal DNS resolution", "gdmcp_source": _WRONG_DNS}, "submit the source-grounded diagnosis; no model inference", _WRONG_DNS),
    ("wrong_dns_policy_astronomy_shop", 2, "urn:gymact:sregym:capability:run_kubectl", {"command": "kubectl patch deployment frontend -n {{namespace}} --type=json -p='[{\"op\":\"remove\",\"path\":\"/spec/template/spec/dnsPolicy\"},{\"op\":\"remove\",\"path\":\"/spec/template/spec/dnsConfig\"}]'"}, "restore the deployment to normal ClusterFirst DNS semantics", _WRONG_DNS_INJECTOR),
    ("wrong_dns_policy_astronomy_shop", 3, "urn:gymact:sregym:capability:run_kubectl", {"command": "kubectl rollout status deployment frontend -n {{namespace}} --timeout=120s"}, "wait for the repaired deployment to become stable", _WRONG_DNS_INJECTOR),
    ("wrong_dns_policy_astronomy_shop", 4, "urn:gymact:sregym:capability:submit_mitigation", {"action": "removed the injected dnsPolicy/dnsConfig override and waited for the frontend rollout", "gdmcp_source": _WRONG_DNS_INJECTOR}, "submit the deterministic mitigation evidence", _WRONG_DNS_INJECTOR),
)
