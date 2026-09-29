# GymAct standing census

- Command: `python scripts/standing_census.py --markdown`
- Tree git HEAD: `61293b8`

**pytest-passing != actuated.** A `tests/test_<gym>*.py` file (or a green run of it) is
a claim about `request accepted`. Only a real, schema-valid, conformant-replay log with
a real `act` event carrying `solved=True` counts as ACTUATED here, derived directly from
`reports/ocel/<subject>/episode.ocel.json` per `.claude/rules/ocel-standing.md`.
This census is a measurement of committed logs; it is not a release-standing claim and
it does not re-run any episode.

## Headline

- Providers in roster: **42** (27 registered builtins, 15 unregistered Provider classes)
- ACTUATED: **7**
- NOT_RUN (no log): **34**
- Named gap (log exists, not ACTUATED): **1** {'NO_SOLVED_ACT': 1}
- Have a test file: 32 (of which not ACTUATED: 25)
- Logs under reports/ocel matching no roster subject: 3 (0 ACTUATED)

## Roster

| subject | registered | provider class | OCEL standing | schema | conformant | act / solved | test file | detail |
|---|---|---|---|---|---|---|---|---|
| browsergym | False | BrowserGymProvider | NOT_RUN | - | - | - | test_browsergym_edges.py, test_browsergym_gym.py | no episode.ocel.json for this subject |
| chatman-state | True | ChatmanStateProvider | NOT_RUN | - | - | - | test_chatman_state.py, test_chatman_state_gym.py | no episode.ocel.json for this subject |
| cloud-topology | True | CloudTopologyProvider | NOT_RUN | - | - | - | test_cloud_topology.py, test_cloud_topology_validation.py | no episode.ocel.json for this subject |
| cloudsim | True | CloudSimProvider | NOT_RUN | - | - | - | test_cloudsim.py | no episode.ocel.json for this subject |
| codebase | True | CodebaseProvider | ACTUATED | True | True | 8 / 1 | test_codebase.py, test_codebase_clone_at_ref.py, test_codebase_crown.py, test_codebase_dispatch.py, test_codebase_ontology.py, test_codebase_restore.py | 1/8 act event(s) carry solved=True |
| commerce-dfcm | True | CommerceDfcmProvider | NOT_RUN | - | - | - | test_commerce_dfcm.py, test_commerce_dfcm_billing_fence.py, test_commerce_dfcm_enterprise.py, test_commerce_dfcm_graph.py, test_commerce_dfcm_gym.py, test_commerce_dfcm_orchestration.py, test_commerce_dfcm_runtime.py | no episode.ocel.json for this subject |
| cube-container-counter | False | CubeContainerCounterProvider | NOT_RUN | - | - | - | test_cube_container_counter.py | no episode.ocel.json for this subject |
| cube-counter | False | CubeCounterProvider | NOT_RUN | - | - | - | test_cube_counter.py | no episode.ocel.json for this subject |
| dependency-world | False | DependencyWorldProvider | NOT_RUN | - | - | - | - | no episode.ocel.json for this subject |
| dev-portfolio | True | DevPortfolioProvider | NOT_RUN | - | - | - | test_dev_portfolio.py | no episode.ocel.json for this subject |
| discovered | True | GenericDiscoveredProvider | NOT_RUN | - | - | - | test_discovered_authority.py | no episode.ocel.json for this subject |
| enterprise-company | True | EnterpriseCompanyProvider | NOT_RUN | - | - | - | - | no episode.ocel.json for this subject |
| filesystem | True | FilesystemProvider | NOT_RUN | - | - | - | - | no episode.ocel.json for this subject |
| ggen | True | GgenProvider | NOT_RUN | - | - | - | test_ggen_agent.py, test_ggen_gym_contract.py, test_ggen_legacy_gym.py, test_ggen_post_agi_pack.py, test_ggen_protocol_gym_pack.py, test_ggen_togaf_gym_pack.py, test_ggen_world_cyber_pack.py | no episode.ocel.json for this subject |
| ggen-legacy | True | GgenLegacyVerifierProvider | NOT_RUN | - | - | - | test_ggen_legacy_gym.py | no episode.ocel.json for this subject |
| git | True | GitProvider | NOT_RUN | - | - | - | - | no episode.ocel.json for this subject |
| gymnasium-env | False | GymnasiumProvider | NOT_RUN | - | - | - | test_gymnasium_env.py | no episode.ocel.json for this subject |
| http-json | True | HTTPJSONProvider | NOT_RUN | - | - | - | - | no episode.ocel.json for this subject |
| inspect-evals | False | InspectEvalsProvider | NOT_RUN | - | - | - | test_inspect_evals.py | no episode.ocel.json for this subject |
| k8s-resource | True | K8sResourceProvider | NOT_RUN | - | - | - | test_k8s_resource_gym.py | no episode.ocel.json for this subject |
| kubernetes-goat | False | KubernetesGoatProvider | NOT_RUN | - | - | - | test_kubernetes_goat.py | no episode.ocel.json for this subject |
| kubernetes-reconciliation | True | KubernetesReconciliationProvider | NOT_RUN | - | - | - | test_kubernetes_reconciliation.py | no episode.ocel.json for this subject |
| lock-and-key | True | LockAndKeyProvider | ACTUATED | True | True | 13 / 1 | test_lock_and_key.py | 1/13 act event(s) carry solved=True |
| mcp-client-session | True | McpClientSessionProvider | ACTUATED | True | True | 1 / 1 | test_mcp_client_session.py, test_mcp_client_session_ontology.py | 1/1 act event(s) carry solved=True |
| memory | True | MemoryProvider | NOT_RUN | - | - | - | - | no episode.ocel.json for this subject |
| multicloud | True | MulticloudProvider | NOT_RUN | - | - | - | test_multicloud.py | no episode.ocel.json for this subject |
| ontology-gym | False | OntologyDrivenProvider | NOT_RUN | - | - | - | test_ontology_gym.py | no episode.ocel.json for this subject |
| opaque-procedure | False | OpaqueProcedureProvider | NO_SOLVED_ACT | True | True | 2 / 0 | - | 2 act event(s), none carry solved=True; reasons=[] |
| platform-console | True | PlatformConsoleProvider | NOT_RUN | - | - | - | test_platform_console_provider.py | no episode.ocel.json for this subject |
| platform-console-ontology-provider | False | PlatformConsoleOntologyDrivenProvider | NOT_RUN | - | - | - | - | no episode.ocel.json for this subject |
| resource-flow | True | ResourceFlowProvider | ACTUATED | True | True | 9 / 1 | test_resource_flow.py | 1/9 act event(s) carry solved=True |
| shared-dependency-world | False | SharedDependencyWorldProvider | NOT_RUN | - | - | - | - | no episode.ocel.json for this subject |
| sqlite | True | SQLiteProvider | NOT_RUN | - | - | - | - | no episode.ocel.json for this subject |
| sregym | True | SregymOntologyProvider | NOT_RUN | - | - | - | test_sregym_mcp_ontology.py, test_sregym_mcp_shacl.py, test_sregym_provider.py | no episode.ocel.json for this subject |
| sregym-vendor | False | SregymVendorProvider | NOT_RUN | - | - | - | test_sregym_mcp_ontology.py, test_sregym_mcp_shacl.py, test_sregym_provider.py | no episode.ocel.json for this subject |
| swegym | True | SWEGymProvider | NOT_RUN | - | - | - | test_swegym.py, test_swegym_live.py | no episode.ocel.json for this subject |
| switchboard | True | SwitchboardProvider | ACTUATED | True | True | 5 / 1 | test_switchboard.py | 1/5 act event(s) carry solved=True |
| tau2-bench | False | Tau2BenchProvider | NOT_RUN | - | - | - | test_tau2_bench.py | no episode.ocel.json for this subject |
| terminal-bench | False | TerminalBenchProvider | NOT_RUN | - | - | - | test_terminal_bench.py | no episode.ocel.json for this subject |
| terraform-docker-apply | True | TerraformDockerApplyProvider | ACTUATED | True | True | 2 / 1 | test_terraform_docker_apply.py | 1/2 act event(s) carry solved=True |
| terraform-plan | True | TerraformPlanProvider | ACTUATED | True | True | 1 / 1 | test_terraform_plan.py | 1/1 act event(s) carry solved=True |
| vendor-benchmarks | False | VendorBenchmarkProvider | NOT_RUN | - | - | - | test_vendor_benchmarks.py | no episode.ocel.json for this subject |

## Logs matching no roster subject

| subject | OCEL standing | schema | conformant | act / solved | possible alias | detail |
|---|---|---|---|---|---|---|
| crown-p1-allowed | NO_SOLVED_ACT | True | True | 1 / 0 | - | 1 act event(s), none carry solved=True; reasons=[] |
| crown-p1-denied | NO_SOLVED_ACT | True | True | 1 / 0 | - | 1 act event(s), none carry solved=True; reasons=[] |
| k8s-resources | NO_ACT_EVENT | True | True | 0 / 0 | k8s-resource | schema-valid, conformant, but no act event (bootstrap/read-only only) |

A possible alias is only a naming hint; it does not change the roster subject's
classification (an exact directory-name match is required).

