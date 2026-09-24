from __future__ import annotations

import pytest

from gymact import dcm
from gymact.action_contract import (
    ActionDefinition,
    AuthorityRequirement,
    ExpectedEffect,
    ReversalClass,
    SubjectRef,
    VerificationKind,
    VerificationStrategy,
)
from gymact.action_graph import action_possibility_fragment
from gymact.combinatorial import AdmissionContext, PossibilityObjectKind
from gymact.dcm_runtime import DecisionCourtRequest
from gymact.evidence import digest
from gymact.models import Standing
from gymact.skill_court import (
    CollectiveSkillCourtBundle,
    CollectiveSkillCourtEvaluator,
    MarketplaceContractBinding,
    SkillCourtContract,
    SkillCourtProbe,
)

MARKETPLACE_SHA = "02c13c468892c040c8abfd5023db4c1a19fa4820"
AUTOFDE_BASE_SHA = "29ffb8f9749b0b693579bc68c7f61ac15b16841f"
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64
DIGEST_E = "sha256:" + "e" * 64
DIGEST_F = "sha256:" + "f" * 64


def contract() -> SkillCourtContract:
    return SkillCourtContract(
        schema="collective-skill-court.v1",
        authority_ceiling="OBSERVE|SELECT|CONSTRUCT",
        grants_do_authority=False,
        projections={
            "sjira_work_order": "urn:seanchatmangpt:sjira:v1#WorkOrder",
            "sa2a_candidate": "https://spec.autofde.org/sa2a#Candidate",
        },
        requires={
            "source_provenance": True,
            "exact_marketplace_pin": True,
            "exact_subject_pin": True,
            "replay_identity": True,
            "oracle_pass": True,
            "noop_fail": True,
            "mutation_rejection": True,
        },
        admission=(
            "oracle_pass && noop_fail && mutation_rejection && "
            "!grants_do_authority"
        ),
    )


def bundle(
    *,
    oracle_success: bool = True,
    noop_success: bool = False,
    mutation_success: bool = False,
    contract_digest_override: str | None = None,
) -> CollectiveSkillCourtBundle:
    projected = contract()
    contract_digest = "blake3:" + digest(projected.model_dump(mode="json"))
    return CollectiveSkillCourtBundle(
        bundle_id="court:chicago-domain-solver:repair-01",
        marketplace=MarketplaceContractBinding(
            repository="seanchatmangpt/ggen-marketplace",
            commit_sha=MARKETPLACE_SHA,
            pack_name="collective-skill-court-pack",
            pack_version="26.9.24",
            contract_digest=contract_digest_override or contract_digest,
        ),
        contract=projected,
        source_skill_digest=DIGEST_A,
        source_court_receipt_digest=DIGEST_B,
        sjira_work_order_id="AFDE-CSKILL-26924-001",
        sjira_base_sha=AUTOFDE_BASE_SHA,
        sa2a_candidate_digest=DIGEST_C,
        sa2a_admission_receipt_digest=DIGEST_D,
        exact_subject_sha=AUTOFDE_BASE_SHA,
        oracle=SkillCourtProbe(
            probe_id="oracle",
            kind="oracle",
            observed_success=oracle_success,
            evidence_digest=DIGEST_E,
        ),
        noop=SkillCourtProbe(
            probe_id="noop",
            kind="noop",
            observed_success=noop_success,
            evidence_digest=DIGEST_F,
        ),
        mutations=(
            SkillCourtProbe(
                probe_id="skip-verifier",
                kind="mutation",
                observed_success=mutation_success,
                evidence_digest=DIGEST_A,
            ),
        ),
    )


def decision_request() -> DecisionCourtRequest:
    subject = SubjectRef(
        semantic_id="urn:skill-court:subject",
        provider_ref="provider-subject",
        revision="rev-1",
    )
    action = ActionDefinition(
        semantic_id="urn:skill-court:action",
        provider_ref="urn:provider:memory",
        capability_ref="urn:capability:set",
        subject_type="schema:Thing",
        input_schema={"type": "object"},
        authority=AuthorityRequirement(policy_refs=("urn:policy:auto",)),
        expected_effects=(ExpectedEffect(predicate="state", parameters={"x": 2}),),
        verification=VerificationStrategy(
            kind=VerificationKind.EXACT_STATE,
            observer_ref="urn:verifier:memory",
            expected={"x": 2},
        ),
        reversal=ReversalClass.REVERSIBLE,
    )
    graph = action_possibility_fragment(action, subject)
    start = next(
        item
        for item in graph.objects
        if item.kind is PossibilityObjectKind.SUBJECT
    )
    return DecisionCourtRequest(
        graph=graph,
        start_ids=(start.object_id,),
        context=AdmissionContext(
            capability_refs=(action.capability_ref,),
            policy_refs=("urn:policy:auto",),
            current_revision="rev-1",
            execution_grant_ref="urn:grant:admitted",
        ),
    )


def test_admitted_skill_bundle_enters_dcm_exploration_without_do_authority() -> None:
    evaluator = CollectiveSkillCourtEvaluator()
    value = bundle()

    record = evaluator.admit_and_explore(value, decision_request())

    assert record.bundle_digest == value.bundle_digest
    assert record.qualification.admitted is True
    assert record.qualification.standing is Standing.STRUCTURAL
    assert record.qualification.authority == "none"
    assert record.decision_court.rdf_validation.conforms
    assert record.decision_court.exploration.truncated is False
    assert len(record.decision_court.exploration.irreversible_frontier) == 1
    assert "CollectiveSkillCourtEvaluator" in dcm.__all__


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"oracle_success": False}, "ORACLE_FAILED"),
        ({"noop_success": True}, "NOOP_PASSED"),
        ({"mutation_success": True}, "MUTATION_SURVIVED:skip-verifier"),
    ],
)
def test_failed_discriminator_refuses_before_dcm_exploration(kwargs, reason) -> None:
    evaluator = CollectiveSkillCourtEvaluator()
    value = bundle(**kwargs)

    qualification = evaluator.qualify(value)

    assert qualification.admitted is False
    assert qualification.standing is Standing.REFUSED
    assert reason in qualification.reasons
    with pytest.raises(ValueError, match="COLLECTIVE_SKILL_COURT_REFUSED"):
        evaluator.admit_and_explore(value, decision_request())


def test_marketplace_contract_digest_is_bound_to_bundle() -> None:
    with pytest.raises(ValueError, match="COLLECTIVE_SKILL_CONTRACT_DIGEST_MISMATCH"):
        bundle(contract_digest_override="blake3:" + "0" * 64)
