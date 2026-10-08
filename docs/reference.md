# API reference

## Runtime

::: gymact.runtime.GymAct

::: gymact.limits.RuntimeLimits

::: gymact.runtime.BoundaryBlocked

## Environment providers

::: gymact.providers.EnvironmentProvider

::: gymact.providers.Environment

::: gymact.providers.MemoryProvider

::: gymact.plugins.ProviderPluginInfo

::: gymact.plugins.ProviderPluginLoad

::: gymact.plugins.discover_provider_plugins

::: gymact.plugins.load_provider_plugin

## Semantic models

::: gymact.models.Capability

::: gymact.models.MaterializationIntent

::: gymact.models.MaterializationResult

::: gymact.models.ActuationIntent

::: gymact.models.ActuationResult

::: gymact.models.VerificationResult

::: gymact.models.Receipt

::: gymact.models.Score

## Authority

::: gymact.authority.AuthorityResolver

::: gymact.authority.DenyAuthorityResolver

::: gymact.authority.AllowListAuthorityResolver

## Evidence

::: gymact.evidence.ReceiptLedger

::: gymact.evidence.EvidenceRecord

::: gymact.evidence.MemoryReceiptLedger

::: gymact.sqlite_ledger.SQLiteReceiptLedger

::: gymact.evidence.evidence_graph

## Scoring

::: gymact.scoring.Scorer

::: gymact.scoring.BinaryVerificationScorer

::: gymact.scoring.score_verification

## Semantic profile and manufacture

::: gymact.semantic.ProfileAuthority

::: gymact.standing.require_standing

::: gymact.process.ConformanceChecker

::: gymact.ocel.receipts_to_ocel

::: gymact.ocel.validate_ocel_log

::: gymact.gyms.codebase.CodebaseProvider

::: gymact.gyms.cube_counter.CubeCounterProvider

::: gymact.gyms.cube_container_counter.CubeContainerCounterProvider

::: gymact.gyms.ggen_legacy.GgenLegacyVerifierProvider

::: gymact.gyms.discovered.GenericDiscoveredProvider

::: gymact.gyms.gymnasium_env.GymnasiumProvider

::: gymact.gyms.mcp_client_session.McpClientSessionProvider

::: gymact.gyms.kubernetes_reconciliation.KubernetesReconciliationProvider

::: gymact.gyms.kubernetes_goat.KubernetesGoatProvider

::: gymact.gyms.terraform_plan.TerraformPlanProvider

::: gymact.gyms.terraform_docker_apply.TerraformDockerApplyProvider

::: gymact.gyms.tau2_bench.Tau2BenchProvider

::: gymact.gyms.terminal_bench.TerminalBenchProvider

::: gymact.gyms.inspect_evals.InspectEvalsProvider


::: gymact.gyms.vendor_benchmarks.VendorBenchmarkProvider

::: gymact.contract.RuntimeContract

::: gymact.contract.build_contract

::: gymact.manufacture.export_manufacturing_bundle

## Skill courts

Provenance-qualified collective skill courts bound to the existing DCM
decision court (`src/gymact/skill_court.py`; the types below are re-exported
via `gymact.dcm.__all__`, the README-declared canonical public API). The
expected bundle schema is `collective-skill-court.v1` (`EXPECTED_SCHEMA`),
the authority ceiling is `OBSERVE|SELECT|CONSTRUCT`, and the marketplace
contract binding is pinned to `seanchatmangpt/ggen-marketplace` +
`collective-skill-court-pack` (`MarketplaceContractBinding`). Skill courts
admit a marketplace bundle into the DCM graph court for bounded exploration
only; irreversible selection/execution remain separate APIs.

::: gymact.skill_court.SkillCourtQualification

::: gymact.skill_court.SkillCourtProbe

::: gymact.skill_court.SkillCourtContract

::: gymact.skill_court.SkillBoundDecisionCourtRecord

::: gymact.skill_court.MarketplaceContractBinding

::: gymact.skill_court.CollectiveSkillCourtEvaluator

::: gymact.skill_court.CollectiveSkillCourtBundle

## Execution loop

Autonomous ALOOP-style episode kernel (`src/gymact/execution_loop.py`):
ExecutionRequest -> ExecutionProvider -> ExecutionReceipt with fault handling
that never terminates by waiting for a human. Legal terminal outcomes are
exactly the five `LegalOutcome` values (Recover, Replan, Substitute, Refuse,
TypedBlock); `WaitForHumanToNotice` is named only as `IllegalOutcome` and is
proven unreachable by court. Every transition emits a real OCEL 2.0 event
(`execution.start`/`execution.claim`/`actuation`/`execution.crash`,
`failure.detect`, `reconcile.retry`/`reconcile.replan`, `provider.replace`,
`verification`, `receipt.emit`, `refuse`, `typed.block`). All execution in the
accompanying court is simulated in-process; nothing here actuates production.

Actuation accounting is kernel-owned: each witnessed actuation (an effect
returned by `execute`, or a journal fragment recovered after a post-actuation
crash) appends one ledger entry and one `actuation` event, and
`LoopResult.actuation_count` is the ledger length on every terminal, never a
provider-reported number. A replan that re-executes is receipted as a second
actuation (`commands`/`consequences` list every entry; `ext["aloup.actuations"]`
marks each `superseded` or `admitted`). A post-actuation SHA equal to the claim
pin or to the effect's declared `subject_after_sha` is the actuation's own
consequence; any other SHA is an external move, on the live and the
journal-reconstruction path alike.

Exactly-once holds across redelivery: a run that actuated but ended without an
admitted receipt is remembered by idempotency key, and redelivering the same
request typed-blocks with `TYPED_BLOCK_PRIOR_ACTUATION_UNRECONCILED`
(`R_missing_consequence`) and zero new actuations instead of executing again.
Identity fields (work order, capabilities, repo, evidence requirements) must
contain a visible character; zero-width and format characters do not count.

::: gymact.execution_loop.AuthorityGrant

::: gymact.execution_loop.AutonomousLoop

::: gymact.execution_loop.BrokenTerm

::: gymact.execution_loop.EpisodeStanding

::: gymact.execution_loop.ExecutionProvider

::: gymact.execution_loop.ExecutionReceipt

::: gymact.execution_loop.ExecutionRequest

::: gymact.execution_loop.IllegalOutcome

::: gymact.execution_loop.LegalOutcome

::: gymact.execution_loop.LoopBudgetExceeded

::: gymact.execution_loop.LoopResult

::: gymact.execution_loop.LOOP_OCEL_EVENT_TYPES

::: gymact.execution_loop.LOOP_OCEL_OBJECT_TYPES

::: gymact.execution_loop.OcelEvent

::: gymact.execution_loop.ResourceConstraints

::: gymact.execution_loop.SubjectRef

::: gymact.execution_loop.WorkerCrashed

::: gymact.execution_loop.loop_log

## SA2A replan envelope

Portable SA2A replanning envelope consumed by GymAct
(`src/gymact/sa2a_envelope.py`): the consequence/recovery decision is
manufactured upstream by ash_a2a; GymAct validates that contract and carries it
as data, deliberately containing no outcome->recovery mapping. The envelope is
pinned to `sa2a/replan-envelope/v1` and its contract digest; `SA2AReplanEnvelope`
and `SA2ARecoveryDirective` both carry `exact_subject` (any JSON value) and
`receipt_id`, and every consumer holds authority `"none"` — the envelope is
consumed non-actuatingly.

`exact_subject` admits every JSON value except null; numbers (recursively,
through lists and objects) must be finite. Violations refuse as
`SA2A_EXACT_SUBJECT_REQUIRED` (null) and `SA2A_EXACT_SUBJECT_NONFINITE_NUMBER`
(NaN/Infinity, renamed from `SA2A_EXACT_SUBJECT_NOT_CANONICAL_JSON` in `2e6dca0`,
2026-09-29). Consumers live in `src/gymact/sa2a_consumer.py` (powerless GymAct
consumer; refuses a subject mismatch with `SA2A_EXACT_SUBJECT_MISMATCH`),
`src/gymact/sa2a_evolution.py` (powerless feedback projection for environment
evolution), and `src/gymact/sa2a_replay.py` (replay identity imported from the
envelope).

::: gymact.sa2a_envelope.SA2ADecision

::: gymact.sa2a_envelope.SA2AReplanEnvelope

::: gymact.sa2a_envelope.SA2ARecoveryDirective

::: gymact.sa2a_envelope.admit_envelope
