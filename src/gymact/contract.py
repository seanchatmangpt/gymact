"""Portable semantic/runtime contract for cross-language manufacture."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from gymact.action_contract import ActionDefinition, ExecutionGrant, PreparedAction
from gymact.brce import BrokerRequest
from gymact.evidence import digest
from gymact.experiments import (
    AntiAgentPoint,
    CompileOutReport,
    FaultPlan,
    IntelligenceRun,
    SelfPlayReport,
    TransitionEconomics,
)
from gymact.intelligence import CompileOutObservation, SelectionDecision
from gymact.lab import ActionProjection, ForwardBenchSubject, ProblemSignature
from gymact.models import (
    ActuationIntent,
    MaterializationIntent,
    Operation,
    Receipt,
    VerificationResult,
)
from gymact.physical import (
    EdgeControllerArtifact,
    PhysicalCommand,
    PhysicalProviderProfile,
    SafetyEnvelope,
)
from gymact.provider_spi import (
    ObservationRequest,
    ProviderExecutionAttempt,
    ProviderPreparation,
    ProviderRollbackResult,
)
from gymact.replay import ReplayExpectation, ReplayReport
from gymact.semantic import ProfileAuthority
from gymact.transport import CandidateIntentEnvelope

PUBLIC_SEMANTICS = (
    "http://www.w3.org/ns/dx/prof/",
    "http://www.w3.org/ns/prov#",
    "http://purl.org/net/p-plan#",
    "http://www.w3.org/ns/sosa/",
    "https://www.w3.org/2019/wot/td#",
    "http://www.w3.org/ns/odrl/2/",
    "http://www.w3.org/ns/shacl#",
    "http://www.w3.org/ns/earl#",
    "http://www.w3.org/ns/dqv#",
    "http://qudt.org/schema/qudt/",
    "http://www.w3.org/ns/dcat#",
    "http://www.w3.org/2004/02/skos/core#",
    "http://www.w3.org/2006/time#",
    "http://purl.org/dc/terms/",
)


class RuntimeContract(BaseModel):
    """Stable contract consumable by ggen, Rust/WIT/WASM or independent checkers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gymact_version: str
    profile_uri: str
    canonicalization: str
    digest_algorithm: str
    operations: tuple[str, ...]
    surfaces: tuple[str, ...]
    public_semantics: tuple[str, ...]
    schemas: dict[str, dict[str, object]]
    contract_digest: str

    def verify_digest(self) -> bool:
        """Recompute the contract digest without trusting the stored value."""
        payload = self.model_dump(mode="json", exclude={"contract_digest"})
        return digest(payload) == self.contract_digest


def build_contract(version: str = "26.8.7") -> RuntimeContract:
    """Build and self-digest the admitted Python and Crown semantic contract."""
    payload = {
        "gymact_version": version,
        "profile_uri": ProfileAuthority.profile_uri,
        "canonicalization": "RFC8785-JCS",
        "digest_algorithm": "blake3-256",
        "operations": tuple(operation.value for operation in Operation),
        "surfaces": (
            "python",
            "pydantic",
            "brce",
            "fastapi",
            "openapi",
            "fastmcp",
            "typer",
            "faststream",
            "http-json",
            "rdf",
            "json-ld",
            "ocel",
            "pddl",
            "ppddl",
            "rddl",
            "powl-v2",
            "bpmn",
            "a2a",
            "robotics-profile",
            "industrial-ot-profile",
            "edge-controller-profile",
        ),
        "public_semantics": PUBLIC_SEMANTICS,
        "schemas": {
            "materialization_intent": MaterializationIntent.model_json_schema(),
            "actuation_intent": ActuationIntent.model_json_schema(),
            "verification_result": VerificationResult.model_json_schema(),
            "receipt": Receipt.model_json_schema(),
            "action_definition": ActionDefinition.model_json_schema(),
            "prepared_action": PreparedAction.model_json_schema(),
            "execution_grant": ExecutionGrant.model_json_schema(),
            "broker_request": BrokerRequest.model_json_schema(),
            "candidate_intent_envelope": CandidateIntentEnvelope.model_json_schema(),
            "problem_signature": ProblemSignature.model_json_schema(),
            "action_projection": ActionProjection.model_json_schema(),
            "forwardbench_subject": ForwardBenchSubject.model_json_schema(),
            "observation_request": ObservationRequest.model_json_schema(),
            "provider_preparation": ProviderPreparation.model_json_schema(),
            "provider_execution_attempt": ProviderExecutionAttempt.model_json_schema(),
            "provider_rollback_result": ProviderRollbackResult.model_json_schema(),
            "selection_decision": SelectionDecision.model_json_schema(),
            "compile_out_observation": CompileOutObservation.model_json_schema(),
            "replay_expectation": ReplayExpectation.model_json_schema(),
            "replay_report": ReplayReport.model_json_schema(),
            "safety_envelope": SafetyEnvelope.model_json_schema(),
            "physical_command": PhysicalCommand.model_json_schema(),
            "physical_provider_profile": PhysicalProviderProfile.model_json_schema(),
            "edge_controller_artifact": EdgeControllerArtifact.model_json_schema(),
            "fault_plan": FaultPlan.model_json_schema(),
            "self_play_report": SelfPlayReport.model_json_schema(),
            "transition_economics": TransitionEconomics.model_json_schema(),
            "anti_agent_point": AntiAgentPoint.model_json_schema(),
            "intelligence_run": IntelligenceRun.model_json_schema(),
            "compile_out_report": CompileOutReport.model_json_schema(),
        },
    }
    return RuntimeContract(**payload, contract_digest=digest(payload))
